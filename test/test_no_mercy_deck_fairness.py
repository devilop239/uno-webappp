"""NO MERCY deck — equal probability per card type."""
import unittest
from collections import Counter

from deck import Deck

from no_mercy.constants import BASE_DECK_SIZE, MERCY_WILD_SPECIALS
from no_mercy.deck_fill import (
    deck_multiplier_for_players,
    expected_mercy_card_keys,
    fill_no_mercy_deck,
    mercy_card_key,
    verify_uniform_distribution,
)


class NoMercyDeckFairnessTests(unittest.TestCase):
    def test_expected_63_unique_types(self):
        keys = expected_mercy_card_keys()
        self.assertEqual(len(keys), BASE_DECK_SIZE)
        self.assertEqual(len(keys), 56 + len(MERCY_WILD_SPECIALS))

    def test_single_set_uniform(self):
        deck = Deck()
        deck._fill_no_mercy_(1)
        verify_uniform_distribution(deck.cards, multiplier=1)
        counts = Counter(mercy_card_key(c) for c in deck.cards)
        self.assertTrue(all(n == 1 for n in counts.values()))

    def test_scaled_set_uniform(self):
        for mult in (1, 2, 4, 5):
            deck = Deck()
            fill_no_mercy_deck(deck, multiplier=mult)
            verify_uniform_distribution(deck.cards, multiplier=mult)
            self.assertEqual(len(deck.cards), mult * BASE_DECK_SIZE)

    def test_draw_simulation_near_uniform(self):
        """After shuffle, each type should appear ~equally often in first N draws."""
        deck = Deck()
        deck._fill_no_mercy_(1)
        draws = 630  # 10 full deck passes
        seen = Counter()
        for _ in range(draws):
            card = deck.draw()
            seen[mercy_card_key(card)] += 1
            deck.dismiss(card)
            if not deck.cards:
                deck.cards.extend(deck.graveyard)
                deck.graveyard.clear()
                deck.shuffle()
        expected = draws / BASE_DECK_SIZE
        for key in expected_mercy_card_keys():
            # Allow 15% deviation for randomness
            self.assertGreaterEqual(seen[key], int(expected * 0.85))
            self.assertLessEqual(seen[key], int(expected * 1.15) + 1)

    def test_multiplier_matches_player_count_formula(self):
        mult = deck_multiplier_for_players(12)
        deck = Deck()
        fill_no_mercy_deck(deck, multiplier=mult)
        counts = Counter(mercy_card_key(c) for c in deck.cards)
        self.assertEqual(len(counts), BASE_DECK_SIZE)
        self.assertTrue(all(n == mult for n in counts.values()))


if __name__ == "__main__":
    unittest.main()
