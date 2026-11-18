"""Graphical User Interface for Currency Converter using Tkinter/ttk."""

import logging
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from tkinter import ttk

from currency_converter import APP_TITLE
from currency_converter.converter import convert, currency_options
from currency_converter.errors import (
    ConverterError,
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
from currency_converter.models import LoadResult, LoadStatus, RateTable
from currency_converter.rate_service import RateService
from currency_converter.validation import parse_amount, parse_rate_date

logger = logging.getLogger(__name__)


class ConverterApp:
    """Main application controller and view for Currency Converter."""

    def __init__(
        self,
        root: tk.Tk,
        service: RateService | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self.root = root
        self.service = service if service is not None else RateService()
        self.today = today

        self.active: LoadResult | None = None
        self._saved_table: RateTable | None = None
        self.is_loading: bool = False
        self._pending_conversion: tuple[Decimal, date] | None = None
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()

        self._init_window()
        self._create_widgets()
        self._setup_bindings()
        self._setup_error_handler()

        self._startup()

    def _init_window(self) -> None:
        self.root.title(APP_TITLE)
        self.root.minsize(560, 460)
        self.root.resizable(True, True)

    def _create_widgets(self) -> None:
        main_frame = ttk.Frame(self.root, padding=16)
        main_frame.pack(fill="both", expand=True)

        main_frame.columnconfigure(1, weight=1)

        # Row 1: Сумма
        ttk.Label(main_frame, text="Сумма:").grid(
            row=0, column=0, sticky="w", pady=4, padx=(0, 8)
        )
        self.amount_var = tk.StringVar()
        self.amount_entry = ttk.Entry(main_frame, textvariable=self.amount_var)
        self.amount_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=4)

        # Row 2: Из валюты + ⇄ Поменять
        ttk.Label(main_frame, text="Из валюты:").grid(
            row=1, column=0, sticky="w", pady=4, padx=(0, 8)
        )
        self.from_var = tk.StringVar()
        self.from_combo = ttk.Combobox(main_frame, textvariable=self.from_var, state="readonly")
        self.from_combo.grid(row=1, column=1, sticky="ew", pady=4)
        self.swap_btn = ttk.Button(main_frame, text="⇄ Поменять", command=self.on_swap)
        self.swap_btn.grid(row=1, column=2, padx=(8, 0), pady=4)

        # Row 3: В валюту
        ttk.Label(main_frame, text="В валюту:").grid(
            row=2, column=0, sticky="w", pady=4, padx=(0, 8)
        )
        self.to_var = tk.StringVar()
        self.to_combo = ttk.Combobox(main_frame, textvariable=self.to_var, state="readonly")
        self.to_combo.grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)

        # Row 4: Дата курса + Сегодня
        ttk.Label(main_frame, text="Дата курса:").grid(
            row=3, column=0, sticky="w", pady=4, padx=(0, 8)
        )
        self.date_var = tk.StringVar(value=format_date(self.today()))
        self.date_entry = ttk.Entry(main_frame, textvariable=self.date_var)
        self.date_entry.grid(row=3, column=1, sticky="ew", pady=4)
        self.today_btn = ttk.Button(main_frame, text="Сегодня", command=self.on_today)
        self.today_btn.grid(row=3, column=2, padx=(8, 0), pady=4)

        # Row 5: Конвертировать and Обновить курс
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=(8, 4), sticky="w")
        self.convert_btn = ttk.Button(
            btn_frame, text="Конвертировать", command=self.on_convert, default="active"
        )
        self.convert_btn.pack(side="left", padx=(0, 8))
        self.refresh_btn = ttk.Button(btn_frame, text="Обновить курс", command=self.on_refresh)
        self.refresh_btn.pack(side="left")

        # Row 6: error label (red)
        self.error_label = ttk.Label(main_frame, text="", foreground="red", wraplength=520)
        self.error_label.grid(row=5, column=0, columnspan=3, sticky="w", pady=(2, 4))

        # Row 7: result label
        self.result_label = ttk.Label(
            main_frame, text="", font=("TkDefaultFont", 14, "bold"), wraplength=520
        )
        self.result_label.grid(row=6, column=0, columnspan=3, sticky="w", pady=4)

        # Row 8: rates label
        self.rates_label = ttk.Label(main_frame, text="", wraplength=520)
        self.rates_label.grid(row=7, column=0, columnspan=3, sticky="w", pady=2)

        # Row 9: note label
        self.note_label = ttk.Label(main_frame, text="", wraplength=520)
        self.note_label.grid(row=8, column=0, columnspan=3, sticky="w", pady=2)

        # Row 10: status line
        self.status_label = ttk.Label(main_frame, text="Курс не загружен", wraplength=520)
        self.status_label.grid(row=9, column=0, columnspan=3, sticky="w", pady=(4, 2))

        # Row 11: notification frame
        self.notify_frame = ttk.Frame(main_frame)
        self.notify_frame.grid(row=10, column=0, columnspan=3, sticky="ew", pady=4)
        self.notify_msg = ttk.Label(self.notify_frame, text="", wraplength=520)
        self.notify_msg.pack(anchor="w", pady=(0, 4))
        self.notify_buttons = ttk.Frame(self.notify_frame)
        self.notify_buttons.pack(anchor="w")
        self.use_saved_btn = ttk.Button(self.notify_buttons, text="", command=self.on_use_saved)
        self.retry_btn = ttk.Button(self.notify_buttons, text="Повторить", command=self.on_retry)
        self.notify_frame.grid_remove()

        # Row 12: loading label
        self.loading_label = ttk.Label(
            main_frame, text="Загрузка курса…", font=("TkDefaultFont", 9, "italic")
        )
        self.loading_label.grid(row=11, column=0, columnspan=3, sticky="w", pady=2)
        self.loading_label.grid_remove()

    def _setup_bindings(self) -> None:
        self.amount_var.trace_add("write", lambda *_: self._update_convert_button_state())
        self.amount_entry.bind("<KeyRelease>", lambda _: self._update_convert_button_state())
        self.from_combo.bind("<<ComboboxSelected>>", lambda _: self._update_convert_button_state())
        self.to_combo.bind("<<ComboboxSelected>>", lambda _: self._update_convert_button_state())
        self.root.bind("<Return>", self.on_convert)

    def _setup_error_handler(self) -> None:
        def report_callback_exception(exc_type, exc_value, exc_traceback):
            logger.error(
                "Unexpected callback exception", exc_info=(exc_type, exc_value, exc_traceback)
            )
            self.error_label.config(
                text=f"Непредвиденная ошибка: {exc_value}. Приложение продолжает работу."
            )

        self.root.report_callback_exception = report_callback_exception

    def _startup(self) -> None:
        # Behaviour 1: load saved rates if available
        saved = self.service.load_saved()
        if saved is not None:
            self._saved_table = saved.table
            self._populate_currencies(saved.table)
        elif self.service.cache.last_error:
            self.note_label.config(text=self.service.cache.last_error)

        self._update_convert_button_state()
        self._start_load(self.today())

    def _get_selected_from_code(self) -> str:
        text = self.from_var.get().strip()
        if not text:
            return ""
        return text.split(" — ")[0].strip()

    def _get_selected_to_code(self) -> str:
        text = self.to_var.get().strip()
        if not text:
            return ""
        return text.split(" — ")[0].strip()

    def _select_combo_by_code(
        self, combo: ttk.Combobox, code: str, display_list: list[str]
    ) -> None:
        prefix = f"{code} — "
        for i, disp in enumerate(display_list):
            if disp.startswith(prefix) or disp == code:
                combo.current(i)
                return
        combo.set("")

    def _populate_currencies(self, table: RateTable) -> None:
        current_from = self._get_selected_from_code()
        current_to = self._get_selected_to_code()

        options = currency_options(table)
        display_list = [disp for _, disp in options]

        self.from_combo["values"] = display_list
        self.to_combo["values"] = display_list

        available_codes = table.codes

        if current_from and current_from in available_codes:
            self._select_combo_by_code(self.from_combo, current_from, display_list)
        elif "USD" in available_codes:
            self._select_combo_by_code(self.from_combo, "USD", display_list)
        elif display_list:
            self.from_combo.current(0)
        else:
            self.from_combo.set("")

        if current_to and current_to in available_codes:
            self._select_combo_by_code(self.to_combo, current_to, display_list)
        elif "MDL" in available_codes:
            self._select_combo_by_code(self.to_combo, "MDL", display_list)
        elif display_list:
            self.to_combo.current(0)
        else:
            self.to_combo.set("")

        if current_from and current_from not in available_codes:
            self.note_label.config(text="Выберите валюту заново")
        if current_to and current_to not in available_codes:
            self.note_label.config(text="Выберите валюту заново")

        self._update_convert_button_state()

    def _can_convert(self) -> bool:
        if self.is_loading:
            return False
        if not self.amount_var.get().strip():
            return False
        from_code = self._get_selected_from_code()
        to_code = self._get_selected_to_code()
        if not from_code or not to_code:
            return False
        return True

    def _update_convert_button_state(self) -> None:
        if self._can_convert():
            self.convert_btn.config(state="normal")
        else:
            self.convert_btn.config(state="disabled")

        if self.is_loading:
            self.refresh_btn.config(state="disabled")
        else:
            self.refresh_btn.config(state="normal")

    def _start_load(self, day: date) -> None:
        if self.is_loading:
            return

        self.is_loading = True
        self.loading_label.grid()
        self._update_convert_button_state()

        def worker() -> None:
            try:
                res = self.service.load(day)
                self.queue.put(("SUCCESS", res))
            except Exception as e:
                self.queue.put(("ERROR", e))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self._poll_queue)

    def _poll_queue(self) -> None:
        try:
            status_code, payload = self.queue.get_nowait()
        except queue.Empty:
            if self.is_loading:
                self.root.after(100, self._poll_queue)
            return

        self.is_loading = False
        self.loading_label.grid_remove()
        self._update_convert_button_state()

        if status_code == "SUCCESS":
            assert isinstance(payload, LoadResult)
            self._on_load_success(payload)
        else:
            assert isinstance(payload, Exception)
            self._on_load_error(payload)

    def _on_load_success(self, result: LoadResult) -> None:
        self.active = result
        self._saved_table = result.table
        self._populate_currencies(result.table)
        self.status_label.config(text=status_line(result))
        self.notify_frame.grid_remove()

        current_note = self.note_label.cget("text")
        notes: list[str] = []
        if current_note:
            notes.append(current_note)

        if result.status == LoadStatus.EARLIER_DATE:
            notice = fallback_notice(result)
            if notice and notice not in notes:
                notes.append(notice)

        if result.warning and result.warning not in notes:
            notes.append(result.warning)

        if notes:
            self.note_label.config(text="\n".join(notes))

        if self._pending_conversion is not None:
            amt, req_d = self._pending_conversion
            self._pending_conversion = None
            if req_d == result.table.requested_date:
                self._perform_conversion(amt, req_d)

    def _on_load_error(self, error: Exception) -> None:
        self._pending_conversion = None
        if isinstance(error, NoRatesError):
            self.notify_frame.grid_remove()
            self.error_label.config(text=str(error))
        elif isinstance(error, (SourceUnavailableError, InvalidResponseError)):
            self.notify_frame.grid()
            is_cached_active = (
                self.active is not None and self.active.status == LoadStatus.CACHED
            )
            if self._saved_table is not None and not is_cached_active:
                saved_date_str = format_date(self._saved_table.rates_date)
                self.notify_msg.config(
                    text=f"{error}\nМожно продолжить с сохранённым курсом от {saved_date_str}."
                )
                self.use_saved_btn.config(
                    text=f"Использовать сохранённый курс от {saved_date_str}"
                )
                self.use_saved_btn.pack(side="left", padx=4, pady=2)
                self.retry_btn.pack(side="left", padx=4, pady=2)
            else:
                self.notify_msg.config(
                    text=(
                        f"{error}\nКурс недоступен: нет связи с источником и нет сохранённых данных. "
                        "Проверьте подключение и нажмите «Обновить курс»."
                    )
                )
                self.use_saved_btn.pack_forget()
                self.retry_btn.pack(side="left", padx=4, pady=2)
        else:
            logger.exception("Unexpected error during rate load")
            self.notify_frame.grid_remove()
            self.error_label.config(
                text=f"Непредвиденная ошибка: {error}. Приложение продолжает работу."
            )

    def on_use_saved(self) -> None:
        if self._saved_table is not None:
            self.active = LoadResult(table=self._saved_table, status=LoadStatus.CACHED)
            self.date_var.set(format_date(self._saved_table.requested_date))
            self._populate_currencies(self.active.table)
            self.status_label.config(text=status_line(self.active))
            self.notify_frame.grid_remove()
            self.error_label.config(text="")
            self._update_convert_button_state()

    def on_retry(self) -> None:
        self.notify_frame.grid_remove()
        try:
            req_date = parse_rate_date(self.date_var.get(), self.today())
        except ValidationError as e:
            self.error_label.config(text=str(e))
            return
        self.error_label.config(text="")
        self._start_load(req_date)

    def on_swap(self) -> None:
        from_val = self.from_var.get()
        to_val = self.to_var.get()
        self.from_var.set(to_val)
        self.to_var.set(from_val)

        self.result_label.config(text="")
        self.rates_label.config(text="")
        self.note_label.config(text="")

        self._update_convert_button_state()

    def on_today(self) -> None:
        self.date_var.set(format_date(self.today()))
        self._update_convert_button_state()

    def on_refresh(self) -> None:
        try:
            req_date = parse_rate_date(self.date_var.get(), self.today())
        except ValidationError as e:
            self.error_label.config(text=str(e))
            return

        self.error_label.config(text="")
        self._start_load(req_date)

    def on_convert(self, event=None) -> None:
        if not self._can_convert():
            return

        # FR-010 / Behaviour 6: clear error and previous result
        self.error_label.config(text="")
        self.result_label.config(text="")
        self.rates_label.config(text="")
        self.note_label.config(text="")

        try:
            amount = parse_amount(self.amount_var.get())
        except ValidationError as e:
            self.error_label.config(text=str(e))
            return

        try:
            req_date = parse_rate_date(self.date_var.get(), self.today())
        except ValidationError as e:
            self.error_label.config(text=str(e))
            return

        if self.active is not None and self.active.table.requested_date == req_date:
            self._perform_conversion(amount, req_date)
        else:
            self._pending_conversion = (amount, req_date)
            self._start_load(req_date)

    def _perform_conversion(self, amount: Decimal, req_date: date) -> None:
        if self.active is None:
            return

        from_code = self._get_selected_from_code()
        to_code = self._get_selected_to_code()

        try:
            res = convert(amount, from_code, to_code, self.active.table)
        except ValidationError as e:
            self.error_label.config(text=str(e))
            return

        self.error_label.config(text="")
        self.result_label.config(text=result_line(res))
        self.rates_label.config(text=rates_line(res))
        if res.same_currency:
            self.note_label.config(text=SAME_CURRENCY_NOTE)
        elif self.active is not None and self.active.status == LoadStatus.EARLIER_DATE:
            self.note_label.config(text=fallback_notice(self.active))
        else:
            self.note_label.config(text="")


def main() -> None:
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


__all__ = [
    "ConverterApp",
    "main",
]
