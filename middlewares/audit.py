# -*- coding: utf-8 -*-
"""Global audit middleware for commands and update actions."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, ChosenInlineResult, InlineQuery, Message, TelegramObject

from loggers import format_chat, format_user, schedule_audit_telegram


def _extract_command(text: str) -> str:
    raw = (text or "").strip()
    if not raw.startswith("/"):
        return ""
    return raw.split()[0].lstrip("/").split("@")[0].lower()


class AuditMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            cmd = _extract_command(event.text or event.caption or "")
            if cmd:
                ch = format_chat(event.chat)
                schedule_audit_telegram(
                    "command_used",
                    action="command",
                    command=cmd,
                    user=format_user(event.from_user),
                    chat=ch,
                    chat_link=ch.get("chat_link", ""),
                    message_id=getattr(event, "message_id", None),
                )
        elif isinstance(event, CallbackQuery):
            ch = format_chat(event.message.chat if event.message else None)
            schedule_audit_telegram(
                "callback_used",
                action="callback",
                callback_data=(event.data or "")[:128],
                user=format_user(event.from_user),
                chat=ch,
                chat_link=ch.get("chat_link", ""),
                message_id=getattr(event.message, "message_id", None) if event.message else None,
            )
        elif isinstance(event, InlineQuery):
            schedule_audit_telegram(
                "inline_query",
                action="inline_query",
                query=(event.query or "")[:128],
                user=format_user(event.from_user),
            )
        elif isinstance(event, ChosenInlineResult):
            schedule_audit_telegram(
                "inline_chosen_result",
                action="inline_chosen",
                result_id=(event.result_id or "")[:128],
                query=(event.query or "")[:128],
                user=format_user(event.from_user),
            )
        return await handler(event, data)

