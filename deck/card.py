# -*- coding: utf-8 -*-
"""
UNO Card representation and playability rules.
"""

from __future__ import annotations
from deck.assets.normal import CARDS_CLASSIC

# Colors
RED = 'r'
BLUE = 'b'
GREEN = 'g'
YELLOW = 'y'
PURPLE = 'p'
ORANGE = 'o'
BLACK = 'x'

COLORS = (RED, BLUE, GREEN, YELLOW)
RAINBOW_COLORS = (RED, BLUE, GREEN, YELLOW, PURPLE, ORANGE)

COLOR_ICONS = {
    RED: '❤️',
    BLUE: '💙',
    GREEN: '💚',
    YELLOW: '💛',
    PURPLE: '💜',
    ORANGE: '🧡',
    BLACK: '⬛️'
}

# Values
ZERO = '0'
ONE = '1'
TWO = '2'
THREE = '3'
FOUR = '4'
FIVE = '5'
SIX = '6'
SEVEN = '7'
EIGHT = '8'
NINE = '9'
DRAW_TWO = 'draw'
REVERSE = 'reverse'
SKIP = 'skip'

VALUES = (ZERO, ONE, TWO, THREE, FOUR, FIVE, SIX, SEVEN, EIGHT, NINE, DRAW_TWO, REVERSE, SKIP)
WILD_VALUES = (ONE, TWO, THREE, FOUR, FIVE, DRAW_TWO, REVERSE, SKIP)
RAINBOW_VALUES = (ZERO, ONE, TWO, THREE, FOUR, FIVE, SIX, DRAW_TWO, REVERSE, SKIP)

# Special cards
CHOOSE = 'colorchooser'
DRAW_FOUR = 'draw_four'
DRAW_EIGHT = 'draw_eight'
RAINBOW_WILD = 'rainbow_wild'
RAINBOW_LIGHTNING = 'rainbow_lightning'
RAINBOW_MONSTER = 'rainbow_monster'

SPECIALS = (CHOOSE, DRAW_FOUR)
WILD_SPECIALS = (CHOOSE, DRAW_FOUR, DRAW_EIGHT)
RAINBOW_SPECIALS = (DRAW_EIGHT, RAINBOW_WILD, RAINBOW_LIGHTNING, RAINBOW_MONSTER)
ALL_SPECIALS = SPECIALS + RAINBOW_SPECIALS


def mode_colors(mode: str):
    if mode == "rainbow":
        return RAINBOW_COLORS
    return COLORS


CARDS_CLASSIC_COLORBLIND = CARDS_CLASSIC

STICKERS_OPTIONS = {
    "option_draw": "/images/options/webp/option_draw.webp",
    "option_pass": "/images/options/webp/option_pass.webp",
    "option_bluff": "/images/options/webp/option_bluff.webp",
    "option_info": "/images/options/webp/option_info.webp",
}

STICKERS = {
    **CARDS_CLASSIC["normal"],
    **STICKERS_OPTIONS,
}

STICKERS_GREY = {
    **CARDS_CLASSIC["not_playable"],
}


def sticker_for(card, game=None, *, playable=True):
    """Telegram sticker file_id; deck style resolved in deck.styles."""
    from deck.styles import sticker_for as _sticker_for
    return _sticker_for(card, game, playable=playable)


class Card(object):
    """Represents an individual UNO card."""

    def __init__(self, color, value, special=None):
        self.color = color
        self.value = value
        self.special = special

    def __str__(self):
        if self.special:
            return self.special
        else:
            return '%s_%s' % (self.color, self.value)

    def __repr__(self):
        if self.special:
            return '%s%s%s' % (
                COLOR_ICONS.get(self.color, ''),
                COLOR_ICONS[BLACK],
                ' '.join([s.capitalize() for s in self.special.split('_')])
            )
        else:
            return '%s%s' % (COLOR_ICONS.get(self.color, ''), self.value.capitalize())

    def __eq__(self, other):
        return str(self) == str(other)

    def __lt__(self, other):
        return str(self) < str(other)


def from_str(string):
    """Decodes a Card object from a string representation."""
    try:
        from modes.no_mercy import MERCY_SPECIAL_STRINGS
        if string in MERCY_SPECIAL_STRINGS:
            return Card(None, None, special=string)
    except (ImportError, AttributeError):
        pass
    if string not in ALL_SPECIALS:
        color, value = string.split("_", 1)
        return Card(color, value)
    else:
        return Card(None, None, string)
