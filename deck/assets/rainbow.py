# -*- coding: utf-8 -*-
"""Rainbow 6-color expansion WebP card image assets."""

_RAINBOW_CARDS = [
    # Blue
    "b_0", "b_1", "b_2", "b_3", "b_4", "b_5", "b_6", "b_draw", "b_reverse", "b_skip",
    # Green
    "g_0", "g_1", "g_2", "g_3", "g_4", "g_5", "g_6", "g_draw", "g_reverse", "g_skip",
    # Red
    "r_0", "r_1", "r_2", "r_3", "r_4", "r_5", "r_6", "r_draw", "r_reverse", "r_skip",
    # Yellow
    "y_0", "y_1", "y_2", "y_3", "y_4", "y_5", "y_6", "y_draw", "y_reverse", "y_skip",
    # Purple
    "p_0", "p_1", "p_2", "p_3", "p_4", "p_5", "p_6", "p_7", "p_8", "p_9", "p_draw", "p_reverse", "p_skip",
    # Orange
    "o_0", "o_1", "o_2", "o_3", "o_4", "o_5", "o_6", "o_7", "o_8", "o_9", "o_draw", "o_reverse", "o_skip",
    # Wilds & Power cards
    "draw_four", "draw_eight", "rainbow_wild", "rainbow_monster", "rainbow_lightning"
]

CARDS_RAINBOW = {
    "normal": {k: f"/images/Rainbow/Playble/{k}.webp" for k in _RAINBOW_CARDS},
    "not_playable": {k: f"/images/Rainbow/Non_playble/{k}.webp" for k in _RAINBOW_CARDS},
}

RAINBOW_STICKERS = CARDS_RAINBOW["normal"]
