from uuid import uuid4

from fastapi.testclient import TestClient

from invoice_agent.main import app


def test_review_and_audit_require_authentication() -> None:
    client = TestClient(app)
    invoice_id = uuid4()
    assert client.get(f"/api/v1/invoices/{invoice_id}/audit").status_code == 401
    assert (
        client.post(
            f"/api/v1/invoices/{invoice_id}/review", json={"status": "reviewed"}
        ).status_code
        == 401
    )


def test_chat_creation_requires_authentication() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/chat/sessions", json={"invoice_id": str(uuid4())})
    assert response.status_code == 401


async def test_new_workbook_and_review_note_persist(test_client, monkeypatch) -> None:
    client, factory = test_client
    csrf = {"X-CSRF-Token": "test-csrf-token"}
    from pydantic import SecretStr

    from invoice_agent.config import settings

    monkeypatch.setattr(
        settings, "data_encryption_key", SecretStr("0123456789abcdef0123456789abcdef")
    )
    monkeypatch.setattr(settings, "workbook_profile_approved", True)
    created = await client.post(
        "/api/v1/workbooks/new",
        headers=csrf,
        json={"name": "AP log", "headers": ["Invoice No", "Total"]},
    )
    assert created.status_code == 201
    invoice_id = __import__("uuid").uuid4()
    from invoice_agent.persistence.invoice_models import Invoice

    async with factory() as session:
        session.add(
            Invoice(
                id=invoice_id,
                tenant_id=__import__("uuid").UUID("00000000-0000-4000-8000-000000000001"),
                source_blob_id="blob",
                source_sha256="0" * 64,
                source_media_type="application/pdf",
                processing_status="ready_for_review",
                review_status="needs_review",
                current_revision=1,
                created_by="test-operator",
            )
        )
        await session.commit()
    response = await client.post(
        f"/api/v1/invoices/{invoice_id}/review",
        headers=csrf,
        json={"status": "reviewed", "note": "Verified source details"},
    )
    assert response.status_code == 200
    assert response.json()["meaning"] == "data_review_only_not_payment_approval"
