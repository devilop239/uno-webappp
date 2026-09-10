# -*- coding: utf-8 -*-
"""Pokemon theme WebP card image assets."""

from deck.assets.normal import _CARDS

CARDS_POKEMON = {
    "normal": {k: f"/images/classic/playble/{k}.webp" for k in _CARDS},
    "not_playable": {k: f"/images/classic/non_playble/{k}.webp" for k in _CARDS},
}

POKEMON_STICKERS = CARDS_POKEMON["normal"]
