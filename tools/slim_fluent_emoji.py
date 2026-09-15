#!/usr/bin/env python3
"""Rebuild fonts/fluent-emoji.ttf under the app's 32 MiB emoji-font cap.

The upstream build (tetunori/fluent-emoji-webfont, FluentEmojiColor.ttf)
ships three colour representations of the same glyphs: an SVG table
(41 MB, which Android never renders), CBDT/CBLC bitmaps (39 MB, what every
Android version draws) and COLRv1 outlines (8 MB, Android 13+ only). Since
the keyboard runs on Android 7.0+, the bitmaps are the one set that works
everywhere, so this keeps CBDT/CBLC alone and re-encodes each embedded PNG
losslessly (same pixels, better zlib), which lands the file at ~29 MiB.

    python3 tools/slim_fluent_emoji.py path/to/FluentEmojiColor.ttf
    python3 tools/build_index.py
    python3 tools/validate.py

Needs fontTools and Pillow.
"""
import io
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "fonts" / "fluent-emoji.ttf"
DROP = ("SVG ", "COLR", "CPAL")


def main(src: str) -> None:
    font = TTFont(src)
    for tag in DROP:
        if tag in font:
            del font[tag]
    strike = font["CBDT"].strikeData[0]
    saved = 0
    for glyph in strike.values():
        data = getattr(glyph, "imageData", None)
        if not data:
            continue
        image = Image.open(io.BytesIO(data))
        out = io.BytesIO()
        image.save(out, "PNG", optimize=True)
        packed = out.getvalue()
        if len(packed) < len(data):
            glyph.imageData = packed
            saved += len(data) - len(packed)
    font.save(TARGET)
    size = TARGET.stat().st_size
    cap = 32 * 1024 * 1024
    print(f"{TARGET.name}: {size:,} bytes ({size / 1048576:.1f} MiB), {saved / 1e6:.1f} MB saved by recompression")
    if size > cap:
        sys.exit(f"still over the {cap:,}-byte cap")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
