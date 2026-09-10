# -*- coding: utf-8 -*-
"""Numeric callback_data: pick which group game when user is in several chats."""

import logging
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery

from ui.inline_buttons import btn_switch_query, markup
from internationalization import _
from shared_vars import gm
from tg.helpers import answer_callback_query_safe, safe_edit_message_text

logger = logging.getLogger(__name__)

router = Router(name="select")

_NUM = re.compile(r"^-?\d+$")


@router.callback_query(F.data.func(lambda d: bool(d and _NUM.match(d))))
async def select_game(query: CallbackQuery, bot) -> None:
    try:
        chat_id = int(query.data)
    except (TypeError, ValueError):
        logger.info(
            "select_game: invalid callback data %r", getattr(query, "data", None)
        )
        await answer_callback_query_safe(query, text=_("Invalid selection."))
        return

    user_id = query.from_user.id
    gm.prune_stale_player_refs_for_user(user_id)
    players = gm.userid_players.get(user_id) or []
    if not players:
        logger.debug("select_game: no player mappings for user_id=%s", user_id)
        await answer_callback_query_safe(
            query,
            text=_("You are not in any active game."),
        )
        return

    active = gm.get_active_game(chat_id)
    chosen = None
    for player in players:
        if player.game.chat.id != chat_id:
            continue
        if active is not None and player.game is active:
            chosen = player
            break
        if chosen is None:
            chosen = player
    if chosen is not None:
        gm.userid_current[user_id] = chosen
    else:
        await answer_callback_query_safe(query, text=_("Game not found."))
        return

    back = [[btn_switch_query(_("Back to last group"), "", "default")]]
    await answer_callback_query_safe(
        query,
        text=_("Please switch to the group you selected!"),
        show_alert=False,
    )
    cur = gm.userid_current.get(user_id)
    group_title = ""
    if cur is not None and cur.game and cur.game.chat:
        group_title = cur.game.chat.title or ""
    body = _(
        "Selected group: {group}\n"
        "<b>Make sure that you switch to the correct group!</b>"
    ).format(group=group_title)
    await safe_edit_message_text(
        query,
        text=body,
        reply_markup=markup(back),
    )
