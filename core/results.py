# -*- coding: utf-8 -*-
"""Defines helper functions to build inline queries and game summary results."""

from typing import List, Dict, Any, Optional

from aiogram.types import InlineQueryResultArticle, InlineQueryResultCachedSticker as Sticker

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
    # A lobby has a current host player but no last card yet. Do not ask the
    # game rule engine to calculate playability until dealing has started.
    is_running = bool(getattr(game, "started", False) and last_c)
    legal_actions = {
        "play": bool(is_running and not game.choosing_color and cp.playable_cards()),
        "draw": bool(is_running and cp and not cp.drew),
        "pass": bool(is_running and cp and cp.drew and not game.draw_counter and pass_supported),
        "choose_color": bool(is_running and game.choosing_color),
        "call_bluff": bool(
            is_running
            and supports_bluff_challenge(game)
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
    playable_ids = (
        {str(card) for card in player.playable_cards()}
        if getattr(game, "started", False) and hasattr(player, "playable_cards")
        else set()
    )

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


# ---------------------------------------------------------------------------
# Telegram inline-result compatibility helpers
# ---------------------------------------------------------------------------
#
# The web client uses the structured serializers above, while the original
# Telegram bot still consumes these small result builders.  Keep them here so
# both clients use the same card assets and action identifiers.


def _article(result_id: str, title: str, description: str = ""):
    return InlineQueryResultArticle(
        id=result_id,
        title=title,
        description=description or None,
        input_message_content=premium_input_text(title),
    )


def _sticker(results, result_id: str, sticker_id: str, title: str = ""):
    kwargs = {"id": result_id, "sticker_file_id": sticker_id}
    if title:
        kwargs["input_message_content"] = premium_input_text(title)
    results.append(Sticker(**kwargs))


def add_no_game(results):
    results.append(_article("nogame", "No active game", "Start a game with /new."))


def add_not_started(results):
    results.append(_article("not_started", "Waiting for the host", "The game has not started yet."))


def add_gameinfo(game, results):
    results.append(_article("gameinfo", "Game information", desc_trim(game_info_text(game))))


def add_draw(player, results):
    _sticker(results, "draw", c.STICKERS["option_draw"], "Draw a card")


def add_pass(results, game):
    _sticker(results, "pass", c.STICKERS["option_pass"], "Pass turn")


def add_call_bluff(results, game):
    _sticker(results, "call_bluff", c.STICKERS["option_bluff"], "Call bluff")


def add_choose_color(results, game):
    for color in c.mode_colors(game.mode):
        title = inline_color_choice_title(color)
        kwargs = {
            "id": color,
            "title": title,
            "description": inline_label(_("Choose a color to continue your move.")),
            "input_message_content": premium_input_text(display_color_group(color, game)),
        }
        thumbnail = color_inline_thumbnail_url(color)
        if thumbnail:
            kwargs.update(
                thumbnail_url=thumbnail,
                thumbnail_width=48,
                thumbnail_height=48,
            )
        results.append(InlineQueryResultArticle(**kwargs))


def add_card(game, card, results, can_play=True, hand_index=None):
    """Add a playable or disabled hand card using its stable card ID."""
    result_id = str(card)
    if hand_index is not None and not can_play:
        result_id = f"blocked_{hand_index}"
    _sticker(
        results,
        result_id,
        c.sticker_for(card, game, playable=can_play),
        desc_trim(repr(card)),
    )


def add_other_cards(player, results, game):
    for index, card in enumerate(sorted(player.cards, key=str)):
        add_card(game, card, results, can_play=False, hand_index=index)


def _add_mode(results, mode, title):
    results.append(_article(f"mode_{mode}", title, f"Switch to {title}."))


def add_mode_classic(results):
    _add_mode(results, "classic", "Classic UNO")


def add_mode_fast(results):
    _add_mode(results, "fast", "Fast UNO")


def add_mode_wild(results):
    _add_mode(results, "wild", "Wild UNO")


def add_mode_rainbow(results):
    _add_mode(results, "rainbow", "Rainbow UNO")


def add_mode_sudden_death(results):
    _add_mode(results, "sudden_death", "Sudden Death")


def add_mode_no_mercy(results):
    _add_mode(results, "no_mercy", "No Mercy")


def add_mode_text(results):
    _add_mode(results, "text", "Text mode")


def add_mode_team(results):
    _add_mode(results, "team", "Team UNO")


def add_mercy_bonus_discard(results, game, player):
    """Expose the no-mercy bonus discard choices when that mode is active."""
    for index, card in enumerate(sorted(player.cards, key=str)):
        _sticker(
            results,
            f"nmbonus_{index}",
            c.sticker_for(card, game, playable=True),
            desc_trim(repr(card)),
        )
    results.append(_article("nmbonus_skip", "Skip bonus discard"))


def add_mercy_choose_opponent(results, game, player, prefix, title_fmt):
    for target in game.players:
        if target.user.id == player.user.id:
            continue
        title = title_fmt.format(display_name_label(target.user))
        results.append(_article(f"{prefix}{target.user.id}", title))


def add_no_mercy_turn_cards(player, results, game):
    playable = {str(card) for card in player.playable_cards()}
    for index, card in enumerate(sorted(player.cards, key=str)):
        add_card(
            game,
            card,
            results,
            can_play=str(card) in playable,
            hand_index=index,
        )
