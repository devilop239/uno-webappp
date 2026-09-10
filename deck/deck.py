# -*- coding: utf-8 -*-
"""
UNO Deck generator and card shuffling mechanics.
"""

from random import shuffle
import logging

import deck.card as c
from deck.card import Card
from errors import DeckEmptyError


class Deck(object):
    """Represents a deck of UNO cards."""

    def __init__(self):
        self.cards = list()
        self.graveyard = list()
        self.logger = logging.getLogger(__name__)

    def shuffle(self):
        """Shuffles the deck."""
        self.logger.debug("Shuffling Deck")
        shuffle(self.cards)

    def draw(self):
        """Draws a card from this deck."""
        try:
            card = self.cards.pop()
            self.logger.debug("Drawing card %s", card)
            return card
        except IndexError:
            if len(self.graveyard):
                while len(self.graveyard):
                    self.cards.append(self.graveyard.pop())
                self.shuffle()
                return self.draw()
            else:
                raise DeckEmptyError()

    def dismiss(self, card):
        """Returns a card to the discard pile."""
        if card.special:
            card.color = None
        if self.graveyard and self.graveyard[-1] is card:
            return
        self.graveyard.append(card)

    def _fill_classic_(self, multiplier=1):
        self.cards.clear()
        for _ in range(multiplier):
            for color in c.COLORS:
                for value in c.VALUES:
                    self.cards.append(Card(color, value))
                    if not value == c.ZERO:
                        self.cards.append(Card(color, value))
            for special in c.SPECIALS:
                for _ in range(4):
                    self.cards.append(Card(None, None, special=special))
        self.shuffle()

    def _fill_wild_(self, multiplier=1):
        self.cards.clear()
        for _ in range(multiplier):
            for color in c.COLORS:
                for value in c.WILD_VALUES:
                    for _ in range(4):
                        self.cards.append(Card(color, value))
            for special in c.WILD_SPECIALS:
                for _ in range(6):
                    self.cards.append(Card(None, None, special=special))
        self.shuffle()

    def _fill_rainbow_(self, multiplier=1):
        self.cards.clear()
        colors = c.RAINBOW_COLORS
        for _ in range(multiplier):
            for color in colors:
                for value in c.RAINBOW_VALUES:
                    self.cards.append(Card(color, value))
                    if value != c.ZERO:
                        self.cards.append(Card(color, value))
            rainbow_power_cards = (
                c.DRAW_FOUR,
                c.DRAW_EIGHT,
                c.RAINBOW_WILD,
                c.RAINBOW_MONSTER,
                c.RAINBOW_LIGHTNING,
            )
            for special in rainbow_power_cards:
                for _ in range(4):
                    self.cards.append(Card(None, None, special=special))

        self.shuffle()

    def _fill_no_mercy_(self, multiplier=1):
        try:
            from modes.no_mercy import fill_no_mercy_deck
            fill_no_mercy_deck(self, multiplier=multiplier)
        except (ImportError, AttributeError):
            from no_mercy.deck_fill import fill_no_mercy_deck
            fill_no_mercy_deck(self, multiplier=multiplier)
