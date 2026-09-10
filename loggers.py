# -*- coding: utf-8 -*-
"""
Structured audit logging for the UNO bot.

- Writes one JSON object per line to the `bot_audit` logger (stdout by default).
- Optionally mirrors selected events to a Telegram log group (see config.LOG_GROUP_ID).

Keep payloads small and avoid secrets (no tokens).
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from aiogram import Bot
from aiogram.enums import ParseMode

from config import LOG_GROUP_ID, LOG_TELEGRAM_ENABLED
from tg.runtime import get_bot_ref

logger = logging.getLogger(__name__)

_audit_logger = logging.getLogger("bot_audit")
_audit_logger.setLevel(logging.INFO)
if not _audit_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _audit_logger.addHandler(_handler)
    _audit_logger.propagate = False


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_user(user: Any) -> Dict[str, Any]:
    """Normalize a Telegram User (or similar) into a JSON-safe dict."""
    if user is None:
        return {}
    uid = getattr(user, "id", None)
    try:
        uid = int(uid) if uid is not None else None
    except (TypeError, ValueError):
        uid = None
    return {
        "user_id": uid,
        "first_name": (getattr(user, "first_name", None) or "") or "",
        "last_name": (getattr(user, "last_name", None) or "") or "",
        "username": (getattr(user, "username", None) or "") or "",
        "is_bot": bool(getattr(user, "is_bot", False)),
    }


def format_chat(chat: Any) -> Dict[str, Any]:
    if chat is None:
        return {}
    cid = getattr(chat, "id", None)
    try:
        cid = int(cid) if cid is not None else None
    except (TypeError, ValueError):
        cid = None
    username = (getattr(chat, "username", None) or "") or ""
    return {
        "chat_id": cid,
        "type": getattr(chat, "type", None),
        "title": (getattr(chat, "title", None) or "") or "",
        "username": username,
        "chat_link": ("https://t.me/%s" % username.strip()) if str(username).strip() else "",
    }


def log_event(event: str, telegram: bool = True, **fields: Any) -> Dict[str, Any]:
    """
    Record a structured audit event (JSON line) and optionally queue Telegram delivery.
    """
    payload: Dict[str, Any] = {"event": event, "ts": _utc_iso(), **fields}
    try:
        line = json.dumps(payload, ensure_ascii=False, default=str)
    except TypeError:
        payload["_serialization"] = "fallback"
        line = json.dumps(payload, ensure_ascii=False, default=str)
    _audit_logger.info(line)
    if telegram and LOG_TELEGRAM_ENABLED:
        schedule_audit_telegram_payload(payload)
    return payload


def schedule_audit_telegram_payload(payload: Dict[str, Any]) -> None:
    """Send payload JSON to the log group (async, fire-and-forget)."""
    if not LOG_TELEGRAM_ENABLED or LOG_GROUP_ID is None:
        return
    bot = get_bot_ref()
    if bot is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _send() -> None:
        try:
            body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
            text = "<pre>%s</pre>" % html.escape(body, quote=True)
            await bot.send_message(
                int(LOG_GROUP_ID),
                text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            logger.exception("audit telegram send failed event=%s", payload.get("event"))

    loop.create_task(_send())


def schedule_audit_telegram(event: str, telegram: bool = True, **fields: Any) -> None:
    """Sync-friendly: build payload, log to stdout, optionally Telegram."""
    log_event(event, telegram=telegram, **fields)


async def notify_bot_deployed(bot: Bot) -> None:
    """Call from Dispatcher startup: confirms polling is live."""
    payload = log_event(
        "bot_deployed",
        telegram=False,
        status="ok",
        message="Bot started successfully; polling is active.",
    )
    if not LOG_TELEGRAM_ENABLED or LOG_GROUP_ID is None:
        return
    try:
        body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        text = "<pre>%s</pre>" % html.escape(body, quote=True)
        await bot.send_message(
            int(LOG_GROUP_ID),
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception:
        logger.exception("notify_bot_deployed telegram failed")


def players_snapshot(game: Any) -> list:
    """Compact list of players in a Game for audit logs."""
    out = []
    try:
        for p in getattr(game, "players", []) or []:
            u = getattr(p, "user", None)
            out.append(format_user(u))
    except Exception:
        logger.exception("players_snapshot failed")
    return out
