from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from threading import Thread
from xml.etree import ElementTree

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from currency_converter.cache import RateCache
from currency_converter.errors import SourceUnavailableError
from currency_converter.rate_service import RateService
from currency_converter.web.server import create_server


TODAY = date(2026, 11, 18)
TODAY_TEXT = "18.11.2026"
LIVE_STATUS = f"курс на {TODAY_TEXT}"
XML_FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/bnm_2026-11-18.xml"


class RateSource:
    def __init__(self):
        self.responses = {TODAY: XML_FIXTURE.read_bytes()}
        self.calls = []
        self.offline = False

    def __call__(self, day):
        self.calls.append(day)
        if self.offline:
            raise SourceUnavailableError("offline fixture")
        return self.responses.get(day)


@pytest.fixture(scope="module")
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1200,850")
    with webdriver.Chrome(options=options) as driver:
        yield driver


@pytest.fixture
def source():
    return RateSource()


@pytest.fixture
def cache(tmp_path):
    return RateCache(tmp_path / "rates.json")


@pytest.fixture
def start_server(source, cache):
    @contextmanager
    def start():
        service = RateService(
            fetch=source, cache=RateCache(cache.path), now=lambda: datetime(2026, 11, 18, 12)
        )
        with create_server(service=service, today=lambda: TODAY, port=0) as server:
            thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
            thread.start()
            try:
                yield f"http://127.0.0.1:{server.server_port}"
            finally:
                server.shutdown()
                thread.join()

    return start


def control(browser, element_id):
    return browser.find_element(By.ID, element_id)


def enter(browser, element_id, value):
    field = control(browser, element_id)
    field.clear()
    field.send_keys(value)


def click(browser, element_id):
    WebDriverWait(browser, 5).until(EC.element_to_be_clickable((By.ID, element_id))).click()


def wait_for_text(browser, element_id, expected):
    WebDriverWait(browser, 5).until(EC.text_to_be_present_in_element((By.ID, element_id), expected))


@pytest.fixture
def live_page(browser, start_server):
    with start_server() as url:
        browser.get(url)
        wait_for_text(browser, "status", LIVE_STATUS)
        yield browser


def test_startup_loads_default_pair_and_requires_amount(live_page, source):
    assert source.calls == [TODAY]
    assert control(live_page, "date").get_property("value") == TODAY_TEXT
    assert control(live_page, "from").get_property("value") == "USD"
    assert control(live_page, "to").get_property("value") == "MDL"
    assert control(live_page, "swap").is_enabled()
    assert not control(live_page, "convert").is_enabled()
    assert not control(live_page, "result").is_displayed()

    enter(live_page, "amount", "   ")
    assert not control(live_page, "convert").is_enabled()
    enter(live_page, "amount", "100")
    assert control(live_page, "convert").is_enabled()
    Select(control(live_page, "from")).select_by_value("")
    assert control(live_page, "from").get_property("value") == ""
    assert not control(live_page, "convert").is_enabled()
    assert not control(live_page, "swap").is_enabled()


def test_enter_converts_swap_reverses_and_equal_currencies_keep_amount(live_page, source):
    enter(live_page, "amount", "100")
    control(live_page, "amount").send_keys(Keys.ENTER)
    wait_for_text(live_page, "result", "100,00 USD = 1 833,83 MDL")
    assert control(live_page, "rates").text == "1 USD = 18,3383 MDL · 1 MDL = 0,0545 USD"

    click(live_page, "swap")
    assert control(live_page, "from").get_property("value") == "MDL"
    assert control(live_page, "to").get_property("value") == "USD"
    assert not control(live_page, "result").is_displayed()
    click(live_page, "convert")
    wait_for_text(live_page, "result", "100,00 MDL = 5,45 USD")

    Select(control(live_page, "to")).select_by_value("MDL")
    assert not control(live_page, "result").is_displayed()
    click(live_page, "convert")
    wait_for_text(live_page, "result", "100,00 MDL = 100,00 MDL")
    wait_for_text(live_page, "selection-notice", "Валюты совпадают")
    assert source.calls == [TODAY]


def test_invalid_amount_and_date_do_not_fetch_rates(live_page, source):
    enter(live_page, "amount", "100.123")
    click(live_page, "convert")
    wait_for_text(live_page, "error", "Не больше двух знаков после запятой.")
    assert not control(live_page, "result").is_displayed()

    enter(live_page, "amount", "100")
    enter(live_page, "date", "31.02.2026")
    click(live_page, "convert")
    wait_for_text(live_page, "error", "Введите дату в формате ДД.ММ.ГГГГ")
    assert not control(live_page, "result").is_displayed()
    assert source.calls == [TODAY]

    click(live_page, "today")
    assert control(live_page, "date").get_property("value") == TODAY_TEXT
    click(live_page, "convert")
    wait_for_text(live_page, "result", "100,00 USD = 1 833,83 MDL")
    assert source.calls == [TODAY]


