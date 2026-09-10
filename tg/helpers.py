# -*- coding: utf-8 -*-
"""Async Telegram helpers for Aiogram 3."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Optional, Sequence, Union

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineQueryResultUnion,
    ReplyKeyboardMarkup,
)

from tg.markup import reply_markup_from_dict

logger = logging.getLogger(__name__)

ReplyMarkup = Optional[Union[InlineKeyboardMarkup, ReplyKeyboardMarkup]]

# Telegram rejects some <tg-emoji> (wrong id / inner char); strip to placeholder on retry.
_TG_EMOJI_HTML_RE = re.compile(
    r'<tg-emoji emoji-id="[0-9]+">([\s\S]*?)</tg-emoji>',
    re.IGNORECASE,
)


def html_without_tg_emoji(text: str) -> str:
    """Remove premium <tg-emoji> wrappers; keep inner character(s) for plain display."""
    return _TG_EMOJI_HTML_RE.sub(lambda m: m.group(1), text)


def _parse_mode_is_html(parse_mode: Optional[Union[str, ParseMode]]) -> bool:
    if parse_mode is None:
        return False
    if parse_mode is ParseMode.HTML:
        return True
    return str(parse_mode).upper() == "HTML"


async def get_bot_username(bot: Bot) -> str:
    me = await bot.get_me()
    return me.username or ""

_admin_cache: dict[int, tuple[list[int], float]] = {}
_ADMIN_TTL = 3600.0


async def get_admin_ids(bot: Bot, chat_id: int) -> list[int]:
    now = time.time()
    hit = _admin_cache.get(chat_id)
    if hit and now - hit[1] < _ADMIN_TTL:
        return hit[0]
    admins = await bot.get_chat_administrators(chat_id)
    ids = [m.user.id for m in admins if m.user]
    _admin_cache[chat_id] = (ids, now)
    return ids


async def user_is_admin_aiogram(user, bot: Bot, chat) -> bool:
    if not chat:
        return False
    try:
        admins = await get_admin_ids(bot, chat.id)
        return user.id in admins
    except Exception:
        logger.exception("user_is_admin_aiogram failed chat_id=%s", getattr(chat, "id", None))
        return False


async def user_is_creator_or_admin_aiogram(user, game, bot: Bot, chat) -> bool:
    from utils import user_is_creator

    if user_is_creator(user, game):
        return True
    return await user_is_admin_aiogram(user, bot, chat)


async def answer_callback_query_safe(
    query: CallbackQuery,
    text: Optional[str] = None,
    show_alert: bool = False,
    url: Optional[str] = None,
    cache_time: int = 0,
) -> Optional[bool]:
    """Acknowledge callback; ignore expired or invalid queries (same idea as PTB utils)."""
    try:
        return await query.answer(
            text=text,
            show_alert=show_alert,
            url=url,
            cache_time=cache_time,
        )
    except TelegramBadRequest as e:
        es = str(e).lower()
        if "too old" in es or "query is invalid" in es or "query_id_invalid" in es:
            return None
        raise


async def safe_edit_message_text(
    query: CallbackQuery,
    text: str,
    reply_markup: Any = None,
    parse_mode: Optional[Union[str, ParseMode]] = ParseMode.HTML,
    *,
    entities: Any = None,
) -> None:
    """Edit message from a callback; swallow harmless Telegram errors."""
    if not query.message:
        return
    rk = reply_markup_from_dict(reply_markup) if reply_markup is not None else None
    try:
        kwargs: dict = {
            "text": text,
            "reply_markup": rk,
            "disable_web_page_preview": True,
        }
        if entities is not None:
            kwargs["entities"] = entities
            kwargs["parse_mode"] = None
        else:
            kwargs["parse_mode"] = parse_mode
        await query.message.edit_text(**kwargs)
    except TelegramBadRequest as e:
        es = str(e).lower()
        if "not modified" in es or "message is not modified" in es:
            return
        if "message to edit not found" in es:
            logger.debug("safe_edit_message_text: %s", e)
            return
        if "message can't be edited" in es:
            logger.debug("safe_edit_message_text: %s", e)
            return
        if (
            "entity_text_invalid" in es
            and entities is None
            and _parse_mode_is_html(parse_mode)
            and text
            and "<tg-emoji" in text.lower()
        ):
            try:
                kwargs["text"] = html_without_tg_emoji(text)
                await query.message.edit_text(**kwargs)
                logger.warning(
                    "safe_edit_message_text: ENTITY_TEXT_INVALID, retried without <tg-emoji>"
                )
                return
            except TelegramBadRequest:
                raise
        raise


async def send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    reply_markup: Any = None,
    parse_mode: Optional[Union[str, ParseMode]] = None,
    reply_to_message_id: Optional[int] = None,
    disable_web_page_preview: bool = False,
    **kwargs: Any,
) -> None:
    rk = reply_markup_from_dict(reply_markup) if reply_markup is not None else None
    try:
        await bot.send_message(
            chat_id,
            text,
            reply_markup=rk,
            parse_mode=parse_mode,
            reply_to_message_id=reply_to_message_id,
            disable_web_page_preview=disable_web_page_preview,
            **kwargs,
        )
    except TelegramBadRequest as e:
        es = str(e).lower()
        if (
            _parse_mode_is_html(parse_mode)
            and "entity_text_invalid" in es
            and text
            and "<tg-emoji" in text.lower()
        ):
            try:
                await bot.send_message(
                    chat_id,
                    html_without_tg_emoji(text),
                    reply_markup=rk,
                    parse_mode=parse_mode,
                    reply_to_message_id=reply_to_message_id,
                    disable_web_page_preview=disable_web_page_preview,
                    **kwargs,
                )
                logger.warning(
                    "send_message: ENTITY_TEXT_INVALID, retried without <tg-emoji> "
                    "chat_id=%s",
                    chat_id,
                )
                return
            except Exception:
                logger.exception(
                    "send_message fallback failed chat_id=%s", chat_id
                )
                return
        logger.exception("send_message failed chat_id=%s", chat_id)
    except Exception:
        logger.exception("send_message failed chat_id=%s", chat_id)


async def delete_game_turn_prompt_safe(bot: Bot, game: Any) -> None:
    """Remove the previous turn / inline prompt message if the bot still can."""
    mid = getattr(game, "turn_prompt_message_id", None)
    if mid is None:
        return
    chat = getattr(game, "chat", None)
    chat_id = getattr(chat, "id", None) if chat is not None else None
    try:
        if chat_id is not None:
            await bot.delete_message(chat_id, mid)
    except TelegramBadRequest as e:
        logger.debug(
            "delete_game_turn_prompt: chat_id=%s msg_id=%s %s",
            chat_id,
            mid,
            e,
        )
    except Exception:
        logger.debug(
            "delete_game_turn_prompt failed chat_id=%s msg_id=%s",
            chat_id,
            mid,
            exc_info=True,
        )
    finally:
        game.turn_prompt_message_id = None


async def send_game_turn_prompt(
    bot: Bot,
    game: Any,
    text: str,
    *,
    reply_markup: Any = None,
    parse_mode: Optional[Union[str, ParseMode]] = None,
    reply_to_message_id: Optional[int] = None,
    disable_web_page_preview: bool = False,
    **kwargs: Any,
) -> None:
    """
    Replace the group's turn prompt: post the new prompt first, then remove the old
    one. Sending a *new* message (instead of editing the previous) keeps Telegram
    notifications and chat ordering predictable; deleting the old prompt afterward
    avoids a long delete-then-send gap before users see the update.
    """
    chat_id = game.chat.id
    rk = reply_markup_from_dict(reply_markup) if reply_markup is not None else None
    old_prompt_id = getattr(game, "turn_prompt_message_id", None)

    async def _do_send(body: str):
        return await bot.send_message(
            chat_id,
            body,
            reply_markup=rk,
            parse_mode=parse_mode,
            reply_to_message_id=reply_to_message_id,
            disable_web_page_preview=disable_web_page_preview,
            **kwargs,
        )

    try:
        sent = await _do_send(text)
        game.turn_prompt_message_id = sent.message_id
    except TelegramBadRequest as e:
        es = str(e).lower()
        if (
            _parse_mode_is_html(parse_mode)
            and "entity_text_invalid" in es
            and text
            and "<tg-emoji" in text.lower()
        ):
            try:
                sent = await _do_send(html_without_tg_emoji(text))
                game.turn_prompt_message_id = sent.message_id
                logger.warning(
                    "send_game_turn_prompt: ENTITY_TEXT_INVALID, retried without "
                    "<tg-emoji> chat_id=%s",
                    chat_id,
                )
            except Exception:
                logger.exception("send_game_turn_prompt fallback failed chat_id=%s", chat_id)
                return
        else:
            logger.exception("send_game_turn_prompt failed chat_id=%s", chat_id)
            return
    except Exception:
        logger.exception("send_game_turn_prompt failed chat_id=%s", chat_id)
        return

    # Drop the previous prompt after the new one is posted so the turn update is
    # visible immediately; delete in the background so the handler can finish faster.
    if old_prompt_id is not None and old_prompt_id != game.turn_prompt_message_id:

        async def _delete_old_prompt() -> None:
            try:
                await bot.delete_message(chat_id, old_prompt_id)
            except TelegramBadRequest as e:
                logger.debug(
                    "send_game_turn_prompt: delete old prompt chat_id=%s msg_id=%s %s",
                    chat_id,
                    old_prompt_id,
                    e,
                )
            except Exception:
                logger.debug(
                    "send_game_turn_prompt: delete old prompt failed chat_id=%s msg_id=%s",
                    chat_id,
                    old_prompt_id,
                    exc_info=True,
                )

        asyncio.create_task(_delete_old_prompt(), name="uno-delete-turn-prompt")


async def send_sticker(bot: Bot, chat_id: int, sticker: str, **kwargs: Any) -> None:
    try:
        await bot.send_sticker(chat_id, sticker=sticker, **kwargs)
    except Exception:
        logger.exception("send_sticker failed chat_id=%s", chat_id)


async def answer_inline_query(
    bot: Bot,
    inline_query_id: str,
    results: Sequence[InlineQueryResultUnion],
    *,
    cache_time: int = 0,
    switch_pm_text: Optional[str] = None,
    switch_pm_parameter: Optional[str] = None,
) -> None:
    try:
        await bot.answer_inline_query(
            inline_query_id,
            results=list(results),
            cache_time=cache_time,
            switch_pm_text=switch_pm_text,
            switch_pm_parameter=switch_pm_parameter,
        )
    except Exception:
        logger.exception("answer_inline_query failed")
