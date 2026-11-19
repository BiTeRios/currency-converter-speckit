"""Tests for amount and date input validation."""

from datetime import date
from decimal import Decimal

import pytest

from currency_converter.errors import ValidationError
from currency_converter.validation import (
    MAX_AMOUNT,
    MIN_RATE_DATE,
    MSG_AMOUNT_EMPTY,
    MSG_AMOUNT_NOT_NUMBER,
    MSG_AMOUNT_NOT_POSITIVE,
    MSG_AMOUNT_TOO_LARGE,
    MSG_AMOUNT_TOO_PRECISE,
    MSG_DATE_FORMAT,
    MSG_DATE_RANGE,
    parse_amount,
    parse_rate_date,
)

TODAY = date(2026, 11, 18)
TOMORROW_STR = "19.11.2026"


# =============================================================================
# Amount Validation: Accepted Cases
# =============================================================================


@pytest.mark.parametrize(
    "raw_text, expected",
    [
        ("150", Decimal("150")),
        ("99.95", Decimal("99.95")),
        ("99,95", Decimal("99.95")),
        ("1.5", Decimal("1.5")),
        ("1,5", Decimal("1.5")),
        ("0.01", Decimal("0.01")),
        ("0,01", Decimal("0.01")),
        (" 1 500,50 ", Decimal("1500.50")),
        (" 150 ", Decimal("150")),
        ("1 000 000.00", Decimal("1000000.00")),
        ("1\u00a0500,50", Decimal("1500.50")),  # Non-breaking space
        ("1000000000000", MAX_AMOUNT),
        ("1 000 000 000 000,00", MAX_AMOUNT),
    ],
)
def test_parse_amount_accepted(raw_text: str, expected: Decimal):
    assert parse_amount(raw_text) == expected


# =============================================================================
# Amount Validation: Rejected Cases
# =============================================================================


@pytest.mark.parametrize(
    "empty_text",
    ["", "   ", "\t", "\n", " \t \n "],
)
def test_parse_amount_empty_rejected(empty_text: str):
    with pytest.raises(ValidationError) as exc_info:
        parse_amount(empty_text)
    assert str(exc_info.value) == MSG_AMOUNT_EMPTY


@pytest.mark.parametrize(
    "invalid_text",
    [
        "abc",
        "12a",
        "1e5",
        "NaN",
        "inf",
        "-inf",
        "--5",
        "1.2.3",
        "1,2,3",
        "$100",
        "+100",
        ".",
        ",",
        "-.",
        "-",
    ],
)
def test_parse_amount_not_number_rejected(invalid_text: str):
    with pytest.raises(ValidationError) as exc_info:
        parse_amount(invalid_text)
    assert str(exc_info.value) == MSG_AMOUNT_NOT_NUMBER


@pytest.mark.parametrize(
    "non_positive_text",
    ["0", "0.0", "0.00", "0,00", "-0", "-10", "-0.01", "-1 500,50", "-100"],
)
def test_parse_amount_not_positive_rejected(non_positive_text: str):
    with pytest.raises(ValidationError) as exc_info:
        parse_amount(non_positive_text)
    assert str(exc_info.value) == MSG_AMOUNT_NOT_POSITIVE


@pytest.mark.parametrize(
    "too_precise_text",
    ["10.123", "0.001", "1,999", "150.0001", "1 500,555"],
)
def test_parse_amount_too_precise_rejected(too_precise_text: str):
    with pytest.raises(ValidationError) as exc_info:
        parse_amount(too_precise_text)
    assert str(exc_info.value) == MSG_AMOUNT_TOO_PRECISE


@pytest.mark.parametrize(
    "too_large_text",
    [
        "1000000000000.01",
        "1 000 000 000 001",
        "999999999999999",
        "1000000000000,05",
    ],
)
def test_parse_amount_too_large_rejected(too_large_text: str):
    with pytest.raises(ValidationError) as exc_info:
        parse_amount(too_large_text)
    assert str(exc_info.value) == MSG_AMOUNT_TOO_LARGE


# =============================================================================
# Date Validation: Accepted Cases
# =============================================================================


@pytest.mark.parametrize(
    "date_text, expected",
    [
        ("18.11.2026", date(2026, 11, 18)),
        (" 18.11.2026 ", date(2026, 11, 18)),
        ("19.11.2026", date(2026, 11, 19)),  # Tomorrow is allowed
        ("01.01.2000", MIN_RATE_DATE),  # Earliest allowed
        ("15.06.2015", date(2015, 6, 15)),
        ("5.1.2026", date(2026, 1, 5)),  # Single digit day/month accepted
    ],
)
def test_parse_rate_date_accepted(date_text: str, expected: date):
    assert parse_rate_date(date_text, TODAY) == expected


# =============================================================================
# Date Validation: Rejected Format Cases
# =============================================================================


@pytest.mark.parametrize(
    "bad_format",
    [
        "2026-11-18",
        "18/11/2026",
        "",
        "   ",
        "abc",
        "18.11",
        "18.11.26",
        "18.11.2026.01",
    ],
)
def test_parse_rate_date_bad_format_rejected(bad_format: str):
    with pytest.raises(ValidationError) as exc_info:
        parse_rate_date(bad_format, TODAY)
    assert str(exc_info.value) == MSG_DATE_FORMAT


@pytest.mark.parametrize(
    "impossible_date",
    [
        "31.02.2026",
        "29.02.2025",  # 2025 is not a leap year
        "32.01.2026",
        "00.01.2026",
        "15.13.2026",
    ],
)
def test_parse_rate_date_impossible_rejected(impossible_date: str):
    with pytest.raises(ValidationError) as exc_info:
        parse_rate_date(impossible_date, TODAY)
    assert str(exc_info.value) == MSG_DATE_FORMAT


# =============================================================================
# Date Validation: Out of Range Cases
# =============================================================================


@pytest.mark.parametrize(
    "too_early_date",
    ["31.12.1999", "01.01.1990", "15.08.1985"],
)
def test_parse_rate_date_before_2000_rejected(too_early_date: str):
    expected_msg = MSG_DATE_RANGE.format(max_date=TOMORROW_STR)
    with pytest.raises(ValidationError) as exc_info:
        parse_rate_date(too_early_date, TODAY)
    assert str(exc_info.value) == expected_msg


@pytest.mark.parametrize(
    "too_late_date",
    ["20.11.2026", "21.11.2026", "25.12.2030"],  # Day after tomorrow and later
)
def test_parse_rate_date_after_tomorrow_rejected(too_late_date: str):
    expected_msg = MSG_DATE_RANGE.format(max_date=TOMORROW_STR)
    with pytest.raises(ValidationError) as exc_info:
        parse_rate_date(too_late_date, TODAY)
    assert str(exc_info.value) == expected_msg
