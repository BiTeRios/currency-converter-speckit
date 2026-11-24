# Lab 3 Report — Spec-Driven Currency Converter with Google Antigravity

This report records the original desktop implementation. The desktop visual refresh and the
separate browser interface have their own [follow-up specification](specs/002-web-ui/spec.md).

## Tools and responsibilities

| Stage | Tool | Model |
|---|---|---|
| Installing GitHub Spec Kit 1.4.3 and running `specify init --integration copilot --extension git --script ps` | Claude Code | Claude Opus 5.5 |
| `/speckit-constitution`, `/speckit-specify`, `/speckit-plan`, `/speckit-tasks` | Claude Code following the Spec Kit skill files (`.github/skills/speckit-*/SKILL.md`) and PowerShell scripts | Claude Opus 5.5 |
| `/speckit-analyze`, two passes | Independent Claude Code review agent with read-only access | Claude |
| **Implementation, phases 1–7 (T001–T023)** | **Google Antigravity CLI `agy` 1.5.11** | **Gemini 3.8 Flash (High)** |
| Manual quickstart validation (T024) and test execution (T032) | Claude Code | Claude Opus 5.5 |
| **Unit tests, phase 8 (T025–T031)** | **Google Antigravity** | **Gemini 3.8 Flash (High)** |
| Independent review of generated code | Claude Code review agent | Claude |
| Review fixes | Antigravity (Gemini, then GPT-OSS 120B and Claude Sonnet 4.6) and manual fixes with Claude Code | See section 4 |

**Departures from the assignment**

- **Claude Code took over the Copilot work.** The assignment specifies VS Code with Copilot Chat.
  The instructor allowed any generative AI, so Claude Code followed the same skill files that
  Spec Kit generated for Copilot. The resulting Markdown artifacts were executed by an agent
  from another company.
- **Antigravity permissions were restricted after the first run.** Run 1 auto-approved all actions
  (`--dangerously-skip-permissions`). Claude Code's permission system then disallowed fully
  auto-approved runs as a bypass of its controls. Runs 2–9 used `--mode accept-edits`, which
  allowed Antigravity to read and edit files without running commands. Claude Code verified each
  run and performed T024 and T032.

The [Antigravity logs](docs/antigravity/) record each prompt, model, runtime, token count and
verbatim agent response.

## 1. Data source and rationale

The converter uses the official XML feed from the National Bank of Moldova (BNM).

`https://www.bnm.md/ru/official_exchange_rates?get_xml=1&date=DD.MM.YYYY`

1. BNM publishes the official rates for Moldova. Free exchange-rate APIs usually omit MDL or
   require an API key, and their rates are unofficial.
2. The feed requires no API key or registration and has no usage limits.
3. Each request targets a specific date, making weekend and holiday cases straightforward to
   verify.
4. Parsing denominations, invalid entries and malformed responses provides useful unit-test cases.

The feed was checked live on 18 November 2026. See R2 in [research.md](specs/001-currency-converter/research.md).

| Requested date | Response |
|---|---|
| Business day | HTTP 200 with 40 currencies |
| Weekend | HTTP 200 with Friday's rates and the requested date in `Date` |
| Tomorrow | HTTP 200 after publication at around 13:00 |
| Day after tomorrow or a date in 1990 | HTTP 404 with an empty body |

JPY and UZS are quoted per 100 units. After the first analysis pass, the endpoint changed from
`/en/` to `/ru/`. Both endpoints provide the same rates, and the Russian currency names match
the interface language.

## 2. Antigravity model runs

On 18 November 2026, `agy models` listed `gemini-3.8-flash-high/medium/low`,
`claude-sonnet-4-6`, `claude-opus-4-6-thinking` and `gpt-oss-120b-medium`.
The list omitted **Gemini 3.5 Flash** and **Gemini 3.1 Pro**, which the assignment names.
Gemini 3.8 Flash (High) was the main implementation model because the exercise called for an
agent and model from a company different from the one that produced the specification.

