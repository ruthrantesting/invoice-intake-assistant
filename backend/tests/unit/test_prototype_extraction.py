from decimal import Decimal

from invoice_agent.domain.arithmetic_validation import validate_total
from invoice_agent.services.document_service import PageText
from invoice_agent.services.prototype_extraction import extract_prototype_fields

OCR_TEXT = """INVOICE
LOGO
East Repair Inc.
1912 Harvest Lane
New York, NY 12210
BILLTO  SHIPTO  INVOICE#  US-001
John Smith  John Smith  INVOICEDATE  11/02/2019
2 Court Square  3787Pineview Drive  P.0.#  2312/2019
NewYork,NY12210  Cambridge,MA 12210  DUE DATE  26/02/2019
QTY  DESCRIPTION  UNIT PRICE  AMOUNT
1  Front and rear brake cables  100.00  100.00
Subtotal  145.00
Sales Tax6.25%  9.06
TOTAL  $154.06
"""


def test_extracts_sample_invoice_fields_with_evidence() -> None:
    result = extract_prototype_fields([PageText(1, OCR_TEXT, "ocr")])
    assert result.vendor_name.normalized_value == "East Repair Inc."
    assert result.invoice_number.normalized_value == "US-001"
    assert result.invoice_date.normalized_value == "11/02/2019"
    assert result.due_date.normalized_value == "26/02/2019"
    assert result.po_number.normalized_value == "2312/2019"
    assert result.subtotal.normalized_value == "145.00"
    assert result.tax.normalized_value == "9.06"
    assert result.total.normalized_value == "154.06"
    assert result.currency is None  # a bare "$" is not guessed
    assert result.total.page_number == 1 and result.total.evidence_snippet
    outcome = validate_total(
        subtotal=Decimal(result.subtotal.normalized_value),
        tax=Decimal(result.tax.normalized_value),
        other_charges=Decimal(result.other_charges.normalized_value),
        discounts=Decimal(result.discounts.normalized_value),
        stated_total=Decimal(result.total.normalized_value),
        tolerance=Decimal("0.01"),
    )
    assert outcome.outcome == "passed"


def test_missing_fields_stay_empty() -> None:
    result = extract_prototype_fields([PageText(1, "hello world", "pdf_text")])
    assert result.invoice_number is None
    assert result.total is None
    assert result.other_charges is None
    assert result.po_number is None
