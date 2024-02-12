from __future__ import annotations

from difflib import SequenceMatcher
from itertools import count, tee
from pathlib import Path
import re
from typing import Callable, Iterable, Iterator, Sequence, TypeVar

T = TypeVar("T")


def diff_blocks(
        seq1: Sequence[T], seq2: Sequence[T],
        isjunk: Callable[[T], bool] | None = None,
        autojunk: bool = True
) -> Iterator[tuple[Sequence[T], Sequence[T], Sequence[T]]]:
    """Step through the two sequences, returning matching/unmatching subsequences."""
    # initialise our pointers in seq1 (i) and seq2 (j)
    i, j = 0, 0

    for block in SequenceMatcher(isjunk, seq1, seq2, autojunk).get_matching_blocks():
        unmatched_a = seq1[i:block.a]  # read up to this match
        unmatched_b = seq2[j:block.b]  # read up to this match
        matched = seq1[block.a:block.a+block.size]  # take the matching part

        yield unmatched_a, unmatched_b, matched

        # and update our pointers to the end of this match
        i = block.a + block.size
        j = block.b + block.size


def diff_block_str(
        str1: str, str2: str, *,
        case_sensitive: bool = False, remove_punctuation: bool = True
) -> Iterator[tuple[str, str, str]]:
    def _transform(s: str, /) -> list[str]:
        if not case_sensitive:
            s = s.lower()

        words = s.split()

        return [re.sub(r"[^a-zA-z]", "", w) for w in words] if remove_punctuation else words

    for u, v, matched in diff_blocks(_transform(str1), _transform(str2)):
        yield ' '.join(u), ' '.join(v), ' '.join(matched)


def frange(start: float, stop: float | None = None, step: float | None = None) -> Iterator[float]:
    """Generalize the built-in range function to allow for float arguments."""
    start = float(start)

    if stop is None:
        # frange(stop, step=...) -> arange(0.0, stop, step)
        start, stop = 0.0, start

    if step is None:
        # frange(..., step=None) -> arange(..., step=1.0)
        step = 1.0

    for n in count():
        current = float(start + n * step)

        if step > 0 and current >= stop:
            break

        if step < 0 and current <= stop:
            break

        yield current


def truncate_path(path: Path, highest_parent: str) -> Path:
    if match := re.search(rf"({highest_parent}.*)", str(path)):
        return Path(match.group(1))

    raise ValueError(f"cannot truncate {path} to {highest_parent}")


def pairwise(s: Iterable[T]) -> Iterator[tuple[T, T]]:
    """s -> (s0, s1), (s1, s2), (s2, s3), ..."""
    a, b = tee(s)
    next(b, None)
    yield from zip(a, b)


def read_leading_float(s: str, /) -> float | None:
    if match := re.match(r"\s*([0-9]*\.?[0-9]+)", s):
        return float(match.group(1))

    return None


def get_space_prefix(s: str, /) -> str:
    if match := re.match(r"(\s*)", s):
        return match.group(1)

    raise ValueError(f"cannot read space prefix for {s!r}")


def seconds_to_hms(seconds: float, *, omit_hour: bool = True, srt_format: bool = False) -> str:
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if srt_format:
        # SRT requires HH:MM:SS,fff
        return f"{hours:02.0f}:{minutes:02.0f}:{seconds:06.3f}".replace(".", ",")

    if hours and not omit_hour:
        # H:MM:SS.SSS
        return f"{hours:.0f}:{minutes:02.0f}:{seconds:06.3f}"

    # M:SS.SSS
    return f"{minutes:.0f}:{seconds:06.3f}"
