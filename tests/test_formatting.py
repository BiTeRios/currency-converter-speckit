"""Tests for formatting amounts, rates, dates, conversion results, status lines and fallback notices."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from currency_converter import SOURCE_NAME
from currency_converter.formatting import (
    SAME_CURRENCY_NOTE,
    fallback_notice,
    format_amount,
    format_date,
    format_rate,
    rates_line,
    result_line,
    status_line,
)
from currency_converter.models import ConversionResult, LoadResult, LoadStatus, RateTable


@pytest.fixture
def base_rate_table() -> RateTable:
    return RateTable(
        rates_date=date(2026, 11, 18),
        requested_date=date(2026, 11, 18),
        source=SOURCE_NAME,
        fetched_at=datetime(2026, 11, 18, 14, 3, 12),
        rates={},
    )


# =============================================================================
# Amount Formatting Tests
# =============================================================================


@pytest.mark.parametrize(
    "value, expected",
    [
        (Decimal("1833.83"), "1 833,83"),
        (Decimal("100"), "100,00"),
        (Decimal("100.5"), "100,50"),
        (Decimal("0"), "0,00"),
        (Decimal("0.05"), "0,05"),
        (Decimal("1234567.89"), "1 234 567,89"),
        (Decimal("1000000000000"), "1 000 000 000 000,00"),
        # ROUND_HALF_UP rounding
        (Decimal("1.005"), "1,01"),
        (Decimal("1.004"), "1,00"),
        (Decimal("1.125"), "1,13"),
        (Decimal("1.124"), "1,12"),
        (Decimal("2.555"), "2,56"),
        (Decimal("2.554"), "2,55"),
    ],
)
def test_format_amount(value: Decimal, expected: str):
    assert format_amount(value) == expected


# =============================================================================
# Rate Formatting Tests
# =============================================================================


@pytest.mark.parametrize(
    "value, expected",
    [
        (Decimal("18.3383"), "18,3383"),
        (Decimal("1"), "1,0000"),
        (Decimal("1.0000"), "1,0000"),
        (Decimal("0.0545"), "0,0545"),
        (Decimal("174.9993"), "174,9993"),
        (Decimal("1234.5678"), "1 234,5678"),
        (Decimal("0"), "0,0000"),
        # ROUND_HALF_UP rounding
        (Decimal("18.33835"), "18,3384"),
        (Decimal("18.33834"), "18,3383"),
        # < 0,0001 rule: positive value rounding to 0.0000
        (Decimal("0.00004"), "< 0,0001"),
        (Decimal("0.00001"), "< 0,0001"),
        (Decimal("0.000001"), "< 0,0001"),
        (Decimal("0.000049"), "< 0,0001"),
        # Edge of < 0,0001: 0.00005 rounds to 0.0001
        (Decimal("0.00005"), "0,0001"),
    ],
)
def test_format_rate(value: Decimal, expected: str):
    assert format_rate(value) == expected


# =============================================================================
# Date Formatting Tests
# =============================================================================


@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2026, 11, 18), "18.11.2026"),
        (date(2026, 1, 5), "05.01.2026"),
        (date(2000, 1, 1), "01.01.2000"),
    ],
)
def test_format_date(day: date, expected: str):
    assert format_date(day) == expected


# =============================================================================
# Result Line and Rates Line Tests
# =============================================================================


def test_result_line_standard():
    r = ConversionResult(
        amount=Decimal("100"),
        from_code="USD",
        to_code="MDL",
        converted=Decimal("1833.83"),
        rate=Decimal("18.3383"),
        reverse_rate=Decimal("0.0545"),
        same_currency=False,
    )
    assert result_line(r) == "100,00 USD = 1 833,83 MDL"


def test_result_line_large_amount():
    r = ConversionResult(
        amount=Decimal("1000000"),
        from_code="EUR",
        to_code="MDL",
        converted=Decimal("20153800.00"),
        rate=Decimal("20.1538"),
        reverse_rate=Decimal("0.0496"),
        same_currency=False,
    )
    assert result_line(r) == "1 000 000,00 EUR = 20 153 800,00 MDL"


def test_result_line_less_than_001_rule():
    # Converted amount rounds to 0.00 -> "< 0,01 CODE"
    r = ConversionResult(
        amount=Decimal("0.10"),
        from_code="MDL",
        to_code="EUR",
        converted=Decimal("0.00"),
        rate=Decimal("0.0496"),
        reverse_rate=Decimal("20.1538"),
        same_currency=False,
    )
    assert result_line(r) == "0,10 MDL = < 0,01 EUR"

    r_small = ConversionResult(
        amount=Decimal("0.05"),
        from_code="MDL",
        to_code="USD",
        converted=Decimal("0.0027"),
        rate=Decimal("0.0545"),
        reverse_rate=Decimal("18.3383"),
        same_currency=False,
    )
    assert result_line(r_small) == "0,05 MDL = < 0,01 USD"


def test_rates_line_standard():
    r = ConversionResult(
        amount=Decimal("100"),
        from_code="USD",
        to_code="MDL",
        converted=Decimal("1833.83"),
        rate=Decimal("18.3383"),
        reverse_rate=Decimal("0.0545"),
        same_currency=False,
    )
    assert rates_line(r) == "1 USD = 18,3383 MDL · 1 MDL = 0,0545 USD"


def test_rates_line_with_less_than_0001_rate():
    r = ConversionResult(
        amount=Decimal("100"),
        from_code="UZS",
        to_code="GBP",
        converted=Decimal("0.01"),
        rate=Decimal("0.00004"),
        reverse_rate=Decimal("15849.5412"),
        same_currency=False,
    )
    assert rates_line(r) == "1 UZS = < 0,0001 GBP · 1 GBP = 15 849,5412 UZS"


# =============================================================================
# Status Line and Fallback Notice Tests
# =============================================================================


def test_status_line_live(base_rate_table):
    lr = LoadResult(table=base_rate_table, status=LoadStatus.LIVE)
    assert status_line(lr) == "Источник: Национальный банк Молдовы, bnm.md · курс на 18.11.2026"


def test_status_line_earlier_date():
    table = RateTable(
        rates_date=date(2026, 11, 16),
        requested_date=date(2026, 11, 18),
        source=SOURCE_NAME,
        fetched_at=datetime(2026, 11, 18, 14, 3, 12),
        rates={},
    )
    lr = LoadResult(table=table, status=LoadStatus.EARLIER_DATE)
    assert status_line(lr) == (
        "Источник: Национальный банк Молдовы, bnm.md · "
        "курс на 16.11.2026 (за 18.11.2026 курс не опубликован)"
    )


def test_status_line_cached(base_rate_table):
    lr = LoadResult(table=base_rate_table, status=LoadStatus.CACHED)
    assert status_line(lr) == (
        "Источник: Национальный банк Молдовы, bnm.md · "
        "сохранённый курс на 18.11.2026 (офлайн, загружен 18.11.2026 14:03)"
    )


def test_fallback_notice():
    table_earlier = RateTable(
        rates_date=date(2026, 11, 16),
        requested_date=date(2026, 11, 18),
        source=SOURCE_NAME,
        fetched_at=datetime(2026, 11, 18, 14, 3, 12),
        rates={},
    )
    lr_earlier = LoadResult(table=table_earlier, status=LoadStatus.EARLIER_DATE)
    assert (
        fallback_notice(lr_earlier)
        == "За 18.11.2026 официальный курс не опубликован, использован курс за 16.11.2026"
    )

    table_live = RateTable(
        rates_date=date(2026, 11, 18),
        requested_date=date(2026, 11, 18),
        source=SOURCE_NAME,
        fetched_at=datetime(2026, 11, 18, 14, 3, 12),
        rates={},
    )
    lr_live = LoadResult(table=table_live, status=LoadStatus.LIVE)
    assert fallback_notice(lr_live) == ""

    lr_cached = LoadResult(table=table_live, status=LoadStatus.CACHED)
    assert fallback_notice(lr_cached) == ""


def test_same_currency_note_constant():
    assert SAME_CURRENCY_NOTE == "Валюты совпадают — конвертация не требуется"
