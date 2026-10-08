"""
Cyber Incident Reporting Portal — Email Notification Service
Sends automated email alerts asynchronously for status changes, assignments, and case filings.
Uses standard library smtplib and email.mime with thread-based non-blocking dispatch.
"""
import os
import smtplib
import threading
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

STATUS_COLORS = {
    'Pending': {'bg': '#ffab40', 'fg': '#000000', 'badge': 'Pending Review'},
    'Assigned': {'bg': '#00e5ff', 'fg': '#000000', 'badge': 'Officer Assigned'},
    'Under Investigation': {'bg': '#3d7bfd', 'fg': '#ffffff', 'badge': 'Under Investigation'},
    'Resolved': {'bg': '#00e676', 'fg': '#000000', 'badge': 'Resolved'},
    'Closed': {'bg': '#64748b', 'fg': '#ffffff', 'badge': 'Closed'},
}


def _send_smtp_worker(to_email, subject, html_content, text_content=None):
    """Worker function executed in a background thread to send the email."""
    mail_server = Config.MAIL_SERVER
    mail_username = Config.MAIL_USERNAME
    mail_password = Config.MAIL_PASSWORD
    mail_port = Config.MAIL_PORT
    sender = (Config.MAIL_DEFAULT_SENDER or '').strip()
    sender_lower = sender.lower()
    if (
        '@' not in sender
        or sender_lower.startswith(('your-', 'placeholder', 'change-me'))
        or sender_lower.endswith(('@example.com', '@example.org', '@example.net'))
    ):
        sender = mail_username or 'noreply@cyberportal.local'

    if not mail_server or not mail_username:
        print(f"[MAIL NOTICE] SMTP is not configured. Email to <{to_email}> was skipped.")
        print(f"              Subject: {subject}")
        print("              To enable live emails, provide MAIL_SERVER, MAIL_USERNAME, and MAIL_PASSWORD in your .env file.")
        return

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"Cyber Incident Portal <{sender}>"
        msg['To'] = to_email

        # Fallback plain text version
        if text_content:
            msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        else:
            msg.attach(MIMEText(subject, 'plain', 'utf-8'))

        # Rich HTML version
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        if Config.MAIL_USE_SSL:
            server = smtplib.SMTP_SSL(mail_server, mail_port, timeout=15)
        else:
            server = smtplib.SMTP(mail_server, mail_port, timeout=15)
            if Config.MAIL_USE_TLS:
                server.ehlo()
                server.starttls()
                server.ehlo()

        if mail_password:
            server.login(mail_username, mail_password)

        server.send_message(msg)
        server.quit()
        print(f"[MAIL SUCCESS] Notification email sent to {to_email} ({subject})")

    except Exception as e:
        print(f"[MAIL ERROR] Failed to send email to {to_email}: {e}")
        logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)


def send_email_async(to_email, subject, html_content, text_content=None):
    """Dispatches email in a background daemon thread to avoid blocking web requests."""
    if not to_email:
        return
    thread = threading.Thread(
        target=_send_smtp_worker,
        args=(to_email, subject, html_content, text_content),
        daemon=True
    )
    thread.start()


