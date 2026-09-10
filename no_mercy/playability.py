"""
NO MERCY playability — same color / same number; full draw-stack rules.
"""
from __future__ import annotations

import deck.card as c

from no_mercy.constants import (
    COLOR_CHOOSER_SPECIALS,
    DISCARD_ALL,
    DRAW2,
    MERCY_WILD_SPECIALS,
    STACK_BLOCKED_WHILE_ACTIVE,
    W_DRAW4_REVERSE,
    W_ROULETTE,
    W_SKIP_ALL,
    W_WILD,
)
from no_mercy.stack import can_stack_with, is_stack_defense_card
from no_mercy.state import is_eliminated_uid, should_eliminate


def _last(game):
    return game.last_card


def _two_players(game) -> bool:
    return len(game.players) == 2


def _matches_color_or_value(card, last) -> bool:
    if not last:
        return False
    if last.color and card.color == last.color:
        return True
    if card.value and last.value and card.value == last.value:
        return True
    return False


def is_card_playable(player, card) -> bool:
    game = player.game
    uid = getattr(getattr(player, "user", None), "id", None)
    if uid is not None and is_eliminated_uid(game, uid):
        return False
    if should_eliminate(len(player.cards)):
        return False
    last = _last(game)

    if game.draw_counter:
        if card.special in STACK_BLOCKED_WHILE_ACTIVE:
            return False
        if card.value in (c.SKIP, c.REVERSE, DISCARD_ALL):
            return False
        if not card.special and card.value not in (DRAW2,):
            # number cards blocked
            if card.value in (
                c.ZERO,
                c.ONE,
                c.TWO,
                c.THREE,
                c.FOUR,
                c.FIVE,
                c.SIX,
                c.SEVEN,
                c.EIGHT,
                c.NINE,
            ):
                return False
        if not is_stack_defense_card(card):
            return False
        last_was_rev = getattr(game, "mercy_stack_last", None) == W_DRAW4_REVERSE
        return can_stack_with(
            card,
            last,
            last_was_draw4_reverse=last_was_rev
            or (last and last.special == W_DRAW4_REVERSE),
        )

    if not last:
        return False

    # Wild cards (off-stack): draw wilds always playable; skip-all / roulette blocked above
    if card.special in MERCY_WILD_SPECIALS:
        if card.special == W_WILD and last.special == W_WILD:
            return False
        return True

    if card.value == c.SKIP:
        return _matches_color_or_value(card, last) or last.value == c.SKIP
    if card.value == c.REVERSE:
        return _matches_color_or_value(card, last) or last.value == c.REVERSE
    if card.value == DRAW2:
        return _matches_color_or_value(card, last) or last.value == DRAW2
    if card.value == DISCARD_ALL:
        return _matches_color_or_value(card, last) or last.value == DISCARD_ALL

    # Numbers 0-9 and seven swap
    return _matches_color_or_value(card, last)


def can_play_last_card(card) -> bool:
    if card.special in COLOR_CHOOSER_SPECIALS:
        return False
    if card.special in (W_ROULETTE, W_SKIP_ALL):
        return False
    return True


def playable_cards(player) -> list:
    cards = player.cards
    if player.drew and not player.game.draw_counter:
        cards = player.cards[-1:]

    playable = [card for card in cards if is_card_playable(player, card)]

    if len(player.cards) == 1:
        only = player.cards[0]
        if only.special and not can_play_last_card(only):
            return []

    return playable


def has_any_playable(player) -> bool:
    return bool(playable_cards(player))
