"""Callback validation — turn ownership, tokens, elimination."""
from __future__ import annotations

from utils import game_is_running

from no_mercy.extra_discard import is_owner as bonus_owner, is_pending as bonus_pending
from no_mercy.game_state import (
    blocks_normal_play,
    is_choosing_color,
    is_pending_swap,
    roulette_phase,
)
from no_mercy.ui.tokens import parse_callback, token_matches


def _player_for_user(game, user_id: int):
    for p in game.players:
        if int(p.user.id) == int(user_id):
            return p
    return None


def is_eliminated_uid(game, user_id: int) -> bool:
    return int(user_id) in (getattr(game, "eliminated_players", []) or [])


def validate(query, game) -> tuple[bool, object | None, str]:
    """
    Returns (ok, player_or_none, error_message).
    Spectators may use hand/info only.
    """
    from shared_vars import gm
    if not game_is_running(game) or not gm.is_game_registered(game):
        return False, None, "Game ended."

    user = query.from_user
    if user is None:
        return False, None, "Invalid user."

    parsed = parse_callback(query.data or "")
    if parsed is None:
        return False, None, "Invalid callback."

    if not token_matches(game, parsed.token):
        return False, None, "Outdated menu — wait for the new turn."

    if getattr(game, "mercy_callback_busy", False):
        return False, None, "Please wait…"

    player = _player_for_user(game, user.id)
    action = parsed.action

    if action in ("h", "i"):
        if player is None and not is_eliminated_uid(game, user.id):
            return False, None, "You are not in this game."
        return True, player, ""

    if is_eliminated_uid(game, user.id):
        return False, None, "Eliminated — spectate only (info)."

    if player is None:
        return False, None, "Not in this game."

    cur = game.current_player
    if cur is None:
        return False, None, "No active turn."

    if action in ("d", "p", "pg", "c", "s", "t", "b", "bx", "x"):
        if player is not cur:
            return False, None, "Not your turn."

    if bonus_pending(game) and action not in ("b", "bx", "h", "i", "pg"):
        if bonus_owner(player):
            return False, None, "Complete bonus discard first."

    if is_choosing_color(game) and action not in ("c", "h", "i"):
        if player is cur:
            return False, None, "Choose a color first."

    phase = roulette_phase(game)
    if phase == "color" and action not in ("c", "h", "i"):
        if player is cur:
            return False, None, "Roulette: choose a color."
    if phase == "target" and action not in ("t", "h", "i"):
        if player is cur:
            return False, None, "Roulette: choose a target."

    if is_pending_swap(game) and action not in ("s", "h", "i"):
        if player is cur:
            return False, None, "Choose a player to swap with."

    if action == "x" and game.draw_counter:
        return False, None, "You must draw or stack."

    if action == "p" and game.draw_counter:
        from no_mercy.playability import is_card_playable

        idx = int(parsed.arg or -1)
        from no_mercy.ui.keyboard import playable_card_at_index

        card = playable_card_at_index(player, idx)
        if card is None or not is_card_playable(player, card):
            return False, None, "Cannot play that card on the stack."

    if action in ("p", "d", "x") and blocks_normal_play(game) and player is cur:
        return False, None, "Use the buttons on the turn message."

    return True, player, ""
