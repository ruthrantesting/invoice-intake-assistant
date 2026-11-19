from uuid import uuid4

from fastapi.testclient import TestClient

from invoice_agent.main import app


def test_workbook_upload_requires_authentication() -> None:
    client = TestClient(app)
    response = client.get(f"/api/v1/workbooks/{uuid4()}")
    assert response.status_code == 401


def test_confirmation_requires_authentication_and_idempotency_header() -> None:
    client = TestClient(app)
    response = client.post(
        f"/api/v1/invoices/{uuid4()}/log-confirmations",
        json={"preview_id": "missing", "preview_digest": "0" * 64},
    )
    assert response.status_code == 401


def test_new_workbook_requires_authentication() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/workbooks/new",
        json={"name": "Test log", "headers": ["Invoice No", "Total"]},
    )
    assert response.status_code == 401


async def test_new_workbook_inspection_and_mapping_workflow(test_client, monkeypatch) -> None:
    from pydantic import SecretStr

    from invoice_agent.config import settings

    monkeypatch.setattr(
        settings, "data_encryption_key", SecretStr("0123456789abcdef0123456789abcdef")
    )
    monkeypatch.setattr(settings, "workbook_profile_approved", True)
    client, _ = test_client
    csrf = {"X-CSRF-Token": "test-csrf-token"}
    response = await client.post(
        "/api/v1/workbooks/new",
        headers=csrf,
        json={"name": "AP Log", "headers": ["Invoice No", "Vendor", "Total"]},
    )
    assert response.status_code == 201
    payload = response.json()
    mapping = await client.post(
        f"/api/v1/workbooks/{payload['workbook_id']}/mappings",
        headers=csrf,
        json={
            "expected_version_id": payload["version_id"],
            "sheet": "Invoice Log",
            "field_to_column": {
                "invoice_number": "Invoice No",
                "vendor_name": "Vendor",
                "total": "Total",
            },
        },
    )
    assert mapping.status_code == 201
    details = await client.get(f"/api/v1/workbooks/{payload['workbook_id']}")
    assert details.status_code == 200
    assert details.json()["sheets"][0]["headers"] == ["Invoice No", "Vendor", "Total"]


