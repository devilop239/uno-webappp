#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Composited WebP Card Sprite Sheet Generator for UNO WebApp.
Generates static 1-to-1 WebP sprite sheets for Playable and Non-Playable cards for all modes:
- Classic (classic_playable.webp, classic_non_playable.webp)
- Anime (anime_deck_playable.webp, anime_deck_non_playable.webp)
- No Mercy (no_mercy_playable.webp, no_mercy_non_playable.webp)
- Rainbow (rainbow_playable.webp, rainbow_non_playable.webp)

Generates and updates front-end/sprites_manifest.json with sheet paths and coordinate mappings.
"""

import os
import json
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = BASE_DIR / "images"
SPRITES_OUT_DIR = IMAGES_DIR / "sprites"
PUBLIC_SPRITES_OUT_DIR = BASE_DIR / "front-end" / "public" / "images" / "sprites"
MANIFEST_OUT = BASE_DIR / "front-end" / "sprites_manifest.json"

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

CLASSIC_CARD_ORDER = [
    "b_0", "b_1", "b_2", "b_3", "b_4", "b_5", "b_6", "b_7", "b_8", "b_9", "b_draw", "b_reverse", "b_skip",
    "g_0", "g_1", "g_2", "g_3", "g_4", "g_5", "g_6", "g_7", "g_8", "g_9", "g_draw", "g_reverse", "g_skip",
    "r_0", "r_1", "r_2", "r_3", "r_4", "r_5", "r_6", "r_7", "r_8", "r_9", "r_draw", "r_reverse", "r_skip",
    "y_0", "y_1", "y_2", "y_3", "y_4", "y_5", "y_6", "y_7", "y_8", "y_9", "y_draw", "y_reverse", "y_skip",
    "colorchooser", "draw_four", "draw_eight",
]

RAINBOW_CARD_ORDER = [
    "b_0", "b_1", "b_2", "b_3", "b_4", "b_5", "b_6", "b_draw", "b_reverse", "b_skip",
    "g_0", "g_1", "g_2", "g_3", "g_4", "g_5", "g_6", "g_draw", "g_reverse", "g_skip",
    "r_0", "r_1", "r_2", "r_3", "r_4", "r_5", "r_6", "r_draw", "r_reverse", "r_skip",
    "y_0", "y_1", "y_2", "y_3", "y_4", "y_5", "y_6", "y_draw", "y_reverse", "y_skip",
    "p_0", "p_1", "p_2", "p_3", "p_4", "p_5", "p_6", "p_7", "p_8", "p_9", "p_draw", "p_reverse", "p_skip",
    "o_0", "o_1", "o_2", "o_3", "o_4", "o_5", "o_6", "o_7", "o_8", "o_9", "o_draw", "o_reverse", "o_skip",
    "draw_four", "draw_eight", "rainbow_wild", "rainbow_monster", "rainbow_lightning",
]

DECKS_TO_PACK = {
    "classic": {
        "playable": IMAGES_DIR / "classic" / "playble",
        "non_playable": IMAGES_DIR / "classic" / "non_playble",
        "custom_map": None,
        "explicit_order": CLASSIC_CARD_ORDER,
    },
    "anime_deck": {
        "playable": IMAGES_DIR / "anime_deck" / "playable",
        "non_playable": IMAGES_DIR / "anime_deck" / "not_playable",
        "custom_map": None,
        "explicit_order": CLASSIC_CARD_ORDER,
    },
    "no_mercy": {
        "playable": IMAGES_DIR / "No_Mercy" / "Playble",
        "non_playable": IMAGES_DIR / "No_Mercy" / "Non_playble",
        "custom_map": _MERCY_FILE_MAP,
        "explicit_order": None,
    },
    "rainbow": {
        "playable": IMAGES_DIR / "Rainbow" / "Playble",
        "non_playable": IMAGES_DIR / "Rainbow" / "Non_playble",
        "custom_map": None,
        "explicit_order": RAINBOW_CARD_ORDER,
    },
}

TILE_WIDTH = 240
TILE_HEIGHT = 360
COLS_PER_ROW = 10


def get_card_items(source_dir: Path, custom_map: dict | None, explicit_order: list | None = None):
    if not source_dir.exists():
        return []
    card_items = []
    if custom_map:
        for card_id, filename in custom_map.items():
            file_path = source_dir / filename
            if file_path.exists():
                card_items.append((card_id, file_path))
    elif explicit_order:
        for card_id in explicit_order:
            for ext in (".webp", ".png"):
                file_path = source_dir / f"{card_id}{ext}"
                if file_path.exists():
                    card_items.append((card_id, file_path))
                    break
    else:
        card_files = sorted([f for f in source_dir.glob("*.webp") if f.is_file() and not f.name.startswith(".")])
        if not card_files:
            card_files = sorted([f for f in source_dir.glob("*.png") if f.is_file() and not f.name.startswith(".")])
        card_items = [(f.stem, f) for f in card_files]
    return card_items


def create_webp_spritesheet(card_items: list, sheet_width: int, sheet_height: int, out_paths: list[Path]):
    canvas = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
    for idx, (card_id, file_path) in enumerate(card_items):
        col = idx % COLS_PER_ROW
        row = idx // COLS_PER_ROW
        x = col * TILE_WIDTH
        y = row * TILE_HEIGHT
        
        try:
            with Image.open(file_path) as card_img:
                card_resized = card_img.convert("RGBA").resize((TILE_WIDTH, TILE_HEIGHT), Image.Resampling.LANCZOS)
                canvas.paste(card_resized, (x, y), card_resized)
        except Exception as e:
            print(f"Error pasting card {card_id} from {file_path}: {e}")

    for out_path in out_paths:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out_path, "WEBP", quality=92, method=6)


def clean_legacy_svgs():
    for d in [SPRITES_OUT_DIR, PUBLIC_SPRITES_OUT_DIR]:
        if d.exists():
            for svg_file in d.glob("*.svg"):
                try:
                    svg_file.unlink()
                    print(f"Removed legacy SVG sprite sheet: {svg_file.name}")
                except Exception as e:
                    print(f"Failed removing {svg_file.name}: {e}")


def main():
    SPRITES_OUT_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_SPRITES_OUT_DIR.mkdir(parents=True, exist_ok=True)
    clean_legacy_svgs()

    manifest_data = {}

    for deck_name, deck_config in DECKS_TO_PACK.items():
        explicit_order = deck_config.get("explicit_order")
        playable_items = get_card_items(deck_config["playable"], deck_config.get("custom_map"), explicit_order=explicit_order)
        non_playable_items = get_card_items(deck_config["non_playable"], deck_config.get("custom_map"), explicit_order=explicit_order)

        if not playable_items:
            print(f"Skipping {deck_name}: no playable items found.")
            continue

        card_count = len(playable_items)
        rows = (card_count + COLS_PER_ROW - 1) // COLS_PER_ROW
        sheet_width = COLS_PER_ROW * TILE_WIDTH
        sheet_height = rows * TILE_HEIGHT

        # 1. Playable WebP Sprite Sheet
        playable_webp_name = f"{deck_name}_playable.webp"
        playable_webp_path = SPRITES_OUT_DIR / playable_webp_name
        public_playable_webp_path = PUBLIC_SPRITES_OUT_DIR / playable_webp_name
        
        create_webp_spritesheet(playable_items, sheet_width, sheet_height, [playable_webp_path, public_playable_webp_path])

        # 2. Non-Playable WebP Sprite Sheet
        non_playable_webp_name = f"{deck_name}_non_playable.webp"
        non_playable_webp_path = SPRITES_OUT_DIR / non_playable_webp_name
        public_non_playable_webp_path = PUBLIC_SPRITES_OUT_DIR / non_playable_webp_name

        items_for_non_playable = non_playable_items if non_playable_items else playable_items
        create_webp_spritesheet(items_for_non_playable, sheet_width, sheet_height, [non_playable_webp_path, public_non_playable_webp_path])

        # Build card coordinate lookup
        cards_coords = {}
        for idx, (card_id, _) in enumerate(playable_items):
            col = idx % COLS_PER_ROW
            row = idx // COLS_PER_ROW
            cards_coords[card_id] = {
                "col": col,
                "row": row,
                "x": col * TILE_WIDTH,
                "y": row * TILE_HEIGHT,
            }

        manifest_data[deck_name] = {
            "deck": deck_name,
            "playable_sheet_path": f"/images/sprites/{playable_webp_name}",
            "non_playable_sheet_path": f"/images/sprites/{non_playable_webp_name}",
            "sheet_path": f"/images/sprites/{playable_webp_name}",
            "cols": COLS_PER_ROW,
            "rows": rows,
            "tile_width": TILE_WIDTH,
            "tile_height": TILE_HEIGHT,
            "sheet_width": sheet_width,
            "sheet_height": sheet_height,
            "cards": cards_coords,
        }

        print(f"Generated WebP sprite sheets for {deck_name}: {playable_webp_name}, {non_playable_webp_name}")

    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # Sync manifest to front-end/public/sprites_manifest.json as well
    public_manifest = BASE_DIR / "front-end" / "public" / "sprites_manifest.json"
    public_manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(public_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print("WebP Sprite sheets build complete!")


if __name__ == "__main__":
    main()
