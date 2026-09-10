"""
🔥 NO MERCY — isolated premium UNO mode.

Public API for hooks in game.py, player.py, actions.py, deck_styles.py, etc.
"""
from __future__ import annotations

from no_mercy.constants import MODE
from no_mercy import state
from no_mercy.deck_fill import fill_no_mercy_deck
from no_mercy.effects import (
    apply_discard_all,
    choose_color,
    opening_card_allowed,
    play_card,
)
from no_mercy.playability import playable_cards
from no_mercy.stickers import is_no_mercy_game, sticker_for_card


def configure_new_lobby(game) -> None:
    """Apply fixed NO MERCY lobby rules."""
    state.init_state(game)


def configure_game_start(game) -> None:
    from no_mercy.constants import FIXED_HAND_SIZE

    state.init_state(game)
    game.hand_size = FIXED_HAND_SIZE
    game.stacking_enabled = True


def is_no_mercy(game) -> bool:
    return state.is_no_mercy(game)


__all__ = [
    "MODE",
    "configure_new_lobby",
    "configure_game_start",
    "fill_no_mercy_deck",
    "is_no_mercy",
    "is_no_mercy_game",
    "play_card",
    "playable_cards",
    "opening_card_allowed",
    "apply_discard_all",
    "choose_color",
    "sticker_for_card",
    "state",
]
