#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# UNO Telegram bot — by demon (@demon12809)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


import unittest

from game import Game
from player import Player
import card as c


class _DummyUser:
    def __init__(self, uid, name):
        self.id = uid
        self.first_name = name


class Test(unittest.TestCase):

    game = None

    def setUp(self):
        self.game = Game(None)

    def test_insert(self):
        p0 = Player(self.game, "Player 0")
        p1 = Player(self.game, "Player 1")
        p2 = Player(self.game, "Player 2")

        self.assertEqual(p0, p2.next)
        self.assertEqual(p1, p0.next)
        self.assertEqual(p2, p1.next)

        self.assertEqual(p0.prev, p2)
        self.assertEqual(p1.prev, p0)
        self.assertEqual(p2.prev, p1)

    def test_reverse(self):
        p0 = Player(self.game, "Player 0")
        p1 = Player(self.game, "Player 1")
        p2 = Player(self.game, "Player 2")
        self.game.reverse()
        p3 = Player(self.game, "Player 3")

        self.assertEqual(p0, p3.next)
        self.assertEqual(p1, p2.next)
        self.assertEqual(p2, p0.next)
        self.assertEqual(p3, p1.next)

        self.assertEqual(p0, p2.prev)
        self.assertEqual(p1, p3.prev)
        self.assertEqual(p2, p1.prev)
        self.assertEqual(p3, p0.prev)

    def test_leave(self):
        p0 = Player(self.game, "Player 0")
        p1 = Player(self.game, "Player 1")
        p2 = Player(self.game, "Player 2")

        p1.leave()

        self.assertEqual(p0, p2.next)
        self.assertEqual(p2, p0.next)

    def test_draw(self):
        p = Player(self.game, "Player 0")
        self.game.start()

        deck_before = len(self.game.deck.cards)
        top_card = self.game.deck.cards[-1]

        p.draw()

        self.assertEqual(top_card, p.cards[-1])
        self.assertEqual(deck_before, len(self.game.deck.cards) + 1)

    def test_draw_two(self):
        p = Player(self.game, "Player 0")
        self.game.start()

        deck_before = len(self.game.deck.cards)
        self.game.draw_counter = 2

        p.draw()

        self.assertEqual(deck_before, len(self.game.deck.cards) + 2)

    def test_playable_cards_simple(self):
        p = Player(self.game, "Player 0")

        self.game.last_card = c.Card(c.RED, '5')

        p.cards = [c.Card(c.RED, '0'), c.Card(c.RED, '5'), c.Card(c.BLUE, '0'),
                   c.Card(c.GREEN, '5'), c.Card(c.GREEN, '8')]

        expected = [c.Card(c.RED, '0'), c.Card(c.RED, '5'),
                    c.Card(c.GREEN, '5')]

        self.assertListEqual(p.playable_cards(), expected)

    def test_playable_cards_on_draw_two(self):
        p = Player(self.game, "Player 0")

        self.game.last_card = c.Card(c.RED, c.DRAW_TWO)
        self.game.draw_counter = 2
        self.game.stacking_enabled = True

        p.cards = [c.Card(c.RED, c.DRAW_TWO), c.Card(c.RED, '5'),
                   c.Card(c.BLUE, '0'), c.Card(c.GREEN, '5'),
                   c.Card(c.GREEN, c.DRAW_TWO)]

        expected = [c.Card(c.RED, c.DRAW_TWO), c.Card(c.GREEN, c.DRAW_TWO)]

        self.assertListEqual(p.playable_cards(), expected)

    def test_draw_two_cannot_stack_when_disabled(self):
        p = Player(self.game, "Player 0")

        self.game.last_card = c.Card(c.RED, c.DRAW_TWO)
        self.game.draw_counter = 2
        self.game.stacking_enabled = False
        p.cards = [c.Card(c.RED, c.DRAW_TWO)]

        self.assertListEqual(p.playable_cards(), [])

    def test_playable_cards_on_draw_four(self):
        p = Player(self.game, "Player 0")

        self.game.last_card = c.Card(c.RED, None, c.DRAW_FOUR)
        self.game.draw_counter = 4

        p.cards = [c.Card(c.RED, c.DRAW_TWO), c.Card(c.RED, '5'),
                   c.Card(c.BLUE, '0'), c.Card(c.GREEN, '5'),
                   c.Card(c.GREEN, c.DRAW_TWO),
                   c.Card(None, None, c.DRAW_FOUR),
                   c.Card(None, None, c.CHOOSE)]

        expected = list()

        self.assertListEqual(p.playable_cards(), expected)

    def test_bluffing(self):
        p = Player(self.game, "Player 0")
        Player(self.game, "Player 01")

        self.game.last_card = c.Card(c.RED, '1')

        p.cards = [c.Card(c.RED, c.DRAW_TWO), c.Card(c.RED, '5'),
                   c.Card(c.BLUE, '0'), c.Card(c.GREEN, '5'),
                   c.Card(c.RED, '5'), c.Card(c.GREEN, c.DRAW_TWO),
                   c.Card(None, None, c.DRAW_FOUR),
                   c.Card(None, None, c.CHOOSE)]

        p.playable_cards()
        self.assertTrue(p.bluffing)

        p.cards = [c.Card(c.BLUE, '1'), c.Card(c.GREEN, '1'),
                   c.Card(c.GREEN, c.DRAW_TWO),
                   c.Card(None, None, c.DRAW_FOUR),
                   c.Card(None, None, c.CHOOSE)]

        p.playable_cards()

        p.play(c.Card(None, None, c.DRAW_FOUR))
        self.game.choose_color(c.GREEN)

        self.assertFalse(self.game.current_player.prev.bluffing)

    def test_rainbow_lightning_use(self):
        self.game.set_mode("rainbow")
        self.game.deck._fill_rainbow_()
        p0 = Player(self.game, _DummyUser(10, "p0"))
        p1 = Player(self.game, _DummyUser(11, "p1"))
        self.game.current_player = p0
        self.game.last_card = c.Card(c.RED, c.ONE)
        p0.cards = [c.Card(None, None, c.RAINBOW_LIGHTNING)]

        p0.play(c.Card(None, None, c.RAINBOW_LIGHTNING))
        self.assertTrue(self.game.choosing_color)
        self.assertTrue(self.game.pending_skip_after_color)

        self.game.choose_color(c.BLUE)
        # Lightning: choose color, then skip next player.
        self.assertEqual(self.game.current_player, p0)
        self.assertFalse(self.game.pending_skip_after_color)
        self.assertEqual(self.game.last_card.color, c.BLUE)

    def test_rainbow_monster_use(self):
        self.game.set_mode("rainbow")
        self.game.deck._fill_rainbow_()
        p0 = Player(self.game, _DummyUser(20, "p0"))
        p1 = Player(self.game, _DummyUser(21, "p1"))
        self.game.current_player = p0
        self.game.last_card = c.Card(c.GREEN, c.TWO)
        p0.cards = [c.Card(None, None, c.RAINBOW_MONSTER)]

        p0.play(c.Card(None, None, c.RAINBOW_MONSTER))
        self.assertTrue(self.game.choosing_color)
        self.assertEqual(self.game.draw_counter, 4)

        self.game.choose_color(c.YELLOW)
        self.assertEqual(self.game.current_player, p1)
        self.assertEqual(self.game.last_card.color, c.YELLOW)
        self.assertEqual(len(p1.cards), 0)

        p1.draw()
        self.assertEqual(len(p1.cards), 4)
        self.assertEqual(self.game.draw_counter, 0)

    def test_rainbow_wild_use(self):
        self.game.set_mode("rainbow")
        self.game.deck._fill_rainbow_()
        p0 = Player(self.game, _DummyUser(30, "p0"))
        p1 = Player(self.game, _DummyUser(31, "p1"))
        self.game.current_player = p0
        self.game.last_card = c.Card(c.YELLOW, c.THREE)
        p0.cards = [c.Card(None, None, c.RAINBOW_WILD)]

        p0.play(c.Card(None, None, c.RAINBOW_WILD))
        self.assertTrue(self.game.choosing_color)
        self.assertEqual(self.game.draw_counter, 0)

        self.game.choose_color(c.PURPLE)
        self.assertEqual(self.game.current_player, p1)
        self.assertEqual(self.game.last_card.color, c.PURPLE)
