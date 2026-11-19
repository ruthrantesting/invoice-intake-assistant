"""Local, deterministic, line-based field extraction used only in prototype mode.

Values are always taken from document text. Nothing is guessed: a field with no match stays empty.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from invoice_agent.services.document_service import PageText
from invoice_agent.services.extraction_service import ExtractedField, InvoiceExtraction

NOTE = "Prototype text-pattern extraction; verify against the original document."
AMOUNT = r"([0-9][0-9,]*\.\d{2})"
DATE = r"([0-9]{1,4}[/.\-][0-9]{1,2}[/.\-][0-9]{1,4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})"
TOKEN = r"([A-Za-z0-9][A-Za-z0-9./\-]*)"
VENDOR_STOP = {
    "invoice",
    "tax invoice",
    "logo",
    "company logo",
    "bill to",
    "ship to",
    "receipt",
    "original",
    "copy",
}
COMPANY_SUFFIX = re.compile(
    r"\b(inc|llc|ltd|limited|corp|corporation|gmbh|co|company|plc|pty|sa|ag|bv|s\.?r\.?l)\b\.?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Line:
    page: int
    text: str


def extract_prototype_fields(pages: Sequence[PageText]) -> InvoiceExtraction:
    lines = [
        _Line(page.page_number, stripped)
        for page in pages
        for raw in page.text.splitlines()
        if (stripped := raw.strip())
    ]

    def find(pattern: str, *, last: bool = False, group: int = 1) -> ExtractedField | None:
        compiled = re.compile(pattern, re.IGNORECASE)
        hits = [(line, match) for line in lines if (match := compiled.search(line.text))]
        if not hits:
            return None
        line, match = hits[-1] if last else hits[0]
        raw = match.group(group).strip().rstrip(".,;")
        return _field(raw, line, match.group(0).strip(), 0.4)

    def money(field: ExtractedField | None) -> ExtractedField | None:
        if field is None or field.raw_value is None:
            return field
        return field.model_copy(update={"normalized_value": field.raw_value.replace(",", "")})

    subtotal = money(find(rf"sub\s*-?\s*total\D{{0,12}}{AMOUNT}"))
    tax = money(
        find(
            rf"(?:sales\s*tax|vat|gst|tax)(?:\s*\(?[0-9.]+\s*%\)?)?[^0-9\n]{{0,12}}{AMOUNT}",
            last=True,
        )
    )
    total = money(
        find(
            rf"(?<![A-Za-z])(?:grand\s+total|total\s+due|amount\s+due|balance\s+due|total)"
            rf"[^0-9\n]{{0,16}}{AMOUNT}",
            last=True,
        )
    )
    other = _assumed_zero("other_charges", subtotal, total)
    discounts = _assumed_zero("discounts", subtotal, total)
    return InvoiceExtraction(
        vendor_name=_vendor(lines),
        invoice_number=find(rf"invoice\s*(?:number|no\.?|num|#)\s*[:#\-]?\s*{TOKEN}"),
        invoice_date=find(rf"(?:invoice\s*date|date\s+of\s+issue)\D{{0,4}}{DATE}")
        or find(rf"(?<![A-Za-z])(?<!due\s)date\b[^0-9A-Za-z\n]{{0,4}}{DATE}"),
        due_date=find(rf"due\s*date\D{{0,4}}{DATE}") or find(rf"payment\s+due\D{{0,4}}{DATE}"),
        po_number=find(
            rf"(?:p\.?\s*[o0]\.?\s*(?:number|no\.?|num|#)|purchase\s+order(?:\s*(?:number|no\.?|#))?)"
            rf"\s*[:#\-]?\s*{TOKEN}"
        ),
        currency=_currency(lines),
        subtotal=subtotal,
        tax=tax,
        other_charges=other,
        discounts=discounts,
        total=total,
        line_items=[],
    )


def _field(raw: str, line: _Line, snippet: str, confidence: float) -> ExtractedField:
    return ExtractedField(
        raw_value=raw,
        normalized_value=raw,
        page_number=line.page,
        evidence_snippet=snippet,
        confidence=confidence,
        uncertainty=NOTE,
    )


def _currency(lines: list[_Line]) -> ExtractedField | None:
    pattern = re.compile(r"\b(USD|EUR|GBP|CAD|AUD)\b")
    for line in lines:
        match = pattern.search(line.text)
        if match:
            return _field(match.group(1), line, match.group(0), 0.5)
    return None  # A bare "$" or "€" symbol is ambiguous and is never guessed.


def _vendor(lines: list[_Line]) -> ExtractedField | None:
    labelled = re.compile(r"^(?:vendor|supplier|from)\s*[:\-]\s*(.+)$", re.IGNORECASE)
    for line in lines:
        match = labelled.match(line.text)
        if match:
            return _field(match.group(1).strip(), line, line.text, 0.4)
    candidates = [
        line
        for line in lines[:12]
        if re.search(r"[A-Za-z]{3,}", line.text)
        and line.text.lower().strip(" :#") not in VENDOR_STOP
        and not re.search(
            r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\binvoice\b|\bbill\s*to\b", line.text, re.I
        )
    ]
    for line in candidates:
        if COMPANY_SUFFIX.search(line.text):
            return _field(line.text, line, line.text, 0.35)
    return (
        _field(candidates[0].text, candidates[0], candidates[0].text, 0.2) if candidates else None
    )


def _assumed_zero(
    name: str, subtotal: ExtractedField | None, total: ExtractedField | None
) -> ExtractedField | None:
    if subtotal is None or total is None:
        return None
    return ExtractedField(
        raw_value=None,
        normalized_value="0.00",
        page_number=None,
        evidence_snippet=None,
        confidence=0.1,
        uncertainty=(
            f"No {name.replace('_', ' ')} line was found; 0.00 was assumed so totals can be "
            "checked. Correct it if the document shows one."
        ),
    )
