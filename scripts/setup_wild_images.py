# -*- coding: utf-8 -*-
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "images"

src_playble = BASE / "Rainbow" / "Playble" / "draw_eight.webp"
dst_playble = BASE / "classic" / "playble" / "draw_eight.webp"

src_non_playble = BASE / "Rainbow" / "Non_playble" / "draw_eight.webp"
dst_non_playble = BASE / "classic" / "non_playble" / "draw_eight.webp"

if src_playble.exists():
    shutil.copy(src_playble, dst_playble)
    print(f"Copied {src_playble} -> {dst_playble}")

if src_non_playble.exists():
    shutil.copy(src_non_playble, dst_non_playble)
    print(f"Copied {src_non_playble} -> {dst_non_playble}")
