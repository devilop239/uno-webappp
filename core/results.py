# -*- coding: utf-8 -*-
"""Defines helper functions to build inline queries and game summary results."""

from typing import List, Dict, Any, Optional

import deck.card as c
from modes.capabilities import supports_bluff_challenge, supports_pass_after_draw
from ui.text_style import inline_label, premium_input_text, smallcaps
from utils import (
    color_inline_thumbnail_url,
    display_color_group,
    display_name_html,
    display_name_label,
    inline_color_choice_title,
    display_color,
)


def desc_trim(s: str, max_len: int = 200) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def player_list(game) -> List[str]:
    """Generate player status text representations."""
    return [
        "{name} ({number} card{plural})".format(
            name=display_name_html(player.user),
            number=len(player.cards),
            plural="s" if len(player.cards) != 1 else "",
        )
        for player in game.players
    ]


def game_info_text(game) -> str:
    """Generate textual summary of current game state for API or web UI."""
    if getattr(game, "is_team_mode", False):
        return (
            "Mode: Team UNO %dv%d\n"
            "A (%s): %d cards\n"
            "B (%s): %d cards\n"
            "Current turn: %s\n"
            "Top card: %s\n"
            "Active color: %s"
            % (
                int(game.team_size or 0),
                int(game.team_size or 0),
                game.team_names.get("A") or "Team A",
                game.team_cards_left("A"),
                game.team_names.get("B") or "Team B",
                game.team_cards_left("B"),
                display_name_html(game.current_player.user),
                repr(game.last_card),
                display_color(game.last_card.color) if getattr(game.last_card, "color", None) else "-",
            )
        )
    
    players = player_list(game)
    raw = (
        "Current player: {name}\n"
        "Last card: {card}\n"
        "Players: {player_list}"
    ).format(
        name=display_name_html(game.current_player.user),
        card=repr(game.last_card),
        player_list=" → ".join(players),
    )

    if getattr(game, "mode", None) == "no_mercy":
        from no_mercy.state import status_warnings
        extra = status_warnings(game, game.current_player)
        if extra:
            raw += "\n" + "\n".join(extra)

    return raw


def serialize_game_state(game) -> Dict[str, Any]:
    """
    Structured JSON representation of game state for Web UI / WebSockets.
    """
    if not game or not game.current_player:
        return {}

    cp = game.current_player
    last_c = game.last_card
    pass_supported = supports_pass_after_draw(game)
    legal_actions = {
        "play": bool(cp and not game.choosing_color and cp.playable_cards()),
        "draw": bool(cp and not cp.drew),
        "pass": bool(cp and cp.drew and not game.draw_counter and pass_supported),
        "choose_color": bool(game.choosing_color),
        "call_bluff": bool(
            supports_bluff_challenge(game)
            and getattr(game, "last_draw_special_challengeable", False)
        ),
    }

    players_data = []
    for p in game.players:
        p_info = {
            "id": p.user.id,
            "name": p.user.first_name,
            "card_count": len(p.cards),
            "is_current": (p.user.id == cp.user.id),
        }
        if game.is_team_mode:
            p_info["team"] = game.team_of(p.user.id)
        players_data.append(p_info)

    return {
        "chat_id": game.chat.id if game.chat else None,
        "match_uuid": getattr(game, "match_uuid", None),
        "mode": game.mode,
        "deck_style": getattr(game, "deck_style", "normal"),
        "started": game.started,
        "draw_counter": game.draw_counter,
        "choosing_color": game.choosing_color,
        "active_color": getattr(last_c, "color", None) if last_c else None,
        "current_player_drew": bool(cp.drew) if cp else False,
        "legal_actions": legal_actions,
        "available_colors": list(c.mode_colors(game.mode)),
        "capabilities": {
            "supports_bluff_challenge": supports_bluff_challenge(game),
            "supports_pass_after_draw": pass_supported,
            "stacking_enabled": bool(getattr(game, "stacking_enabled", False)),
        },
        "current_player_id": cp.user.id if cp else None,
        "current_player_name": cp.user.first_name if cp else None,
        "last_card": {
            "id": str(last_c) if last_c else None,
            "name": repr(last_c) if last_c else None,
            "color": getattr(last_c, "color", None),
            "value": getattr(last_c, "value", None),
            "special": getattr(last_c, "special", None),
            "image": c.sticker_for(last_c, game) if last_c else None,
        } if last_c else None,
        "players": players_data,
        "finish_order": game.finish_order,
        "is_team_mode": game.is_team_mode,
        "teams": game.team_members if game.is_team_mode else None,
    }


def serialize_player_hand(player) -> List[Dict[str, Any]]:
    """
    Structured cards array for the current player's view.
    """
    game = player.game
    cards_list = []
    playable_ids = {
        str(card) for card in player.playable_cards()
    } if hasattr(player, "playable_cards") else set()

    for idx, card in enumerate(player.cards):
        is_playable = str(card) in playable_ids
        cards_list.append({
            "index": idx,
            "id": str(card),
            "name": repr(card),
            "color": getattr(card, "color", None),
            "value": getattr(card, "value", None),
            "special": getattr(card, "special", None),
            "playable": is_playable,
            "sticker_file_id": c.sticker_for(card, game, playable=is_playable),
        })
    return cards_list
