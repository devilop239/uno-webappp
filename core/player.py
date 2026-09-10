# -*- coding: utf-8 -*-
"""
Player model and hand state machine.
"""

from __future__ import annotations
import logging
from datetime import datetime

import deck.card as c
from errors import CardNotOwnedError, DeckEmptyError, IllegalCardError
from config import WAITING_TIME


class Player(object):
    """
    Represents an active player in a game.
    Organized as a doubly-linked ring list supporting direction reversals.
    """

    def __init__(self, game, user):
        self.cards = list()
        self.game = game
        self.user = user
        self.logger = logging.getLogger(__name__)

        if game.current_player:
            self.next = game.current_player
            self.prev = game.current_player.prev
            game.current_player.prev.next = self
            game.current_player.prev = self
        else:
            self._next = self
            self._prev = self
            game.current_player = self

        self.bluffing = False
        self.drew = False
        self.anti_cheat = 0
        self.turn_started = datetime.now()
        self.waiting_time = WAITING_TIME

    def draw_first_hand(self):
        try:
            hand_size = self.game.effective_hand_size()
            for _ in range(hand_size):
                self.cards.append(self.game.deck.draw())
        except DeckEmptyError:
            for card in self.cards:
                self.game.deck.dismiss(card)
            raise

    def _unlink_from_ring(self):
        if self.next is self:
            return
        self.next.prev = self.prev
        self.prev.next = self.next
        self.next = None
        self.prev = None

    def _uses_team_shared_hand(self) -> bool:
        game = self.game
        if not getattr(game, "is_team_mode", False) or not getattr(game, "team_locked", False):
            return False
        uid = getattr(self.user, "id", None)
        if uid is None:
            return False
        tid = game.team_of(uid)
        if not tid:
            return False
        shared = game.team_shared_hands.get(tid)
        return shared is not None and self.cards is shared

    def leave(self):
        self._unlink_from_ring()
        if self._uses_team_shared_hand():
            uid = int(self.user.id)
            tid = self.game.team_of(uid)
            members = self.game.team_members.get(tid) or []
            if uid in members:
                members.remove(uid)
            self.cards = list()
            return
        for card in self.cards:
            self.game.deck.dismiss(card)
        self.cards = list()

    def __repr__(self):
        return repr(self.user)

    def __str__(self):
        return str(self.user)

    @property
    def next(self):
        return self._next if not self.game.reversed else self._prev

    @next.setter
    def next(self, player):
        if not self.game.reversed:
            self._next = player
        else:
            self._prev = player

    @property
    def prev(self):
        return self._prev if not self.game.reversed else self._next

    @prev.setter
    def prev(self, player):
        if not self.game.reversed:
            self._prev = player
        else:
            self._next = player

    def draw(self):
        _amount = self.game.draw_counter or 1
        try:
            for _ in range(_amount):
                self.cards.append(self.game.deck.draw())
        except DeckEmptyError:
            raise
        finally:
            self.game.draw_counter = 0
            self.drew = True

    def play(self, card):
        if card not in self.cards:
            raise CardNotOwnedError("The selected card is not in the player's hand")
        if not self._card_playable(card):
            raise IllegalCardError("The selected card cannot be played now")
        if self.game.mode != "no_mercy":
            self.game.last_bluffable_draw_special = self._is_illegal_draw_special_play(card)
        else:
            self.game.last_bluffable_draw_special = False
        self.cards.remove(card)
        self.game.play_card(card)

    def playable_cards(self):
        if self.game.mode == "no_mercy":
            try:
                from modes.no_mercy import mercy_playable
                return mercy_playable(self)
            except (ImportError, AttributeError):
                from no_mercy.playability import playable_cards as mercy_playable
                return mercy_playable(self)

        playable = list()
        last = self.game.last_card
        self.logger.debug("Last card was " + str(last))
        cards = self.cards
        if self.drew:
            cards = self.cards[-1:]

        self.bluffing = False
        for card in cards:
            if self._card_playable(card):
                self.logger.debug("Matching!")
                playable.append(card)
                self.bluffing = self.bluffing or card.color == last.color

        if len(self.cards) == 1 and self.cards[0].special:
            return list()

        return playable

    def _card_playable(self, card):
        if self.game.mode == "no_mercy":
            try:
                from modes.no_mercy import is_card_playable
                return is_card_playable(self, card)
            except (ImportError, AttributeError):
                from no_mercy.playability import is_card_playable
                return is_card_playable(self, card)

        if self.game.mode == "rainbow":
            return self._rainbow_card_playable(card)

        is_playable = True
        last = self.game.last_card
        self.logger.debug("Checking card " + str(card))

        if (card.color != last.color and card.value != last.value and not card.special):
            self.logger.debug("Card's color or value doesn't match")
            is_playable = False
        elif last.value == c.DRAW_TWO and self.game.draw_counter:
            if not self.game.stacking_enabled or card.value != c.DRAW_TWO:
                self.logger.debug("Player has to draw and can't counter")
                is_playable = False
        elif last.special in (c.DRAW_FOUR, c.DRAW_EIGHT) and self.game.draw_counter:
            if self.game.stacking_enabled:
                if card.special not in (c.DRAW_FOUR, c.DRAW_EIGHT):
                    self.logger.debug("Stacking ON: only +4 or +8 can counter +4")
                    is_playable = False
            else:
                self.logger.debug("Player has to draw and can't counter")
                is_playable = False
        elif (last.special == c.CHOOSE or last.special == c.DRAW_FOUR or last.special == c.DRAW_EIGHT) and \
                (card.special == c.CHOOSE or card.special == c.DRAW_FOUR):
            self.logger.debug("Can't play colorchooser on another one")
            is_playable = False
        elif not last.color:
            self.logger.debug("Last card has no color")
            is_playable = False

        return is_playable

    def _is_illegal_draw_special_play(self, card):
        if card.special not in (c.DRAW_FOUR, c.DRAW_EIGHT):
            return False
        if self.game.draw_counter:
            return False
        last = self.game.last_card
        last_color = getattr(last, "color", None)
        if not last_color:
            return False
        for hand_card in self.cards:
            if hand_card is card:
                continue
            if hand_card.special:
                continue
            if hand_card.color == last_color:
                return True
        return False

    def _rainbow_card_playable(self, card):
        last = self.game.last_card
        power_specials = {
            c.DRAW_FOUR,
            c.DRAW_EIGHT,
            c.RAINBOW_WILD,
            c.RAINBOW_LIGHTNING,
            c.RAINBOW_MONSTER,
        }

        if last.value == c.DRAW_TWO and card.value != c.DRAW_TWO and self.game.draw_counter:
            return False
        if last.special in (c.DRAW_FOUR, c.DRAW_EIGHT, c.RAINBOW_MONSTER) and self.game.draw_counter:
            if last.special == c.RAINBOW_MONSTER:
                return False
            if self.game.stacking_enabled:
                if card.special not in (c.DRAW_FOUR, c.DRAW_EIGHT):
                    return False
            else:
                return False
        if card.special in power_specials:
            return True
        if not last.color:
            return False
        return card.color == last.color or card.value == last.value
