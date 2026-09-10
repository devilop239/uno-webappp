"""
NO MERCY hooks called from actions.py / inline (keeps actions.py thin).
"""
from __future__ import annotations

from aiogram.enums import ParseMode

from no_mercy.constants import DISCARD_ALL, SWAP_VALUE
from no_mercy import state
from no_mercy.effects import apply_discard_all, swap_hands
from no_mercy.effects_roulette import run_roulette_draws
from no_mercy.elimination import (
    check_and_eliminate,
    check_last_survivor_win,
    check_match_end,
    enforce_elimination_threshold,
)
from no_mercy.forced_draw import clear_forced_draw
from no_mercy.messages import (
    announce_chain_bounced,
    announce_stack,
    announce_swap,
    announce_uno,
)
from no_mercy.text_style import sc, sc_bold
from utils import display_name_html


async def after_play_card(bot, player, card) -> str | None:
    """
    Post-play handling. Returns 'stop' if caller should return early.
    """
    game = player.game
    chat = game.chat
    user = player.user

    if getattr(game, "mercy_chain_bounced", False):
        await announce_chain_bounced(bot, chat.id)

    if game.draw_counter:
        await announce_stack(bot, game, chat.id)

    if card.value == DISCARD_ALL:
        n = apply_discard_all(player, card)
        if n > 0:
            from tg.helpers import send_message

            await send_message(
                bot,
                chat.id,
                text="🔥 %s — %s %s!"
                % (
                    sc_bold("DISCARD ALL"),
                    display_name_html(user),
                    sc("dropped %d cards" % n),
                ),
                parse_mode=ParseMode.HTML,
            )

    if await enforce_elimination_threshold(bot, player):
        return "stop"

    if len(player.cards) == 0:
        game.finish_order.append(user.id)
        from tg.helpers import send_message

        await send_message(
            bot,
            chat.id,
            text="🔥 %s %s!" % (sc_bold("NO MERCY"), display_name_html(user)),
            parse_mode=ParseMode.HTML,
        )
        await check_match_end(bot, game, user)
        return "stop"

    if len(player.cards) == 1 and not state.has_announced_uno(game, user.id):
        state.note_uno(game, user.id)
        await announce_uno(bot, game, chat.id, user)

    if card.value == SWAP_VALUE and getattr(game, "mercy_pending_swap", False):
        from tg.helpers import send_message

        await send_message(
            bot,
            chat.id,
            text="🔀 %s" % sc("Choose a player to swap with (@bot)."),
        )

    if card.special == "w_roulette" and game.mercy_pending_roulette == "color":
        from tg.helpers import send_message

        await send_message(
            bot,
            chat.id,
            text="🎰 %s" % sc("Choose a color, then a target (@bot)."),
        )

    return None


async def after_draw(bot, player, *, stack_penalty: bool) -> None:
    game = player.game
    if stack_penalty:
        from no_mercy.stack import clear_active_stack

        clear_active_stack(game)
    if await enforce_elimination_threshold(bot, player):
        return
    clear_forced_draw(game)


async def after_color_choice(bot, player) -> None:
    """After wild color pick — eliminate if hand is still 30+."""
    if await enforce_elimination_threshold(bot, player):
        return


async def handle_swap_target(bot, player, target_uid: int) -> None:
    game = player.game
    target = next(
        (p for p in game.players if int(p.user.id) == int(target_uid)),
        None,
    )
    if not target or target is player:
        return
    before_p, before_t = len(player.cards), len(target.cards)
    swap_hands(player, target)
    game.mercy_pending_swap = False
    await announce_swap(bot, game.chat.id)
    from tg.helpers import send_message

    await send_message(
        bot,
        game.chat.id,
        text=(
            "🔀 %s (%d→%d) ↔ %s (%d→%d)"
            % (
                display_name_html(player.user),
                before_p,
                len(player.cards),
                display_name_html(target.user),
                before_t,
                len(target.cards),
            )
        ),
        parse_mode=ParseMode.HTML,
    )
    if len(player.cards) == 1:
        state.note_uno(game, player.user.id)
        await announce_uno(bot, game, game.chat.id, player.user)
    if len(target.cards) == 1:
        state.note_uno(game, target.user.id)
        await announce_uno(bot, game, game.chat.id, target.user)
    if await enforce_elimination_threshold(bot, player):
        return
    if await enforce_elimination_threshold(bot, target):
        return
    game.turn()


async def handle_bonus_discard_index(bot, player, index: int) -> None:
    from no_mercy.extra_discard import apply_bonus_discard, sorted_hand

    hand = sorted_hand(player)
    if index < 0 or index >= len(hand):
        return
    if not apply_bonus_discard(player, hand[index]):
        return


async def handle_bonus_discard_skip(bot, player) -> None:
    from no_mercy.extra_discard import clear_pending, is_owner

    if not is_owner(player):
        return
    clear_pending(player.game)


async def handle_roulette_target(bot, player, target_uid: int) -> None:
    from no_mercy.ui.renderer import render_roulette_sequence

    game = player.game
    color = game.mercy_roulette_color
    target = next(
        (p for p in game.players if int(p.user.id) == int(target_uid)),
        None,
    )
    if not target or not color:
        return
    game.mercy_pending_roulette = None
    game.choosing_color = False
    drawn, reveals = run_roulette_draws(target, color)
    from tg.helpers import send_message

    await send_message(
        bot,
        game.chat.id,
        text=render_roulette_sequence(
            display_name_html(player.user),
            display_name_html(target.user),
            color,
            reveals,
        ),
        parse_mode=ParseMode.HTML,
    )
    if await enforce_elimination_threshold(bot, target):
        return
    game.turn()
