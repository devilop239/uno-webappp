"""Draw-stack rules for NO MERCY."""
from __future__ import annotations

import deck.card as c

from no_mercy.constants import (
    DRAW2,
    DRAW_STACK_AMOUNTS,
    DRAW_STACK_DEFENSE,
    W_DRAW4,
    W_DRAW4_REVERSE,
    W_DRAW6,
    W_DRAW10,
)


def stack_amount(card) -> int:
    if card.special and card.special in DRAW_STACK_AMOUNTS:
        return DRAW_STACK_AMOUNTS[card.special]
    if card.value == DRAW2:
        return 2
    return 0


def is_stack_defense_card(card) -> bool:
    if card.value == DRAW2:
        return True
    return bool(card.special and card.special in DRAW_STACK_DEFENSE)


def is_draw_stack_top(last) -> bool:
    """Top card of an active +2 / +4 / +6 / +10 chain."""
    if not last:
        return False
    if last.value == DRAW2:
        return True
    return bool(
        last.special
        and last.special in (W_DRAW4, W_DRAW6, W_DRAW10, W_DRAW4_REVERSE)
    )


def can_stack_with(card, last, *, last_was_draw4_reverse: bool) -> bool:
    """
    Whether card may be played on an active draw stack.

    +2, +4, +6, and +10 may stack on each other (no color match required).
    +4 Reverse cannot be stacked on another +4 Reverse.
    """
    if not is_stack_defense_card(card) or not is_draw_stack_top(last):
        return False

    if card.special == W_DRAW4_REVERSE:
        if last_was_draw4_reverse or (
            last and last.special == W_DRAW4_REVERSE
        ):
            return False
        return True

    if card.special in (W_DRAW4, W_DRAW6, W_DRAW10):
        return True

    if card.value == DRAW2:
        return True

    return False


def record_stack_play(game, card) -> None:
    """Track last stack card type for defense rules."""
    if card.special == W_DRAW4_REVERSE:
        game.mercy_stack_last = W_DRAW4_REVERSE
    elif card.special:
        game.mercy_stack_last = card.special
    elif card.value == DRAW2:
        game.mercy_stack_last = DRAW2
    else:
        game.mercy_stack_last = None


def clear_active_stack(game) -> None:
    """Reset stack tracking after the penalty is drawn (draw_counter already cleared)."""
    game.mercy_stack_last = None
    game.mercy_chain_bounced = False


def should_offer_draw(player) -> bool:
    """
    Whether inline should show the draw option (group @bot UI).

    Active stack: always allow accepting the penalty even if a stack card is playable.
    Otherwise: draw until playable / first draw of turn rules.
    """
    game = player.game
    if int(getattr(game, "draw_counter", 0) or 0) > 0:
        return True
    if not player.drew:
        return True
    from no_mercy.playability import has_any_playable

    return not has_any_playable(player)
