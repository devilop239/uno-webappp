#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Professional Card Sprite Sheet Generator for UNO WebApp.
Stitches card images into unified grid WebP sprite sheets for ready decks (classic, anime_deck, no_mercy).
Generates front-end/sprites_manifest.json with grid dimensions and card coordinate mappings.
"""

import os
import json
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = BASE_DIR / "images"
SPRITES_OUT_DIR = IMAGES_DIR / "sprites"
MANIFEST_OUT = BASE_DIR / "front-end" / "sprites_manifest.json"

# Import mercy mapping if available
_MERCY_FILE_MAP = {
    'b_0': 'Blue_0.webp', 'b_1': 'Blue_1.webp', 'b_2': 'Blue_2.webp', 'b_3': 'Blue_3.webp',
    'b_4': 'Blue_4.webp', 'b_5': 'Blue_5.webp', 'b_6': 'Blue_6.webp', 'b_7': 'Blue_7_Swap.webp',
    'b_8': 'Blue_8.webp', 'b_9': 'Blue_9.webp', 'b_discard_all': 'Blue_DiscardAll.webp',
    'b_draw2': 'Blue_Draw2.webp', 'b_reverse': 'Blue_Reverse.webp', 'b_skip': 'Blue_Skip.webp',
    'g_0': 'Green_0.webp', 'g_1': 'Green_1.webp', 'g_2': 'Green_2.webp', 'g_3': 'Green_3.webp',
    'g_4': 'Green_4.webp', 'g_5': 'Green_5.webp', 'g_6': 'Green_6.webp', 'g_7': 'Green_7_Swap.webp',
    'g_8': 'Green_8.webp', 'g_9': 'Green_9.webp', 'g_discard_all': 'Green_DiscardAll.webp',
    'g_draw2': 'Green_Draw2.webp', 'g_reverse': 'Green_Reverse.webp', 'g_skip': 'Green_Skip.webp',
    'r_0': 'Red_0.webp', 'r_1': 'Red_1.webp', 'r_2': 'Red_2.webp', 'r_3': 'Red_3.webp',
    'r_4': 'Red_4.webp', 'r_5': 'Red_5.webp', 'r_6': 'Red_6.webp', 'r_7': 'Red_7_Swap.webp',
    'r_8': 'Red_8.webp', 'r_9': 'Red_9.webp', 'r_discard_all': 'Red_DiscardAll.webp',
    'r_draw2': 'Red_Draw2.webp', 'r_reverse': 'Red_Reverse.webp', 'r_skip': 'Red_Skip.webp',
    'y_0': 'Yellow_0.webp', 'y_1': 'Yellow_1.webp', 'y_2': 'Yellow_2.webp', 'y_3': 'Yellow_3.webp',
    'y_4': 'Yellow_4.webp', 'y_5': 'Yellow_5.webp', 'y_6': 'Yellow_6.webp', 'y_7': 'Yellow_7_Swap.webp',
    'y_8': 'Yellow_8.webp', 'y_9': 'Yellow_9.webp', 'y_discard_all': 'Yellow_DiscardAll.webp',
    'y_draw2': 'Yellow_Draw2.webp', 'y_reverse': 'Yellow_Reverse.webp', 'y_skip': 'Yellow_Skip.webp',
    'w_wild': 'Wild.webp', 'w_draw4': 'Wild_Draw4.webp', 'w_draw6': 'Wild_Draw6.webp',
    'w_draw10': 'Wild_Draw10.webp', 'w_draw4_reverse': 'Wild_Draw4_Reverse.webp',
    'w_skip_all': 'Wild Skip All.webp', 'w_roulette': 'Wild_roulette.webp',
}

DECKS_TO_PACK = {
    "classic": {"dir": IMAGES_DIR / "classic" / "playble", "custom_map": None},
    "anime_deck": {"dir": IMAGES_DIR / "anime_deck" / "playable", "custom_map": None},
    "no_mercy": {"dir": IMAGES_DIR / "No_Mercy" / "Playble", "custom_map": _MERCY_FILE_MAP},
    "rainbow": {"dir": IMAGES_DIR / "Rainbow" / "Playble", "custom_map": None},
}

TILE_WIDTH = 200
TILE_HEIGHT = 290
COLS_PER_ROW = 10


def build_spritesheet(deck_name: str, deck_info: dict):
    source_dir = deck_info["dir"]
    custom_map = deck_info.get("custom_map")

    if not source_dir.exists():
        print(f"Skipping {deck_name}: directory {source_dir} does not exist.")
        return None

    card_items = []
    if custom_map:
        for card_id, filename in custom_map.items():
            file_path = source_dir / filename
            if file_path.exists():
                card_items.append((card_id, file_path))
    else:
        card_files = sorted([f for f in source_dir.glob("*.webp") if f.is_file()])
        if not card_files:
            card_files = sorted([f for f in source_dir.glob("*.png") if f.is_file()])
        card_items = [(f.stem, f) for f in card_files]

    if not card_items:
        print(f"No card image files found in {source_dir}")
        return None

    card_count = len(card_items)
    rows = (card_count + COLS_PER_ROW - 1) // COLS_PER_ROW

    sheet_width = COLS_PER_ROW * TILE_WIDTH
    sheet_height = rows * TILE_HEIGHT

    sprite_sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
    card_coords = {}

    for idx, (card_id, card_file) in enumerate(card_items):
        col = idx % COLS_PER_ROW
        row = idx // COLS_PER_ROW
        x = col * TILE_WIDTH
        y = row * TILE_HEIGHT

        try:
            with Image.open(card_file) as card_img:
                card_resized = card_img.convert("RGBA").resize((TILE_WIDTH, TILE_HEIGHT), Image.Resampling.LANCZOS)
                sprite_sheet.paste(card_resized, (x, y))
                card_coords[card_id] = {
                    "col": col,
                    "row": row,
                    "x": x,
                    "y": y
                }
        except Exception as e:
            print(f"Error processing card {card_file}: {e}")

    SPRITES_OUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = SPRITES_OUT_DIR / f"{deck_name}.webp"
    
    sprite_sheet.save(output_path, "WEBP", quality=90, method=6)
    print(f"✅ Generated sprite sheet for '{deck_name}': {output_path} ({sheet_width}x{sheet_height}px, {card_count} cards)")

    return {
        "deck": deck_name,
        "sheet_path": f"/images/sprites/{deck_name}.webp",
        "cols": COLS_PER_ROW,
        "rows": rows,
        "tile_width": TILE_WIDTH,
        "tile_height": TILE_HEIGHT,
        "sheet_width": sheet_width,
        "sheet_height": sheet_height,
        "cards": card_coords
    }


def main():
    print("Building UNO Card Sprite Sheets...")
    manifest = {}
    
    for deck_name, deck_info in DECKS_TO_PACK.items():
        meta = build_spritesheet(deck_name, deck_info)
        if meta:
            manifest[deck_name] = meta

    if manifest:
        with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"✅ Wrote sprite manifest to: {MANIFEST_OUT}")

    sprites_manifest_copy = SPRITES_OUT_DIR / "manifest.json"
    with open(sprites_manifest_copy, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"✅ Wrote sprite manifest copy to: {sprites_manifest_copy}")


if __name__ == "__main__":
    main()
