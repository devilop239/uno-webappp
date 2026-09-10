"""NO MERCY mode — rules smoke tests."""
import unittest

import card as c
from deck import Deck
from game import Game
from player import Player

from no_mercy.constants import BASE_DECK_SIZE, DRAW2, W_DRAW4_REVERSE
from no_mercy.deck_fill import deck_multiplier_for_players, estimated_deck_size
from no_mercy.playability import is_card_playable
from no_mercy.stack import can_stack_with


class FakeUser:
    def __init__(self, uid):
        self.id = uid
        self.first_name = "P%d" % uid
        self.username = None
        self.is_bot = False


class FakeChat:
    id = 99
    title = "test"


class NoMercyTests(unittest.TestCase):
    def test_deck_has_63_cards_by_default(self):
        deck = Deck()
        deck._fill_no_mercy_(1)
        self.assertEqual(len(deck.cards), BASE_DECK_SIZE)

    def test_deck_scales_for_large_lobbies(self):
        deck = Deck()
        mult = deck_multiplier_for_players(12)
        self.assertGreaterEqual(mult, 4)
        deck._fill_no_mercy_(mult)
        self.assertEqual(len(deck.cards), mult * BASE_DECK_SIZE)
        self.assertGreaterEqual(estimated_deck_size(12), 252)

    def test_from_str_mercy_colored_actions(self):
        self.assertEqual(str(c.from_str("r_draw2")), "r_draw2")
        self.assertEqual(str(c.from_str("b_discard_all")), "b_discard_all")
        self.assertEqual(str(c.from_str("w_draw4_reverse")), "w_draw4_reverse")

    def test_draw2_stacks_on_draw_penalties_not_number_cards(self):
        plus2 = c.Card("g", "draw2")
        self.assertFalse(
            can_stack_with(plus2, c.Card("r", "5"), last_was_draw4_reverse=False)
        )
        self.assertTrue(
            can_stack_with(plus2, c.Card("r", "draw2"), last_was_draw4_reverse=False)
        )
        last_wild = c.Card(None, None, special="w_draw4")
        last_wild.color = "r"
        self.assertTrue(
            can_stack_with(plus2, last_wild, last_was_draw4_reverse=False)
        )

    def test_draw4_reverse_cannot_stack_on_draw4_reverse(self):
        last = c.Card(None, None, special=W_DRAW4_REVERSE)
        rev = c.Card(None, None, special=W_DRAW4_REVERSE)
        self.assertFalse(
            can_stack_with(rev, last, last_was_draw4_reverse=True)
        )

    def test_wild_blocked_during_stack(self):
        chat = FakeChat()
        game = Game(chat)
        game.set_mode("no_mercy")
        from no_mercy import configure_game_start

        configure_game_start(game)
        u1, u2 = FakeUser(1), FakeUser(2)
        p1 = Player(game, u1)
        Player(game, u2)
        game.last_card = c.Card("r", "5")
        game.draw_counter = 4
        wild = c.Card(None, None, special="w_wild")
        self.assertFalse(p1._card_playable(wild))


if __name__ == "__main__":
    unittest.main()
