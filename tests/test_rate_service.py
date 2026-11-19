"""Tests for RateService lookback fallback, error propagation, caching and saved rates."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from currency_converter import SOURCE_NAME
from currency_converter.cache import RateCache
from currency_converter.errors import (
    InvalidResponseError,
    NoRatesError,
    SourceUnavailableError,
)
from currency_converter.models import CurrencyRate, LoadStatus, RateTable
from currency_converter.rate_service import MAX_LOOKBACK_DAYS, RateService


def make_rates_xml(day: date, code: str = "EUR", value: str = "20.1538") -> bytes:
    """Helper to generate minimal valid BNM rates XML."""
    date_str = day.strftime("%d.%m.%Y")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <ValCurs Date="{date_str}" name="Official exchange rates">
      <Valute ID="47">
        <CharCode>{code}</CharCode>
        <Nominal>1</Nominal>
        <Name>Евро</Name>
        <Value>{value}</Value>
      </Valute>
    </ValCurs>
    """.encode("utf-8")


def make_empty_xml(day: date) -> bytes:
    """Helper to generate empty ValCurs XML."""
    date_str = day.strftime("%d.%m.%Y")
    return f'<ValCurs Date="{date_str}"/>'.encode("utf-8")


def make_fetcher(responses: dict[date, bytes | None | Exception]):
    """Helper to create a mock fetcher tracking called dates."""
    calls: list[date] = []

    def fetch(day: date) -> bytes | None:
        calls.append(day)
        val = responses.get(day)
        if isinstance(val, Exception):
            raise val
        return val

    return fetch, calls


@pytest.fixture(autouse=True)
def isolate_home_env(monkeypatch, tmp_path):
    """Ensure tests never write to user profile even if default cache is instantiated."""
    monkeypatch.setenv("CURRENCY_CONVERTER_HOME", str(tmp_path / "env_home"))


# =============================================================================
# Live Load and Fallback Tests
# =============================================================================


def test_rate_service_live_success(tmp_path):
    req_date = date(2026, 11, 18)
    fetch, calls = make_fetcher({req_date: make_rates_xml(req_date)})
    cache = RateCache(tmp_path / "cache.json")
    fixed_now = datetime(2026, 11, 18, 12, 0)
    service = RateService(fetch=fetch, cache=cache, now=lambda: fixed_now)

    result = service.load(req_date)

    assert result.status == LoadStatus.LIVE
    assert result.warning is None
    assert result.table.requested_date == req_date
    assert result.table.rates_date == req_date
    assert result.table.source == SOURCE_NAME
    assert result.table.fetched_at == fixed_now
    assert "EUR" in result.table.rates
    assert calls == [req_date]

    # Verify rates saved to cache
    cached_table = cache.load()
    assert cached_table is not None
    assert cached_table.rates_date == req_date
    assert cached_table.requested_date == req_date


def test_rate_service_fallback_to_earlier_date(tmp_path):
    req_date = date(2026, 11, 18)
    day_minus_1 = req_date - timedelta(days=1)
    day_minus_2 = req_date - timedelta(days=2)

    responses = {
        req_date: None,
        day_minus_1: None,
        day_minus_2: make_rates_xml(day_minus_2),
    }
    fetch, calls = make_fetcher(responses)
    cache = RateCache(tmp_path / "cache.json")
    service = RateService(fetch=fetch, cache=cache)

    result = service.load(req_date)

    assert result.status == LoadStatus.EARLIER_DATE
    assert result.warning is None
    assert result.table.requested_date == req_date
    assert result.table.rates_date == day_minus_2
    assert calls == [req_date, day_minus_1, day_minus_2]

    # Verify cached table stores user's requested date
    cached_table = cache.load()
    assert cached_table is not None
    assert cached_table.requested_date == req_date
    assert cached_table.rates_date == day_minus_2


def test_rate_service_empty_valcurs_triggers_fallback(tmp_path):
    req_date = date(2026, 11, 18)
    day_minus_1 = req_date - timedelta(days=1)

    responses = {
        req_date: make_empty_xml(req_date),
        day_minus_1: make_rates_xml(day_minus_1),
    }
    fetch, calls = make_fetcher(responses)
    cache = RateCache(tmp_path / "cache.json")
    service = RateService(fetch=fetch, cache=cache)

    result = service.load(req_date)

    assert result.status == LoadStatus.EARLIER_DATE
    assert result.table.requested_date == req_date
    assert result.table.rates_date == day_minus_1
    assert calls == [req_date, day_minus_1]


# =============================================================================
# Lookback Limit and NoRatesError Tests
# =============================================================================


