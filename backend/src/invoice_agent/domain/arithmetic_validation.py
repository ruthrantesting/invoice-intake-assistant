from dataclasses import dataclass
from decimal import Decimal

from invoice_agent.domain.amounts import format_amount


@dataclass(frozen=True)
class ArithmeticOutcome:
    outcome: str
    reason: str
    calculated_total: Decimal | None
    difference: Decimal | None


def validate_total(
    *,
    subtotal: Decimal | None,
    tax: Decimal | None,
    other_charges: Decimal | None,
    discounts: Decimal | None,
    stated_total: Decimal | None,
    tolerance: Decimal,
) -> ArithmeticOutcome:
    components = (subtotal, tax, other_charges, discounts, stated_total)
    if any(value is None for value in components):
        return ArithmeticOutcome(
            "not_verifiable",
            "One or more required amounts or signs are unavailable.",
            None,
            None,
        )
    calculated = subtotal + tax + other_charges - discounts
    difference = calculated - stated_total
    if abs(difference) <= tolerance:
        return ArithmeticOutcome(
            "passed",
            f"Calculated total {format_amount(calculated)} is within tolerance {tolerance}.",
            calculated,
            difference,
        )
    return ArithmeticOutcome(
        "flagged",
        f"Calculated total {format_amount(calculated)} differs from stated total "
        f"{format_amount(stated_total)} by {format_amount(difference)}.",
        calculated,
        difference,
    )
