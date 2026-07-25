"""Data models shared across the Furigana Studio conversion engine.

These dataclasses define the structures passed between pipeline stages:

    SubtitleEvent -> Token -> FuriganaSegment -> PositionedEvent

Keeping them centralized means every module agrees on the same shapes,
which matters for reuse across the API layer (request handling, response
shaping) without touching the conversion logic itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SubtitleEvent:
    """A single subtitle cue as read from the source SRT file.

    Timing is kept in raw milliseconds (as pysubs2 provides it) and is
    never modified anywhere in the pipeline.
    """

    index: int
    start_ms: int
    end_ms: int
    text: str  # raw pysubs2 text; line breaks are the literal token \N


@dataclass
class Token:
    """A single morphological unit produced by the tokenizer."""

    surface: str
    reading_hiragana: str
    dictionary_form: str
    contains_kanji: bool


@dataclass
class FuriganaPart:
    """One chunk of a token: either plain text or a kanji run with a reading.

    `furigana` is None for parts that should render as-is with nothing
    positioned above them (particles, punctuation, already-kana text,
    numbers, English, okurigana, etc.).
    """

    text: str
    furigana: Optional[str]


@dataclass
class FuriganaSegment:
    """Furigana-annotated breakdown of a single token."""

    token: Token
    parts: list[FuriganaPart] = field(default_factory=list)


@dataclass
class PositionedPart:
    """A FuriganaPart with computed pixel coordinates for \\pos placement."""

    text: str
    x_start: float
    x_end: float
    furigana: Optional[str]
    furigana_center_x: Optional[float]


@dataclass
class PositionedLine:
    """One visual subtitle row (post \\N split), fully laid out."""

    parts: list[PositionedPart]
    baseline_y: float
    line_start_x: float
    line_end_x: float


@dataclass
class PositionedEvent:
    """A fully laid-out subtitle event, ready for ASS dialogue generation."""

    subtitle_event: SubtitleEvent
    lines: list[PositionedLine]
