"""
WSGI entry point for Gunicorn / Render deployment.
Exposes a top-level `app` instance from the application factory.
"""
from app import create_app

app = create_app()
