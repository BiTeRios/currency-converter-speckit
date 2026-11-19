"""Tests for BNM rate source client, URL builder and XML parser."""

import http.client
import socket
import urllib.error
import urllib.request
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from currency_converter import SOURCE_NAME
from currency_converter.bnm_source import (
    DEFAULT_BASE_URL,
    SOURCE_URL_ENV,
    TIMEOUT_SECONDS,
    USER_AGENT,
    build_url,
    fetch_xml,
    parse_rates,
)
from currency_converter.errors import InvalidResponseError, SourceUnavailableError
from currency_converter.models import MDL_RATE

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class FakeResponse:
    """Mock HTTP response usable as a context manager."""

    def __init__(self, body: bytes = b"", status: int = 200) -> None:
        self.body = body
        self.status = status

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


# =============================================================================
# URL Builder Tests
# =============================================================================


def test_build_url_default():
    day = date(2026, 11, 18)
    expected = f"{DEFAULT_BASE_URL}?get_xml=1&date=18.11.2026"
    assert build_url(day) == expected


def test_build_url_zero_padding():
    day = date(2026, 1, 5)
    expected = f"{DEFAULT_BASE_URL}?get_xml=1&date=05.01.2026"
    assert build_url(day) == expected


def test_build_url_explicit_base():
    day = date(2026, 11, 18)
    custom_base = "http://localhost:8080/rates"
    assert build_url(day, custom_base) == f"{custom_base}?get_xml=1&date=18.11.2026"


def test_build_url_env_override(monkeypatch):
    monkeypatch.setenv(SOURCE_URL_ENV, "http://env-override.example.com/xml")
    day = date(2026, 11, 18)
    assert build_url(day) == "http://env-override.example.com/xml?get_xml=1&date=18.11.2026"


def test_build_url_empty_env_ignored(monkeypatch):
    monkeypatch.setenv(SOURCE_URL_ENV, "")
    day = date(2026, 11, 18)
    assert build_url(day) == f"{DEFAULT_BASE_URL}?get_xml=1&date=18.11.2026"

    monkeypatch.setenv(SOURCE_URL_ENV, "   ")
    assert build_url(day) == f"{DEFAULT_BASE_URL}?get_xml=1&date=18.11.2026"


# =============================================================================
# XML Parsing Tests
# =============================================================================


def test_parse_rates_real_sample():
    sample_file = FIXTURES_DIR / "bnm_2026-11-18.xml"
    xml_bytes = sample_file.read_bytes()
    req_date = date(2026, 11, 18)
    fixed_now = datetime(2026, 11, 18, 14, 30, 0)

    table = parse_rates(xml_bytes, requested_date=req_date, fetched_at=fixed_now)

    assert table.source == SOURCE_NAME
    assert table.rates_date == date(2026, 11, 18)
    assert table.requested_date == req_date
    assert table.fetched_at == fixed_now
    assert len(table.rates) == 40
    assert "MDL" not in table.rates

    # Specific currency checks from spec
    eur = table.rates["EUR"]
    assert eur.code == "EUR"
    assert eur.name == "Евро"
    assert eur.nominal == 1
    assert eur.value == Decimal("20.1538")
    assert eur.per_unit == Decimal("20.1538")

    usd = table.rates["USD"]
    assert usd.code == "USD"
    assert usd.name == "Доллар США"
    assert usd.nominal == 1
    assert usd.value == Decimal("18.3383")
    assert usd.per_unit == Decimal("18.3383")

    jpy = table.rates["JPY"]
    assert jpy.code == "JPY"
    assert jpy.name == "Японская Йена"
    assert jpy.nominal == 100
    assert jpy.value == Decimal("11.5165")
    assert jpy.per_unit == Decimal("0.115165")

    # Table methods
    assert table.get("EUR") == eur
    assert table.get("MDL") == MDL_RATE
    with pytest.raises(KeyError):
        table.get("UNKNOWN")

    codes = table.codes
    assert codes[0] == "MDL"
    assert len(codes) == 41


