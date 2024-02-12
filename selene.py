from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import NamedTuple

import ttkbootstrap as ttkb
from PIL import ImageFont
from attrs import define
from loguru import logger
from stlrcore.audio_utils import audio_only, is_audio_only
from stlrcore.transcribe import Segment, Transcription, WordTiming

from src.image import get_system_fonts, render_text, transparent_image
from src.ui import CCombobox, CEntry, CSwitch, CText, CToplevel, TextAlignment, file_selection_row, CTextLogHandler

GRID_KW = dict(sticky="nsew", padx=10, pady=10)


def images_to_video(image_template: str, fps: float) -> Path:
    """
    Convert a sequence of images to a video file.
    https://video.stackexchange.com/a/33011
    ffmpeg -i anim.%04d.png -r 30 -pix_fmt yuva420p video.webm

    >>> images_to_video("anim.%04d.png")
    ...
    """
    dest = Path("output.webm")
    command = ("ffmpeg", "-i", image_template, "-r", str(fps), "-pix_fmt", "yuva420p", str(dest))
    subprocess.run(command, capture_output=True)

    return dest


def clear_directory(directory: Path, *, glob: str = "*") -> None:
    """Remove all files from the directory matching the given glob."""
    if not directory.is_dir():
        raise ValueError(f"{directory} is not a directory.")

    for f in directory.glob(glob):
        if f.is_file():
            f.unlink()
        else:
            clear_directory(f, glob="*")
            f.rmdir()


class BoundingBox(NamedTuple):
    x: int
    y: int
    width: int
    height: int


@define
class SubtitleConfig:
    bounding_box: BoundingBox
    font: Path
    fontsize: int
    start_time: float
    end_time: float
    ligatures: bool
    alignment: TextAlignment
    fps: float


class Selene(ttkb.Window):
    def __init__(self, title, *args, **kwargs):
        super().__init__(title, *args, **kwargs)

        self.media_file_box, self.media_file_button = file_selection_row(self, row=0, label_text="Media File",
                                                                         grid_kw=GRID_KW)

        self.progress = ttkb.Floodgauge(bootstyle=ttkb.INFO, mode="indeterminate")

        button = ttkb.Button(self, text="Transcribe", command=lambda: run(media_file=Path(self.media_file_box.text),
                                                                          progress_meter=self.progress))
        button.grid(row=1, column=0, columnspan=3, **GRID_KW)  # type: ignore

        # add progress bar
        self.progress.grid(row=2, column=0, columnspan=3, **GRID_KW)  # type: ignore

        # add log container
        log_box = CText(self)
        log_box.configure(state="disabled", font="TkFixedFont")
        log_box.grid(row=10, column=0, columnspan=3, **GRID_KW)  # type: ignore

        handler = CTextLogHandler(sink=log_box)
        fmt = '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>'
        logger.add(handler, format=fmt)


def run(media_file: Path, progress_meter: ttkb.Floodgauge) -> None:
    # Step 0: Load file
    try:
        a = is_audio_only(media_file)
    except ValueError:
        logger.error(f"{media_file} is not a valid media file.")
        return

    if a:
        audio_file = media_file
        logger.debug(f"{audio_file} is already an audio file")
    else:
        logger.info(f"{media_file} is not an audio file. Converting...")
        audio_file = audio_only(media_file)
        logger.success(f"Conversion successful: {audio_file}")

    # Step 1: Generate transcription
    logger.info("Generating transcription...")
    progress_meter.start()
    transcription = Transcription.from_audio(audio_file)
    progress_meter.stop()
    progress_meter.configure(value=100)
    logger.success("Transcription generated.")

    # Step 2: Get segments
    word_timings = user_split_transcription(transcription)
    logger.success("Segments confirmed.")

    # Step 3: Correct transcriptions
    segments = user_correct_transcription(word_timings)
    logger.success("Corrections confirmed.")

    # Step 4: Output to SRT
    dest = media_file.with_suffix(".srt")
    Transcription.write_srt(segments, dest=dest)
    logger.success(f"SRT file written: {dest}")

    # Step 5: Get subtitle configuration
    fonts = get_system_fonts()
    while (config := get_subtitle_config(fonts=fonts)) is None:
        logger.error("Configuration not processed. Try again.")

    # Step 6: Start building
    image_dir = draw_subtitles(segments, config)
    logger.success(f"Frames written to {image_dir}")


