# -*- coding: utf-8 -*-
"""FastAPI endpoints for UNO game lifecycle (Create, Join, Start, Play, State, AI Bot turns)."""

import asyncio
import logging
import random
import secrets
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Header, HTTPException, Query

from shared_vars import gm
from core.actions import do_play_card, do_draw, do_call_bluff, do_pass, do_skip
from core.results import serialize_game_state, serialize_player_hand
from api.websocket_api import ws_manager
import deck.card as c
from errors import GameActionError
from api.auth import issue_session, verify_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/game", tags=["game"])


class CreateGameRequest(BaseModel):
    room_id: Optional[int] = None
    user_id: int
    first_name: str
    mode: str = "classic"
    deck_style: str = "normal"
    hand_size: int = 7
    stacking_enabled: bool = True
    is_bot_match: bool = False
    bot_count: int = 1


class JoinGameRequest(BaseModel):
    room_id: int
    user_id: int
    first_name: str
    session_token: Optional[str] = None


class ActionRequest(BaseModel):
    room_id: int
    user_id: int
    action_type: str  # play | draw | pass | call_bluff | choose_color | choose_swap_target | choose_roulette_target
    card_id: Optional[str] = None  # stem or repr like 'r_5', 'h0'
    color: Optional[str] = None  # r, b, g, y, p, o
    target_id: Optional[int] = None
    session_token: Optional[str] = None


class DummyUser:
    def __init__(self, user_id: int, first_name: str, is_bot: bool = False):
        self.id = int(user_id)
        self.first_name = first_name
        self.last_name = ""
        self.username = first_name
        self.is_bot = is_bot


class DummyChat:
    def __init__(self, room_id: int):
        self.id = int(room_id)
        self.type = "group"
        self.title = f"Room {room_id}"


BOT_NAMES = ["Pawri Wala Bhai", "Chai Sutta Boss", "Titu Mama", "Circuit", "Babu Bhaiya"]


def _new_room_id() -> int:
    """Return an unused six-digit room code for web-created lobbies."""
    for _ in range(20):
        candidate = secrets.randbelow(900000) + 100000
        if not gm.has_active_game(candidate):
            return candidate
    raise HTTPException(status_code=503, detail="Could not allocate a room code")


def _finish_web_winner(game, player) -> bool:
    """End a web match immediately when a hand reaches zero."""
    if not player or player.cards:
        return False
    winner_id = int(player.user.id)
    if winner_id not in game.finish_order:
        game.finish_order.append(winner_id)
    # Telegram supports finish-order games where players leave one by one.
    # The first web release is a single-match table: close the room as soon
    # as someone wins so no disconnected winner can keep a stale session.
    gm.end_game(game.chat, player.user, reason="completed")
    return True


async def _trigger_bot_turns_if_needed(game):
    """Automated AI Bot turn execution loop with realistic 3-5s human thinking delays and smart decision logic."""
    max_steps = 15
    steps = 0
    while game.started and game.current_player and steps < max_steps:
        cp = game.current_player
        is_bot_player = bool(getattr(cp.user, "is_bot", False))
        if not is_bot_player:
            break

        steps += 1

        # Broadcast thinking state to room
        think_time = round(random.uniform(0.6, 1.0), 1)
        await ws_manager.broadcast_to_room(str(game.chat.id), {
            "event": "bot_thinking",
            "bot_id": cp.user.id,
            "bot_name": cp.user.first_name,
            "think_time": think_time,
        })
        await asyncio.sleep(think_time)

        # Handle No Mercy pending 7-swap
        if getattr(game, "mercy_pending_swap", False):
            from no_mercy.actions_hook import handle_swap_target
            eliminated = set(getattr(game, "eliminated_players", []) or [])
            opponents = [p for p in game.players if p.user.id != cp.user.id and p.user.id not in eliminated]
            if opponents:
                # Bot picks opponent with fewest cards to swap
                best_target = min(opponents, key=lambda p: len(p.cards))
                await handle_swap_target(bot=None, player=cp, target_uid=best_target.user.id)
            else:
                game.mercy_pending_swap = False
                game.turn()
            await ws_manager.broadcast_to_room(str(game.chat.id), {
                "event": "bot_turn",
                "bot_id": cp.user.id,
                "state": serialize_game_state(game),
            })
            continue

        # Handle No Mercy pending Wild Roulette
        roulette_state = getattr(game, "mercy_pending_roulette", None)
        if roulette_state == "color":
            colors = c.mode_colors(game.mode)
            chosen = random.choice(colors)
            game.mercy_roulette_color = chosen
            game.mercy_pending_roulette = "target"
            await ws_manager.broadcast_to_room(str(game.chat.id), {
                "event": "bot_turn",
                "bot_id": cp.user.id,
                "state": serialize_game_state(game),
            })
            continue
        elif roulette_state == "target":
            from no_mercy.actions_hook import handle_roulette_target
            eliminated = set(getattr(game, "eliminated_players", []) or [])
            opponents = [p for p in game.players if p.user.id != cp.user.id and p.user.id not in eliminated]
            if opponents:
                # Bot picks opponent with fewest cards
                best_target = min(opponents, key=lambda p: len(p.cards))
                await handle_roulette_target(bot=None, player=cp, target_uid=best_target.user.id)
            else:
                game.mercy_pending_roulette = None
                game.turn()
            await ws_manager.broadcast_to_room(str(game.chat.id), {
                "event": "bot_turn",
                "bot_id": cp.user.id,
                "state": serialize_game_state(game),
            })
            continue

