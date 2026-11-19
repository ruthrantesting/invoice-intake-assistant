from decimal import Decimal
from uuid import UUID, uuid4

from invoice_agent.persistence.invoice_models import Invoice, InvoiceRevision

TENANT = UUID("00000000-0000-4000-8000-000000000001")


def _invoice(invoice_id: UUID, sha: str) -> tuple[Invoice, InvoiceRevision]:
    return (
        Invoice(
            id=invoice_id,
            tenant_id=TENANT,
            source_blob_id="source",
            source_sha256=sha,
            source_media_type="image/png",
            processing_status="ready_for_review",
            review_status="needs_review",
            current_revision=1,
            created_by="test-operator",
        ),
        InvoiceRevision(
            invoice_id=invoice_id,
            revision=1,
            invoice_number="US-001",
            vendor="East Repair Inc.",
            currency="USD",
            subtotal=Decimal("145.00"),
            tax=Decimal("9.06"),
            other_charges=Decimal("0"),
            discounts=Decimal("0"),
            total=Decimal("154.06"),
        ),
    )


async def test_validation_flags_other_invoice_with_same_source_file(test_client, monkeypatch):
    from invoice_agent.config import settings

    monkeypatch.setattr(settings, "currency_tolerances_json", '{"USD":"0.01"}')
    client, factory = test_client
    first, second = uuid4(), uuid4()
    async with factory() as session:
        for invoice_id in (first, second):
            invoice, revision = _invoice(invoice_id, "a" * 64)
            session.add(invoice)
            await session.flush()
            session.add(revision)
        await session.commit()
    response = await client.post(
        f"/api/v1/invoices/{second}/validate",
        headers={"X-CSRF-Token": "test-csrf-token"},
        json={},
    )
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert any(
        item["check_type"] == "duplicate" and item["outcome"] == "flagged" for item in results
    )
    assert any(
        item["check_type"] == "arithmetic" and item["outcome"] == "passed" for item in results
    )
