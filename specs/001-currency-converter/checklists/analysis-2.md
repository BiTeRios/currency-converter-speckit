# /speckit-analyze — pass 2 (2026-11-18)

Second read-only run by the same independent reviewer after remediation commit `f7d995b`.

**Pass-1 findings**: 16 of 17 RESOLVED; F3 PARTIAL (the constitution still named `/en/`).

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| N1 | CRITICAL | Constitution still names the `/en/` endpoint and overrides other documents | Constitution v1.1.1, amended in its own commit (`/ru/`) |
| N2 | MEDIUM | Constitution v1.1.0 was committed together with other files, but Governance requires a dedicated commit | Process deviation recorded here and in `REPORT.md`; v1.1.1 committed alone |
| N3 | MEDIUM | The start-up damaged-cache notice in the note label could be wiped by the successful start-up load | gui.md behaviour 2: a successful load never clears the note label; the notice stays until the next Convert or Swap |
| N4 | MEDIUM | GUI's copy of "saved rates" stays the start-up snapshot, so a later failure could offer a stale date | gui.md behaviour 2: after every successful load the saved copy is replaced by the loaded table |
| N5 | LOW | Unclear whether `RateService.cache` can be `None` | core-api.md: never `None` (`cache=None` → `RateCache()`) |
| N6 | LOW | `http.client.HTTPException` (`IncompleteRead`) not mapped | bnm-source.md: mapped to `SourceUnavailableError` |

Metrics after pass 2: 27 requirements, 32 tasks, coverage 100 %, 1 critical (fixed as above).
The pass-2 fixes are small textual edits verified by reviewing the diff; a third full pass was
not run.