COLOR_NAMES = {
    "r": "Red ❤️",
    "b": "Blue 💙",
    "g": "Green 💚",
    "y": "Yellow 💛",
    "p": "Purple 💜",
    "o": "Orange 🧡",
}


def _resolve_bot_color_choice(game, bot_player) -> str:
    """Helper for AI bot to choose optimal color from hand and apply it."""
    colors = c.mode_colors(game.mode)
    hand_colors = [getattr(card, "color", None) for card in bot_player.cards if getattr(card, "color", None) in colors]
    chosen = max(set(hand_colors), key=hand_colors.count) if hand_colors else random.choice(colors)
    game.choose_color(chosen)
    color_label = COLOR_NAMES.get(chosen, chosen.upper())
    return f"{bot_player.user.first_name} chose {color_label}"


async def _trigger_bot_turns_if_needed(game):
    """Automated AI Bot turn execution loop with realistic 3-5s human thinking delays and smart decision logic."""
    max_steps = 15
    steps = 0
    while game.started and game.current_player and steps < max_steps:
        cp = game.current_player
        is_bot_player = bool(getattr(cp.user, "is_bot", False))
        if not is_bot_player:
            break

        steps += 1

        # Broadcast thinking state to room
        think_time = round(random.uniform(3.0, 4.8), 1)
        await ws_manager.broadcast_to_room(str(game.chat.id), {
            "event": "bot_thinking",
            "bot_id": cp.user.id,
            "bot_name": cp.user.first_name,
            "think_time": think_time,
        })
        await asyncio.sleep(think_time)

        # Handle No Mercy pending 7-swap
        if getattr(game, "mercy_pending_swap", False):
            from no_mercy.actions_hook import handle_swap_target
            eliminated = set(getattr(game, "eliminated_players", []) or [])
            opponents = [p for p in game.players if p.user.id != cp.user.id and p.user.id not in eliminated]
            if opponents:
                # Bot picks opponent with fewest cards to swap
                best_target = min(opponents, key=lambda p: len(p.cards))
                await handle_swap_target(bot=None, player=cp, target_uid=best_target.user.id)
            else:
                game.mercy_pending_swap = False
                game.turn()
            await ws_manager.broadcast_to_room(str(game.chat.id), {
                "event": "bot_turn",
                "bot_id": cp.user.id,
                "state": serialize_game_state(game),
            })
            continue

        # Handle No Mercy pending Wild Roulette
        roulette_state = getattr(game, "mercy_pending_roulette", None)
        if roulette_state == "color":
            colors = c.mode_colors(game.mode)
            chosen = random.choice(colors)
            game.mercy_roulette_color = chosen
            game.mercy_pending_roulette = "target"
            c_label = COLOR_NAMES.get(chosen, chosen.upper())
            notice = f"{cp.user.first_name} picked {c_label} for Roulette!"
            await ws_manager.broadcast_to_room(str(game.chat.id), {
                "event": "bot_turn",
                "bot_id": cp.user.id,
                "notice": notice,
                "state": serialize_game_state(game),
            })
            continue
        elif roulette_state == "target":
            from no_mercy.actions_hook import handle_roulette_target
            eliminated = set(getattr(game, "eliminated_players", []) or [])
            opponents = [p for p in game.players if p.user.id != cp.user.id and p.user.id not in eliminated]
            if opponents:
                best_target = min(opponents, key=lambda p: len(p.cards))
                await handle_roulette_target(bot=None, player=cp, target_uid=best_target.user.id)
            else:
                game.mercy_pending_roulette = None
                game.turn()
            await ws_manager.broadcast_to_room(str(game.chat.id), {
                "event": "bot_turn",
                "bot_id": cp.user.id,
                "state": serialize_game_state(game),
            })
            continue

        # 1. Handle choosing color if bot just played a wild card
        if game.choosing_color:
            notice = _resolve_bot_color_choice(game, cp)
            await ws_manager.broadcast_to_room(str(game.chat.id), {
                "event": "color_chosen",
                "bot_id": cp.user.id,
                "notice": notice,
                "state": serialize_game_state(game),
            })
            continue

        # 2. Evaluate playable cards with human-like strategy
        playable = cp.playable_cards() if hasattr(cp, "playable_cards") else []
        if playable:
            # Separate normal cards from wild/power cards
            normals = [card for card in playable if getattr(card, "color", None) not in (None, "w")]
            wilds = [card for card in playable if getattr(card, "color", None) in (None, "w")]

            # 85% smart human preference: play matching normal cards first, save wild power cards for emergency
            if normals and (not wilds or random.random() < 0.85):
                card_to_play = random.choice(normals)
            else:
                card_to_play = random.choice(playable)

            stem = str(card_to_play)
            await do_play_card(bot=None, player=cp, result_id=stem)
            if _finish_web_winner(game, cp):
                break

            # Auto-call UNO when 1 card left (no penalty)
            if len(cp.cards) == 1:
                cp.called_uno = True

            if game.choosing_color:
                notice = _resolve_bot_color_choice(game, cp)
                await ws_manager.broadcast_to_room(str(game.chat.id), {
                    "event": "color_chosen",
                    "bot_id": cp.user.id,
                    "notice": notice,
                    "state": serialize_game_state(game),
                })
                continue
        else:
            # Bot draws card
            try:
                await do_draw(bot=None, player=cp)
            except GameActionError as error:
                logger.warning(
                    "Bot draw rejected user_id=%s: %s",
                    getattr(cp.user, "id", None),
                    error,
                )
                if game.current_player == cp:
                    game.turn()
                continue

            if game.current_player == cp:
                playable_after = cp.playable_cards() if hasattr(cp, "playable_cards") else []
                if playable_after:
                    try:
                        await do_play_card(bot=None, player=cp, result_id=str(playable_after[0]))
                    except GameActionError as error:
                        logger.warning(
                            "Bot drawn-card play rejected user_id=%s: %s",
                            getattr(cp.user, "id", None),
                            error,
                        )
                        if game.current_player == cp:
                            game.turn()
                        continue
                    if _finish_web_winner(game, cp):
                        break
                    if len(cp.cards) == 1:
                        cp.called_uno = True
                    if game.choosing_color:
                        notice = _resolve_bot_color_choice(game, cp)
                        await ws_manager.broadcast_to_room(str(game.chat.id), {
                            "event": "color_chosen",
                            "bot_id": cp.user.id,
                            "notice": notice,
                            "state": serialize_game_state(game),
                        })
                        continue
                else:
                    game.turn()

        state = serialize_game_state(game)
        await ws_manager.broadcast_to_room(str(game.chat.id), {
            "event": "bot_turn",
            "bot_id": cp.user.id,
            "state": state,
        })


