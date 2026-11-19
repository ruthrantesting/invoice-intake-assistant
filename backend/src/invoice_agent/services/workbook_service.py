import hashlib
import json
from io import BytesIO
from uuid import uuid4

from openpyxl import Workbook as OpenPyxlWorkbook

from invoice_agent.domain.workbook_safety import (
    inspect_xlsx,
    safe_text_cell,
)

PROFILE_VERSION = "xlsx-safe-v1"
ALLOWED_INVOICE_FIELDS = {
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "due_date",
    "po_number",
    "currency",
    "subtotal",
    "tax",
    "other_charges",
    "discounts",
    "total",
}


def create_blank_workbook(headers: list[str], sheet_name: str = "Invoice Log") -> bytes:
    if not headers or len(headers) != len(set(headers)):
        raise ValueError("Provide unique, non-empty workbook headers.")
    if any(not header.strip() for header in headers):
        raise ValueError("Workbook headers cannot be empty.")
    workbook = OpenPyxlWorkbook()
    sheet = workbook.active
    sheet.title = sheet_name[:31]
    for column, header in enumerate(headers, start=1):
        sheet.cell(row=1, column=column, value=safe_text_cell(header))
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def inspect_workbook(data: bytes) -> dict[str, object]:
    inspection = inspect_xlsx(data)
    return {
        "profile_version": PROFILE_VERSION,
        "sheets": [
            {"name": name, "headers": list(headers)} for name, headers in inspection.headers.items()
        ],
    }


def validate_mapping(headers: list[str | None], field_to_column: dict[str, str]) -> dict[str, int]:
    if not field_to_column or set(field_to_column) - ALLOWED_INVOICE_FIELDS:
        raise ValueError("Mapping contains unsupported invoice fields.")
    normalized = [header for header in headers if header is not None]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Duplicate workbook headers must be resolved before mapping.")
    if len(field_to_column.values()) != len(set(field_to_column.values())):
        raise ValueError("Each workbook column can be mapped only once.")
    positions = {header: index for index, header in enumerate(headers) if header is not None}
    if set(field_to_column.values()) - positions.keys():
        raise ValueError("Mapping refers to a header not present in the selected worksheet.")
    return {field: positions[header] for field, header in field_to_column.items()}


def build_row(
    headers: list[str | None], mapping: dict[str, str], values: dict[str, object]
) -> list[object | None]:
    validate_mapping(headers, mapping)
    row: list[object | None] = [None] * len(headers)
    positions = {header: index for index, header in enumerate(headers) if header is not None}
    for field_name, header in mapping.items():
        row[positions[header]] = values.get(field_name)
    return row


def serialize_mapping(mapping: dict[str, str]) -> str:
    return json.dumps(mapping, sort_keys=True, separators=(",", ":"))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_id() -> str:
    return uuid4().hex
