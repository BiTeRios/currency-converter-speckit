"""Tests for RateCache persistence, error handling, atomic write and path resolution."""

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from currency_converter import SOURCE_NAME
from currency_converter.cache import (
    CACHE_FILE_NAME,
    CACHE_HOME_ENV,
    RateCache,
    default_cache_path,
)
from currency_converter.models import CurrencyRate, RateTable


@pytest.fixture
def sample_table_for_cache() -> RateTable:
    return RateTable(
        rates_date=date(2026, 11, 18),
        requested_date=date(2026, 11, 20),
        source=SOURCE_NAME,
        fetched_at=datetime(2026, 11, 18, 14, 3, 12),
        rates={
            "EUR": CurrencyRate("EUR", "Евро", 1, Decimal("20.1538")),
            "USD": CurrencyRate("USD", "Доллар США", 1, Decimal("18.3383")),
            "JPY": CurrencyRate("JPY", "Японская Йена", 100, Decimal("11.5165")),
        },
    )


# =============================================================================
# Save / Load Round Trip Tests
# =============================================================================


def test_cache_save_load_round_trip(tmp_path, sample_table_for_cache):
    cache_path = tmp_path / "sub" / "rates_cache.json"
    cache = RateCache(cache_path)

    # Save table to disk
    cache.save(sample_table_for_cache)

    # Check raw JSON on disk
    raw_data = json.loads(cache_path.read_text(encoding="utf-8"))
    assert raw_data["version"] == 1
    assert raw_data["source"] == SOURCE_NAME
    assert raw_data["requested_date"] == "2026-11-20"
    assert raw_data["rates_date"] == "2026-11-18"
    assert raw_data["fetched_at"] == "2026-11-18T14:03:12"
    assert len(raw_data["rates"]) == 3

    # Check decimals stored as strings
    eur_item = next(item for item in raw_data["rates"] if item["code"] == "EUR")
    assert eur_item == {
        "code": "EUR",
        "name": "Евро",
        "nominal": 1,
        "value": "20.1538",
    }

    # Load back and verify complete model
    loaded = cache.load()
    assert loaded is not None
    assert cache.last_error is None
    assert loaded.rates_date == sample_table_for_cache.rates_date
    assert loaded.requested_date == sample_table_for_cache.requested_date
    assert loaded.source == sample_table_for_cache.source
    assert loaded.fetched_at == sample_table_for_cache.fetched_at
    assert loaded.rates == sample_table_for_cache.rates

    # Exact decimal preservation
    assert isinstance(loaded.rates["EUR"].value, Decimal)
    assert loaded.rates["EUR"].value == Decimal("20.1538")
    assert loaded.rates["JPY"].nominal == 100
    assert loaded.rates["JPY"].value == Decimal("11.5165")


# =============================================================================
# Missing and Corrupt Cache File Tests
# =============================================================================


def test_cache_load_missing_file(tmp_path):
    cache = RateCache(tmp_path / "nonexistent.json")
    loaded = cache.load()
    assert loaded is None
    assert cache.last_error is None


def test_cache_load_corrupt_json(tmp_path):
    cache_path = tmp_path / "corrupt.json"
    cache_path.write_text("NOT A JSON {{{", encoding="utf-8")
    cache = RateCache(cache_path)

    loaded = cache.load()
    assert loaded is None
    assert cache.last_error is not None
    assert "Сохранённый курс не удалось прочитать" in cache.last_error
    assert "он будет заменён при следующей загрузке." in cache.last_error


def test_cache_load_json_not_an_object(tmp_path):
    cache_path = tmp_path / "array.json"
    cache_path.write_text("[1, 2, 3]", encoding="utf-8")
    cache = RateCache(cache_path)

    loaded = cache.load()
    assert loaded is None
    assert cache.last_error is not None


def test_cache_load_unsupported_version(tmp_path):
    cache_path = tmp_path / "version2.json"
    data = {
        "version": 2,
        "source": SOURCE_NAME,
        "requested_date": "2026-11-18",
        "rates_date": "2026-11-18",
        "fetched_at": "2026-11-18T10:00:00",
        "rates": [],
    }
    cache_path.write_text(json.dumps(data), encoding="utf-8")
    cache = RateCache(cache_path)

    loaded = cache.load()
    assert loaded is None
    assert cache.last_error is not None
    assert "unsupported version: 2" in cache.last_error


