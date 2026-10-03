"""
Authentication routes — registration, login, logout, profile, password change.
"""
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from config import Config
from models.user import User
from utils.helpers import validate_email, validate_phone, validate_password, sanitize_input, log_audit
from utils.mailer import send_password_reset_email

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Citizen registration."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        full_name = sanitize_input(request.form.get('full_name', ''))
        email = sanitize_input(request.form.get('email', '')).lower()
        phone = sanitize_input(request.form.get('phone', ''))
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Validation
        errors = []
        if not full_name or len(full_name) < 2:
            errors.append('Full name is required (min 2 characters).')
        if not validate_email(email):
            errors.append('Please enter a valid email address.')
        if phone and not validate_phone(phone):
            errors.append('Please enter a valid phone number.')

        valid_pwd, pwd_msg = validate_password(password)
        if not valid_pwd:
            errors.append(pwd_msg)
        if password != confirm:
            errors.append('Passwords do not match.')

        # Check if email already exists
        if User.get_by_email(email):
            errors.append('An account with this email already exists.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('auth/register.html')

        # Create user
        try:
            user_id = User.create(full_name, email, phone or None, password, role='citizen')
            log_audit(user_id, 'USER_REGISTERED', f'New citizen: {email}')
            flash('Account created successfully! Please sign in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash('Registration failed. Please try again.', 'danger')
            return render_template('auth/register.html')

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login (all roles)."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = sanitize_input(request.form.get('email', '')).lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both email and password.', 'warning')
            return render_template('auth/login.html')

        user = User.get_by_email(email)
        if not user:
            flash('You need to register first.', 'danger')
            return render_template('auth/login.html')

        authenticated_user = User.verify_password(email, password)
        if authenticated_user:
            if not authenticated_user.is_active:
                flash('Your account has been deactivated. Contact admin.', 'danger')
                return render_template('auth/login.html')

            login_user(authenticated_user)
            log_audit(authenticated_user.id, 'USER_LOGIN', f'Login: {email}')
            flash(f'Welcome back, {authenticated_user.full_name}!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Your password or username is incorrect.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request a password reset email for a registered account."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = sanitize_input(request.form.get('email', '')).lower()
        if not validate_email(email):
            flash('Please enter a valid email address.', 'danger')
            return render_template('auth/forgot_password.html')

        user = User.get_by_email(email)
        if user and user.is_active:
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            User.set_reset_token(user.id, token, expires_at)
            base_url = Config.PORTAL_BASE_URL.rstrip('/')
            reset_url = f"{base_url}{url_for('auth.reset_password', token=token)}"
            send_password_reset_email(user.email, user.full_name, reset_url)

        flash('If an account exists for that email, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Allow a user to set a new password using a valid reset token."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    user = User.get_by_reset_token(token)
    if not user:
        flash('This password reset link is invalid or has already been used.', 'danger')
        return redirect(url_for('auth.login'))

    expires_at = user.reset_token_expires
    if not expires_at:
        User.clear_reset_token(user.id)
        flash('This password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    try:
        expires_at_dt = datetime.strptime(str(expires_at), '%Y-%m-%d %H:%M:%S')
    except ValueError:
        User.clear_reset_token(user.id)
        flash('This password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if datetime.now(timezone.utc).replace(tzinfo=None) > expires_at_dt:
        User.clear_reset_token(user.id)
        flash('This password reset link has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        valid_pwd, pwd_msg = validate_password(password)
        if not valid_pwd:
            flash(pwd_msg, 'danger')
            return render_template('auth/reset_password.html', token=token)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        User.change_password(user.id, password)
        User.clear_reset_token(user.id)
        log_audit(user.id, 'PASSWORD_RESET', 'Password reset via forgot-password flow')
        flash('Password reset successfully! You can now sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/logout')
@login_required
def logout():
    """Log the user out and redirect to login."""
    log_audit(current_user.id, 'USER_LOGOUT', f'Logout: {current_user.email}')
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """View and edit profile, change password."""
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'profile':
            full_name = sanitize_input(request.form.get('full_name', ''))
            phone = sanitize_input(request.form.get('phone', ''))
            address = sanitize_input(request.form.get('address', ''))

            if not full_name or len(full_name) < 2:
                flash('Full name is required.', 'danger')
                return render_template('auth/profile.html')

            User.update_profile(current_user.id, full_name, phone or None, address or None)
            log_audit(current_user.id, 'PROFILE_UPDATED', 'Profile details updated')
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('auth.profile'))

        elif form_type == 'password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_new = request.form.get('confirm_new_password', '')

            if not User.check_current_password(current_user.id, current_password):
                flash('Current password is incorrect.', 'danger')
                return render_template('auth/profile.html')

            valid_pwd, pwd_msg = validate_password(new_password)
            if not valid_pwd:
                flash(pwd_msg, 'danger')
                return render_template('auth/profile.html')

            if new_password != confirm_new:
                flash('New passwords do not match.', 'danger')
                return render_template('auth/profile.html')

            User.change_password(current_user.id, new_password)
            log_audit(current_user.id, 'PASSWORD_CHANGED', 'Password updated')
            flash('Password changed successfully!', 'success')
            return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')
