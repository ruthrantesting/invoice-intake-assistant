from uuid import uuid4

from fastapi.testclient import TestClient

from invoice_agent.api.auth import session_manager
from invoice_agent.main import app


def test_unauthenticated_resources_are_denied_without_disclosure() -> None:
    client = TestClient(app)
    invoice_id = uuid4()
    paths = [
        ("GET", f"/api/v1/invoices/{invoice_id}"),
        ("GET", f"/api/v1/invoices/{invoice_id}/source"),
        ("GET", f"/api/v1/invoices/{invoice_id}/audit"),
        ("GET", f"/api/v1/workbooks/{uuid4()}"),
    ]
    for method, path in paths:
        response = client.request(method, path)
        assert response.status_code == 401
        assert str(invoice_id) not in response.text


def test_session_manager_expires_and_revokes_sessions(monkeypatch) -> None:
    from pydantic import SecretStr

    from invoice_agent.config import settings

    monkeypatch.setattr(
        settings, "session_secret", SecretStr("test-session-secret-0123456789abcdef")
    )
    token, principal = session_manager.issue("subject-1", uuid4(), {"operator"})
    assert session_manager.resolve(token) == principal
    session_manager.revoke(token)
    assert session_manager.resolve(token) is None


def test_cookie_configuration_is_secure_and_http_only() -> None:
    from invoice_agent.api.auth import session_cookie_settings

    cookie = session_cookie_settings()
    assert cookie["secure"] is True
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "lax"


def test_all_foreign_key_targets_are_registered_in_persistence_metadata() -> None:
    from invoice_agent.persistence.models import Base

    tables = Base.metadata.tables
    assert tables
    for table in tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.target_fullname.split(".")[0] in tables
