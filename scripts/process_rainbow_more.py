#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to process cards from images/rainbow_more:
- Maps 001..013 to Purple cards (p_0..p_9, p_draw, p_reverse, p_skip)
- Maps 014..026 to Orange cards (o_0..o_9, o_draw, o_reverse, o_skip)
- Saves/copies them to images/Rainbow/Playble/
- Generates darker/grayscale non-playable versions into images/Rainbow/Non_playble/
"""

import os
import shutil
from pathlib import Path
from PIL import Image, ImageEnhance

BASE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = BASE_DIR / "images"
RAINBOW_MORE_DIR = IMAGES_DIR / "rainbow_more"
PLAYABLE_DIR = IMAGES_DIR / "Rainbow" / "Playble"
NON_PLAYABLE_DIR = IMAGES_DIR / "Rainbow" / "Non_playble"

# Mapping of file numbers (001 to 026) to standard UNO card IDs
FILE_MAPPING = {
    # Purple cards (001 - 013)
    "001": "p_0.webp",
    "002": "p_1.webp",
    "003": "p_2.webp",
    "004": "p_3.webp",
    "005": "p_4.webp",
    "006": "p_5.webp",
    "007": "p_6.webp",
    "008": "p_7.webp",
    "009": "p_8.webp",
    "010": "p_9.webp",
    "011": "p_draw.webp",
    "012": "p_reverse.webp",
    "013": "p_skip.webp",
    # Orange cards (014 - 026)
    "014": "o_0.webp",
    "015": "o_1.webp",
    "016": "o_2.webp",
    "017": "o_3.webp",
    "018": "o_4.webp",
    "019": "o_5.webp",
    "020": "o_6.webp",
    "021": "o_7.webp",
    "022": "o_8.webp",
    "023": "o_9.webp",
    "024": "o_draw.webp",
    "025": "o_reverse.webp",
    "026": "o_skip.webp",
}


def make_non_playable(src_path: Path, dst_path: Path):
    """Generate darker/desaturated non-playable variant of a card image."""
    try:
        with Image.open(src_path) as img:
            img = img.convert("RGBA")
            # Desaturate slightly and darken
            enhancer_color = ImageEnhance.Color(img)
            img_desat = enhancer_color.enhance(0.35)
            enhancer_bright = ImageEnhance.Brightness(img_desat)
            img_dark = enhancer_bright.enhance(0.63)
            img_dark.save(dst_path, "WEBP", quality=90)
    except Exception as e:
        print(f"Error creating non-playable variant for {src_path.name}: {e}")
        shutil.copy2(src_path, dst_path)


def main():
    PLAYABLE_DIR.mkdir(parents=True, exist_ok=True)
    NON_PLAYABLE_DIR.mkdir(parents=True, exist_ok=True)

    if not RAINBOW_MORE_DIR.exists():
        print(f"Directory {RAINBOW_MORE_DIR} does not exist.")
        return

    processed_count = 0

    for num_str, target_filename in FILE_MAPPING.items():
        src_name = f"UNOBotGamesArenaV_{num_str}_768x1152.webp"
        src_file = RAINBOW_MORE_DIR / src_name

        if not src_file.exists():
            print(f"File not found: {src_file}")
            continue

        playable_dst = PLAYABLE_DIR / target_filename
        non_playable_dst = NON_PLAYABLE_DIR / target_filename

        # Copy to Playble
        shutil.copy2(src_file, playable_dst)

        # Generate Non_playble variant
        make_non_playable(src_file, non_playable_dst)

        processed_count += 1

    print(f"✅ Processed {processed_count} Purple & Orange cards from rainbow_more to {PLAYABLE_DIR} & {NON_PLAYABLE_DIR}")


if __name__ == "__main__":
    main()
