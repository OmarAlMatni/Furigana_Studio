"""Decides which parts of each token get furigana.

Isolates exactly the kanji-bearing substring(s) of a token so that
surrounding kana (okurigana) is left untouched — e.g.:

    食べる -> 食[た]べる      (not 食べる[たべる])
    飲み物 -> 飲[の]み物[もの] (kanji on both sides of an internal kana)
    行った -> 行[い]った

The core idea: a token's surface form and its hiragana reading always
agree, character-for-character, on any part that is already kana (since
the "reading" of a kana character is itself). So splitting the surface
into alternating kanji/non-kanji runs and walking the reading in lockstep
tells us exactly which slice of the reading belongs to each kanji run.
"""
from __future__ import annotations

import logging

from .models import FuriganaPart, FuriganaSegment, Token
from .utils import contains_kanji

logger = logging.getLogger(__name__)


def _segment_by_script(surface: str) -> list[tuple[str, str]]:
    """Split surface text into contiguous runs of ('kanji', ...) or ('other', ...)."""
    segments: list[tuple[str, str]] = []
    current_type: str | None = None
    current_chars: list[str] = []

    for ch in surface:
        ch_type = "kanji" if contains_kanji(ch) else "other"
        if ch_type != current_type and current_chars:
            segments.append((current_type, "".join(current_chars)))
            current_chars = []
        current_type = ch_type
        current_chars.append(ch)

    if current_chars:
        segments.append((current_type, "".join(current_chars)))

    return segments


def _split_kanji_core(surface: str, reading: str) -> list[FuriganaPart]:
    """Split a token into parts, attaching a reading only to its kanji runs."""
    segments = _segment_by_script(surface)
    parts: list[FuriganaPart] = []
    cursor = 0

    for i, (seg_type, seg_text) in enumerate(segments):
        if seg_type == "other":
            if reading[cursor : cursor + len(seg_text)] == seg_text:
                cursor += len(seg_text)
            else:
                found = reading.find(seg_text, cursor)
                if found != -1:
                    cursor = found + len(seg_text)
            parts.append(FuriganaPart(text=seg_text, furigana=None))
        else:
            next_other = next((s for t, s in segments[i + 1 :] if t == "other"), None)
            if next_other:
                end = reading.find(next_other, cursor)
                end = end if end != -1 else len(reading)
            else:
                end = len(reading)
            core_reading = reading[cursor:end]
            cursor = end
            parts.append(FuriganaPart(text=seg_text, furigana=core_reading or None))

    return parts


def generate_furigana(token: Token) -> FuriganaSegment:
    """Build the furigana breakdown for a single token."""
    if not token.contains_kanji:
        return FuriganaSegment(
            token=token, parts=[FuriganaPart(text=token.surface, furigana=None)]
        )

    parts = _split_kanji_core(token.surface, token.reading_hiragana)

    if not parts:
        parts = [FuriganaPart(text=token.surface, furigana=token.reading_hiragana or None)]

    return FuriganaSegment(token=token, parts=parts)


def generate_furigana_for_line(tokens: list[Token]) -> list[FuriganaSegment]:
    """Generate furigana segments for every token in a tokenized line."""
    return [generate_furigana(t) for t in tokens]
