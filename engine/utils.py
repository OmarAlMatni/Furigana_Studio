"""Shared helpers: Japanese character detection, font resolution, logging.

Kept separate from the pipeline modules so these small, reusable utilities
don't get duplicated or entangled with any single stage's logic.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import regex

# Matches any CJK Unified Ideograph (kanji). Deliberately narrow: this
# must NOT match hiragana/katakana, so furigana is never generated for
# already-phonetic text.
_KANJI_PATTERN = regex.compile(r"[\p{Han}]")

# Common install locations for a Japanese-capable font, checked in order.
# Pillow (unlike Qt) needs an actual font FILE path, not a family name, so
# we search likely locations rather than relying on OS font lookup.
#
# Each entry is (path, face_index). Font COLLECTION files (.ttc) bundle
# several language variants as separate "faces" in one file — e.g. Noto
# Sans CJK ships Japanese, Korean, Simplified/Traditional Chinese, and
# Hong Kong variants all in one .ttc, at different indices. Picking the
# wrong index silently measures with the wrong glyph widths.
_FONT_CANDIDATES: list[tuple[str, int]] = [
    ("/usr/share/fonts/opentype/noto/NotoSansJP-Regular.otf", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttf", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),  # index 0 = JP face
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 0),
    (str(Path.home() / ".fonts" / "NotoSansJP-Regular.otf"), 0),
    # Per-user Windows font install location — fonts installed via
    # double-click "Install" (not "Install for all users") land here,
    # NOT in C:/Windows/Fonts, and are easy to miss.
    (str(Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts" / "NotoSansJP-Regular.otf"), 0),
    (str(Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts" / "NotoSansJP-Regular.ttf"), 0),
    ("C:/Windows/Fonts/NotoSansJP-Regular.otf", 0),
    ("C:/Windows/Fonts/meiryo.ttc", 0),
    ("C:/Windows/Fonts/YuGothM.ttc", 0),
    ("/Library/Fonts/NotoSansJP-Regular.otf", 0),
    ("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 0),
]


def contains_kanji(text: str) -> bool:
    """Return True if the text contains at least one kanji character."""
    return bool(_KANJI_PATTERN.search(text))


# Font families known to cause Windows-specific rendering mismatches: the OS
# registers multiple weight files (Regular/Medium/Light/Bold) under the same
# or very similar family names, so a video player's own font substitution
# can silently resolve the declared name to a DIFFERENT physical file than
# the one actually measured here — even though the name matches exactly.
# This is a well-documented pitfall in ASS/SSA subtitle typesetting
# specifically with Yu Gothic on Windows.
RISKY_FONT_FAMILIES = {"yu gothic", "yu gothic ui", "yu gothic light", "yu gothic medium"}


def is_risky_font_family(family_name: str) -> bool:
    """Return True if this family is known to be prone to OS-level
    weight/file substitution mismatches (see RISKY_FONT_FAMILIES)."""
    return family_name.strip().lower() in RISKY_FONT_FAMILIES


def resolve_font_path(
    explicit_path: Optional[str] = None, explicit_index: int = 0
) -> tuple[str, int]:
    """Find a usable Japanese font file (and face index) for Pillow measurement.

    Args:
        explicit_path: A caller-provided font file path. If given, it is
            used as-is (and must exist).
        explicit_index: Face index to use within explicit_path, for font
            collection (.ttc) files. Ignored if explicit_path is None.

    Returns:
        A (font_file_path, face_index) tuple.

    Raises:
        FileNotFoundError: if no usable font file could be found. This is
            intentionally fatal rather than silently falling back to a
            non-CJK font, since that would make every width measurement
            wrong and misplace all furigana. Matters even more on a server:
            the deployment machine's available fonts are often unknown
            ahead of time, so failing loudly at startup beats silently
            mis-measuring for every request.
    """
    if explicit_path:
        if Path(explicit_path).exists():
            return explicit_path, explicit_index
        raise FileNotFoundError(f"Configured font path does not exist: {explicit_path}")

    for candidate, index in _FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate, index

    raise FileNotFoundError(
        "No Japanese font file found for text measurement. Install Noto Sans JP "
        "(or another CJK-capable font) on the server and either place it at one "
        "of the standard OS font locations, or pass font_path explicitly via "
        "LayoutConfig. See README.md for details."
    )


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
