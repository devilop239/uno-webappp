# -*- coding: utf-8 -*-
"""Inline card id resolution (duplicate hands, indexed stems)."""

import unittest

import card as c
from player import Player
from utils import card_from_inline_stem, sorted_hand_cards


class _User:
    def __init__(self, uid):
        self.id = uid
        self.first_name = "Test"
        self.username = None


class _Game:
    current_player = None


class InlineCardStemTests(unittest.TestCase):
    def _player_with_hand(self, cards):
        user = _User(1)
        player = Player(_Game(), user)
        player.cards = list(cards)
        return player

    def test_indexed_stem_resolves_duplicate_cards(self):
        a = c.from_str("r_5")
        b = c.from_str("r_5")
        player = self._player_with_hand([a, b])
        hand = sorted_hand_cards(player)
        self.assertEqual(len(hand), 2)
        self.assertIs(card_from_inline_stem(player, "h0"), hand[0])
        self.assertIs(card_from_inline_stem(player, "h1"), hand[1])

    def test_legacy_stem_still_works(self):
        card = c.from_str("g_skip")
        player = self._player_with_hand([card])
        self.assertEqual(card_from_inline_stem(player, "g_skip"), card)

    def test_blocked_stems_return_none(self):
        player = self._player_with_hand([c.from_str("b_3")])
        self.assertIsNone(card_from_inline_stem(player, "bh0"))
        self.assertIsNone(card_from_inline_stem(player, "blocked_b_3"))


if __name__ == "__main__":
    unittest.main()
