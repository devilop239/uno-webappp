"""Roulette draw with reveal sequence (NO MERCY)."""
from __future__ import annotations

from no_mercy.constants import ELIMINATION_HAND_SIZE
from no_mercy.stats import note_roulette
from no_mercy.ui.renderer import card_label


def run_roulette_draws(target, color: str) -> tuple[int, list[tuple[str, bool]]]:
    """Draw until color hits; return count and reveal lines."""
    game = target.game
    reveals: list[tuple[str, bool]] = []
    drawn = 0
    while True:
        if len(target.cards) >= ELIMINATION_HAND_SIZE:
            break
        card = game.deck.draw()
        target.cards.append(card)
        drawn += 1
        hit = card.color == color
        reveals.append((card_label(card), hit))
        if hit:
            break
        if drawn > 60:
            break
    note_roulette(game)
    return drawn, reveals
