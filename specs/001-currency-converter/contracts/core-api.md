# Contract: core modules (GUI-free public API)

Package: `currency_converter`. None of these modules may import `tkinter`.
Tests (`tests/`) and the GUI (`gui.py`) use exactly these names. Types are described in
[../data-model.md](../data-model.md).

## `currency_converter/__init__.py`

```python
APP_TITLE = "Конвертер валют — официальный курс НБМ"
SOURCE_NAME = "Национальный банк Молдовы, bnm.md"
```

## `currency_converter/errors.py`

```python
class ConverterError(Exception): ...            # str(e) is a Russian user-facing message
class ValidationError(ConverterError): ...
class SourceUnavailableError(ConverterError): ...
class InvalidResponseError(ConverterError): ...
class NoRatesError(ConverterError):
    def __init__(self, requested_date: date, earliest_date: date): ...
    # message: "Нет опубликованного курса за период с {earliest:DD.MM.YYYY} по {requested:DD.MM.YYYY}."
```

`SourceUnavailableError` message: `"Нет связи с bnm.md: {detail}"`.
`InvalidResponseError` message: `"bnm.md вернул некорректные данные: {detail}"`.

## `currency_converter/models.py`

```python
@dataclass(frozen=True)
class CurrencyRate:
    code: str
    name: str
    nominal: int
    value: Decimal
    @property
    def per_unit(self) -> Decimal: ...           # value / nominal

MDL_RATE: CurrencyRate                            # ("MDL", "Молдавский лей", 1, Decimal("1"))

@dataclass(frozen=True)
class RateTable:
    rates_date: date
    requested_date: date
    source: str
    fetched_at: datetime
    rates: dict[str, CurrencyRate]               # without MDL
    def get(self, code: str) -> CurrencyRate: ...  # "MDL" → MDL_RATE; unknown → KeyError
    @property
    def codes(self) -> list[str]: ...             # ["MDL", *rates]

class LoadStatus(Enum):
    LIVE = "live"
    EARLIER_DATE = "earlier_date"
    CACHED = "cached"

@dataclass(frozen=True)
class LoadResult:
    table: RateTable
    status: LoadStatus

@dataclass(frozen=True)
class ConversionResult:
    amount: Decimal
    from_code: str
    to_code: str
    converted: Decimal
    rate: Decimal
    reverse_rate: Decimal
    same_currency: bool
```

## `currency_converter/bnm_source.py`

```python
DEFAULT_BASE_URL = "https://www.bnm.md/en/official_exchange_rates"
SOURCE_URL_ENV = "CURRENCY_CONVERTER_SOURCE_URL"
TIMEOUT_SECONDS = 10

def build_url(day: date, base_url: str | None = None) -> str
    # base_url None → env SOURCE_URL_ENV or DEFAULT_BASE_URL; returns f"{base}?get_xml=1&date=DD.MM.YYYY"

def fetch_xml(day: date, timeout: float = TIMEOUT_SECONDS) -> bytes | None
    # see bnm-source.md "Responses"; uses urllib.request.urlopen

def parse_rates(xml_bytes: bytes, requested_date: date, fetched_at: datetime | None = None) -> RateTable
    # see bnm-source.md "Parsing rules"; fetched_at None → datetime.now(); source = SOURCE_NAME
    # NOTE: `requested_date` here is the date sent to the source (used when @Date is missing);
    # RateService replaces requested_date in the returned table with the user's date.
```

## `currency_converter/cache.py`

```python
CACHE_FILE_NAME = "rates_cache.json"
CACHE_HOME_ENV = "CURRENCY_CONVERTER_HOME"

def default_cache_path() -> Path               # resolution order: research.md R5

class RateCache:
    def __init__(self, path: Path | None = None): ...   # None → default_cache_path()
    path: Path
    def load(self) -> RateTable | None: ...      # never raises; missing/corrupt → None
    def save(self, table: RateTable) -> None: ...  # atomic write; creates parent dirs; may raise OSError
```

## `currency_converter/rate_service.py`

```python
MAX_LOOKBACK_DAYS = 10

class RateService:
    def __init__(
        self,
        fetch: Callable[[date], bytes | None] = fetch_xml,
        cache: RateCache | None = None,
        now: Callable[[], datetime] = datetime.now,
    ): ...

    def load(self, requested: date) -> LoadResult:
        # for offset in 0..MAX_LOOKBACK_DAYS: day = requested - offset
        #   xml = fetch(day)                      # SourceUnavailableError propagates immediately
        #   if xml is None: continue
        #   table = parse_rates(xml, day, now())  # InvalidResponseError propagates immediately
        #   if not table.rates: continue
        #   table = replace(table, requested_date=requested)
        #   save to cache (OSError is logged and ignored)
        #   return LoadResult(table, LIVE if offset == 0 else EARLIER_DATE)
        # raise NoRatesError(requested, requested - timedelta(days=MAX_LOOKBACK_DAYS))

    def load_saved(self) -> LoadResult | None:
        # cache.load() wrapped as LoadResult(table, CACHED); None if no cache or nothing saved
```

