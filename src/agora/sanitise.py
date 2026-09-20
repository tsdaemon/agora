"""Cleaning of remote text (listing fields, buyer messages) before it reaches the model.

Marketplace content is untrusted data. This does not make injected instructions harmless; it
removes the characters that hide them (control, format and bidi characters), bounds their size,
and lets callers return the text in a named data field instead of free prose.
"""

import unicodedata

ELLIPSIS = "…"
# Category "Cc" is dropped except newline and tab; "Cf" (zero-width, bidi overrides), surrogates,
# private-use and unassigned code points are always dropped.
_KEPT_CONTROLS = {"\n", "\t"}
_DROPPED_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn"}


def clean_text(value: str, max_length: int) -> str:
    """Return `value` with hidden characters removed, at most `max_length` characters long."""
    if max_length < 1:
        raise ValueError("max_length must be positive")
    text = unicodedata.normalize("NFC", value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        ch
        for ch in text
        if ch in _KEPT_CONTROLS or unicodedata.category(ch) not in _DROPPED_CATEGORIES
    )
    text = text.strip()
    if len(text) <= max_length:
        return text
    if max_length == 1:
        return ELLIPSIS
    return text[: max_length - 1].rstrip() + ELLIPSIS
