"""Rate service for loading and caching exchange rates."""

import logging
from collections.abc import Callable
from datetime import date, datetime

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
        """Load rates for the requested date.

        Phase 3 (T012): offset 0 only; None or empty rates raises NoRatesError.
        """
        xml = self.fetch(requested)
        if xml is None:
            raise NoRatesError(requested, requested)

        table = parse_rates(xml, requested, self.now())
        if not table.rates:
            raise NoRatesError(requested, requested)

        warning: str | None = None
        try:
            self.cache.save(table)
        except OSError as e:
            logger.warning("Could not save rates to cache: %s", e)
            warning = f"Курс получен, но не сохранён на диск: {e}"

        return LoadResult(table=table, status=LoadStatus.LIVE, warning=warning)

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
