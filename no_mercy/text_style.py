"""NO MERCY copy — smallcaps style (same as ɢᴀᴍᴇ / premium bot UI)."""
from __future__ import annotations

from ui.text_style import inline_label, smallcaps


def sc(text: str) -> str:
    """Smallcaps for plain chat / alert text."""
    return smallcaps(text) if text else text


def sc_bold(text: str) -> str:
    """Bold smallcaps for HTML messages."""
    return "<b>%s</b>" % sc(text)


def sc_inline(text: str) -> str:
    """Smallcaps for inline result titles / descriptions."""
    return inline_label(text)
