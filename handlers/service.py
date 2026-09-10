# -*- coding: utf-8 -*-
"""Service updates: member left group → remove from game."""

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import ChatMemberUpdated, Message

from errors import NoGameInChatError, NotEnoughPlayersError
from internationalization import __
from internationalization import pop_locale_stack_n, push_game_locales_for_user_chat
from loggers import format_chat, format_user, schedule_audit_telegram
from shared_vars import gm
from services.match_result_service import (
    capture_match_context,
    send_post_match_scoreboard,
)
from tg.helpers import delete_game_turn_prompt_safe, send_message
from utils import display_name_html

router = Router(name="service")

_ACTIVE_STATUSES = {"member", "administrator", "creator", "restricted"}
_REMOVED_STATUSES = {"left", "kicked"}


@router.my_chat_member()
async def bot_membership_audit(update: ChatMemberUpdated) -> None:
    """
    Audit when UNO bot is added to / removed from a group.
    Payload stays JSON-structured for easy parsing downstream.
    """
    old_status = str(getattr(update.old_chat_member, "status", "") or "").lower()
    new_status = str(getattr(update.new_chat_member, "status", "") or "").lower()
    chat = update.chat
    actor = update.from_user

    link = ""
    chat_username = (getattr(chat, "username", None) or "").strip()
    if chat_username:
        link = "https://t.me/%s" % chat_username
    elif getattr(update, "invite_link", None) is not None:
        link = str(getattr(update.invite_link, "invite_link", "") or "").strip()

    common = {
        "chat": format_chat(chat),
        "chat_link": link,
        "chat_id": getattr(chat, "id", None),
        "chat_title": getattr(chat, "title", None) or "",
        "actor": format_user(actor),
        "old_status": old_status,
        "new_status": new_status,
    }

    if old_status in _REMOVED_STATUSES and new_status in _ACTIVE_STATUSES:
        schedule_audit_telegram(
            "bot_added_to_group",
            action="bot_added_gc",
            **common,
        )
        return

    if old_status in _ACTIVE_STATUSES and new_status in _REMOVED_STATUSES:
        schedule_audit_telegram(
            "bot_removed_from_group",
            action="bot_removed_gc",
            **common,
        )
        return


@router.message(F.left_chat_member)
async def status_update(message: Message, bot) -> None:
    chat = message.chat
    user = message.left_chat_member
    if not user:
        return
    schedule_audit_telegram(
        "member_left_chat",
        action="member_left",
        chat=format_chat(chat),
        chat_link=(format_chat(chat).get("chat_link", "")),
        actor=format_user(user),
    )
    n = push_game_locales_for_user_chat(user, chat)
    try:
        player = gm.player_for_user_in_chat(user, chat)
        game = player.game if player else None

        try:
            gm.leave_game(user, chat)
        except NoGameInChatError:
            pass
        except NotEnoughPlayersError:
            if game is not None:
                await delete_game_turn_prompt_safe(bot, game)
            ctx = capture_match_context(game, fallback_user=user) if game is not None else {}
            gm.end_game(chat, user, reason="not_enough_players")
            if ctx:
                await send_post_match_scoreboard(bot, chat.id, ctx)
            schedule_audit_telegram(
                "group_game_ended_due_to_leave",
                action="game_end_leave",
                chat=format_chat(chat),
                chat_link=(format_chat(chat).get("chat_link", "")),
                actor=format_user(user),
            )
            await send_message(
                bot,
                chat.id,
                text=__("ɢᴀᴍᴇ ᴇɴᴅᴇᴅ!", multi=game.translate),
            )
        else:
            if game is not None:
                schedule_audit_telegram(
                    "member_removed_from_game",
                    action="leave_cleanup",
                    chat=format_chat(chat),
                    chat_link=(format_chat(chat).get("chat_link", "")),
                    actor=format_user(user),
                )
                await send_message(
                    bot,
                    chat.id,
                    text=__("Removing {name} from the game", multi=game.translate).format(
                        name=display_name_html(user)
                    ),
                    parse_mode=ParseMode.HTML,
                )
    finally:
        pop_locale_stack_n(n)
