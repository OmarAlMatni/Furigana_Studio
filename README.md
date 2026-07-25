# Furigana Studio — Streamlit App

Pure Python, single process: Streamlit handles the UI, the same script
drives the conversion engine directly. No separate frontend, no REST
API, no CORS to configure. Upload a `.srt`, click **Generate
Furigana**, download the `.ass`.

## A note on which engine version this is built on

This app is built on the most up-to-date version of the engine from
this project's history, **not** the zip most recently uploaded (which
matched an earlier version, before two fixes were made). Specifically,
this carries forward:

1. **Font-name sync** — the ASS style always declares whichever font
   was actually measured with (read back from the font file itself via
   `LayoutEngine.font_family_name`), never a hardcoded assumed name.
   Declaring a font name that doesn't match what was measured causes
   the video player to substitute a different-width font at playback,
   which misaligns every furigana reading.
2. **Broader Windows font search** — including the per-user font
   install location (`%LOCALAPPDATA%\Microsoft\Windows\Fonts`), which
   is easy to miss since fonts installed via "Install" (not "Install
   for all users") land there instead of `C:\Windows\Fonts`.
3. **A warning for known-risky font families** — specifically Yu
   Gothic, which ships as several separate weight files
   (`yugothr.ttc`, `YuGothM.ttc`, `YuGothL.ttc`, `yugothb.ttc`) that
   Windows can register under the same or very similar family names.
   Pillow measuring one specific file directly by path doesn't
   guarantee a video player's own font substitution resolves the
   declared family name back to that *same* file — so even with fix
   #1 in place, this specific family can still misalign furigana. The
   app now surfaces a warning in the UI when this font is in use,
   recommending Noto Sans JP instead.

If you were mid-troubleshooting a "furigana not directly above kanji"
issue with the FastAPI/React version, #3 above is very likely what you
were hitting — the font-name mismatch in #1 was already fixed at that
point, but the underlying font *file* your Windows machine picked
(`YuGothM.ttc`, reported as family "Yu Gothic") is exactly the kind of
font this warning is designed to catch.

## Project structure

```
furigana_streamlit/
├── app.py                    -- Streamlit UI + orchestration (the only web-specific code)
├── engine/                    -- conversion engine (framework-agnostic, unchanged logic)
│   ├── models.py
│   ├── utils.py
│   ├── subtitle_parser.py
│   ├── tokenizer.py
│   ├── furigana_generator.py
│   ├── layout_engine.py
│   ├── ass_generator.py
│   └── converter.py
├── requirements.txt
├── test.srt
└── README.md
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Font requirement

Pillow measures text using an actual font **file**, not just a family
name. `engine/utils.py` auto-searches common install locations (Noto
Sans JP, Noto Sans CJK, per-user and system-wide Windows font
directories, Meiryo, Yu Gothic as a last resort) at startup.

**For the most reliable results, install Noto Sans JP explicitly**
rather than relying on whatever the OS happens to already have:

- Download it from Google Fonts (search "Noto Sans JP") and install it
  normally (double-click the `.otf`/`.ttf` → Install).
- Or, to bypass auto-detection entirely and guarantee a specific file
  is used, edit the `load_layout_engine()` function in `app.py`:

  ```python
  @st.cache_resource(show_spinner="Loading font for layout…")
  def load_layout_engine() -> LayoutEngine:
      from engine.layout_engine import LayoutConfig
      return LayoutEngine(LayoutConfig(font_path="/path/to/NotoSansJP-Regular.otf"))
  ```

If no usable font is found at all, the app shows an error on startup
instead of silently mis-measuring every conversion.

## Running

```bash
streamlit run app.py
```

Opens at `http://localhost:8501` by default. The Sudachi dictionary
and font are loaded **once per server process** (via
`@st.cache_resource`) and reused across every conversion in that
session — both are relatively slow to initialize.

## Using the app

1. Upload a `.srt` file (or use the included `test.srt`).
2. Optionally check **Show layout debug info** to see a table of every
   token's surface text, pixel width, x position, furigana, and
   furigana x position — the same diagnostic data the desktop/CLI
   version could print, shown here as an actual table instead of
   console output.
3. Click **Generate Furigana**.
4. Click **Download .ass file** once conversion finishes.

## Limitations (same as the underlying engine)

- Fixed V1 layout parameters: 1920×1080, 64px main / 32px furigana
  text, 60px bottom margin. Not yet exposed as UI controls.
- Placement accuracy depends on the server machine's font matching
  exactly what the video player uses at playback — see the font notes
  above.
- Single-file conversion only, no batch processing.
- This is a local single-user tool, not designed for multiple
  concurrent users sharing one Streamlit process — `layout_engine.debug_log`
  in particular is shared, unscoped, mutable state across sessions.