def user_split_transcription(transcription: Transcription) -> list[WordTiming]:
    """Have the user split the given transcription into individual segments."""
    window: CToplevel[list[WordTiming]] = CToplevel(title="Σελήνη: Split Transcription")

    message = "Separate the transcription into individual segments.\nDo NOT edit or correct the transcription."
    ttkb.Label(window, text=message) \
        .grid(row=0, column=0, **GRID_KW)  # type: ignore

    textbox = CText(window)
    textbox.text = str(transcription)
    textbox.grid(row=1, column=0, **GRID_KW)  # type: ignore

    def process_splits():
        fragments = (line.strip() for line in textbox.text.splitlines())
        segments = (transcription.get_fragment(f) for f in fragments)

        # conflate each segment (a list of word timings) into one WordTiming, which is a bit of an abuse
        # of the class, but at this point, we no longer care about the timing of the individual words, just
        # the segment as a whole
        word_timings = [WordTiming(word=str(s), start=s.start, end=s.end) for s in segments]
        window.return_(word_timings)

    ttkb.Button(window, text="Confirm Segments", command=process_splits) \
        .grid(row=2, column=0, **GRID_KW)  # type: ignore

    return window.result() or []


def user_correct_transcription(segments: list[WordTiming]) -> list[Segment]:
    """Have the user correct errors, punctuation, etc. in the transcriptions."""
    window: CToplevel[list[Segment]] = CToplevel(title="Σελήνη: Correct Transcription")

    message = "Make any edits to the transcription, including spelling or punctuation.\nDo NOT edit any line breaks."
    ttkb.Label(window, text=message) \
        .grid(row=0, column=0, **GRID_KW)  # type: ignore

    textbox = CText(window)
    textbox.text = "\n".join(segment.word for segment in segments)
    textbox.grid(row=1, column=0, **GRID_KW)  # type: ignore

    def process_splits():
        corrected_segments: list[Segment] = []

        lines = (line.strip() for line in textbox.text.splitlines())
        for line, segment in zip(lines, segments):
            segment.word = line
            corrected_segments.append(Segment(words=[segment], wait_after=0.0))

        window.return_(corrected_segments)

    ttkb.Button(window, text="Confirm Segments", command=process_splits) \
        .grid(row=2, column=0, **GRID_KW)  # type: ignore

    return window.result() or []


