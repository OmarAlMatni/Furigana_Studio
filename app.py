"""Furigana Studio — Streamlit app."""

from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st
from engine.converter import ConversionError, convert_srt_to_ass
from engine.layout_engine import LayoutEngine
from engine.tokenizer import JapaneseTokenizer, TokenizerError
from engine.utils import is_risky_font_family, setup_logging

setup_logging()

st.set_page_config(page_title="Furigana Studio", page_icon="🌸", layout="centered")

# --- Background asset resolution ---
ASSETS_DIR = Path(__file__).parent / "assets"
_BACKGROUND_CANDIDATES = [
    "background.jpg",
    "background.png",
    "background.jpeg",
    "background.webp",
    "bg.png",
    "bg.jpg",
    "hero.png",
    "hero-bg.png",
    "hero_bg.png",
]
_IMAGE_MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def resolve_background_image() -> Optional[Path]:
    for name in _BACKGROUND_CANDIDATES:
        candidate = ASSETS_DIR / name
        if candidate.exists():
            return candidate

    if ASSETS_DIR.exists():
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            matches = sorted(ASSETS_DIR.glob(pattern))
            if matches:
                return matches[0]
    return None


@st.cache_data(show_spinner=False)
def background_image_data_uri(path_str: str) -> str:
    path = Path(path_str)
    mime = _IMAGE_MIME_TYPES.get(path.suffix.lstrip(".").lower(), "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


_bg_path = resolve_background_image()
if _bg_path is not None:
    _background_css = (
        f"linear-gradient(180deg, rgba(8,6,20,0.65) 0%, rgba(8,6,20,0.88) 100%), "
        f'url("{background_image_data_uri(str(_bg_path))}")'
    )
else:
    _background_css = (
        "radial-gradient(circle at 20% 10%, #2a1a3d 0%, #0d0a17 45%), "
        "linear-gradient(180deg, #120c1f 0%, #0a0714 100%)"
    )

# --- App Custom Styling ---
st.markdown(
    f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Noto+Sans+JP:wght@500;700;900&display=swap" rel="stylesheet">
    <style>
        :root {{
            --fs-pink: #f472b6;
            --fs-purple: #a78bfa;
            --fs-violet: #c084fc;
            --fs-glass-bg: rgba(20, 15, 38, 0.65);
        }}

        /* Hide Streamlit Chrome */
        #MainMenu, header[data-testid="stHeader"], footer {{
            visibility: hidden;
            height: 0;
        }}

        .stApp {{
            background-image: {_background_css};
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            direction: ltr !important;
        }}

        .stApp, .stApp p, .stApp span, .stApp label, .stApp div {{
            font-family: 'Poppins', sans-serif;
        }}

        .block-container {{
            max-width: 800px;
            padding-top: 7rem;
            padding-bottom: 3rem;
        }}

        /* Top Header */
        .fs-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 2rem;
        }}
        .fs-logo {{
            width: 42px;
            height: 42px;
            border-radius: 12px;
            background: linear-gradient(135deg, var(--fs-pink), var(--fs-purple));
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Noto Sans JP', sans-serif;
            font-weight: 700;
            font-size: 1.3rem;
            color: white;
            flex-shrink: 0;
        }}
        .fs-header-title {{
            font-weight: 600;
            font-size: 1.15rem;
            color: #f4f1fb;
        }}

        /* Hero */
        .fs-hero {{
            text-align: center;
            margin-bottom: 1.8rem;
        }}
        .fs-hero-title {{
            font-family: 'Noto Sans JP', sans-serif;
            font-weight: 900;
            font-size: clamp(2.1rem, 7vw, 3.2rem);
            margin: 0 0 6px;
            background: linear-gradient(90deg, var(--fs-pink) 0%, var(--fs-violet) 50%, var(--fs-purple) 100%);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            color: transparent;
            filter: drop-shadow(0 0 22px rgba(196, 132, 252, 0.35));
        }}
        .fs-hero-subtitle {{
            font-weight: 600;
            font-size: 0.95rem;
            letter-spacing: 0.35em;
            color: #e4defc;
            margin-bottom: 14px;
        }}
        .fs-hero-tagline {{
            font-size: 0.98rem;
            color: #cfc9e6;
        }}

        /* --- Clean Glassmorphism Dropzone Layout --- */
        div[data-testid="stFileUploader"] {{
            width: 100%;
        }}

        /* Dropzone Card Base */
        div[data-testid="stFileUploader"] section {{
            background: var(--fs-glass-bg) !important;
            border: 2px dashed rgba(216, 112, 147, 0.6) !important;
            border-radius: 18px !important;
            padding: 7.5rem 1.5rem !important;
            backdrop-filter: blur(12px) !important;
            transition: all 0.3s ease !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            text-align: center !important;
        }}

        div[data-testid="stFileUploader"] section:hover {{
            border-color: var(--fs-pink) !important;
            box-shadow: 0 0 22px rgba(238, 130, 238, 0.4) !important;
            transform: translateY(-2px);
        }}

        /* Center container inner layout */
        div[data-testid="stFileUploader"] section > div {{
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 12px !important;
            width: 100% !important;
        }}

        /* Text element styling */
        div[data-testid="stFileUploader"] section span,
        div[data-testid="stFileUploader"] section p {{
            color: #e0d0f5 !important;
            font-size: 0.95rem !important;
            text-align: center !important;
        }}

        /* Fix button positioning & layout inside dropzone */
        div[data-testid="stFileUploader"] section button {{
            background: rgba(138, 43, 226, 0.35) !important;
            border: 1px solid rgba(255, 105, 180, 0.5) !important;
            color: #ffffff !important;
            border-radius: 12px !important;
            padding: 0.5rem 1.2rem !important;
            margin-top: 8px !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
            transition: all 0.2s ease !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            position: relative !important;
        }}

        div[data-testid="stFileUploader"] section button:hover {{
            background: rgba(255, 105, 180, 0.4) !important;
            border-color: var(--fs-pink) !important;
        }}

        /* Clean up Streamlit's internal hidden/duplicate text elements */
        div[data-testid="stFileUploader"] button p {{
            color: #ffffff !important;
            margin: 0 !important;
            display: inline-block !important;
        }}

        /* --- HIDE EXTRA / ADD BUTTONS IN FILE UPLOADER --- */
        div[data-testid="stFileUploader"] [data-testid="stFileUploadDropzone"] + div,
        div[data-testid="stFileUploaderDeleteBtn"],
        div[data-testid="stFileUploader"] button[aria-label="Add files"],
        div[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] {{
            display: none !important;
        }}

        /* Streamlit's own native per-file row (filename + its delete
           button) is hidden unconditionally here — not because we know
           for certain the rule above already caught it, but so the
           custom filename+✕ row below is guaranteed to be the only one
           shown, regardless of exactly which selector is doing what. */
        [data-testid="stFileUploaderFile"] {{
            display: none !important;
        }}

        /* --- HIDE DEFAULT INSTRUCTION TEXT & INJECT "click to upload" --- */

        /* 1. Force collapse all default instruction children (Drag & Drop + 200MB text) */
        [data-testid="stFileUploaderDropzoneInstructions"] *,
        div[data-testid="stFileUploader"] section small,
        div[data-testid="stFileUploader"] section [data-testid="stCaptionContainer"] {{
            display: none !important;
            font-size: 0 !important;
            visibility: hidden !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}

        /* 2. Display custom "click to upload" subtext */
        [data-testid="stFileUploaderDropzoneInstructions"]::after {{
            content: "Click to upload" !important;
            visibility: visible !important;
            display: block !important;
            color: #cfc9e6 !important;
            font-size: 1.6rem !important;
            font-weight: 500 !important;
            text-align: center !important;
            margin-top: 4px !important;
            text-transform: lowercase !important;
        }}

        [data-testid="stFileUploaderDropzoneInstructions"] {{
           display: flex !important;
           justify-content: center !important;
           width: 100% !important;
         }}

        /* Delete button row: pulled UP into the box above via negative
           top margin, rather than position:absolute. Three prior
           attempts using position:absolute all landed wrong, because
           that technique depends on correctly identifying Streamlit's
           internal "nearest positioned ancestor" — unverifiable without
           an actual browser render, and guessed wrong each time.
           Negative margin has no such dependency: it's plain box-model
           math (pull this element up by N pixels, full stop), so the
           only real uncertainty is whether N is exactly right — a
           small, safe tuning value rather than "positioned against the
           wrong element entirely." margin-bottom restores normal
           spacing before the Generate button afterward, since pulling
           this row up would otherwise also drag that button closer.
           The exact -64px pull is estimated from the box's own
           padding (2.5rem \u2248 40px) plus this row's approximate
           natural height — likely close, may need a small nudge once
           actually rendered. */
        div[data-testid="stHorizontalBlock"] {{
            margin-top: -175px !important;
            margin-bottom: 1.1rem !important;
            padding: 0 1.3rem !important;
            position: relative;
            z-index: 3;
        }}
        button[kind="secondary"] {{
            background: rgba(138, 43, 226, 0.35) !important;
            border: 1px solid rgba(255, 105, 180, 0.55) !important;
            color: #ffffff !important;
            border-radius: 50% !important;
            font-weight: 600 !important;
            min-height: unset !important;
            width: 2.3rem !important;
            height: 2.3rem !important;
            padding: 0 !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
        }}
        button[kind="secondary"]:hover {{
            background: rgba(255, 105, 180, 0.5) !important;
            border-color: var(--fs-pink) !important;
        }}

        /* Generate & Download Action Buttons */
        button[kind="primary"] {{
            background: linear-gradient(90deg, #8a2be2, #ff69b4) !important;
            border: 1px solid rgba(196, 132, 252, 0.5) !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
            font-size: 1.05rem !important;
            height: 3.2rem !important;
            box-shadow: 0 4px 15px rgba(255, 105, 180, 0.4) !important;
            transition: all 0.3s ease !important;
            margin-top: 1rem !important;
        }}

        button[kind="primary"]:hover {{
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(255, 105, 180, 0.6) !important;
        }}

        .fs-footer {{
            text-align: center;
            font-size: 0.85rem;
            color: #8f85b0;
            margin-top: 3rem;
            padding-top: 1.2rem;
            border-top: 1px solid rgba(167, 139, 250, 0.18);
        }}
    </style>
    """,
    unsafe_allow_html=True,
)


# --- Engine resource loading ---
@st.cache_resource(show_spinner="Loading Japanese dictionary…")
def load_tokenizer() -> JapaneseTokenizer:
    return JapaneseTokenizer()


@st.cache_resource(show_spinner="Loading font for layout…")
def load_layout_engine() -> LayoutEngine:
    return LayoutEngine()


# --- Top Header ---


# --- Hero Section ---
st.markdown(
    """
    <div class="fs-hero">
        <div class="fs-hero-title">🌸 振り仮名スタジオ 🌸</div>
        <div class="fs-hero-subtitle">FURIGANA STUDIO</div>
        <div class="fs-hero-tagline">Convert Japanese .srt subtitles into anime-style .ass subtitles.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

engine_error: str | None = None
tokenizer: JapaneseTokenizer | None = None
layout_engine: LayoutEngine | None = None

try:
    tokenizer = load_tokenizer()
except TokenizerError as exc:
    engine_error = str(exc)

if engine_error is None:
    try:
        layout_engine = load_layout_engine()
    except FileNotFoundError as exc:
        engine_error = str(exc)

if engine_error:
    st.error(f"Conversion engine failed to load: {engine_error}")
    st.stop()

assert layout_engine is not None and tokenizer is not None

if is_risky_font_family(layout_engine.font_family_name):
    logging.getLogger(__name__).warning(
        "Using risky font family '%s'", layout_engine.font_family_name
    )

# --- File Uploader & State Management ---
# `uploader_key` is bumped to force Streamlit to remount the file_uploader
# with a blank state. st.file_uploader has no direct "clear" method, so
# changing its `key` (which makes Streamlit treat it as a brand-new
# widget) is the standard, documented way to reset an uploaded file.
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

uploaded_file = st.file_uploader(
    "Drop your Japanese subtitle file here (.srt)",
    type=["srt"],
    label_visibility="collapsed",
    key=f"file_uploader_{st.session_state.uploader_key}",
)

# Delete row: deliberately NOT absolutely positioned. Three rounds of
# trying to place this button precisely inside the box via
# position:absolute all landed wrong, because that technique depends on
# knowing Streamlit's exact internal wrapper/positioning-context chain —
# which isn't verifiable without an actual browser render. st.columns is
# normal document flow with no such dependency, and has already rendered
# correctly earlier in this app. It won't sit literally inside the
# dashed border, but the CSS below removes the gap and matches the box's
# background/border so it reads as one continuous attached piece rather
# than a separate section.
if uploaded_file is not None:
    _, clear_col = st.columns([0.50, 0.32])
    with clear_col:
        if st.button("✕", key="clear_uploaded_file", help="Remove this file"):
            st.session_state.uploader_key += 1
            st.session_state.uploaded_filename = None
            st.session_state.ready_file = None
            st.rerun()

# Reset output state if a new file is uploaded or removed
if (
    "uploaded_filename" not in st.session_state
    or st.session_state.uploaded_filename
    != (uploaded_file.name if uploaded_file else None)
):
    st.session_state.uploaded_filename = uploaded_file.name if uploaded_file else None
    st.session_state.ready_file = None

# If ready_file is set, show ONLY the Download button
if st.session_state.ready_file is not None:
    st.download_button(
        "💾 Download .ass Subtitle File",
        data=st.session_state.ready_file["bytes"],
        file_name=st.session_state.ready_file["filename"],
        mime="application/octet-stream",
        type="primary",
        use_container_width=True,
    )
else:
    # If not ready, show the Generate button
    convert_clicked = st.button(
        "✨ Generate Furigana Subtitle",
        disabled=uploaded_file is None,
        type="primary",
        use_container_width=True,
    )

    if convert_clicked and uploaded_file is not None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / uploaded_file.name
            input_path.write_bytes(uploaded_file.getvalue())
            output_path = input_path.with_name(f"{input_path.stem}_furigana.ass")

            layout_engine.debug_log.clear()

            with st.spinner("Converting — tokenizing and generating furigana…"):
                try:
                    convert_srt_to_ass(
                        input_path,
                        output_path,
                        debug=False,
                        tokenizer=tokenizer,
                        layout_engine=layout_engine,
                    )
                except ConversionError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.ready_file = {
                        "bytes": output_path.read_bytes(),
                        "filename": output_path.name,
                    }
                    st.rerun()

st.markdown(
    "<div class='fs-footer'>🌸 Made with ❤️ for the anime community 🌸</div>",
    unsafe_allow_html=True,
)
