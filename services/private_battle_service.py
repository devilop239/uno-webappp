# -*- coding: utf-8 -*-
"""Private 1v1 friendly UNO battles in DM."""

from __future__ import annotations

import asyncio
import logging
import random
import string
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import deck.card as c
from deck.card import Card, from_str
from deck.deck import Deck
from db.mongo_client import get_database
from ui.text_style import custom_emoji_heading_html, smallcaps

logger = logging.getLogger(__name__)

LOBBY_TTL_SEC = 15 * 60
FINISHED_GAME_CACHE_TTL_SEC = 15 * 60
CB_PREFIX = "pv"


@dataclass
class PrivateLobby:
    code: str
    host_user_id: int
    host_name: str
    status: str = "pending"  # pending | active | expired | cancelled
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + LOBBY_TTL_SEC)
    joiner_user_id: Optional[int] = None


@dataclass
class DrawFourChallengeState:
    attacker_id: int
    challenger_id: int
    previous_top_card: str
    attacker_had_legal_alternative: bool
    chosen_color: Optional[str] = None
    resolved: bool = False


@dataclass
class PrivateGame:
    game_id: str
    player1_id: int
    player2_id: int
    players: Tuple[int, int]
    hands: Dict[int, List[Card]]
    deck: Deck
    discard: List[Card]
    current_turn_user_id: int
    status: str = "pending_start"  # pending_start | active | completed | cancelled
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None

    draw_penalty: int = 0
    choosing_color_for: Optional[int] = None
    drew_this_turn: bool = False
    turn_token: int = 1
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    last_action: str = ""
    winner_user_id: Optional[int] = None
    board_message_ids: Dict[int, int] = field(default_factory=dict)

    # +4 bluff/challenge support
    draw_four_state: Optional[DrawFourChallengeState] = None

    def opponent(self, uid: int) -> int:
        return self.player2_id if uid == self.player1_id else self.player1_id


