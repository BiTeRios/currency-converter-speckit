# Feature Specification: Currency Converter with Official BNM Rates

**Feature Branch**: `001-currency-converter`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "Desktop currency converter with a graphical interface (a console app is
not acceptable). Data source: official exchange rates of the National Bank of Moldova. The window
has an amount field, a source currency selector, a target currency selector, a convert button that
stays disabled until the required fields are filled, the conversion result, and the date and source
of the rates. Mandatory behaviour: no network → no crash, a clear message and an offer to use the
last successfully fetched rates with their date; weekends and holidays → if the source publishes
nothing for the chosen date, take the last available rates and say so explicitly; invalid input
(negative, zero, letters, empty) → an error and no conversion; the same currency on both sides is
handled without error; the last successful response is cached locally and survives a restart.
Conversion must work in both directions. Unit tests cover parsing of the source response,
conversion (including the reverse direction), empty or invalid source responses, and input
validation; tests run with one command described in the README."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Convert an amount at today's official rate (Priority: P1)

A user opens the converter, types an amount, picks the currency they have and the currency they
want, presses "Convert" and sees the converted amount together with the exchange rate, the date the
rate applies to and the name of the source. With one click they can swap the two currencies to
convert in the opposite direction.

**Why this priority**: this is the whole purpose of the application; everything else protects
this flow.

**Independent Test**: start the application with network access, enter `100`, choose USD → MDL,
press "Convert": a result, the USD/MDL rate, today's rate date and "National Bank of Moldova"
are shown. Swap the currencies and convert the result back: the original amount is returned
(±0.01).

**Acceptance Scenarios**:

1. **Given** rates for today are loaded, **When** the user enters `100`, selects USD as source and
   MDL as target and presses "Convert", **Then** the result equals 100 × the official USD rate,
   rounded to 2 decimal places, and the rate date and source are displayed next to it.
2. **Given** a conversion USD → MDL was shown, **When** the user presses "Swap" and converts the
   shown MDL amount, **Then** the result is the original USD amount within ±0.01.
3. **Given** rates are loaded, **When** the user converts between two foreign currencies
   (e.g. EUR → JPY), **Then** the result is computed through MDL and respects the source's
   nominal (JPY is quoted per 100 units).
4. **Given** rates are loaded, **When** the user selects the same currency on both sides and
   presses "Convert", **Then** no error occurs, the result equals the entered amount and a note
   says that no conversion was needed.
5. **Given** the amount field is empty or a currency is not selected, **Then** the "Convert"
   button is disabled; it becomes enabled as soon as all required fields are filled.

---

### User Story 2 - Invalid input is rejected with a clear message (Priority: P1)

A user mistypes the amount (letters, a negative number, zero, an empty field). The application
explains what is wrong and does not show a conversion result.

**Why this priority**: a wrong number presented as a correct conversion is worse than no number.

**Independent Test**: for each invalid input from the list below, press "Convert" (or try to)
and check that an error message appears, no result is shown and the application keeps running.

**Acceptance Scenarios**:

1. **Given** the amount is `abc`, `12a`, `1e5`, `NaN` or `--5`, **When** the user presses
   "Convert", **Then** the message "Введите число, например 150 или 99,95" is shown and no result
   is displayed.
2. **Given** the amount is `0` or `-10`, **When** the user presses "Convert", **Then** a message
   says the amount must be greater than zero and no result is displayed.
3. **Given** the amount has more than 2 decimal places or exceeds 1 000 000 000 000, **When** the
   user presses "Convert", **Then** a message names the limit and no result is displayed.
4. **Given** the amount is ` 1 500,50 ` (spaces, comma), **When** the user presses "Convert",
   **Then** it is accepted as 1500.50.
5. **Given** an error message is shown, **When** the user corrects the amount and converts,
   **Then** the message disappears and the result is shown.

---

### User Story 3 - Work offline with the last saved rates (Priority: P2)

A user starts the converter without internet access (or the source is down). The application
does not crash; it tells the user that fresh rates could not be loaded and offers to use the last
successfully loaded rates, showing their date. Saved rates survive closing and reopening the
application.

**Why this priority**: required behaviour; the application must stay useful when the network
is unavailable.

**Independent Test**: run the application once online (rates are saved), close it, disable the
network, start it again: a message about the missing connection appears together with an offer
to use the saved rates dated D; after accepting, conversions work and are labelled as saved
offline rates of date D.

**Acceptance Scenarios**:

1. **Given** there is no network and saved rates from date D exist, **When** the application
   starts or the user requests rates, **Then** a message explains that the source is unreachable
   and offers "Use saved rates from D".
2. **Given** the user accepted the offer, **When** they convert, **Then** the result is computed
   from the saved rates and labelled "saved rates, D (offline)".
