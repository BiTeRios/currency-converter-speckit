"""Tests for currency conversion logic, options sorting, round-trip tolerance and performance."""

import itertools
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from currency_converter.bnm_source import parse_rates
from currency_converter.converter import convert, currency_options
from currency_converter.errors import ValidationError
from currency_converter.models import CurrencyRate, RateTable

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module")
def sample_table() -> RateTable:
    """Loaded rate table from the official BNM sample of 18.11.2026."""
    xml_path = FIXTURES_DIR / "bnm_2026-11-18.xml"
    return parse_rates(xml_path.read_bytes(), requested_date=date(2026, 11, 18))


# =============================================================================
# Worked Examples from contracts/core-api.md
# =============================================================================


def test_worked_example_usd_to_mdl(sample_table):
    r = convert(Decimal("100"), "USD", "MDL", sample_table)
    assert r.amount == Decimal("100")
    assert r.from_code == "USD"
    assert r.to_code == "MDL"
    assert r.converted == Decimal("1833.83")
    assert r.rate == Decimal("18.3383")
    assert r.reverse_rate == Decimal("0.0545")
    assert r.same_currency is False


def test_worked_example_mdl_to_usd_reverse(sample_table):
    r = convert(Decimal("1833.83"), "MDL", "USD", sample_table)
    assert r.amount == Decimal("1833.83")
    assert r.from_code == "MDL"
    assert r.to_code == "USD"
    assert r.converted == Decimal("100.00")
    assert r.rate == Decimal("0.0545")
    assert r.reverse_rate == Decimal("18.3383")
    assert r.same_currency is False


def test_worked_example_eur_to_jpy_cross_rate(sample_table):
    # 100 EUR to JPY: 100 * 20.1538 / (11.5165 / 100) = 17499.9348... -> 17499.93
    r = convert(Decimal("100"), "EUR", "JPY", sample_table)
    assert r.amount == Decimal("100")
    assert r.from_code == "EUR"
    assert r.to_code == "JPY"
    assert r.converted == Decimal("17499.93")
    assert r.rate == Decimal("174.9993")
    assert r.reverse_rate == Decimal("0.0057")
    assert r.same_currency is False


def test_worked_example_same_currency(sample_table):
    r = convert(Decimal("50"), "EUR", "EUR", sample_table)
    assert r.amount == Decimal("50")
    assert r.from_code == "EUR"
    assert r.to_code == "EUR"
    assert r.converted == Decimal("50.00")
    assert r.rate == Decimal("1.0000")
    assert r.reverse_rate == Decimal("1.0000")
    assert r.same_currency is True


# =============================================================================
# Reverse Direction and Cross Rate Tests
# =============================================================================


def test_convert_reverse_direction_eur_and_mdl(sample_table):
    r1 = convert(Decimal("100"), "EUR", "MDL", sample_table)
    assert r1.converted == Decimal("2015.38")
    assert r1.rate == Decimal("20.1538")
    assert r1.reverse_rate == Decimal("0.0496")

    r2 = convert(r1.converted, "MDL", "EUR", sample_table)
    assert r2.converted == Decimal("100.00")
    assert r2.rate == Decimal("0.0496")
    assert r2.reverse_rate == Decimal("20.1538")


def test_convert_cross_rate_nominal_100_jpy_usd(sample_table):
    # JPY nominal 100, value 11.5165 -> per_unit = 0.115165
    # USD nominal 1, value 18.3383 -> per_unit = 18.3383
    # 1000 JPY to USD = 1000 * 0.115165 / 18.3383 = 6.2800... -> 6.28
    r = convert(Decimal("1000"), "JPY", "USD", sample_table)
    assert r.converted == Decimal("6.28")
    assert r.rate == Decimal("0.0063")
    assert r.reverse_rate == Decimal("159.2350")

    # Reverse: 6.28 USD to JPY = 6.28 * 18.3383 / 0.115165 = 999.996... -> 1000.00
    r_rev = convert(r.converted, "USD", "JPY", sample_table)
    assert r_rev.converted == Decimal("1000.00")


def test_convert_cross_rate_two_nominal_100_currencies(sample_table):
    # JPY nominal 100, value 11.5165 -> per_unit = 0.115165
    # HUF nominal 100, value 5.5244 -> per_unit = 0.055244
    # 100 JPY to HUF = 100 * 0.115165 / 0.055244 = 208.466... -> 208.47
    r = convert(Decimal("100"), "JPY", "HUF", sample_table)
    assert r.converted == Decimal("208.47")
    assert r.rate == Decimal("2.0847")
    assert r.reverse_rate == Decimal("0.4797")


