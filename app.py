"""
Cyber Incident Reporting Portal — Flask Application Entry Point
Registers blueprints, error handlers, login manager, and CSRF protection.
"""
import os
from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
from models.user import User


def create_app():
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── CSRF Protection ────────────────────────────────────────
    csrf = CSRFProtect(app)

    # ── Proxy Fix for Reverse Proxies (Render, Heroku) ──────────
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


    # ── Flask-Login ────────────────────────────────────────────
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id))

    # ── Create Upload Directories ──────────────────────────────
    upload_dirs = [
        Config.UPLOAD_FOLDER,
        os.path.join(Config.UPLOAD_FOLDER, 'images'),
        os.path.join(Config.UPLOAD_FOLDER, 'documents'),
        os.path.join(Config.UPLOAD_FOLDER, 'videos'),
    ]
    for d in upload_dirs:
        os.makedirs(d, exist_ok=True)

    os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)

    # ── Register Blueprints ────────────────────────────────────
    from routes.auth import auth_bp
    from routes.incident import incident_bp
    from routes.evidence import evidence_bp
    from routes.dashboard import dashboard_bp
    from routes.officer import officer_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(incident_bp)
    app.register_blueprint(evidence_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(officer_bp)
    app.register_blueprint(admin_bp)

    # ── Error Handlers ─────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/404.html'), 403

    # ── Context Processors ─────────────────────────────────────
    @app.context_processor
    def inject_notifications():
        """Make notification data available in all templates."""
        from flask_login import current_user
        if current_user.is_authenticated:
            from models.notification import Notification
            unread_count = Notification.count_unread(current_user.id)
            notifications = Notification.get_for_user(current_user.id, limit=8)
            return {
                'unread_count': unread_count,
                'notifications': notifications
            }
        return {'unread_count': 0, 'notifications': []}

    return app


# ── WSGI app instance (for gunicorn app:app on Render) ─────────────
app = create_app()

# ── Local dev server ────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
