"""Pending player choices (color, swap target, roulette)."""
from __future__ import annotations

import deck.card as c

from no_mercy.constants import W_ROULETTE, W_SKIP_ALL


def clear_pending(game) -> None:
    game.mercy_pending_swap = False
    game.mercy_pending_roulette = None
    game.mercy_pending_skip_all = False
    game.mercy_roulette_color = None


def begin_swap_choice(game) -> None:
    game.mercy_pending_swap = True
    game.choosing_color = False


def begin_roulette(game) -> None:
    game.mercy_pending_roulette = "color"
    game.mercy_roulette_color = None
    game.choosing_color = True


def begin_skip_all_color(game) -> None:
    game.mercy_pending_skip_all = True
    game.choosing_color = True


def needs_color_choice(card) -> bool:
    from no_mercy.constants import COLOR_CHOOSER_SPECIALS

    return bool(card.special and card.special in COLOR_CHOOSER_SPECIALS)


def needs_swap_choice(card, player) -> bool:
    return card.value == c.SEVEN and len(player.cards) > 0


def needs_roulette_setup(card) -> bool:
    return card.special == W_ROULETTE


def needs_skip_all_color(card) -> bool:
    return card.special == W_SKIP_ALL
