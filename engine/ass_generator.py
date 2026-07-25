"""Generates a valid ASS (v4+) subtitle file from positioned events.

Produces two families of Dialogue lines per row: one "Main" line (the
full row of subtitle text, bottom-left anchored at its computed start
x) and one "Furigana" line per kanji-bearing word (bottom-center
anchored directly above that word). All lines for a given row share
identical timestamps so they render in perfect sync.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

from .layout_engine import LayoutConfig
from .models import PositionedEvent

logger = logging.getLogger(__name__)

_HEADER_TEMPLATE = """[Script Info]
Title: Furigana Studio Output
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{font_name},{main_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,0,1,20,20,{bottom_margin},1
Style: Furigana,{font_name},{furigana_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,1,20,20,{bottom_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ms_to_ass_time(ms: int) -> str:
    """Convert milliseconds to ASS timestamp format H:MM:SS.CC (centiseconds)."""
    total_cs = round(ms / 10)
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _dialogue_line(
    layer: int,
    start_ms: int,
    end_ms: int,
    style: str,
    pos_x: float,
    pos_y: float,
    align_tag: str,
    text: str,
) -> str:
    start = _ms_to_ass_time(start_ms)
    end = _ms_to_ass_time(end_ms)
    escaped_text = text.replace("\n", r"\N")
    return (
        f"Dialogue: {layer},{start},{end},{style},,0,0,0,,"
        f"{{{align_tag}\\pos({pos_x:.1f},{pos_y:.1f})}}{escaped_text}"
    )


def build_ass(
    positioned_events: list[PositionedEvent],
    config: LayoutConfig,
    font_name: str = "Noto Sans JP",
) -> str:
    """Render all positioned events into a complete ASS document string.

    Args:
        positioned_events: Output of the layout engine, one per subtitle event.
        config: The LayoutConfig used to compute those positions.
        font_name: Font family name written into the ASS style header.
            Should match the font actually used for width measurement
            (LayoutEngine.font_family_name) — see layout_engine.py.

    Returns:
        The full text content of a valid .ass file.
    """
    header = _HEADER_TEMPLATE.format(
        play_res_x=config.play_res_x,
        play_res_y=config.play_res_y,
        font_name=font_name,
        main_size=config.main_font_size,
        furigana_size=config.furigana_font_size,
        bottom_margin=config.bottom_margin,
    )

    dialogue_lines: list[str] = []
    for pos_event in positioned_events:
        se = pos_event.subtitle_event
        for row in pos_event.lines:
            # Main text: one Dialogue event PER PART (same granularity as
            # furigana below), each an2 bottom-center anchored at that
            # part's own pre-computed center x. This deliberately avoids
            # emitting the whole row as a single an1-anchored continuous
            # string: doing so makes correctness depend on the video
            # player's own internal text shaping of that continuous run
            # matching our externally-computed per-character width sum —
            # which in practice does not reliably hold across renderers/
            # fonts. Per-part an2 centering is self-correcting instead:
            # each piece is independently centered by the renderer using
            # its own live glyph metrics for exactly that isolated
            # substring, the same way Pillow measured it.
            for part in row.parts:
                part_center_x = (part.x_start + part.x_end) / 2
                dialogue_lines.append(
                    _dialogue_line(
                        layer=0,
                        start_ms=se.start_ms,
                        end_ms=se.end_ms,
                        style="Main",
                        pos_x=part_center_x,
                        pos_y=row.baseline_y,
                        align_tag=r"\an2",
                        text=part.text,
                    )
                )

            furigana_baseline_y = row.baseline_y - config.main_font_size - config.furigana_gap
            for part in row.parts:
                if not part.furigana or part.furigana_center_x is None:
                    continue
                dialogue_lines.append(
                    _dialogue_line(
                        layer=1,
                        start_ms=se.start_ms,
                        end_ms=se.end_ms,
                        style="Furigana",
                        pos_x=part.furigana_center_x,
                        pos_y=furigana_baseline_y,
                        align_tag=r"\an2",
                        text=part.furigana,
                    )
                )

    return header + "\n".join(dialogue_lines) + "\n"


def save_ass(content: str, output_path: Union[str, Path]) -> None:
    """Write ASS content to disk as UTF-8."""
    Path(output_path).write_text(content, encoding="utf-8")
    logger.info("Wrote ASS file: %s", output_path)