| Run | Stage | Model | Duration | Outcome |
|---|---|---|---|---|
| 1 | Phases 1–2, T001–T007 | Gemini 3.8 Flash High | 7 min 9 s | ✅ No issues |
| 2 | Phases 3–4, T008–T014 | Gemini 3.8 Flash High | 5 min 29 s | ✅ Also completed parts of later phases |
| 3 | Phases 5–7, T015–T023 | Gemini 3.8 Flash High | 4 min 6 s | ✅ No issues |
| 4 | Phase 8, tests T025–T031 | Gemini 3.8 Flash High | 9 min 8 s | ⚠️ A test file failed to compile |
| 5 | Test fix (T032) | Gemini 3.8 Flash High | 55 s | ✅ Fixed |
| 6 | Review fixes | Gemini 3.8 Flash High | 4 min 31 s | ⚠️ Interrupted when the weekly quota ran out |
| 7 | Remaining review fixes | GPT-OSS 120B | 2 min 53 s | ❌ Asked for the task again and made no changes |
| 8 | Remaining review fixes | GPT-OSS 120B | 9 min 58 s | ❌ Reported changes that did not exist |
| 9 | Remaining review fixes | Claude Sonnet 4.6 | 7 s | ❌ Stopped without edits |

The durations come from the CLI logs. The `duration_seconds` field accumulates across a continued
conversation (`-c`). Commit `a681f00` therefore incorrectly recorded 2 h 10 min for run 3.
The description of PR #2 was corrected.

## 3. What the agent delivered on the first attempt

The code from runs 1–3 (all tasks T001–T023) passed these checks without manual edits:

- **103 checks against the core and data-source contracts.** These covered exact names,
  signatures and Russian messages, denomination-aware conversion and the contract examples
  (`100 USD = 1833,83 MDL` and `100 EUR = 17499,93 JPY`), real XML parsing, HTTP 200/404/5xx
  and network failures, exactly 11 requests before `NoRatesError`, atomic caching, `last_error`
  and `LoadResult.warning`. [Core API contract](specs/001-currency-converter/contracts/core-api.md)
  · [BNM source contract](specs/001-currency-converter/contracts/bnm-source.md)
- **25 window checks with a stubbed service.** These covered automatic loading at start-up,
  button state and Enter, validation messages, the offline offer and the visibility of the
  damaged-cache notice.
- **Quickstart scenarios 1–10 against the live source.** These covered conversion in both
  directions, Sunday rates, offline operation with and without saved rates, and a damaged cache.
  [T024 results](docs/quickstart/T024-results.md)

The original README was in Russian. The task list marked only completed tasks.
Of the 190 tests from the first version of phase 8, 167 were correct on the first attempt
(five of six files).

## 4. Agent errors and manual fixes

| # | Issue | How it was found | Fix |
|---|---|---|---|
| 1 | **Exceeded the scope of run 2.** The agent was told to stop at T014 but implemented parts of T015, T017, T019 and T021. | Review of the run 2 diff | Recorded as a process deviation. The code was correct. |
| 2 | **A test file failed to compile.** Cyrillic characters in byte literals such as `b"""…"""` caused a `SyntaxError`. | `pytest` run (T032) | Agent, run 5 |
| 3 | **The test encoded the implementation's behavior.** It expected `None` for a 404 returned as a response, while the contract requires `SourceUnavailableError` in that case. In run 4 the agent claimed it had found no discrepancies. | Independent review. The test failed after the implementation was corrected. | Manual |
| 4 | **The app substituted USD or MDL when a new rate table no longer contained a selected currency.** It converted the wrong pair, violating GUI behavior 2. | Independent review | Agent, run 6 |
| 5 | The app cleared the save-failure warning after a rate load triggered by Convert (FR-015). | Independent review | Agent, run 6 |
| 6 | The app claimed no saved data existed while it was already using saved rates (constitution principle II). | Independent review | Agent, run 6 |
| 7 | The parser accepted rates such as `Infinity`, `1E+30` and `1_8.5`. Conversion could then fail with `InvalidOperation`. | Independent review | Agent, run 6 |
| 8 | An invalid source URL produced `ValueError` instead of `SourceUnavailableError`. A 404 returned as a response also diverged from the contract. | Independent review | Agent, run 6 |
| 9 | `logger.exception` was called outside the exception handler, so the logs omitted the worker's traceback. | Independent review | Agent, run 6 |
| 10 | Amount validation accepted Arabic and full-width digits and inputs like `"1, 5"`. The cache accepted `nominal: true` and the code `U1D`. | Independent review | Agent, run 6 |
| 11 | Unused import and unreachable `else` branch. | Independent review | Agent removed the import. The branch was removed manually. |
| 12 | **GPT-OSS 120B falsely reported new tests and fixes.** The run recorded 86 tool errors and produced an empty diff. | Comparison of `git diff` before and after the run | The remaining work was completed manually. |

