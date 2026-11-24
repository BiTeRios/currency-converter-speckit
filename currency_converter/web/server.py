"""Serve the browser interface and delegate all currency logic to the core."""

import json
import logging
from collections import OrderedDict
from collections.abc import Callable
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit
from uuid import uuid4

from currency_converter.converter import convert, currency_options
from currency_converter.errors import (
    InvalidResponseError,
    NoRatesError,
    SourceUnavailableError,
    ValidationError,
)
from currency_converter.formatting import (
    SAME_CURRENCY_NOTE,
    fallback_notice,
    format_date,
    rates_line,
    result_line,
    status_line,
)
from currency_converter.models import LoadResult
from currency_converter.rate_service import RateService
from currency_converter.validation import parse_amount, parse_rate_date

logger = logging.getLogger(__name__)
ASSETS = Path(__file__).with_name("static")
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
MAX_SNAPSHOTS = 64
MAX_REQUEST_BYTES = 4096


class WebConverter:
    def __init__(self, service: RateService, today: Callable[[], date]) -> None:
        self.service = service
        self.today = today
        self.snapshots: OrderedDict[str, LoadResult] = OrderedDict()
        self.snapshot_lock = Lock()
        self.cache_read_lock = Lock()

    def snapshot(self, rates: LoadResult, identifier: str = "") -> dict:
        if not identifier:
            identifier = uuid4().hex
            with self.snapshot_lock:
                self.snapshots[identifier] = rates
                if len(self.snapshots) > MAX_SNAPSHOTS:
                    self.snapshots.popitem(last=False)
        notice = fallback_notice(rates)
        if not notice and rates.table.rates_date != rates.table.requested_date:
            notice = f"Запрошенная дата: {format_date(rates.table.requested_date)}."
        return {
            "id": identifier,
            "requestedDate": format_date(rates.table.requested_date),
            "ratesDate": format_date(rates.table.rates_date),
            "status": rates.status.value,
            "statusText": status_line(rates),
            "notice": notice,
            "warning": rates.warning,
            "currencies": currency_options(rates.table),
        }

    def saved(self) -> dict:
        with self.cache_read_lock:
            result = self.service.load_saved()
            unreadable = self.service.cache.last_error is not None
        return {
            "saved": self.snapshot(result) if result else None,
            "cacheWarning": (
                "Сохранённый курс не удалось прочитать. "
                "Он будет заменён при следующей загрузке."
                if unreadable else ""
            ),
        }

    def load(self, payload: dict) -> dict:
        requested = parse_rate_date(field(payload, "date"), self.today())
        return {"snapshot": self.snapshot(self.service.load(requested))}

    def conversion(self, payload: dict) -> tuple[HTTPStatus, dict]:
        amount = parse_amount(field(payload, "amount"))
        requested = parse_rate_date(field(payload, "date"), self.today())
        from_code = field(payload, "fromCode")
        to_code = field(payload, "toCode")
        identifier = field(payload, "snapshotId")
        with self.snapshot_lock:
            rates = self.snapshots.get(identifier)
            if rates is not None:
                self.snapshots.move_to_end(identifier)

        if identifier and rates is None:
            return HTTPStatus.CONFLICT, {
                "error": "Курс устарел. Обновите курс и повторите конвертацию.",
                "retry": True,
            }
        if rates is None or rates.table.requested_date != requested:
            rates = self.service.load(requested)
            identifier = ""
        snapshot = self.snapshot(rates, identifier)

        try:
            result = convert(amount, from_code, to_code, rates.table)
        except ValidationError:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {
                "error": "Выберите валюту заново.",
                "snapshot": snapshot,
            }
        return HTTPStatus.OK, {
            "snapshot": snapshot,
            "result": result_line(result),
            "rates": rates_line(result),
            "note": SAME_CURRENCY_NOTE if result.same_currency else "",
        }


def field(payload: dict, name: str) -> str:
    value = payload.get(name, "")
    if not isinstance(value, str):
        raise ValidationError("Проверьте введённые данные.")
    return value


def create_server(
    service: RateService | None = None,
    today: Callable[[], date] = date.today,
    port: int = 8000,
) -> ThreadingHTTPServer:
    app = WebConverter(service if service is not None else RateService(), today)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if not self.allowed_host():
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            path = urlsplit(self.path).path
            if path == "/api/bootstrap":
                self.send_json(HTTPStatus.OK, {
                    "today": format_date(app.today()),
                    **app.saved(),
                })
            elif path in STATIC_ROUTES:
                filename, mime = STATIC_ROUTES[path]
                self.send_body(HTTPStatus.OK, (ASSETS / filename).read_bytes(), mime)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            origin = self.headers.get("Origin")
            if not self.allowed_host() or (
                origin and origin != f"http://{self.headers.get('Host')}"
            ):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            path = urlsplit(self.path).path
            if path not in ("/api/rates", "/api/convert"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                payload = self.read_json()
            except ValueError:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Некорректный запрос."})
                return
            try:
                if path == "/api/rates":
                    status, response = HTTPStatus.OK, app.load(payload)
                else:
                    status, response = app.conversion(payload)
            except ValidationError as error:
                status, response = HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)}
            except NoRatesError as error:
                status, response = HTTPStatus.NOT_FOUND, {"error": str(error)}
            except (SourceUnavailableError, InvalidResponseError) as error:
                logger.warning("Rate source: %s", error)
                message = (
                    "НБМ вернул некорректные данные."
                    if isinstance(error, InvalidResponseError)
                    else "Не удалось получить курс НБМ. Проверьте подключение."
                )
                status = HTTPStatus.SERVICE_UNAVAILABLE
                response = {"error": message, "retry": True, **app.saved()}
            except Exception:
                logger.exception("Unable to handle %s", path)
                status = HTTPStatus.INTERNAL_SERVER_ERROR
                response = {"error": "Не удалось завершить операцию. Попробуйте ещё раз."}
            self.send_json(status, response)

        def allowed_host(self) -> bool:
            port = self.server.server_port
            return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                raise ValueError("Body length")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Content type")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Expected an object")
            return body

        def send_json(self, status: HTTPStatus, data: dict) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_body(status, body, "application/json; charset=utf-8")

        def send_body(self, status: HTTPStatus, body: bytes, mime: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