@pytest.mark.parametrize(
    "missing_key",
    ["source", "requested_date", "rates_date", "fetched_at", "rates"],
)
def test_cache_load_missing_required_keys(tmp_path, missing_key):
    data = {
        "version": 1,
        "source": SOURCE_NAME,
        "requested_date": "2026-11-18",
        "rates_date": "2026-11-18",
        "fetched_at": "2026-11-18T10:00:00",
        "rates": [],
    }
    del data[missing_key]
    cache_path = tmp_path / f"missing_{missing_key}.json"
    cache_path.write_text(json.dumps(data), encoding="utf-8")
    cache = RateCache(cache_path)

    loaded = cache.load()
    assert loaded is None
    assert cache.last_error is not None
    assert f"missing key: '{missing_key}'" in cache.last_error


@pytest.mark.parametrize(
    "invalid_rate",
    [
        {"code": "MDL", "name": "Лей", "nominal": 1, "value": "1.0"},  # MDL forbidden
        {"code": "EU", "name": "Евро", "nominal": 1, "value": "20.0"},  # Code < 3 chars
        {"code": "EURO", "name": "Евро", "nominal": 1, "value": "20.0"},  # Code > 3 chars
        {"code": "usd", "name": "Доллар", "nominal": 1, "value": "18.0"},  # Lowercase code
        {"code": "USD", "name": "Доллар", "nominal": 0, "value": "18.0"},  # Nominal 0
        {"code": "USD", "name": "Доллар", "nominal": -1, "value": "18.0"},  # Nominal negative
        {"code": "USD", "name": "Доллар", "nominal": 1, "value": "-18.0"},  # Negative value
        {"code": "USD", "name": "Доллар", "nominal": 1, "value": "0.0"},  # Zero value
        {"code": "USD", "name": "Доллар", "nominal": 1, "value": 18.0},  # Value float, not string
        {"name": "Доллар", "nominal": 1, "value": "18.0"},  # Missing code
        {"code": "USD", "name": "Доллар", "value": "18.0"},  # Missing nominal
    ],
)
def test_cache_load_invalid_rate_items(tmp_path, invalid_rate):
    data = {
        "version": 1,
        "source": SOURCE_NAME,
        "requested_date": "2026-11-18",
        "rates_date": "2026-11-18",
        "fetched_at": "2026-11-18T10:00:00",
        "rates": [invalid_rate],
    }
    cache_path = tmp_path / "bad_rates.json"
    cache_path.write_text(json.dumps(data), encoding="utf-8")
    cache = RateCache(cache_path)

    loaded = cache.load()
    assert loaded is None
    assert cache.last_error is not None


# =============================================================================
# Atomic Write and Temporary File Cleanup Tests
# =============================================================================


def test_cache_atomic_write_no_temp_files_left(tmp_path, sample_table_for_cache):
    cache_dir = tmp_path / "atomic_dir"
    cache_file = cache_dir / CACHE_FILE_NAME
    cache = RateCache(cache_file)

    cache.save(sample_table_for_cache)

    files_in_dir = list(cache_dir.iterdir())
    assert files_in_dir == [cache_file]
    # No temporary files (.tmp) remain
    assert not any(f.name.endswith(".tmp") for f in files_in_dir)


def test_cache_save_failure_cleans_up_temp_file(tmp_path, sample_table_for_cache, monkeypatch):
    cache_dir = tmp_path / "fail_dir"
    cache_file = cache_dir / CACHE_FILE_NAME
    cache = RateCache(cache_file)

    def failing_dump(*args, **kwargs):
        raise RuntimeError("Disk write failed midway")

    monkeypatch.setattr(json, "dump", failing_dump)

    with pytest.raises(RuntimeError):
        cache.save(sample_table_for_cache)

    # Ensure no leftover temp files
    if cache_dir.exists():
        files_in_dir = list(cache_dir.iterdir())
        assert not any(f.name.endswith(".tmp") for f in files_in_dir)


# =============================================================================
# Path Resolution Tests
# =============================================================================


def test_default_cache_path_honours_custom_home(tmp_path, monkeypatch):
    custom_dir = tmp_path / "custom_home_path"
    monkeypatch.setenv(CACHE_HOME_ENV, str(custom_dir))

    resolved = default_cache_path()
    assert resolved == custom_dir / CACHE_FILE_NAME


def test_default_cache_path_ignores_empty_or_whitespace_env(tmp_path, monkeypatch):
    fake_appdata = tmp_path / "fake_appdata"
    monkeypatch.setenv("APPDATA", str(fake_appdata))

    monkeypatch.setenv(CACHE_HOME_ENV, "")
    resolved_empty = default_cache_path()
    assert resolved_empty == fake_appdata / "CurrencyConverter" / CACHE_FILE_NAME

    monkeypatch.setenv(CACHE_HOME_ENV, "   ")
    resolved_spaces = default_cache_path()
    assert resolved_spaces == fake_appdata / "CurrencyConverter" / CACHE_FILE_NAME
