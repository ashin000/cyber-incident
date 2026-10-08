"""
Admin routes — dashboard, user management, officer management,
case assignment, categories, analytics, report generation.
"""
import os
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, send_file
)
from flask_login import login_required, current_user
from models.user import User
from models.incident import Incident
from models.notification import Notification
from database import fetch_all, fetch_one, execute
from utils.decorators import admin_required
from utils.helpers import paginate, sanitize_input, log_audit, validate_email, validate_password
from utils.reports import generate_pdf_report, generate_excel_report
from utils.mailer import send_status_change_email
from config import Config

admin_bp = Blueprint('admin', __name__)


# ── Admin Dashboard ────────────────────────────────────────────
@admin_bp.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    """Admin analytics dashboard."""
    total_reports = Incident.count()
    pending = Incident.count(status='Pending')
    active = fetch_one(
        "SELECT COUNT(*) AS cnt FROM incidents WHERE status IN ('Assigned','Under Investigation')"
    )['cnt']
    closed = Incident.count(status='Closed')
    resolved = Incident.count(status='Resolved')
    total_users = User.count_by_role('citizen')
    total_officers = User.count_by_role('officer')

    notifications = Notification.get_for_user(current_user.id, limit=10)
    unread_count = Notification.count_unread(current_user.id)

    return render_template('dashboard/admin.html',
                           total_reports=total_reports,
                           pending=pending,
                           active=active,
                           closed=closed,
                           resolved=resolved,
                           total_users=total_users,
                           total_officers=total_officers,
                           notifications=notifications,
                           unread_count=unread_count)


# ── Analytics Data API (JSON for Chart.js) ─────────────────────
@admin_bp.route('/admin/analytics/data')
@login_required
@admin_required
def analytics_data():
    """Return JSON data for Chart.js charts."""
    monthly = Incident.monthly_stats()
    categories = Incident.category_stats()
    resolution = Incident.resolution_rate()
    priority = Incident.priority_stats()
    daily = Incident.daily_stats(30)

    # Convert date objects to strings for JSON
    daily_serialized = []
    for d in daily:
        daily_serialized.append({
            'date': d['date'].strftime('%d %b') if hasattr(d['date'], 'strftime') else str(d['date']),
            'count': d['count']
        })

    return jsonify({
        'monthly': monthly,
        'categories': categories,
        'resolution': resolution,
        'priority': priority,
        'daily': daily_serialized
    })