class PrivateBattleService:
    def __init__(self) -> None:
        self.lobbies_by_code: Dict[str, PrivateLobby] = {}
        self.pending_lobby_by_host: Dict[int, str] = {}
        self.active_game_by_user: Dict[int, str] = {}
        self.games_by_id: Dict[str, PrivateGame] = {}
        self._lock = asyncio.Lock()

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _serialize_cards(cards: List[Card]) -> List[str]:
        return [str(x) for x in cards]

    @staticmethod
    def _deserialize_cards(raw: List[str]) -> List[Card]:
        out: List[Card] = []
        for s in raw or []:
            try:
                out.append(from_str(str(s)))
            except Exception:
                logger.exception("Failed to deserialize card: %r", s)
        return out

    @staticmethod
    def _deserialize_board_message_ids(raw: Optional[dict]) -> Dict[int, int]:
        """BSON requires string keys; restore int user_id -> message_id for in-memory use."""
        out: Dict[int, int] = {}
        for k, v in (raw or {}).items():
            try:
                out[int(k)] = int(v)
            except (TypeError, ValueError):
                continue
        return out

    @staticmethod
    def _serialize_draw_four_state(
        state: Optional[DrawFourChallengeState],
    ) -> Optional[dict]:
        if state is None:
            return None
        return {
            "attacker_id": state.attacker_id,
            "challenger_id": state.challenger_id,
            "previous_top_card": state.previous_top_card,
            "attacker_had_legal_alternative": state.attacker_had_legal_alternative,
            "chosen_color": state.chosen_color,
            "resolved": state.resolved,
        }

    @staticmethod
    def _deserialize_draw_four_state(raw: Optional[dict]) -> Optional[DrawFourChallengeState]:
        if not raw:
            return None
        try:
            return DrawFourChallengeState(
                attacker_id=int(raw["attacker_id"]),
                challenger_id=int(raw["challenger_id"]),
                previous_top_card=str(raw["previous_top_card"]),
                attacker_had_legal_alternative=bool(raw["attacker_had_legal_alternative"]),
                chosen_color=raw.get("chosen_color"),
                resolved=bool(raw.get("resolved", False)),
            )
        except Exception:
            logger.exception("Failed to deserialize draw_four_state: %r", raw)
            return None

    def _persist_game(self, game: PrivateGame) -> None:
        db = get_database()
        if db is None:
            return
        try:
            db.private_games.update_one(
                {"_id": game.game_id},
                {
                    "$set": {
                        "game_id": game.game_id,
                        "player1_id": game.player1_id,
                        "player2_id": game.player2_id,
                        "status": game.status,
                        "current_turn_user_id": game.current_turn_user_id,
                        "hands": {
                            str(game.player1_id): self._serialize_cards(game.hands.get(game.player1_id, [])),
                            str(game.player2_id): self._serialize_cards(game.hands.get(game.player2_id, [])),
                        },
                        "draw_pile": self._serialize_cards(game.deck.cards),
                        "discard_pile": self._serialize_cards(game.discard),
                        "draw_penalty": int(game.draw_penalty or 0),
                        "choosing_color_for": game.choosing_color_for,
                        "drew_this_turn": bool(game.drew_this_turn),
                        "turn_token": int(game.turn_token or 1),
                        "started_at": game.started_at,
                        "ended_at": game.ended_at,
                        "winner_user_id": game.winner_user_id,
                        "last_action": game.last_action or "",
                        "board_message_ids": {
                            str(uid): int(mid)
                            for uid, mid in (game.board_message_ids or {}).items()
                        },
                        "draw_four_state": self._serialize_draw_four_state(game.draw_four_state),
                        "updated_at": self._iso_now(),
                    },
                    "$setOnInsert": {"created_at": self._iso_now()},
                },
                upsert=True,
            )
        except Exception:
            logger.exception("Failed to persist private game %s", game.game_id)

    def _set_user_mapping(self, user_id: int, game_id: str, status: str) -> None:
        db = get_database()
        if db is None:
            return
        try:
            db.private_user_games.update_one(
                {"user_id": int(user_id)},
                {
                    "$set": {
                        "user_id": int(user_id),
                        "game_id": str(game_id),
                        "status": str(status),
                        "updated_at": self._iso_now(),
                    }
                },
                upsert=True,
            )
        except Exception:
            logger.exception("Failed to set private user mapping for user %s", user_id)

    def _clear_user_mapping(self, user_id: int) -> None:
        db = get_database()
        if db is None:
            return
        try:
            db.private_user_games.delete_one({"user_id": int(user_id)})
        except Exception:
            logger.exception("Failed to clear private user mapping for user %s", user_id)

    def _load_game_from_db(self, game_id: str) -> Optional[PrivateGame]:
        db = get_database()
        if db is None:
            return None

        try:
            doc = db.private_games.find_one({"_id": str(game_id)})
        except Exception:
            logger.exception("Failed loading private game %s", game_id)
            return None

        if not doc:
            return None

        try:
            p1 = int(doc.get("player1_id"))
            p2 = int(doc.get("player2_id"))
        except (TypeError, ValueError):
            logger.warning("Invalid player ids in private game %s", game_id)
            return None

        deck = Deck()
        deck.cards = self._deserialize_cards(doc.get("draw_pile") or [])
        deck.graveyard = []
        discard = self._deserialize_cards(doc.get("discard_pile") or [])
        if not discard:
            logger.warning("Private game %s has empty discard pile", game_id)
            return None

        hands_raw = doc.get("hands") or {}
        hands = {
            p1: self._deserialize_cards(hands_raw.get(str(p1)) or []),
            p2: self._deserialize_cards(hands_raw.get(str(p2)) or []),
        }

        game = PrivateGame(
            game_id=str(doc.get("game_id") or doc.get("_id")),
            player1_id=p1,
            player2_id=p2,
            players=(p1, p2),
            hands=hands,
            deck=deck,
            discard=discard,
            current_turn_user_id=int(doc.get("current_turn_user_id") or p1),
            status=str(doc.get("status") or "active"),
            started_at=float(doc.get("started_at") or time.time()),
            ended_at=doc.get("ended_at"),
            draw_penalty=int(doc.get("draw_penalty") or 0),
            choosing_color_for=doc.get("choosing_color_for"),
            drew_this_turn=bool(doc.get("drew_this_turn")),
            turn_token=int(doc.get("turn_token") or 1),
            last_action=str(doc.get("last_action") or ""),
            winner_user_id=doc.get("winner_user_id"),
            board_message_ids=self._deserialize_board_message_ids(
                doc.get("board_message_ids")
            ),
            draw_four_state=self._deserialize_draw_four_state(doc.get("draw_four_state")),
        )

        self.games_by_id[game.game_id] = game
        if game.status in ("active", "pending_start"):
            self.active_game_by_user[p1] = game.game_id
            self.active_game_by_user[p2] = game.game_id
        return game

    def _cleanup_finished_games_cache(self) -> None:
        now = time.time()
        stale_ids: List[str] = []
        for gid, game in self.games_by_id.items():
            if game.status in ("completed", "cancelled") and game.ended_at and now - game.ended_at > FINISHED_GAME_CACHE_TTL_SEC:
                stale_ids.append(gid)
        for gid in stale_ids:
            self.games_by_id.pop(gid, None)

    def _prune_lobbies(self) -> None:
        now = time.time()
        stale = [
            code
            for code, lob in self.lobbies_by_code.items()
            if lob.status == "pending" and lob.expires_at <= now
        ]
        for code in stale:
            lob = self.lobbies_by_code.get(code)
            if lob:
                lob.status = "expired"
                self.pending_lobby_by_host.pop(lob.host_user_id, None)

    def _gen_code(self) -> str:
        for _ in range(24):
            code = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            if code not in self.lobbies_by_code:
                return code
        return uuid.uuid4().hex[:6].upper()

    def _top_card(self, game: PrivateGame) -> Card:
        return game.discard[-1]

    def _rebuild_deck_if_needed(self, game: PrivateGame) -> None:
        if game.deck.cards:
            return

        if len(game.discard) <= 1:
            raise RuntimeError("No cards left to draw and discard pile cannot be recycled.")

        top = game.discard[-1]
        recycle = game.discard[:-1]
        random.shuffle(recycle)
        game.deck.cards = recycle
        game.discard = [top]
        logger.info("Rebuilt draw pile for private game %s with %d cards", game.game_id, len(recycle))

    def _draw_one(self, game: PrivateGame) -> Card:
        self._rebuild_deck_if_needed(game)
        return game.deck.draw()

    def _draw_cards(self, game: PrivateGame, uid: int, n: int) -> None:
        for _ in range(max(0, n)):
            game.hands[uid].append(self._draw_one(game))

    # ---------------------------------------------------------------------
    # Rules
    # ---------------------------------------------------------------------

    def _is_legal_draw_four(self, hand: List[Card], chosen_card: Card, top: Card) -> bool:
        """
        Official-style simplification:
        Wild Draw Four is legal only if player has no other playable non-wild card
        matching active color. We intentionally keep this rule simple and strict.
        """
        if chosen_card.special != c.DRAW_FOUR:
            return True

        for card in hand:
            if card is chosen_card:
                continue
            if getattr(card, "special", None) in (c.CHOOSE, c.DRAW_FOUR):
                continue
            if top.special:
                if card.color == top.color:
                    return False
            else:
                if card.color == top.color:
                    return False
        return True

    def _is_playable(self, card: Card, top: Card, draw_penalty: int) -> bool:
        # During penalty, only stacking card is allowed.
        if draw_penalty > 0:
            return card.value == c.DRAW_TWO or card.special == c.DRAW_FOUR

        # Wilds are always playable when no penalty is active.
        if card.special in (c.CHOOSE, c.DRAW_FOUR):
            return True

        # If top is wild and already recolored, color match matters.
        if top.special:
            return card.color == top.color

        return card.color == top.color or card.value == top.value

    def playable_hand(self, game: PrivateGame, user_id: int) -> List[Card]:
        top = self._top_card(game)
        return [x for x in game.hands.get(user_id, []) if self._is_playable(x, top, game.draw_penalty)]

    def _advance_turn(self, game: PrivateGame, *, keep_same_player: bool = False) -> None:
        if not keep_same_player:
            game.current_turn_user_id = game.opponent(game.current_turn_user_id)
        game.drew_this_turn = False
        game.turn_token += 1

    def _finish_game(self, game: PrivateGame, winner_id: int) -> None:
        game.status = "completed"
        game.winner_user_id = winner_id
        game.ended_at = time.time()
        self.active_game_by_user.pop(game.player1_id, None)
        self.active_game_by_user.pop(game.player2_id, None)
        self._persist_game(game)
        self._clear_user_mapping(game.player1_id)
        self._clear_user_mapping(game.player2_id)

    # ---------------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------------

    async def create_lobby(self, host_id: int, host_name: str) -> Tuple[Optional[PrivateLobby], str]:
        async with self._lock:
            self._cleanup_finished_games_cache()
            self._prune_lobbies()

            if host_id in self.active_game_by_user:
                return None, "You already have an active private battle."

            old_code = self.pending_lobby_by_host.get(host_id)
            if old_code:
                old = self.lobbies_by_code.get(old_code)
                if old and old.status == "pending" and old.expires_at > time.time():
                    return old, ""

            code = self._gen_code()
            lob = PrivateLobby(code=code, host_user_id=host_id, host_name=host_name)
            self.lobbies_by_code[code] = lob
            self.pending_lobby_by_host[host_id] = code
            return lob, ""

    async def cancel_lobby(self, host_id: int) -> bool:
        async with self._lock:
            code = self.pending_lobby_by_host.pop(host_id, None)
            if not code:
                return False

            lob = self.lobbies_by_code.get(code)
            if not lob or lob.status != "pending":
                return False

            lob.status = "cancelled"
            return True

    def _deal_new_game(self, p1: int, p2: int) -> PrivateGame:
        d = Deck()
        d._fill_classic_()

        hands = {p1: [], p2: []}
        for _ in range(7):
            hands[p1].append(d.draw())
            hands[p2].append(d.draw())

        first = d.draw()
        while first.special is not None:
            d.dismiss(first)
            first = d.draw()

        gid = uuid.uuid4().hex
        return PrivateGame(
            game_id=gid,
            player1_id=p1,
            player2_id=p2,
            players=(p1, p2),
            hands=hands,
            deck=d,
            discard=[first],
            current_turn_user_id=p1,  # set properly on start_match()
            last_action="Battle created.",
        )

    async def join_by_code(self, code_raw: str, joiner_id: int) -> Tuple[Optional[PrivateGame], str]:
        code = (code_raw or "").strip().upper()

        async with self._lock:
            self._cleanup_finished_games_cache()
            self._prune_lobbies()

            lob = self.lobbies_by_code.get(code)
            if not lob:
                return None, "Invalid lobby code."

            if lob.status != "pending":
                return None, "This lobby is not available anymore."

            if lob.expires_at <= time.time():
                lob.status = "expired"
                self.pending_lobby_by_host.pop(lob.host_user_id, None)
                return None, "This lobby code has expired."

            if joiner_id == lob.host_user_id:
                return None, "You cannot join your own lobby."

            if joiner_id in self.active_game_by_user:
                return None, "You are already in an active private battle."

            if lob.host_user_id in self.active_game_by_user:
                lob.status = "cancelled"
                self.pending_lobby_by_host.pop(lob.host_user_id, None)
                return None, "Host is already in another active battle."

            game = self._deal_new_game(lob.host_user_id, joiner_id)
            lob.status = "active"
            lob.joiner_user_id = joiner_id
            self.pending_lobby_by_host.pop(lob.host_user_id, None)

            self.games_by_id[game.game_id] = game
            self.active_game_by_user[lob.host_user_id] = game.game_id
            self.active_game_by_user[joiner_id] = game.game_id

            self._persist_game(game)
            self._set_user_mapping(lob.host_user_id, game.game_id, game.status)
            self._set_user_mapping(joiner_id, game.game_id, game.status)
            return game, ""

    async def start_match(self, game_id: str, actor_id: int) -> Tuple[bool, str]:
        game = self.games_by_id.get(game_id)
        if not game:
            return False, "Private game not found."

        async with game.lock:
            if game.status == "active":
                return True, ""

            if game.status != "pending_start":
                return False, "This private battle cannot be started."

            if actor_id != game.player1_id:
                return False, "Only the lobby host can start this match."

            game.current_turn_user_id = random.choice([game.player1_id, game.player2_id])
            game.status = "active"
            game.drew_this_turn = False
            game.turn_token += 1
            game.last_action = "Match started."
            self._persist_game(game)
            self._set_user_mapping(game.player1_id, game.game_id, game.status)
            self._set_user_mapping(game.player2_id, game.game_id, game.status)
            return True, ""

    def game_for_user(self, user_id: int) -> Optional[PrivateGame]:
        gid = self.active_game_by_user.get(user_id)
        if gid:
            game = self.games_by_id.get(gid)
            if game:
                return game
            return self._load_game_from_db(gid)

        db = get_database()
        if db is None:
            return None

        try:
            row = db.private_user_games.find_one(
                {"user_id": int(user_id), "status": {"$in": ["active", "pending_start"]}}
            )
        except Exception:
            logger.exception("Failed looking up private user mapping for %s", user_id)
            return None

        if not row:
            return None

        gid = str(row.get("game_id") or "")
        if not gid:
            return None

        self.active_game_by_user[int(user_id)] = gid
        return self._load_game_from_db(gid)

    # ---------------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------------

    async def play_card(self, game_id: str, actor_id: int, token: int, card_key: str) -> Tuple[bool, str]:
        game = self.games_by_id.get(game_id)
        if not game:
            return False, "Private game not found."

        async with game.lock:
            if game.status != "active":
                return False, "This private battle is already finished."

            if token != game.turn_token:
                return False, "Stale action ignored."

            if actor_id != game.current_turn_user_id:
                return False, "It is not your turn."

            if game.choosing_color_for is not None:
                return False, "Choose a color first."

            if game.draw_four_state and not game.draw_four_state.resolved and actor_id == game.draw_four_state.challenger_id:
                return False, "Resolve the +4 by challenging or drawing first."

            hand = game.hands.get(actor_id, [])
            if not hand:
                return False, "Your hand is empty."

            try:
                idx = int(card_key)
            except ValueError:
                return False, "Invalid card action."

            if idx < 0 or idx >= len(hand):
                return False, "Card index expired. Open hand again."

            card = hand[idx]
            top_before_play = self._top_card(game)

            if not self._is_playable(card, top_before_play, game.draw_penalty):
                return False, "That card cannot be played now."

            # Reset old challenge state unless a fresh +4 creates a new one.
            game.draw_four_state = None

            # DRAW FOUR: store bluff info before removing the card.
            if card.special == c.DRAW_FOUR:
                legal_draw_four = self._is_legal_draw_four(hand, card, top_before_play)

                hand.pop(idx)
                game.discard.append(card)
                game.choosing_color_for = actor_id
                game.drew_this_turn = False
                game.draw_four_state = DrawFourChallengeState(
                    attacker_id=actor_id,
                    challenger_id=game.opponent(actor_id),
                    previous_top_card=str(top_before_play),
                    attacker_had_legal_alternative=not legal_draw_four,
                )
                game.last_action = f"Played {repr(card)} and must choose a color."
                game.turn_token += 1

                if len(hand) == 0:
                    # Winner still needs color choice flow to complete +4 state cleanly.
                    # We allow it and finish in choose_color().
                    pass

                self._persist_game(game)
                return True, ""

            # Normal wild
            if card.special == c.CHOOSE:
                hand.pop(idx)
                game.discard.append(card)
                game.choosing_color_for = actor_id
                game.drew_this_turn = False
                game.last_action = f"Played {repr(card)} and must choose a color."
                game.turn_token += 1
                self._persist_game(game)
                return True, ""

            # Regular card play
            hand.pop(idx)
            game.discard.append(card)
            game.last_action = f"Played {repr(card)}"

            if card.value == c.DRAW_TWO:
                game.draw_penalty += 2
                self._advance_turn(game, keep_same_player=False)

            elif card.value == c.SKIP:
                # 1v1: skip means same player keeps turn
                game.draw_penalty = 0
                self._advance_turn(game, keep_same_player=True)

            elif card.value == c.REVERSE:
                # 1v1 rule requested by user: reverse acts like skip
                game.draw_penalty = 0
                self._advance_turn(game, keep_same_player=True)

            else:
                game.draw_penalty = 0
                self._advance_turn(game, keep_same_player=False)

            if len(hand) == 0:
                self._finish_game(game, actor_id)
            else:
                self._persist_game(game)

            return True, ""

    async def choose_color(self, game_id: str, actor_id: int, token: int, color: str) -> Tuple[bool, str]:
        game = self.games_by_id.get(game_id)
        if not game:
            return False, "Private game not found."

        async with game.lock:
            if game.status != "active":
                return False, "This private battle is already finished."

            if token != game.turn_token:
                return False, "Stale action ignored."

            if game.choosing_color_for != actor_id:
                return False, "Color choose is not active for you."

            if color not in c.COLORS:
                return False, "Invalid color."

            last = self._top_card(game)
            last.color = color
            game.choosing_color_for = None

            # Was this a +4?
            if game.draw_four_state and game.draw_four_state.attacker_id == actor_id and not game.draw_four_state.resolved:
                game.draw_four_state.chosen_color = color
                game.draw_penalty += 4
                self._advance_turn(game, keep_same_player=False)
                game.last_action = f"Set color to {color}. Opponent may challenge the +4."
            else:
                self._advance_turn(game, keep_same_player=False)
                game.last_action = f"Set color to {color}."

            if len(game.hands.get(actor_id, [])) == 0:
                self._finish_game(game, actor_id)
            else:
                self._persist_game(game)

            return True, ""

    async def challenge_draw_four(self, game_id: str, actor_id: int, token: int) -> Tuple[bool, str]:
        """
        Bluff call system:
        - If challenge succeeds, attacker illegally played +4:
          attacker draws 4, challenger keeps turn, no penalty on challenger.
        - If challenge fails, challenger draws 6 total and turn passes.
        """
        game = self.games_by_id.get(game_id)
        if not game:
            return False, "Private game not found."

        async with game.lock:
            state = game.draw_four_state

            if game.status != "active":
                return False, "This private battle is already finished."

            if token != game.turn_token:
                return False, "Stale action ignored."

            if not state or state.resolved:
                return False, "No +4 challenge is available right now."

            if actor_id != state.challenger_id:
                return False, "Only the affected player can challenge this +4."

            if actor_id != game.current_turn_user_id:
                return False, "Challenge is only available on your turn."

            if game.draw_penalty != 4:
                return False, "This +4 is not challengeable anymore."

            state.resolved = True

            if state.attacker_had_legal_alternative:
                # Challenge successful: attacker bluffed.
                self._draw_cards(game, state.attacker_id, 4)
                game.draw_penalty = 0
                game.last_action = "Challenge succeeded. +4 bluff caught."
                # Challenger keeps the turn.
                game.drew_this_turn = False
                game.turn_token += 1
                self._persist_game(game)
                return True, "Challenge succeeded."

            # Challenge failed: challenger draws 6 and loses turn.
            self._draw_cards(game, actor_id, 6)
            game.draw_penalty = 0
            game.last_action = "Challenge failed. Challenger drew 6 cards."
            self._advance_turn(game, keep_same_player=False)
            self._persist_game(game)
            return True, "Challenge failed."

    async def draw_card(self, game_id: str, actor_id: int, token: int) -> Tuple[bool, str]:
        game = self.games_by_id.get(game_id)
        if not game:
            return False, "Private game not found."

        async with game.lock:
            if game.status != "active":
                return False, "This private battle is already finished."

            if token != game.turn_token:
                return False, "Stale action ignored."

            if actor_id != game.current_turn_user_id:
                return False, "It is not your turn."

            if game.choosing_color_for is not None:
                return False, "Choose a color first."

            # If +4 challenge exists and this player chooses not to challenge,
            # drawing means they accept the penalty.
            if game.draw_four_state and not game.draw_four_state.resolved and actor_id == game.draw_four_state.challenger_id:
                state = game.draw_four_state
                state.resolved = True
                n = game.draw_penalty if game.draw_penalty > 0 else 4
                self._draw_cards(game, actor_id, n)
                game.draw_penalty = 0
                game.last_action = (
                    f"Accepted +4 and drew {n} cards."
                    if n != 1
                    else "Accepted +4 and drew 1 card."
                )
                self._advance_turn(game, keep_same_player=False)
                self._persist_game(game)
                return True, ""

            if game.draw_penalty == 0 and game.drew_this_turn:
                return False, "You already drew. Play a card or pass."

            n = game.draw_penalty if game.draw_penalty > 0 else 1
            self._draw_cards(game, actor_id, n)

            if game.draw_penalty > 0:
                game.draw_penalty = 0
                game.last_action = (
                    f"Drew {n} penalty cards." if n != 1 else "Drew 1 penalty card."
                )
                self._advance_turn(game, keep_same_player=False)
            else:
                game.drew_this_turn = True
                game.last_action = "Drew 1 card."
                game.turn_token += 1

            self._persist_game(game)
            return True, ""

    async def pass_turn(self, game_id: str, actor_id: int, token: int) -> Tuple[bool, str]:
        game = self.games_by_id.get(game_id)
        if not game:
            return False, "Private game not found."

        async with game.lock:
            if game.status != "active":
                return False, "This private battle is already finished."

            if token != game.turn_token:
                return False, "Stale action ignored."

            if actor_id != game.current_turn_user_id:
                return False, "It is not your turn."

            if game.choosing_color_for is not None:
                return False, "Choose a color first."

            if game.draw_four_state and not game.draw_four_state.resolved and actor_id == game.draw_four_state.challenger_id:
                return False, "Resolve the +4 by challenging or drawing first."

            if not game.drew_this_turn:
                return False, "You can pass only after drawing."

            game.last_action = "Passed turn"
            self._advance_turn(game, keep_same_player=False)
            self._persist_game(game)
            return True, ""

    async def close_game(self, game_id: str, reason: str = "cancelled") -> None:
        game = self.games_by_id.get(game_id)
        if not game:
            return

        async with game.lock:
            game.status = reason
            game.ended_at = time.time()
            self.active_game_by_user.pop(game.player1_id, None)
            self.active_game_by_user.pop(game.player2_id, None)
            self._persist_game(game)
            self._clear_user_mapping(game.player1_id)
            self._clear_user_mapping(game.player2_id)


