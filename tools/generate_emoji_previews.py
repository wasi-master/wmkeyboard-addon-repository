#!/usr/bin/env python3
"""Generate preview grid images for all emoji fonts in the repository."""

import fitz
import io
import os
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import fontTools.ttLib as ttLib

ROOT = Path(__file__).resolve().parent.parent
PREVIEWS_DIR = ROOT / "previews"
FONTS_DIR = ROOT / "fonts"

DEFAULT_EMOJI_LIST = [
    'u1F600', 'u1F602', 'u1F60D', 'u1F914', 'u1F973',
    'u1F680', 'u1F525', 'u1F355', 'u1F431', 'u1F389',
    'u1F499', 'u1F601', 'u1F604', 'u1F609', 'u1F60A',
    'u1F618', 'u1F60E', 'u1F970', 'u1F97A', 'u1F929'
]

# Emojitwo only supports Unicode 9 and below
EMOJITWO_LIST = [
    'u1F600', 'u1F602', 'u1F60D', 'u1F914', 'u1F61C',
    'u1F680', 'u1F525', 'u1F355', 'u1F431', 'u1F389',
    'u1F499', 'u1F601', 'u1F604', 'u1F609', 'u1F60A',
    'u1F618', 'u1F60E', 'u1F970', 'u1F97A', 'u1F61D'
]

def get_unicode_char(glyph_code):
    if glyph_code.startswith('u') and len(glyph_code) >= 5:
        hex_str = glyph_code[1:]
        return chr(int(hex_str, 16))
    return None

def fetch_openmoji_png(glyph_code):
    if glyph_code.startswith('u'):
        hex_str = glyph_code[1:].upper()
        url = f"https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/72x72/{hex_str}.png"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            data = urllib.request.urlopen(req).read()
            return Image.open(io.BytesIO(data))
        except Exception as e:
            print(f"Error fetching OpenMoji {glyph_code}: {e}", flush=True)
    return None

def extract_emoji_image(font_path, font_type, glyph_name, pil_font=None, cbdt_strike=None):
    if font_type == 'cbdt' and cbdt_strike:
        if glyph_name in cbdt_strike:
            obj = cbdt_strike[glyph_name]
            raw = obj.data
            png_idx = raw.find(b'\x89PNG')
            if png_idx != -1:
                return Image.open(io.BytesIO(raw[png_idx:]))
    elif font_type == 'pil_colr' and pil_font:
        char = get_unicode_char(glyph_name)
        if char:
            img = Image.new('RGBA', (140, 140), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), char, font=pil_font, embedded_color=True)
            return img
    elif font_type == 'openmoji_web':
        return fetch_openmoji_png(glyph_name)
    return None

