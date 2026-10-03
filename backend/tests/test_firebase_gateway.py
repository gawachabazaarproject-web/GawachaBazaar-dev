from unittest.mock import MagicMock, patch

import pytest
from firebase_admin.exceptions import UnavailableError
from google.auth.exceptions import DefaultCredentialsError

from app.core.config import settings
from app.core.firebase import (
    FirebaseAdminGateway,
    FirebaseUnavailableError,
)


def test_missing_project_id_raises_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "")
    gateway = FirebaseAdminGateway()
    with pytest.raises(FirebaseUnavailableError, match="FIREBASE_PROJECT_ID is not configured"):
        gateway._get_app()


def test_invalid_json_raises_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "test-project")
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "not-json-content")
    gateway = FirebaseAdminGateway()
    with pytest.raises(FirebaseUnavailableError, match="FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON"):
        gateway._get_app()


def test_invalid_cert_file_raises_unavailable(monkeypatch, tmp_path):
    cert_file = tmp_path / "cert.json"
    cert_file.write_text("invalid json file content", encoding="utf-8")
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "test-project")
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", str(cert_file))
    gateway = FirebaseAdminGateway()
    with pytest.raises(FirebaseUnavailableError, match="FIREBASE_SERVICE_ACCOUNT_JSON file could not be read"):
        gateway._get_app()


def test_reusing_existing_app(monkeypatch):
    mock_app = MagicMock()
    mock_app.name = "gawachabazaar"
    gateway = FirebaseAdminGateway()

    with patch("firebase_admin.get_app", return_value=mock_app):
        monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "test-project")
        app = gateway._get_app()
        assert app is mock_app


def test_write_operations_translate_auth_errors_to_unavailable(monkeypatch):
    gateway = FirebaseAdminGateway()
    mock_app = MagicMock()
    gateway._app = mock_app

    with patch("firebase_admin.auth.create_user", side_effect=DefaultCredentialsError("missing ADC")):
        with pytest.raises(FirebaseUnavailableError, match="Could not reach Firebase or credentials are not configured"):
            gateway.create_user(email="test@example.com", password="password123", display_name="Test", email_verified=True)

    with patch("firebase_admin.auth.update_user", side_effect=DefaultCredentialsError("missing ADC")):
        with pytest.raises(FirebaseUnavailableError, match="Could not reach Firebase or credentials are not configured"):
            gateway.update_password("uid-123", "new-password")

    with patch("firebase_admin.auth.update_user", side_effect=UnavailableError("network error")):
        with pytest.raises(FirebaseUnavailableError, match="Could not reach Firebase or credentials are not configured"):
            gateway.set_disabled("uid-123", True)

    with patch("firebase_admin.auth.revoke_refresh_tokens", side_effect=DefaultCredentialsError("missing ADC")):
        with pytest.raises(FirebaseUnavailableError, match="Could not reach Firebase or credentials are not configured"):
            gateway.revoke_sessions("uid-123")

    with patch("firebase_admin.auth.delete_user", side_effect=UnavailableError("network error")):
        with pytest.raises(FirebaseUnavailableError, match="Could not reach Firebase or credentials are not configured"):
            gateway.delete_user("uid-123")
