"""Input validation for amounts and dates."""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from currency_converter.errors import ValidationError

MAX_AMOUNT = Decimal("1000000000000")
MIN_RATE_DATE = date(2000, 1, 1)

MSG_AMOUNT_EMPTY = "Введите сумму."
MSG_AMOUNT_NOT_NUMBER = "Введите число, например 150 или 99,95."
MSG_AMOUNT_NOT_POSITIVE = "Сумма должна быть больше нуля."
MSG_AMOUNT_TOO_PRECISE = "Не больше двух знаков после запятой."
MSG_AMOUNT_TOO_LARGE = "Сумма не должна превышать 1 000 000 000 000."
MSG_DATE_FORMAT = "Введите дату в формате ДД.ММ.ГГГГ, например 18.11.2026."
MSG_DATE_RANGE = "Дата должна быть не раньше 01.01.2000 и не позже {max_date}."


def parse_amount(text: str) -> Decimal:
    """Validate and parse an amount string into a positive Decimal with <= 2 decimal places."""
    stripped = text.strip()
    if not stripped:
        raise ValidationError(MSG_AMOUNT_EMPTY)

    cleaned = stripped.replace(" ", "").replace("\u00a0", "").replace(",", ".")

    if not re.match(r"^-?\d+(\.\d+)?$", cleaned):
        raise ValidationError(MSG_AMOUNT_NOT_NUMBER)

    try:
        val = Decimal(cleaned)
    except InvalidOperation:
        raise ValidationError(MSG_AMOUNT_NOT_NUMBER)

    if val <= 0:
        raise ValidationError(MSG_AMOUNT_NOT_POSITIVE)

    if "." in cleaned and len(cleaned.split(".")[1]) > 2:
        raise ValidationError(MSG_AMOUNT_TOO_PRECISE)

    if val > MAX_AMOUNT:
        raise ValidationError(MSG_AMOUNT_TOO_LARGE)

    return val


def parse_rate_date(text: str, today: date) -> date:
    """Validate and parse a date string in DD.MM.YYYY format within [MIN_RATE_DATE, today + 1 day]."""
    stripped = text.strip()
    if not re.match(r"^\d{1,2}\.\d{1,2}\.\d{4}$", stripped):
        raise ValidationError(MSG_DATE_FORMAT)

    try:
        parsed_date = datetime.strptime(stripped, "%d.%m.%Y").date()
    except ValueError:
        raise ValidationError(MSG_DATE_FORMAT)

    max_date = today + timedelta(days=1)
    if parsed_date < MIN_RATE_DATE or parsed_date > max_date:
        max_date_str = max_date.strftime("%d.%m.%Y")
        raise ValidationError(MSG_DATE_RANGE.format(max_date=max_date_str))

    return parsed_date


__all__ = [
    "MAX_AMOUNT",
    "MIN_RATE_DATE",
    "MSG_AMOUNT_EMPTY",
    "MSG_AMOUNT_NOT_NUMBER",
    "MSG_AMOUNT_NOT_POSITIVE",
    "MSG_AMOUNT_TOO_PRECISE",
    "MSG_AMOUNT_TOO_LARGE",
    "MSG_DATE_FORMAT",
    "MSG_DATE_RANGE",
    "parse_amount",
    "parse_rate_date",
]
