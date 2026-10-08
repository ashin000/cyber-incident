"""
Officer routes — officer dashboard, case management, status updates, notes.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.incident import Incident
from models.evidence import Evidence
from models.notification import Notification
from utils.mailer import send_status_change_email
from utils.decorators import officer_required
from utils.helpers import (
    paginate, sanitize_input, log_audit,
    get_status_color, get_priority_color
)
from config import Config
from database import fetch_one

officer_bp = Blueprint('officer', __name__)


@officer_bp.route('/officer/dashboard')
@login_required
@officer_required
def officer_dashboard():
    """Officer dashboard with stats and case overview."""
    assigned_total = fetch_one(
        "SELECT COUNT(*) AS cnt FROM incidents WHERE assigned_officer_id = %s",
        (current_user.id,)
    )['cnt']
    pending = fetch_one(
        "SELECT COUNT(*) AS cnt FROM incidents WHERE assigned_officer_id = %s AND status = 'Pending'",
        (current_user.id,)
    )['cnt']
    investigating = fetch_one(
        "SELECT COUNT(*) AS cnt FROM incidents WHERE assigned_officer_id = %s AND status = 'Under Investigation'",
        (current_user.id,)
    )['cnt']
    high_priority = fetch_one(
        "SELECT COUNT(*) AS cnt FROM incidents WHERE assigned_officer_id = %s AND priority IN ('high', 'critical')",
        (current_user.id,)
    )['cnt']
    resolved = fetch_one(
        "SELECT COUNT(*) AS cnt FROM incidents WHERE assigned_officer_id = %s AND status IN ('Resolved', 'Closed')",
        (current_user.id,)
    )['cnt']

    # Recent assigned cases
    recent_cases, _ = Incident.get_all(
        page=1, per_page=10, officer_id=current_user.id
    )

    notifications = Notification.get_for_user(current_user.id, limit=10)
    unread_count = Notification.count_unread(current_user.id)

    return render_template('dashboard/officer.html',
                           assigned_total=assigned_total,
                           pending=pending,
                           investigating=investigating,
                           high_priority=high_priority,
                           resolved=resolved,
                           recent_cases=recent_cases,
                           notifications=notifications,
                           unread_count=unread_count,
                           get_status_color=get_status_color,
                           get_priority_color=get_priority_color)


@officer_bp.route('/officer/cases')
@login_required
@officer_required
def assigned_cases():
    """List all cases assigned to this officer."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    search = request.args.get('search', '').strip()

    cases, total = Incident.get_all(
        page=page,
        per_page=Config.ITEMS_PER_PAGE,
        officer_id=current_user.id,
        status=status or None,
        priority=priority or None,
        search=search or None,
    )

    pagination = paginate(total, page, Config.ITEMS_PER_PAGE)

    return render_template('incidents/list.html',
                           incidents=cases,
                           pagination=pagination,
                           search=search,
                           status=status,
                           priority=priority,
                           sort_by='created_at',
                           sort_dir='DESC',
                           get_status_color=get_status_color,
                           get_priority_color=get_priority_color)


