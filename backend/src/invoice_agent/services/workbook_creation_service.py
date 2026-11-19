from invoice_agent.services.workbook_service import create_blank_workbook


def create_log(name: str, headers: list[str]) -> tuple[str, bytes]:
    label = name.strip()
    if not label or len(label) > 255:
        raise ValueError("Workbook name must contain 1–255 characters.")
    if len(headers) > 200:
        raise ValueError("A workbook log cannot contain more than 200 columns.")
    return label, create_blank_workbook(headers)
