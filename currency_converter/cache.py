"""Local cache for exchange rates."""

import json
import logging
import os
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from currency_converter.models import CurrencyRate, RateTable

logger = logging.getLogger(__name__)

CACHE_FILE_NAME = "rates_cache.json"
CACHE_HOME_ENV = "CURRENCY_CONVERTER_HOME"


def default_cache_path() -> Path:
    """Resolve default cache file path following research.md R5."""
    env_home = os.environ.get(CACHE_HOME_ENV)
    if env_home and env_home.strip():
        return Path(env_home.strip()) / CACHE_FILE_NAME

    appdata = os.environ.get("APPDATA")
    if appdata and appdata.strip():
        return Path(appdata.strip()) / "CurrencyConverter" / CACHE_FILE_NAME

    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data and xdg_data.strip():
        return Path(xdg_data.strip()) / "currency-converter" / CACHE_FILE_NAME

    return Path.home() / ".local" / "share" / "currency-converter" / CACHE_FILE_NAME


class RateCache:
    """Persistent storage for the last successful rate table."""

    def __init__(self, path: Path | str | None = None) -> None:
        if path is None:
            self.path = default_cache_path()
        else:
            self.path = Path(path)
        self.last_error: str | None = None

    def load(self) -> RateTable | None:
        """Load and parse saved rate table. Never raises; returns None on failure or missing file."""
        self.last_error = None
        if not self.path.is_file():
            return None

        try:
            content = self.path.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError("JSON root must be an object")

            if data.get("version") != 1:
                raise ValueError(f"unsupported version: {data.get('version')}")

            required_keys = ("source", "requested_date", "rates_date", "fetched_at", "rates")
            for key in required_keys:
                if key not in data:
                    raise ValueError(f"missing key: '{key}'")

            source = data["source"]
            if not isinstance(source, str):
                raise ValueError("source must be a string")

            requested_date_str = data["requested_date"]
            if not isinstance(requested_date_str, str):
                raise ValueError("requested_date must be a string")
            requested_date = date.fromisoformat(requested_date_str)

            rates_date_str = data["rates_date"]
            if not isinstance(rates_date_str, str):
                raise ValueError("rates_date must be a string")
            rates_date = date.fromisoformat(rates_date_str)

            fetched_at_str = data["fetched_at"]
            if not isinstance(fetched_at_str, str):
                raise ValueError("fetched_at must be a string")
            fetched_at = datetime.fromisoformat(fetched_at_str)

            raw_rates = data["rates"]
            if not isinstance(raw_rates, list):
                raise ValueError("rates must be a list")

            rates: dict[str, CurrencyRate] = {}
            for item in raw_rates:
                if not isinstance(item, dict):
                    raise ValueError("rate item must be an object")
                for key in ("code", "name", "nominal", "value"):
                    if key not in item:
                        raise ValueError(f"missing rate key: '{key}'")

                code = item["code"]
                name = item["name"]
                nominal = item["nominal"]
                value_str = item["value"]

                if not isinstance(code, str) or len(code) != 3 or not code.isupper() or code == "MDL":
                    raise ValueError(f"invalid currency code: {code}")
                if not isinstance(name, str):
                    raise ValueError(f"invalid currency name: {name}")
                if not isinstance(nominal, int) or nominal < 1:
                    raise ValueError(f"invalid nominal: {nominal}")
                if not isinstance(value_str, str):
                    raise ValueError(f"value must be string: {value_str}")

                value = Decimal(value_str)
                if value <= 0:
                    raise ValueError(f"value must be positive: {value}")

                rates[code] = CurrencyRate(
                    code=code,
                    name=name,
                    nominal=nominal,
                    value=value,
                )

            return RateTable(
                rates_date=rates_date,
                requested_date=requested_date,
                source=source,
                fetched_at=fetched_at,
                rates=rates,
            )
        except Exception as e:
            logger.error("Ошибка чтения кэша: %s", e)
            self.last_error = (
                f"Сохранённый курс не удалось прочитать ({e}); "
                "он будет заменён при следующей загрузке."
            )
            return None

    def save(self, table: RateTable) -> None:
        """Atomically persist rate table to disk. Creates parent directories. May raise OSError."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "source": table.source,
            "requested_date": table.requested_date.isoformat(),
            "rates_date": table.rates_date.isoformat(),
            "fetched_at": table.fetched_at.isoformat(),
            "rates": [
                {
                    "code": rate.code,
                    "name": rate.name,
                    "nominal": rate.nominal,
                    "value": str(rate.value),
                }
                for rate in table.rates.values()
            ],
        }

        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix="rates_cache_",
                suffix=".tmp",
                delete=False,
            ) as f:
                temp_path = Path(f.name)
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.path)
        except Exception as e:
            logger.error("Ошибка записи кэша: %s", e)
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise


__all__ = [
    "CACHE_FILE_NAME",
    "CACHE_HOME_ENV",
    "default_cache_path",
    "RateCache",
]
