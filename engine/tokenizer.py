"""Japanese tokenization via SudachiPy.

Wraps the Sudachi morphological analyzer to produce Token objects with
surface form, hiragana reading, and dictionary form.
"""
from __future__ import annotations

import logging

import jaconv
from sudachipy import dictionary
from sudachipy import tokenizer as sudachi_tokenizer

from .models import Token
from .utils import contains_kanji

logger = logging.getLogger(__name__)

# Mode C = longest-unit segmentation (closest to how a word would be
# written/read as a single unit, e.g. keeps 学校 together rather than
# splitting into finer morphemes).
_SPLIT_MODE = sudachi_tokenizer.Tokenizer.SplitMode.C


class TokenizerError(Exception):
    """Raised when the Sudachi tokenizer cannot be initialized or used."""


class JapaneseTokenizer:
    """Thin wrapper around SudachiPy.

    Dictionary loading is relatively slow, so on a server this class
    should be instantiated once at startup and reused across requests —
    it holds no per-request mutable state, so sharing one instance is safe.
    """

    def __init__(self) -> None:
        try:
            self._tokenizer_obj = dictionary.Dictionary(dict="core").create()
        except Exception as exc:
            raise TokenizerError(
                "Could not load the SudachiDict-Core dictionary. Make sure "
                "'sudachidict-core' is installed (pip install sudachidict-core)."
            ) from exc

    def tokenize(self, text: str) -> list[Token]:
        """Tokenize a line of Japanese text into Token objects.

        Args:
            text: A single subtitle row, possibly mixed with punctuation,
                numbers, or other scripts.

        Returns:
            Tokens in original left-to-right order, covering the entire
            input text with no gaps (so re-joining all token surfaces
            reproduces the original text exactly).
        """
        if not text:
            return []

        try:
            morphemes = self._tokenizer_obj.tokenize(text, _SPLIT_MODE)
        except Exception as exc:
            raise TokenizerError(f"Sudachi failed to tokenize text: {exc}") from exc

        tokens: list[Token] = []
        for m in morphemes:
            surface = m.surface()
            reading_katakana = m.reading_form() or surface
            reading_hiragana = jaconv.kata2hira(reading_katakana)
            tokens.append(
                Token(
                    surface=surface,
                    reading_hiragana=reading_hiragana,
                    dictionary_form=m.dictionary_form(),
                    contains_kanji=contains_kanji(surface),
                )
            )
        return tokens
