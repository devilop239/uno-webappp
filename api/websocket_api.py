# -*- coding: utf-8 -*-
"""WebSocket Manager and endpoint for real-time UNO WebApp state sync."""

import logging
from typing import Dict, Set, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.auth import verify_session
from shared_vars import gm
from core.actions import do_call_bluff, do_draw, do_pass, do_play_card
from core.results import serialize_game_state, serialize_player_hand
from errors import GameActionError
import deck.card as c

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websockets"])


class ConnectionManager:
    """Manages active WebSocket connections per room_id."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
        self.active_connections[room_id].add(websocket)
        logger.info("WS Client connected to room=%s", room_id)

    def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id in self.active_connections:
            self.active_connections[room_id].discard(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        logger.info("WS Client disconnected from room=%s", room_id)

    async def broadcast_to_room(self, room_id: str, message: Dict[str, Any]):
        """Broadcast event JSON to all clients connected to room_id."""
        if room_id not in self.active_connections:
            return
        dead_sockets = set()
        for websocket in list(self.active_connections[room_id]):
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning("Failed sending WS msg: %s", e)
                dead_sockets.add(websocket)
        
        for dead in dead_sockets:
            self.disconnect(room_id, dead)


ws_manager = ConnectionManager()


@router.websocket("/game/{room_id}/{user_id}")
async def websocket_game_endpoint(websocket: WebSocket, room_id: str, user_id: int):
    """
    WebSocket channel for live game session updates.
    """
    try:
        verify_session(websocket.query_params.get("session_token"), int(room_id), user_id)
    except ValueError as exc:
        await websocket.close(code=1008, reason=str(exc))
        return

    await ws_manager.connect(room_id, websocket)
    try:
        # Send initial confirmation message
        await websocket.send_json({
            "event": "connected",
            "room_id": room_id,
            "user_id": user_id,
        })
        while True:
            data = await websocket.receive_json()
            game = gm.get_game_in_chat(type("Chat", (), {"id": int(room_id)})())
            if not game or not game.started:
                await websocket.send_json({"event": "action_rejected", "detail": "No running game found"})
                continue
            if not game.current_player or int(game.current_player.user.id) != int(user_id):
                await websocket.send_json({"event": "action_rejected", "detail": "It is not your turn"})
                continue

            action = str(data.get("action_type", "")).strip().lower()
            player = game.current_player
            try:
                if action == "play":
                    await do_play_card(bot=None, player=player, result_id=str(data.get("card_id", "")))
                elif action == "draw":
                    await do_draw(bot=None, player=player)
                elif action == "pass":
                    await do_pass(bot=None, player=player)
                elif action == "choose_color":
                    color = data.get("color")
                    if color not in c.mode_colors(game.mode) or not game.choose_color(color):
                        raise GameActionError("Invalid or unexpected color choice")
                elif action == "call_bluff":
                    await do_call_bluff(bot=None, player=player)
                else:
                    raise GameActionError("Unknown action type")
            except GameActionError as exc:
                await websocket.send_json({"event": "action_rejected", "action": action, "detail": str(exc)})
                continue

            await ws_manager.broadcast_to_room(str(room_id), {
                "event": "state_updated",
                "user_id": int(user_id),
                "state": serialize_game_state(game),
            })
            from api.game_api import schedule_bot_turns
            schedule_bot_turns(game)
    except WebSocketDisconnect:
        ws_manager.disconnect(room_id, websocket)
    except Exception as e:
        logger.error("WS error room=%s user=%s: %s", room_id, user_id, e)
        ws_manager.disconnect(room_id, websocket)
