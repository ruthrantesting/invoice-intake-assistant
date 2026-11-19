from dataclasses import dataclass
from decimal import Decimal

from invoice_agent.domain.arithmetic_validation import ArithmeticOutcome, validate_total
from invoice_agent.domain.duplicate_validation import (
    DuplicateCandidate,
    DuplicateMatch,
    find_duplicate_matches,
)


@dataclass(frozen=True)
class ValidationResult:
    check_type: str
    outcome: str
    reason: str
    matched_record_id: str | None = None
    comparison_scope: str | None = None


def run_issue_checks(
    *,
    subtotal: Decimal | None,
    tax: Decimal | None,
    other_charges: Decimal | None,
    discounts: Decimal | None,
    total: Decimal | None,
    tolerance: Decimal,
    po_number: str | None,
    invoice_number: str | None,
    vendor: str | None,
    source_sha256: str | None,
    candidates: list[DuplicateCandidate],
    comparison_scope: str,
) -> list[ValidationResult]:
    arithmetic: ArithmeticOutcome = validate_total(
        subtotal=subtotal,
        tax=tax,
        other_charges=other_charges,
        discounts=discounts,
        stated_total=total,
        tolerance=tolerance,
    )
    results = [ValidationResult("arithmetic", arithmetic.outcome, arithmetic.reason)]
    if not po_number or not po_number.strip():
        results.append(
            ValidationResult(
                "missing_po", "flagged", "No readable purchase order number was found."
            )
        )
    else:
        results.append(
            ValidationResult("missing_po", "passed", "A purchase order number is present.")
        )
    matches: list[DuplicateMatch] = find_duplicate_matches(
        invoice_number=invoice_number,
        vendor=vendor,
        source_sha256=source_sha256,
        candidates=candidates,
        scope=comparison_scope,
    )
    if matches:
        results.extend(
            ValidationResult("duplicate", "flagged", match.reason, match.record_id, match.scope)
            for match in matches
        )
    else:
        results.append(
            ValidationResult(
                "duplicate", "passed", f"No possible duplicate found in {comparison_scope}."
            )
        )
    return results
