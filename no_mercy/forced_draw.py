"""NO MERCY — draw until a playable card (no pass; player picks the card)."""
from __future__ import annotations

import logging

from errors import DeckEmptyError

from no_mercy.constants import ELIMINATION_HAND_SIZE
from no_mercy.playability import has_any_playable

logger = logging.getLogger(__name__)

_SAFETY_MAX = 120


def clear_forced_draw(game) -> None:
    game.mercy_forced_draw_active = False
    game.mercy_forced_draw_count = 0


def draw_until_playable(player) -> int:
    """
    Draw until the player has a playable card (respects drew = last-card rule).
    Returns number of cards drawn this call.
    """
    game = player.game
    game.mercy_forced_draw_active = True
    drew = 0

    if not player.drew:
        player.drew = True

    while not has_any_playable(player):
        if len(player.cards) >= ELIMINATION_HAND_SIZE:
            break
        card = game.deck.draw()
        player.cards.append(card)
        drew += 1
        game.mercy_forced_draw_count = int(getattr(game, "mercy_forced_draw_count", 0) or 0) + 1
        if drew >= _SAFETY_MAX:
            logger.warning(
                "NO MERCY draw-until-playable safety stop user_id=%s drew=%d",
                getattr(player.user, "id", None),
                drew,
            )
            break

    return drew


def mercy_draw_turn(player) -> int:
    """
    One draw action for NO MERCY (no stack): voluntary single draw if already playable,
    otherwise draw until playable.
    """
    if not player.drew:
        if not has_any_playable(player):
            return draw_until_playable(player)
        player.draw()
        if has_any_playable(player):
            return 1
        return 1 + draw_until_playable(player)

    if has_any_playable(player):
        return 0
    return draw_until_playable(player)
