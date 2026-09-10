"""
NO MERCY mode — card ids and deck composition (isolated from classic UNO).
"""
from __future__ import annotations

import deck.card as c

MODE = "no_mercy"

DRAW2 = "draw2"
DISCARD_ALL = "discard_all"
SWAP_VALUE = c.SEVEN

MERCY_COLOR_VALUES = (
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
    c.SKIP,
    c.REVERSE,
    DRAW2,
    DISCARD_ALL,
)

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

OPENING_DISALLOWED_SPECIALS = frozenset(MERCY_WILD_SPECIALS)

COLOR_CHOOSER_SPECIALS = frozenset(
    {W_WILD, W_DRAW4, W_DRAW6, W_DRAW10, W_DRAW4_REVERSE}
)

DRAW_STACK_AMOUNTS = {
    W_DRAW4: 4,
    W_DRAW6: 6,
    W_DRAW10: 10,
    W_DRAW4_REVERSE: 4,
}

DRAW_STACK_DEFENSE = frozenset(
    {DRAW2, W_DRAW4, W_DRAW6, W_DRAW10, W_DRAW4_REVERSE}
)

STACK_BLOCKED_WHILE_ACTIVE = frozenset(
    {W_WILD, W_ROULETTE, W_SKIP_ALL}
)

BASE_DECK_SIZE = 63  # one full set: 56 colored + 7 wild
DECK_SIZE = BASE_DECK_SIZE  # alias (minimum / single-set size)
FIXED_HAND_SIZE = 7
MIN_PLAYERS = 2
MAX_PLAYERS = 12
# Extra draws per player (forced draw, stacks, discard-all) beyond opening hands
GAMEPLAY_BUFFER_PER_PLAYER = 20
ELIMINATION_HAND_SIZE = 30
# Above this hand size, @bot inline shows playable cards + draw only (not every blocked card).
# Increased from 12 to 20 to prevent cards from being hidden when users draw multiple cards.
INLINE_COMPACT_HAND = 20
FORCED_DRAW_BONUS_DISCARD_THRESHOLD = 5

# Inline result stems (see results.add_mercy_bonus_discard)
BONUS_DISCARD_PREFIX = "nmbonus"
BONUS_DISCARD_SKIP_ID = "nmbonus_skip"
BONUS_DISCARD_INFO_ID = "nmbonus_info"
