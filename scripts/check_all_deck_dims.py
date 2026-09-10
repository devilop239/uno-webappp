# -*- coding: utf-8 -*-
"""
Generates a comprehensive report of image pixel dimensions for all deck styles.
"""

from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = BASE_DIR / "images"

report_lines = ["=== UNO DECK IMAGE DIMENSIONS REPORT ===", ""]

targets = [
    ("Classic PNG", IMAGES_DIR / "classic" / "png" / "r_0.png"),
    ("Classic WebP", IMAGES_DIR / "classic" / "webp" / "r_0.webp"),
    ("Classic Colorblind PNG", IMAGES_DIR / "classic_colorblind" / "png" / "r_0.png"),
    ("Classic Colorblind WebP", IMAGES_DIR / "classic_colorblind" / "webp" / "r_0.webp"),
    ("Anime PNG Playable", IMAGES_DIR / "anime_deck" / "png" / "b_0.png"),
    ("Anime PNG Non-Playable", IMAGES_DIR / "anime_deck" / "png_not_playable" / "b_0.png"),
    ("Anime WebP Playable (New)", IMAGES_DIR / "anime_deck" / "webp" / "playable" / "b_0.webp"),
    ("Anime WebP Non-Playable (New)", IMAGES_DIR / "anime_deck" / "webp" / "not_playable" / "b_0.webp"),
]

for label, p in targets:
    if p.exists():
        try:
            with Image.open(p) as img:
                report_lines.append(f"• {label}: {img.size[0]} x {img.size[1]} px (Aspect Ratio: {img.size[0]/img.size[1]:.3f})")
        except Exception as e:
            report_lines.append(f"• {label}: Failed reading ({e})")
    else:
        report_lines.append(f"• {label}: File not found ({p.relative_to(BASE_DIR)})")

out_file = BASE_DIR / "scripts" / "deck_dimensions_report.txt"
with open(out_file, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print("Report generated in scripts/deck_dimensions_report.txt")
