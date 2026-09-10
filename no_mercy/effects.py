"""
NO MERCY card effects and turn flow.
"""
from __future__ import annotations

import logging

import deck.card as c

from no_mercy.constants import (
    COLOR_CHOOSER_SPECIALS,
    DISCARD_ALL,
    DRAW2,
    OPENING_DISALLOWED_SPECIALS,
    SWAP_VALUE,
    W_DRAW4_REVERSE,
    W_ROULETTE,
    W_SKIP_ALL,
)
from no_mercy import pending
from no_mercy.stack import record_stack_play, stack_amount

logger = logging.getLogger(__name__)


def opening_card_allowed(card) -> bool:
    if card.special and card.special in OPENING_DISALLOWED_SPECIALS:
        return False
    if card.value in (c.SKIP, c.REVERSE, DRAW2, DISCARD_ALL):
        return False
    return True


def _two_players(game) -> bool:
    return len(game.players) == 2


def _defer_turn(game) -> bool:
    if game.choosing_color:
        return True
    if getattr(game, "mercy_pending_swap", False):
        return True
    if getattr(game, "mercy_pending_roulette", None):
        return True
    return False


def play_card(game, card, *, opening: bool = False) -> None:
    if not opening:
        game.deck.dismiss(game.last_card)
    game.last_card = card

    game.pending_skip_after_color = False
    game.last_draw_special_challengeable = False
    game.last_bluffable_draw_special = False
    pending.clear_pending(game)
    game.mercy_chain_bounced = False

    added_stack = False
    if card.value == DRAW2:
        game.draw_counter += 2
        record_stack_play(game, card)
        added_stack = True
    elif card.special:
        amt = stack_amount(card)
        if amt:
            game.draw_counter += amt
            record_stack_play(game, card)
            added_stack = True
    if game.draw_counter:
        from no_mercy.stats import note_stack

        note_stack(game, game.draw_counter)

    if card.special == W_DRAW4_REVERSE:
        game.mercy_chain_bounced = True
        if _two_players(game):
            pass
        else:
            game.reverse()
        game.stack_reversed = True

    if card.value == c.SKIP:
        game.turn()
    elif card.value == c.REVERSE:
        if _two_players(game):
            game.turn()
        elif game.current_player == game.current_player.next.next:
            game.turn()
        else:
            game.reverse()
    elif card.special == W_SKIP_ALL:
        pending.begin_skip_all_color(game)
    elif card.special == W_ROULETTE:
        pending.begin_roulette(game)
    elif card.value == SWAP_VALUE and len(game.current_player.cards) > 0:
        pending.begin_swap_choice(game)

    if card.special in COLOR_CHOOSER_SPECIALS:
        game.choosing_color = True

    if opening or _defer_turn(game):
        return

    # Classic-style double advance for skip/reverse (skip effect + end turn)
    if card.value in (c.SKIP, c.REVERSE):
        game.turn()
    elif added_stack or game.draw_counter:
        game.turn()
    else:
        game.turn()


def apply_discard_all(player, played_card) -> int:
    color = played_card.color
    if not color:
        return 0
    removed = [
        hand_card
        for hand_card in list(player.cards)
        if hand_card.color == color
    ]
    for hand_card in removed:
        if hand_card in player.cards:
            player.cards.remove(hand_card)
            player.game.deck.dismiss(hand_card)
    player.game.discard_all_count = len(removed)
    return len(removed)


def swap_hands(player, target) -> None:
    player.cards, target.cards = target.cards, player.cards


def apply_skip_all_after_color(game) -> None:
    """
    Skip every other player, then the same player plays again.

    Each turn() advances once around the ring. To skip all opponents and
    land back on the player who played Skip All, advance len(players) times
    (2p: same as Skip — opponent skipped, you play again).
    """
    n = len(game.players)
    for _ in range(n):
        game.turn()
    game.mercy_pending_skip_all = False


def choose_color(game, color) -> bool:
    if not game.choosing_color and getattr(game, "mercy_pending_roulette", None) != "color":
        return False
    game.last_card.color = color
    game.choosing_color = False

    if getattr(game, "mercy_pending_skip_all", False):
        apply_skip_all_after_color(game)
        return True

    if getattr(game, "mercy_pending_roulette", None) == "color":
        game.mercy_roulette_color = color
        game.mercy_pending_roulette = "target"
        return True

    if game.draw_counter:
        game.turn()
    else:
        game.turn()
    return True
