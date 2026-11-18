# Implementation Plan: Currency Converter with Official BNM Rates

**Branch**: `001-currency-converter` | **Date**: 2026-11-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-currency-converter/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A single-window Tkinter desktop application converts amounts between MDL and the ~40 currencies
published daily by the National Bank of Moldova (BNM). Rates come from the official BNM XML
endpoint, are parsed with `xml.etree`, computed with `decimal.Decimal`, and the last successful
rate table is persisted as JSON so the app keeps working offline. All non-GUI logic (source
client, parser, rate service with date fallback, cache, conversion, validation, formatting) lives
in GUI-free modules with exact, documented signatures so that unit tests and the GUI depend on the
same contracts. Network calls run in a worker thread; the GUI polls a queue.

## Technical Context

**Language/Version**: Python 3.11+ (developed and verified on CPython 3.14, Windows 11)

**Primary Dependencies**: standard library only — `tkinter`/`ttk`, `urllib.request`,
`xml.etree.ElementTree`, `decimal`, `json`, `threading`, `queue`, `datetime`, `pathlib`, `os`

**Storage**: one JSON file with the last successful rate table
(`%APPDATA%\CurrencyConverter\rates_cache.json` on Windows; see [research.md](./research.md) R5)

**Testing**: `pytest` (only dev dependency, `requirements-dev.txt`); command `python -m pytest`

**Target Platform**: desktop — Windows 10/11 primary; Linux/macOS with Python + Tk should work

**Project Type**: desktop-app (single project)

**Performance Goals**: conversion with loaded rates < 0.5 s (SC-002); first live result
< 10 s after start on a normal connection (SC-001)

**Constraints**: offline-capable via cache; network timeout 10 s per request; at most 11 requests
per load (requested date + 10 days back); GUI thread never blocks on I/O

**Scale/Scope**: 1 window, ~8 modules, ~41 currencies, 1 user

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How the plan satisfies it | Status |
|---|---|---|
| I. Specification is the source of truth | Every module maps to FRs (see table below); tasks reference FR ids; deviations go to `REPORT.md` | PASS |
| II. Never crash, always explain | All source errors become typed exceptions handled by the GUI; top-level `report_callback_exception` handler; cache errors ignored | PASS |
| III. Honest data provenance | `RateTable` carries `rates_date`, `requested_date`, `source`; `LoadStatus` drives the info line; `Decimal` everywhere | PASS |
| IV. Testable core, thin GUI | Core modules never import `tkinter`; fetcher and clock are injected into `RateService` | PASS |
| V. Simplicity, minimal deps | Standard library only; `pytest` dev-only; one cache file | PASS |
| Workflow: branches + PRs | spec → `001-currency-converter`, implementation → `001-currency-converter-implementation`, tests → `001-currency-converter-tests`, each merged by PR | PASS |

*Post-design re-check (after Phase 1)*: PASS — the contracts keep `tkinter` confined to `gui.py`,
and the source URL is overridable by environment variable only for manual offline testing
(no new dependency, no new abstraction layer).

### Requirement → module map

| Module | Requirements |
|---|---|
| `currency_converter/bnm_source.py` | FR-012, FR-014 (errors), FR-018 (timeout), FR-020 (parser) |
| `currency_converter/rate_service.py` | FR-012, FR-013, FR-015 (save after success) |
| `currency_converter/cache.py` | FR-015, FR-016 |
| `currency_converter/converter.py` | FR-003 (options), FR-005, FR-006, FR-007, FR-008 |
| `currency_converter/validation.py` | FR-009, FR-011 |
| `currency_converter/formatting.py` | FR-006, FR-017 (texts) |
| `currency_converter/gui.py` | FR-001, FR-002, FR-004, FR-010, FR-014 (offer), FR-017, FR-018, FR-019 |

## Project Structure

### Documentation (this feature)

```text
specs/001-currency-converter/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── bnm-source.md            # external source: URL, status codes, XML format
│   ├── bnm-sample-2026-11-18.xml  # real response saved on 2026-11-18 (test fixture source)
│   ├── core-api.md              # public functions/classes of the core modules + exact messages
│   └── gui.md                   # window layout, widget states, texts
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
currency_converter/
├── __init__.py          # APP_TITLE, SOURCE_NAME constants
├── __main__.py          # `python -m currency_converter` → gui.main()
├── models.py            # CurrencyRate, RateTable, LoadStatus, LoadResult, ConversionResult
├── errors.py            # ValidationError, SourceUnavailableError, InvalidResponseError, NoRatesError
├── bnm_source.py        # build_url(), fetch_xml(), parse_rates()
├── rate_service.py      # RateService.load(date) with 10-day fallback + cache save
├── cache.py             # RateCache(path).load()/save(); default_cache_path()
├── converter.py         # convert(), currency_options()
├── validation.py        # parse_amount(), parse_rate_date()
├── formatting.py        # format_amount(), format_rate(), format_date(), status_line()
└── gui.py               # ConverterApp (Tkinter/ttk), worker thread + queue

tests/
├── fixtures/
│   ├── bnm_2026-11-18.xml       # copy of contracts/bnm-sample-2026-11-18.xml
│   ├── bnm_empty.xml            # <ValCurs> with no <Valute>
│   └── bnm_malformed.xml        # broken XML
├── test_bnm_source.py
├── test_rate_service.py
├── test_cache.py
├── test_converter.py
├── test_validation.py
└── test_formatting.py

README.md                 # run + test commands
REPORT.md                 # lab report (agent errors, deviations)
requirements-dev.txt      # pytest>=8
pyproject.toml            # [tool.pytest.ini_options] testpaths, pythonpath
```

**Structure Decision**: single project, package at repository root so `python -m currency_converter`
and `python -m pytest` work from a fresh clone without installation. `tests/` mirrors the core
modules one-to-one; the GUI is verified manually through [quickstart.md](./quickstart.md).

## Complexity Tracking

No constitution violations; nothing to justify.
