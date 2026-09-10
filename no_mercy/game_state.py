"""NO MERCY game-state helpers for validators and UI."""
from __future__ import annotations


def is_choosing_color(game) -> bool:
    return bool(getattr(game, "choosing_color", False))


def is_pending_swap(game) -> bool:
    return bool(getattr(game, "mercy_pending_swap", False))


def is_pending_roulette(game) -> bool:
    return bool(getattr(game, "mercy_pending_roulette", None))


def roulette_phase(game) -> str | None:
    return getattr(game, "mercy_pending_roulette", None)


def blocks_normal_play(game) -> bool:
    return (
        is_choosing_color(game)
        or is_pending_swap(game)
        or is_pending_roulette(game)
    )
