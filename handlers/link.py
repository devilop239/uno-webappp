# -*- coding: utf-8 -*-
"""Sudo-only: export group invite link by chat id."""

from __future__ import annotations

import html
import logging
import re
from typing import Optional

from aiogram import Bot, Router
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import (
    ChatMemberAdministrator,
    ChatMemberOwner,
    Message,
)

from loggers import format_user, schedule_audit_telegram
from services import admin_acl

logger = logging.getLogger(__name__)

router = Router(name="link")

_CHAT_ID_RE = re.compile(r"-?\d+")


def _parse_chat_id(raw: str) -> Optional[int]:
    text = (raw or "").strip().strip("`").strip()
    if not text:
        return None
    match = _CHAT_ID_RE.search(text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except (TypeError, ValueError):
        return None


def _can_invite_users(member) -> bool:
    if isinstance(member, ChatMemberOwner):
        return True
    if isinstance(member, ChatMemberAdministrator):
        return bool(getattr(member, "can_invite_users", False))
    return False


@router.message(Command("link"))
async def cmd_link(message: Message, bot: Bot) -> None:
    user = message.from_user
    if not user or not admin_acl.is_sudo(user.id):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "<b>Usage</b>\n<code>/link &lt;chat_id&gt;</code>\n\n"
            "Example: <code>/link -1001234567890</code>\n\n"
            "The bot must be in that group/supergroup as an admin with "
            "<b>invite users via link</b> permission.",
            parse_mode=ParseMode.HTML,
        )
        return

    chat_id = _parse_chat_id(parts[1])
    if chat_id is None:
        await message.answer(
            "Invalid chat id. Use the numeric id (e.g. <code>-1001234567890</code>).",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        chat = await bot.get_chat(chat_id)
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        await message.answer(
            "Cannot load that chat. Check the id.\n<i>%s</i>"
            % html.escape(str(exc)),
            parse_mode=ParseMode.HTML,
        )
        return
    except Exception:
        logger.exception("link: get_chat failed chat_id=%s", chat_id)
        await message.answer("Failed to load chat info.")
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.answer(
            "Only <b>group</b> or <b>supergroup</b> ids are supported.",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        bot_id = bot.id or (await bot.get_me()).id
        member = await bot.get_chat_member(chat_id, bot_id)
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        await message.answer(
            "Cannot access that chat.\n"
            "Make sure the bot is a member and the id is correct.\n"
            "<i>%s</i>" % html.escape(str(exc)),
            parse_mode=ParseMode.HTML,
        )
        return
    except Exception:
        logger.exception("link: get_chat_member failed chat_id=%s", chat_id)
        await message.answer("Failed to check bot membership in that chat.")
        return

    if not _can_invite_users(member):
        await message.answer(
            "Bot is in that chat but <b>cannot invite users</b>.\n"
            "Promote the bot to admin and enable "
            "<b>Invite users via link</b> (add members), then try again.",
            parse_mode=ParseMode.HTML,
        )
        return

    invite_link: Optional[str] = None
    try:
        invite_link = await bot.export_chat_invite_link(chat_id)
    except Exception:
        logger.debug("export_chat_invite_link failed chat_id=%s", chat_id, exc_info=True)
        try:
            created = await bot.create_chat_invite_link(chat_id, name="Bot link")
            invite_link = getattr(created, "invite_link", None)
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            await message.answer(
                "Could not create an invite link.\n<i>%s</i>"
                % html.escape(str(exc)),
                parse_mode=ParseMode.HTML,
            )
            return
        except Exception:
            logger.exception("link: create_chat_invite_link failed chat_id=%s", chat_id)
            await message.answer("Failed to generate invite link for that chat.")
            return

    if not invite_link:
        await message.answer("No invite link returned for that chat.")
        return

    plain_title = chat.title or str(chat_id)
    chat_type = html.escape(str(chat.type or ""))

    schedule_audit_telegram(
        "link_extracted",
        action="link",
        actor=format_user(user),
        chat_id=chat_id,
        chat_title=plain_title,
    )

    lines = [
        "<b>Invite link</b>",
        "Chat: <b>%s</b>" % html.escape(plain_title),
        "ID: <code>%d</code>" % chat_id,
        "Type: <code>%s</code>" % chat_type,
        "",
        invite_link,
    ]
    await message.answer(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
