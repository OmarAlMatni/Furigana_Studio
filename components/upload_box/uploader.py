import os
import json
import base64
import streamlit as st
import streamlit.components.v1 as components

def render_upload_box(key="furigana_uploader"):
    """
    Renders the custom HTML/CSS/JS upload box inside an isolated iframe.
    Bypasses declare_component file-server limitations entirely.
    """
    frontend_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "frontend")
    )
    
    html_path = os.path.join(frontend_dir, "index.html")
    css_path = os.path.join(frontend_dir, "style.css")
    js_path = os.path.join(frontend_dir, "component.js")

    # Read component frontend files
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    with open(css_path, "r", encoding="utf-8") as f:
        css_content = f.read()
    with open(js_path, "r", encoding="utf-8") as f:
        js_content = f.read()

    # Combine into a single standalone bundle
    bundled_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <style>
      {css_content}
      </style>
    </head>
    <body>
      {html_content}
      <script>
      {js_content}
      </script>
    </body>
    </html>
    """

    # Encode to Base64 to bypass iframe rendering / path loading glitches
    b64_html = base64.b64encode(bundled_html.encode("utf-8")).decode("utf-8")

    # Session state initialization for file receipt
    state_key = f"payload_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = None

    # JS Message Receiver Script in Python DOM
    receiver_js = f"""
    <script>
    window.addEventListener("message", (event) => {{
        if (event.data && event.data.type === "FURIGANA_FILE_SELECTED") {{
            const payload = event.data.payload;
            const inputElement = window.parent.document.getElementById("fs_hidden_file_data");
            if (inputElement) {{
                inputElement.value = JSON.stringify(payload);
                inputElement.dispatchEvent(new Event("change", {{ bubbles: true }}));
            }}
        }}
    }});
    </script>
    """
    components.html(receiver_js, height=0)

    # Render custom component iframe directly from inline Base64 data
    iframe_src = f"data:text/html;base64,{b64_html}"
    st.markdown(
        f'<iframe src="{iframe_src}" style="width:100%; height:220px; border:none; overflow:hidden;" scrolling="no"></iframe>',
        unsafe_allow_html=True
    )

    # Hidden input bridge to receive file data back into Python
    file_data_raw = st.text_input(
        "Hidden File Data", 
        key="fs_hidden_file_data", 
        label_visibility="collapsed"
    )

    # Hide the text input container via CSS so it never shows on screen
    st.markdown(
        """
        <style>
        div[element-id*="fs_hidden_file_data"], 
        div[data-testid="stTextInput"]:has(#fs_hidden_file_data) {
            display: none !important;
            height: 0px !important;
            margin: 0px !important;
            padding: 0px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    if file_data_raw:
        try:
            return json.loads(file_data_raw)
        except Exception:
            return None

    return None