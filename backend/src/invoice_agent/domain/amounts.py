from decimal import Decimal


def format_amount(value: Decimal | None) -> str | None:
    """Plain decimal text with at least two places and no padded zeros or exponent."""
    if value is None:
        return None
    text = format(value, "f")
    whole, _, fraction = text.partition(".")
    fraction = fraction.rstrip("0").ljust(2, "0")
    return f"{whole}.{fraction}"
