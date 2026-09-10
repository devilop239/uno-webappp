# -*- coding: utf-8 -*-
"""Premium small-caps + rotating custom emoji IDs for UI and inline descriptions."""

import itertools

from typing import Optional, Union

from aiogram.enums import MessageEntityType, ParseMode
from aiogram.types import InputTextMessageContent, MessageEntity

from config import BUTTON_EMOJI_IDS

# Latin letters → small-cap style (Telegram-safe subset).
_LOW = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
_SMALLCAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    _LOW + _LOW,
)

# Rotate through extended premium IDs (p1..p22 from config / defaults).
_PREMIUM_CYCLE = itertools.cycle("p%d" % i for i in range(1, 23))

# Placeholder for one UTF-16 code unit (required for custom_emoji entities).
_CUSTOM_EMOJI_PLACEHOLDER = "\u200b"


def utf16_len(s: str) -> int:
    """Length of string in UTF-16 code units (Telegram entity offsets)."""
    return len(s.encode("utf-16-le")) // 2


def smallcaps(text: str) -> str:
    """Apply stylized small caps to ASCII letters; leave digits/symbols unchanged."""
    if not text:
        return text
    return text.translate(_SMALLCAPS)


# Alias for backwards compatibility with modules that import 'sc'
sc = smallcaps


def next_premium_key() -> str:
    """Next BUTTON_EMOJI_IDS role key (p1..p22) for rotating premium icons."""
    return next(_PREMIUM_CYCLE)


def inline_label(text: str) -> str:
    """Smallcaps line for inline result titles / short descriptions."""
    return smallcaps(text) if text else text


def menu_title_bar(emoji: str, label: str) -> str:
    """Bold smallcaps line with a leading emoji (same tone as styled inline buttons)."""
    return "%s <b>%s</b>" % (emoji, smallcaps(label))


def menu_heading_bold(label: str) -> str:
    """Bold smallcaps only (no emoji), for subheads inside a longer message."""
    return "<b>%s</b>" % smallcaps(label)


def custom_emoji_heading_html(emoji_id: str, placeholder: str, title: str) -> str:
    """Leading Telegram premium <tg-emoji> + bold smallcaps title (ParseMode.HTML)."""
    return '<tg-emoji emoji-id="%s">%s</tg-emoji> %s' % (
        emoji_id,
        placeholder,
        menu_heading_bold(title),
    )


def premium_input_text(
    body: str,
    *,
    parse_mode: Optional[Union[str, ParseMode]] = None,
):
    """
    InputTextMessageContent with a leading Telegram custom emoji (premium sticker id).
    Rotates through BUTTON_EMOJI_IDS p1..p22. Use for inline result message bodies.
    """
    role = next_premium_key()
    eid = BUTTON_EMOJI_IDS.get(role) or BUTTON_EMOJI_IDS.get("emoji_btn")
    if eid is None:
        kwargs = {"message_text": body or " "}
        if parse_mode is not None:
            kwargs["parse_mode"] = parse_mode
        return InputTextMessageContent(**kwargs)
    text = _CUSTOM_EMOJI_PLACEHOLDER + (body if body is not None else "")
    if len(text) < 2:
        text = _CUSTOM_EMOJI_PLACEHOLDER + " "
    ent = MessageEntity(
        type=MessageEntityType.CUSTOM_EMOJI,
        offset=0,
        length=1,
        custom_emoji_id=str(eid),
    )
    kwargs = {"message_text": text, "entities": [ent]}
    if parse_mode is not None:
        kwargs["parse_mode"] = parse_mode
    return InputTextMessageContent(**kwargs)
