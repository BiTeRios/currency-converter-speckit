"""Data models for currency conversion and exchange rates."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


@dataclass(frozen=True)
class CurrencyRate:
    code: str
    name: str
    nominal: int
    value: Decimal

    @property
    def per_unit(self) -> Decimal:
        return self.value / Decimal(self.nominal)


MDL_RATE = CurrencyRate(
    code="MDL",
    name="Молдавский лей",
    nominal=1,
    value=Decimal("1"),
)


@dataclass(frozen=True)
class RateTable:
    rates_date: date
    requested_date: date
    source: str
    fetched_at: datetime
    rates: dict[str, CurrencyRate]

    def get(self, code: str) -> CurrencyRate:
        if code == "MDL":
            return MDL_RATE
        if code in self.rates:
            return self.rates[code]
        raise KeyError(code)

    @property
    def codes(self) -> list[str]:
        return ["MDL", *self.rates]


class LoadStatus(Enum):
    LIVE = "live"
    EARLIER_DATE = "earlier_date"
    CACHED = "cached"


@dataclass(frozen=True)
class LoadResult:
    table: RateTable
    status: LoadStatus
    warning: str | None = None


@dataclass(frozen=True)
class ConversionResult:
    amount: Decimal
    from_code: str
    to_code: str
    converted: Decimal
    rate: Decimal
    reverse_rate: Decimal
    same_currency: bool


__all__ = [
    "CurrencyRate",
    "MDL_RATE",
    "RateTable",
    "LoadStatus",
    "LoadResult",
    "ConversionResult",
]
