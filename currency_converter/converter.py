"""Conversion logic and currency selector options."""

from decimal import Decimal, ROUND_HALF_UP

from currency_converter.errors import ValidationError
from currency_converter.models import ConversionResult, MDL_RATE, RateTable


def convert(
    amount: Decimal,
    from_code: str,
    to_code: str,
    table: RateTable,
) -> ConversionResult:
    """Convert amount between two currencies using rates from table.

    1) Unknown from_code or to_code -> ValidationError("Выберите валюту из списка.") (checked first)
    2) Same code -> converted = amount (quantized 0.01), rates = 1.0000, same_currency=True
    3) Different codes -> amount * per_unit(from) / per_unit(to)
    """
    if from_code not in table.codes or to_code not in table.codes:
        raise ValidationError("Выберите валюту из списка.")

    if from_code == to_code:
        return ConversionResult(
            amount=amount,
            from_code=from_code,
            to_code=to_code,
            converted=amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            rate=Decimal("1.0000"),
            reverse_rate=Decimal("1.0000"),
            same_currency=True,
        )

    rate_from = table.get(from_code)
    rate_to = table.get(to_code)

    per_unit_from = rate_from.per_unit
    per_unit_to = rate_to.per_unit

    converted = (amount * per_unit_from / per_unit_to).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    rate = (per_unit_from / per_unit_to).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    reverse_rate = (per_unit_to / per_unit_from).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

    return ConversionResult(
        amount=amount,
        from_code=from_code,
        to_code=to_code,
        converted=converted,
        rate=rate,
        reverse_rate=reverse_rate,
        same_currency=False,
    )


def currency_options(table: RateTable) -> list[tuple[str, str]]:
    """Return currency options [(code, f"{code} — {name}")].

    Sorted with MDL, EUR, USD (if present) first, then the rest sorted alphabetically by code.
    """
    options: list[tuple[str, str]] = [("MDL", f"MDL — {MDL_RATE.name}")]
    if "EUR" in table.rates:
        options.append(("EUR", f"EUR — {table.rates['EUR'].name}"))
    if "USD" in table.rates:
        options.append(("USD", f"USD — {table.rates['USD'].name}"))

    remaining_codes = sorted(k for k in table.rates if k not in ("EUR", "USD"))
    for code in remaining_codes:
        options.append((code, f"{code} — {table.rates[code].name}"))

    return options


__all__ = [
    "convert",
    "currency_options",
]
