"""Graphical User Interface for Currency Converter using Tkinter/ttk."""

import logging
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from tkinter import font, ttk

from currency_converter import APP_TITLE
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
        self._configure_styles()
        self._create_widgets()
        self._setup_bindings()
        self._setup_error_handler()

        self._startup()

    def _init_window(self) -> None:
        self.root.title(APP_TITLE)
        self.root.geometry("840x480")
        self.root.minsize(560, 460)
        self.root.resizable(True, True)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        family = font.nametofont("TkDefaultFont", root=self.root).actual("family")

        canvas = "#edf4fc"
        surface = "#ffffff"
        result_surface = "#f3f8ff"
        status_surface = "#e2eefc"
        ink = "#142d4b"
        muted = "#435d7b"
        border = "#cbd9eb"
        accent = "#215bc2"
        focus = "#2364d4"

        style.configure("Converter.TFrame", background=canvas)
        style.configure("ConverterForm.TFrame", background=surface)
        style.configure("ConverterResult.TFrame", background=result_surface)
        style.configure("ConverterStatus.TFrame", background=status_surface)
        style.configure(
            "ConverterTitle.TLabel", background=canvas, foreground=ink,
            font=(family, 25, "bold"),
        )
        style.configure(
            "ConverterField.TLabel", background=surface, foreground=ink,
            font=(family, 10, "bold"),
        )
        style.configure(
            "ConverterError.TLabel", background=surface, foreground="#a82325",
            font=(family, 10),
        )
        style.configure(
            "ConverterResultTitle.TLabel", background=result_surface, foreground=muted,
            font=(family, 11, "bold"),
        )
        style.configure(
            "ConverterAmount.TLabel", background=result_surface, foreground=accent,
            font=(family, 18, "bold"),
        )
        style.configure(
            "ConverterDetail.TLabel", background=result_surface, foreground=muted,
            font=(family, 10),
        )
        style.configure(
            "ConverterStatus.TLabel", background=status_surface, foreground=ink,
            font=(family, 10),
        )
        style.configure(
            "ConverterLoading.TLabel", background=canvas, foreground=accent,
            font=(family, 10, "bold"),
        )
        style.configure(
            "Converter.Vertical.TScrollbar", background=border, troughcolor=canvas,
            bordercolor=canvas, lightcolor=border, darkcolor=border, arrowcolor=muted,
        )

        for name in ("Converter.TEntry", "Converter.TCombobox"):
            style.configure(
                name, padding=(9, 4), foreground=ink, fieldbackground=surface,
                background=surface, bordercolor=border, lightcolor=border, darkcolor=border,
                selectforeground=ink, selectbackground=status_surface, insertcolor=ink,
            )
            style.map(
                name, fieldbackground=[("readonly", surface)],
                bordercolor=[("focus", focus)], lightcolor=[("focus", focus)],
                darkcolor=[("focus", focus)],
            )

        style.configure(
            "ConverterPrimary.TButton", padding=(11, 7), background=accent,
            foreground=surface, bordercolor=accent, lightcolor=accent, darkcolor=accent,
            focuscolor=surface, font=(family, 10, "bold"),
        )
        style.map(
            "ConverterPrimary.TButton",
            background=[("disabled", "#e4edf9"), ("pressed", "#164494"), ("active", "#1c51ad")],
            foreground=[("disabled", "#526b8a")],
            bordercolor=[("disabled", "#e4edf9")],
            lightcolor=[("disabled", "#e4edf9")], darkcolor=[("disabled", "#e4edf9")],
        )
        style.configure(
            "ConverterSecondary.TButton", padding=(9, 5), background=surface, foreground=ink,
            bordercolor=border, lightcolor=border, darkcolor=border, focuscolor=focus,
            font=(family, 10),
        )
        style.map(
            "ConverterSecondary.TButton",
            background=[("disabled", "#edf2fa"), ("pressed", "#d7e7fd"), ("active", "#eaf3ff")],
            foreground=[("disabled", "#526b8a")], bordercolor=[("focus", focus)],
        )

    def _create_widgets(self) -> None:
        main_frame = ttk.Frame(self.root, padding=(20, 16), style="Converter.TFrame")
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        header = ttk.Frame(main_frame, style="Converter.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Конвертер валют", style="ConverterTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.loading_label = ttk.Label(
            header, text="Загрузка курса…", style="ConverterLoading.TLabel"
        )
        self.loading_label.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.loading_label.grid_remove()

        content = self._create_content(main_frame)
        content.columnconfigure(0, minsize=288, weight=3)
        content.columnconfigure(1, minsize=205, weight=2)
        content.rowconfigure(0, weight=1)

        form = ttk.Frame(content, padding=(16, 11), style="ConverterForm.TFrame")
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Сумма:", style="ConverterField.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 9)
        )
        self.amount_var = tk.StringVar()
        self.amount_entry = ttk.Entry(
            form, textvariable=self.amount_var, width=1, style="Converter.TEntry"
        )
        self.amount_entry.grid(row=0, column=1, columnspan=2, sticky="ew")

        ttk.Label(form, text="Из валюты:", style="ConverterField.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(7, 2)
        )
        self.from_var = tk.StringVar()
        self.from_combo = ttk.Combobox(
            form, textvariable=self.from_var, state="readonly", width=1, style="Converter.TCombobox"
        )
        self.from_combo.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.swap_btn = ttk.Button(
            form, text="⇄ Поменять", command=self.on_swap, style="ConverterSecondary.TButton"
        )
        self.swap_btn.grid(row=1, column=2, sticky="e", pady=(5, 2))

        ttk.Label(form, text="В валюту:", style="ConverterField.TLabel").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(7, 2)
        )
        self.to_var = tk.StringVar()
        self.to_combo = ttk.Combobox(
            form, textvariable=self.to_var, state="readonly", width=1, style="Converter.TCombobox"
        )
        self.to_combo.grid(row=4, column=0, columnspan=3, sticky="ew")

        date_controls = ttk.Frame(form, style="ConverterForm.TFrame")
        date_controls.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(9, 0))
        date_controls.columnconfigure(1, weight=1)
        ttk.Label(date_controls, text="Дата курса:", style="ConverterField.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 9)
        )
        self.date_var = tk.StringVar(value=format_date(self.today()))
        self.date_entry = ttk.Entry(
            date_controls, textvariable=self.date_var, width=1, style="Converter.TEntry"
        )
        self.date_entry.grid(row=0, column=1, sticky="ew")
        self.today_btn = ttk.Button(
            date_controls, text="Сегодня", command=self.on_today, width=0,
            style="ConverterSecondary.TButton",
        )
        self.today_btn.grid(row=0, column=2, sticky="ew", padx=(7, 0))

        btn_frame = ttk.Frame(form, style="ConverterForm.TFrame")
        btn_frame.grid(row=6, column=0, columnspan=3, pady=(10, 0), sticky="ew")
        self.convert_btn = ttk.Button(
            btn_frame, text="Конвертировать", command=self.on_convert, default="active",
            style="ConverterPrimary.TButton",
        )
        self.convert_btn.pack(side="left", fill="x", expand=True, padx=(0, 7))
        self.refresh_btn = ttk.Button(
            btn_frame, text="Обновить курс", command=self.on_refresh,
            style="ConverterSecondary.TButton",
        )
        self.refresh_btn.pack(side="left")

        self.error_label = ttk.Label(form, style="ConverterError.TLabel")
        self.error_label.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        self._wrap_labels(form, 32, self.error_label)

        result = ttk.Frame(content, padding=(14, 13), style="ConverterResult.TFrame")
        result.grid(row=0, column=1, sticky="nsew")
        result.columnconfigure(0, weight=1)

        ttk.Label(result, text="Результат", style="ConverterResultTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        self.result_label = ttk.Label(result, style="ConverterAmount.TLabel")
        self.result_label.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self.rates_label = ttk.Label(result, style="ConverterDetail.TLabel")
        self.rates_label.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        status = ttk.Frame(result, padding=(9, 9), style="ConverterStatus.TFrame")
        status.grid(row=3, column=0, sticky="ew")
        self.status_label = ttk.Label(
            status, text="Курс не загружен", style="ConverterStatus.TLabel"
        )
        self.status_label.pack(fill="x")
        self._wrap_labels(status, 18, self.status_label)

        self.note_label = ttk.Label(result, style="ConverterDetail.TLabel")
        self.note_label.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self._wrap_labels(result, 28, self.result_label, self.rates_label, self.note_label)

        self.notify_frame = ttk.Frame(
            main_frame, padding=(12, 9), style="ConverterStatus.TFrame"
        )
        self.notify_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.notify_msg = ttk.Label(self.notify_frame, style="ConverterStatus.TLabel")
        self.notify_msg.pack(fill="x", pady=(0, 4))
        self.notify_buttons = ttk.Frame(self.notify_frame, style="ConverterStatus.TFrame")
        self.notify_buttons.pack(anchor="w")
        self.use_saved_btn = ttk.Button(
            self.notify_buttons, command=self.on_use_saved, style="ConverterSecondary.TButton"
        )
        self.retry_btn = ttk.Button(
            self.notify_buttons, text="Повторить", command=self.on_retry,
            style="ConverterSecondary.TButton",
        )
        self._wrap_labels(self.notify_frame, 24, self.notify_msg)
        self.notify_frame.grid_remove()

    def _create_content(self, main_frame: ttk.Frame) -> ttk.Frame:
        viewport = ttk.Frame(main_frame, style="Converter.TFrame")
        viewport.grid(row=1, column=0, sticky="nsew")
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)

        background = ttk.Style(self.root).lookup("Converter.TFrame", "background")
        canvas = tk.Canvas(viewport, background=background, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            viewport, orient="vertical", command=canvas.yview,
            style="Converter.Vertical.TScrollbar",
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        scrollbar.grid_remove()

        content = ttk.Frame(canvas, style="Converter.TFrame")
        pane = canvas.create_window(0, 0, window=content, anchor="nw")

        def fit_content(_event: tk.Event) -> None:
            width = canvas.winfo_width()
            view_height = canvas.winfo_height()
            content_height = content.winfo_reqheight()
            height = max(content_height, view_height)
            canvas.itemconfigure(pane, width=width, height=height)
            canvas.configure(scrollregion=(0, 0, width, height))
            if content_height > view_height:
                scrollbar.grid()
            else:
                scrollbar.grid_remove()

        def reveal_focus(event: tk.Event) -> None:
            widget = event.widget
            if not isinstance(widget, tk.Misc):
                return
            ancestor = widget.master
            while ancestor is not None and ancestor is not content:
                ancestor = ancestor.master
            if ancestor is None or not scrollbar.winfo_ismapped():
                return
            top = widget.winfo_rooty() - content.winfo_rooty()
            bottom = top + widget.winfo_height()
            view_top = canvas.canvasy(0)
            view_height = canvas.winfo_height()
            if top < view_top:
                canvas.yview_moveto(top / content.winfo_height())
            elif bottom > view_top + view_height:
                canvas.yview_moveto((bottom - view_height) / content.winfo_height())

        self.root.bind("<Configure>", fit_content, add="+")
        self.root.bind("<FocusIn>", reveal_focus, add="+")
        return content

    @staticmethod
    def _wrap_labels(frame: ttk.Frame, padding: int, *labels: ttk.Label) -> None:
        def update_wrap(event: tk.Event) -> None:
            width = max(1, event.width - padding)
            for label in labels:
                label.configure(wraplength=width)

        frame.bind("<Configure>", update_wrap)

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

    def _populate_currencies(self, table: RateTable) -> bool:
        current_from = self._get_selected_from_code()
        current_to = self._get_selected_to_code()

        options = currency_options(table)
        display_list = [disp for _, disp in options]

        self.from_combo["values"] = display_list
        self.to_combo["values"] = display_list

        available_codes = table.codes
        selection_lost = False

        if current_from:
            if current_from in available_codes:
                self._select_combo_by_code(self.from_combo, current_from, display_list)
            else:
                self.from_combo.set("")
                selection_lost = True
        else:
            if "USD" in available_codes:
                self._select_combo_by_code(self.from_combo, "USD", display_list)
            elif display_list:
                self.from_combo.current(0)
            else:
                self.from_combo.set("")

        if current_to:
            if current_to in available_codes:
                self._select_combo_by_code(self.to_combo, current_to, display_list)
            else:
                self.to_combo.set("")
                selection_lost = True
        else:
            if "MDL" in available_codes:
                self._select_combo_by_code(self.to_combo, "MDL", display_list)
            elif display_list:
                self.to_combo.current(0)
            else:
                self.to_combo.set("")

        if selection_lost:
            self.note_label.config(text="Выберите валюту заново")

        self._update_convert_button_state()
        return selection_lost

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
        selection_lost = self._populate_currencies(result.table)
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
            if not selection_lost and self._can_convert() and req_d == result.table.requested_date:
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
            if is_cached_active:
                saved_date_str = format_date(self.active.table.rates_date)
                self.notify_msg.config(
                    text=(
                        f"{error}\nИсточник недоступен, продолжают использоваться "
                        f"сохранённые курсы от {saved_date_str}."
                    )
                )
                self.use_saved_btn.pack_forget()
                self.retry_btn.pack(side="left", padx=4, pady=2)
            elif self._saved_table is not None:
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
            logger.error("Unexpected error during rate load", exc_info=error)
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

        notes: list[str] = []
        current_note = self.note_label.cget("text")
        if current_note:
            notes.extend([n for n in current_note.split("\n") if n and n != SAME_CURRENCY_NOTE])

        if self.active.status == LoadStatus.EARLIER_DATE:
            notice = fallback_notice(self.active)
            if notice and notice not in notes:
                notes.append(notice)

        if self.active.warning and self.active.warning not in notes:
            notes.append(self.active.warning)

        if res.same_currency:
            if SAME_CURRENCY_NOTE not in notes:
                notes.append(SAME_CURRENCY_NOTE)

        self.note_label.config(text="\n".join(notes))


def main() -> None:
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


__all__ = [
    "ConverterApp",
    "main",
]