def test_rate_service_11_misses_raises_no_rates_error(tmp_path):
    req_date = date(2026, 11, 18)
    fetch, calls = make_fetcher({})  # All dates return None
    cache = RateCache(tmp_path / "cache.json")
    service = RateService(fetch=fetch, cache=cache)

    with pytest.raises(NoRatesError) as exc_info:
        service.load(req_date)

    assert len(calls) == MAX_LOOKBACK_DAYS + 1  # Exactly 11 fetch calls
    earliest_expected = req_date - timedelta(days=MAX_LOOKBACK_DAYS)
    assert exc_info.value.requested_date == req_date
    assert exc_info.value.earliest_date == earliest_expected
    assert str(exc_info.value) == (
        f"Нет опубликованного курса за период с {earliest_expected.strftime('%d.%m.%Y')} "
        f"по {req_date.strftime('%d.%m.%Y')}."
    )


def test_rate_service_11_empty_xml_misses_raises_no_rates_error(tmp_path):
    req_date = date(2026, 11, 18)
    responses = {
        req_date - timedelta(days=offset): make_empty_xml(req_date - timedelta(days=offset))
        for offset in range(MAX_LOOKBACK_DAYS + 1)
    }
    fetch, calls = make_fetcher(responses)
    cache = RateCache(tmp_path / "cache.json")
    service = RateService(fetch=fetch, cache=cache)

    with pytest.raises(NoRatesError):
        service.load(req_date)

    assert len(calls) == 11


# =============================================================================
# Error Propagation Tests (No Fallback)
# =============================================================================


def test_rate_service_source_unavailable_propagates_immediately(tmp_path):
    req_date = date(2026, 11, 18)
    error = SourceUnavailableError("Connection refused")
    fetch, calls = make_fetcher({req_date: error})
    cache = RateCache(tmp_path / "cache.json")
    service = RateService(fetch=fetch, cache=cache)

    with pytest.raises(SourceUnavailableError) as exc_info:
        service.load(req_date)

    assert "Connection refused" in str(exc_info.value)
    assert calls == [req_date]  # Immediate propagation, no fallback lookback


def test_rate_service_invalid_response_propagates_immediately(tmp_path):
    req_date = date(2026, 11, 18)
    # Wrong root tag causes parse_rates to raise InvalidResponseError
    fetch, calls = make_fetcher({req_date: b'<WrongRoot Tag="18.11.2026"/>'})
    cache = RateCache(tmp_path / "cache.json")
    service = RateService(fetch=fetch, cache=cache)

    with pytest.raises(InvalidResponseError):
        service.load(req_date)

    assert calls == [req_date]  # Immediate propagation, no fallback lookback


# =============================================================================
# Cache Error Handling & load_saved Tests
# =============================================================================


class BrokenSaveCache(RateCache):
    """Cache stub whose save method raises OSError."""

    def save(self, table: RateTable) -> None:
        raise OSError("Permission denied / disk full")


def test_rate_service_cache_save_oserror_returns_warning(tmp_path):
    req_date = date(2026, 11, 18)
    fetch, _ = make_fetcher({req_date: make_rates_xml(req_date)})
    broken_cache = BrokenSaveCache(tmp_path / "broken.json")
    service = RateService(fetch=fetch, cache=broken_cache)

    result = service.load(req_date)

    assert result.status == LoadStatus.LIVE
    assert result.table.requested_date == req_date
    assert result.warning == "Курс получен, но не сохранён на диск: Permission denied / disk full"


def test_rate_service_load_saved_present(tmp_path):
    cache = RateCache(tmp_path / "cache.json")
    table = RateTable(
        rates_date=date(2026, 11, 18),
        requested_date=date(2026, 11, 18),
        source=SOURCE_NAME,
        fetched_at=datetime(2026, 11, 18, 10, 0),
        rates={"EUR": CurrencyRate("EUR", "Евро", 1, Decimal("20.1538"))},
    )
    cache.save(table)

    service = RateService(fetch=lambda d: None, cache=cache)
    result = service.load_saved()

    assert result is not None
    assert result.status == LoadStatus.CACHED
    assert result.warning is None
    assert result.table.rates_date == table.rates_date
    assert result.table.requested_date == table.requested_date
    assert result.table.rates["EUR"].value == Decimal("20.1538")


def test_rate_service_load_saved_absent(tmp_path):
    cache = RateCache(tmp_path / "nonexistent.json")
    service = RateService(fetch=lambda d: None, cache=cache)

    result = service.load_saved()
    assert result is None
