"""
NO MERCY per-game state.
"""
from __future__ import annotations

from no_mercy.constants import ELIMINATION_HAND_SIZE, FIXED_HAND_SIZE, MODE
from no_mercy.text_style import sc


def is_no_mercy(game) -> bool:
    return getattr(game, "mode", None) == MODE


def init_state(game) -> None:
    from no_mercy.stats import init_stats

    init_stats(game)
    game.hand_size = FIXED_HAND_SIZE
    game.stacking_enabled = True
    game.forced_draw_count = 0
    game.comeback_eligible = False
    game.roulette_target = None
    game.roulette_color = None
    game.stack_reversed = False
    game.discard_all_count = 0
    game.uno_announced = set()
    game.eliminated_players = []
    game.mercy_stack_last = None
    game.mercy_chain_bounced = False
    game.mercy_pending_swap = False
    game.mercy_pending_roulette = None
    game.mercy_pending_skip_all = False
    game.mercy_roulette_color = None
    game.mercy_forced_draw_active = False
    game.mercy_forced_draw_count = 0
    game.mercy_extra_discard_allowed = False
    game.mercy_extra_discard_pending = False
    game.mercy_extra_discard_uid = None
    game.mercy_suppress_turn_end = False
    game.mercy_deck_multiplier = 1
    game.last_draw_special_challengeable = False
    game.last_bluffable_draw_special = False


def effective_hand_size(game) -> int:
    return FIXED_HAND_SIZE


def note_uno(game, user_id: int) -> None:
    if not hasattr(game, "uno_announced") or game.uno_announced is None:
        game.uno_announced = set()
    game.uno_announced.add(int(user_id))


def has_announced_uno(game, user_id: int) -> bool:
    return int(user_id) in getattr(game, "uno_announced", set())


def active_player_count(game) -> int:
    return len(game.players)


def should_eliminate(hand_size: int) -> bool:
    return hand_size >= ELIMINATION_HAND_SIZE


def mark_eliminated(game, user_id: int) -> None:
    uid = int(user_id)
    eliminated = getattr(game, "eliminated_players", None)
    if eliminated is None:
        game.eliminated_players = []
        eliminated = game.eliminated_players
    if uid not in eliminated:
        eliminated.append(uid)


def is_eliminated_uid(game, user_id: int) -> bool:
    return int(user_id) in (getattr(game, "eliminated_players", []) or [])


def status_warnings(game, player) -> list[str]:
    lines = []
    n = int(game.draw_counter or 0)
    if n >= 20:
        lines.append("💀 %s" % sc("STACK IS AT +%d" % n))
    elif n >= 10:
        lines.append("⚠️ %s" % sc("STACK IS AT +%d" % n))
    if len(player.cards) == 1:
        lines.append("🃏 %s" % sc("UNO!"))
    if should_eliminate(len(player.cards)):
        lines.append("💀 %s" % sc("Elimination risk (30+ cards)"))
    eliminated = getattr(game, "eliminated_players", []) or []
    if eliminated:
        lines.append("☠️ %s" % sc("Eliminated: %d" % len(eliminated)))
    return lines
