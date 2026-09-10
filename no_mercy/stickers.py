"""
NO MERCY sticker resolution — uses mercy_assets only; never classic STICKERS.
"""
from __future__ import annotations

from deck.assets.mercy import CARDS_MERCY

from no_mercy.constants import MODE


def is_no_mercy_game(game) -> bool:
    return getattr(game, "mode", None) == MODE


def sticker_key(card_id: str, *, playable: bool) -> str:
    """
    Map universal card id to mercy_assets dict key.
    Colored cards already match (b_draw2). Wild specials use w_* keys.
    """
    return card_id


def get_mercy_sticker(card_id: str, *, playable: bool) -> str:
    variant = "normal" if playable else "not_playable"
    pack = CARDS_MERCY.get(variant, {})
    key = sticker_key(card_id, playable=playable)
    if playable:
        return pack.get(key) or ""
    # Grey keys: prefix n + strip color letter for wild, or n + color for colored
    grey = _grey_key(key)
    return pack.get(grey) or pack.get(key) or ""


def _grey_key(playable_key: str) -> str:
    if playable_key.startswith("w_"):
        return "n" + playable_key  # w_draw4 -> nw_draw4
    if len(playable_key) >= 2 and playable_key[1] == "_":
        return "n" + playable_key  # b_5 -> nb_5
    return "n" + playable_key


def sticker_for_card(card, game=None, *, playable: bool = True) -> str:
    card_id = str(card)
    return get_mercy_sticker(card_id, playable=playable)