## `currency_converter/converter.py`

```python
def convert(amount: Decimal, from_code: str, to_code: str, table: RateTable) -> ConversionResult
    # formula and rounding: data-model.md ConversionResult; unknown code → ValidationError("Выберите валюту из списка.")
    # same code → converted = amount (quantized 0.01), rate = reverse_rate = Decimal("1.0000"), same_currency=True

def currency_options(table: RateTable) -> list[tuple[str, str]]
    # [(code, f"{code} — {name}")], order: MDL, EUR, USD (if present), then the rest sorted by code
```

## `currency_converter/validation.py`

```python
MAX_AMOUNT = Decimal("1000000000000")
MIN_RATE_DATE = date(2000, 1, 1)

MSG_AMOUNT_EMPTY = "Введите сумму."
MSG_AMOUNT_NOT_NUMBER = "Введите число, например 150 или 99,95."
MSG_AMOUNT_NOT_POSITIVE = "Сумма должна быть больше нуля."
MSG_AMOUNT_TOO_PRECISE = "Не больше двух знаков после запятой."
MSG_AMOUNT_TOO_LARGE = "Сумма не должна превышать 1 000 000 000 000."
MSG_DATE_FORMAT = "Введите дату в формате ДД.ММ.ГГГГ, например 18.11.2026."
MSG_DATE_RANGE = "Дата должна быть не раньше 01.01.2000 и не позже {max_date}."  # max_date = tomorrow, DD.MM.YYYY

def parse_amount(text: str) -> Decimal
    # 1. strip; empty → MSG_AMOUNT_EMPTY
    # 2. remove spaces/NBSP between digits ("1 500" → "1500"); "," → "."
    # 3. must match ^-?\d+(\.\d+)?$ else MSG_AMOUNT_NOT_NUMBER  (rejects "abc", "1e5", "NaN", "--5", "1.2.3")
    # 4. value <= 0 → MSG_AMOUNT_NOT_POSITIVE; more than 2 fraction digits → MSG_AMOUNT_TOO_PRECISE;
    #    value > MAX_AMOUNT → MSG_AMOUNT_TOO_LARGE
    # raises ValidationError(message)

def parse_rate_date(text: str, today: date) -> date
    # strip; must match ^\d{1,2}\.\d{1,2}\.\d{4}$ and be a real date else MSG_DATE_FORMAT
    # outside MIN_RATE_DATE .. today + 1 day → MSG_DATE_RANGE; raises ValidationError
```

## `currency_converter/formatting.py`

```python
SAME_CURRENCY_NOTE = "Валюты совпадают — конвертация не требуется"

def format_amount(value: Decimal) -> str      # 2 decimals, "," separator, space thousands: "1 833,83"
def format_rate(value: Decimal) -> str        # 4 decimals, same separators: "18,3383"
def format_date(day: date) -> str             # "18.11.2026"
def result_line(r: ConversionResult) -> str   # "100,00 USD = 1 833,83 MDL"
def rates_line(r: ConversionResult) -> str    # "1 USD = 18,3383 MDL · 1 MDL = 0,0545 USD"
def status_line(result: LoadResult) -> str
    # "Источник: Национальный банк Молдовы, bnm.md · " + LoadStatus text from data-model.md
    # dates via format_date; fetched_at as "DD.MM.YYYY HH:MM"
def fallback_notice(result: LoadResult) -> str
    # EARLIER_DATE → "За {requested} официальный курс не опубликован, использован курс за {rates_date}"
    # otherwise ""
```

## Worked examples (rates of 18.11.2026)

| Input | Expected |
|---|---|
| `convert(100, "USD", "MDL")` | converted `1833.83`, rate `18.3383`, reverse `0.0545` |
| `convert(1833.83, "MDL", "USD")` | converted `100.00` |
| `convert(100, "EUR", "JPY")` | `100 × 20.1538 / (11.5165/100)` = `17499.93` |
| `convert(50, "EUR", "EUR")` | converted `50.00`, rate `1.0000`, `same_currency=True` |
| `parse_amount(" 1 500,50 ")` | `Decimal("1500.50")` |
| `parse_amount("12a")` | `ValidationError(MSG_AMOUNT_NOT_NUMBER)` |
| `parse_rate_date("31.02.2026", today)` | `ValidationError(MSG_DATE_FORMAT)` |
