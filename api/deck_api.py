# -*- coding: utf-8 -*-
"""FastAPI endpoints for UNO visual deck styles and card assets."""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from deck.styles import (
    ALT_DECK_STYLES,
    DECK_STYLE_NORMAL,
    DECK_STYLE_ANIME,
    DECK_STYLE_POKEMON,
    DECK_STYLE_NO_MERCY,
)
import deck.assets.normal as normal_assets
import deck.assets.anime as anime_assets
import deck.assets.pokemon as pokemon_assets
import deck.assets.mercy as mercy_assets

router = APIRouter(prefix="/api/deck", tags=["deck"])


@router.get("/styles", response_model=List[Dict[str, Any]])
async def get_deck_styles():
    """List available visual deck themes."""
    return [
        {
            "id": DECK_STYLE_NORMAL,
            "name": "Classic UNO",
            "description": "Standard vibrant UNO card design.",
            "preview_card": "r_5",
        },
        {
            "id": DECK_STYLE_ANIME,
            "name": "Anime Theme",
            "description": "Japanese anime artwork edition cards.",
            "preview_card": "b_7",
        },
        {
            "id": DECK_STYLE_POKEMON,
            "name": "Pokemon Theme",
            "description": "Pocket Monster character artwork cards.",
            "preview_card": "g_0",
        },
        {
            "id": DECK_STYLE_NO_MERCY,
            "name": "No Mercy Dark Theme",
            "description": "Dark intense high contrast No Mercy style cards.",
            "preview_card": "w_draw10",
        },
    ]


@router.get("/assets/{style_id}", response_model=Dict[str, Any])
async def get_deck_assets(style_id: str):
    """Get sticker asset IDs / image references for a visual style."""
    style_clean = style_id.lower().strip()
    if style_clean == DECK_STYLE_NORMAL:
        return {"style": DECK_STYLE_NORMAL, "assets": normal_assets.NORMAL_STICKERS}
    elif style_clean == DECK_STYLE_ANIME:
        return {
            "style": DECK_STYLE_ANIME,
            "assets": anime_assets.ANIME_STICKERS,
            "webp_cards": anime_assets.ANIME_WEBP_CONFIG,
        }
    elif style_clean == DECK_STYLE_POKEMON:
        return {"style": DECK_STYLE_POKEMON, "assets": pokemon_assets.POKEMON_STICKERS}
    elif style_clean == DECK_STYLE_NO_MERCY:
        return {"style": DECK_STYLE_NO_MERCY, "assets": mercy_assets.MERCY_STICKERS}
    else:
        raise HTTPException(status_code=404, detail=f"Deck style '{style_id}' not found")
