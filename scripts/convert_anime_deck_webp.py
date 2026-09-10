# -*- coding: utf-8 -*-
"""
Script to resize/convert all Anime Deck cards to 342x512 WebP files.
Works with both .png and .webp source files.
"""

import os
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
ANIME_DECK_DIR = BASE_DIR / "images" / "anime_deck"

# Check available source folders
PLAYABLE_SRC = (
    (ANIME_DECK_DIR / "playable")
    if (ANIME_DECK_DIR / "playable").exists()
    else (ANIME_DECK_DIR / "png")
)
NOT_PLAYABLE_SRC = (
    (ANIME_DECK_DIR / "not_playable")
    if (ANIME_DECK_DIR / "not_playable").exists()
    else (ANIME_DECK_DIR / "png_not_playable")
)

WEBP_PLAYABLE_DIR = ANIME_DECK_DIR / "webp" / "playable"
WEBP_NOT_PLAYABLE_DIR = ANIME_DECK_DIR / "webp" / "not_playable"

TARGET_SIZE = (342, 512)


def convert_folder(src_dir: Path, dst_dir: Path):
    if not src_dir.exists():
        print(f"Source folder '{src_dir}' does not exist.")
        return

    dst_dir.mkdir(parents=True, exist_ok=True)
    card_files = sorted(
        list(src_dir.glob("*.webp")) + list(src_dir.glob("*.png"))
    )
    # Deduplicate stems
    seen_stems = set()
    filtered_files = []
    for f in card_files:
        if f.stem not in seen_stems and f.parent != dst_dir:
            seen_stems.add(f.stem)
            filtered_files.append(f)

    print(f"Found {len(filtered_files)} card files in '{src_dir.name}'...")

    converted_count = 0
    for card_path in filtered_files:
        webp_name = f"{card_path.stem}.webp"
        webp_path = dst_dir / webp_name
        try:
            with Image.open(card_path) as img:
                resized_img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
                resized_img.save(webp_path, "WEBP", quality=90, method=6)
                converted_count += 1
                print(f"  [+] Converted: {card_path.name} -> {webp_name} (342x512)")
        except Exception as e:
            print(f"  [-] Failed converting {card_path.name}: {e}")

    print(f"Successfully converted {converted_count}/{len(filtered_files)} cards in '{dst_dir.relative_to(BASE_DIR)}'.")


def main():
    print("Starting Anime Deck Card Resizing to 342x512 WebP...")
    print(f"Base Directory: {ANIME_DECK_DIR}")

    print("\n1. Converting Playable Cards...")
    convert_folder(PLAYABLE_SRC, WEBP_PLAYABLE_DIR)

    print("\n2. Converting Non-Playable Cards...")
    convert_folder(NOT_PLAYABLE_SRC, WEBP_NOT_PLAYABLE_DIR)

    print("\nAll card conversions completed successfully!")


if __name__ == "__main__":
    main()
