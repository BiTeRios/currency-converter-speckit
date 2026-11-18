# /speckit-analyze — pass 1 (2026-11-18)

Run by an independent reviewer agent following `.github/skills/speckit-analyze/SKILL.md`
(read-only). The command itself writes no files; this record was saved afterwards so the
consistency check is visible in the repository. Resolutions were applied in the next commit.

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| C1 | CRITICAL | Constitution: "a stage is complete only when `python -m pytest` passes", but the implementation branch has no tests (pytest exits with code 5) | Constitution v1.1.0: implementation stage is complete when the app starts and quickstart passes; the pytest gate applies from the tests stage on |
| C2 | CRITICAL | Principle II requires a message for an unreadable cache; FR-016 ignored it silently; cache save errors were only logged | FR-015/FR-016 now require a non-blocking notice; `RateCache.last_error` and `LoadResult.warning` added to the contracts |
| I1 | HIGH | "±0.01 for MDL/EUR/USD pairs" is false (0.10 MDL → EUR → MDL differs by 0.10); the general FR-007 formula held for 1640 pairs × 2002 amounts | The ±0.01 claim removed from FR-007/SC-003; examples reference the formula |
| I2 | HIGH | FR-004 vs gui.md behaviour 10 disagree on enabling Convert without an active table; Enter not covered | One rule: enabled iff amount non-blank, both currencies selected (lists come from live or saved rates), not loading; Enter does nothing when disabled |
| U1 | HIGH | `fetch_xml` call form unspecified, so tests could hit the network | core-api.md fixes `urllib.request.urlopen(Request, timeout=…)` as a module attribute, context manager, `HTTPError` handling |
| U2 | HIGH | Constrained fields without `Entity.field` citations (`RateTable.source`, `RateTable.fetched_at`, `CurrencyRate.name`, `ConversionResult.amount/from_code/to_code`) | Citations added to the implementing tasks |
| U3 | MEDIUM | Source URL env variable read at import time | `build_url` reads it on every call |
| U4 | MEDIUM | Rate-service tests could write to the real %APPDATA% | Test task requires a fake or `tmp_path` cache |
| F1 | MEDIUM | T011 (Phase 3) depends on `RateCache` from Phase 5 | `cache.py` moved to the Foundational phase |
| F2 | MEDIUM | No task builds GUI row 9; wrong behaviour number | Fixed in the GUI task |
| U5 | MEDIUM | Offer `{date}` ambiguous (rates vs requested date) | Offer shows `rates_date`; the date field gets `requested_date` |
| U6 | LOW | Message punctuation differs between spec and contract | Spec aligned with `MSG_AMOUNT_NOT_NUMBER` |
| U7 | LOW | Empty `CURRENCY_CONVERTER_HOME` would mean the current directory | Empty value is ignored |
| U8 | LOW | Display of a result 0,00 or a rate 0,0000 undefined | `< 0,01` / `< 0,0001` rules added |
| U9 | LOW | Order of unknown-code check vs same currency | Unknown code is checked first |
| F3 | LOW | Russian UI but English currency names from `/en/` | Switched to the `/ru/` endpoint (verified: same codes and values, Russian names, same 404 behaviour) |
| — | (coverage) | SC-002 (< 0.5 s) never measured | Timing assertion added to the converter test task |

Metrics before fixes: 27 requirements, 32 tasks, coverage 96 %, 2 critical issues.