def schedule_bot_turns(game) -> None:
    """Run bot turns in the background without delaying the human action response."""
    task = getattr(game, "bot_turn_task", None)
    if task is not None and not task.done():
        return

    task = asyncio.create_task(
        _trigger_bot_turns_if_needed(game),
        name=f"uno-bot-turns-{game.chat.id}",
    )
    game.bot_turn_task = task

    def report_task_failure(completed_task):
        if completed_task.cancelled():
            return
        error = completed_task.exception()
        if error:
            logger.error("Bot turn task failed for room=%s: %s", game.chat.id, error, exc_info=error)

    task.add_done_callback(report_task_failure)


@router.post("/create", response_model=Dict[str, Any])
async def create_game(req: CreateGameRequest):
    """Host/Create a new UNO game session room."""
    room_id = int(req.room_id or _new_room_id())
    if gm.has_active_game(room_id):
        raise HTTPException(status_code=409, detail="That room code is already in use")

    chat = DummyChat(room_id)
    user = DummyUser(req.user_id, req.first_name)

    try:
        game = gm.new_game(chat)
        if game is None:
            raise HTTPException(status_code=409, detail="That room code is already in use")
        game.mode = req.mode
        from deck.styles import is_deck_style_allowed_for_mode, DECK_STYLE_NORMAL
        game.deck_style = req.deck_style if is_deck_style_allowed_for_mode(req.deck_style, req.mode) else DECK_STYLE_NORMAL
        game.hand_size = req.hand_size
        game.stacking_enabled = req.stacking_enabled
        game.host_user_id = req.user_id
        # Host automatically joins
        gm.join_game(user, chat)

        # Spawn AI Bot opponents if bot match
        if req.is_bot_match:
            count = min(3, max(1, req.bot_count))
            for i in range(count):
                bot_user = DummyUser(8001 + i, BOT_NAMES[i % len(BOT_NAMES)], is_bot=True)
                gm.join_game(bot_user, chat)
            game.start()

        state = serialize_game_state(game)
        await ws_manager.broadcast_to_room(str(room_id), {
            "event": "game_created",
            "state": state,
        })

        if req.is_bot_match:
            # Return the dealt hand immediately; bot thinking must not block room creation.
            schedule_bot_turns(game)

        host_player = next((p for p in game.players if p.user.id == req.user_id), None)
        return {
            "status": "success",
            "room_id": room_id,
            "session_token": issue_session(room_id, req.user_id, game.match_uuid),
            "state": state,
            "hand": serialize_player_hand(host_player) if host_player else [],
        }
    except Exception as e:
        logger.error("Error creating game: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/join", response_model=Dict[str, Any])
