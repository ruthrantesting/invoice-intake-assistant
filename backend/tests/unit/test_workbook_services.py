import pytest

from invoice_agent.services.workbook_creation_service import create_log
from invoice_agent.services.workbook_service import build_row, validate_mapping


def test_new_log_validates_unique_nonempty_headers() -> None:
    label, data = create_log("AP log", ["Invoice No", "Total"])
    assert label == "AP log"
    assert data.startswith(b"PK")
    with pytest.raises(ValueError, match="unique"):
        create_log("AP log", ["Total", "Total"])


def test_mapping_leaves_unmapped_columns_blank_and_rejects_duplicates() -> None:
    headers = ["Vendor", "Invoice No", "Total"]
    row = build_row(
        headers,
        {"vendor_name": "Vendor", "total": "Total"},
        {"vendor_name": "Acme", "total": "12.00"},
    )
    assert row == ["Acme", None, "12.00"]
    with pytest.raises(ValueError, match="only once"):
        validate_mapping(headers, {"vendor_name": "Vendor", "invoice_number": "Vendor"})