def test_parse_rates_default_fetched_at():
    xml = b'<ValCurs Date="18.11.2026"/>'
    before = datetime.now()
    table = parse_rates(xml, requested_date=date(2026, 11, 18))
    after = datetime.now()
    assert before <= table.fetched_at <= after


def test_parse_rates_skipped_invalid_valutes():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ValCurs Date="18.11.2026">
      <!-- Valid EUR -->
      <Valute ID="47">
        <CharCode>EUR</CharCode>
        <Nominal>1</Nominal>
        <Name>Евро</Name>
        <Value>20.1538</Value>
      </Valute>
      <!-- Bad CharCode (too short) -->
      <Valute ID="1"><CharCode>EU</CharCode><Nominal>1</Nominal><Value>10.0</Value></Valute>
      <!-- Bad CharCode (too long) -->
      <Valute ID="2"><CharCode>EURO</CharCode><Nominal>1</Nominal><Value>10.0</Value></Valute>
      <!-- Bad CharCode (digits) -->
      <Valute ID="3"><CharCode>123</CharCode><Nominal>1</Nominal><Value>10.0</Value></Valute>
      <!-- Bad CharCode (special char) -->
      <Valute ID="4"><CharCode>E#R</CharCode><Nominal>1</Nominal><Value>10.0</Value></Valute>
      <!-- CharCode MDL is skipped -->
      <Valute ID="5"><CharCode>MDL</CharCode><Nominal>1</Nominal><Value>1.0</Value></Valute>
      <!-- Nominal 0 -->
      <Valute ID="6"><CharCode>GBP</CharCode><Nominal>0</Nominal><Value>24.0</Value></Valute>
      <!-- Nominal negative -->
      <Valute ID="7"><CharCode>CHF</CharCode><Nominal>-1</Nominal><Value>21.0</Value></Valute>
      <!-- Nominal non-integer -->
      <Valute ID="8"><CharCode>CAD</CharCode><Nominal>abc</Nominal><Value>12.0</Value></Valute>
      <!-- Value zero -->
      <Valute ID="9"><CharCode>AUD</CharCode><Nominal>1</Nominal><Value>0</Value></Valute>
      <!-- Value negative -->
      <Valute ID="10"><CharCode>RON</CharCode><Nominal>1</Nominal><Value>-3.5</Value></Valute>
      <!-- Value non-numeric -->
      <Valute ID="11"><CharCode>UAH</CharCode><Nominal>1</Nominal><Value>invalid</Value></Valute>
      <!-- Missing CharCode -->
      <Valute ID="12"><Nominal>1</Nominal><Value>10.0</Value></Valute>
      <!-- Empty CharCode -->
      <Valute ID="13"><CharCode>   </CharCode><Nominal>1</Nominal><Value>10.0</Value></Valute>
      <!-- Missing Nominal -->
      <Valute ID="14"><CharCode>JPY</CharCode><Value>11.0</Value></Valute>
      <!-- Missing Value -->
      <Valute ID="15"><CharCode>PLN</CharCode><Nominal>1</Nominal></Valute>
    </ValCurs>
    """.encode("utf-8")
    table = parse_rates(xml, requested_date=date(2026, 11, 18))
    assert list(table.rates.keys()) == ["EUR"]
    assert table.rates["EUR"].value == Decimal("20.1538")


def test_parse_rates_comma_decimal_and_missing_name():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ValCurs Date="18.11.2026">
      <Valute ID="47">
        <CharCode>eur</CharCode>
        <Nominal>1</Nominal>
        <Value>20,1538</Value>
      </Valute>
    </ValCurs>
    """.encode("utf-8")
    table = parse_rates(xml, requested_date=date(2026, 11, 18))
    assert "EUR" in table.rates
    rate = table.rates["EUR"]
    assert rate.value == Decimal("20.1538")
    assert rate.name == ""


