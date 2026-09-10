"""NO MERCY forced draw (no pass) tests."""
import unittest

import card as c
from game import Game
from player import Player

from no_mercy.forced_draw import draw_until_playable, mercy_draw_turn
from no_mercy.playability import has_any_playable


class FakeUser:
    def __init__(self, uid):
        self.id = uid
        self.first_name = "P%d" % uid
        self.username = None
        self.is_bot = False


class FakeChat:
    id = 99
    title = "test"


class FakeDeck:
    def __init__(self, cards):
        self.cards = list(cards)
        self.graveyard = []

    def draw(self):
        if not self.cards:
            from errors import DeckEmptyError

            raise DeckEmptyError()
        return self.cards.pop(0)


class NoMercyForcedDrawTests(unittest.TestCase):
    def _game(self):
        game = Game(FakeChat())
        game.set_mode("no_mercy")
        from no_mercy import configure_game_start

        configure_game_start(game)
        p1 = Player(game, FakeUser(1))
        Player(game, FakeUser(2))
        game.last_card = c.Card("r", "5")
        return game, p1

    def test_draw_until_playable_stops_on_matching_card(self):
        game, p1 = self._game()
        game.deck = FakeDeck(
            [
                c.Card("b", "3"),
                c.Card("g", "7"),
                c.Card("r", "2"),
            ]
        )
        p1.cards = [c.Card("b", "9")]
        self.assertFalse(has_any_playable(p1))
        n = draw_until_playable(p1)
        self.assertEqual(n, 3)
        self.assertTrue(p1.drew)

    def test_mercy_draw_turn_no_pass_when_voluntary_draw_misses(self):
        game, p1 = self._game()
        game.deck = FakeDeck([c.Card("b", "3"), c.Card("r", "2")])
        p1.cards = [c.Card("r", "5")]
        self.assertTrue(has_any_playable(p1))
        n = mercy_draw_turn(p1)
        self.assertEqual(n, 2)
        self.assertTrue(has_any_playable(p1))

    def test_draw_until_playable_stops_at_elimination_threshold(self):
        game, p1 = self._game()
        game.deck = FakeDeck([c.Card("b", "3")] * 10 + [c.Card("r", "2")])
        p1.cards = [c.Card("b", "9")] * 29
        self.assertFalse(has_any_playable(p1))
        n = draw_until_playable(p1)
        self.assertEqual(len(p1.cards), 30)
        self.assertEqual(n, 1)
        self.assertFalse(has_any_playable(p1))


if __name__ == "__main__":
    unittest.main()
