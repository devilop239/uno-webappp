# -*- coding: utf-8 -*-
"""Game Modes & Rules Engine Package."""

from modes.capabilities import (
    game_mode,
    supports_bluff_challenge,
    supports_pass_after_draw,
    MODES_WITHOUT_BLUFF,
    MODES_WITHOUT_PASS,
)
from modes.classic import CLASSIC_MODE_SPEC, FAST_MODE_SPEC, WILD_MODE_SPEC
from modes.rainbow import RAINBOW_MODE_SPEC
from modes.no_mercy import NO_MERCY_MODE_SPEC, fill_no_mercy_deck
from modes.sudden_death import SUDDEN_DEATH_MODE_SPEC

ALL_GAME_MODES = {
    "classic": CLASSIC_MODE_SPEC,
    "fast": FAST_MODE_SPEC,
    "wild": WILD_MODE_SPEC,
    "rainbow": RAINBOW_MODE_SPEC,
    "no_mercy": NO_MERCY_MODE_SPEC,
    "sudden_death": SUDDEN_DEATH_MODE_SPEC,
}

__all__ = [
    "game_mode",
    "supports_bluff_challenge",
    "supports_pass_after_draw",
    "MODES_WITHOUT_BLUFF",
    "MODES_WITHOUT_PASS",
    "CLASSIC_MODE_SPEC",
    "FAST_MODE_SPEC",
    "WILD_MODE_SPEC",
    "RAINBOW_MODE_SPEC",
    "NO_MERCY_MODE_SPEC",
    "SUDDEN_DEATH_MODE_SPEC",
    "ALL_GAME_MODES",
    "fill_no_mercy_deck",
]
