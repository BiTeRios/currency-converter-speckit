# Data Model: Currency Converter with Official BNM Rates

All types live in `currency_converter/models.py` (immutable dataclasses) and
`currency_converter/errors.py`. Exact signatures: [contracts/core-api.md](./contracts/core-api.md).

## CurrencyRate

| Field | Type | Rules |
|---|---|---|
| `code` | `str` | ISO 4217, exactly 3 uppercase letters (`USD`) |
| `name` | `str` | Name as published by the source (`US Dollar`); may be empty |
| `nominal` | `int` | ≥ 1; number of units `value` refers to (JPY = 100) |
| `value` | `Decimal` | > 0; price of `nominal` units in MDL |

Derived: `per_unit = value / nominal` (MDL per 1 unit).
Constant `MDL_RATE = CurrencyRate("MDL", "Молдавский лей", 1, Decimal("1"))` — the base currency is
never taken from the source.

## RateTable

| Field | Type | Rules |
|---|---|---|
| `rates_date` | `date` | Date the rates belong to (`ValCurs/@Date`; if absent — the fetched date) |
| `requested_date` | `date` | Date the user asked for; differs from `rates_date` after a fallback |
| `source` | `str` | Always `SOURCE_NAME` = `"Национальный банк Молдовы, bnm.md"` |
| `fetched_at` | `datetime` | Local time of the successful download |
| `rates` | `dict[str, CurrencyRate]` | Keyed by code; **does not** contain MDL; may be empty only inside the parser |

Operations: `get(code)` returns `MDL_RATE` for `"MDL"`, the rate for known codes, raises `KeyError`
otherwise; `codes` returns `["MDL", *rates]`.

## LoadStatus (Enum)

| Value | Meaning | Shown as (FR-017) |
|---|---|---|
| `LIVE` | Downloaded now for the requested date | `курс на {rates_date}` |
| `EARLIER_DATE` | Downloaded now, but for an earlier date (FR-013) | `курс на {rates_date} (за {requested_date} курс не опубликован)` |
| `CACHED` | Taken from the saved file after the user accepted the offer (FR-014) | `сохранённый курс на {rates_date} (офлайн, загружен {fetched_at})` |

## LoadResult

`table: RateTable`, `status: LoadStatus`.

## ConversionResult

| Field | Type | Rules |
|---|---|---|
| `amount` | `Decimal` | Validated input, > 0, ≤ 2 decimals |
| `from_code`, `to_code` | `str` | Codes present in the table |
| `converted` | `Decimal` | `amount × per_unit(from) / per_unit(to)`, quantized to `0.01`, `ROUND_HALF_UP` |
| `rate` | `Decimal` | `per_unit(from) / per_unit(to)`, quantized to `0.0001` |
| `reverse_rate` | `Decimal` | `per_unit(to) / per_unit(from)`, quantized to `0.0001` |
| `same_currency` | `bool` | `from_code == to_code` → `converted == amount`, rates = 1 |

## Saved rates (JSON file)

```json
{
  "version": 1,
  "source": "Национальный банк Молдовы, bnm.md",
  "requested_date": "2026-11-18",
  "rates_date": "2026-11-18",
  "fetched_at": "2026-11-18T14:03:12",
  "rates": [
    {"code": "EUR", "name": "Euro", "nominal": 1, "value": "20.1538"},
    {"code": "JPY", "name": "Japanese Yen", "nominal": 100, "value": "11.5165"}
  ]
}
```

Rules: dates ISO 8601; `value` as string (exact decimal); any missing key, wrong type, unknown
`version` or invalid rate makes the whole file count as "no saved rates" (FR-016).

## Errors (`currency_converter/errors.py`)

| Exception | Raised when | GUI reaction |
|---|---|---|
| `ValidationError(message)` | Invalid amount or date (FR-009, FR-011) | Message next to the inputs, result cleared |
| `SourceUnavailableError(detail)` | Network error, timeout, DNS, HTTP status other than 200/404 | Notification + offer of saved rates |
| `InvalidResponseError(detail)` | Unparsable XML or root element is not `ValCurs` | Notification + offer of saved rates |
| `NoRatesError(requested_date, earliest_date)` | No rates for the date and 10 days back | Message, no conversion |

All inherit from `ConverterError(Exception)`; `str(error)` is the Russian user-facing message.

## State transitions (active rate table in the GUI)

```text
start ─► [saved table loaded from disk?] ─► loading(today)
loading ─ success ─► active = LIVE | EARLIER_DATE
loading ─ Source/Invalid error ─► notification (offer if saved table exists)
notification ─ "Использовать сохранённый курс" ─► active = CACHED, date field = saved.requested_date
active ─ date changed + Convert/Refresh ─► loading(new date)
```
