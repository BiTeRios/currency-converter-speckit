"""Client and parser for official National Bank of Moldova (BNM) exchange rates."""

import http.client
import os
import re
import socket
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from currency_converter import SOURCE_NAME
from currency_converter.errors import InvalidResponseError, SourceUnavailableError
from currency_converter.models import CurrencyRate, RateTable

DEFAULT_BASE_URL = "https://www.bnm.md/ru/official_exchange_rates"
SOURCE_URL_ENV = "CURRENCY_CONVERTER_SOURCE_URL"
TIMEOUT_SECONDS = 10
USER_AGENT = "CurrencyConverter/1.0 (educational project)"


def build_url(day: date, base_url: str | None = None) -> str:
    """Build the BNM exchange rates XML URL for the specified date."""
    if base_url is None:
        env_url = os.environ.get(SOURCE_URL_ENV)
        if env_url and env_url.strip():
            base_url = env_url.strip()
        else:
            base_url = DEFAULT_BASE_URL
    date_str = day.strftime("%d.%m.%Y")
    return f"{base_url}?get_xml=1&date={date_str}"


def fetch_xml(day: date, timeout: float = TIMEOUT_SECONDS) -> bytes | None:
    """Fetch raw XML rates for the given date from BNM.

    Returns bytes on HTTP 200 with non-empty body;
    Returns None on HTTP 404 or empty/whitespace body;
    Raises SourceUnavailableError on other HTTP errors, timeouts, or network failures.
    """
    url = build_url(day)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status == 404:
                return None
            if status != 200:
                raise SourceUnavailableError(f"HTTP {status}")
            body = response.read()
            if not body or not body.strip():
                return None
            return body
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise SourceUnavailableError(str(e)) from e
    except (
        urllib.error.URLError,
        TimeoutError,
        socket.timeout,
        ConnectionError,
        OSError,
        http.client.HTTPException,
    ) as e:
        raise SourceUnavailableError(str(e)) from e


def parse_rates(
    xml_bytes: bytes,
    requested_date: date,
    fetched_at: datetime | None = None,
) -> RateTable:
    """Parse BNM XML response into a RateTable.

    Follows parsing rules from contracts/bnm-source.md:
    1. Invalid XML -> InvalidResponseError
    2. Root != 'ValCurs' -> InvalidResponseError
    3. ValCurs/@Date parsed as DD.MM.YYYY, falls back to requested_date
    4. Valute items: CharCode ^[A-Z]{3}$, != MDL, Nominal >= 1, Value > 0
    5. First occurrence of CharCode wins
    6. Empty rates -> RateTable with empty rates dict
    """
    if not isinstance(xml_bytes, (bytes, bytearray)):
        raise InvalidResponseError("Ожидались байты XML")

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise InvalidResponseError(str(e)) from e

    if root.tag != "ValCurs":
        raise InvalidResponseError(f"Ожидался корневой элемент 'ValCurs', получен '{root.tag}'")

    date_attr = root.get("Date")
    rates_date: date
    if date_attr:
        try:
            rates_date = datetime.strptime(date_attr.strip(), "%d.%m.%Y").date()
        except ValueError:
            rates_date = requested_date
    else:
        rates_date = requested_date

    if fetched_at is None:
        fetched_at = datetime.now()

    rates: dict[str, CurrencyRate] = {}
    for valute in root.findall("Valute"):
        char_code_el = valute.find("CharCode")
        if char_code_el is None or not char_code_el.text:
            continue
        code = char_code_el.text.strip().upper()
        if not re.match(r"^[A-Z]{3}$", code) or code == "MDL":
            continue

        if code in rates:
            # First occurrence wins
            continue

        nominal_el = valute.find("Nominal")
        if nominal_el is None or not nominal_el.text:
            continue
        try:
            nominal = int(nominal_el.text.strip())
            if nominal < 1:
                continue
        except ValueError:
            continue

        value_el = valute.find("Value")
        if value_el is None or not value_el.text:
            continue
        try:
            val_str = value_el.text.strip().replace(",", ".")
            value = Decimal(val_str)
            if value <= 0:
                continue
        except (InvalidOperation, ValueError):
            continue

        name_el = valute.find("Name")
        name = name_el.text.strip() if (name_el is not None and name_el.text) else ""

        rates[code] = CurrencyRate(
            code=code,
            name=name,
            nominal=nominal,
            value=value,
        )

    return RateTable(
        rates_date=rates_date,
        requested_date=requested_date,
        source=SOURCE_NAME,
        fetched_at=fetched_at,
        rates=rates,
    )


__all__ = [
    "DEFAULT_BASE_URL",
    "SOURCE_URL_ENV",
    "TIMEOUT_SECONDS",
    "USER_AGENT",
    "build_url",
    "fetch_xml",
    "parse_rates",
]
