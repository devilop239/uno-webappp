# -*- coding: utf-8 -*-
"""Rainbow 6-color game mode definitions."""

RAINBOW_MODE_SPEC = {
    "id": "rainbow",
    "name": "Rainbow",
    "description": "6-color expansion (adds Purple & Orange) with Power Cards (+8, Lightning, Monster).",
    "colors": ["r", "b", "g", "y", "p", "o"],
    "power_cards": ["draw_four", "draw_eight", "rainbow_wild", "rainbow_monster", "rainbow_lightning"],
    "turn_time": 30,
    "supports_stacking": True,
    "supports_bluff": True,
}