def send_password_reset_email(to_email, full_name, reset_url):
    """Send a password-reset email with a secure link that expires after one hour."""
    if not to_email:
        return

    first_name = (full_name or 'there').split()[0]
    subject = 'Reset your Cyber Incident Portal password'
    text_content = f"""
Hello {first_name},

We received a request to reset your password for the Cyber Incident Reporting Portal.

Use the link below to set a new password:
{reset_url}

This reset link will expire in 1 hour. If you did not request this change, you can ignore this email.

Regards,
Cyber Incident Response Team
    """.strip()

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Reset Password</title>
</head>
<body style="margin:0;padding:0;background:#0b0f19;font-family:Arial,sans-serif;color:#e2e8f0;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:30px 15px;background:#0b0f19;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width:620px;background:#121829;border:1px solid rgba(0,229,255,0.2);border-radius:14px;overflow:hidden;">
                    <tr>
                        <td style="background:linear-gradient(135deg,#0d1b33,#152445);padding:25px 30px;border-bottom:1px solid rgba(0,229,255,0.25);">
                            <span style="font-size:20px;">🛡️</span>
                            <span style="font-size:18px;font-weight:700;color:#ffffff;">Cyber Incident Reporting Portal</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:30px;">
                            <h2 style="margin:0 0 12px 0;color:#ffffff;">Reset Your Password</h2>
                            <p style="margin:0 0 18px 0;font-size:14px;color:#94a3b8;line-height:1.6;">
                                Hello <strong style="color:#ffffff;">{first_name}</strong>,
                                we received a request to reset your password. Click the button below to create a new one.
                            </p>
                            <div style="text-align:center;margin:20px 0 25px 0;">
                                <a href="{reset_url}" target="_blank" style="display:inline-block;background:linear-gradient(135deg,#00e5ff,#3d7bfd);color:#0b0f19;text-decoration:none;font-weight:700;padding:12px 28px;border-radius:8px;">
                                    Reset Password
                                </a>
                            </div>
                            <p style="margin:0 0 10px 0;font-size:13px;color:#94a3b8;line-height:1.6;">
                                If the button does not work, copy and paste this link into your browser:
                            </p>
                            <p style="margin:0;color:#00e5ff;font-size:12px;word-break:break-all;">{reset_url}</p>
                            <p style="margin:20px 0 0 0;font-size:12px;color:#64748b;line-height:1.6;">
                                This reset link will expire in 1 hour. If you did not request this change, you can safely ignore this email.
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="background:#090d16;padding:18px 30px;text-align:center;font-size:11px;color:#64748b;">
                            Cyber Incident Reporting System • Automated Security Notice
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """.strip()

    send_email_async(to_email, subject, html_content, text_content)


def send_status_change_email(incident, new_status, old_status=None, notes=None, changed_by_name=None):
    """
    Sends an incident status update notification email to the citizen who filed the report.
    """
    to_email = incident.get('reporter_email')
    reporter_name = incident.get('reporter_name') or 'Citizen'
    case_id = incident.get('case_id', 'Unknown')
    title = incident.get('title', 'Cyber Incident')
    incident_id = incident.get('id', '')
    incident_type = incident.get('incident_type', 'General Cyber Incident')

    if not to_email:
        return

    status_meta = STATUS_COLORS.get(new_status, {'bg': '#3d7bfd', 'fg': '#ffffff', 'badge': new_status})
    portal_url = Config.PORTAL_BASE_URL.rstrip('/')
    case_url = f"{portal_url}/incidents/{incident_id}" if incident_id else portal_url
    updated_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    subject = f"🛡️ [Case {case_id}] Status Updated to: {new_status}"

    # Status emoji mapping
    status_emojis = {
        'Pending': '⏳',
        'Assigned': '👮',
        'Under Investigation': '🔍',
        'Resolved': '✅',
        'Closed': '📁',
    }
    status_emoji = status_emojis.get(new_status, 'ℹ️')

    # Plain text summary
    text_content = f"""
Your {incident_type} complaint has been {new_status.lower()}.

Complaint Status: {new_status} {status_emoji}{f' {notes}' if notes else ''}

Thank you for using the Cyber Incident Reporting Portal.

---
Case ID: {case_id}
Incident Title: {title}
Updated By: {changed_by_name or 'Incident Response Team'}
Date & Time: {updated_at}

Track your case: {case_url}
""".strip()

    # Beautiful Cyber-Themed HTML Email
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Incident Status Update</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e2e8f0;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0b0f19; padding: 30px 15px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width: 620px; background: #121829; border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 14px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.6);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #0d1b33 0%, #152445 100%); padding: 25px 30px; border-bottom: 1px solid rgba(0, 229, 255, 0.25);">
                            <table width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td>
                                        <div style="display: inline-block; vertical-align: middle; background: rgba(0, 229, 255, 0.15); border: 1px solid #00e5ff; border-radius: 8px; padding: 8px 12px; margin-right: 12px;">
                                            <span style="font-size: 20px;">🛡️</span>
                                        </div>
                                        <span style="font-size: 18px; font-weight: 700; color: #ffffff; letter-spacing: 0.5px; vertical-align: middle;">Cyber Incident Reporting Portal</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Body Content -->
                    <tr>
                        <td style="padding: 30px;">
                            <h2 style="margin: 0 0 10px 0; font-size: 20px; color: #ffffff;">Case Status Update</h2>
                            <p style="margin: 0 0 20px 0; font-size: 15px; color: #e2e8f0; line-height: 1.7;">
                                Your <strong style="color: #00e5ff;">{incident_type}</strong> complaint has been <strong style="color: #ffffff;">{new_status.lower()}</strong>.
                            </p>

                            <!-- Status Highlight Banner -->
                            <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 18px 20px; margin-bottom: 20px;">
                                <p style="margin: 0; font-size: 15px; color: #e2e8f0; line-height: 1.7;">
                                    <strong>Complaint Status:</strong>
                                    <span style="display: inline-block; background-color: {status_meta['bg']}; color: {status_meta['fg']}; font-weight: 700; font-size: 13px; padding: 4px 12px; border-radius: 20px; margin: 0 6px;">
                                        {new_status}
                                    </span>
                                    {status_emoji}
                                    {f'<span style="color: #cbd5e1;"> {notes}</span>' if notes else ''}
                                </p>
                            </div>

                            <p style="margin: 0 0 20px 0; font-size: 14px; color: #94a3b8; line-height: 1.6;">
                                Thank you for using the <strong style="color: #ffffff;">Cyber Incident Reporting Portal</strong>.
                            </p>

                            <!-- Case Details (compact) -->
                            <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 25px; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.15); width: 38%; font-size: 13px; color: #94a3b8;">Case ID:</td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.15); font-size: 14px; font-weight: 600; color: #00e5ff; font-family: monospace;">{case_id}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.15); font-size: 13px; color: #94a3b8;">Incident Type:</td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.15); font-size: 13px; color: #cbd5e1;">{incident_type}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.15); font-size: 13px; color: #94a3b8;">Updated On:</td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.15); font-size: 13px; color: #cbd5e1;">{updated_at}</td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table width="100%" cellspacing="0" cellpadding="0" style="margin: 30px 0 10px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{case_url}" target="_blank" style="display: inline-block; background: linear-gradient(135deg, #00e5ff 0%, #3d7bfd 100%); color: #0b0f19; font-weight: 700; font-size: 14px; text-decoration: none; padding: 12px 28px; border-radius: 8px; box-shadow: 0 4px 14px rgba(0, 229, 255, 0.35);">
                                            View Case Details & Timeline
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background: #090d16; padding: 20px 30px; border-top: 1px solid rgba(148, 163, 184, 0.1); text-align: center;">
                            <p style="margin: 0 0 6px 0; font-size: 12px; color: #64748b;">
                                This is an automated security advisory from the Cyber Incident Reporting System.
                            </p>
                            <p style="margin: 0; font-size: 11px; color: #475569;">
                                If you did not file this report, please contact our administrative security office immediately.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
""".strip()

    send_email_async(to_email, subject, html_content, text_content)


