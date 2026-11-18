# Quickstart: validating the Currency Converter

## Prerequisites

- Python 3.11+ with Tk (the python.org installer for Windows includes it).
- Network access to `www.bnm.md` for the online scenarios.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Automated checks

```powershell
python -m pytest
```

Expected: all tests pass, no network access needed (FR-020, SC-007). The suites map to
[core-api.md](./contracts/core-api.md): `test_bnm_source.py`, `test_rate_service.py`,
`test_cache.py`, `test_converter.py`, `test_validation.py`, `test_formatting.py`.

## Run

```powershell
python -m currency_converter
```

## Manual validation scenarios

Use a separate cache directory so the checks are repeatable:
`$env:CURRENCY_CONVERTER_HOME = "$env:TEMP\cc-demo"`.

| # | Steps | Expected | Spec |
|---|---|---|---|
| 1 | Start online, amount `100`, USD → MDL, Convert | `100,00 USD = … MDL`, rate line, status `курс на <today>` with the source name | US1, FR-006, FR-017 |
| 2 | Press `⇄ Поменять`, type the MDL result, Convert | ≈ `100,00 USD` (within ±0,0103, FR-007 tolerance) | FR-007 |
| 3 | EUR → EUR, Convert | amount unchanged, note `Валюты совпадают…` | FR-008 |
| 4 | Clear the amount | `Конвертировать` disabled | FR-004 |
| 5 | Amounts `abc`, `0`, `-5`, `1,234`, `1e5` | specific red message, no result | FR-009, FR-010 |
| 6 | Date `31.02.2026`, `01.01.1999`, a date two days ahead | date message, no request | FR-011 |
| 7 | Date of last Sunday, Convert | rates of that day (carried forward by the source) | US4 |
| 8 | Close the app. `$env:CURRENCY_CONVERTER_SOURCE_URL = "http://127.0.0.1:9/"`, start again | message about no connection + `Использовать сохранённый курс от …`; after pressing it conversions work and the status says `офлайн` | US3, FR-014 |
| 9 | Same as 8 but with `CURRENCY_CONVERTER_HOME` pointing to a new, empty directory | message that rates are unavailable, window stays open, Convert disabled | US3 AS-3 |
| 10 | Write `garbage` into `rates_cache.json`, start | starts normally, note says the saved rates could not be read | FR-016 |

Remove the overrides afterwards:
`Remove-Item Env:CURRENCY_CONVERTER_SOURCE_URL, Env:CURRENCY_CONVERTER_HOME`.