def get_subtitle_config(fonts: dict[str, Path]) -> SubtitleConfig | None:
    window: CToplevel[SubtitleConfig] = CToplevel(title="Σελήνη: Subtitle Configuration")

    # Subtitle bounding box
    ttkb.Label(window, text="Subtitle bounding box") \
        .grid(row=1, column=0, **GRID_KW)  # type: ignore

    bbox_x_entry = CEntry(window, text="(x)", converter=int, validator=(0).__lt__)
    bbox_x_entry.grid(row=1, column=1, **GRID_KW)  # type: ignore

    bbox_y_entry = CEntry(window, text="(y)", converter=int, validator=(0).__lt__)
    bbox_y_entry.grid(row=1, column=2, **GRID_KW)  # type: ignore

    bbox_w_entry = CEntry(window, text="(width)", converter=int, validator=(0).__lt__)
    bbox_w_entry.grid(row=1, column=3, **GRID_KW)  # type: ignore

    bbox_h_entry = CEntry(window, text="(height)", converter=int, validator=(0).__lt__)
    bbox_h_entry.grid(row=1, column=4, **GRID_KW)  # type: ignore

    # Font selector
    ttkb.Label(window, text="Subtitle font") \
        .grid(row=2, column=0, **GRID_KW)  # type: ignore

    font_selector = CCombobox(window, options=list(fonts.keys()), mapfunc=fonts.__getitem__)
    font_selector.grid(row=2, column=1, columnspan=2, **GRID_KW)  # type: ignore

    # Font size
    ttkb.Label(window, text="Font size (pt)") \
        .grid(row=2, column=3, **GRID_KW)  # type: ignore

    fontsize_entry = CEntry(window, converter=int, validator=(0).__lt__)
    fontsize_entry.grid(row=2, column=4, **GRID_KW)  # type: ignore

    # Start and end times
    ttkb.Label(window, text="Start time (seconds)") \
        .grid(row=3, column=0, **GRID_KW)  # type: ignore

    start_time_entry = CEntry(window, text="0.0", converter=float, validator=0.0.__lt__)
    start_time_entry.grid(row=3, column=1, **GRID_KW)  # type: ignore

    ttkb.Label(window, text="End time (seconds)") \
        .grid(row=3, column=2, **GRID_KW)  # type: ignore

    end_time_entry = CEntry(window, text="inf", converter=float, validator=0.0.__lt__)
    end_time_entry.grid(row=3, column=3, **GRID_KW)  # type: ignore

    ligature_switch = CSwitch(window, text="Allow ligatures?", bootstyle="info.RoundToggle.Toolbutton")
    ligature_switch.checked = True
    ligature_switch.grid(row=3, column=4, **GRID_KW)  # type: ignore

    ttkb.Label(window, text="Text Alignment") \
        .grid(row=4, column=2, **GRID_KW)  # type: ignore
    alignment_selector = CCombobox(window, options=[a.name for a in TextAlignment], mapfunc=TextAlignment.__getitem__)
    alignment_selector.grid(row=4, column=3, columnspan=2, **GRID_KW)  # type: ignore

    ttkb.Label(window, text="Video Framerate (fps)") \
        .grid(row=4, column=0, **GRID_KW)  # type: ignore
    fps_entry = CEntry(window, text="30.0", converter=float, validator=0.0.__lt__)
    fps_entry.grid(row=4, column=1, **GRID_KW)  # type: ignore

    def interpret():
        bounding_box = BoundingBox(x=bbox_x_entry.value, y=bbox_y_entry.value, width=bbox_w_entry.value,
                                   height=bbox_h_entry.value)

        config = SubtitleConfig(
            bounding_box=bounding_box,
            font=font_selector.value,
            fontsize=fontsize_entry.value,
            start_time=start_time_entry.value,
            end_time=end_time_entry.value,
            ligatures=ligature_switch.checked,
            alignment=alignment_selector.value,
            fps=fps_entry.value
        )
        window.return_(config)

    ttkb.Button(window, text="Generate", command=interpret) \
        .grid(row=100, column=0, columnspan=5, **GRID_KW)  # type: ignore

    return window.result()


def draw_subtitles(segments: list[Segment], config: SubtitleConfig) -> Path:
    """Render the subtitles onto the appropriate frames, returning the folder into which they are saved."""
    image_dir = Path("subtitle-images")
    image_dir.mkdir(exist_ok=True)
    clear_directory(image_dir)

    frame = 0
    blank_image = transparent_image(width=1920, height=1080)

    for segment in segments:
        start_frame = int(segment.start * config.fps)
        end_frame = int(segment.end * config.fps)
        logger.debug(f"Segment: {segment!r} || {start_frame}-{end_frame}")

        background = transparent_image(width=1920, height=1080)
        text = str(segment)
        pos = config.bounding_box.x, config.bounding_box.y
        width = config.bounding_box.width
        font = ImageFont.truetype(str(config.font), size=config.fontsize)

        subtitled = render_text(image=background, text=text, font=font, pos=pos, width=width, align=config.alignment)

        for i in range(frame, start_frame):
            blank_image.save(image_dir / f"frame-{i:06}.png")

        for i in range(start_frame, end_frame + 1):
            subtitled.save(image_dir / f"frame-{i:06}.png")

        frame = end_frame

    return image_dir


def main():
    with open("./config.toml", "rb") as f:
        config = tomllib.load(f)["selene"]

    theme = config.pop("theme", "darkly")

    app = Selene("Σελήνη", themename=theme, **config)
    app.mainloop()


if __name__ == "__main__":
    main()
