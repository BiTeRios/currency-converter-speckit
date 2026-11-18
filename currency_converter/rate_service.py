"""Rate service for loading and caching exchange rates."""

import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime, timedelta

from currency_converter.bnm_source import fetch_xml, parse_rates
from currency_converter.cache import RateCache
from currency_converter.errors import NoRatesError
from currency_converter.models import LoadResult, LoadStatus

logger = logging.getLogger(__name__)

MAX_LOOKBACK_DAYS = 10


class RateService:
    """Service to load and manage currency exchange rates."""

    def __init__(
        self,
        fetch: Callable[[date], bytes | None] = fetch_xml,
        cache: RateCache | None = None,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.fetch = fetch
        self.cache: RateCache = cache if cache is not None else RateCache()
        self.now = now

    def load(self, requested: date) -> LoadResult:
        """Load rates for requested date with fallback up to MAX_LOOKBACK_DAYS earlier.

        Makes at most 11 fetch calls (offset 0..10).
        SourceUnavailableError and InvalidResponseError propagate immediately without fallback.
        None or empty rates trigger next lookback day.
        Raises NoRatesError(requested, requested - 10 days) if no rates found.
        """
        for offset in range(MAX_LOOKBACK_DAYS + 1):
            day = requested - timedelta(days=offset)
            logger.info("Запрос курса на дату %s (смещение: %d дн.)", day, offset)

            xml = self.fetch(day)
            if xml is None:
                logger.info("Курс за %s отсутствует (нет данных от источника)", day)
                continue

            table = parse_rates(xml, day, self.now())
            if not table.rates:
                logger.info("Курс за %s отсутствует (список валют пуст)", day)
                continue

            if offset > 0:
                logger.info(
                    "Курс за запрошенную дату %s не опубликован; использован курс за %s",
                    requested,
                    day,
                )

            table = replace(table, requested_date=requested)

            warning: str | None = None
            try:
                self.cache.save(table)
            except OSError as e:
                logger.error("Ошибка сохранения курса в кэш: %s", e)
                warning = f"Курс получен, но не сохранён на диск: {e}"

            status = LoadStatus.LIVE if offset == 0 else LoadStatus.EARLIER_DATE
            return LoadResult(table=table, status=status, warning=warning)

        logger.info(
            "Нет опубликованного курса за %d дней до запрошенной даты %s",
            MAX_LOOKBACK_DAYS,
            requested,
        )
        raise NoRatesError(requested, requested - timedelta(days=MAX_LOOKBACK_DAYS))

    def load_saved(self) -> LoadResult | None:
        """Load rates from local cache wrapped as LoadResult with CACHED status."""
        table = self.cache.load()
        if table is None:
            return None
        return LoadResult(table=table, status=LoadStatus.CACHED)


__all__ = [
    "MAX_LOOKBACK_DAYS",
    "RateService",
]