@officer_bp.route('/officer/cases/<int:incident_id>/status', methods=['POST'])
@login_required
@officer_required
def update_case_status(incident_id):
    """Update the status of an assigned case."""
    incident = Incident.get_by_id(incident_id)
    if not incident:
        flash('Incident not found.', 'danger')
        return redirect(url_for('officer.officer_dashboard'))

    new_status = request.form.get('new_status', '')
    notes = sanitize_input(request.form.get('notes', ''))
    resolution_remarks = sanitize_input(request.form.get('resolution_remarks', ''))
    incident_type = incident.get('incident_type', 'Cyber Incident')

    if new_status not in Incident.STATUS_LIST:
        flash('Invalid status.', 'danger')
        return redirect(url_for('incident.view_incident', incident_id=incident_id))

    old_status = incident.get('status', 'Pending')
    Incident.update_status(incident_id, new_status, current_user.id, notes)

    if resolution_remarks and new_status in ('Resolved', 'Closed'):
        Incident.set_resolution(incident_id, resolution_remarks)

    # Notify the reporter with formatted message
    status_emojis = {
        'Pending': '⏳',
        'Assigned': '👮',
        'Under Investigation': '🔍',
        'Resolved': '✅',
        'Closed': '📁',
    }
    status_emoji = status_emojis.get(new_status, 'ℹ️')
    notif_notes = resolution_remarks if (resolution_remarks and new_status in ('Resolved', 'Closed')) else notes
    notif_message = f'Your {incident_type} complaint has been {new_status.lower()}.\n\n'
    notif_message += f'Complaint Status: {new_status} {status_emoji}'
    if notif_notes:
        notif_message += f' {notif_notes}'
    notif_message += f'\n\nThank you for using the Cyber Incident Reporting Portal.'

    Notification.create(
        user_id=incident['user_id'],
        title='Case Status Updated',
        message=notif_message,
        notif_type='info',
        incident_id=incident_id
    )

    # Email notification to reporter's registered email
    status_notes = resolution_remarks if (resolution_remarks and new_status in ('Resolved', 'Closed')) else notes
    send_status_change_email(
        incident=incident,
        new_status=new_status,
        old_status=old_status,
        notes=status_notes,
        changed_by_name=f'Officer {current_user.full_name}'
    )

    log_audit(current_user.id, 'STATUS_UPDATED',
              f'Case {incident["case_id"]}: {incident["status"]} → {new_status}')
    flash(f'Status updated to {new_status}.', 'success')
    return redirect(url_for('incident.view_incident', incident_id=incident_id))


@officer_bp.route('/officer/cases/<int:incident_id>/notes', methods=['POST'])
@login_required
@officer_required
def add_case_notes(incident_id):
    """Add investigation notes to a case."""
    note = sanitize_input(request.form.get('note', ''))
    if not note:
        flash('Note cannot be empty.', 'warning')
        return redirect(url_for('incident.view_incident', incident_id=incident_id))

    Incident.add_note(incident_id, current_user.id, note)
    log_audit(current_user.id, 'NOTE_ADDED', f'Note added to incident {incident_id}')
    flash('Investigation note added.', 'success')
    return redirect(url_for('incident.view_incident', incident_id=incident_id))


@officer_bp.route('/officer/cases/<int:incident_id>/priority', methods=['POST'])
@login_required
@officer_required
def change_priority(incident_id):
    """Change case priority."""
    priority = request.form.get('priority', '')
    if priority not in Incident.PRIORITY_LIST:
        flash('Invalid priority.', 'danger')
        return redirect(url_for('incident.view_incident', incident_id=incident_id))

    Incident.update_priority(incident_id, priority)
    log_audit(current_user.id, 'PRIORITY_CHANGED',
              f'Incident {incident_id} priority → {priority}')
    flash(f'Priority updated to {priority}.', 'success')
    return redirect(url_for('incident.view_incident', incident_id=incident_id))


@officer_bp.route('/officer/cases/<int:incident_id>/request-evidence', methods=['POST'])
@login_required
@officer_required
def request_evidence(incident_id):
    """Request additional evidence from the reporter."""
    incident = Incident.get_by_id(incident_id)
    if not incident:
        flash('Incident not found.', 'danger')
        return redirect(url_for('officer.officer_dashboard'))

    message = sanitize_input(request.form.get('message', ''))
    if not message:
        message = 'The investigating officer has requested additional evidence for your case.'

    Notification.create(
        user_id=incident['user_id'],
        title='Additional Evidence Requested',
        message=f'Case {incident["case_id"]}: {message}',
        notif_type='warning',
        incident_id=incident_id
    )

    log_audit(current_user.id, 'EVIDENCE_REQUESTED',
              f'Evidence requested for case {incident["case_id"]}')
    flash('Evidence request sent to the reporter.', 'success')
    return redirect(url_for('incident.view_incident', incident_id=incident_id))