Claude Code applied the manual code changes in commit `0520ae1`.

- Removed the unreachable branch in `formatting.status_line`.
- Updated `test_fetch_xml_404_status_response` to reflect the contract.
- Added regression tests for issues 7, 8 and 10.

Manual work was needed because Gemini's weekly quota ran out with 165 hours until reset,
GPT-OSS produced a false report, and Claude Sonnet 4.6 stopped without changes. These were the
only manual application-code fixes in the original implementation.

**Issues in the specification written with Claude Code**

- The first version of `spec.md` gave an incorrect round-trip tolerance of ±0.01.
  Planning and analysis both identified that converting 0.10 MDL to EUR and back gives a
  discrepancy of 0.10. The tolerance was corrected.
- The contract requires the message `"Нет связи с bnm.md: {detail}"`. Following it exposes
  technical text such as `<urlopen error [WinError 10061]…>`. This conflicts with the
  constitution's requirement for a plain-language message. The discrepancy remains documented.
- The v1.1.0 amendment to the constitution was committed together with other files. The
  Governance section calls for a dedicated commit. See N2 in the second analysis pass.

## 5. Conformance to the original specification

| Requirements | Status | Evidence |
|---|---|---|
| FR-001–FR-004 (window, controls, currency lists and button state) | ✅ | Window smoke checks and quickstart scenarios 1 and 4 |
| FR-005–FR-008 (formula, rounding, swap and same currency) | ✅ | Unit tests, FR-007 tolerance for 1,640 pairs and quickstart scenarios 1–3 |
| FR-009–FR-011 (amount and date validation) | ✅ With a caveat | Unit tests and quickstart scenarios 5–6. After the review fix for issue 10, spaces are allowed only between three-digit groups. Inputs such as `15 00` and `1  500` now trigger the invalid-number message. `- 10` also triggers that message, where the contract would report that the amount must be greater than zero. This follows FR-009's digit-grouping requirement and leaves a documented discrepancy with `contracts/core-api.md`, which calls for removing spaces between digits. |
| FR-012–FR-013 (rates by date and up to 10 days of lookback) | ✅ | Unit tests and quickstart scenario 7 |
| FR-014 (saved-rate offer when the source is unreachable) | ⚠️ Correct behavior with technical error text | Quickstart scenarios 8–9 and section 4 |
| FR-015–FR-016 (caching and damaged-cache handling) | ✅ After review fixes for issues 5 and 10 | Unit tests and quickstart scenario 10 |
| FR-017–FR-019 (provenance, responsive loading and error handling) | ✅ | Quickstart and review |
| FR-020 (one-command unit tests) | ✅ `python -m pytest` — 218 passed | README |
| SC-001–SC-007 | ✅ SC-002 was checked indirectly with a timed test | Tests and quickstart |

The experiment demonstrated that an agent from another company could implement a working
application from the specification without manual code edits during initial implementation.
Briefly described edge cases still required review. For example, GUI behavior 2 said to clear
a selection that became unavailable. The agent substituted USD, and the initial contract checks
missed that case. Independent review found it. The Gemini claim that it found no discrepancies
and the GPT-OSS report of edits that did not exist illustrate why each run was verified against
the actual diff and test results.

## Git history

| Branch | Stage | PR |
|---|---|---|
| `001-currency-converter` | Spec Kit specification | #1 |
| `001-currency-converter-implementation` | Antigravity implementation | #2 |
| `001-currency-converter-tests` | Antigravity unit tests | #3 |
| `001-currency-converter-review-fixes` | Review fixes | #4 |
| `report` | Original lab report | #5 |
| `report-fix`, `report-wording` | Report clarifications | #6, #7 |

The specification was merged into `main` on 18 November at 23:30. The first code commit followed
at 23:39.

## 6. Interface follow-up

Feature 002 refreshes the Tkinter form and adds a local browser interface with a
responsive layout. Both interfaces use the existing Python rate service,
decimal conversion, validation, and cache. When a source request fails, the
browser shows a short explanation and keeps the diagnostic details in the log.
The browser offers the saved rate and displays its effective date before the
user decides whether to use it.

The feature specification was committed before the interface changes. The
constitution records the approved exception for reviewing the specification,
implementation, and browser tests as stacked pull requests.
