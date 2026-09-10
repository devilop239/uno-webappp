#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from unittest.mock import AsyncMock, patch

import card as c
from actions import do_call_bluff, do_draw
from game import Game
from player import Player


class _DummyUser:
    def __init__(self, uid, name):
        self.id = uid
        self.first_name = name


class _DummyChat:
    def __init__(self, cid):
        self.id = cid


class TestRainbowActions(unittest.IsolatedAsyncioTestCase):
    def _mk_game_two_players(self):
        game = Game(_DummyChat(999))
        game.set_mode("rainbow")
        game.deck._fill_rainbow_()
        p0 = Player(game, _DummyUser(1, "p0"))
        p1 = Player(game, _DummyUser(2, "p1"))
        game.current_player = p0
        return game, p0, p1

    async def test_do_call_bluff_true_bluff_penalizes_previous_player(self):
        game, attacker, challenger = self._mk_game_two_players()
        game.current_player = challenger
        game.last_card = c.Card(c.RED, None, c.DRAW_FOUR)
        game.draw_counter = 4
        game.last_bluffable_draw_special = True
        game.last_draw_special_challengeable = True

        prev_count = len(attacker.cards)
        ch_count = len(challenger.cards)

        with patch("actions.send_message", new=AsyncMock()):
            await do_call_bluff(None, challenger)

        self.assertEqual(len(attacker.cards), prev_count + 4)
        self.assertEqual(len(challenger.cards), ch_count)
        self.assertEqual(game.current_player, attacker)
        self.assertFalse(game.last_bluffable_draw_special)

    async def test_do_call_bluff_false_bluff_penalizes_challenger(self):
        game, attacker, challenger = self._mk_game_two_players()
        game.current_player = challenger
        game.last_card = c.Card(c.BLUE, None, c.DRAW_EIGHT)
        game.draw_counter = 8
        game.last_bluffable_draw_special = False
        game.last_draw_special_challengeable = True

        prev_count = len(attacker.cards)
        ch_count = len(challenger.cards)

        with patch("actions.send_message", new=AsyncMock()):
            await do_call_bluff(None, challenger)

        self.assertEqual(len(attacker.cards), prev_count)
        self.assertEqual(len(challenger.cards), ch_count + 10)
        self.assertEqual(game.current_player, attacker)
        self.assertFalse(game.last_bluffable_draw_special)

    async def test_do_draw_normal_draws_exactly_one_and_keeps_turn(self):
        game, current, _other = self._mk_game_two_players()
        game.current_player = current
        game.last_card = c.Card(c.YELLOW, c.THREE)
        game.draw_counter = 0

        before = len(current.cards)
        with patch("actions.send_message", new=AsyncMock()):
            await do_draw(None, current)

        self.assertEqual(len(current.cards), before + 1)
        self.assertEqual(game.current_player, current)
        self.assertEqual(game.draw_counter, 0)

    async def test_do_draw_penalty_advances_turn(self):
        game, attacker, victim = self._mk_game_two_players()
        game.current_player = victim
        game.last_card = c.Card(c.GREEN, None, c.RAINBOW_MONSTER)
        game.last_card.color = c.GREEN
        game.draw_counter = 4

        before = len(victim.cards)
        with patch("actions.send_message", new=AsyncMock()):
            await do_draw(None, victim)

        self.assertEqual(len(victim.cards), before + 4)
        self.assertEqual(game.draw_counter, 0)
        self.assertEqual(game.current_player, attacker)

    async def test_do_draw_stacked_penalty_draws_full_amount(self):
        game, attacker, victim = self._mk_game_two_players()
        game.current_player = victim
        game.last_card = c.Card(c.BLUE, None, c.DRAW_EIGHT)
        game.draw_counter = 16

        before = len(victim.cards)
        with patch("actions.send_message", new=AsyncMock()):
            await do_draw(None, victim)

        self.assertEqual(len(victim.cards), before + 16)
        self.assertEqual(game.draw_counter, 0)
        self.assertEqual(game.current_player, attacker)

    async def test_do_call_bluff_false_bluff_uses_stacked_total(self):
        game, attacker, challenger = self._mk_game_two_players()
        game.current_player = challenger
        game.last_card = c.Card(c.BLUE, None, c.DRAW_FOUR)
        game.draw_counter = 12
        game.last_bluffable_draw_special = False
        game.last_draw_special_challengeable = True

        ch_count = len(challenger.cards)
        with patch("actions.send_message", new=AsyncMock()):
            await do_call_bluff(None, challenger)

        # Failed challenge draws stacked total + 2.
        self.assertEqual(len(challenger.cards), ch_count + 14)

    async def test_do_call_bluff_ignored_when_not_challengeable(self):
        game, _attacker, challenger = self._mk_game_two_players()
        game.current_player = challenger
        game.last_card = c.Card(c.BLUE, None, c.DRAW_FOUR)
        game.draw_counter = 12
        game.last_bluffable_draw_special = False
        game.last_draw_special_challengeable = False

        before = len(challenger.cards)
        with patch("actions.send_message", new=AsyncMock()):
            await do_call_bluff(None, challenger)

        self.assertEqual(len(challenger.cards), before)
        self.assertEqual(game.draw_counter, 12)

