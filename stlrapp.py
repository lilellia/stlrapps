import tomllib
from itertools import chain
from pathlib import Path
from tkinter.filedialog import askopenfilenames
from typing import Any

import ttkbootstrap as ttkb
from stlrcore import Transcription

from src.ui import CEntry
from src.vn import renpyify


class STLRApp(ttkb.Window):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)  # type: ignore
        self.init_components()

    # noinspection PyAttributeOutsideInit
    def init_components(self) -> None:
        self.fileselector = ttkb.Button(self, text="Choose Audio Files", command=self.select_files)
        self.fileselector.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)

        self.filenames: list[Path] = []
        self.filename_labels: list[ttkb.Label] = []
        self.transcriptions: list[CEntry] = []

    def clear(self) -> None:
        for widget in chain(self.filename_labels, self.transcriptions):
            widget.grid_remove()

    # noinspection PyAttributeOutsideInit
    def select_files(self) -> None:
        self.clear()
        self.filenames = [Path(s) for s in askopenfilenames()]

        if not self.filenames:
            return

        for i, path in enumerate(self.filenames, start=1):
            e = ttkb.Label(self, text=str(path))
            e.grid(row=i, column=0, padx=10, pady=10)
            self.filename_labels.append(e)

            f = CEntry(self, width=150)
            f.grid(row=i, column=1, columnspan=2, sticky="nsew", padx=10, pady=10)
            self.transcriptions.append(f)

        self.transcribe_btn = ttkb.Button(self, text="Transcribe", command=self.transcribe,
                                          bootstyle="info")  # type: ignore
        self.transcribe_btn.grid(row=i + 1, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)  # type: ignore

    def transcribe(self) -> None:
        for path, entry in zip(self.filenames, self.transcriptions):
            transcription = Transcription.from_audio(path)
            entry.text = renpyify(transcription)


def main():
    with open("./config.toml", "rb") as f:
        config = tomllib.load(f)["stlrapp"]

    theme = config.pop("theme", "darkly")
    app = STLRApp("stlrapp", themename=theme, **config)
    app.mainloop()


if __name__ == "__main__":
    main()
