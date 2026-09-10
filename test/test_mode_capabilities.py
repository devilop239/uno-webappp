# -*- coding: utf-8 -*-
"""Mode capability guards."""

import unittest

from modes.capabilities import supports_bluff_challenge, supports_pass_after_draw


class _Game:
    def __init__(self, mode):
        self.mode = mode


class ModeCapabilityTests(unittest.TestCase):
    def test_no_mercy_disables_bluff_and_pass(self):
        game = _Game("no_mercy")
        self.assertFalse(supports_bluff_challenge(game))
        self.assertFalse(supports_pass_after_draw(game))

    def test_classic_keeps_bluff_and_pass(self):
        game = _Game("classic")
        self.assertTrue(supports_bluff_challenge(game))
        self.assertTrue(supports_pass_after_draw(game))


if __name__ == "__main__":
    unittest.main()
