# Implementation plan

Continue to run Tkinter with `python -m currency_converter`. Add
`python -m currency_converter.web` with a standard-library HTTP server and bundled
HTML, CSS, and JavaScript.

The browser loads date and saved-rate information at startup, then requests live
rates. The server returns currency choices and provenance with each snapshot.
Tabs track their own selections and which snapshot is active. The server keeps a
bounded in-memory set of snapshots and uses the existing JSON cache across restarts.
Conversion sends an amount, requested date, currency codes, and active snapshot
identifier. The server validates the input before fetching a different date and
computes the result through the existing conversion function.

Use the existing date lookback, formatters, and cache environment settings.
Keep the local server on loopback and return user-facing errors for invalid
input or unavailable data. Selenium uses headless Chrome with an ephemeral port,
a fixed clock, fixture XML, and a temporary cache.
