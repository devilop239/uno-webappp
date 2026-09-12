# -*- coding: utf-8 -*-
"""
Deck style resolution and visual asset pack manager.
"""

from __future__ import annotations
from deck.assets.anime import CARDS_ANIME
from deck.assets.pokemon import CARDS_POKEMON
from deck.assets.mercy import CARDS_MERCY

DECK_STYLE_NORMAL = "normal"
DECK_STYLE_ANIME = "anime"
DECK_STYLE_POKEMON = "pokemon"
DECK_STYLE_NO_MERCY = "no_mercy"

VALID_DECK_STYLES = frozenset({
    DECK_STYLE_NORMAL,
    DECK_STYLE_ANIME,
    DECK_STYLE_POKEMON,
    DECK_STYLE_NO_MERCY,
})

ALT_DECK_STYLES = frozenset({DECK_STYLE_ANIME, DECK_STYLE_POKEMON, DECK_STYLE_NO_MERCY})

_STYLE_ALIASES = {
    "classic": DECK_STYLE_NORMAL,
    "default": DECK_STYLE_NORMAL,
    "normal": DECK_STYLE_NORMAL,
    "anime": DECK_STYLE_ANIME,
    "pokemon": DECK_STYLE_POKEMON,
    "poke": DECK_STYLE_POKEMON,
    "no_mercy": DECK_STYLE_NO_MERCY,
    "mercy": DECK_STYLE_NO_MERCY,
}

MODES_NORMAL_STICKERS_ONLY = frozenset({"rainbow"})
MODES_FIXED_STICKER_PACK = frozenset({"no_mercy"})

STICKER_PACKS = {
    DECK_STYLE_ANIME: {
        "normal": CARDS_ANIME["normal"],
        "not_playable": CARDS_ANIME["not_playable"],
    },
    DECK_STYLE_POKEMON: {
        "normal": CARDS_POKEMON["normal"],
        "not_playable": CARDS_POKEMON["not_playable"],
    },
    DECK_STYLE_NO_MERCY: {
        "normal": CARDS_MERCY["normal"],
        "not_playable": CARDS_MERCY["not_playable"],
    },
}


def normalize_deck_style(value: str | None) -> str:
    if value is None:
        return DECK_STYLE_NORMAL
    key = str(value).strip().lower()
    if key in VALID_DECK_STYLES:
        return key
    return _STYLE_ALIASES.get(key, DECK_STYLE_NORMAL)


def is_deck_style_allowed_for_mode(style: str | None, mode: str | None) -> bool:
    style = normalize_deck_style(style)
    mode_clean = str(mode or "classic").strip().lower()

    if mode_clean == "no_mercy":
        return style == DECK_STYLE_NO_MERCY or style == DECK_STYLE_NORMAL

    # No Mercy deck style is not allowed in non-No Mercy modes
    if style == DECK_STYLE_NO_MERCY:
        return False

    # Anime deck style is allowed ONLY in classic mode
    if style == DECK_STYLE_ANIME:
        return mode_clean == "classic"

    return True


def resolve_deck_style(game) -> str:
    if game is None:
        return DECK_STYLE_NORMAL
    mode = getattr(game, "mode", "classic")
    if mode == "no_mercy":
        return DECK_STYLE_NO_MERCY
    if mode in MODES_NORMAL_STICKERS_ONLY:
        return DECK_STYLE_NORMAL
    style = normalize_deck_style(getattr(game, "deck_style", DECK_STYLE_NORMAL))
    if not is_deck_style_allowed_for_mode(style, mode):
        return DECK_STYLE_NORMAL
    return style


def deck_style_selectable_for_mode(mode: str | None) -> bool:
    mode_clean = str(mode or "classic").strip().lower()
    if mode_clean in MODES_FIXED_STICKER_PACK or mode_clean in MODES_NORMAL_STICKERS_ONLY:
        return False
    return mode_clean == "classic"


def is_alt_deck_style(style: str) -> bool:
    return normalize_deck_style(style) in ALT_DECK_STYLES


def deck_style_label(style: str) -> str:
    style = normalize_deck_style(style)
    if style == DECK_STYLE_ANIME:
        return "Anime"
    if style == DECK_STYLE_POKEMON:
        return "Pokemon"
    if style == DECK_STYLE_NO_MERCY:
        return "No Mercy"
    return "Normal"


def _default_sticker_pack(*, playable: bool) -> dict[str, str]:
    from deck import card as card_mod
    return card_mod.STICKERS if playable else card_mod.STICKERS_GREY


def get_card_asset(card_id: str, deck_style: str, *, playable: bool = True) -> str:
    style = normalize_deck_style(deck_style)
    default = _default_sticker_pack(playable=playable)

    if style not in STICKER_PACKS:
        return default.get(card_id) or ""

    variant = "normal" if playable else "not_playable"
    pack = STICKER_PACKS[style].get(variant, {})
    return pack.get(card_id) or default.get(card_id) or ""


def sticker_for(card, game=None, *, playable: bool = True) -> str:
    if game is not None and getattr(game, "mode", None) == "no_mercy":
        from no_mercy.stickers import sticker_for_card
        return sticker_for_card(card, game, playable=playable)
    if game is not None and getattr(game, "mode", None) == "rainbow":
        from deck.assets.rainbow import CARDS_RAINBOW
        variant = "normal" if playable else "not_playable"
        return CARDS_RAINBOW[variant].get(str(card)) or f"/images/Rainbow/{'Playble' if playable else 'Non_playble'}/{card}.webp"
    card_id = str(card)
    style = resolve_deck_style(game)
    return get_card_asset(card_id, style, playable=playable)
