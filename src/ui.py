from __future__ import annotations

import logging
import tkinter as tk
from enum import Enum
from tkinter.filedialog import askopenfilename
from typing import Any, Callable, Generic, Iterable, TypeVar

import ttkbootstrap as ttkb  # type: ignore

T = TypeVar("T")


class TextAlignment(Enum):
    LEFT = "left"
    RIGHT = "right"
    CENTRE = "center"
    CENTER = "center"


class CEntry(ttkb.Entry, Generic[T]):
    def __init__(self, master: Any, text: str = "", *args: Any, converter: Callable[[str], T] = str,
                 validator: Callable[[T], bool] = lambda _: True, **kwargs: Any) -> None:
        self._var = tk.StringVar(master, text)
        super().__init__(master, *args, textvariable=self._var, **kwargs)

        self.converter = converter
        self.validator = validator

        self.hint_text = text
        self.initial_fg = self.cget("foreground")
        self.entered = False
        self.config(foreground="grey")
        self.bind("<FocusIn>", self.on_focus)
        self.bind("<FocusOut>", self.on_unfocus)

    @property
    def text(self) -> str:
        return self._var.get()

    @text.setter
    def text(self, text: str) -> None:
        self._var.set(text)

    @property
    def value(self) -> T:
        return self.converter(self.text)

    def validate(self) -> bool:
        """Determine whether the input value is "valid", according to the entry's validator function."""
        try:
            return self.validator(self.value)
        except (ValueError, TypeError):
            return False

    def on_focus(self, _: tk.Event):
        self.config(foreground=self.initial_fg)
        if not self.entered:
            # this is the first time the user has focused this textbox,
            # so the hint text is what should still be in there
            self.entered = True
            self.text = ""

    def on_unfocus(self, _: tk.Event):
        if not self.text:
            # user has left this textbox empty, so return to starting state
            self.text = self.hint_text
            self.entered = False
            self.config(foreground="grey")

        if not self.validate():
            # resulting value is invalid
            self.config(foreground="red")


class CDropdown(ttkb.OptionMenu, Generic[T]):
    def __init__(self, master: Any, options: Iterable[T], mapfunc: Callable[[str], T] = str, **kwargs: Any):
        self._var = ttkb.StringVar(master)
        self.options = tuple(str(x) for x in options)
        self.mapfunc = mapfunc
        super().__init__(master, self._var, self.options[0], *self.options, **kwargs)

    @property
    def value(self) -> T:
        return self.mapfunc(self._var.get())

    @value.setter
    def value(self, val: T) -> None:
        self._var.set(str(val))


class CCombobox(ttkb.Combobox, Generic[T]):
    def __init__(self, master: Any, options: Iterable[Any], mapfunc: Callable[[str], T] = str, **kwargs: Any):
        self._var = ttkb.StringVar(master)
        self.options = tuple(str(x) for x in options)
        self.mapfunc = mapfunc
        super().__init__(master, textvariable=self._var, values=self.options, **kwargs)

    @property
    def value(self) -> T:
        return self.mapfunc(self._var.get())

    @value.setter
    def value(self, val: T) -> None:
        self._var.set(str(val))


class CSwitch(ttkb.Checkbutton):
    def __init__(self, master: Any, *args: Any, **kwargs: Any) -> None:
        self._var = tk.IntVar(master)
        super().__init__(master, *args, variable=self._var, **kwargs)

    @property
    def checked(self) -> bool:
        return bool(self._var.get())

    @checked.setter
    def checked(self, value: bool) -> None:
        self._var.set(int(value))


class CText(ttkb.ScrolledText):
    @property
    def text(self) -> str:
        return self.get("1.0", "end-1c")

    @text.setter
    def text(self, text: str) -> None:
        self.delete("1.0", "end")
        self.insert("1.0", text)

    def write(self, text, *, end: str = "") -> None:
        """Append the given text to the end of the textbox."""
        self.insert("end", text + end)


class CToplevel(ttkb.Toplevel, Generic[T]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._result = None

    def result(self) -> T | None:
        """Get the "return value" from a Toplevel window. The window sets this by calling self.return_(value)"""
        self.wait_window()
        return self._result

    def return_(self, value: T) -> None:
        """Set the return value of the window and destroy it."""
        self._result = value
        self.destroy()


def file_selection_row(
        master: Any,
        row: int,
        label_text: str,
        button_text: str = "Select File",
        grid_kw: dict[str, Any] | None = None,
) -> tuple[CEntry, ttkb.Button]:
    def _select_file() -> None:
        entry.text = askopenfilename()

    if grid_kw is None:
        grid_kw = dict()

    ttkb.Label(master, text=label_text).grid(row=row, column=0, **grid_kw)

    entry: CEntry[str] = CEntry(master, width=80)
    entry.grid(row=row, column=1, **grid_kw)

    button = ttkb.Button(master, text=button_text, command=_select_file)
    button.grid(row=row, column=2, **grid_kw)

    return entry, button


class CTextLogHandler(logging.Handler):
    """A custom log handler designed to log to a CText object.

    https://stackoverflow.com/a/41959785
    """

    def __init__(self, sink: CText):
        logging.Handler.__init__(self)
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)

        def append_to_log():
            self.sink.configure(state="normal")
            self.sink.write(message, end="\n")
            self.sink.configure(state="disabled")
            self.sink.yview(tk.END)

        # required since we can't modify the sink from other threads
        self.sink.after(ms=0, func=append_to_log)
