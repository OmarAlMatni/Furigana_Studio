"""SRT loading and validation.

Wraps pysubs2 to load .srt files and convert them into our internal
SubtitleEvent structures. Timing, ordering, and line breaks are never
modified here or anywhere downstream.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import pysubs2

from .models import SubtitleEvent

logger = logging.getLogger(__name__)


class SubtitleParseError(Exception):
    """Raised when an input file cannot be parsed as a valid subtitle file."""


def load_srt(path: Union[str, Path]) -> list[SubtitleEvent]:
    """Load an .srt file and return its events in original order.

    Args:
        path: Path to a .srt subtitle file.

    Returns:
        A list of SubtitleEvent, one per subtitle cue, preserving
        original start/end times and ordering exactly.

    Raises:
        FileNotFoundError: if the file does not exist.
        SubtitleParseError: if the file has the wrong extension, is
            empty, or cannot be parsed/decoded as a valid SRT.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Input subtitle file not found: {file_path}")

    if file_path.suffix.lower() != ".srt":
        raise SubtitleParseError(
            f"Unsupported file type '{file_path.suffix}'. Only .srt files are accepted."
        )

    try:
        subs = pysubs2.load(str(file_path), encoding="utf-8")
    except UnicodeDecodeError:
        try:
            subs = pysubs2.load(str(file_path), encoding="utf-8-sig")
        except Exception as exc:
            raise SubtitleParseError(
                f"Could not decode '{file_path.name}'. Please re-save it as UTF-8."
            ) from exc
    except Exception as exc:
        raise SubtitleParseError(
            f"Could not parse '{file_path.name}' as a valid SRT file: {exc}"
        ) from exc

    if len(subs) == 0:
        raise SubtitleParseError(f"'{file_path.name}' contains no subtitle events.")

    events: list[SubtitleEvent] = [
        SubtitleEvent(index=i, start_ms=line.start, end_ms=line.end, text=line.text)
        for i, line in enumerate(subs)
    ]

    logger.info("Parsed %d subtitle events from %s", len(events), file_path.name)
    return events
