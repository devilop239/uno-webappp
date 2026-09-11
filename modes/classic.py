# -*- coding: utf-8 -*-
"""Classic and Fast game mode definitions."""

RULE_SUMMARY = {
    "colors": ["r", "b", "g", "y"],
    "deck_size": 108,
    "hand_sizes": [7, 14, 21],
    "supports_stacking": True,
    "supports_7_0_swap": False,
    "supports_jump_in": False,
    "supports_bluff": True,
    "supports_pass_after_draw": True,
}

CLASSIC_MODE_SPEC = {
    "id": "classic",
    "name": "Classic",
    "description": "Standard UNO rules with relaxed turn timer and full grace period.",
    "turn_time": 30,
    "hand_sizes": [7, 14, 21],
    "supports_stacking": True,
    "supports_7_0_swap": False,
    "supports_jump_in": False,
    "supports_bluff": True,
}

FAST_MODE_SPEC = {
    "id": "fast",
    "name": "Fast",
    "description": "Fast-paced UNO mode with 15-second turn timers and automated skipping.",
    "turn_time": 15,
    "hand_sizes": [7, 14, 21],
    "supports_stacking": True,
    "supports_7_0_swap": False,
    "supports_jump_in": False,
    "supports_bluff": True,
}

WILD_MODE_SPEC = {
    "id": "wild",
    "name": "Wild",
    "description": "Expanded UNO mode with extra wild cards and unpredictable turns.",
    "turn_time": 30,
    "hand_sizes": [7, 14, 21],
    "supports_stacking": True,
    "supports_7_0_swap": False,
    "supports_jump_in": False,
    "supports_bluff": True,
}