def send_incident_created_email(incident):
    """
    Sends an initial confirmation email when a citizen registers a complaint.
    """
    to_email = incident.get('reporter_email')
    reporter_name = incident.get('reporter_name') or 'Citizen'
    case_id = incident.get('case_id', 'Unknown')
    title = incident.get('title', 'Cyber Incident')
    incident_id = incident.get('id', '')
    incident_type = incident.get('incident_type', 'General')

    if not to_email:
        return

    portal_url = Config.PORTAL_BASE_URL.rstrip('/')
    case_url = f"{portal_url}/incidents/{incident_id}" if incident_id else portal_url
    created_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    subject = f"🛡️ [Case {case_id}] Incident Report Successfully Registered"

    text_content = f"""
Your {incident_type} complaint has been registered.

Complaint Status: Pending Review ⏳ Our cyber security response officers will review your submission and investigate accordingly.

Case ID: {case_id}
Filed On: {created_at}

Track your case: {case_url}

Thank you for using the Cyber Incident Reporting Portal.
""".strip()

    html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0b0f19;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;color:#e2e8f0;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:30px 15px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width:620px;background:#121829;border:1px solid rgba(0,229,255,0.2);border-radius:14px;overflow:hidden;">
                    <tr>
                        <td style="background:#0d1b33;padding:25px 30px;border-bottom:1px solid rgba(0,229,255,0.25);">
                            <span style="font-size:20px;margin-right:10px;">🛡️</span>
                            <span style="font-size:18px;font-weight:700;color:#ffffff;">Cyber Incident Reporting Portal</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:30px;">
                            <h2 style="margin:0 0 10px 0;font-size:20px;color:#ffffff;">Report Acknowledged</h2>
                            <p style="margin:0 0 20px 0;font-size:15px;color:#e2e8f0;line-height:1.7;">
                                Your <strong style="color:#00e5ff;">{incident_type}</strong> complaint has been <strong style="color:#ffffff;">registered</strong>.
                            </p>

                            <!-- Status Banner -->
                            <div style="background:rgba(15,23,42,0.8);border:1px solid rgba(148,163,184,0.2);border-radius:10px;padding:18px 20px;margin-bottom:20px;">
                                <p style="margin:0;font-size:15px;color:#e2e8f0;line-height:1.7;">
                                    <strong>Complaint Status:</strong>
                                    <span style="display:inline-block;background-color:#ffab40;color:#000000;font-weight:700;font-size:13px;padding:4px 12px;border-radius:20px;margin:0 6px;">
                                        Pending Review
                                    </span>
                                    ⏳ Our cyber security response officers will review your submission and investigate accordingly.
                                </p>
                            </div>

                            <!-- Case ID Highlight -->
                            <div style="background:rgba(0,229,255,0.06);border:1px solid #00e5ff;border-radius:10px;padding:18px 20px;margin-bottom:20px;text-align:center;">
                                <span style="font-size:12px;color:#94a3b8;display:block;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Your Unique Case ID</span>
                                <span style="font-size:22px;font-weight:800;color:#00e5ff;letter-spacing:1px;font-family:monospace;">{case_id}</span>
                            </div>

                            <p style="margin:0 0 20px 0;font-size:14px;color:#94a3b8;line-height:1.6;">
                                Thank you for using the <strong style="color:#ffffff;">Cyber Incident Reporting Portal</strong>.
                            </p>
                            <table width="100%" cellspacing="0" cellpadding="0" style="margin:25px 0 10px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{case_url}" target="_blank" style="display:inline-block;background:linear-gradient(135deg,#00e5ff,#3d7bfd);color:#0b0f19;font-weight:700;font-size:14px;text-decoration:none;padding:12px 28px;border-radius:8px;">
                                            Track Case Status
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="background:#090d16;padding:16px 30px;text-align:center;font-size:11px;color:#64748b;">
                            Cyber Incident Reporting System &bull; Automated Security Advisory
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
""".strip()

    send_email_async(to_email, subject, html_content, text_content)