3. **Given** there is no network and no saved rates, **When** the application starts, **Then** a
   message explains that rates are unavailable and how to retry; the window stays open and the
   "Convert" button stays disabled.
4. **Given** rates were loaded successfully, **When** the application is closed and reopened,
   **Then** the saved rates (with their date) are still available.
5. **Given** the saved-rates file is damaged, **When** the application starts, **Then** it starts
   normally as if no rates were saved.

---

### User Story 4 - Rates for a chosen date, including days without publication (Priority: P3)

A user wants to convert at the official rate of a particular past date. If the source has not
published rates for that date, the application uses the most recent earlier date that has rates
and says so explicitly.

**Why this priority**: required behaviour for weekends and holidays; less frequent than
converting at today's rate.

**Independent Test**: with a simulated source that returns no rates for date D but has rates for
D − 2, convert at date D: the result shows D − 2 as the rate date and a notice that D had no
published rates. In the live application, choosing a past date shows that date's official rate.

**Acceptance Scenarios**:

1. **Given** the user enters a valid date D in `DD.MM.YYYY` format, **When** they convert,
   **Then** rates for D are loaded and the result shows D as the rate date.
2. **Given** the source returns no rates for D, **When** the user converts, **Then** the
   application uses the closest earlier date D' (looking back at most 10 days) and shows
   "За D официальный курс не опубликован, использован курс за D'".
3. **Given** the source returns no rates for D and for the 10 previous days, **When** the user
   converts, **Then** a message says no rates were found for that period and no result is shown.
4. **Given** the user enters an impossible date (`31.02.2026`), a date in the wrong format, a date
   before 01.01.2000 or later than tomorrow, **When** they convert, **Then** a message explains the
   accepted format and range and no request is made.
5. **Given** a date other than today is selected, **When** the user presses "Today",
   **Then** the date field is reset to today's date.

---

### Edge Cases

- The source answers with HTTP 404 or an empty body for dates without publication (future dates,
  very old dates): treated as "no rates for this date", never as a crash.
- The source answers with malformed XML, XML without currencies, or a currency whose value or
  nominal is missing, non-numeric, zero or negative: malformed currencies are skipped; if nothing
  valid remains the response counts as empty; malformed XML counts as an invalid response.
- The request times out or DNS fails: treated as "source unreachable" (User Story 3).
- Weekends and public holidays: the source returns the rates valid on that day (carried forward
  from the last working day); they are shown with the requested date as the source labels them.
- A currency selected before a reload disappears from the new rate table: the selection is cleared
  and the user is asked to choose again.
- The user presses "Convert" repeatedly while rates are loading: only one load runs at a time.
- Very large and very small amounts: up to 1 000 000 000 000 and at least 0.01.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST be a desktop application with a graphical window; all
  interaction happens in that window. Interface language: Russian.
- **FR-002**: The window MUST contain: an amount field, a source currency selector, a target
  currency selector, a "Swap" button, a rate date field with a "Today" button, a "Convert" button,
  a "Refresh rates" button, a result area and a rate information area.
- **FR-003**: Currency selectors MUST list Moldovan leu (MDL) plus every currency present in the
  currently loaded rate table, each shown as `CODE — name`, sorted with MDL, EUR, USD first and the
  rest alphabetically by code. Default selection: USD → MDL.
- **FR-004**: The "Convert" button MUST be disabled while the amount field is empty (after trimming
  spaces), while either currency is not selected, while no rate table is available, or while rates
  are loading; otherwise it MUST be enabled.
- **FR-005**: Conversion MUST compute `amount × (value_from / nominal_from) ÷ (value_to / nominal_to)`
  where `value` is the official MDL price of `nominal` units of the currency and MDL itself has
  value 1 and nominal 1. All arithmetic MUST be exact decimal arithmetic.
- **FR-006**: The result area MUST show the converted amount rounded half-up to 2 decimal places,
  the direct rate `1 FROM = X TO` and the reverse rate `1 TO = Y FROM`, each with 4 decimal places.
- **FR-007**: The "Swap" button MUST exchange the source and target currencies. Converting the
  displayed result back MUST return the original amount within the rounding tolerance of the
  displayed result: `|back − amount| ≤ 0.01 + 0.005 × price(target) / price(source)`, where price
  is the MDL value of one unit. For MDL, EUR and USD pairs this is within ±0.01.
- **FR-008**: Selecting the same currency on both sides MUST NOT be an error: the result equals the
  amount, the rate is 1 and the note "Валюты совпадают — конвертация не требуется" is shown.
