# -*- coding: utf-8 -*-
"""Anime theme WebP card image assets."""

_ANIME_CARDS = [
    "b_0", "b_1", "b_2", "b_3", "b_4", "b_5", "b_6", "b_7", "b_8", "b_9", "b_draw", "b_reverse", "b_skip",
    "g_0", "g_1", "g_2", "g_3", "g_4", "g_5", "g_6", "g_7", "g_8", "g_9", "g_draw", "g_reverse", "g_skip",
    "r_0", "r_1", "r_2", "r_3", "r_4", "r_5", "r_6", "r_7", "r_8", "r_9", "r_draw", "r_reverse", "r_skip",
    "y_0", "y_1", "y_2", "y_3", "y_4", "y_5", "y_6", "y_7", "y_8", "y_9", "y_draw", "y_reverse", "y_skip",
    "colorchooser", "draw_four", "draw_eight",
]

CARDS_ANIME = {
    "normal": {k: f"/images/anime_deck/playable/{k}.webp" for k in _ANIME_CARDS},
    "not_playable": {k: f"/images/anime_deck/not_playable/{k}.webp" for k in _ANIME_CARDS},
}

ANIME_STICKERS = CARDS_ANIME["normal"]

ANIME_WEBP_CONFIG = {
    "target_resolution": "342x512",
    "format": "webp",
    "playable_path": "images/anime_deck/playable",
    "not_playable_path": "images/anime_deck/not_playable",
}
