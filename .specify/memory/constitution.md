# Currency Converter Constitution

## Core Principles

### I. Specification Is the Source of Truth

- Every behaviour of the application MUST trace back to a functional requirement (`FR-xxx`)
  or success criterion (`SC-xxx`) in `specs/`.
- The implementing agent MUST NOT add features that are not in the specification and MUST NOT
  silently drop required ones.
- Any deviation between the specification and the delivered code, and every place where a human
  had to change agent-generated code, MUST be recorded in `REPORT.md`.

Rationale: the project exists to prove that a specification written for one agent can be
executed by another agent without hidden knowledge.

### II. Never Crash, Always Explain

- No user action and no state of the network or data source may terminate the application
  with an unhandled exception.
- Every failure (no network, source unavailable, empty or malformed response, invalid input,
  unreadable cache) MUST produce a plain-language message in the GUI that says what happened
  and what the user can do.
- When live data is unavailable the application MUST offer the last successfully fetched rates,
  clearly labelled with their date.

Rationale: a converter that dies when Wi-Fi drops is useless; the user must always know whether
the numbers in front of them are current.

### III. Honest Data Provenance

- Every displayed conversion result MUST be accompanied by the date the rates apply to and the
  name of the data source.
- Data from the cache or from an earlier date than requested MUST be explicitly marked as such.
- Money arithmetic MUST use `decimal.Decimal`, never binary floating point.

Rationale: an exchange rate without a date is not information; rounding errors in money are bugs.

### IV. Testable Core, Thin GUI

- Parsing, conversion, input validation, date fallback and caching MUST live in modules that
  do not import the GUI toolkit, so they can be unit-tested without a display.
- The GUI layer only wires widgets to the core and renders its results.
- The data source MUST be injectable (a fetch function or client object) so tests never touch
  the real network.
- All unit tests MUST run locally with one command documented in `README.md`.

Rationale: the core is where the bugs that matter live; it must be cheap to test exhaustively.

### V. Simplicity and Minimal Dependencies

- Runtime code uses the Python standard library only (`tkinter`, `urllib`, `xml.etree`, `json`,
  `decimal`, `datetime`, `pathlib`). `pytest` is the only development dependency.
- No speculative abstractions: one data source, one GUI, one cache file.

Rationale: fewer moving parts means fewer ways for a code-generating agent to go wrong and an
application that runs on any machine with Python installed.

## Technology and Data Constraints

- Language and runtime: Python 3.11 or newer; desktop GUI built with Tkinter/ttk.
  A console-only application is not acceptable.
- Data source: official exchange rates of the National Bank of Moldova (BNM), XML endpoint
  `https://www.bnm.md/en/official_exchange_rates?get_xml=1&date=DD.MM.YYYY`.
  Rates are quoted in Moldovan lei (MDL) per `Nominal` units of the foreign currency.
- Network calls MUST use a timeout (10 seconds or less) and MUST NOT block the GUI thread.
- The cache is a single JSON file in the user's application-data directory; it MUST survive
  application restarts and a corrupted cache MUST be ignored rather than crash the app.
- No API keys, secrets or personal data are stored or transmitted.

## Development Workflow

- Work is split into stages, each on its own Git branch: specification, implementation, tests.
  Branches are merged into `main` only through GitHub Pull Requests, never by direct push.
- Specification artifacts (`constitution.md`, `spec.md`, `plan.md`, `tasks.md` and supporting
  documents) MUST be committed and merged before any implementation code is written.
- Implementation is performed by a coding agent (Google Antigravity) from `tasks.md`.
  Human or other-agent edits to that code are allowed but MUST be listed in `REPORT.md`.
- Commit messages describe the change itself; a single "everything done" commit is not acceptable.
- The implementation stage is complete when the application starts and the quickstart scenarios
  pass. From the tests stage on, a stage is complete only when `python -m pytest` passes.

## Governance

- This constitution overrides any conflicting instruction in other project documents.
- Amendments are made by editing this file in a dedicated commit that states what changed and why,
  with the version bumped by semantic versioning: MAJOR for removed or redefined principles,
  MINOR for new principles or sections, PATCH for wording fixes.
- Every Pull Request is reviewed against the Core Principles; a violation must either be fixed or
  justified in the plan's Complexity Tracking section.

**Version**: 1.1.0 | **Ratified**: 2026-11-18 | **Last Amended**: 2026-11-18
