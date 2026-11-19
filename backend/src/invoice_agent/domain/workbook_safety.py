import re
from dataclasses import dataclass
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.workbook import Workbook

from invoice_agent.config import settings


@dataclass(frozen=True)
class WorkbookInspection:
    sheet_names: tuple[str, ...]
    headers: dict[str, tuple[str | None, ...]]


class UnsupportedWorkbookError(ValueError):
    pass


def inspect_xlsx(data: bytes) -> WorkbookInspection:
    if not data.startswith(b"PK"):
        raise UnsupportedWorkbookError("The uploaded file is not a valid .xlsx package.")
    try:
        workbook = load_workbook(BytesIO(data), read_only=False, data_only=False, keep_links=False)
    except Exception as exc:
        raise UnsupportedWorkbookError("The workbook is corrupt or unsupported.") from exc
    try:
        if workbook.vba_archive is not None:
            raise UnsupportedWorkbookError("Macro-enabled workbooks are not supported.")
        headers: dict[str, tuple[str | None, ...]] = {}
        for sheet in workbook.worksheets:
            if sheet.protection.sheet or sheet.protection.password:
                raise UnsupportedWorkbookError("Protected worksheets are not supported.")
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.data_type == "f":
                        raise UnsupportedWorkbookError(
                            "Workbooks containing formulas are not supported by the "
                            "current safety profile."
                        )
            headers[sheet.title] = tuple(
                cell.value if isinstance(cell.value, str) else None for cell in sheet[1]
            )
        if not headers:
            raise UnsupportedWorkbookError("The workbook has no worksheets.")
        return WorkbookInspection(tuple(workbook.sheetnames), headers)
    finally:
        workbook.close()


def safe_text_cell(value: object, max_length: int | None = None) -> str:
    text = str(value)
    max_length = max_length or settings.max_cell_text_length
    if len(text) > max_length:
        raise ValueError("Workbook cell content exceeds the supported text length.")
    if ILLEGAL_CHARACTERS_RE.search(text):
        raise ValueError("Workbook cell content contains unsupported control characters.")
    # Store user data as explicit strings. Prefix potentially executable spreadsheet values.
    if re.match(r"^[\s]*[=+@]", text):
        return "'" + text
    return text


def append_text_row(data: bytes, sheet_name: str, values: list[object]) -> bytes:
    inspection = inspect_xlsx(data)
    if sheet_name not in inspection.sheet_names:
        raise ValueError("The selected worksheet does not exist.")
    workbook: Workbook = load_workbook(BytesIO(data), data_only=False, keep_links=False)
    try:
        sheet = workbook[sheet_name]
        row_index = sheet.max_row + 1
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row_index, column=column)
            cell.value = safe_text_cell(value) if value is not None else None
            cell.data_type = "s" if value is not None else "n"
        output = BytesIO()
        workbook.save(output)
        result = output.getvalue()
    finally:
        workbook.close()
    # Re-read to ensure the produced package remains valid under the same fail-closed profile.
    inspect_xlsx(result)
    verified = load_workbook(BytesIO(result), data_only=False, read_only=True)
    try:
        for column, value in enumerate(values, start=1):
            cell = verified[sheet_name].cell(row=verified[sheet_name].max_row, column=column)
            if value is not None and cell.data_type != "s":
                raise UnsupportedWorkbookError("A generated cell was not serialized as text.")
    finally:
        verified.close()
    return result
