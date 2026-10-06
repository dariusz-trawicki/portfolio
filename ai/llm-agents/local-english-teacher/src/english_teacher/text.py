"""Pure text helpers: cleaning LLM output for speech and parsing corrections."""

from __future__ import annotations

import re

CORRECTION_RE = re.compile(
    r"small correction:\s*you said\s*[\"“']?(.+?)[\"”']?\s*[,;]\s*"
    r"(?:it is |it's )?(?:a )?better (?:is|would be|to say)\s*[\"“']?(.+?)[\"”']?"
    r"\s*(?:[.!?](?:\s|$)|$)",
    re.IGNORECASE,
)

_MARKDOWN_RE = re.compile(r"[*#_`>\[\]{}|~]")
_ODD_CHARS_RE = re.compile(r"[^\w\s.,!?'\"\-:;()]")
_SPACES_RE = re.compile(r"\s+")


def clean_for_tts(text: str) -> str:
    """Strip markdown, emojis and odd symbols so the text sounds natural when spoken."""
    text = _MARKDOWN_RE.sub("", text)
    text = _ODD_CHARS_RE.sub("", text)
    return _SPACES_RE.sub(" ", text).strip()


def extract_correction(text: str) -> tuple[str, str] | None:
    """Parse 'Small correction: you said "X", better is "Y".' -> (X, Y)."""
    m = CORRECTION_RE.search(text)
    if not m:
        return None
    wrong, correct = m.group(1).strip(), m.group(2).strip()
    if wrong and correct and wrong.lower() != correct.lower():
        return wrong, correct
    return None
