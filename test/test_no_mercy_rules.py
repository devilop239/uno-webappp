"""NO MERCY rules + UI consistency tests."""
import unittest

import card as c
from game import Game
from player import Player

from no_mercy.constants import (
    DISCARD_ALL,
    DRAW2,
    W_DRAW4,
    W_DRAW4_REVERSE,
    W_DRAW6,
    W_DRAW10,
    W_ROULETTE,
    W_SKIP_ALL,
    W_WILD,
)
from no_mercy.effects import choose_color, play_card
from no_mercy.playability import is_card_playable
from no_mercy.ui.renderer import card_label, render_status
from no_mercy.ui.tokens import build_callback, parse_callback


class FakeUser:
    def __init__(self, uid, name=None):
        self.id = uid
        self.first_name = name or ("P%d" % uid)
        self.username = None
        self.is_bot = False


class FakeChat:
    id = 99
    title = "Test"


class NoMercyRulesTests(unittest.TestCase):
    def _game_with_players(self, n=3):
        game = Game(FakeChat())
        game.set_mode("no_mercy")
        from no_mercy import configure_game_start

        configure_game_start(game)
        players = []
        for i in range(n):
            players.append(Player(game, FakeUser(i + 1)))
        game.last_card = c.Card("r", "5")
        return game, players[0]

    def test_wild_draw_cards_playable_off_stack(self):
        game, p1 = self._game_with_players()
        for special in (W_WILD, W_DRAW4, W_DRAW6, W_DRAW10, W_DRAW4_REVERSE):
            card = c.Card(None, None, special=special)
            self.assertTrue(
                is_card_playable(p1, card),
                "%s should be playable" % special,
            )

    def test_roulette_and_skip_all_blocked_on_stack(self):
        game, p1 = self._game_with_players()
        game.draw_counter = 4
        game.last_card = c.Card("r", "draw2")
        self.assertFalse(is_card_playable(p1, c.Card(None, None, special=W_ROULETTE)))
        self.assertFalse(is_card_playable(p1, c.Card(None, None, special=W_SKIP_ALL)))

    def test_skip_on_skip(self):
        game, p1 = self._game_with_players()
        game.last_card = c.Card("g", "skip")
        self.assertTrue(is_card_playable(p1, c.Card("r", "skip")))

    def test_discard_all_on_discard_all(self):
        game, p1 = self._game_with_players()
        game.last_card = c.Card("b", DISCARD_ALL)
        self.assertTrue(is_card_playable(p1, c.Card("y", DISCARD_ALL)))

    def test_callback_roundtrip(self):
        game, p1 = self._game_with_players()
        from no_mercy.ui.tokens import refresh_ui_token

        refresh_ui_token(game)
        data = build_callback("p", game, "2")
        self.assertLessEqual(len(data), 64)
        parsed = parse_callback(data)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.action, "p")
        self.assertEqual(parsed.arg, "2")

    def test_render_status_contains_stack(self):
        game, p1 = self._game_with_players()
        game.draw_counter = 16
        text = render_status(game)
        self.assertIn("🔥", text)
        self.assertIn("+16", text)

    def test_card_labels(self):
        from no_mercy.text_style import sc

        self.assertIn("+2", card_label(c.Card("r", DRAW2)))
        self.assertEqual(sc("Wild +4"), card_label(c.Card(None, None, special=W_DRAW4)))
        self.assertEqual(sc("Wild Roulette"), card_label(c.Card(None, None, special=W_ROULETTE)))

    def _play_skip_all_and_choose_red(self, game, actor):
        game.current_player = actor
        skip_all = c.Card(None, None, special=W_SKIP_ALL)
        play_card(game, skip_all)
        self.assertTrue(game.choosing_color)
        self.assertTrue(getattr(game, "mercy_pending_skip_all", False))
        choose_color(game, "r")
        self.assertFalse(getattr(game, "mercy_pending_skip_all", False))

    def test_skip_all_two_players_same_player_again(self):
        game, p1 = self._game_with_players(2)
        p2 = next(p for p in game.players if p is not p1)
        self._play_skip_all_and_choose_red(game, p1)
        self.assertIs(game.current_player, p1)
        self.assertEqual(game.last_card.color, "r")

    def test_skip_all_three_players_same_player_again(self):
        game, p1 = self._game_with_players(3)
        self._play_skip_all_and_choose_red(game, p1)
        self.assertIs(game.current_player, p1)

    def test_skip_all_matches_regular_skip_in_two_player(self):
        game, p1 = self._game_with_players(2)
        p2 = next(p for p in game.players if p is not p1)

        game.current_player = p1
        game.last_card = c.Card("r", "5")
        play_card(game, c.Card("r", "skip"))
        after_skip = game.current_player

        game.current_player = p1
        game.last_card = c.Card("r", "5")
        self._play_skip_all_and_choose_red(game, p1)
        after_skip_all = game.current_player

        self.assertIs(after_skip, p1)
        self.assertIs(after_skip_all, p1)


if __name__ == "__main__":
    unittest.main()
