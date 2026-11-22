#!/usr/bin/env python3
"""Build Android-drawable Noto 3D emoji fonts from Google's release.

Google publishes Noto's 3D emoji (googlefonts/noto-emoji, 3D/fonts) only as
`sbix` fonts, Apple's bitmap format, which Android does not draw. The pictures
are fine; the container is the problem. So this takes the 2D Noto Color Emoji
build of the same release, whose CBDT bitmap table Android draws on every
version, and swaps each glyph's picture for the 3D one of the same glyph name.
The 2D font keeps its own character map and sequence rules, so coverage is
exactly Noto Color Emoji's. A glyph the 3D set lacks keeps its 2D picture.

Each 3D picture (128 x 128 at 109 ppem) is centred on the 2D glyph's
136 x 128 canvas so the strike metrics stay valid.

    python3 tools/build_noto_3d.py Noto-3D-128.ttf fonts/noto-color-emoji.ttf fonts/noto-emoji-3d.ttf

Each picture is stored as a 256-colour palette PNG with dithering: 18 MB
against 66 MB lossless, with no difference visible at keyboard size. The
result is OFL-1.1, like the fonts it is built from. Needs fontTools and
Pillow.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image


def pictures_3d(path: str) -> dict[str, bytes]:
    """Glyph name -> PNG of the largest sbix strike."""
    font = TTFont(path)
    strikes = font["sbix"].strikes
    strike = strikes[max(strikes)]
    return {name: g.imageData for name, g in strike.glyphs.items() if g.imageData and g.graphicType == "png "}


def fitted(png: bytes, width: int, height: int, palette: bool) -> bytes:
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    if image.size != (width, height):
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.paste(image, ((width - image.width) // 2, (height - image.height) // 2))
        image = canvas
    if palette:
        # Fast octree keeps alpha; dithering hides the banding on the gradients.
        image = image.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def build(sbix_font: str, noto_2d: str, target: Path, palette: bool) -> tuple[int, int]:
    pictures = pictures_3d(sbix_font)
    font = TTFont(noto_2d)
    swapped = 0
    for strike in font["CBDT"].strikeData:
        for name, glyph in strike.items():
            png = pictures.get(name)
            if png is None:
                continue
            metrics = glyph.metrics  # decompiles the glyph before its data is replaced
            glyph.imageData = fitted(png, metrics.width, metrics.height, palette)
            swapped += 1
    font["name"].setName("Noto Emoji 3D", 1, 3, 1, 0x409)
    font["name"].setName("Noto Emoji 3D", 4, 3, 1, 0x409)
    font["name"].setName("NotoEmoji3D", 6, 3, 1, 0x409)
    font.save(target)
    return swapped, target.stat().st_size


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        sys.exit(__doc__)
    sbix_font, noto_2d, target = argv[1:]
    swapped, size = build(sbix_font, noto_2d, Path(target), palette=True)
    print(f"{Path(target).name}: {swapped} glyphs, {size:,} bytes ({size / 1048576:.1f} MiB)", file=sys.stderr)
    # App versions up to 45 take emoji fonts of up to 64 MiB.
    if size > 64 * 1024 * 1024:
        sys.exit(f"{target} is over 64 MiB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