def test_earlier_publication_clears_a_currency_that_disappeared(live_page, source):
    requested = date(2026, 11, 17)
    effective = date(2026, 11, 16)
    earlier_xml = ElementTree.fromstring(source.responses[TODAY])
    earlier_xml.set("Date", "16.11.2026")
    earlier_xml.remove(next(rate for rate in earlier_xml if rate.findtext("CharCode") == "EUR"))
    source.responses[effective] = ElementTree.tostring(earlier_xml, encoding="utf-8")

    enter(live_page, "amount", "100")
    Select(control(live_page, "from")).select_by_value("EUR")
    click(live_page, "convert")
    wait_for_text(live_page, "result", "100,00 EUR = 2 015,38 MDL")

    enter(live_page, "date", "17.11.2026")
    click(live_page, "refresh")
    wait_for_text(live_page, "status", "курс на 16.11.2026")
    wait_for_text(live_page, "rate-notice", "За 17.11.2026 официальный курс не опубликован")
    wait_for_text(live_page, "selection-notice", "Выберите валюту заново")
    assert control(live_page, "from").get_property("value") == ""
    assert control(live_page, "to").get_property("value") == "MDL"
    assert not control(live_page, "convert").is_enabled()
    assert not control(live_page, "result").is_displayed()
    assert source.calls == [TODAY, requested, effective]


def test_saved_rates_require_opt_in_after_server_restart(browser, start_server, source, cache):
    with start_server() as url:
        browser.get(url)
        wait_for_text(browser, "status", LIVE_STATUS)
        assert cache.path.is_file()

    source.offline = True
    with start_server() as url:
        browser.get(url)
        wait_for_text(browser, "use-saved", f"Использовать сохранённый курс от {TODAY_TEXT}")
        assert control(browser, "status").text == "Курс ещё не загружен."
        assert not control(browser, "result").is_displayed()

        enter(browser, "amount", "100")
        click(browser, "convert")
        wait_for_text(browser, "error", "Не удалось получить курс НБМ")
        assert not control(browser, "result").is_displayed()
        assert source.calls == [TODAY, TODAY, TODAY]

        click(browser, "use-saved")
        wait_for_text(browser, "status", f"сохранённый курс на {TODAY_TEXT} (офлайн")
        assert not control(browser, "problem").is_displayed()
        click(browser, "convert")
        wait_for_text(browser, "result", "100,00 USD = 1 833,83 MDL")
        assert source.calls == [TODAY, TODAY, TODAY]


@pytest.mark.parametrize("damaged", [False, True], ids=["missing-cache", "damaged-cache"])
def test_retry_recovers_without_a_readable_cache(browser, start_server, source, cache, damaged):
    if damaged:
        cache.path.write_text("invalid JSON", encoding="utf-8")
    source.offline = True

    with start_server() as url:
        browser.get(url)
        wait_for_text(browser, "error", "Сохранённых курсов нет.")
        assert control(browser, "cache-notice").is_displayed() == damaged
        assert not control(browser, "use-saved").is_displayed()
        assert not control(browser, "from").is_enabled()
        assert not control(browser, "convert").is_enabled()

        source.offline = False
        click(browser, "retry")
        wait_for_text(browser, "status", LIVE_STATUS)
        assert not control(browser, "problem").is_displayed()
        assert not control(browser, "cache-notice").is_displayed()
        assert cache.load().rates_date == TODAY
        assert source.calls == [TODAY, TODAY]


def test_narrow_viewport_stacks_cards_without_horizontal_overflow(live_page):
    live_page.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
    )
    try:
        WebDriverWait(live_page, 5).until(
            lambda driver: driver.execute_script("return window.innerWidth") == 390
        )
        layout = live_page.execute_script(
            """
            const form = document.querySelector('#converter').closest('section').getBoundingClientRect();
            const result = document.querySelector('.result-card').getBoundingClientRect();
            return {
                stacked: result.top >= form.bottom,
                fits: document.documentElement.scrollWidth <= window.innerWidth,
            };
            """
        )
        assert layout == {"stacked": True, "fits": True}
    finally:
        live_page.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
