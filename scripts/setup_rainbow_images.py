#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to create images/Rainbow directory structure and copy matching Classic card webp assets
into Playble and Non_playble subdirectories for Rainbow Mode.
"""

import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = BASE_DIR / "images"
CLASSIC_PLAYABLE = IMAGES_DIR / "classic" / "playble"
CLASSIC_NON_PLAYABLE = IMAGES_DIR / "classic" / "non_playble"

RAINBOW_DIR = IMAGES_DIR / "Rainbow"
RAINBOW_PLAYABLE = RAINBOW_DIR / "Playble"
RAINBOW_NON_PLAYABLE = RAINBOW_DIR / "Non_playble"

# Rainbow values for Red, Blue, Green, Yellow: 0 to 6, draw, reverse, skip + draw_four
RAINBOW_CLASSIC_CARD_IDS = [
    # Blue
    'b_0', 'b_1', 'b_2', 'b_3', 'b_4', 'b_5', 'b_6', 'b_draw', 'b_reverse', 'b_skip',
    # Green
    'g_0', 'g_1', 'g_2', 'g_3', 'g_4', 'g_5', 'g_6', 'g_draw', 'g_reverse', 'g_skip',
    # Red
    'r_0', 'r_1', 'r_2', 'r_3', 'r_4', 'r_5', 'r_6', 'r_draw', 'r_reverse', 'r_skip',
    # Yellow
    'y_0', 'y_1', 'y_2', 'y_3', 'y_4', 'y_5', 'y_6', 'y_draw', 'y_reverse', 'y_skip',
    # Wilds
    'draw_four'
]

def main():
    RAINBOW_PLAYABLE.mkdir(parents=True, exist_ok=True)
    RAINBOW_NON_PLAYABLE.mkdir(parents=True, exist_ok=True)
    print(f"Created directories: {RAINBOW_PLAYABLE} and {RAINBOW_NON_PLAYABLE}")

    copied_playable = 0
    copied_non_playable = 0

    for card_id in RAINBOW_CLASSIC_CARD_IDS:
        filename = f"{card_id}.webp"
        
        # Copy Playable
        src_p = CLASSIC_PLAYABLE / filename
        dst_p = RAINBOW_PLAYABLE / filename
        if src_p.exists():
            shutil.copy2(src_p, dst_p)
            copied_playable += 1
        else:
            print(f"Warning: {src_p} not found")

        # Copy Non_playable
        src_np = CLASSIC_NON_PLAYABLE / filename
        dst_np = RAINBOW_NON_PLAYABLE / filename
        if src_np.exists():
            shutil.copy2(src_np, dst_np)
            copied_non_playable += 1
        else:
            print(f"Warning: {src_np} not found")

    print(f"✅ Successfully copied {copied_playable} Playble and {copied_non_playable} Non_playble card images to {RAINBOW_DIR}")

if __name__ == "__main__":
    main()
