# -*- coding: utf-8 -*-
"""
Core UNO Game state machine.
"""

import logging
import random
import uuid
from config import ADMIN_LIST, OPEN_LOBBY, DEFAULT_GAMEMODE
from datetime import datetime, timezone

from deck import Deck
import deck.card as c
from deck.styles import (
    DECK_STYLE_NORMAL,
    deck_style_label,
    is_alt_deck_style,
    normalize_deck_style,
    resolve_deck_style,
)


class Game(object):
    """Represents an active UNO game instance."""

    def __init__(self, chat):
        self.chat = chat
        self.last_card = None
        self.owner = set(ADMIN_LIST) if ADMIN_LIST else set()
        self.deck = Deck()
        self.logger = logging.getLogger(__name__)

        self.match_uuid = str(uuid.uuid4())
        self.started_at = None
        self.turn_count = 0
        self.participant_ids = []
        self.finish_order = []

        self.current_player = None
        self.reversed = False
        self.choosing_color = False
        self.started = False
        self.draw_counter = 0
        self.players_won = 0
        self.starter = None
        self.mode = DEFAULT_GAMEMODE
        self.hand_size = None
        self.stacking_enabled = False
        self.deck_style = DECK_STYLE_NORMAL
        self.pending_skip_after_color = False
        self.last_bluffable_draw_special = False
        self.last_draw_special_challengeable = False
        self.countdown_task = None
        self.open = OPEN_LOBBY
        self.translate = False
        self.turn_prompt_message_id = None
        self.is_team_mode = False
        self.team_size = 0
        self.team_assignment = ""
        self.team_names = {"A": "", "B": ""}
        self.team_members = {"A": [], "B": []}
        self.team_shared_hands = {"A": [], "B": []}
        self.team_locked = False
        self.last_winning_team_id = None
        self.team_turn_order_ids = []
        self.team_turn_index = 0
        self.team_action_stats = {}
        self.rematch_payload = None

    @property
    def players(self):
        players = list()
        if not self.current_player:
            return players
        current_player = self.current_player
        itplayer = current_player.next
        players.append(current_player)
        while itplayer and itplayer != current_player:
            players.append(itplayer)
            itplayer = itplayer.next
        return players

    def start(self, deal_hands: bool = True):
        hand_size = self.effective_hand_size()
        player_count = len(self.players)
        total_cards_needed = hand_size * player_count + (player_count * 15)

        base_deck_sizes = {
            "classic": 108,
            "text": 108,
            "wild": 146,
            "rainbow": 120,
            "sudden_death": 108,
            "team": 108,
            "no_mercy": 63,
        }
        if self.mode == "no_mercy":
            try:
                from modes.no_mercy import configure_game_start, deck_multiplier_for_players
                configure_game_start(self)
                multiplier = deck_multiplier_for_players(player_count, hand_size=hand_size)
            except (ImportError, AttributeError):
                from no_mercy import configure_game_start
                from no_mercy.deck_fill import deck_multiplier_for_players
                configure_game_start(self)
                multiplier = deck_multiplier_for_players(player_count, hand_size=hand_size)
            self.mercy_deck_multiplier = multiplier
            self.deck._fill_no_mercy_(multiplier)
        else:
            base_size = base_deck_sizes.get(self.mode, 108)
            import math
            multiplier = max(1, math.ceil(total_cards_needed / base_size))

            if self.mode == "wild":
                self.deck._fill_wild_(multiplier)
            elif self.mode == "rainbow":
                self.deck._fill_rainbow_(multiplier)
            else:
                self.deck._fill_classic_(multiplier)

        self._first_card_()
        self.started = True
        self.started_at = datetime.now(timezone.utc)
        self.participant_ids = []

        if deal_hands:
            for player in self.players:
                player.draw_first_hand()

        for p in self.players:
            u = getattr(p, "user", None)
            uid = getattr(u, "id", None)
            if uid is not None:
                self.participant_ids.append(uid)

    def add_participant(self, user_id):
        if user_id not in self.participant_ids:
            self.participant_ids.append(user_id)

    def set_mode(self, mode):
        self.mode = mode

    def effective_hand_size(self):
        if self.mode == "no_mercy":
            try:
                from modes.no_mercy import mercy_hand
                return mercy_hand(self)
            except (ImportError, AttributeError):
                from no_mercy.state import effective_hand_size as mercy_hand
                return mercy_hand(self)
        if self.hand_size is not None:
            return self.hand_size
        return 7

    def effective_deck_style(self):
        return resolve_deck_style(self)

    def deck_style_display(self):
        if self.mode == "no_mercy":
            return "ɴᴏ ᴍᴇʀᴄʏ"
        stored = normalize_deck_style(getattr(self, "deck_style", DECK_STYLE_NORMAL))
        if self.mode == "rainbow" and is_alt_deck_style(stored):
            return "%s (Rainbow)" % deck_style_label(DECK_STYLE_NORMAL)
        return deck_style_label(self.effective_deck_style())

    def enable_team_mode(self, team_size: int, assignment: str):
        self.is_team_mode = True
        self.team_size = int(team_size)
        self.team_assignment = str(assignment or "manual")
        self.team_names = {"A": "", "B": ""}
        self.team_members = {"A": [], "B": []}
        self.team_shared_hands = {"A": [], "B": []}
        self.team_locked = False
        self.last_winning_team_id = None
        self.team_turn_order_ids = []
        self.team_turn_index = 0
        self.team_action_stats = {}

    def disable_team_mode(self):
        self.is_team_mode = False
        self.team_size = 0
        self.team_assignment = ""
        self.team_names = {"A": "", "B": ""}
        self.team_members = {"A": [], "B": []}
        self.team_shared_hands = {"A": [], "B": []}
        self.team_locked = False
        self.last_winning_team_id = None
        self.team_turn_order_ids = []
        self.team_turn_index = 0
        self.team_action_stats = {}

    def team_of(self, user_id: int):
        uid = int(user_id)
        for tid in ("A", "B"):
            if uid in self.team_members[tid]:
                return tid
        return None

    def team_ready(self) -> bool:
        if not self.is_team_mode:
            return False
        return len(self.team_members["A"]) == self.team_size and len(self.team_members["B"]) == self.team_size

    def set_team_name(self, team_id: str, raw_name: str) -> bool:
        tid = (team_id or "").upper()
        if tid not in ("A", "B") or self.team_locked:
            return False
        cleaned = " ".join((raw_name or "").strip().split())[:24]
        if not cleaned:
            return False
        self.team_names[tid] = cleaned
        return True

    def ensure_team_names(self):
        pairs = [
            ("Inferno", "Frost"),
            ("Thunder", "Shadow"),
            ("Phoenix", "Titan"),
            ("Eclipse", "Nova"),
            ("Vortex", "Blaze"),
            ("Crimson", "Azure"),
        ]
        existing = set(n.lower() for n in self.team_names.values() if n)
        available = [p for p in pairs if p[0].lower() not in existing and p[1].lower() not in existing]
        if not available:
            available = pairs
        a, b = random.choice(available)
        if not self.team_names["A"]:
            self.team_names["A"] = a
        if not self.team_names["B"]:
            self.team_names["B"] = b if b.lower() != self.team_names["A"].lower() else "Nova"

    def move_user_to_team(self, user_id: int, team_id: str) -> bool:
        if not self.is_team_mode or self.team_locked:
            return False
        tid = (team_id or "").upper()
        if tid not in ("A", "B"):
            return False
        uid = int(user_id)
        for x in ("A", "B"):
            if uid in self.team_members[x]:
                self.team_members[x].remove(uid)
        if len(self.team_members[tid]) >= self.team_size:
            return False
        self.team_members[tid].append(uid)
        return True

    def leave_team_lobby(self, user_id: int) -> bool:
        if not self.is_team_mode or self.team_locked:
            return False
        uid = int(user_id)
        for tid in ("A", "B"):
            if uid in self.team_members[tid]:
                self.team_members[tid].remove(uid)
                return True
        return False

    def randomize_teams(self, joined_user_ids):
        users = [int(u) for u in joined_user_ids]
        if len(users) != self.team_size * 2:
            return False
        random.shuffle(users)
        self.team_members["A"] = users[: self.team_size]
        self.team_members["B"] = users[self.team_size :]
        return True

    def alternating_turn_user_ids(self):
        order = []
        for idx in range(self.team_size):
            order.append(self.team_members["A"][idx])
            order.append(self.team_members["B"][idx])
        return order

    def initialize_team_runtime(self, players):
        by_uid = {int(p.user.id): p for p in players}
        turn_ids = self.alternating_turn_user_ids()
        if len(turn_ids) != len(players):
            return False
        try:
            ordered = [by_uid[uid] for uid in turn_ids]
        except KeyError:
            return False
        n = len(ordered)
        for i, p in enumerate(ordered):
            p._next = ordered[(i + 1) % n]
            p._prev = ordered[(i - 1) % n]
        self.current_player = ordered[0]
        self.team_turn_order_ids = list(turn_ids)
        self.team_turn_index = 0
        self.team_locked = True
        self.ensure_team_names()
        self.team_shared_hands = {"A": [], "B": []}
        for tid in ("A", "B"):
            hand = []
            for _ in range(self.effective_hand_size() * self.team_size):
                hand.append(self.deck.draw())
            self.team_shared_hands[tid] = hand
            for uid in self.team_members[tid]:
                by_uid[uid].cards = hand
        for p in players:
            self.team_action_stats[int(p.user.id)] = {
                "special_plays": 0,
                "draw_penalties": 0,
                "turns": 0,
                "winning_move": 0,
            }
        return True

    def team_cards_left(self, team_id: str) -> int:
        tid = (team_id or "").upper()
        return len(self.team_shared_hands.get(tid, []))

    def note_team_action(self, user_id: int, card_obj=None, winning_move: bool = False):
        uid = int(user_id)
        row = self.team_action_stats.get(uid)
        if not row:
            return
        row["turns"] += 1
        if card_obj is not None and (getattr(card_obj, "special", None) or getattr(card_obj, "value", None) in (c.SKIP, c.DRAW_TWO, c.REVERSE)):
            row["special_plays"] += 1
        if winning_move:
            row["winning_move"] += 1

    def choose_team_mvp(self, winning_team_id: str):
        tid = (winning_team_id or "").upper()
        if tid not in ("A", "B"):
            return None, ""
        members = [int(x) for x in self.team_members[tid]]
        if not members:
            return None, ""
        best_uid = None
        best_score = None
        best_row = None
        for uid in members:
            row = self.team_action_stats.get(uid) or {}
            score = (
                int(row.get("winning_move") or 0) * 10
                + int(row.get("special_plays") or 0) * 3
                + int(row.get("turns") or 0)
                - int(row.get("draw_penalties") or 0) * 2
            )
            if best_score is None or score > best_score:
                best_score = score
                best_uid = uid
                best_row = row
        if best_uid is None:
            return None, ""
        reason = (
            "special plays: %d, turns: %d, winning move: %d"
            % (
                int(best_row.get("special_plays") or 0),
                int(best_row.get("turns") or 0),
                int(best_row.get("winning_move") or 0),
            )
        )
        return best_uid, reason

    def reverse(self):
        self.reversed = not self.reversed

    def turn(self):
        self.logger.debug("Next Player")
        self.turn_count += 1
        self.current_player = self.current_player.next
        self.current_player.drew = False
        self.current_player.turn_started = datetime.now()
        self.choosing_color = False

    def _first_card_(self):
        if not self.deck.cards:
            self.set_mode(DEFAULT_GAMEMODE)

        if self.mode == "no_mercy":
            from no_mercy.effects import opening_card_allowed
            while True:
                self.last_card = self.deck.draw()
                if opening_card_allowed(self.last_card):
                    break
                self.deck.cards.append(self.last_card)
                self.deck.shuffle()
            self.play_card(self.last_card, opening=True)
            return

        while not self.last_card or self.last_card.special:
            self.last_card = self.deck.draw()
            if self.last_card.special:
                self.deck.dismiss(self.last_card)

        self.play_card(self.last_card, opening=True)

    def play_card(self, card, opening=False):
        if self.mode == "no_mercy":
            from no_mercy.effects import play_card as mercy_play_card
            mercy_play_card(self, card, opening=opening)
            return
        if not opening:
            self.deck.dismiss(self.last_card)
        self.last_card = card

        self.logger.info(
            "%s %s",
            "Opening card (face-up)" if opening else "Playing card",
            repr(card),
        )
        self.pending_skip_after_color = False
        had_pending_draw = self.draw_counter > 0
        self.last_draw_special_challengeable = False
        if card.value == c.SKIP:
            self.turn()
        elif card.special == c.DRAW_FOUR:
            self.draw_counter += 4
            self.last_draw_special_challengeable = not had_pending_draw
        elif card.special == c.DRAW_EIGHT:
            self.draw_counter += 8
            self.last_draw_special_challengeable = not had_pending_draw
        elif card.special == c.RAINBOW_MONSTER:
            self.draw_counter += 4
        elif card.special == c.RAINBOW_LIGHTNING:
            self.pending_skip_after_color = True
        elif card.value == c.DRAW_TWO:
            self.draw_counter += 2
        elif card.value == c.REVERSE:
            if self.current_player == self.current_player.next.next:
                self.turn()
            else:
                self.reverse()

        if card.special not in (c.CHOOSE, c.DRAW_FOUR, c.DRAW_EIGHT, c.RAINBOW_WILD, c.RAINBOW_LIGHTNING, c.RAINBOW_MONSTER):
            self.turn()
        else:
            self.choosing_color = True

    def choose_color(self, color):
        if self.mode == "no_mercy":
            from no_mercy.effects import choose_color as mercy_choose_color
            return mercy_choose_color(self, color)
        if not self.choosing_color:
            return False
        self.last_card.color = color
        self.turn()
        if self.pending_skip_after_color:
            self.pending_skip_after_color = False
            self.turn()
        return True
