# -*- coding: utf-8 -*-
"""Classic colorblind WebP card image assets."""

_CARDS = [
    "b_0", "b_1", "b_2", "b_3", "b_4", "b_5", "b_6", "b_7", "b_8", "b_9", "b_draw", "b_reverse", "b_skip",
    "g_0", "g_1", "g_2", "g_3", "g_4", "g_5", "g_6", "g_7", "g_8", "g_9", "g_draw", "g_reverse", "g_skip",
    "r_0", "r_1", "r_2", "r_3", "r_4", "r_5", "r_6", "r_7", "r_8", "r_9", "r_draw", "r_reverse", "r_skip",
    "y_0", "y_1", "y_2", "y_3", "y_4", "y_5", "y_6", "y_7", "y_8", "y_9", "y_draw", "y_reverse", "y_skip",
    "colorchooser", "draw_four",
]

CARDS_CLASSIC = {
    "normal": {k: f"/images/classic/playble/{k}.webp" for k in _CARDS},
    "not_playable": {k: f"/images/classic/non_playble/{k}.webp" for k in _CARDS},
}

NORMAL_STICKERS = CARDS_CLASSIC["normal"]
