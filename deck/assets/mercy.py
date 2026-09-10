# -*- coding: utf-8 -*-
"""No Mercy expansion WebP card image assets."""

_MERCY_PLAYABLE_KEYS = [
    'b_0', 'b_1', 'b_2', 'b_3', 'b_4', 'b_5', 'b_6', 'b_7', 'b_8', 'b_9',
    'b_discard_all', 'b_draw2', 'b_reverse', 'b_skip',
    'g_0', 'g_1', 'g_2', 'g_3', 'g_4', 'g_5', 'g_6', 'g_7', 'g_8', 'g_9',
    'g_discard_all', 'g_draw2', 'g_reverse', 'g_skip',
    'r_0', 'r_1', 'r_2', 'r_3', 'r_4', 'r_5', 'r_6', 'r_7', 'r_8', 'r_9',
    'r_discard_all', 'r_draw2', 'r_reverse', 'r_skip',
    'y_0', 'y_1', 'y_2', 'y_3', 'y_4', 'y_5', 'y_6', 'y_7', 'y_8', 'y_9',
    'y_discard_all', 'y_draw2', 'y_reverse', 'y_skip',
    'w_draw10', 'w_draw4', 'w_draw4_reverse', 'w_draw6', 'w_roulette', 'w_skip_all', 'w_wild',
]


def _map_mercy_webp(key: str, playable: bool = True) -> str:
    folder = "playble" if playable else "non_playble"
    if key in ("w_draw10", "w_draw6", "w_draw4", "w_draw4_reverse"):
        return f"/images/classic/{folder}/draw_four.webp"
    if key in ("w_roulette", "w_skip_all", "w_wild"):
        return f"/images/classic/{folder}/colorchooser.webp"
    if "discard" in key or "draw2" in key:
        clean = key.replace("_discard_all", "_draw").replace("_draw2", "_draw")
        return f"/images/classic/{folder}/{clean}.webp"
    stem = key[1:] if key.startswith("n") and len(key) > 2 else key
    return f"/images/classic/{folder}/{stem}.webp"


CARDS_MERCY = {
    "normal": {k: _map_mercy_webp(k, playable=True) for k in _MERCY_PLAYABLE_KEYS},
    "not_playable": {k: _map_mercy_webp(k, playable=False) for k in _MERCY_PLAYABLE_KEYS},
}

MERCY_STICKERS = CARDS_MERCY["normal"]
