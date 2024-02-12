from __future__ import annotations

import math
from itertools import cycle
from pathlib import Path
from typing import NamedTuple

from loguru import logger
from stlrcore import Transcription
from stlrcore.transcribe import WordTiming

from src.utils import frange, get_space_prefix, read_leading_float


def wait_tag(seconds: float, *, precision: int = 2) -> str:
    """Construct a Ren'Py wait tag: {w=...}"""
    seconds = round(seconds, precision)

    return f"{{w={seconds}}}" if seconds else ""


def renpyify(transcription: Transcription) -> str:
    """Convert the list of transcribed words into a Ren'Py say statement."""
    waits = transcription.waits
    return " ".join(f"{word.word}{wait_tag(wait)}" for word, wait in zip(transcription, waits))


class Indent(NamedTuple):
    initial: str
    full: str


def get_indents(*, initial_indent: int, additional_indent: int) -> Indent:
    """Determine the two necessary levels of indentation for ATL."""
    initial = " " * initial_indent
    full = initial + " " * additional_indent

    return Indent(initial, full)


class ATLImageGenerator:
    def __init__(self, image_name: str, transcription: Transcription, open_mouth: Path, closed_mouth: Path,
                 frame_length: float, initial_indent: int, additional_indent: int):
        self.image_name = image_name
        self.transcription = transcription
        self.open_mouth = open_mouth
        self.closed_mouth = closed_mouth
        self.frame_length = frame_length
        self.indents = get_indents(initial_indent=initial_indent, additional_indent=additional_indent)
        self._images = cycle([self.open_mouth, self.closed_mouth])
        self._atl = ""

    @property
    def atl(self) -> str:
        """Return the generated image ATL code."""
        return self._atl

    @property
    def duration(self) -> float:
        """Determine the length (in seconds) of the animation."""
        return sum(read_leading_float(line) or 0.0 for line in self.atl.splitlines())

    def annotate(self, start: float, end: float, *, verbose: bool = True, assisted: bool = False) -> str:
        if assisted and not verbose:
            # we're in assisted mode but only want simple annotations
            # so, we only need the word headers/tails that are generated over there
            return ""

        boundaries = [(t.word, t.start, "start") for t in self.transcription if start <= t.start < end]
        boundaries.sort(key=lambda item: item[1])

        if not verbose:
            # unassisted mode, so we don't have the headers/tails
            annotation = " |".join(f"{word[0]}" for word in boundaries)
            return f"  # {annotation}" if annotation else ""

        # otherwise, we need the detailed annotation, so...
        boundaries += [(t.word, t.end, "end") for t in self.transcription if start < t.end <= end]
        boundaries.sort(key=lambda item: item[1])

        annotation = f"  # animation time: {start:.3f} → {end:.3f} "
        annotation += " ".join(
            f"| {word!r} [{bound} @ {time:.2f}]" for word, time, bound in boundaries
        )

        return annotation.rstrip()

    def alternate_frames_for_duration(self, duration: float, start: float, time_step: float, *,
                                      ensure_close: bool = True, verbose: bool = True) -> tuple[list[str], Path | None]:
        """Alternate frames for at least the given duration, returning the new lines and the last image used."""
        lines: list[str] = []
        image: Path | None = None

        indent = self.indents.full
        for time, image in zip(frange(start, start + duration, time_step), self._images):
            lines.append(f'{indent}"{image.as_posix()}"')

            annotation = self.annotate(time, time + time_step, verbose=verbose)
            delay_line = f"{indent}{self.frame_length:.3f}{annotation}"
            lines.append(delay_line)

        if ensure_close and image != self.closed_mouth:
            lines.append(f'{indent}"{next(self._images).as_posix()}"')

        return lines, image

    def generate_fixed_aligned_atl(self, *, frame_length: float, verbose: bool = True) -> str:
        lines = [
            f"{self.indents.initial}image {self.image_name}:",
            f"{self.indents.full}# {self.transcription}",
            f"{self.indents.full}# length: {self.transcription.duration:.3f} seconds",
            f"{self.indents.full}# confidence: {self.transcription.confidence:.1%} (min: {self.transcription.min_confidence:.1%})",
        ]

        segments = self.transcription.get_segments(tolerance=frame_length)

        for segment in segments:
            duration = math.ceil(segment.duration / frame_length) * frame_length
            overstep = duration - segment.duration

            logger.debug(
                f"segment: {segment.duration:.2f}s->{duration:.2f}s, {segment}"
            )
            added_lines, _ = self.alternate_frames_for_duration(
                duration=duration,
                start=segment.start,
                time_step=frame_length,
                ensure_close=True,
                verbose=verbose,
            )
            lines.extend(added_lines)

            if (wait := segment.wait_after - overstep) > 0:
                logger.debug(f"{wait=}")
                wait_lines = ["", f"{self.indents.full}{wait:.2f}  # pause", ""]
                lines.extend(wait_lines)

        self._atl = "\n".join(lines)
        return self._atl

    def _generate_word_aligned_block(
            self,
            word: WordTiming,
            *,
            verbose: bool = True,
    ) -> list[str]:
        # The actual length (in seconds) of each frame.
        #                               ↓ the "actual" number of frames, as close to target number
        frame_length = word.duration / max(round(word.duration / self.frame_length), 1)

        lines, _ = self.alternate_frames_for_duration(
            duration=word.duration,
            start=word.start,
            time_step=frame_length,
            ensure_close=True,
            verbose=verbose,
        )

        # add delineating comments
        indent = self.indents.full
        pre_block = (
            f"{indent}# ↓ --- {word.word} (duration: {word.duration:.2f}s) --- ↓"
        )
        post_block = f"{indent}# ↑ --- {word.word} --- ↑"

        return [pre_block, *lines, post_block]

    def generate_word_aligned_atl(self, *, verbose: bool = True) -> str:
        lines = [
            f"{self.indents.initial}image {self.image_name}:",
            f"{self.indents.full}# {self.transcription}",
            f"{self.indents.full}# length: {self.transcription.duration:.2f} seconds",
            f"{self.indents.full}# confidence: {self.transcription.confidence:.1%} (min: {self.transcription.min_confidence:.1%})",
            f'{self.indents.full}"{self.closed_mouth.as_posix()}"',
            f"{self.indents.full}{self.transcription.start}",
        ]

        for word, wait in zip(self.transcription, self.transcription.waits):
            lines.extend(self._generate_word_aligned_block(word, verbose=verbose))
            if wait:
                lines.extend(["", f"{self.indents.full}{wait:.3f}  # (pause)", ""])

        return "\n".join(lines)

    def generate_atl(self, *, alignment: str, verbose: bool = True) -> str:
        lookup = {
            "word alignment": self.generate_word_aligned_atl,
            "fixed alignment": self.generate_fixed_aligned_atl,
        }

        return lookup[alignment](verbose=verbose)

    def reannotate(self, atl: str, *, verbose: bool = True) -> str:
        lines: list[str] = []

        time = 0.0
        for line in atl.splitlines():
            if (pause := read_leading_float(line)) is None:
                # this line doesn't have a delay, so add it unchanged
                lines.append(line)
                continue

            prefix = get_space_prefix(line)
            annotation = self.annotate(time, time + pause, verbose=verbose)
            lines.append(f"{prefix}{pause:.2f}{annotation}")

            time += pause

            if time >= self.transcription.duration:
                # we've reached the end of the line, so we can cut the animation here
                break
        else:
            # we're exhausted the existing animation,
            # so check if we need to add additional frames
            if time < self.transcription.duration:
                buffer = self.transcription.duration - time
                added_lines, _ = self.alternate_frames_for_duration(
                    duration=buffer, start=time, ensure_close=True, verbose=verbose,
                    time_step=self.frame_length
                )
                lines.extend(added_lines)

        return "\n".join(lines)
