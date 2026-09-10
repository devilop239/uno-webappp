"""NO MERCY UI / callback configuration (isolated from classic bot)."""
from __future__ import annotations

# Callback prefix — all NO MERCY keyboard data starts with this
CB_PREFIX = "nm"

# Action codes (keep callback_data under 64 bytes)
ACT_DRAW = "d"
ACT_HAND = "h"
ACT_INFO = "i"
ACT_PLAY = "p"
ACT_PAGE = "pg"
ACT_COLOR = "c"
ACT_SWAP = "s"
ACT_ROULETTE = "t"
ACT_BONUS = "b"
ACT_BONUS_SKIP = "bx"
ACT_PASS = "x"

CARDS_PER_PAGE = 6
CARDS_PER_ROW = 2

# Shorthand for suggested naming in docs
CB_DRAW = "nm_draw"
CB_HAND = "nm_hand"
CB_INFO = "nm_info"
CB_PLAY_PREFIX = "nm_play_"
