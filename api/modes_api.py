# -*- coding: utf-8 -*-
"""FastAPI endpoints for UNO game modes and rule specifications."""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from modes import ALL_GAME_MODES
import modes.classic as classic_mode
import modes.rainbow as rainbow_mode
import modes.no_mercy as mercy_mode
import modes.sudden_death as sudden_death_mode
import modes.team as team_mode

router = APIRouter(prefix="/api/modes", tags=["modes"])


@router.get("", response_model=List[Dict[str, Any]])
async def get_all_modes():
    """List all available UNO game modes with summary metadata."""
    modes_list = [
        {
            "id": "classic",
            "name": "Classic UNO",
            "description": "Standard deck with 108 cards, balanced pacing, stacking, and bluff rules.",
            "image": "/images/Modes_Selection/Classic.jpg",
            "capabilities": {
                "supports_bluff_challenge": True,
                "supports_pass_after_draw": True,
                "supports_7_0_swap": False,
                "supports_jump_in": False,
                "special_cards": ["Draw Two", "Skip", "Reverse", "Wild", "Wild Draw Four"],
            },
        },
        {
            "id": "fast",
            "name": "Fast UNO",
            "description": "Short turn timer with auto-skip penalties for high-speed action.",
            "image": "/images/Modes_Selection/Sanic.png",
            "capabilities": {
                "supports_bluff_challenge": True,
                "supports_pass_after_draw": True,
                "turn_timer_seconds": 15,
            },
        },
        {
            "id": "rainbow",
            "name": "Rainbow UNO",
            "description": "Expanded 6-color deck (Red, Blue, Green, Yellow, Purple, Orange) with Draw 8 and Rainbow Monster.",
            "image": "/images/Modes_Selection/rainbow.jpg",
            "capabilities": {
                "colors": ["r", "b", "g", "y", "p", "o"],
                "supports_bluff_challenge": True,
                "supports_pass_after_draw": True,
                "special_cards": ["Draw Eight", "Rainbow Monster"],
            },
        },
        {
            "id": "no_mercy",
            "name": "UNO Show 'Em No Mercy",
            "description": "Ruthless stacking, discard-all, pass-on-7, swap-on-0, and elimination at 25+ cards.",
            "image": "/images/Modes_Selection/Wild.jpg",
            "capabilities": {
                "elimination_threshold": 25,
                "forced_draw_until_playable": True,
                "supports_bluff_challenge": False,
                "supports_pass_after_draw": False,
                "special_cards": ["Wild Draw 6", "Wild Draw 10", "Wild Skip All", "Wild Roulette", "Discard All"],
            },
        },
        {
            "id": "sudden_death",
            "name": "Sudden Death",
            "description": "High stakes match—the game finishes instantly as soon as the first player empties their hand.",
            "image": "/images/Modes_Selection/sudden death.jpg",
            "capabilities": {
                "instant_win": True,
            },
        },
        {
            "id": "team",
            "name": "Team UNO (2v2 / 3v3)",
            "description": "Cooperative team play where teammates share objective card counts to win together.",
            "image": "/images/Modes_Selection/Team.jpg",
            "capabilities": {
                "team_sizes": [2, 3],
                "shared_hand_counters": True,
            },
        },
    ]
    return modes_list


@router.get("/{mode_id}", response_model=Dict[str, Any])
async def get_mode_detail(mode_id: str):
    """Get detailed specification for a single game mode."""
    mode_id_clean = mode_id.lower().strip()
    if mode_id_clean not in ALL_GAME_MODES:
        raise HTTPException(status_code=404, detail=f"Mode '{mode_id}' not found")

    if mode_id_clean in ("classic", "fast"):
        return {
            "mode": mode_id_clean,
            "colors": ["r", "b", "g", "y"],
            "deck_size": 108,
            "rules": classic_mode.RULE_SUMMARY,
        }
    elif mode_id_clean == "rainbow":
        return {
            "mode": "rainbow",
            "colors": rainbow_mode.RAINBOW_COLORS,
            "power_cards": rainbow_mode.RAINBOW_POWER_CARDS,
            "rules": rainbow_mode.RULE_SUMMARY,
        }
    elif mode_id_clean == "no_mercy":
        return {
            "mode": "no_mercy",
            "colors": ["r", "b", "g", "y"],
            "elimination_threshold": mercy_mode.ELIMINATION_THRESHOLD,
            "rules": mercy_mode.RULE_SUMMARY,
        }
    elif mode_id_clean == "sudden_death":
        return {
            "mode": "sudden_death",
            "rules": sudden_death_mode.RULE_SUMMARY,
        }
    elif mode_id_clean == "team":
        return {
            "mode": "team",
            "rules": team_mode.RULE_SUMMARY,
        }
    
    return {"mode": mode_id_clean}
