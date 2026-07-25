"""Main conversion pipeline: SRT -> tokenize -> furigana -> layout -> ASS.

This module is intentionally thin — it wires the other modules together
and translates their exceptions into a single ConversionError with a
user-facing message, but contains no parsing/tokenizing/layout logic
itself.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Optional, Union

from . import ass_generator
from .furigana_generator import generate_furigana_for_line
from .layout_engine import LINE_BREAK, LayoutConfig, LayoutEngine
from .models import PositionedEvent, SubtitleEvent
from .subtitle_parser import SubtitleParseError, load_srt
from .tokenizer import JapaneseTokenizer, TokenizerError

logger = logging.getLogger(__name__)


class ConversionError(Exception):
    """Raised for any failure in the end-to-end conversion pipeline.

    Wraps lower-level exceptions (missing file, bad SRT, missing
    dictionary, missing font, etc.) so callers only need to handle one
    error type with a message safe to show a user.
    """


def convert_srt_to_ass(
    input_file: Union[str, Path],
    output_file: Optional[Union[str, Path]] = None,
    config: Optional[LayoutConfig] = None,
    debug: bool = False,
    tokenizer: Optional[JapaneseTokenizer] = None,
    layout_engine: Optional[LayoutEngine] = None,
) -> str:
    """Convert a Japanese .srt file into a furigana-annotated .ass file.

    Args:
        input_file: Path to the source .srt file.
        output_file: Path for the output .ass file. Defaults to
            "<input_stem>_furigana.ass" next to the input file.
        config: Optional LayoutConfig override. Only used if
            `layout_engine` is not provided (a pre-built engine already
            carries its own config).
        debug: If True, logs per-token layout diagnostics before the ASS
            file is generated. Only applies when `layout_engine` is not
            provided, so a shared/long-lived engine's config isn't
            mutated out from under other concurrent callers.
        tokenizer: An optional pre-built JapaneseTokenizer to reuse
            (dictionary loading is slow) instead of constructing a new
            one. A server should build this once at startup and pass it
            into every call.
        layout_engine: An optional pre-built LayoutEngine to reuse
            (font loading + measurement setup) for the same reason.

    Returns:
        The path to the written .ass file, as a string.

    Raises:
        ConversionError: for any failure — missing/invalid input file,
            missing Sudachi dictionary, missing font, or an empty result.
    """
    input_path = Path(input_file)
    output_path = (
        Path(output_file)
        if output_file
        else input_path.with_name(f"{input_path.stem}_furigana.ass")
    )

    try:
        events = load_srt(input_path)
    except (FileNotFoundError, SubtitleParseError) as exc:
        raise ConversionError(str(exc)) from exc

    if tokenizer is None:
        try:
            tokenizer = JapaneseTokenizer()
        except TokenizerError as exc:
            raise ConversionError(str(exc)) from exc

    if layout_engine is None:
        try:
            engine_config = replace(config, debug=True) if (debug and config) else (
                LayoutConfig(debug=True) if debug else config
            )
            layout_engine = LayoutEngine(engine_config)
        except FileNotFoundError as exc:
            raise ConversionError(str(exc)) from exc
    else:
        # Reused engine (e.g. a Streamlit-cached or FastAPI-startup
        # singleton): toggle its runtime debug flag for this call rather
        # than mutating its frozen config or reconstructing it.
        layout_engine.debug = debug

    positioned_events: list[PositionedEvent] = []
    for event in events:
        try:
            positioned_events.append(_process_event(event, tokenizer, layout_engine))
        except TokenizerError as exc:
            logger.warning("Skipping event %d due to a tokenizer error: %s", event.index, exc)

    if not positioned_events:
        raise ConversionError("No subtitle events could be processed.")

    ass_content = ass_generator.build_ass(
        positioned_events, layout_engine.config, font_name=layout_engine.font_family_name
    )
    ass_generator.save_ass(ass_content, output_path)

    logger.info("Converted %d subtitle events -> %s", len(positioned_events), output_path)
    return str(output_path)


def _process_event(
    event: SubtitleEvent, tokenizer: JapaneseTokenizer, layout_engine: LayoutEngine
) -> PositionedEvent:
    """Tokenize, generate furigana for, and lay out a single subtitle event.

    A subtitle event may span multiple visual rows (original \\N breaks);
    each row is tokenized and laid out independently so furigana aligns
    correctly with the kanji on its own row.
    """
    rows = event.text.split(LINE_BREAK) if event.text else [""]
    segments_by_row = [
        generate_furigana_for_line(tokenizer.tokenize(row_text)) for row_text in rows
    ]
    return layout_engine.layout_event(event, segments_by_row)
