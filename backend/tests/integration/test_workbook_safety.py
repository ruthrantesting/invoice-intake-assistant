from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from invoice_agent.domain.workbook_safety import (
    UnsupportedWorkbookError,
    append_text_row,
    inspect_xlsx,
)


def make_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Register"
    sheet.append(["Invoice No", "Vendor", "Total"])
    sheet.append(["00041", "Existing Vendor", "10.00"])
    workbook.create_sheet("Notes")["A1"] = "Keep this sheet"
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_append_preserves_existing_rows_sheets_and_text_values() -> None:
    original = make_workbook()
    updated = append_text_row(original, "Register", ["00042", "=2+2", "12.00"])
    workbook = load_workbook(BytesIO(updated), data_only=False)
    assert workbook["Register"]["A2"].value == "00041"
    assert workbook["Register"]["A3"].value == "00042"
    assert workbook["Register"]["B3"].value == "'=2+2"
    assert workbook["Register"]["B3"].data_type == "s"
    assert workbook["Notes"]["A1"].value == "Keep this sheet"
    workbook.close()


def test_formula_workbooks_are_rejected() -> None:
    workbook = Workbook()
    workbook.active["A1"] = "Header"
    workbook.active["A2"] = "=1+1"
    output = BytesIO()
    workbook.save(output)
    with pytest.raises(UnsupportedWorkbookError, match="formulas"):
        inspect_xlsx(output.getvalue())