def generate_preview(font_path, font_type, output_path, title, subtitle, bg_start, bg_end, accent_color, emoji_list=DEFAULT_EMOJI_LIST):
    width, height = 1080, 900
    canvas = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(canvas)

    pil_font = ImageFont.truetype(str(font_path), 100) if font_type == 'pil_colr' else None
    
    cbdt_strike = None
    if font_type == 'cbdt':
        font = ttLib.TTFont(font_path, lazy=True)
        if 'CBDT' in font:
            cbdt_strike = font['CBDT'].strikeData[0]

    # Background gradient
    for y in range(height):
        r = int(bg_start[0] + (bg_end[0] - bg_start[0]) * y / height)
        g = int(bg_start[1] + (bg_end[1] - bg_start[1]) * y / height)
        b = int(bg_start[2] + (bg_end[2] - bg_start[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Fonts
    inter_path = FONTS_DIR / "inter.ttf"
    title_font = ImageFont.truetype(str(inter_path), 56)
    subtitle_font = ImageFont.truetype(str(inter_path), 24)

    # Title
    title_w = draw.textlength(title, font=title_font)
    draw.text(((width - title_w) // 2, 60), title, fill=(255, 255, 255), font=title_font)

    # Subtitle
    sub_w = draw.textlength(subtitle, font=subtitle_font)
    draw.text(((width - sub_w) // 2, 135), subtitle, fill=(203, 213, 225), font=subtitle_font)

    # Divider line
    draw.line([(120, 185), (width - 120, 185)], fill=(71, 85, 105), width=2)

    # Emoji Grid: 5 columns x 4 rows
    cols = 5
    card_w, card_h = 160, 135
    gap_x, gap_y = 28, 24
    grid_w = cols * card_w + (cols - 1) * gap_x
    start_x = (width - grid_w) // 2
    start_y = 220

    for idx, emoji_code in enumerate(emoji_list):
        r_idx = idx // cols
        c_idx = idx % cols
        x = start_x + c_idx * (card_w + gap_x)
        y = start_y + r_idx * (card_h + gap_y)

        # Card container
        draw.rounded_rectangle(
            [x, y, x + card_w, y + card_h],
            radius=16,
            fill=(30, 41, 59),
            outline=accent_color,
            width=2
        )

        # Render emoji image
        emoji_img = extract_emoji_image(font_path, font_type, emoji_code, pil_font=pil_font, cbdt_strike=cbdt_strike)
        if emoji_img:
            emoji_img = emoji_img.convert("RGBA")
            target_size = 115 if font_type == 'openmoji_web' else 90
            if font_type == 'openmoji_web':
                emoji_img = emoji_img.resize((target_size, target_size), Image.Resampling.LANCZOS)
            else:
                emoji_img.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
            ew, eh = emoji_img.size
            ex = x + (card_w - ew) // 2
            ey = y + (card_h - eh) // 2
            canvas.paste(emoji_img, (ex, ey), emoji_img)

    # Save
    canvas.save(output_path, "JPEG", quality=92)
    print(f"Generated {output_path}", flush=True)

def main():
    configs = [
        {
            "font_path": FONTS_DIR / "blobmoji.ttf",
            "font_type": "cbdt",
            "output_path": PREVIEWS_DIR / "blobmoji.jpg",
            "title": "Blobmoji",
            "subtitle": "Google's classic blob emojis updated for modern Unicode standard",
            "bg_start": (15, 23, 42),
            "bg_end": (30, 41, 59),
            "accent_color": (251, 191, 36),
            "emoji_list": DEFAULT_EMOJI_LIST
        },
        {
            "font_path": FONTS_DIR / "fluent-emoji.ttf",
            "font_type": "cbdt",
            "output_path": PREVIEWS_DIR / "fluent-emoji.jpg",
            "title": "Fluent Emoji",
            "subtitle": "Microsoft's modern, friendly 3D emoji collection",
            "bg_start": (15, 23, 42),
            "bg_end": (49, 46, 129),
            "accent_color": (129, 140, 248),
            "emoji_list": DEFAULT_EMOJI_LIST
        },
        {
            "font_path": FONTS_DIR / "twemoji.ttf",
            "font_type": "pil_colr",
            "output_path": PREVIEWS_DIR / "twemoji-grid.jpg",
            "title": "Twemoji",
            "subtitle": "Twitter's flat, friendly vector emoji collection",
            "bg_start": (15, 23, 42),
            "bg_end": (12, 74, 110),
            "accent_color": (56, 189, 248),
            "emoji_list": DEFAULT_EMOJI_LIST
        },
        {
            "font_path": FONTS_DIR / "openmoji-color.ttf",
            "font_type": "openmoji_web",
            "output_path": PREVIEWS_DIR / "openmoji-grid.jpg",
            "title": "OpenMoji Color",
            "subtitle": "Hand-crafted open-source illustrations with distinct outlines",
            "bg_start": (15, 23, 42),
            "bg_end": (6, 78, 59),
            "accent_color": (52, 211, 153),
            "emoji_list": DEFAULT_EMOJI_LIST
        },
        {
            "font_path": FONTS_DIR / "emojitwo.ttf",
            "font_type": "pil_colr",
            "output_path": PREVIEWS_DIR / "emojitwo-grid.jpg",
            "title": "Emojitwo",
            "subtitle": "Clean, classic open-source vector emojis",
            "bg_start": (15, 23, 42),
            "bg_end": (112, 26, 117),
            "accent_color": (232, 121, 249),
            "emoji_list": EMOJITWO_LIST
        }
    ]

    for cfg in configs:
        generate_preview(**cfg)

if __name__ == "__main__":
    main()
