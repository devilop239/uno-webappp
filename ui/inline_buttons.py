# -*- coding: utf-8 -*-
"""Build inline_keyboard dicts with optional Telegram style + premium custom emoji icons."""

from config import BUTTON_EMOJI_IDS, INLINE_BUTTON_STYLES


def styles_on():
    return INLINE_BUTTON_STYLES and bool(BUTTON_EMOJI_IDS)


def _emoji_id(role):
    v = BUTTON_EMOJI_IDS.get(role)
    return str(v) if v is not None else None


def markup(rows):
    """Wrap rows as Telegram reply_markup dict."""
    return {"inline_keyboard": rows}


def btn_plain(text, callback_data):
    """Callback button without premium icon (clean card / control labels)."""
    return {"text": str(text), "callback_data": str(callback_data)}


def btn_callback(text, callback_data, flavor="default", icon_role=None):
    """
    flavor: primary | success | danger | default | emoji
    'emoji' sets only icon_custom_emoji_id (emoji_btn), no style field.
    icon_role: optional key in BUTTON_EMOJI_IDS (e.g. p1..p22) to override icon.
    """
    d = {"text": text, "callback_data": str(callback_data)}
    if not styles_on():
        return d
    if flavor == "emoji":
        eid = _emoji_id(icon_role or "emoji_btn")
        if eid:
            d["icon_custom_emoji_id"] = eid
        return d
    style_map = {
        "primary": "primary",
        "success": "success",
        "danger": "danger",
        "default": "default",
    }
    role_map = {
        "primary": "primary_btn",
        "success": "success_btn",
        "danger": "danger_btn",
        "default": "default_btn",
    }
    st = style_map.get(flavor, "default")
    d["style"] = st
    role = icon_role or role_map.get(flavor, "default_btn")
    eid = _emoji_id(role)
    if eid:
        d["icon_custom_emoji_id"] = eid
    return d


def btn_url(text, url, flavor="primary", icon_role=None):
    d = {"text": text, "url": url}
    if not styles_on():
        return d
    style_map = {
        "primary": "primary",
        "success": "success",
        "danger": "danger",
        "default": "default",
    }
    role_map = {
        "primary": "primary_btn",
        "success": "success_btn",
        "danger": "danger_btn",
        "default": "default_btn",
    }
    st = style_map.get(flavor, "primary")
    d["style"] = st
    role = icon_role or role_map.get(flavor, "primary_btn")
    eid = _emoji_id(role)
    if eid:
        d["icon_custom_emoji_id"] = eid
    return d


def btn_switch_current_chat(text, query="", flavor="success"):
    """switch_inline_query_current_chat (empty string = open inline for this chat)."""
    d = {"text": text, "switch_inline_query_current_chat": query or ""}
    if not styles_on():
        return d
    style_map = {
        "primary": "primary",
        "success": "success",
        "danger": "danger",
        "default": "default",
    }
    role_map = {
        "primary": "primary_btn",
        "success": "success_btn",
        "danger": "danger_btn",
        "default": "default_btn",
    }
    st = style_map.get(flavor, "success")
    d["style"] = st
    eid = _emoji_id(role_map.get(flavor, "success_btn"))
    if eid:
        d["icon_custom_emoji_id"] = eid
    return d


def btn_switch_query(text, query="", flavor="default"):
    """switch_inline_query (e.g. empty opens inline mode to pick a chat)."""
    d = {"text": text, "switch_inline_query": query or ""}
    if not styles_on():
        return d
    style_map = {
        "primary": "primary",
        "success": "success",
        "danger": "danger",
        "default": "default",
    }
    role_map = {
        "primary": "primary_btn",
        "success": "success_btn",
        "danger": "danger_btn",
        "default": "default_btn",
    }
    st = style_map.get(flavor, "default")
    d["style"] = st
    eid = _emoji_id(role_map.get(flavor, "default_btn"))
    if eid:
        d["icon_custom_emoji_id"] = eid
    return d
