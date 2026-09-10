"""
NO MERCY — bonus discard after 5+ forced draws (strict, dedicated inline step).
"""
from __future__ import annotations

import deck.card as c

from no_mercy.constants import FORCED_DRAW_BONUS_DISCARD_THRESHOLD


def is_pending(game) -> bool:
    return bool(getattr(game, "mercy_extra_discard_pending", False))


def owner_id(game) -> int | None:
    uid = getattr(game, "mercy_extra_discard_uid", None)
    return int(uid) if uid is not None else None


def is_owner(player) -> bool:
    game = player.game
    if not is_pending(game):
        return False
    oid = owner_id(game)
    return oid is None or int(player.user.id) == oid


def begin_pending(game, player) -> None:
    game.mercy_extra_discard_pending = True
    game.mercy_extra_discard_uid = int(player.user.id)
    game.mercy_extra_discard_allowed = True


def clear_pending(game) -> None:
    game.mercy_extra_discard_pending = False
    game.mercy_extra_discard_uid = None
    game.mercy_extra_discard_allowed = False
    game.mercy_suppress_turn_end = False


def card_index_from_result(result_id: str) -> int | None:
    if not result_id.startswith("nmbonus") or result_id in ("nmbonus_skip", "nmbonus_info"):
        return None
    suffix = result_id[7:]  # nmbonus0 -> 0
    if not suffix.isdigit():
        return None
    return int(suffix)


def sorted_hand(player) -> list:
    return sorted(player.cards, key=str)


def apply_bonus_discard(player, card) -> bool:
    """Remove one card to graveyard; does not play onto pile."""
    game = player.game
    if not is_owner(player) or card not in player.cards:
        return False
    player.cards.remove(card)
    game.deck.dismiss(card)
    clear_pending(game)
    return True


def should_offer_after_forced_draw(drew: int) -> bool:
    return drew >= FORCED_DRAW_BONUS_DISCARD_THRESHOLD
