"""Match statistics for NO MERCY end screens."""
from __future__ import annotations


def init_stats(game) -> None:
    game.mercy_stats = {
        "max_stack": 0,
        "roulette_count": 0,
    }


def note_stack(game, amount: int) -> None:
    stats = getattr(game, "mercy_stats", None) or {}
    game.mercy_stats = stats
    stats["max_stack"] = max(int(stats.get("max_stack") or 0), int(amount))


def note_roulette(game) -> None:
    stats = getattr(game, "mercy_stats", None) or {}
    game.mercy_stats = stats
    stats["roulette_count"] = int(stats.get("roulette_count") or 0) + 1


def snapshot(game) -> dict:
    s = getattr(game, "mercy_stats", None) or {}
    return {
        "max_stack": int(s.get("max_stack") or 0),
        "roulette_count": int(s.get("roulette_count") or 0),
        "turns": int(getattr(game, "turn_count", 0) or 0),
    }
