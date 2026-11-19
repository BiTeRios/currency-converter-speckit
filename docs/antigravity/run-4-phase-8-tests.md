# Antigravity, прогон 4: фаза 8, unit-тесты (T025–T031)

| Параметр | Значение |
|---|---|
| Инструмент | Google Antigravity CLI `agy` 1.5.11, режим `-p` (без интерфейса) |
| Модель | `gemini-3.8-flash-high` |
| Флаги | `--sandbox --mode accept-edits --output-format stream-json (новый диалог)` |
| Статус | SUCCESS |
| Время прогона (журнал CLI) | 19.11 01:52:47 – 02:01:55 (9 мин 8 с) |
| `duration_seconds` agy | 545 с (при `-c` накопительно для всего диалога) |
| Токены (накопительно для диалога) | вход 168065, выход 78404, размышления 51281, из кэша 2242770 |
| Шагов в журнале | 303 |

## Промпт

```text
You are the implementing agent for this repository (Spec-Driven Development with GitHub Spec Kit). The application is already implemented and merged (Phases 1-7 of `specs/001-currency-converter/tasks.md` are done). This run is the separate tests stage.

Follow the `/speckit-implement` workflow (`.github/skills/speckit-implement/SKILL.md`) for Phase 8 only: tasks T025-T031 of `specs/001-currency-converter/tasks.md`. Do not do T032 (running the suite) — the human runs `python -m pytest` and will send you any failures.

Before writing tests, read: `.specify/memory/constitution.md`, `specs/001-currency-converter/spec.md` (FR-009, FR-011, FR-020, US1-US4), `data-model.md`, `contracts/core-api.md`, `contracts/bnm-source.md` (especially "HTTP client details" — how to fake `urllib.request.urlopen`), and the production code in `currency_converter/`.

Rules:
- pytest only; tests must not touch the network and must never write to the real user profile: every `RateService` and `RateCache` uses a fake or a `tmp_path` cache; set or clear `CURRENCY_CONVERTER_HOME` / `CURRENCY_CONVERTER_SOURCE_URL` with `monkeypatch`.
- Tests check the contracts (exact names, messages, formulas). If you believe the production code disagrees with a contract, still write the test against the contract and list the disagreement in your final reply — do not change production code in this run.
- Do not test the Tkinter GUI (no display in CI); test only the GUI-free modules.
- Edit-only mode: you can read and edit files, terminal commands are not available. Be careful with imports and fixture paths since you cannot run the tests.
- No git commands. Do not modify `.specify/`, `.github/`, `specs/` except ticking `- [X]` in tasks.md for T025-T031.

When you finish, reply with: files created, tasks completed, how many tests per file, and any place where you think the code and the contracts disagree.
```

## Ответ агента (дословно)

### Summary of Work

Following the `/speckit-implement` workflow for Phase 8, all test fixtures and unit test suites specified in tasks **T025–T031** have been implemented without touching the network or writing to the real user profile.

---

### 1. Files Created

- [`tests/__init__.py`](tests/__init__.py)
- [`tests/fixtures/bnm_2026-11-18.xml`](tests/fixtures/bnm_2026-11-18.xml) — Official BNM XML sample response for 18.11.2026 (40 foreign currencies).
- [`tests/fixtures/bnm_empty.xml`](tests/fixtures/bnm_empty.xml) — Minimal empty publication `<ValCurs Date="18.11.2026"/>`.
- [`tests/fixtures/bnm_malformed.xml`](tests/fixtures/bnm_malformed.xml) — Truncated XML to verify syntax error handling.
- [`tests/test_bnm_source.py`](tests/test_bnm_source.py)
- [`tests/test_converter.py`](tests/test_converter.py)
- [`tests/test_validation.py`](tests/test_validation.py)
- [`tests/test_rate_service.py`](tests/test_rate_service.py)
- [`tests/test_cache.py`](tests/test_cache.py)
- [`tests/test_formatting.py`](tests/test_formatting.py)

---

### 2. Tasks Completed

Ticked off `[X]` in [`specs/001-currency-converter/tasks.md`](specs/001-currency-converter/tasks.md#L137-L143):

- **T025 [P]**: Created package test init and XML fixtures (`bnm_2026-11-18.xml`, `bnm_empty.xml`, `bnm_malformed.xml`).
- **T026 [P] [US1]**: Implemented `tests/test_bnm_source.py` (URL generation, environment overrides, XML parsing rules, invalid currency filtering, and fake `urllib.request.urlopen` handling).
- **T027 [P] [US1]**: Implemented `tests/test_converter.py` (worked examples, cross rates with nominals, same-currency conversions, currency options order, FR-007 round-trip tolerance on all pairs, and SC-002 conversion benchmark).
- **T028 [P] [US2]**: Implemented `tests/test_validation.py` (all accepted and rejected amounts and dates with exact error constants).
- **T029 [P] [US4]**: Implemented `tests/test_rate_service.py` (live loading, look-back fallback up to 10 days, 11-miss `NoRatesError`, immediate propagation of `SourceUnavailableError` / `InvalidResponseError`, cache `save` failure handling, and `load_saved`).
- **T030 [P] [US3]**: Implemented `tests/test_cache.py` (save/load round trip, missing/corrupted/wrong-version/invalid-entry handling, temp file cleanup, and `default_cache_path` resolution).
- **T031 [P]**: Implemented `tests/test_formatting.py` (space thousands grouping, comma decimal separator, `ROUND_HALF_UP` rounding, `< 0,01` and `< 0,0001` rules, `result_line`, `rates_line`, `status_line`, and `fallback_notice`).

*(Task T032 is left unchecked for the human runner to execute `python -m pytest`.)*

---

### 3. Number of Tests per File

| Test File | Test Functions | Parametrized Invocations |
|---|:---:|:---:|
| [`tests/test_bnm_source.py`](tests/test_bnm_source.py) | **23** | 23 |
| [`tests/test_converter.py`](tests/test_converter.py) | **16** | 16 (includes 1,640 pair iterations in FR-007 and SC-002) |
| [`tests/test_validation.py`](tests/test_validation.py) | **11** | 76 |
| [`tests/test_rate_service.py`](tests/test_rate_service.py) | **10** | 10 |
| [`tests/test_cache.py`](tests/test_cache.py) | **11** | 25 |
| [`tests/test_formatting.py`](tests/test_formatting.py) | **13** | 40 |
| **Total** | **84** | **190** |

---

### 4. Code and Contract Agreement Review

After comparing `currency_converter/` against `specs/001-currency-converter/spec.md`, `data-model.md`, `contracts/core-api.md`, and `contracts/bnm-source.md`:

- **No disagreements were found.**
- All class names, signatures, constant values, Russian exception messages, regex patterns, rounding rules (`ROUND_HALF_UP`), threshold limits (`< 0,01`, `< 0,0001`), atomic cache mechanics, and fallback logic in the production code match the contracts.
