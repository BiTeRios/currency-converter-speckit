---

description: "Task list for the Currency Converter with Official BNM Rates"
---

# Tasks: Currency Converter with Official BNM Rates

**Input**: Design documents from `/specs/001-currency-converter/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (bnm-source.md,
core-api.md, gui.md, bnm-sample-2026-11-18.xml), quickstart.md

**Tests**: requested by the specification (FR-020). Following the constitution's workflow
(one branch per stage), all unit-test tasks are grouped in **Phase 8**, executed on the separate
branch `001-currency-converter-tests`. Each test task keeps its `[USx]` label for traceability.

**Branches**: Phases 1–7 → `001-currency-converter-implementation`; Phase 8 →
`001-currency-converter-tests`. Each branch is merged into `main` by a Pull Request.

**Rules for the implementing agent**:
- Names, signatures, messages and formulas are fixed by `contracts/core-api.md`,
  `contracts/bnm-source.md`, `contracts/gui.md` and `data-model.md`. Do not rename or "improve" them.
- Standard library only at runtime (constitution V). Core modules MUST NOT import `tkinter`.
- Mark a task `[X]` in this file when it is done. Do not write `REPORT.md` — the student writes it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4 from spec.md)

## Path Conventions

Single project, package at repository root: `currency_converter/`, tests in `tests/`
(see plan.md "Project Structure").

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: project skeleton

- [X] T001 Create package `currency_converter/` with `currency_converter/__init__.py` defining `APP_TITLE` and `SOURCE_NAME` exactly as in contracts/core-api.md, and `currency_converter/__main__.py` that calls `currency_converter.gui.main()`
- [X] T002 [P] Create `pyproject.toml` with only `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["."]`) and `requirements-dev.txt` containing `pytest>=8`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: types, errors, validation, number formatting and the cache used by every story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Implement the exception hierarchy and messages in `currency_converter/errors.py` per contracts/core-api.md (`ConverterError`, `ValidationError`, `SourceUnavailableError`, `InvalidResponseError`, `NoRatesError(requested_date, earliest_date)`) and data-model.md "Errors"
- [X] T004 [P] Implement in `currency_converter/models.py`: `CurrencyRate` (data-model.md CurrencyRate.code, CurrencyRate.name, CurrencyRate.nominal, CurrencyRate.value; `per_unit`), `MDL_RATE`, `RateTable` (data-model.md RateTable.rates_date, RateTable.requested_date, RateTable.source, RateTable.fetched_at, RateTable.rates — MDL never stored; `get`, `codes`), `LoadStatus`, `LoadResult` (data-model.md LoadResult.warning, default `None`) and `ConversionResult` (data-model.md ConversionResult.amount, ConversionResult.from_code, ConversionResult.to_code, ConversionResult.converted, ConversionResult.rate, ConversionResult.reverse_rate, ConversionResult.same_currency)
- [X] T005 [P] Implement `parse_amount` and `parse_rate_date` with the exact `MSG_*` constants, `MAX_AMOUNT` and `MIN_RATE_DATE` in `currency_converter/validation.py` per contracts/core-api.md (FR-009, FR-011)
- [X] T006 [P] Implement `format_amount`, `format_rate` (including the `< 0,0001` rule) and `format_date` in `currency_converter/formatting.py` per contracts/core-api.md (space thousands separator, comma decimal separator, `ROUND_HALF_UP`)
- [X] T007 [P] Implement `CACHE_FILE_NAME`, `CACHE_HOME_ENV`, `default_cache_path` (research.md R5; an empty env value counts as unset) and `RateCache` with `path`, `last_error`, `load`, `save` in `currency_converter/cache.py` using data-model.md "Saved rates" (decimals as strings, atomic write via temp file + `os.replace`; `load` never raises and sets `last_error` for an unreadable file — FR-015, FR-016)

**Checkpoint**: foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Convert an amount at today's official rate (Priority: P1) 🎯 MVP

**Goal**: start the app online, convert USD → MDL (and any pair, both directions) at today's
official BNM rate with date and source shown.

**Independent Test**: quickstart.md scenarios 1–4.

- [X] T008 [P] [US1] Implement `DEFAULT_BASE_URL`, `SOURCE_URL_ENV`, `TIMEOUT_SECONDS`, `USER_AGENT`, `build_url` (environment read at call time) and `fetch_xml` in `currency_converter/bnm_source.py` exactly per contracts/bnm-source.md "Request", "Responses" and "HTTP client details" (`urllib.request.urlopen` called through the module attribute)
- [X] T009 [P] [US1] Implement `parse_rates` in `currency_converter/bnm_source.py` per contracts/bnm-source.md "Parsing rules" (data-model.md CurrencyRate.code, CurrencyRate.name, CurrencyRate.nominal, CurrencyRate.value, RateTable.rates_date, RateTable.source = `SOURCE_NAME`, RateTable.fetched_at)
- [X] T010 [P] [US1] Implement `convert` (unknown code checked before same currency) and `currency_options` in `currency_converter/converter.py` (data-model.md ConversionResult.amount, ConversionResult.from_code, ConversionResult.to_code, ConversionResult.converted, ConversionResult.rate, ConversionResult.reverse_rate, ConversionResult.same_currency; FR-005–FR-008); check against the worked examples in contracts/core-api.md
- [X] T011 [P] [US1] Implement `SAME_CURRENCY_NOTE`, `result_line` (including the `< 0,01 CODE` rule), `rates_line` and `status_line` for `LoadStatus.LIVE` in `currency_converter/formatting.py`
- [X] T012 [US1] Implement `RateService.__init__` (injectable `fetch`, `cache` defaulting to `RateCache()`, `now`; public `cache` attribute) and `RateService.load` for the requested date only (offset 0; `None` or an empty table → `NoRatesError`) in `currency_converter/rate_service.py`
- [X] T013 [US1] Implement `ConverterApp` and `main()` in `currency_converter/gui.py`: layout rows 1–10 and 12 of contracts/gui.md, default USD → MDL, worker thread + `queue.Queue` polled with `root.after(100)` (behaviour 11), start-up load of today's rates (behaviour 1 without the saved-rates part, behaviour 2), Convert with immediate conversion when the active table matches (behaviour 6), Swap (8), Today (9), button rule and Enter binding (behaviour 10, FR-004), same-currency note in row 9 (FR-008)

**Checkpoint**: `python -m currency_converter` converts at today's live rate

---

## Phase 4: User Story 2 - Invalid input is rejected with a clear message (Priority: P1)

**Goal**: every invalid amount/date produces a specific message and no result.

**Independent Test**: quickstart.md scenarios 5–6.

- [X] T014 [US2] In `currency_converter/gui.py` show `ValidationError` messages from `parse_amount`/`parse_rate_date` in the red error label (row 6), clear result/rates/note labels on error, clear the error label on the next successful conversion (FR-010, contracts/gui.md behaviour 6)

**Checkpoint**: US1 + US2 work together

---

## Phase 5: User Story 3 - Work offline with the last saved rates (Priority: P2)

**Goal**: saved rates survive restarts and are offered when the source is unreachable.

**Independent Test**: quickstart.md scenarios 8–10.

- [X] T015 [US3] In `currency_converter/rate_service.py` save every successful table to `self.cache` (on `OSError` log it and return the `warning` text from contracts/core-api.md) and implement `RateService.load_saved` returning `LoadResult(table, LoadStatus.CACHED)` or `None`
- [X] T016 [P] [US3] Extend `status_line` in `currency_converter/formatting.py` with the `LoadStatus.CACHED` text from data-model.md "LoadStatus"
- [X] T017 [US3] In `currency_converter/gui.py` implement start-up `load_saved` with the `cache.last_error` notice (behaviour 1), the notification frame (row 11) with the messages and the `Использовать сохранённый курс от DD.MM.YYYY` (saved `rates_date`) / `Повторить` buttons for `SourceUnavailableError` and `InvalidResponseError` (behaviour 3), accepting the offer (behaviour 5: active = CACHED, date field = saved `requested_date`), and showing `LoadResult.warning` in the note label (behaviour 2)

**Checkpoint**: quickstart scenario 8 works with `CURRENCY_CONVERTER_SOURCE_URL=http://127.0.0.1:9/`

