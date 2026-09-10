"""NO MERCY — 30+ card elimination."""
import asyncio
import unittest

import card as c
from game import Game
from player import Player
from no_mercy.constants import ELIMINATION_HAND_SIZE
from no_mercy.elimination import check_and_eliminate, enforce_elimination_threshold
from shared_vars import gm
from no_mercy.playability import is_card_playable
from no_mercy.state import is_eliminated_uid, mark_eliminated


class FakeChat:
    id = 99
    title = "test"


class FakeUser:
    def __init__(self, uid):
        self.id = uid
        self.first_name = "P%d" % uid
        self.username = None
        self.is_bot = False


class NoMercyEliminationTests(unittest.TestCase):
    def _game(self, n=3):
        game = Game(FakeChat())
        game.set_mode("no_mercy")
        from no_mercy import configure_game_start

        configure_game_start(game)
        players = [Player(game, FakeUser(i + 1)) for i in range(n)]
        return game, players

    def test_mark_eliminated_exists(self):
        game, players = self._game(2)
        mark_eliminated(game, players[0].user.id)
        self.assertTrue(is_eliminated_uid(game, players[0].user.id))

    def test_elimination_at_30_removes_player(self):
        async def run():
            game, players = self._game(3)
            victim = players[1]
            victim.cards = [c.Card("r", "5")] * ELIMINATION_HAND_SIZE
            before = len(game.players)
            eliminated = await check_and_eliminate(None, victim)
            self.assertTrue(eliminated)
            self.assertTrue(is_eliminated_uid(game, victim.user.id))
            self.assertEqual(len(game.players), before - 1)
            self.assertFalse(is_card_playable(victim, c.Card("r", "5")))

        asyncio.run(run())

    def test_elimination_at_31_cards(self):
        async def run():
            game, players = self._game(2)
            victim = players[0]
            victim.cards = [c.Card("b", "3")] * 31
            self.assertTrue(await check_and_eliminate(None, victim))
            self.assertEqual(len(game.players), 1)

        asyncio.run(run())

    def test_two_player_elimination_ends_match(self):
        async def run():
            from utils import game_is_running

            game, players = self._game(2)
            gm.chatid_games[game.chat.id] = [game]
            game.started = True
            survivor = players[1]
            victim = players[0]
            victim.cards = [c.Card("r", "5")] * 30
            self.assertTrue(await enforce_elimination_threshold(None, victim))
            self.assertFalse(game_is_running(game))
            self.assertIn(survivor.user.id, game.finish_order)

        asyncio.run(run())

    def test_three_player_elimination_continues_match(self):
        async def run():
            game, players = self._game(3)
            gm.chatid_games[game.chat.id] = [game]
            game.started = True
            victim = players[1]
            victim.cards = [c.Card("g", "2")] * 31
            self.assertTrue(await enforce_elimination_threshold(None, victim))
            self.assertEqual(len(game.players), 2)
            self.assertTrue(game_is_running(game))

        from utils import game_is_running

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
