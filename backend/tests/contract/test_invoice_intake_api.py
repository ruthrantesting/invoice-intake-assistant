from uuid import uuid4

from fastapi.testclient import TestClient

from invoice_agent.main import app


def test_invoice_routes_are_registered_and_authentication_is_required() -> None:
    client = TestClient(app)
    response = client.get(f"/api/v1/invoices/{uuid4()}")
    assert response.status_code == 401


def test_health_route_does_not_require_authentication() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invoice_correction_route_requires_authentication() -> None:
    client = TestClient(app)
    response = client.patch(
        f"/api/v1/invoices/{uuid4()}/fields",
        json={"expected_revision": 1, "changes": {"invoice_number": "000123"}},
    )
    assert response.status_code == 401


def test_invoice_upload_rejects_missing_csrf_or_authentication() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/invoices", files={"file": ("invoice.pdf", b"bad")})
    assert response.status_code == 401


async def test_health_and_session_contract_with_test_dependencies(test_client) -> None:
    client, _ = test_client
    response = await client.get("/api/v1/session")
    assert response.status_code == 200
    assert response.json()["roles"] == ["operator", "reviewer"]


async def test_correction_requires_record_and_returns_non_disclosing_not_found(test_client) -> None:
    client, _ = test_client
    response = await client.patch(
        f"/api/v1/invoices/{uuid4()}/fields",
        headers={"X-CSRF-Token": "test-csrf-token"},
        json={"expected_revision": 1, "changes": {"invoice_number": "000123"}},
    )
    assert response.status_code == 404
    assert "invoice" not in response.json().get("details", {})


async def test_upload_creates_separate_invoice_and_processing_job(
    test_client, monkeypatch, tmp_path
) -> None:
    from pydantic import SecretStr
    from reportlab.pdfgen import canvas

    from invoice_agent.config import settings

    monkeypatch.setattr(
        settings, "data_encryption_key", SecretStr("0123456789abcdef0123456789abcdef")
    )
    monkeypatch.setattr(settings, "blob_root", tmp_path / "blobs")
    monkeypatch.setattr(settings, "max_upload_bytes", 2_000_000)
    output = __import__("io").BytesIO()
    document = canvas.Canvas(output)
    document.drawString(50, 700, "Invoice INV-00042 total 10.00")
    document.save()
    client, _ = test_client
    response = await client.post(
        "/api/v1/invoices",
        headers={"X-CSRF-Token": "test-csrf-token"},
        files={"file": ("invoice.pdf", output.getvalue(), "application/pdf")},
    )
    assert response.status_code == 202
    payload = response.json()
    detail = await client.get(f"/api/v1/invoices/{payload['invoice_id']}")
    assert detail.status_code == 200
    assert detail.json()["processing_status"] == "received"
    job = await client.get(f"/api/v1/jobs/{payload['job_id']}")
    assert job.status_code == 200
    source = await client.get(f"/api/v1/invoices/{payload['invoice_id']}/source")
    assert source.content == output.getvalue()


async def test_correction_creates_revision_and_preserves_original_evidence(test_client) -> None:
    from uuid import UUID

    from sqlalchemy import select

    from invoice_agent.persistence.invoice_models import (
        FieldEvidence,
        Invoice,
        InvoiceRevision,
    )

    client, factory = test_client
    tenant_id = UUID("00000000-0000-4000-8000-000000000001")
    async with factory() as session:
        invoice = Invoice(
            tenant_id=tenant_id,
            source_blob_id="source",
            source_sha256="0" * 64,
            source_media_type="application/pdf",
            processing_status="ready_for_review",
            review_status="not_reviewed",
            current_revision=1,
            created_by="test-operator",
        )
        session.add(invoice)
        await session.flush()
        revision = InvoiceRevision(
            invoice_id=invoice.id,
            revision=1,
            invoice_number="INV-1",
        )
        session.add(revision)
        await session.flush()
        session.add(
            FieldEvidence(
                revision_id=revision.id,
                field_name="invoice_number",
                raw_value="INV-I",
                normalized_value="INV-1",
                page_number=1,
                snippet="INV-I",
                extraction_method="ocr",
            )
        )
        await session.commit()
        invoice_id = invoice.id

    response = await client.patch(
        f"/api/v1/invoices/{invoice_id}/fields",
        headers={"X-CSRF-Token": "test-csrf-token"},
        json={
            "expected_revision": 1,
            "changes": {"invoice_number": "000INV-1"},
        },
    )
    assert response.status_code == 200
    detail = await client.get(f"/api/v1/invoices/{invoice_id}")
    assert detail.json()["fields"]["invoice_number"] == "000INV-1"

    async with factory() as session:
        original = await session.scalar(
            select(InvoiceRevision).where(
                InvoiceRevision.invoice_id == invoice_id,
                InvoiceRevision.revision == 1,
            )
        )
        assert original.invoice_number == "INV-1"
        original_evidence = await session.scalar(
            select(FieldEvidence).where(FieldEvidence.revision_id == original.id)
        )
        assert original_evidence.raw_value == "INV-I"
