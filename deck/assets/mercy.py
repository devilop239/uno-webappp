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


_MERCY_FILE_MAP = {
    # Blue
    'b_0': 'Blue_0.webp',
    'b_1': 'Blue_1.webp',
    'b_2': 'Blue_2.webp',
    'b_3': 'Blue_3.webp',
    'b_4': 'Blue_4.webp',
    'b_5': 'Blue_5.webp',
    'b_6': 'Blue_6.webp',
    'b_7': 'Blue_7_Swap.webp',
    'b_8': 'Blue_8.webp',
    'b_9': 'Blue_9.webp',
    'b_discard_all': 'Blue_DiscardAll.webp',
    'b_draw2': 'Blue_Draw2.webp',
    'b_reverse': 'Blue_Reverse.webp',
    'b_skip': 'Blue_Skip.webp',
    # Green
    'g_0': 'Green_0.webp',
    'g_1': 'Green_1.webp',
    'g_2': 'Green_2.webp',
    'g_3': 'Green_3.webp',
    'g_4': 'Green_4.webp',
    'g_5': 'Green_5.webp',
    'g_6': 'Green_6.webp',
    'g_7': 'Green_7_Swap.webp',
    'g_8': 'Green_8.webp',
    'g_9': 'Green_9.webp',
    'g_discard_all': 'Green_DiscardAll.webp',
    'g_draw2': 'Green_Draw2.webp',
    'g_reverse': 'Green_Reverse.webp',
    'g_skip': 'Green_Skip.webp',
    # Red
    'r_0': 'Red_0.webp',
    'r_1': 'Red_1.webp',
    'r_2': 'Red_2.webp',
    'r_3': 'Red_3.webp',
    'r_4': 'Red_4.webp',
    'r_5': 'Red_5.webp',
    'r_6': 'Red_6.webp',
    'r_7': 'Red_7_Swap.webp',
    'r_8': 'Red_8.webp',
    'r_9': 'Red_9.webp',
    'r_discard_all': 'Red_DiscardAll.webp',
    'r_draw2': 'Red_Draw2.webp',
    'r_reverse': 'Red_Reverse.webp',
    'r_skip': 'Red_Skip.webp',
    # Yellow
    'y_0': 'Yellow_0.webp',
    'y_1': 'Yellow_1.webp',
    'y_2': 'Yellow_2.webp',
    'y_3': 'Yellow_3.webp',
    'y_4': 'Yellow_4.webp',
    'y_5': 'Yellow_5.webp',
    'y_6': 'Yellow_6.webp',
    'y_7': 'Yellow_7_Swap.webp',
    'y_8': 'Yellow_8.webp',
    'y_9': 'Yellow_9.webp',
    'y_discard_all': 'Yellow_DiscardAll.webp',
    'y_draw2': 'Yellow_Draw2.webp',
    'y_reverse': 'Yellow_Reverse.webp',
    'y_skip': 'Yellow_Skip.webp',
    # Wilds
    'w_wild': 'Wild.webp',
    'w_draw4': 'Wild_Draw4.webp',
    'w_draw6': 'Wild_Draw6.webp',
    'w_draw10': 'Wild_Draw10.webp',
    'w_draw4_reverse': 'Wild_Draw4_Reverse.webp',
    'w_skip_all': 'Wild Skip All.webp',
    'w_roulette': 'Wild_roulette.webp',
}


def _map_mercy_webp(key: str, playable: bool = True) -> str:
    folder = "Playble" if playable else "Non_playble"
    clean_key = key[1:] if key.startswith("n") and len(key) > 2 and not key.startswith("nb_") and not key.startswith("ng_") and not key.startswith("nr_") and not key.startswith("ny_") else key
    if clean_key.startswith("n") and len(clean_key) > 2 and clean_key[1] in ("b", "g", "r", "y", "w"):
        clean_key = clean_key[1:]
    filename = _MERCY_FILE_MAP.get(clean_key) or _MERCY_FILE_MAP.get(key)
    if filename:
        return f"/images/No_Mercy/{folder}/{filename}"
    return f"/images/No_Mercy/{folder}/Wild.webp"


CARDS_MERCY = {
    "normal": {k: _map_mercy_webp(k, playable=True) for k in _MERCY_PLAYABLE_KEYS},
    "not_playable": {k: _map_mercy_webp(k, playable=False) for k in _MERCY_PLAYABLE_KEYS},
}

MERCY_STICKERS = CARDS_MERCY["normal"]

