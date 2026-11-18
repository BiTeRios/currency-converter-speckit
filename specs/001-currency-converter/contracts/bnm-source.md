# Contract: National Bank of Moldova official exchange rates (external source)

## Request

```text
GET {BASE_URL}?get_xml=1&date=DD.MM.YYYY
BASE_URL = os.environ.get("CURRENCY_CONVERTER_SOURCE_URL",
                          "https://www.bnm.md/en/official_exchange_rates")
Header: User-Agent: CurrencyConverter/1.0 (educational project)
Timeout: 10 seconds
```

`DD.MM.YYYY` is zero-padded (`05.01.2026`).

## Responses (verified 2026-11-18, see research.md R2)

| Situation | HTTP | Body | Client result |
|---|---|---|---|
| Working day, weekend, holiday, tomorrow after ~13:00 | 200 | XML below | `bytes` |
| No publication (future, before the archive) | 404 | empty | `None` |
| 200 with empty or whitespace-only body | 200 | empty | `None` |
| Any other HTTP status (5xx, 403, …) | ≠200/404 | any | `SourceUnavailableError` |
| DNS failure, refused connection, timeout, TLS error | — | — | `SourceUnavailableError` |

## XML format

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ValCurs Date="18.11.2026" name="Official exchange rate">
  <Valute ID="47">
    <NumCode>978</NumCode>
    <CharCode>EUR</CharCode>
    <Nominal>1</Nominal>
    <Name>Euro</Name>
    <Value>20.1538</Value>
  </Valute>
  <Valute ID="44">
    <NumCode>840</NumCode>
    <CharCode>USD</CharCode>
    <Nominal>1</Nominal>
    <Name>US Dollar</Name>
    <Value>18.3383</Value>
  </Valute>
  <!-- … 40 currencies in total; JPY has <Nominal>100</Nominal> -->
</ValCurs>
```

Full real response: [bnm-sample-2026-11-18.xml](./bnm-sample-2026-11-18.xml)
(40 currencies; EUR 20.1538, USD 18.3383, JPY 11.5165 per 100, XDR 24.6666).

## Parsing rules

1. Bytes that are not well-formed XML → `InvalidResponseError`.
2. Root element other than `ValCurs` → `InvalidResponseError`.
3. `ValCurs/@Date` parsed as `DD.MM.YYYY` → `rates_date`; missing or unparsable → the date that
   was requested from the source.
4. For each `Valute`: `CharCode` stripped and upper-cased must match `^[A-Z]{3}$` and must not be
   `MDL`; `Nominal` must be an integer ≥ 1; `Value` must be a decimal > 0 (a `,` decimal separator
   is accepted). Otherwise the element is skipped. `Name` may be missing (→ empty string).
5. Duplicate `CharCode` → the first occurrence wins.
6. A well-formed `ValCurs` with no valid `Valute` returns a `RateTable` with empty `rates`; the
   rate service treats it as "no rates for this date".
