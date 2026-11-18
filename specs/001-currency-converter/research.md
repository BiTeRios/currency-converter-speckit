# Research: Currency Converter with Official BNM Rates

All findings below were verified on 2026-11-18 against the live source where marked.

## R1. Data source: BNM XML vs. a free exchange-rate API

- **Decision**: official BNM XML endpoint, Russian-language export
  `https://www.bnm.md/ru/official_exchange_rates?get_xml=1&date=DD.MM.YYYY` (same data as `/en/`,
  Russian currency names to match the Russian interface; switched after analysis pass 1, F3).
- **Rationale**: it is the legally official rate in Moldova (the users' country); no API key, no
  registration, no rate limit documented; per-date requests make the "weekends and holidays"
  requirement natural; XML parsing is a meaningful unit-test target.
- **Alternatives considered**: free JSON APIs (Frankfurter/ECB, exchangerate.host, open.er-api):
  simpler JSON, but most do not publish MDL or need a key, and their rates are not the official
  Moldovan ones; HTML scraping of bnm.md pages: fragile compared with the XML export.

## R2. Behaviour of the source (verified live)

| Request date | Result |
|---|---|
| 13.11.2026 (Friday) | HTTP 200, `ValCurs Date="13.11.2026"`, 40 currencies |
| 14.11.2026, 15.11.2026 (weekend) | HTTP 200, same values as 13.11, `Date` = requested date |
| 18.11.2026 (today) | HTTP 200, today's rates |
| 19.11.2026 (tomorrow) | HTTP 200 — published the day before, after ~13:00 |
| 20.11.2026, 25.12.2030 (future) | HTTP 404, empty body |
| 01.01.1990 (too old) | HTTP 404, empty body |

- **Decision**: treat HTTP 404, an empty body, and a `ValCurs` with no valid `Valute` all as
  "no rates for this date" → fallback to earlier days (FR-013). Treat network errors, timeouts and
  HTTP 5xx as "source unreachable" (FR-014). Treat unparsable XML or a wrong root element as
  "invalid response" (FR-014).
- Date range accepted by validation: 01.01.2000 … tomorrow (FR-011).

## R3. Response format and nominal

- Root `<ValCurs Date="DD.MM.YYYY" name="Official exchange rate">`, children
  `<Valute ID="..."><NumCode/><CharCode/><Nominal/><Name/><Value/></Valute>`.
- `Value` is the price in MDL of `Nominal` units, decimal point `.` (e.g. JPY: Nominal 100,
  Value 11.5165). Rate per one unit = Value / Nominal.
- **Decision**: skip a `Valute` whose `CharCode` is not three letters, or whose `Nominal`/`Value`
  are missing, non-numeric or ≤ 0; keep the rest. A real sample is stored in
  `contracts/bnm-sample-2026-11-18.xml`.

## R4. Money arithmetic and rounding

- **Decision**: `decimal.Decimal` from string inputs, default context (28 digits), results
  quantized with `ROUND_HALF_UP`: amount to `0.01`, rates to `0.0001`.
- **Rationale**: constitution principle III; floats give results like `0.1 + 0.2 ≠ 0.3`.
- **Round trip**: rounding the displayed result to 0.01 of the target currency makes the error of
  a back conversion up to `0.005 × price(target)/price(source)` plus 0.01 of the original
  currency's rounding — this is the tolerance written into FR-007.

## R5. Cache location and format

- **Decision**: JSON, path resolved in order: environment variable `CURRENCY_CONVERTER_HOME`
  (directory; an empty value counts as unset) → Windows `%APPDATA%\CurrencyConverter` → `$XDG_DATA_HOME/currency-converter` →
  `~/.local/share/currency-converter`; file name `rates_cache.json`. Decimals stored as strings.
  Written atomically (temporary file in the same directory + `os.replace`).
- **Rationale**: survives restarts, readable by humans, standard library only; the env variable
  lets tests and manual checks isolate the cache.
- **Alternatives considered**: SQLite (overkill for one table), pickle (unsafe, not readable),
  file next to the program (not writable when installed in Program Files).

## R6. Keeping the GUI responsive

- **Decision**: `threading.Thread(daemon=True)` runs `RateService.load`; it puts a
  `LoadResult` or an exception into a `queue.Queue`; the GUI polls the queue with
  `root.after(100, ...)`. Worker threads never touch widgets (Tk is not thread-safe).
- **Alternatives considered**: `asyncio` with Tk (no standard integration), blocking calls with
  `update()` (freezes on timeouts).

## R7. Offline demonstration hook

- **Decision**: environment variable `CURRENCY_CONVERTER_SOURCE_URL` overrides the base URL
  (default `https://www.bnm.md/ru/official_exchange_rates`). Setting it to
  `http://127.0.0.1:9/` makes every request fail like a dead network, which allows a repeatable
  "no network" demo without touching system settings. Airplane mode works as well.

## R8. Testing approach

- **Decision**: pytest; the fetcher passed to `RateService` is a plain function, so tests use
  dictionaries `{date: bytes | None | Exception}`; `fetch_xml` is tested by monkeypatching
  `urllib.request.urlopen`. The cache is tested in `tmp_path`. No test touches the network.
