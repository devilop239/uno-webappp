"""
NO MERCY elimination (30+ cards) and last-survivor win.
"""
from __future__ import annotations

import logging

from aiogram.enums import ParseMode

from no_mercy import state
from no_mercy.constants import ELIMINATION_HAND_SIZE
from no_mercy.messages import announce_eliminated
from no_mercy.text_style import sc, sc_bold
from tg.helpers import send_message
from utils import display_name_html

logger = logging.getLogger(__name__)


async def check_and_eliminate(bot, player) -> bool:
    if len(player.cards) < ELIMINATION_HAND_SIZE:
        return False

    game = player.game
    user = player.user
    uid = int(user.id)
    if state.is_eliminated_uid(game, uid):
        return False

    chat = game.chat
    state.mark_eliminated(game, uid)

    if player is game.current_player:
        game.turn()

    player.leave()
    from shared_vars import gm
    players = gm.userid_players.get(user.id, [])
    try:
        players.remove(player)
    except ValueError:
        pass
    try:
        if gm.userid_current.get(user.id) is player:
            del gm.userid_current[user.id]
    except KeyError:
        pass

    await announce_eliminated(bot, game, chat.id, user)
    return True


async def enforce_elimination_threshold(bot, player) -> bool:
    """
    Run elimination if the player hit 30+ cards. Returns True if they were eliminated
    (caller should stop the current action). Ends the match when one player remains.
    """
    game = player.game
    if not await check_and_eliminate(bot, player):
        return False
    await check_last_survivor_win(bot, game)
    return True


async def check_last_survivor_win(bot, game) -> bool:
    """If only one active player remains, they win and the match ends."""
    remaining = len(game.players)
    if remaining != 1:
        return False
    winner = game.players[0]
    from services.match_result_service import (
        capture_match_context,
        send_post_match_scoreboard,
    )

    if bot is not None:
        await send_message(
            bot,
            game.chat.id,
            text="🔥 %s %s %s!"
            % (
                sc_bold("NO MERCY"),
                display_name_html(winner.user),
                sc("wins as last survivor"),
            ),
            parse_mode=ParseMode.HTML,
        )
    game.finish_order.append(winner.user.id)
    await check_match_end(bot, game, winner.user)
    return True


async def check_match_end(bot, game, winner_user):
    from aiogram.enums import ParseMode

    from no_mercy.ui.renderer import render_winner_screen
    from services.match_result_service import (
        capture_match_context,
        send_post_match_scoreboard,
    )

    if bot is not None:
        await send_message(
            bot,
            game.chat.id,
            text=render_winner_screen(game, winner_user),
            parse_mode=ParseMode.HTML,
        )
    ctx = capture_match_context(game, fallback_user=winner_user)
    from shared_vars import gm
    gm.end_game(game.chat, winner_user, reason="completed_no_mercy")
    if bot is not None:
        await send_post_match_scoreboard(bot, game.chat.id, ctx)
