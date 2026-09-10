# -*- coding: utf-8 -*-
"""Inline result id parsing (mode + ui-state suffix)."""

import unittest

from handlers.inline import _inline_result_id, _parse_inline_result_id


class _Game:
    choosing_color = False
    mercy_pending_swap = False
    mercy_pending_roulette = None
    mercy_extra_discard_pending = False
    mode = "no_mercy"

    class chat:
        id = -100123


class _Player:
    anti_cheat = 7


class InlineResultIdTests(unittest.TestCase):
    def test_five_part_suffix_roundtrip(self):
        game = _Game()
        player = _Player()
        raw = _inline_result_id("h3", player, game)
        stem, anti, chat_id, mode = _parse_inline_result_id(raw)
        self.assertEqual(stem, "h3")
        self.assertEqual(anti, 7)
        self.assertEqual(chat_id, -100123)
        self.assertEqual(mode, "no_mercy")

    def test_legacy_three_part_suffix(self):
        stem, anti, chat_id, mode = _parse_inline_result_id("r_5:3:-99")
        self.assertEqual(stem, "r_5")
        self.assertEqual(anti, 3)
        self.assertEqual(chat_id, -99)
        self.assertIsNone(mode)

    def test_mode_in_suffix_differs_by_game(self):
        game = _Game()
        player = _Player()
        plain = _inline_result_id("draw", player, game)
        game.mode = "classic"
        classic = _inline_result_id("draw", player, game)
        self.assertNotEqual(plain, classic)


if __name__ == "__main__":
    unittest.main()
