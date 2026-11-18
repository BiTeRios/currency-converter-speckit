"""Exceptions for the currency converter."""

from datetime import date


class ConverterError(Exception):
    """Base class for all converter exceptions. str(e) is a Russian user-facing message."""


class ValidationError(ConverterError):
    """Raised when user input (amount or date) fails validation."""


class SourceUnavailableError(ConverterError):
    """Raised when the external rate source cannot be reached."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"Нет связи с bnm.md: {detail}")


class InvalidResponseError(ConverterError):
    """Raised when the external source returns malformed or invalid data."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"bnm.md вернул некорректные данные: {detail}")


class NoRatesError(ConverterError):
    """Raised when no exchange rates were published for the requested period."""

    def __init__(self, requested_date: date, earliest_date: date) -> None:
        self.requested_date = requested_date
        self.earliest_date = earliest_date
        earliest_str = earliest_date.strftime("%d.%m.%Y")
        requested_str = requested_date.strftime("%d.%m.%Y")
        super().__init__(
            f"Нет опубликованного курса за период с {earliest_str} по {requested_str}."
        )


__all__ = [
    "ConverterError",
    "ValidationError",
    "SourceUnavailableError",
    "InvalidResponseError",
    "NoRatesError",
]