def test_parse_rates_duplicates_first_wins():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ValCurs Date="18.11.2026">
      <Valute ID="1">
        <CharCode>USD</CharCode>
        <Nominal>1</Nominal>
        <Value>18.3383</Value>
        <Name>Первый доллар</Name>
      </Valute>
      <Valute ID="2">
        <CharCode>USD</CharCode>
        <Nominal>1</Nominal>
        <Value>99.9999</Value>
        <Name>Второй доллар</Name>
      </Valute>
    </ValCurs>
    """.encode("utf-8")
    table = parse_rates(xml, requested_date=date(2026, 11, 18))
    assert len(table.rates) == 1
    assert table.rates["USD"].value == Decimal("18.3383")
    assert table.rates["USD"].name == "Первый доллар"


def test_parse_rates_missing_or_invalid_date_attribute():
    requested = date(2026, 11, 18)

    # Missing Date attribute
    xml_no_date = b'<ValCurs name="Test"><Valute ID="1"><CharCode>USD</CharCode><Nominal>1</Nominal><Value>18.0</Value></Valute></ValCurs>'
    table1 = parse_rates(xml_no_date, requested_date=requested)
    assert table1.rates_date == requested

    # Unparsable Date attribute
    xml_bad_date = b'<ValCurs Date="bad-date"><Valute ID="1"><CharCode>USD</CharCode><Nominal>1</Nominal><Value>18.0</Value></Valute></ValCurs>'
    table2 = parse_rates(xml_bad_date, requested_date=requested)
    assert table2.rates_date == requested

    # ISO date format instead of DD.MM.YYYY
    xml_iso_date = b'<ValCurs Date="2026-11-18"><Valute ID="1"><CharCode>USD</CharCode><Nominal>1</Nominal><Value>18.0</Value></Valute></ValCurs>'
    table3 = parse_rates(xml_iso_date, requested_date=requested)
    assert table3.rates_date == requested


def test_parse_rates_empty_valcurs():
    empty_file = FIXTURES_DIR / "bnm_empty.xml"
    xml_bytes = empty_file.read_bytes()
    table = parse_rates(xml_bytes, requested_date=date(2026, 11, 18))
    assert table.rates == {}
    assert table.rates_date == date(2026, 11, 18)


def test_parse_rates_malformed_xml():
    malformed_file = FIXTURES_DIR / "bnm_malformed.xml"
    xml_bytes = malformed_file.read_bytes()
    with pytest.raises(InvalidResponseError):
        parse_rates(xml_bytes, requested_date=date(2026, 11, 18))

    with pytest.raises(InvalidResponseError):
        parse_rates(b"not valid xml at all", requested_date=date(2026, 11, 18))

    with pytest.raises(InvalidResponseError):
        parse_rates(b"", requested_date=date(2026, 11, 18))

    with pytest.raises(InvalidResponseError):
        parse_rates("string instead of bytes", requested_date=date(2026, 11, 18))  # type: ignore


def test_parse_rates_wrong_root_element():
    xml = b'<ExchangeRates Date="18.11.2026"><Valute><CharCode>USD</CharCode><Nominal>1</Nominal><Value>18.0</Value></Valute></ExchangeRates>'
    with pytest.raises(InvalidResponseError) as exc_info:
        parse_rates(xml, requested_date=date(2026, 11, 18))
    assert "ValCurs" in str(exc_info.value)


# =============================================================================
# HTTP Fetch XML Tests
# =============================================================================


def test_fetch_xml_success(monkeypatch):
    expected_body = b'<ValCurs Date="18.11.2026"/>'

    def fake_urlopen(request, timeout=TIMEOUT_SECONDS):
        assert request.get_header("User-agent") == USER_AGENT
        assert "date=18.11.2026" in request.full_url
        assert timeout == TIMEOUT_SECONDS
        return FakeResponse(expected_body, status=200)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = fetch_xml(date(2026, 11, 18))
    assert result == expected_body


def test_fetch_xml_200_empty_body(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=10: FakeResponse(b"", status=200)
    )
    assert fetch_xml(date(2026, 11, 18)) is None

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=10: FakeResponse(b"   \n  \t ", status=200)
    )
    assert fetch_xml(date(2026, 11, 18)) is None


def test_fetch_xml_http_404_error(monkeypatch):
    def fake_urlopen(req, timeout=10):
        raise urllib.error.HTTPError(
            url="https://www.bnm.md/ru/official_exchange_rates",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert fetch_xml(date(2026, 11, 18)) is None


def test_fetch_xml_404_status_response(monkeypatch):
    # Контракт: None даёт только HTTPError с кодом 404; любой не-200 статус
    # без исключения — SourceUnavailableError.
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=10: FakeResponse(b"", status=404)
    )
    with pytest.raises(SourceUnavailableError):
        fetch_xml(date(2026, 11, 18))


def test_fetch_xml_invalid_base_url_is_source_unavailable(monkeypatch):
    # Ревью, п. 5: неверный адрес источника не должен давать ValueError.
    monkeypatch.setenv("CURRENCY_CONVERTER_SOURCE_URL", "notaurl")
    with pytest.raises(SourceUnavailableError):
        fetch_xml(date(2026, 11, 18))


@pytest.mark.parametrize("value", ["Infinity", "inf", "NaN", "1E+30", "1e5", "1_8.5", "2000000"])
def test_parse_rates_rejects_non_plain_or_absurd_values(value):
    # Ревью, п. 4: принимаются только обычные десятичные числа в разумных пределах.
    xml = (
        '<ValCurs Date="18.11.2026">'
        "<Valute><CharCode>USD</CharCode><Nominal>1</Nominal><Name>Доллар</Name><Value>18.3383</Value></Valute>"
        f"<Valute><CharCode>EUR</CharCode><Nominal>1</Nominal><Name>Евро</Name><Value>{value}</Value></Valute>"
        "</ValCurs>"
    ).encode("utf-8")
    table = parse_rates(xml, date(2026, 11, 18))
    assert set(table.rates) == {"USD"}


@pytest.mark.parametrize("nominal", ["1_0", "+1", "1.0", " "])
def test_parse_rates_rejects_non_plain_nominal(nominal):
    xml = (
        '<ValCurs Date="18.11.2026">'
        f"<Valute><CharCode>JPY</CharCode><Nominal>{nominal}</Nominal><Name>Иена</Name><Value>11.5</Value></Valute>"
        "</ValCurs>"
    ).encode("utf-8")
    assert parse_rates(xml, date(2026, 11, 18)).rates == {}


def test_fetch_xml_http_500_error(monkeypatch):
    def fake_urlopen(req, timeout=10):
        raise urllib.error.HTTPError(
            url="https://www.bnm.md/ru/official_exchange_rates",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SourceUnavailableError):
        fetch_xml(date(2026, 11, 18))


def test_fetch_xml_non_200_status(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=10: FakeResponse(b"Service Unavailable", status=503)
    )
    with pytest.raises(SourceUnavailableError) as exc_info:
        fetch_xml(date(2026, 11, 18))
    assert "503" in str(exc_info.value)


def test_fetch_xml_url_error(monkeypatch):
    def fake_urlopen(req, timeout=10):
        raise urllib.error.URLError("DNS resolution failed")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SourceUnavailableError) as exc_info:
        fetch_xml(date(2026, 11, 18))
    assert "DNS resolution failed" in str(exc_info.value)


def test_fetch_xml_timeout_errors(monkeypatch):
    def fake_urlopen_timeout(req, timeout=10):
        raise TimeoutError("Connection timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen_timeout)
    with pytest.raises(SourceUnavailableError) as exc_info:
        fetch_xml(date(2026, 11, 18))
    assert "timed out" in str(exc_info.value)

    def fake_urlopen_socket_timeout(req, timeout=10):
        raise socket.timeout("Socket read timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen_socket_timeout)
    with pytest.raises(SourceUnavailableError) as exc_info:
        fetch_xml(date(2026, 11, 18))
    assert "timed out" in str(exc_info.value)


def test_fetch_xml_connection_and_http_exceptions(monkeypatch):
    def fake_urlopen_conn(req, timeout=10):
        raise ConnectionError("Connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen_conn)
    with pytest.raises(SourceUnavailableError):
        fetch_xml(date(2026, 11, 18))

    def fake_urlopen_http_exc(req, timeout=10):
        raise http.client.IncompleteRead(b"partial")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen_http_exc)
    with pytest.raises(SourceUnavailableError):
        fetch_xml(date(2026, 11, 18))
