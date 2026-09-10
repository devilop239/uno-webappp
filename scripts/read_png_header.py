import struct
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
png_file = BASE_DIR / "images" / "classic" / "png" / "r_0.png"
webp_file = BASE_DIR / "images" / "classic" / "webp" / "r_0.webp"
out_file = BASE_DIR / "scripts" / "dim_result.txt"

info = []

if png_file.exists():
    with open(png_file, "rb") as f:
        data = f.read(24)
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            width, height = struct.unpack(">II", data[16:24])
            info.append(f"Classic PNG (r_0.png): {width} x {height} px")

if webp_file.exists():
    with open(webp_file, "rb") as f:
        data = f.read(30)
        # VP8L lossy/lossless WebP header check
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            if b"VP8L" in data:
                b1 = data[21]
                b2 = data[22]
                b3 = data[23]
                b4 = data[24]
                width = 1 + (((b2 & 0x3F) << 8) | b1)
                height = 1 + (((b4 & 0x0F) << 10) | (b3 << 2) | ((b2 & 0xC0) >> 6))
                info.append(f"Classic WebP (r_0.webp): {width} x {height} px")
            else:
                info.append("Classic WebP file exists")

with open(out_file, "w") as f:
    f.write("\n".join(info))
