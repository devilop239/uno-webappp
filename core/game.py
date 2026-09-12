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
