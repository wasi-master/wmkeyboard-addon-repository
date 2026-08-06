#!/usr/bin/env python3
"""Generate the six showcase themes and their preview images.

Every asset — key textures, sticker decals, particle sprites, the animated
synthwave background, the nebula photo — is drawn here with Pillow, from a
fixed seed, so the whole set regenerates byte-for-byte and nothing in it has
an unclear licence. The output is:

    themes/<id>.wmtheme.json   the theme with every image embedded as base64
    previews/<id>.png          a mock keyboard render for the catalogue card

The six themes together exercise every theme surface the app has: gradients
(linear/radial/sweep), FLOW and HUE_CYCLE animation, a static and an animated
image background, per-class key textures in all three fit modes, single-key
overrides, sticker decals, every press-effect kind including custom images,
per-theme fonts (Google ids) and sounds (built-in style and installed-by-name),
layout overrides, and the popup/tool shape and outline fields.

    python3 tools/generate_showcase_themes.py

Run tools/build_index.py afterwards to refresh sha256/sizeBytes.
"""

from __future__ import annotations

import base64
import io
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
THEMES = ROOT / "themes"
PREVIEWS = ROOT / "previews"

rng = random.Random(20260807)


def c(argb: int) -> int:
    """An 0xAARRGGBB colour as the unsigned decimal the theme JSON uses."""
    return argb & 0xFFFFFFFF


