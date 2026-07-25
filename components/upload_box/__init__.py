"""Furigana Studio conversion engine — SRT to furigana-annotated ASS.

Pure conversion logic, framework-agnostic. app/main.py wraps this in a
FastAPI service; nothing in this package depends on FastAPI or the web
layer at all, so it can also be used directly as a library or CLI.
"""
from components.upload_box.uploader import render_upload_box

__all__ = ["render_upload_box"]