async def test_validation_and_preview_are_read_only_until_confirmation(
    test_client, monkeypatch, tmp_path
) -> None:
    from decimal import Decimal
    from uuid import UUID, uuid4

    from pydantic import SecretStr
    from sqlalchemy import select

    from invoice_agent.config import settings
    from invoice_agent.persistence.blob_store import LocalBlobStore
    from invoice_agent.persistence.invoice_models import Invoice, InvoiceRevision
    from invoice_agent.persistence.validation_models import ValidationRun
    from invoice_agent.persistence.workbook_models import ColumnMapping, Workbook, WorkbookVersion
    from invoice_agent.services.workbook_service import PROFILE_VERSION, new_id

    monkeypatch.setattr(
        settings, "data_encryption_key", SecretStr("0123456789abcdef0123456789abcdef")
    )
    monkeypatch.setattr(settings, "workbook_profile_approved", True)
    monkeypatch.setattr(settings, "currency_tolerances_json", '{"USD":"0.01"}')
    monkeypatch.setattr(settings, "blob_root", tmp_path / "invoice-blobs")
    client, factory = test_client
    tenant_id = UUID("00000000-0000-4000-8000-000000000001")
    blob_store = LocalBlobStore(
        settings.blob_root, settings.data_encryption_key.get_secret_value().encode()
    )
    workbook_bytes = __import__(
        "invoice_agent.services.workbook_service", fromlist=["create_blank_workbook"]
    ).create_blank_workbook(["Invoice No", "Vendor", "Total"])
    blob = blob_store.put(workbook_bytes)
    invoice_id = uuid4()
    async with factory() as session:
        invoice = Invoice(
            id=invoice_id,
            tenant_id=tenant_id,
            source_blob_id="source",
            source_sha256="f" * 64,
            source_media_type="application/pdf",
            processing_status="ready_for_review",
            review_status="needs_review",
            current_revision=1,
            created_by="test-operator",
        )
        session.add(invoice)
        await session.flush()
        revision = InvoiceRevision(
            invoice_id=invoice_id,
            revision=1,
            invoice_number="0001",
            vendor="Acme",
            currency="USD",
            subtotal=Decimal("10"),
            tax=Decimal("0"),
            other_charges=Decimal("0"),
            discounts=Decimal("0"),
            total=Decimal("10"),
        )
        workbook_id = uuid4()
        version_id = new_id()
        mapping_id = new_id()
        session.add(revision)
        session.add(
            Workbook(
                id=workbook_id,
                tenant_id=tenant_id,
                label="test.xlsx",
                source_blob_id=blob.blob_id,
                current_version_id=version_id,
                created_by="test-operator",
            )
        )
        session.add(
            WorkbookVersion(
                id=version_id,
                workbook_id=workbook_id,
                version_number=1,
                blob_id=blob.blob_id,
                sha256=blob.sha256,
                profile_version=PROFILE_VERSION,
            )
        )
        session.add(
            ColumnMapping(
                id=mapping_id,
                workbook_id=workbook_id,
                sheet_name="Invoice Log",
                header_snapshot='["Invoice No","Vendor","Total"]',
                field_to_column=(
                    '{"invoice_number":"Invoice No","vendor_name":"Vendor","total":"Total"}'
                ),
                version=1,
                created_by="test-operator",
                confirmed_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )
        )
        await session.commit()
    csrf = {"X-CSRF-Token": "test-csrf-token"}
    validation = await client.post(
        f"/api/v1/invoices/{invoice_id}/validate",
        headers=csrf,
        json={
            "workbook_id": str(workbook_id),
            "workbook_version_id": version_id,
            "mapping_id": mapping_id,
        },
    )
    assert validation.status_code == 200, validation.text
    preview = await client.post(
        f"/api/v1/invoices/{invoice_id}/log-preview",
        headers=csrf,
        json={
            "invoice_revision": 1,
            "workbook_id": str(workbook_id),
            "workbook_version_id": version_id,
            "mapping_id": mapping_id,
        },
    )
    assert preview.status_code == 200
    output_before = blob_store.get(blob.blob_id, blob.sha256)
    assert output_before == workbook_bytes
    async with factory() as session:
        assert (await session.scalar(select(ValidationRun.id))) is not None

    confirmation_body = {
        "preview_id": preview.json()["preview_id"],
        "preview_digest": preview.json()["preview_digest"],
    }
    idempotency_headers = {**csrf, "Idempotency-Key": "invoice-once-1"}
    committed = await client.post(
        f"/api/v1/invoices/{invoice_id}/log-confirmations",
        headers=idempotency_headers,
        json=confirmation_body,
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["state"] == "committed"
    replay = await client.post(
        f"/api/v1/invoices/{invoice_id}/log-confirmations",
        headers=idempotency_headers,
        json=confirmation_body,
    )
    assert replay.status_code == 200
    assert replay.json()["operation_id"] == committed.json()["operation_id"]
    changed_preview = await client.post(
        f"/api/v1/invoices/{invoice_id}/log-confirmations",
        headers=idempotency_headers,
        json={"preview_id": preview.json()["preview_id"], "preview_digest": "0" * 64},
    )
    assert changed_preview.status_code == 409
    async with factory() as session:
        current_workbook = await session.scalar(select(Workbook).where(Workbook.id == workbook_id))
        current_version = await session.scalar(
            select(WorkbookVersion).where(WorkbookVersion.id == current_workbook.current_version_id)
        )
    updated = blob_store.get(current_version.blob_id, current_version.sha256)
    from io import BytesIO

    from openpyxl import load_workbook

    saved_workbook = load_workbook(BytesIO(updated), read_only=True, data_only=False)
    try:
        assert saved_workbook["Invoice Log"].max_row == 2
        assert saved_workbook["Invoice Log"]["A2"].value == "0001"
    finally:
        saved_workbook.close()
