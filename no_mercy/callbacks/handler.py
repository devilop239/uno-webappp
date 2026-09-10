"""Aiogram router for NO MERCY inline keyboard callbacks (nm|…)."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ParseMode

from actions import cancel_fast_countdown, do_draw, do_play_card, start_player_countdown
from no_mercy.callbacks.validator import validate
from no_mercy.ui import config as ui_cfg
from no_mercy.ui.keyboard import (
    opponent_at_index,
    playable_card_at_index,
)
from no_mercy.ui.locks import chat_lock
from no_mercy.ui.prompt import refresh_mercy_prompt, send_mercy_turn_prompt
from no_mercy.ui.renderer import render_hand_private
from no_mercy.ui.tokens import parse_callback
from tg.helpers import answer_callback_query_safe
from utils import game_is_running

logger = logging.getLogger(__name__)

router = Router(name="no_mercy_callbacks")


@router.callback_query(F.data.startswith("nm|"))
async def mercy_callback(query, bot) -> None:
    chat = query.message.chat if query.message else None
    if chat is None:
        await answer_callback_query_safe(query)
        return

    from shared_vars import gm
    game = gm.get_active_game(chat.id)
    if game is None or game.mode != "no_mercy":
        await answer_callback_query_safe(query, text="Not a NO MERCY game.", show_alert=True)
        return

    parsed = parse_callback(query.data or "")
    if parsed is None:
        await answer_callback_query_safe(query, text="Invalid button.", show_alert=True)
        return

    async with chat_lock(game):
        ok, player, err = validate(query, game)
        if not ok:
            await answer_callback_query_safe(query, text=err, show_alert=True)
            return

        game.mercy_callback_busy = True
        try:
            refresh_only = parsed.action in (
                ui_cfg.ACT_PAGE,
                ui_cfg.ACT_INFO,
            )
            if parsed.action != ui_cfg.ACT_HAND:
                await answer_callback_query_safe(query)
            await _dispatch(
                bot,
                game,
                player,
                query,
                parsed,
                skip_end_refresh=refresh_only,
            )
        finally:
            game.mercy_callback_busy = False

    if game_is_running(game) and game.mode == "no_mercy":
        cancel_fast_countdown(game)
        if parsed.action not in (ui_cfg.ACT_PAGE, ui_cfg.ACT_INFO, ui_cfg.ACT_HAND):
            await refresh_mercy_prompt(bot, game)
        await start_player_countdown(bot, game)


async def _dispatch(
    bot, game, player, query, parsed, *, skip_end_refresh: bool = False
) -> None:
    action = parsed.action
    arg = parsed.arg

    if action == ui_cfg.ACT_PAGE:
        page = int(arg or 0)
        await refresh_mercy_prompt(bot, game, page=page)
        return

    if action == ui_cfg.ACT_INFO:
        await refresh_mercy_prompt(bot, game)
        return

    if action == ui_cfg.ACT_HAND:
        target = player or game.current_player
        if target is None:
            await answer_callback_query_safe(query)
            return
        hand_text = render_hand_private(target)
        plain = hand_text.replace("<b>", "").replace("</b>", "").replace("\n", " ")
        await answer_callback_query_safe(
            query,
            text=plain[:190],
            show_alert=True,
        )
        return

    if player is None:
        return

    if action == ui_cfg.ACT_DRAW:
        await do_draw(bot, player)
        return

    if action == ui_cfg.ACT_PASS:
        if player.drew:
            game.turn()
        return

    if action == ui_cfg.ACT_PLAY:
        idx = int(arg or 0)
        card = playable_card_at_index(player, idx)
        if card is None:
            await answer_callback_query_safe(
                query,
                text="That card is not playable.",
                show_alert=True,
            )
            return
        await do_play_card(bot, player, str(card))
        return

    if action == ui_cfg.ACT_COLOR:
        if arg and game.choose_color(arg):
            await refresh_mercy_prompt(bot, game)
        return

    if action == ui_cfg.ACT_SWAP:
        target = opponent_at_index(game, player, int(arg or 0))
        if target:
            from no_mercy.actions_hook import handle_swap_target

            await handle_swap_target(bot, player, int(target.user.id))
        return

    if action == ui_cfg.ACT_ROULETTE:
        target = opponent_at_index(game, player, int(arg or 0))
        if target:
            from no_mercy.actions_hook import handle_roulette_target

            await handle_roulette_target(bot, player, int(target.user.id))
        return

    if action == ui_cfg.ACT_BONUS:
        from no_mercy.actions_hook import handle_bonus_discard_index

        await handle_bonus_discard_index(bot, player, int(arg or 0))
        return

    if action == ui_cfg.ACT_BONUS_SKIP:
        from no_mercy.actions_hook import handle_bonus_discard_skip

        await handle_bonus_discard_skip(bot, player)
        return