async def join_game(req: JoinGameRequest):
    """Join an open UNO game lobby."""
    chat = DummyChat(req.room_id)
    user = DummyUser(req.user_id, req.first_name)

    game = gm.get_game_in_chat(chat)
    if not game:
        raise HTTPException(status_code=404, detail="No active game found in this room")

    if game.started:
        raise HTTPException(status_code=400, detail="Game has already started")

    try:
        gm.join_game(user, chat)
        state = serialize_game_state(game)
        await ws_manager.broadcast_to_room(str(req.room_id), {
            "event": "player_joined",
            "user_id": req.user_id,
            "first_name": req.first_name,
            "state": state,
        })
        return {
            "status": "success",
            "room_id": req.room_id,
            "session_token": issue_session(req.room_id, req.user_id, game.match_uuid),
            "state": state,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/start", response_model=Dict[str, Any])
async def start_game(req: JoinGameRequest):
    """Start the UNO match for the room."""
    chat = DummyChat(req.room_id)

    game = gm.get_game_in_chat(chat)
    if not game:
        raise HTTPException(status_code=404, detail="No active game found in this room")

    _require_session(req.session_token, req.room_id, req.user_id, game)

    if int(getattr(game, "host_user_id", req.user_id)) != int(req.user_id):
        raise HTTPException(status_code=403, detail="Only the room host can start the game")

    if game.started:
        raise HTTPException(status_code=400, detail="Game has already started")

    if len(game.players) < 2:
        raise HTTPException(status_code=400, detail="At least 2 players are required to start")

    try:
        game.start()
        state = serialize_game_state(game)
        await ws_manager.broadcast_to_room(str(req.room_id), {
            "event": "game_started",
            "state": state,
        })
        schedule_bot_turns(game)
        state = serialize_game_state(game)
        return {"status": "success", "state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{room_id}", response_model=Dict[str, Any])
async def get_game_state(room_id: int, session_token: str = Query(...)):
    """Fetch current state of room."""
    chat = DummyChat(room_id)
    game = gm.get_game_in_chat(chat)
    if not game:
        raise HTTPException(status_code=404, detail="No active game found in this room")

    _require_session(session_token, room_id, None, game)

    return serialize_game_state(game)


@router.get("/{room_id}/hand/{user_id}", response_model=List[Dict[str, Any]])
async def get_player_hand(room_id: int, user_id: int, session_token: str = Query(...)):
    """Fetch private cards hand for player in room."""
    chat = DummyChat(room_id)
    game = gm.get_game_in_chat(chat)
    if not game:
        raise HTTPException(status_code=404, detail="No active game found in this room")

    _require_session(session_token, room_id, user_id, game)

    player = next((p for p in game.players if p.user.id == int(user_id)), None)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found in this game")

    return serialize_player_hand(player)


@router.post("/action", response_model=Dict[str, Any])
async def perform_action(req: ActionRequest):
    """
    Execute a turn action (play card, draw card, choose color, pass, bluff challenge).
    """
    chat = DummyChat(req.room_id)
    game = gm.get_game_in_chat(chat)
    if not game or not game.started:
        raise HTTPException(status_code=400, detail="No running game found in this room")

    _require_session(req.session_token, req.room_id, req.user_id, game)

    cp = game.current_player
    if not cp or cp.user.id != req.user_id:
        raise HTTPException(status_code=403, detail="It is not your turn")

    action = req.action_type.lower().strip()

    try:
        if action == "play":
            if not req.card_id:
                raise HTTPException(status_code=400, detail="card_id is required for play action")
            await do_play_card(bot=None, player=cp, result_id=req.card_id)
            finished = _finish_web_winner(game, cp)

        elif action == "draw":
            await do_draw(bot=None, player=cp)

        elif action == "choose_color":
            if not req.color or req.color not in c.mode_colors(game.mode):
                raise HTTPException(status_code=400, detail=f"Invalid color choice: {req.color}")
            c_label = COLOR_NAMES.get(req.color, req.color.upper())
            notice = f"{cp.user.first_name} chose {c_label}"
            if getattr(game, "mercy_pending_roulette", None) == "color":
                game.mercy_roulette_color = req.color
                game.mercy_pending_roulette = "target"
                game.choosing_color = False
            else:
                if not game.choose_color(req.color):
                    raise HTTPException(status_code=409, detail="No color choice is pending")

        elif action == "choose_swap_target":
            if not req.target_id:
                raise HTTPException(status_code=400, detail="target_id is required for swap action")
            from no_mercy.actions_hook import handle_swap_target
            await handle_swap_target(bot=None, player=cp, target_uid=req.target_id)
            finished = _finish_web_winner(game, cp)

        elif action == "choose_roulette_target":
            if not req.target_id:
                raise HTTPException(status_code=400, detail="target_id is required for roulette action")
            from no_mercy.actions_hook import handle_roulette_target
            await handle_roulette_target(bot=None, player=cp, target_uid=req.target_id)
            finished = _finish_web_winner(game, cp)

        elif action == "call_bluff":
            await do_call_bluff(bot=None, player=cp)

        elif action == "pass":
            await do_pass(bot=None, player=cp)

        elif action == "skip":
            await do_skip(bot=None, player=cp)

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action_type: {req.action_type}")
    except GameActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state = serialize_game_state(game)
    broadcast_payload = {
        "event": f"action_{action}",
        "user_id": req.user_id,
        "state": state,
    }
    if locals().get("notice"):
        broadcast_payload["notice"] = locals()["notice"]
    await ws_manager.broadcast_to_room(str(req.room_id), broadcast_payload)

    # Trigger AI Bot turn if next player is a bot
    schedule_bot_turns(game)
    state = serialize_game_state(game)

    return {
        "status": "success",
        "action": action,
        "state": state,
        "finished": bool(locals().get("finished", False)),
        "winner_id": int(req.user_id) if locals().get("finished", False) else None,
    }


def _require_session(token: Optional[str], room_id: int, user_id: Optional[int], game) -> dict:
    try:
        payload = verify_session(token, room_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if payload.get("match_uuid") and payload["match_uuid"] != game.match_uuid:
        raise HTTPException(status_code=401, detail="Room session is no longer active")
    if not any(int(player.user.id) == int(payload["user_id"]) for player in game.players):
        raise HTTPException(status_code=403, detail="User is not a member of this room")
    return payload
