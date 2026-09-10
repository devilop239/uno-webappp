# -*- coding: utf-8 -*-
"""
UNO No Mercy Expansion rules definition & deck filling interface.
"""

from __future__ import annotations
import deck.card as c

MODE = "no_mercy"
DRAW2 = "draw2"
DISCARD_ALL = "discard_all"
SWAP_VALUE = c.SEVEN

W_WILD = "w_wild"
W_DRAW4 = "w_draw4"
W_DRAW6 = "w_draw6"
W_DRAW10 = "w_draw10"
W_DRAW4_REVERSE = "w_draw4_reverse"
W_SKIP_ALL = "w_skip_all"
W_ROULETTE = "w_roulette"

MERCY_WILD_SPECIALS = (
    W_WILD,
    W_DRAW4,
    W_DRAW6,
    W_DRAW10,
    W_DRAW4_REVERSE,
    W_SKIP_ALL,
    W_ROULETTE,
)

MERCY_SPECIAL_STRINGS = frozenset(MERCY_WILD_SPECIALS)

NO_MERCY_MODE_SPEC = {
    "id": "no_mercy",
    "name": "UNO No Mercy",
    "description": "Aggressive UNO variant with unlimited draw stacking (+2, +4, +6, +10), 0/7 hand swaps, and 25+ card elimination.",
    "mercy_elimination_limit": 25,
    "supports_unlimited_stacking": True,
    "supports_0_7_swap": True,
    "supports_discard_all": True,
    "supports_bluff": False,
    "supports_pass": False,
}


def fill_no_mercy_deck(deck_obj, multiplier=1):
    from no_mercy.deck_fill import fill_no_mercy_deck as _fill
    _fill(deck_obj, multiplier=multiplier)
