"""
Build the NO MERCY deck — scales with player count (repeats the 63-card set).

Each of the 63 unique cards appears exactly ``multiplier`` times in the deck
before shuffle, so every card type has equal draw probability.
"""
from __future__ import annotations

import math
from collections import Counter
from random import shuffle

import deck.card as c
from deck.card import Card

from no_mercy.constants import (
    BASE_DECK_SIZE,
    FIXED_HAND_SIZE,
    GAMEPLAY_BUFFER_PER_PLAYER,
    MERCY_COLOR_VALUES,
    MERCY_WILD_SPECIALS,
)


def mercy_card_key(card) -> str:
    """Stable id for counting (matches Card.__str__)."""
    return str(card)


def expected_mercy_card_keys() -> frozenset[str]:
    """All 63 unique NO MERCY card ids (one per type in a single set)."""
    keys = set()
    for color in c.COLORS:
        for value in MERCY_COLOR_VALUES:
            keys.add("%s_%s" % (color, value))
    keys.update(MERCY_WILD_SPECIALS)
    return frozenset(keys)


def verify_uniform_distribution(cards: list, *, multiplier: int = 1) -> None:
    """
    Raise ValueError if any of the 63 card types is missing or over/under-represented.
    """
    mult = max(1, int(multiplier or 1))
    expected = expected_mercy_card_keys()
    counts = Counter(mercy_card_key(card) for card in cards)
    if len(counts) != len(expected):
        missing = expected - set(counts)
        extra = set(counts) - expected
        raise ValueError(
            "NO MERCY deck has %d types, expected %d (missing=%s extra=%s)"
            % (len(counts), len(expected), sorted(missing)[:5], sorted(extra)[:5])
        )
    for key in expected:
        if counts[key] != mult:
            raise ValueError(
                "NO MERCY card %s count=%d, expected %d"
                % (key, counts[key], mult)
            )


def deck_multiplier_for_players(
    player_count: int,
    *,
    hand_size: int = FIXED_HAND_SIZE,
) -> int:
    """
    How many full 63-card sets to shuffle together.

    Same idea as classic modes: opening hands + buffer for draws/stacks/elimination.
    """
    n = max(1, int(player_count or 1))
    hs = max(1, int(hand_size or FIXED_HAND_SIZE))
    total_needed = (hs * n) + (GAMEPLAY_BUFFER_PER_PLAYER * n)
    return max(1, math.ceil(total_needed / BASE_DECK_SIZE))


def estimated_deck_size(player_count: int, *, hand_size: int = FIXED_HAND_SIZE) -> int:
    return deck_multiplier_for_players(player_count, hand_size=hand_size) * BASE_DECK_SIZE


def fill_no_mercy_deck(deck, *, multiplier: int = 1) -> None:
    """
    56 colored (14 × 4) + 7 wild = 63 cards per set.
    multiplier repeats the full set (e.g. 12 players → ~4–5 sets).
    """
    mult = max(1, int(multiplier or 1))
    deck.cards.clear()
    for _ in range(mult):
        for color in c.COLORS:
            for value in MERCY_COLOR_VALUES:
                deck.cards.append(Card(color, value))
        for special in MERCY_WILD_SPECIALS:
            deck.cards.append(Card(None, None, special=special))
    verify_uniform_distribution(deck.cards, multiplier=mult)
    shuffle(deck.cards)
