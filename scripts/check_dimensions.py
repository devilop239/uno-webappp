# -*- coding: utf-8 -*-
import os
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
CLASSIC_WEBP = BASE_DIR / "images" / "classic" / "webp" / "r_0.webp"
CLASSIC_PNG = BASE_DIR / "images" / "classic" / "png" / "r_0.png"

for p in [CLASSIC_WEBP, CLASSIC_PNG]:
    if p.exists():
        with Image.open(p) as img:
            print(f"{p.name}: {img.size[0]} x {img.size[1]} px (Format: {img.format})")
    else:
        print(f"{p.name} not found")