# ── User Management ───────────────────────────────────────────
@admin_bp.route('/admin/users')
@login_required
@admin_required
def manage_users():
    """List and manage all users."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')

    users, total = User.get_all(
        role=role_filter or None,
        page=page,
        per_page=Config.ITEMS_PER_PAGE,
        search=search or None
    )
    pagination = paginate(total, page, Config.ITEMS_PER_PAGE)

    return render_template('admin/users.html',
                           users=users,
                           pagination=pagination,
                           search=search,
                           role_filter=role_filter)


@admin_bp.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    """Activate / deactivate a user."""
    if user_id == current_user.id:
        flash('You cannot deactivate yourself.', 'danger')
        return redirect(url_for('admin.manage_users'))

    User.toggle_active(user_id)
    log_audit(current_user.id, 'USER_TOGGLED', f'User {user_id} active status toggled')
    flash('User status updated.', 'success')
    return redirect(url_for('admin.manage_users'))


# ── Officer Management ────────────────────────────────────────
@admin_bp.route('/admin/officers', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_officers():
    """List officers and create new ones."""
    if request.method == 'POST':
        full_name = sanitize_input(request.form.get('full_name', ''))
        email = sanitize_input(request.form.get('email', '')).lower()
        phone = sanitize_input(request.form.get('phone', ''))
        password = request.form.get('password', '')
        badge_number = sanitize_input(request.form.get('badge_number', ''))
        department = sanitize_input(request.form.get('department', ''))
        specialization = sanitize_input(request.form.get('specialization', ''))

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not validate_email(email):
            errors.append('Valid email is required.')
        valid_pwd, pwd_msg = validate_password(password)
        if not valid_pwd:
            errors.append(pwd_msg)
        if not badge_number:
            errors.append('Badge number is required.')
        if User.get_by_email(email):
            errors.append('Email already registered.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return redirect(url_for('admin.manage_officers'))

        try:
            user_id = User.create(full_name, email, phone or None, password, role='officer')
            execute(
                """INSERT INTO officers (user_id, badge_number, department, specialization)
                   VALUES (%s, %s, %s, %s)""",
                (user_id, badge_number, department or None, specialization or None)
            )
            log_audit(current_user.id, 'OFFICER_CREATED', f'Officer created: {email}')
            flash('Officer account created successfully!', 'success')
        except Exception as e:
            flash('Failed to create officer.', 'danger')

        return redirect(url_for('admin.manage_officers'))

    # GET — list officers
    officers = fetch_all(
        """SELECT u.*, o.badge_number, o.department, o.specialization,
                  (SELECT COUNT(*) FROM incidents WHERE assigned_officer_id = u.id) AS case_count
           FROM users u
           JOIN officers o ON u.id = o.user_id
           ORDER BY u.created_at DESC"""
    )

    return render_template('admin/officers.html', officers=officers)


# ── Case Assignment ────────────────────────────────────────────
@admin_bp.route('/admin/cases/<int:incident_id>/assign', methods=['GET', 'POST'])
@login_required
@admin_required
def assign_case(incident_id):
    """Assign an officer to a case."""
    incident = Incident.get_by_id(incident_id)
    if not incident:
        flash('Incident not found.', 'danger')
        return redirect(url_for('incident.list_incidents'))

    if request.method == 'POST':
        officer_user_id = request.form.get('officer_id', type=int)
        if not officer_user_id:
            flash('Please select an officer.', 'warning')
            return redirect(url_for('admin.assign_case', incident_id=incident_id))

        Incident.assign_officer(incident_id, officer_user_id, current_user.id)

        # Notify officer
        Notification.create(
            user_id=officer_user_id,
            title='New Case Assigned',
            message=f'You have been assigned case {incident["case_id"]}: {incident["title"]}',
            notif_type='info',
            incident_id=incident_id
        )
        # Notify reporter with formatted message
        officer = User.get_by_id(officer_user_id)
        incident_type = incident.get('incident_type', 'Cyber Incident')
        reporter_msg = f'Your {incident_type} complaint has been assigned.\n\n'
        reporter_msg += f'Complaint Status: Assigned 👮 Your case has been assigned to Officer {officer.full_name}.'
        reporter_msg += f'\n\nThank you for using the Cyber Incident Reporting Portal.'

        Notification.create(
            user_id=incident['user_id'],
            title='Case Assigned',
            message=reporter_msg,
            notif_type='info',
            incident_id=incident_id
        )

        # Email notification to reporter's registered email
        send_status_change_email(
            incident=incident,
            new_status='Assigned',
            old_status=incident.get('status', 'Pending'),
            notes=f'Your case has been assigned to Investigating Officer {officer.full_name}.',
            changed_by_name=f'Administrator ({current_user.full_name})'
        )

        log_audit(current_user.id, 'CASE_ASSIGNED',
                  f'Case {incident["case_id"]} assigned to officer {officer_user_id}')
        flash(f'Case assigned to {officer.full_name}.', 'success')
        return redirect(url_for('incident.view_incident', incident_id=incident_id))

    # GET — show assignment form
    officers = fetch_all(
        """SELECT u.id, u.full_name, o.badge_number, o.department, o.specialization,
                  (SELECT COUNT(*) FROM incidents WHERE assigned_officer_id = u.id
                   AND status NOT IN ('Resolved', 'Closed')) AS active_cases
           FROM users u
           JOIN officers o ON u.id = o.user_id
           WHERE u.is_active = 1
           ORDER BY active_cases ASC"""
    )

    return render_template('admin/assign_case.html',
                           incident=incident, officers=officers)


# ── Incident Categories ───────────────────────────────────────
@admin_bp.route('/admin/categories', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_categories():
    """Manage incident categories."""
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'create':
            name = sanitize_input(request.form.get('name', ''))
            description = sanitize_input(request.form.get('description', ''))
            if name:
                try:
                    execute(
                        "INSERT INTO incident_categories (name, description) VALUES (%s, %s)",
                        (name, description or None)
                    )
                    flash(f'Category "{name}" created.', 'success')
                except Exception:
                    flash('Category already exists or could not be created.', 'danger')
            else:
                flash('Category name is required.', 'warning')

        elif action == 'toggle':
            cat_id = request.form.get('category_id', type=int)
            execute(
                "UPDATE incident_categories SET is_active = NOT is_active WHERE id = %s",
                (cat_id,)
            )
            flash('Category status toggled.', 'success')

        elif action == 'delete':
            cat_id = request.form.get('category_id', type=int)
            execute("DELETE FROM incident_categories WHERE id = %s", (cat_id,))
            flash('Category deleted.', 'success')

        return redirect(url_for('admin.manage_categories'))

    categories = fetch_all("SELECT * FROM incident_categories ORDER BY name")
    return render_template('admin/categories.html', categories=categories)


# ── Report Generation ─────────────────────────────────────────
@admin_bp.route('/admin/reports')
@login_required
@admin_required
def reports_page():
    """Report generation page with history."""
    report_history = fetch_all(
        """SELECT rh.*, u.full_name AS admin_name
           FROM report_history rh
           JOIN users u ON rh.admin_id = u.id
           ORDER BY rh.created_at DESC
           LIMIT 20"""
    )
    return render_template('admin/reports.html', report_history=report_history)


@admin_bp.route('/admin/reports/generate', methods=['POST'])
@login_required
@admin_required
def generate_report():
    """Generate PDF or Excel report."""
    report_format = request.form.get('format', 'pdf')
    report_type = request.form.get('report_type', 'summary')

    try:
        if report_format == 'excel':
            filepath, filename = generate_excel_report(report_type)
        else:
            filepath, filename = generate_pdf_report(report_type)

        # Record in history
        execute(
            """INSERT INTO report_history (admin_id, report_type, file_path, parameters)
               VALUES (%s, %s, %s, %s)""",
            (current_user.id, f'{report_type}_{report_format}', filepath,
             f'format={report_format}')
        )

        log_audit(current_user.id, 'REPORT_GENERATED', f'{report_format.upper()} report: {filename}')

        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Report generation failed: {str(e)}', 'danger')
        return redirect(url_for('admin.reports_page'))


@admin_bp.route('/admin/reports/download/<int:report_id>')
@login_required
@admin_required
def download_report(report_id):
    """Download a previously generated report."""
    report = fetch_one("SELECT * FROM report_history WHERE id = %s", (report_id,))
    if not report or not os.path.exists(report['file_path']):
        flash('Report file not found.', 'danger')
        return redirect(url_for('admin.reports_page'))

    filename = os.path.basename(report['file_path'])
    return send_file(report['file_path'], as_attachment=True, download_name=filename)