def test_convert_same_currency_mdl(sample_table):
    r = convert(Decimal("123.456"), "MDL", "MDL", sample_table)
    assert r.converted == Decimal("123.46")
    assert r.rate == Decimal("1.0000")
    assert r.reverse_rate == Decimal("1.0000")
    assert r.same_currency is True


def test_convert_same_currency_foreign_usd(sample_table):
    r = convert(Decimal("99.95"), "USD", "USD", sample_table)
    assert r.converted == Decimal("99.95")
    assert r.rate == Decimal("1.0000")
    assert r.reverse_rate == Decimal("1.0000")
    assert r.same_currency is True


# =============================================================================
# Validation and Unknown Currency Tests
# =============================================================================


def test_convert_unknown_from_code(sample_table):
    with pytest.raises(ValidationError) as exc_info:
        convert(Decimal("100"), "XYZ", "MDL", sample_table)
    assert str(exc_info.value) == "Выберите валюту из списка."


def test_convert_unknown_to_code(sample_table):
    with pytest.raises(ValidationError) as exc_info:
        convert(Decimal("100"), "MDL", "XYZ", sample_table)
    assert str(exc_info.value) == "Выберите валюту из списка."


def test_convert_both_unknown_same_code(sample_table):
    # Unknown code check MUST happen before same-currency check
    with pytest.raises(ValidationError) as exc_info:
        convert(Decimal("100"), "NONEXISTENT", "NONEXISTENT", sample_table)
    assert str(exc_info.value) == "Выберите валюту из списка."


# =============================================================================
# Currency Options Sorting Tests
# =============================================================================


def test_currency_options_order_with_sample(sample_table):
    options = currency_options(sample_table)
    codes = [code for code, _ in options]

    assert codes[0] == "MDL"
    assert codes[1] == "EUR"
    assert codes[2] == "USD"
    assert options[0] == ("MDL", "MDL — Молдавский лей")
    assert options[1] == ("EUR", "EUR — Евро")
    assert options[2] == ("USD", "USD — Доллар США")

    # Remaining codes must be strictly sorted alphabetically
    remaining_codes = codes[3:]
    assert remaining_codes == sorted(remaining_codes)
    assert len(options) == 41


def test_currency_options_missing_eur_or_usd():
    table = RateTable(
        rates_date=date(2026, 11, 18),
        requested_date=date(2026, 11, 18),
        source="Test",
        fetched_at=date(2026, 11, 18),
        rates={
            "GBP": CurrencyRate("GBP", "Фунт", 1, Decimal("24.0")),
            "CAD": CurrencyRate("CAD", "Доллар Канады", 1, Decimal("13.0")),
        },
    )
    options = currency_options(table)
    codes = [code for code, _ in options]
    assert codes == ["MDL", "CAD", "GBP"]


# =============================================================================
# FR-007 Round-Trip Tolerance & SC-002 Performance
# =============================================================================


def test_fr007_round_trip_tolerance_every_pair(sample_table):
    """Verify FR-007: |back - amount| <= 0.01 + 0.005 * price(target) / price(source)."""
    all_codes = sample_table.codes
    amount = Decimal("100.00")

    for c1, c2 in itertools.permutations(all_codes, 2):
        r1 = convert(amount, c1, c2, sample_table)
        r2 = convert(r1.converted, c2, c1, sample_table)
        back = r2.converted

        price_source = sample_table.get(c1).per_unit
        price_target = sample_table.get(c2).per_unit
        tolerance = Decimal("0.01") + Decimal("0.005") * (price_target / price_source)

        diff = abs(back - amount)
        assert diff <= tolerance, (
            f"FR-007 failed for pair {c1} -> {c2} -> {c1}: "
            f"amount={amount}, target_converted={r1.converted}, back={back}, "
            f"diff={diff}, tolerance={tolerance}"
        )


def test_sc002_conversion_performance_every_pair(sample_table):
    """Verify SC-002 proxy: converting every currency pair takes less than 0.5 s total."""
    all_codes = sample_table.codes
    amount = Decimal("100.00")
    pairs = list(itertools.permutations(all_codes, 2))
    assert len(pairs) == 41 * 40  # 1640 pairs

    start_time = time.perf_counter()
    for c1, c2 in pairs:
        convert(amount, c1, c2, sample_table)
    elapsed = time.perf_counter() - start_time

    assert elapsed < 0.5, f"Converting all 1640 pairs took {elapsed:.4f} s, exceeding 0.5 s limit"