---

## Phase 6: User Story 4 - Rates for a chosen date, including days without publication (Priority: P3)

**Goal**: convert at the rate of any date in range; fall back to the closest earlier published date.

**Independent Test**: quickstart.md scenario 7; fallback is verified by unit tests (T029).

- [X] T018 [US4] Extend `RateService.load` in `currency_converter/rate_service.py` with the look-back loop over `MAX_LOOKBACK_DAYS = 10` exactly as in contracts/core-api.md (`EARLIER_DATE` status, `requested_date` replaced with the user's date, `NoRatesError(requested, requested − 10 days)` when nothing is found)
- [X] T019 [P] [US4] Implement `fallback_notice` and the `LoadStatus.EARLIER_DATE` text of `status_line` in `currency_converter/formatting.py`
- [X] T020 [US4] In `currency_converter/gui.py` load rates for the date in the date field when it differs from the active table (behaviour 6), implement `Обновить курс` (behaviour 7), show `fallback_notice` in the note label (behaviour 2) and `NoRatesError` in the error label (behaviour 4)

**Checkpoint**: all four user stories work

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T021 Override `root.report_callback_exception` and route worker exceptions through the queue so unexpected errors are logged and shown as `Непредвиденная ошибка: … Приложение продолжает работу.` in `currency_converter/gui.py` (FR-019, contracts/gui.md behaviour 12)
- [X] T022 [P] Configure `logging` (INFO to stderr) in `currency_converter/__main__.py`; log every load attempt, fallback day and cache error
- [X] T023 [P] Write `README.md`: purpose, data source, requirements, `python -m currency_converter`, test command `python -m pytest`, environment variables `CURRENCY_CONVERTER_HOME` and `CURRENCY_CONVERTER_SOURCE_URL`
- [ ] T024 Check that `python -m currency_converter` starts and walk through quickstart.md scenarios 1–10 as far as possible; fix any deviation from spec.md (constitution: this is the completion gate of the implementation stage)

**Checkpoint**: implementation branch ready for its Pull Request

---

## Phase 8: Unit tests (branch `001-currency-converter-tests`)

**Purpose**: FR-020 / SC-007 — tests run with `python -m pytest`, no network access, never touching
the real %APPDATA% (every `RateService` and `RateCache` in tests uses a fake or a `tmp_path` cache).

- [ ] T025 [P] Create `tests/__init__.py`, copy `specs/001-currency-converter/contracts/bnm-sample-2026-11-18.xml` to `tests/fixtures/bnm_2026-11-18.xml`, and add `tests/fixtures/bnm_empty.xml` (`<ValCurs Date="18.11.2026"/>`) and `tests/fixtures/bnm_malformed.xml` (truncated XML)
- [ ] T026 [P] [US1] Write `tests/test_bnm_source.py`: parsing the real sample (40 currencies, EUR 20.1538 named «Евро», USD 18.3383, JPY nominal 100, `rates_date` 18.11.2026), skipped invalid `Valute` variants (bad code, MDL, nominal 0, negative or non-numeric value, missing tags), comma decimal, duplicates, missing `@Date`, empty `ValCurs` → empty rates, malformed XML and wrong root → `InvalidResponseError`; `build_url` format and env override set with `monkeypatch.setenv` after import; `fetch_xml` with a fake `urllib.request.urlopen` exactly as described in contracts/bnm-source.md "HTTP client details" for 200, 200-empty, `HTTPError` 404, `HTTPError` 500, non-200 status, `URLError`, `TimeoutError`
- [ ] T027 [P] [US1] Write `tests/test_converter.py`: worked examples of contracts/core-api.md, reverse direction, cross rate through MDL with nominal 100, same currency, unknown code → `ValidationError` (also when both codes are the same unknown code), `currency_options` order, the FR-007 round-trip tolerance for every pair of the real sample, and SC-002 as a proxy: converting every pair of the sample takes less than 0.5 s in total
- [ ] T028 [P] [US2] Write `tests/test_validation.py`: every accepted and rejected amount from spec.md US2 and FR-009 with the exact `MSG_*` message, dates (format, impossible date, before 01.01.2000, tomorrow allowed, day after tomorrow rejected)
- [ ] T029 [P] [US4] Write `tests/test_rate_service.py` with a fake fetcher `{date: bytes | None | Exception}` and a `tmp_path` or fake cache: live result; `None` for D and D−1, rates at D−2 → `EARLIER_DATE`, `rates_date` D−2, `requested_date` D; empty `ValCurs` counts as no data; 11 misses → `NoRatesError` and exactly 11 fetch calls; `SourceUnavailableError`/`InvalidResponseError` propagate without fallback; success is saved to the cache; a cache whose `save` raises `OSError` → result still returned with `warning` set; `load_saved` returns `CACHED` or `None`
- [ ] T030 [P] [US3] Write `tests/test_cache.py` in `tmp_path`: save/load round trip keeps exact decimals, names and dates; missing file → `None` and `last_error is None`; garbage, wrong `version` or missing keys → `None` and `last_error` set; no temp files left; `default_cache_path` honours `CURRENCY_CONVERTER_HOME` and ignores an empty value
- [ ] T031 [P] Write `tests/test_formatting.py`: thousands grouping, comma separator, half-up rounding, `< 0,01` and `< 0,0001` rules, `result_line`, `rates_line`, `status_line` for all three statuses, `fallback_notice`
- [ ] T032 Run `python -m pytest`; fix failing production code only where the test reflects the contracts, and record every such fix in the Pull Request description

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → user stories.
- **US1 (Phase 3)** is the MVP and creates `gui.py`, `bnm_source.py`, `rate_service.py`
  (the cache module already exists from Phase 2).
- **US2 (Phase 4)** needs the GUI from US1.
- **US3 (Phase 5)** and **US4 (Phase 6)** both extend `rate_service.py`, `formatting.py` and
  `gui.py`; run them sequentially (US3 then US4) to avoid conflicting edits.
- **Polish (Phase 7)** after all stories. **Tests (Phase 8)** after the implementation branch is
  merged.

### Parallel Opportunities

- Phase 2: T003–T007 (different files).
- Phase 3: T008/T009 (same file, independent functions — sequential for a single agent),
  T010 and T011 in parallel; T012 after T008–T009; T013 last.
- Phase 8: T026–T031 all in parallel (different test files).

### Parallel Example: User Story 1

```text
Task: "Implement build_url/fetch_xml in currency_converter/bnm_source.py"     (T008)
Task: "Implement convert/currency_options in currency_converter/converter.py" (T010)
Task: "Implement result_line/rates_line/status_line in formatting.py"         (T011)
```

## Implementation Strategy

1. **MVP**: Phases 1–3 → a working live converter (stop and validate with quickstart 1–4).
2. **Increment**: Phase 4 (validation UX) → Phase 5 (offline) → Phase 6 (dates/fallback).
3. **Polish**: Phase 7, then open the implementation Pull Request.
4. **Tests**: Phase 8 on its own branch, then the tests Pull Request.