def b64(img: Image.Image, fmt: str = "PNG", **save_args) -> str:
    buf = io.BytesIO()
    img.save(buf, fmt, **save_args)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def b64_gif(frames: list[Image.Image], duration_ms: int) -> str:
    buf = io.BytesIO()
    frames[0].save(
        buf,
        "GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    return base64.b64encode(buf.getvalue()).decode("ascii")


# --- pixel-art helpers ------------------------------------------------------


def upscale(img: Image.Image, factor: int) -> Image.Image:
    return img.resize((img.width * factor, img.height * factor), Image.NEAREST)


def noisy_tile(size: int, base: tuple, jitter: int, speckles: list[tuple] = ()) -> Image.Image:
    """A size x size tile of the base colour with per-pixel brightness noise."""
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            j = rng.randint(-jitter, jitter)
            px[x, y] = tuple(max(0, min(255, ch + j)) for ch in base)
    for colour in speckles:
        for _ in range(size * size // 14):
            px[rng.randrange(size), rng.randrange(size)] = colour
    return img


def dirt_tile() -> Image.Image:
    return upscale(noisy_tile(16, (121, 85, 58), 14, [(96, 66, 44), (150, 108, 74)]), 8)


def stone_tile() -> Image.Image:
    img = noisy_tile(16, (127, 127, 130), 9)
    draw = ImageDraw.Draw(img)
    # A few darker cracks so it reads as stone rather than static.
    for _ in range(4):
        x, y = rng.randrange(16), rng.randrange(16)
        for _ in range(rng.randint(3, 6)):
            draw.point((x % 16, y % 16), fill=(92, 92, 96))
            x += rng.choice([-1, 0, 1])
            y += rng.choice([0, 1])
    return upscale(img, 8)


def grass_tile() -> Image.Image:
    """Dirt with a bright grass crown, the classic block face."""
    img = noisy_tile(16, (121, 85, 58), 14, [(96, 66, 44)])
    px = img.load()
    for y in range(5):
        for x in range(16):
            base = (88, 160, 70) if y < 4 or rng.random() < 0.55 else (121, 85, 58)
            j = rng.randint(-12, 12)
            px[x, y] = tuple(max(0, min(255, ch + j)) for ch in base)
    return upscale(img, 8)


def plank_tile() -> Image.Image:
    img = noisy_tile(16, (168, 132, 84), 8)
    draw = ImageDraw.Draw(img)
    for y in (3, 7, 11, 15):
        draw.line([(0, y), (15, y)], fill=(132, 100, 60))
    return upscale(img, 8)


def pixel_grid_tile(fg: tuple, bg: tuple) -> Image.Image:
    """A CRT-ish grid: dark cell, one-pixel glowing separations."""
    img = Image.new("RGB", (12, 12), bg)
    draw = ImageDraw.Draw(img)
    draw.line([(0, 0), (11, 0)], fill=fg)
    draw.line([(0, 0), (0, 11)], fill=fg)
    return upscale(img, 8)


def paper_tile() -> Image.Image:
    return upscale(noisy_tile(48, (243, 234, 216), 5, [(226, 214, 190)]), 3)


def sprite_from_rows(rows: list[str], palette: dict[str, tuple], scale: int = 8) -> Image.Image:
    """A tiny sprite from an ASCII grid; '.' is transparent."""
    h, w = len(rows), len(rows[0])
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                px[x, y] = palette[ch] + (255,)
    return upscale(img, scale)


PIXEL_STAR = sprite_from_rows(
    [
        "...X...",
        "..XXX..",
        "XXXYXXX",
        ".XXYXX.",
        "..XXX..",
        ".XX.XX.",
        "X.....X",
    ],
    {"X": (255, 224, 64), "Y": (255, 255, 200)},
)

PIXEL_HEART = sprite_from_rows(
    [
        ".XX.XX.",
        "XXXXXXX",
        "XYXXXXX",
        "XXXXXXX",
        ".XXXXX.",
        "..XXX..",
        "...X...",
    ],
    {"X": (255, 64, 129), "Y": (255, 180, 210)},
)

PIXEL_COIN = sprite_from_rows(
    [
        "..XXX..",
        ".XYYYX.",
        "XYYZYYX",
        "XYZZZYX",
        "XYYZYYX",
        ".XYYYX.",
        "..XXX..",
    ],
    {"X": (183, 130, 20), "Y": (255, 200, 60), "Z": (255, 240, 140)},
)


def cube_sprite(top: tuple, side: tuple, front: tuple) -> Image.Image:
    """A little isometric cube, the block-chunk particle."""
    s = 64
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    mid, quarter = s // 2, s // 4
    draw.polygon([(mid, 2), (s - 4, quarter + 2), (mid, mid + 2), (4, quarter + 2)], fill=top)
    draw.polygon([(4, quarter + 2), (mid, mid + 2), (mid, s - 4), (4, 3 * quarter)], fill=front)
    draw.polygon([(s - 4, quarter + 2), (mid, mid + 2), (mid, s - 4), (s - 4, 3 * quarter)], fill=side)
    return img


def petal(colour: tuple, size: int = 72) -> Image.Image:
    """One cherry petal: a soft teardrop ellipse with a notched tip."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([size * 0.2, size * 0.05, size * 0.8, size * 0.95], fill=colour + (235,))
    # The notch at the outer edge that says "cherry" rather than "oval".
    draw.polygon(
        [(size * 0.5, size * 0.0), (size * 0.62, size * 0.16), (size * 0.38, size * 0.16)],
        fill=(0, 0, 0, 0),
    )
    return img.rotate(rng.randint(0, 359), expand=True, resample=Image.BICUBIC)


def petal_branch() -> Image.Image:
    """A blossom branch decal: a dark bough with petal clusters."""
    w, h = 512, 360
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # The bough: a few thick bezier-ish arcs.
    points = [(w, 30), (w * 0.7, 60), (w * 0.45, 120), (w * 0.2, 210)]
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        for t in range(20):
            f = t / 20
            x, y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            r = 10 - i * 2
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(74, 52, 48, 255))
    # Blossom clusters along it.
    for cx, cy in [(w * 0.82, 55), (w * 0.6, 95), (w * 0.42, 130), (w * 0.3, 180), (w * 0.18, 225)]:
        for _ in range(7):
            p = petal(rng.choice([(255, 183, 205), (255, 208, 221), (250, 160, 190)]), 46)
            img.alpha_composite(
                p, (int(cx + rng.randint(-30, 30) - 23), int(cy + rng.randint(-26, 26) - 23))
            )
        draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 240, 245, 255))
    return img


def planet_decal() -> Image.Image:
    """A ringed planet with a soft terminator shadow."""
    s = 320
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = 92
    cx = cy = s // 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(196, 148, 255, 255))
    # Bands.
    for off, col in [(-30, (170, 120, 240)), (5, (220, 180, 255)), (40, (150, 100, 220))]:
        band = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(band).ellipse(
            [cx - r, cy + off - 16, cx + r, cy + off + 16], fill=col + (200,)
        )
        mask = Image.new("L", (s, s), 0)
        ImageDraw.Draw(mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        img.paste(band, (0, 0), Image.composite(band.split()[3], Image.new("L", (s, s), 0), mask))
    # Terminator: darken the right limb.
    shade = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(shade).ellipse([cx - r + 46, cy - r, cx + r + 46, cy + r], fill=(10, 6, 30, 140))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    img.alpha_composite(Image.composite(shade, Image.new("RGBA", (s, s), (0, 0, 0, 0)), mask))
    # The ring, drawn as an ellipse outline rotated by shearing.
    ring = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse([cx - 150, cy - 40, cx + 150, cy + 40], outline=(230, 210, 255, 220), width=10)
    ring = ring.rotate(-24, resample=Image.BICUBIC)
    # In front of the planet only below its centre.
    front = ring.crop((0, cy, s, s))
    img.alpha_composite(ring)
    img.alpha_composite(front, (0, cy))
    return img


def star_sprite() -> Image.Image:
    s = 64
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.line([(s // 2, 4), (s // 2, s - 4)], fill=(255, 255, 230, 255), width=6)
    draw.line([(4, s // 2), (s - 4, s // 2)], fill=(255, 255, 230, 255), width=6)
    draw.ellipse([s // 2 - 8, s // 2 - 8, s // 2 + 8, s // 2 + 8], fill=(255, 255, 255, 255))
    return img.filter(ImageFilter.GaussianBlur(1.5))


def nebula_background() -> Image.Image:
    """A star field over blurred colour clouds."""
    w, h = 1080, 720
    img = Image.new("RGB", (w, h), (8, 6, 24))
    clouds = Image.new("RGB", (w, h), (8, 6, 24))
    draw = ImageDraw.Draw(clouds)
    for colour in [(90, 40, 140), (30, 60, 140), (150, 40, 110), (40, 20, 80)]:
        for _ in range(6):
            x, y = rng.randrange(w), rng.randrange(h)
            r = rng.randint(120, 320)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=colour)
    clouds = clouds.filter(ImageFilter.GaussianBlur(90))
    img = Image.blend(img, clouds, 0.75)
    draw = ImageDraw.Draw(img)
    for _ in range(420):
        x, y = rng.randrange(w), rng.randrange(h)
        brightness = rng.randint(120, 255)
        if rng.random() < 0.06:
            draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(brightness,) * 3)
        else:
            draw.point((x, y), fill=(brightness,) * 3)
    return img


def galaxy_strip() -> Image.Image:
    """A wide star band for the space bar."""
    img = nebula_background().resize((1024, 320))
    return img


def synthwave_gif() -> list[Image.Image]:
    """The driving-into-the-sunset loop: scrolling grid, banded sun, stars."""
    w, h = 480, 270
    horizon = int(h * 0.56)
    frames = []
    steps = 18
    star_field = [(rng.randrange(w), rng.randrange(horizon - 30), rng.randint(90, 220)) for _ in range(70)]
    for f in range(steps):
        img = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(img)
        # Sky: vertical dusk gradient.
        for y in range(horizon):
            t = y / horizon
            draw.line(
                [(0, y), (w, y)],
                fill=(int(26 + 60 * t), int(6 + 10 * t), int(46 + 60 * t)),
            )
        for x, y, b in star_field:
            draw.point((x, y), fill=(b, b, min(255, b + 30)))
        # The sun: banded disc rising over the horizon.
        r = 66
        cx, cy = w // 2, horizon - 12
        for y in range(-r, r):
            if cy + y >= horizon:
                continue
            # Horizontal gaps widen toward the bottom of the disc.
            band = 5 + max(0, y) // 6
            if y > 0 and (y % band) < max(1, band // 3):
                continue
            half = int(math.sqrt(r * r - y * y))
            t = (y + r) / (2 * r)
            draw.line(
                [(cx - half, cy + y), (cx + half, cy + y)],
                fill=(255, int(210 - 160 * t), int(90 - 60 * t)),
            )
        # Ground.
        draw.rectangle([0, horizon, w, h], fill=(16, 4, 34))
        # Vertical grid lines converging on the vanishing point.
        for i in range(-14, 15):
            x_bottom = w // 2 + i * (w // 9)
            draw.line([(w // 2, horizon), (x_bottom, h)], fill=(120, 30, 130))
        # Horizontal lines rolling toward the viewer; f drives the scroll.
        for i in range(1, 12):
            z = i + f / steps
            y = horizon + int((h - horizon) * (1.4 / z) * 0.9)
            if y >= h:
                continue
            glow = max(0, 255 - i * 18)
            draw.line([(0, y), (w, y)], fill=(min(255, 160 + glow // 4), 40, 170))
        frames.append(img.quantize(colors=128, dither=Image.NONE).convert("P"))
    return frames


# --- the six themes ---------------------------------------------------------


def arcade_cabinet() -> dict:
    fx = [PIXEL_STAR, PIXEL_HEART, PIXEL_COIN]
    return {
        "id": "arcade-cabinet",
        "name": "Arcade Cabinet",
        "dark": True,
        "boardBackground": c(0xFF0A0A14),
        "boardGradient": {
            "colors": [c(0x8C24003C), c(0x8C001D3C), c(0x8C3C0032), c(0x8C24003C)],
            "type": "SWEEP",
            "angleDeg": 90.0,
        },
        "keyShape": "SHARP",
        "keyBackground": c(0xFF101024),
        "keyText": c(0xFF00FF9C),
        "modifierKeyBackground": c(0xFF0C0C1C),
        "modifierKeyText": c(0xFF9AFFDA),
        "enterKeyBackground": c(0xFFFF2975),
        "enterKeyText": c(0xFF14000A),
        "keyBorderColor": c(0xFF00E5FF),
        "keyBorderWidthDp": 1.0,
        "accent": c(0xFFFFE046),
        "gestureTrailColor": c(0xFF00FF9C),
        "popupBackground": c(0xFF181834),
        "popupText": c(0xFF00FF9C),
        "popupShape": "SHARP",
        "toolShape": "SHARP",
        "toolbarIcon": c(0xFF00E5FF),
        "toolCircleBackground": c(0xFF10102A),
        "toolBorderColor": c(0xFF00E5FF),
        "toolBorderWidthDp": 1.0,
        "keyTextureScale": "TILE",
        "keyTextureOpacity": 0.55,
        "fontScale": 0.72,
        "animation": "HUE_CYCLE",
        "animationSpeed": 0.6,
        "fontId": "google:Press Start 2P",
        "soundStyle": "CUSTOM",
        "soundCustomId": "Blip",
        "keyEffect": "CUSTOM_IMAGE",
        "keyEffectIntensity": 1.2,
        "keyOverrides": {
            key: {"background": c(0xFF20204A), "text": c(0xFF00E5FF)}
            for key in ("w", "a", "s", "d")
        },
        "assets": {
            "keyTexture": b64(pixel_grid_tile((26, 26, 62), (16, 16, 36))),
            "keyTexturePressed": b64(pixel_grid_tile((0, 229, 255), (24, 24, 52))),
            **{f"effectImage:{i}": b64(img) for i, img in enumerate(fx)},
        },
    }


def sakura_breeze() -> dict:
    return {
        "id": "sakura-breeze",
        "name": "Sakura Breeze",
        "dark": False,
        "boardBackground": c(0x00FFFFFF),
        "boardGradient": {
            "colors": [c(0xFFFFE0EA), c(0xFFFFF4F0), c(0xFFFFE8F4)],
            "type": "LINEAR",
            "angleDeg": 120.0,
        },
        "keyShape": "SCALLOP",
        "keyBackground": c(0xEDFFFFFF),
        "keyText": c(0xFF87505F),
        "modifierKeyBackground": c(0xD8FFE9F0),
        "modifierKeyText": c(0xFFA06A78),
        "enterKeyBackground": c(0xFFED89A3),
        "enterKeyText": c(0xFF4A1420),
        "pressedKeyBackground": c(0xFFFAD2DE),
        "accent": c(0xFFE86A8C),
        "popupBackground": c(0xFFFFF0F4),
        "popupText": c(0xFF87505F),
        "chipBackground": c(0xB8FFFFFF),
        "suggestionText": c(0xFF87505F),
        "toolbarIcon": c(0xFFB06A80),
        "toolCircleBackground": c(0x8CFFFFFF),
        "animation": "FLOW",
        "animationSpeed": 0.5,
        "fontId": "google:Caveat",
        "fontScale": 1.2,
        "boldKeyLabels": True,
        "soundStyle": "CUSTOM",
        "soundCustomId": "Marimba",
        "keyEffect": "EMOJI",
        "keyEffectParam": "🌸💮🌷",
        "keyEffectIntensity": 1.0,
        "decals": [
            {"id": "branch", "x": 0.84, "y": 0.16, "scale": 0.42, "rotationDeg": 0.0, "opacity": 0.95},
            {"id": "drift", "x": 0.12, "y": 0.78, "scale": 0.2, "rotationDeg": 25.0, "opacity": 0.8},
        ],
        "assets": {
            "decal:branch": b64(petal_branch()),
            "decal:drift": b64(_petal_cluster()),
        },
    }


def _petal_cluster() -> Image.Image:
    img = Image.new("RGBA", (256, 200), (0, 0, 0, 0))
    for _ in range(6):
        p = petal(rng.choice([(255, 183, 205), (255, 208, 221)]), 56)
        img.alpha_composite(p, (rng.randint(0, 190), rng.randint(0, 130)))
    return img


def synthwave_highway() -> dict:
    return {
        "id": "synthwave-highway",
        "name": "Synthwave Highway",
        "dark": True,
        "boardBackground": c(0x3D0A0020),
        "backgroundAnimated": True,
        "backgroundImageOpacity": 1.0,
        "backgroundImageBlur": 0.0,
        "keyShape": "SLANT",
        "keyBackground": c(0xB3150F2E),
        "keyText": c(0xFFFFD5F2),
        "modifierKeyBackground": c(0xB30E0A20),
        "modifierKeyText": c(0xFF9AE8FF),
        "enterKeyBackground": c(0xFFFF2DAF),
        "enterKeyText": c(0xFF1C0014),
        "keyBorderColor": c(0xFFFF2DAF),
        "keyBorderWidthDp": 1.0,
        "accent": c(0xFF00E5FF),
        "gestureTrailColor": c(0xFF00E5FF),
        "gestureTrailWidthDp": 14.0,
        "gestureTrailOpacity": 0.8,
        "popupBackground": c(0xFF1E1440),
        "popupText": c(0xFFFFD5F2),
        "popupHeightDp": 64,
        "toolShape": "PILL",
        "toolWidthDp": 52,
        "toolCircleRadiusDp": 12,
        "toolbarIcon": c(0xFF9AE8FF),
        "toolCircleBackground": c(0x66150F2E),
        "keyEffect": "SPARKLE",
        "keyEffectIntensity": 1.4,
        "assets": {},
        "backgroundImageBase64": b64_gif(synthwave_gif(), 80),
    }


def blockland() -> dict:
    cubes = [
        cube_sprite((121, 189, 92), (95, 66, 44), (121, 85, 58)),
        cube_sprite((150, 150, 154), (100, 100, 104), (127, 127, 130)),
        cube_sprite((190, 152, 100), (132, 100, 60), (168, 132, 84)),
    ]
    return {
        "id": "blockland",
        "name": "Blockland",
        "dark": False,
        "boardBackground": c(0xFF87CEEB),
        "keyShape": "SHARP",
        "keyBackground": c(0xFF9B7653),
        "keyText": c(0xFFFFFFFF),
        "modifierKeyBackground": c(0xFF7F7F82),
        "modifierKeyText": c(0xFFF2F2F2),
        "enterKeyBackground": c(0xFF58A03E),
        "enterKeyText": c(0xFFFFFFFF),
        "keyBorderColor": c(0x66000000),
        "keyBorderWidthDp": 1.5,
        "accent": c(0xFF58A03E),
        "popupBackground": c(0xFF6B4F35),
        "popupText": c(0xFFFFFFFF),
        "suggestionText": c(0xFF2E2418),
        "toolbarIcon": c(0xFF3A2E1E),
        "toolCircleBackground": c(0x8CFFFFFF),
        "keyTextureScale": "TILE",
        "keyTextureOpacity": 1.0,
        "boldKeyLabels": True,
        "hintFontScale": 1.1,
        "soundStyle": "THOCK",
        "keyEffect": "CUSTOM_IMAGE",
        "keyEffectIntensity": 1.6,
        "keyOverrides": {
            "e": {"background": c(0xFF2EBD6B), "text": c(0xFFFFFFFF)},
            "ENTER": {"popupBackground": c(0xFFFFD24A), "popupText": c(0xFF3A2E00)},
        },
        "assets": {
            "keyTexture": b64(dirt_tile()),
            "keyTextureModifier": b64(stone_tile()),
            "keyTextureEnter": b64(grass_tile()),
            "keyTextureSpace": b64(plank_tile()),
            **{f"effectImage:{i}": b64(img) for i, img in enumerate(cubes)},
        },
    }


def typewriter_noir() -> dict:
    return {
        "id": "typewriter-noir",
        "name": "Typewriter Noir",
        "dark": True,
        "boardBackground": c(0xFF17130E),
        "keyShape": "TICKET",
        "keyCornerRadiusDp": 10,
        "keyBackground": c(0xFFF3EAD8),
        "keyText": c(0xFF241F19),
        "modifierKeyBackground": c(0xFFD9CDB4),
        "modifierKeyText": c(0xFF241F19),
        "enterKeyBackground": c(0xFFB3282D),
        "enterKeyText": c(0xFFF8F2E4),
        "pressedKeyBackground": c(0xFFCBBFa4 & 0xFFFFFFFF),
        "keyBorderColor": c(0xFF5A4E3C),
        "keyBorderWidthDp": 1.0,
        "accent": c(0xFFB3282D),
        "popupBackground": c(0xFFF3EAD8),
        "popupText": c(0xFF241F19),
        "popupShape": "TICKET",
        "toolbarIcon": c(0xFFC8B890),
        "toolCircleBackground": c(0xFF2A2318),
        "toolCircleActiveBackground": c(0xFF4A3F2A),
        "chipBackground": c(0xFF241E15),
        "suggestionText": c(0xFFE8DFC8),
        "keyTextureScale": "CROP",
        "keyTextureOpacity": 0.5,
        "hintFontScale": 0.8,
        "fontId": "google:JetBrains Mono",
        "soundStyle": "CUSTOM",
        "soundCustomId": "Typewriter",
        "keyOverrides": {
            "ENTER": {"popupBackground": c(0xFFB3282D), "popupText": c(0xFFF8F2E4)},
            "SHIFT": {"background": c(0xFF3A332A), "text": c(0xFFE8DFC8)},
            "DELETE": {"background": c(0xFF3A332A), "text": c(0xFFE8DFC8)},
        },
        "assets": {
            "keyTexture": b64(paper_tile()),
        },
    }


def deep_orbit() -> dict:
    return {
        "id": "deep-orbit",
        "name": "Deep Orbit",
        "dark": True,
        "boardBackground": c(0x52000814),
        "boardGradient": {
            "colors": [c(0x66502B8C), c(0x00000000)],
            "type": "RADIAL",
            "angleDeg": 0.0,
        },
        "backgroundImageOpacity": 1.0,
        "keyShape": "PILL",
        "keyBackground": c(0xB31A1633),
        "keyText": c(0xFFE8E4FF),
        "modifierKeyBackground": c(0xB3120E26),
        "modifierKeyText": c(0xFFB8B0E8),
        "enterKeyBackground": c(0xFF7C5CFF),
        "enterKeyText": c(0xFF0E0820),
        "accent": c(0xFFB69CFF),
        "gestureTrailColor": c(0xFFB69CFF),
        "popupBackground": c(0xF01E1838),
        "popupText": c(0xFFE8E4FF),
        "toolShape": "HEXAGON",
        "toolbarIcon": c(0xFFB8B0E8),
        "toolCircleBackground": c(0x66241E48),
        "toolBorderColor": c(0xFF7C5CFF),
        "toolBorderWidthDp": 1.0,
        "keyGapScale": 1.15,
        "keyTextureScale": "CROP",
        "keyTextureOpacity": 0.9,
        "soundStyle": "CUSTOM",
        "soundCustomId": "Droplet",
        "keyEffect": "STARS",
        "keyEffectIntensity": 1.2,
        "decals": [
            {"id": "planet", "x": 0.86, "y": 0.2, "scale": 0.3, "rotationDeg": 8.0, "opacity": 0.95},
            {"id": "spark", "x": 0.1, "y": 0.24, "scale": 0.08, "rotationDeg": 0.0, "opacity": 0.9},
        ],
        "assets": {
            "keyTextureSpace": b64(galaxy_strip(), "JPEG", quality=80),
            "decal:planet": b64(planet_decal()),
            "decal:spark": b64(star_sprite()),
            "backgroundImage": "",  # replaced below; kept for slot ordering
        },
        "backgroundImageBase64": b64(nebula_background(), "JPEG", quality=82),
    }


# --- preview renders --------------------------------------------------------


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def argb_to_rgba(v: int) -> tuple:
    return ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF, (v >> 24) & 0xFF)


def preview(theme: dict, subtitle: str) -> Image.Image:
    """A mock keyboard card: board colour/gradient washes, three key rows."""
    w, h = 720, 460
    img = Image.new("RGB", (w, h), (18, 16, 28))
    # Background: nebula/synthwave themes show their actual image.
    b64bg = theme.get("backgroundImageBase64")
    if b64bg:
        bg = Image.open(io.BytesIO(base64.b64decode(b64bg)))
        bg = bg.convert("RGB").resize((w, h))
        img.paste(bg)
    else:
        grad = theme.get("boardGradient")
        colours = (
            [argb_to_rgba(v)[:3] for v in grad["colors"]]
            if grad
            else [argb_to_rgba(theme["boardBackground"])[:3]] * 2
        )
        for y in range(h):
            t = y / h
            idx = min(len(colours) - 2, int(t * (len(colours) - 1)))
            f = t * (len(colours) - 1) - idx
            colour = tuple(
                int(colours[idx][ch] + (colours[idx + 1][ch] - colours[idx][ch]) * f)
                for ch in range(3)
            )
            ImageDraw.Draw(img).line([(0, y), (w, y)], fill=colour)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Board scrim.
    scrim = argb_to_rgba(theme["boardBackground"])
    if scrim[3] > 0:
        draw.rectangle([0, 0, w, h], fill=scrim)

    key = argb_to_rgba(theme["keyBackground"])
    mod = argb_to_rgba(theme.get("modifierKeyBackground", theme["keyBackground"]))
    enter = argb_to_rgba(theme.get("enterKeyBackground", theme["keyBackground"]))
    border = theme.get("keyBorderColor")
    border = argb_to_rgba(border) if border else None
    radius = 6 if theme["keyShape"] in ("SHARP",) else 16

    # Key texture wash, if the theme carries one.
    tex = theme.get("assets", {}).get("keyTexture")
    tex_img = None
    if tex:
        tex_img = Image.open(io.BytesIO(base64.b64decode(tex))).convert("RGBA")

    top = 150
    rows = [10, 9, 7]
    key_h = 74
    for r, count in enumerate(rows):
        key_w = (w - 40) // 10
        inset = (w - key_w * count) // 2
        for i in range(count):
            x0 = inset + i * key_w + 4
            y0 = top + r * (key_h + 12)
            box = [x0, y0, x0 + key_w - 8, y0 + key_h]
            is_mod = r == 2 and i in (0, count - 1)
            fill = mod if is_mod else key
            rounded(draw, box, radius, fill, border, 2)
            if tex_img is not None and not is_mod:
                tile = tex_img.resize((key_w - 8, key_h))
                alpha = int(255 * theme.get("keyTextureOpacity", 1.0))
                tile.putalpha(tile.split()[3].point(lambda a: a * alpha // 255))
                mask = Image.new("L", tile.size, 0)
                ImageDraw.Draw(mask).rounded_rectangle(
                    [0, 0, tile.width, tile.height], radius=radius, fill=255
                )
                tile.putalpha(Image.composite(tile.split()[3], mask, mask))
                overlay.alpha_composite(tile, (x0, y0))
    # Space row with enter.
    y0 = top + 3 * (key_h + 12)
    rounded(draw, [150, y0, w - 190, y0 + key_h], radius, key, border, 2)
    rounded(draw, [w - 180, y0, w - 30, y0 + key_h], radius, enter, border, 2)

    composed = Image.alpha_composite(img.convert("RGBA"), overlay)

    # The theme's stickers, where the keyboard puts them.
    for decal in theme.get("decals", []):
        raw = theme.get("assets", {}).get(f"decal:{decal['id']}")
        if not raw:
            continue
        sticker = Image.open(io.BytesIO(base64.b64decode(raw))).convert("RGBA")
        dst_w = max(1, int(w * decal["scale"]))
        dst_h = max(1, int(dst_w * sticker.height / sticker.width))
        sticker = sticker.resize((dst_w, dst_h)).rotate(
            -decal.get("rotationDeg", 0.0), expand=True, resample=Image.BICUBIC
        )
        alpha = int(255 * decal.get("opacity", 1.0))
        sticker.putalpha(sticker.split()[3].point(lambda a: a * alpha // 255))
        cx, cy = int(w * decal["x"]), int(150 + (h - 150) * decal["y"])
        composed.alpha_composite(sticker, (cx - sticker.width // 2, cy - sticker.height // 2))

    img = composed.convert("RGB")

    # Caption, in whichever polarity the theme's own board keeps readable.
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype(str(ROOT / "fonts" / "inter.ttf"), 44)
        sub_font = ImageFont.truetype(str(ROOT / "fonts" / "inter.ttf"), 20)
    except OSError:
        title_font = sub_font = ImageFont.load_default()
    dark_theme = theme.get("dark", True)
    ink = (255, 255, 255) if dark_theme else (40, 26, 34)
    halo = (0, 0, 0) if dark_theme else (255, 255, 255)
    sub_ink = (235, 235, 245) if dark_theme else (90, 62, 74)
    name = theme["name"]
    tw = draw.textlength(name, font=title_font)
    for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
        draw.text(((w - tw) // 2 + dx, 36 + dy), name, font=title_font, fill=halo)
    draw.text(((w - tw) // 2, 36), name, font=title_font, fill=ink)
    sw = draw.textlength(subtitle, font=sub_font)
    draw.text(((w - sw) // 2 + 1, 95 + 1), subtitle, font=sub_font, fill=halo)
    draw.text(((w - sw) // 2, 95), subtitle, font=sub_font, fill=sub_ink)
    return img


SUBTITLES = {
    "arcade-cabinet": "Pixel font, blip sounds, coin bursts, neon sweep",
    "sakura-breeze": "Blossom stickers, petal bursts, a flowing pink sky",
    "synthwave-highway": "An animated sunset grid behind slanted neon keys",
    "blockland": "Tiled block textures with crumbling cube bursts",
    "typewriter-noir": "Paper keys, mono type, a red carriage return",
    "deep-orbit": "A nebula photo, a ringed planet, star bursts",
}


def main() -> None:
    THEMES.mkdir(exist_ok=True)
    PREVIEWS.mkdir(exist_ok=True)
    builders = [
        arcade_cabinet,
        sakura_breeze,
        synthwave_highway,
        blockland,
        typewriter_noir,
        deep_orbit,
    ]
    for build in builders:
        theme = build()
        theme["assets"] = {k: v for k, v in theme.get("assets", {}).items() if v}
        path = THEMES / f"{theme['id']}.wmtheme.json"
        path.write_text(json.dumps(theme, ensure_ascii=False, indent=1) + "\n")
        preview_img = preview(theme, SUBTITLES[theme["id"]])
        preview_img.save(PREVIEWS / f"{theme['id']}.jpg", quality=88)
        size = path.stat().st_size
        print(f"{theme['id']:<20} {size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
