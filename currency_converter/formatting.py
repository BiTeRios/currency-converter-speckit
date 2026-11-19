"""Formatting utilities for numbers, rates and dates."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from currency_converter.models import ConversionResult, LoadResult, LoadStatus

SAME_CURRENCY_NOTE = "Валюты совпадают — конвертация не требуется"


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


def result_line(r: ConversionResult) -> str:
    """Format conversion result line, e.g. '100,00 USD = 1 833,83 MDL' or '< 0,01 EUR'."""
    amt_str = f"{format_amount(r.amount)} {r.from_code}"
    target = Decimal("0.01")
    quantized_converted = r.converted.quantize(target, rounding=ROUND_HALF_UP)
    if quantized_converted == Decimal("0.00"):
        converted_str = f"< 0,01 {r.to_code}"
    else:
        converted_str = f"{format_amount(r.converted)} {r.to_code}"
    return f"{amt_str} = {converted_str}"


def rates_line(r: ConversionResult) -> str:
    """Format exchange rates line, e.g. '1 USD = 18,3383 MDL · 1 MDL = 0,0545 USD'."""
    direct = f"1 {r.from_code} = {format_rate(r.rate)} {r.to_code}"
    reverse = f"1 {r.to_code} = {format_rate(r.reverse_rate)} {r.from_code}"
    return f"{direct} · {reverse}"


def status_line(result: LoadResult) -> str:
    """Format rate status line with source and publication/offline details."""
    rates_date_str = format_date(result.table.rates_date)
    requested_date_str = format_date(result.table.requested_date)
    fetched_at_str = result.table.fetched_at.strftime("%d.%m.%Y %H:%M")

    if result.status == LoadStatus.LIVE:
        status_text = f"курс на {rates_date_str}"
    elif result.status == LoadStatus.EARLIER_DATE:
        status_text = f"курс на {rates_date_str} (за {requested_date_str} курс не опубликован)"
    else:  # LoadStatus.CACHED — других значений у перечисления нет
        status_text = f"сохранённый курс на {rates_date_str} (офлайн, загружен {fetched_at_str})"

    return f"Источник: {result.table.source} · {status_text}"


def fallback_notice(result: LoadResult) -> str:
    """Format fallback notice when earlier date rates were used."""
    if result.status == LoadStatus.EARLIER_DATE:
        req = format_date(result.table.requested_date)
        rd = format_date(result.table.rates_date)
        return f"За {req} официальный курс не опубликован, использован курс за {rd}"
    return ""


__all__ = [
    "format_amount",
    "format_rate",
    "format_date",
    "SAME_CURRENCY_NOTE",
    "result_line",
    "rates_line",
    "status_line",
    "fallback_notice",
]
