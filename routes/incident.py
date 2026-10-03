"""
Incident routes — create, list, detail, tracking.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.incident import Incident
from models.evidence import Evidence
from models.notification import Notification
from database import fetch_all
from utils.mailer import send_incident_created_email
from utils.helpers import (
    paginate, sanitize_input, log_audit,
    get_status_percentage, get_status_color, get_priority_color
)
from config import Config

incident_bp = Blueprint('incident', __name__)


@incident_bp.route('/incidents/new', methods=['GET', 'POST'])
@login_required
def new_incident():
    """Submit a new cyber incident report."""
    categories = fetch_all(
        "SELECT * FROM incident_categories WHERE is_active = 1 ORDER BY name"
    )

    if request.method == 'POST':
        data = {
            'user_id': current_user.id,
            'title': sanitize_input(request.form.get('title', '')),
            'incident_type': sanitize_input(request.form.get('incident_type', '')),
            'description': sanitize_input(request.form.get('description', '')),
            'incident_date': request.form.get('incident_date', ''),
            'incident_time': request.form.get('incident_time') or None,
            'location': sanitize_input(request.form.get('location', '')) or None,
            'website_involved': sanitize_input(request.form.get('website_involved', '')) or None,
            'email_involved': sanitize_input(request.form.get('email_involved', '')) or None,
            'phone_involved': sanitize_input(request.form.get('phone_involved', '')) or None,
            'social_media': sanitize_input(request.form.get('social_media', '')) or None,
            'financial_loss': request.form.get('financial_loss') or 0,
            'additional_comments': sanitize_input(request.form.get('additional_comments', '')) or None,
            'category_id': request.form.get('category_id') or None,
            'priority': request.form.get('priority', 'medium'),
        }

        # Validation
        errors = []
        if not data['title'] or len(data['title']) < 5:
            errors.append('Title is required (min 5 characters).')
        if not data['incident_type']:
            errors.append('Incident type is required.')
        if not data['description'] or len(data['description']) < 10:
            errors.append('Description is required (min 10 characters).')
        if not data['incident_date']:
            errors.append('Incident date is required.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('incidents/new.html', categories=categories)

        try:
            incident_id = Incident.create(data)
            incident = Incident.get_by_id(incident_id)

            # Handle file uploads
            files = request.files.getlist('evidence_files')
            for f in files:
                if f and f.filename:
                    try:
                        Evidence.save_file(f, incident_id, current_user.id)
                    except ValueError as ve:
                        flash(f'File error: {ve}', 'warning')

            log_audit(current_user.id, 'INCIDENT_CREATED',
                      f'Case {incident["case_id"]} created')

            # Send email confirmation to registered user
            send_incident_created_email(incident)

            flash(f'Incident reported successfully! Case ID: {incident["case_id"]}', 'success')
            return redirect(url_for('incident.view_incident', incident_id=incident_id))
        except Exception as e:
            import traceback
            print("=== ERROR IN new_incident ===")
            traceback.print_exc()
            flash(f'Failed to submit incident: {e}', 'danger')
            return render_template('incidents/new.html', categories=categories)

    return render_template('incidents/new.html', categories=categories)


@incident_bp.route('/incidents')
@login_required
def list_incidents():
    """List incidents with search, filter, pagination, and sorting."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    sort_by = request.args.get('sort_by', 'created_at')
    sort_dir = request.args.get('sort_dir', 'DESC')

    # Scope by role
    user_id = None
    officer_id = None
    if current_user.role == 'citizen':
        user_id = current_user.id
    elif current_user.role == 'officer':
        # Officers see assigned + all cases
        pass

    incidents, total = Incident.get_all(
        page=page,
        per_page=Config.ITEMS_PER_PAGE,
        user_id=user_id,
        officer_id=officer_id,
        status=status or None,
        priority=priority or None,
        search=search or None,
        sort_by=sort_by,
        sort_dir=sort_dir
    )

    pagination = paginate(total, page, Config.ITEMS_PER_PAGE)

    return render_template('incidents/list.html',
                           incidents=incidents,
                           pagination=pagination,
                           search=search,
                           status=status,
                           priority=priority,
                           sort_by=sort_by,
                           sort_dir=sort_dir,
                           get_status_color=get_status_color,
                           get_priority_color=get_priority_color)


@incident_bp.route('/incidents/<int:incident_id>')
@login_required
def view_incident(incident_id):
    """View incident detail with timeline, evidence, and notes."""
    incident = Incident.get_by_id(incident_id)
    if not incident:
        flash('Incident not found.', 'danger')
        return redirect(url_for('incident.list_incidents'))

    # Access control: citizens can only view their own
    if current_user.role == 'citizen' and incident['user_id'] != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('incident.list_incidents'))

    evidence_list = Evidence.get_by_incident(incident_id)
    timeline = Incident.get_timeline(incident_id)
    notes = Incident.get_notes(incident_id)

    status_pct = get_status_percentage(incident['status'])
    statuses = Incident.STATUS_LIST

    return render_template('incidents/detail.html',
                           incident=incident,
                           evidence_list=evidence_list,
                           timeline=timeline,
                           notes=notes,
                           status_pct=status_pct,
                           statuses=statuses,
                           get_status_color=get_status_color,
                           get_priority_color=get_priority_color)