private_battles = PrivateBattleService()


def board_text(game: PrivateGame, viewer_id: int, viewer_name: str, opp_name: str, bot_username: str = "unor0bot") -> str:
    top = game.discard[-1]
    turn_name = viewer_name if game.current_turn_user_id == viewer_id else opp_name
    active_color = c.COLOR_ICONS.get(top.color or c.BLACK, "⬛️")

    if game.status == "pending_start":
        phase = "Waiting for host to start"
    elif game.choosing_color_for == viewer_id:
        phase = "Choose a color in inline"
    elif game.draw_four_state and not game.draw_four_state.resolved and viewer_id == game.draw_four_state.challenger_id:
        phase = "Opponent used +4 — challenge or draw"
    elif game.current_turn_user_id == viewer_id and game.drew_this_turn:
        phase = "You drew a card: play or pass in inline"
    elif game.current_turn_user_id == viewer_id:
        phase = "Your turn: play or draw in inline"
    else:
        phase = "Opponent turn"

    extra = ""
    if game.draw_penalty > 0:
        extra += f"\n{smallcaps('Penalty')}: <code>+{game.draw_penalty}</code>"
    if game.draw_four_state and not game.draw_four_state.resolved:
        extra += f"\n{smallcaps('Challenge')}: <b>Available</b>"

    head = custom_emoji_heading_html("6314237464315696206", "🎮", "Private 1v1 Friendly Battle")
    return (
        "%s\n\n"
        "<b>%s</b> vs <b>%s</b>\n"
        "%s: <code>%d</code> · %s: <code>%d</code>\n"
        "%s: <code>%s</code>\n"
        "%s: %s\n"
        "%s: <b>%s</b>\n"
        "%s: %s%s\n"
        "%s: %s\n"
        "%s"
        % (
            head,
            viewer_name,
            opp_name,
            smallcaps("Your cards"),
            len(game.hands.get(viewer_id, [])),
            smallcaps("Opponent cards"),
            len(game.hands.get(game.opponent(viewer_id), [])),
            smallcaps("Top card"),
            repr(top),
            smallcaps("Active color"),
            active_color,
            smallcaps("Turn"),
            turn_name,
            smallcaps("Last action"),
            game.last_action or "-",
            extra,
            smallcaps("Phase"),
            phase,
            smallcaps(f"Play via @{bot_username} inline in your selected chat"),
        )
    )