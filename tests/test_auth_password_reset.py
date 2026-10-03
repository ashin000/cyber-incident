import uuid
from unittest.mock import patch

from app import create_app
from config import Config
from models.user import User


def test_forgot_password_flow():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    Config.PORTAL_BASE_URL = 'https://portal.example.com'

    email = f"reset_{uuid.uuid4().hex[:8]}@example.com"
    User.create('Reset User', email, '+1234567890', 'Password@123', role='citizen')

    with app.test_client() as client:
        with patch('routes.auth.send_password_reset_email') as mock_email:
            response = client.post('/forgot-password', data={'email': email}, follow_redirects=True)
            assert response.status_code == 200
            assert b'If an account exists for that email' in response.data
            assert mock_email.call_count == 1
            assert mock_email.call_args[0][2].startswith('https://portal.example.com/reset-password/')

        user = User.get_by_email(email)
        assert user is not None
        assert user.reset_token is not None

        response = client.get(f'/reset-password/{user.reset_token}')
        assert response.status_code == 200
        assert b'Set New Password' in response.data

        response = client.post(
            f'/reset-password/{user.reset_token}',
            data={'password': 'NewPassword@321', 'confirm_password': 'NewPassword@321'},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'Password reset successfully' in response.data
        assert User.verify_password(email, 'NewPassword@321') is not None
