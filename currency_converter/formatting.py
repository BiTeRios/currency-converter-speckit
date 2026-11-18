"""Formatting utilities for numbers, rates and dates."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def _format_decimal(value: Decimal, decimals: int) -> str:
    """Format decimal with space thousands separator, comma decimal separator and ROUND_HALF_UP."""
    target = Decimal(10) ** -decimals
    quantized = value.quantize(target, rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    abs_q = abs(quantized)
    s = f"{abs_q:f}"
    int_str, frac_str = s.split(".")
    formatted_int = f"{int(int_str):,}".replace(",", " ")
    return f"{sign}{formatted_int},{frac_str}"


def format_amount(value: Decimal) -> str:
    """Format an amount to 2 decimal places with space thousands separator and comma decimal separator."""
    return _format_decimal(value, 2)


def format_rate(value: Decimal) -> str:
    """Format an exchange rate to 4 decimal places with comma decimal separator, handling < 0,0001."""
    target = Decimal("0.0001")
    quantized = value.quantize(target, rounding=ROUND_HALF_UP)
    if value > 0 and quantized == Decimal("0.0000"):
        return "< 0,0001"
    return _format_decimal(value, 4)


def format_date(day: date) -> str:
    """Format a date in DD.MM.YYYY format."""
    return day.strftime("%d.%m.%Y")


__all__ = [
    "format_amount",
    "format_rate",
    "format_date",
]
