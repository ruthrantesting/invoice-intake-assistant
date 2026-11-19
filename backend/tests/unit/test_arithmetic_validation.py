from decimal import Decimal

import pytest

from invoice_agent.domain.arithmetic_validation import validate_total


def test_total_matches_within_configured_decimal_tolerance() -> None:
    result = validate_total(
        subtotal=Decimal("2480.00"),
        tax=Decimal("198.40"),
        other_charges=Decimal("0"),
        discounts=Decimal("0"),
        stated_total=Decimal("2678.40"),
        tolerance=Decimal("0.01"),
    )
    assert result.outcome == "passed"
    assert result.calculated_total == Decimal("2678.40")


def test_total_mismatch_is_flagged() -> None:
    result = validate_total(
        subtotal=Decimal("100"),
        tax=Decimal("5"),
        other_charges=Decimal("0"),
        discounts=Decimal("0"),
        stated_total=Decimal("110"),
        tolerance=Decimal("0.01"),
    )
    assert result.outcome == "flagged"
    assert result.difference == Decimal("-5")


@pytest.mark.parametrize("field", ["subtotal", "tax", "other_charges", "discounts", "stated_total"])
def test_missing_arithmetic_component_is_not_verifiable(field: str) -> None:
    values = {
        "subtotal": Decimal("100"),
        "tax": Decimal("5"),
        "other_charges": Decimal("0"),
        "discounts": Decimal("0"),
        "stated_total": Decimal("105"),
    }
    values[field] = None
    result = validate_total(**values, tolerance=Decimal("0.01"))
    assert result.outcome == "not_verifiable"
    assert result.calculated_total is None
