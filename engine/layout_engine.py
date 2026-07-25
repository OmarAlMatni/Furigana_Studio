"""Computes pixel positions for anime-style furigana placement.

Standard ASS has no native ruby/furigana tag, so instead we generate
multiple synchronized \\pos()-tagged Dialogue events: one for the main
text row, and one per kanji-bearing word for its furigana reading,
positioned directly above that specific word — never centered relative
to the line as a whole.

Widths are measured with Pillow using the *same* font file, face index,
and font size the ASS style declares, so the computed positions line up
with what the renderer will actually draw. This module also exposes the
resolved font's real family name (`font_family_name`) so the ASS
generator can declare the exact font that was measured. This matters
especially on a server: measuring with one font file but declaring a
different name in the ASS style causes the video player to substitute a
different-width font at playback, which misplaces every furigana
reading — worse the further into the line it is — and the deployment
machine's exact installed fonts aren't always known ahead of time.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from PIL import ImageFont

from .models import (
    FuriganaPart,
    FuriganaSegment,
    PositionedEvent,
    PositionedLine,
    PositionedPart,
    SubtitleEvent,
)
from .utils import resolve_font_path

logger = logging.getLogger(__name__)

# pysubs2 represents a hard line break within a single event's text as
# this literal two-character token (the same token ASS itself uses).
LINE_BREAK = r"\N"


@dataclass(frozen=True)
class LayoutConfig:
    """Fixed V1 layout parameters.

    These are intentionally hard-coded defaults rather than a settings
    page (out of scope for V1) but are grouped here so a future version
    (e.g. per-request overrides via the API) can expose them without
    touching the layout math itself.
    """

    play_res_x: int = 1920
    play_res_y: int = 1080
    main_font_size: int = 64
    furigana_font_size: int = 32
    furigana_gap: int = 6  # px between furigana baseline and top of main text
    row_spacing: int = 12  # px between stacked rows for multi-line subtitles
    bottom_margin: int = 60
    font_path: Optional[str] = None  # None -> auto-resolve via utils.resolve_font_path
    font_index: int = 0  # face index within font_path, only used if font_path is set
    debug: bool = False  # print per-token layout diagnostics before ASS generation


class LayoutEngine:
    """Measures text with Pillow and computes \\pos() coordinates.

    Construction loads a font file — on a server, build ONE instance at
    startup and reuse it across every request rather than reconstructing
    per call.
    """

    def __init__(self, config: Optional[LayoutConfig] = None) -> None:
        self.config = config or LayoutConfig()
        font_path, font_index = resolve_font_path(self.config.font_path, self.config.font_index)
        self._main_font = ImageFont.truetype(font_path, self.config.main_font_size, index=font_index)
        self._furigana_font = ImageFont.truetype(
            font_path, self.config.furigana_font_size, index=font_index
        )

        # The family name Pillow reports for this exact font/face — this is
        # what MUST be written into the ASS style, not an assumed name like
        # "Noto Sans JP", or measurement and playback will use different
        # fonts with different glyph widths.
        self.font_family_name: str = self._main_font.getname()[0]

        # Mutable, independent of the frozen `config` above: lets a caller
        # (e.g. a Streamlit checkbox) toggle debug collection per-call on a
        # single long-lived, cached engine instance without reconstructing
        # it or fighting dataclass immutability.
        self.debug: bool = self.config.debug

        # Structured per-unit diagnostics, populated when `debug` is True.
        # Not reset automatically — callers should clear this themselves
        # (`layout_engine.debug_log.clear()`) before each new conversion
        # they want isolated diagnostics for.
        self.debug_log: list[dict] = []

        logger.info(
            "Layout engine using font: %s (face index %d, family '%s')",
            font_path,
            font_index,
            self.font_family_name,
        )

    def _measure(self, text: str, font: "ImageFont.FreeTypeFont") -> float:
        """Pixel width of text in the given font, at its configured size."""
        if not text:
            return 0.0
        return font.getlength(text)

    def layout_event(
        self, event: SubtitleEvent, segments_by_row: list[list[FuriganaSegment]]
    ) -> PositionedEvent:
        """Compute positions for every visual row of a subtitle event."""
        cfg = self.config
        n_rows = len(segments_by_row)
        row_height = cfg.main_font_size + cfg.furigana_font_size + cfg.furigana_gap
        lines: list[PositionedLine] = []

        for row_index, segments in enumerate(segments_by_row):
            rows_from_bottom = n_rows - 1 - row_index
            baseline_y = cfg.play_res_y - cfg.bottom_margin - rows_from_bottom * (
                row_height + cfg.row_spacing
            )
            row_label = f"event#{event.index} row#{row_index}"
            lines.append(self._layout_row(segments, baseline_y, row_label))

        return PositionedEvent(subtitle_event=event, lines=lines)

    def _layout_row(
        self, segments: list[FuriganaSegment], baseline_y: float, row_label: str = ""
    ) -> PositionedLine:
        """Lay out one visual row: measure every unit, then position each
        independently, centering furigana only over its own unit's span.

        A "unit" here is a FuriganaPart — either a whole Sudachi token (for
        tokens that are entirely kanji, entirely kana, or otherwise not
        split) or a kanji-run sub-piece of a token when furigana_generator
        isolated it from surrounding okurigana (e.g. "食" within "食べる").
        Each unit is measured and positioned on its own; nothing is ever
        centered against the whole line except the line's own start x.
        """
        cfg = self.config

        units: list[tuple[str, FuriganaPart, float]] = []
        for seg in segments:
            for part in seg.parts:
                width = self._measure(part.text, self._main_font)
                units.append((seg.token.surface, part, width))

        total_width = sum(width for _, _, width in units)
        # The line's own start position is the ONE place total width is
        # used — purely to center the row as a whole on screen. Every
        # furigana position below is computed relative to its own unit,
        # never relative to this total.
        line_start_x = (cfg.play_res_x - total_width) / 2

        positioned: list[PositionedPart] = []
        debug_rows = []
        cursor_x = line_start_x
        for token_surface, part, width in units:
            x_start = cursor_x
            x_end = cursor_x + width
            furigana_center_x = (x_start + x_end) / 2 if part.furigana else None

            positioned.append(
                PositionedPart(
                    text=part.text,
                    x_start=x_start,
                    x_end=x_end,
                    furigana=part.furigana,
                    furigana_center_x=furigana_center_x,
                )
            )

            if self.debug:
                debug_rows.append(
                    (token_surface, part.text, width, x_start, part.furigana, furigana_center_x)
                )

            cursor_x = x_end

        if self.debug and debug_rows:
            self._log_debug(row_label, debug_rows)

        return PositionedLine(
            parts=positioned,
            baseline_y=baseline_y,
            line_start_x=line_start_x,
            line_end_x=cursor_x,
        )

    def _log_debug(self, row_label: str, debug_rows: list[tuple]) -> None:
        """Record per-unit layout diagnostics: to the logger (for CLI/console
        use) and to `self.debug_log` as structured dicts (for programmatic
        or UI consumption, e.g. a Streamlit table — console prints aren't
        readable from there)."""
        logger.debug("--- Layout debug: %s ---", row_label)
        for token_surface, surface, width, x_position, furigana, furigana_x in debug_rows:
            logger.debug(
                "Token: %s | surface: %s | width: %.2f | x position: %.2f | "
                "furigana: %s | furigana x position: %s",
                token_surface,
                surface,
                width,
                x_position,
                furigana if furigana else "-",
                f"{furigana_x:.2f}" if furigana_x is not None else "-",
            )
            self.debug_log.append(
                {
                    "row": row_label,
                    "token": token_surface,
                    "surface": surface,
                    "width": round(width, 2),
                    "x_position": round(x_position, 2),
                    "furigana": furigana if furigana else "-",
                    "furigana_x_position": round(furigana_x, 2) if furigana_x is not None else "-",
                }
            )
