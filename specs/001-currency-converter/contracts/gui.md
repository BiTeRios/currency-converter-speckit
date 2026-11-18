# Contract: main window (`currency_converter/gui.py`)

Tkinter + ttk, one `Tk` root, title `APP_TITLE`, minimum size 560×460, resizable.
Entry point: `def main() -> None` (creates the root, `ConverterApp(root)`, `root.mainloop()`).
`ConverterApp.__init__(self, root, service: RateService | None = None, today: Callable[[], date] = date.today)`
— the service and clock are injectable.

## Layout (top to bottom, labels in Russian)

| Row | Widgets |
|---|---|
| 1 | `Сумма:` — `ttk.Entry` (amount) |
| 2 | `Из валюты:` — readonly `ttk.Combobox` (source) · button `⇄ Поменять` |
| 3 | `В валюту:` — readonly `ttk.Combobox` (target) |
| 4 | `Дата курса:` — `ttk.Entry` (DD.MM.YYYY, default today) · button `Сегодня` |
| 5 | buttons `Конвертировать` (default button, also triggered by Enter) and `Обновить курс` |
| 6 | error label (red), empty when there is no error |
| 7 | result label, large bold font: `result_line(...)` |
| 8 | rates label: `rates_line(...)` |
| 9 | note label: `SAME_CURRENCY_NOTE` or `fallback_notice(...)` or selection hint |
| 10 | status line: `status_line(active)` or `Курс не загружен` |
| 11 | notification frame (hidden unless there is a load problem): message label, button `Использовать сохранённый курс от DD.MM.YYYY` (only if saved rates exist), button `Повторить` |
| 12 | loading label `Загрузка курса…` (visible only while loading) |

Combobox values come from `currency_options(table)` (display text), the code is the part before
` — `. Default selection: source `USD`, target `MDL`.

## Behaviour

1. **Start-up**: `service.load_saved()`; if present, fill the currency lists from it (it is *not*
   active yet); if it returned `None` and `service.cache.last_error` is set, show that text in the
   note label (non-blocking). Then start loading today's rates in a worker thread.
2. **Load success**: active = result; lists rebuilt (selections kept if the code still exists,
   otherwise cleared and the note says `Выберите валюту заново`); status line updated; notification
   hidden; `fallback_notice` shown in the note label when status is `EARLIER_DATE`;
   `result.warning`, if any, is appended to the note label.
3. **Load failure** (`SourceUnavailableError` / `InvalidResponseError`): notification shows
   `str(error)` plus, if saved rates exist and are not already active,
   `Можно продолжить с сохранённым курсом от {saved.table.rates_date}.` and the offer button
   (its text uses the same `rates_date`). Without saved
   rates: `Курс недоступен: нет связи с источником и нет сохранённых данных. Проверьте подключение
   и нажмите «Обновить курс».` Pending conversion is cancelled.
4. **`NoRatesError`**: error label shows `str(error)`; no conversion.
5. **Offer accepted**: active = saved result (status `CACHED`); the date field is set to
   `saved.table.requested_date`; notification hidden; status line shows the offline text.
6. **Convert** (button or Enter): clear error/result → `parse_amount` → `parse_rate_date`
   (errors go to the error label, FR-010) → if the active table exists and
   `active.table.requested_date == date` convert immediately, else start loading that date and
   convert when it succeeds.
7. **Refresh rates**: validate the date, then load it (even if it is the active date).
8. **Swap**: exchange the two selections; clear result, rates and note labels.
9. **Today**: set the date field to `format_date(today())`.
10. **Button state (FR-004)**, re-evaluated on every change of the amount text, selections,
    currency lists and loading flag: `Конвертировать` is enabled iff the amount text is non-blank,
    both currencies are selected and nothing is loading (the lists are filled from the live or the
    saved table, so with no rates at all nothing is selectable). The Enter binding calls the same
    handler, which returns immediately when the button is disabled. `Обновить курс` is disabled
    while loading.
11. **Threading**: one worker at a time. The worker calls `service.load(day)` and puts either the
    `LoadResult` or the exception into a `queue.Queue`; the GUI polls it every 100 ms with
    `root.after`. Worker threads never touch Tk objects.
12. **Unexpected errors**: `root.report_callback_exception` is overridden to log the traceback
    and show `Непредвиденная ошибка: {error}. Приложение продолжает работу.` in the error label.
    Exceptions inside the worker are passed through the queue and displayed the same way.