- **FR-009**: The amount MUST be validated before conversion. Accepted: digits with at most one
  decimal separator (`.` or `,`), at most 2 digits after it, surrounding spaces and spaces between
  digit groups. Rejected with a specific message: empty field, any other character (letters,
  exponent notation, `NaN`, `inf`, signs other than a single leading `-`), zero, negative values,
  more than 2 decimal places, values above 1 000 000 000 000.
- **FR-010**: On a validation error the application MUST show the message next to the input, MUST
  NOT perform the conversion and MUST clear any previous result.
- **FR-011**: The rate date field MUST default to today and accept `DD.MM.YYYY`. Dates that do not
  exist, are before 01.01.2000 or after tomorrow MUST be rejected with a message before any request.
- **FR-012**: Rates MUST be loaded from the official National Bank of Moldova publication for the
  selected date: automatically for today at start-up, when "Refresh rates" is pressed, and when
  "Convert" is pressed while the loaded table belongs to a different requested date.
- **FR-013**: When the source returns no rates for the requested date, the application MUST try the
  previous calendar days one by one, at most 10 days back, use the first date that has rates and
  show "За {D} официальный курс не опубликован, использован курс за {D'}". If none is found it MUST
  show that no rates exist for that period and not convert.
- **FR-014**: When the source is unreachable (no network, timeout, DNS failure, HTTP 5xx) or returns
  an invalid response, the application MUST show a plain-language message and, if saved rates
  exist, offer an action "Использовать сохранённый курс от {date}". Accepting it makes the saved
  table the active one.
- **FR-015**: Every successfully loaded rate table MUST be saved locally (rates, rate date,
  requested date, source name, time of download) replacing the previous one, and MUST be loaded
  from disk at start-up before any network request, so it survives restarts.
- **FR-016**: An unreadable or damaged saved-rates file MUST be ignored without crashing; the next
  successful load overwrites it.
- **FR-017**: The rate information area MUST always show the source name
  ("Национальный банк Молдовы, bnm.md"), the date of the active rates and their status:
  live, earlier date used (FR-013) or saved offline (FR-014).
- **FR-018**: Loading rates MUST NOT freeze the window; while loading, a "Загрузка курса…"
  indicator is shown and "Convert"/"Refresh rates" are disabled. Each network request MUST time
  out after at most 10 seconds.
- **FR-019**: The application MUST NOT terminate because of an unhandled error; unexpected errors
  are shown as a message and the window stays usable.
- **FR-020**: Unit tests MUST cover: parsing of the source response (valid, empty, malformed,
  nominal ≠ 1), conversion in both directions including cross rates and same currency, behaviour on
  empty or invalid source responses including the date fallback, and amount and date validation.
  All tests MUST run with one command documented in `README.md` and MUST NOT require network access.

### Key Entities *(include if feature involves data)*

- **Currency rate**: currency code (ISO 4217, e.g. USD), name, nominal (units the price refers to,
  e.g. 100 for JPY), value (price of `nominal` units in MDL).
- **Rate table**: the set of currency rates for one date, plus the requested date, the date the
  rates belong to, the source name and the time it was downloaded.
- **Conversion request**: amount, source currency, target currency, requested rate date.
- **Conversion result**: converted amount, direct and reverse rate, the rate table used and its
  status (live / earlier date / saved offline), optional note (same currency, fallback date).
- **Saved rates**: the last successfully loaded rate table persisted on disk.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With network access, a user converts an amount at today's rate within 10 seconds of
  starting the application, in no more than 4 actions (type amount, choose two currencies, press
  "Convert").
- **SC-002**: When rates are already loaded, the result appears in under 0.5 seconds after
  pressing "Convert".
- **SC-003**: For every currency pair in a real rate table, converting an amount and then
  converting the result back stays within the tolerance of FR-007; for pairs of MDL, EUR and USD
  the difference is at most ±0.01.
- **SC-004**: 100% of the invalid inputs listed in FR-009 and FR-011 produce an error message and
  no result.
- **SC-005**: With the network disabled, the application starts, shows a message and converts
  using saved rates in 100% of attempts where rates had been saved before; zero crashes.
- **SC-006**: 100% of displayed results show the rate date and the data source.
- **SC-007**: The full unit test suite passes with a single documented command without network
  access.

## Assumptions

- Target users are in Moldova; the leu (MDL) is the base currency of all official rates.
- The source publishes rates on working days, usually by 13:00 Chisinau time; those rates apply to
  the next day. For weekends and holidays the source returns the rates in force on that day
  (carried forward). Dates with no publication (later than the next day, very old dates) return no
  data. This was checked against the live source on 2026-11-18.
- Only the most recent successful rate table is saved; a history of rates is out of scope.
- Single user, single window; Windows is the primary platform, other platforms with Python and Tk
  should also work.
- The official rate is used for both directions (no buy/sell spread).
