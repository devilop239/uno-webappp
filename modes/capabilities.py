# -*- coding: utf-8 -*-
"""Per-mode gameplay capabilities and rule flags."""

from __future__ import annotations

MODES_WITHOUT_BLUFF = frozenset({"no_mercy"})
MODES_WITHOUT_PASS = frozenset({"no_mercy"})


def game_mode(game) -> str:
    return getattr(game, "mode", None) or "classic"


def supports_bluff_challenge(game) -> bool:
    """Wild +4/+8 bluff call — not used in NO MERCY (stack rules instead)."""
    return game_mode(game) not in MODES_WITHOUT_BLUFF


def supports_pass_after_draw(game) -> bool:
    return game_mode(game) not in MODES_WITHOUT_PASS
