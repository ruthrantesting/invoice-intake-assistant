from uuid import uuid4

from fastapi.testclient import TestClient

from invoice_agent.main import app


def test_validation_requires_authentication() -> None:
    client = TestClient(app)
    response = client.post(f"/api/v1/invoices/{uuid4()}/validate", json={})
    assert response.status_code == 401


def test_validation_history_requires_authentication() -> None:
    client = TestClient(app)
    response = client.get(f"/api/v1/invoices/{uuid4()}/validation")
    assert response.status_code == 401
