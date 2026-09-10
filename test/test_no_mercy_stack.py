"""NO MERCY draw-stack rules."""
import unittest

import card as c
from game import Game
from player import Player

from no_mercy.constants import DRAW2, W_DRAW4, W_DRAW6, W_DRAW10
from no_mercy.effects import choose_color, play_card
from no_mercy.playability import is_card_playable
from no_mercy.stack import (
    can_stack_with,
    clear_active_stack,
    should_offer_draw,
)


class FakeUser:
    def __init__(self, uid):
        self.id = uid
        self.first_name = "P%d" % uid
        self.username = None
        self.is_bot = False


class FakeChat:
    id = 99
    title = "test"


class NoMercyStackTests(unittest.TestCase):
    def _game(self, n=3):
        game = Game(FakeChat())
        game.set_mode("no_mercy")
        from no_mercy import configure_game_start

        configure_game_start(game)
        players = [Player(game, FakeUser(i + 1)) for i in range(n)]
        game.last_card = c.Card("r", "5")
        return game, players[0], players[1]

    def test_should_offer_draw_during_active_stack_with_stackable_card(self):
        game, p1, _ = self._game()
        game.draw_counter = 4
        game.last_card = c.Card("r", "draw2")
        p1.cards = [c.Card("r", "draw2"), c.Card("g", "3")]
        self.assertTrue(is_card_playable(p1, p1.cards[0]))
        self.assertTrue(should_offer_draw(p1))

    def test_stack_chain_increments_draw_counter(self):
        game, p1, p2 = self._game()
        game.current_player = p1
        play_card(game, c.Card("r", DRAW2))
        self.assertEqual(game.draw_counter, 2)
        self.assertIs(game.current_player, p2)

        game.current_player = p2
        play_card(game, c.Card("r", DRAW2))
        self.assertEqual(game.draw_counter, 4)
        self.assertEqual(game.mercy_stack_last, DRAW2)

    def test_wild_draw6_stacks_and_requires_color(self):
        game, p1, p2 = self._game()
        p3 = next(p for p in game.players if p not in (p1, p2))
        game.current_player = p1
        game.draw_counter = 4
        game.last_card = c.Card("r", DRAW2)
        game.mercy_stack_last = DRAW2

        game.current_player = p2
        play_card(game, c.Card(None, None, special=W_DRAW6))
        self.assertEqual(game.draw_counter, 10)
        self.assertTrue(game.choosing_color)
        self.assertIs(game.current_player, p2)

        choose_color(game, "b")
        self.assertEqual(game.last_card.color, "b")
        self.assertIs(game.current_player, p3)
        self.assertEqual(game.draw_counter, 10)
        self.assertEqual(game.mercy_stack_last, W_DRAW6)

    def test_clear_active_stack_after_penalty(self):
        game, p1, _ = self._game()
        game.draw_counter = 6
        game.mercy_stack_last = W_DRAW4
        game.mercy_chain_bounced = True
        clear_active_stack(game)
        self.assertIsNone(game.mercy_stack_last)
        self.assertFalse(game.mercy_chain_bounced)

    def test_draw2_stacks_on_wild_draw_without_color_match(self):
        last = c.Card(None, None, special=W_DRAW4)
        last.color = "r"
        self.assertTrue(
            can_stack_with(c.Card("g", DRAW2), last, last_was_draw4_reverse=False)
        )

    def test_all_draw_penalties_stack_on_each_other(self):
        """+2, +4, +6, +10 must stack on any active stack top."""
        tops = [
            c.Card("r", DRAW2),
            c.Card(None, None, special=W_DRAW4),
            c.Card(None, None, special=W_DRAW6),
            c.Card(None, None, special=W_DRAW10),
        ]
        for top in tops[1:]:
            top.color = "b"
        defenses = [
            c.Card("g", DRAW2),
            c.Card(None, None, special=W_DRAW4),
            c.Card(None, None, special=W_DRAW6),
            c.Card(None, None, special=W_DRAW10),
        ]
        for top in tops:
            for card in defenses:
                self.assertTrue(
                    can_stack_with(card, top, last_was_draw4_reverse=False),
                    "%s on %s" % (card, top),
                )

    def test_draw10_on_draw6_increments_stack(self):
        game, p1, p2 = self._game()
        game.draw_counter = 6
        game.last_card = c.Card(None, None, special=W_DRAW6)
        game.last_card.color = "y"
        game.mercy_stack_last = W_DRAW6
        game.current_player = p2
        play_card(game, c.Card(None, None, special=W_DRAW10))
        self.assertEqual(game.draw_counter, 16)


if __name__ == "__main__":
    unittest.main()
