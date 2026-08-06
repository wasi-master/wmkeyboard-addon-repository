#!/usr/bin/env python3
"""Standardized generator script for Font showcase preview images (large legible typography matching screenshots)."""

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PREVIEWS_DIR = ROOT / "previews"
FONTS_DIR = ROOT / "fonts"

FONT_CONFIGS = [
    {
        "id": "inter",
        "name": "Inter",
        "subtitle": "Clean, highly legible variable sans-serif UI font family",
        "font_path": FONTS_DIR / "inter.ttf",
        "output_path": PREVIEWS_DIR / "inter-grid.jpg",
        "sample_text": "The quick brown fox jumps over the lazy dog",
        "specimen_chars": "Aa Bb Cc Dd Ee Ff Gg Hh Ii Jj Kk Ll Mm Nn Oo Pp Qq Rr Ss Tt Uu Vv Ww Xx Yy Zz • 0123456789",
        "bg_start": (15, 23, 42),
        "bg_end": (30, 41, 59),
        "accent_color": (56, 189, 248),
        "footer_text": "SIL Open Font License • Variable Sans-Serif • Optimized for Screens",
        "main_key_size": 48,
        "hint_key_size": 18,
        "space_key_size": 20,
        "sample_font_size": 40,
        "chars_font_size": 22,
    },
    {
        "id": "jetbrains-mono",
        "name": "JetBrains Mono",
        "subtitle": "Monospaced font family crafted for developers & code",
        "font_path": FONTS_DIR / "jetbrains-mono.ttf",
        "output_path": PREVIEWS_DIR / "jetbrains-mono-grid.jpg",
        "sample_text": "function main() { return 'Hello World'; }",
        "specimen_chars": "Aa Bb Cc Dd Ee Ff Gg Hh Ii Jj Kk Ll Mm Nn Oo Pp Qq Rr Ss Tt Uu Vv Ww Xx Yy Zz 0123456789",
        "bg_start": (15, 23, 42),
        "bg_end": (6, 78, 59),
        "accent_color": (52, 211, 153),
        "footer_text": "SIL Open Font License • Developer Monospace • High Legibility",
        "main_key_size": 46,
        "hint_key_size": 17,
        "space_key_size": 19,
        "sample_font_size": 36,
        "chars_font_size": 19,
    },
    {
        "id": "caveat",
        "name": "Caveat",
        "subtitle": "Casual and expressive handwriting script with a natural aesthetic",
        "font_path": FONTS_DIR / "caveat.ttf",
        "output_path": PREVIEWS_DIR / "caveat-grid.jpg",
        "sample_text": "The quick brown fox jumps over the lazy dog",
        "specimen_chars": "Aa Bb Cc Dd Ee Ff Gg Hh Ii Jj Kk Ll Mm Nn Oo Pp Qq Rr Ss Tt Uu Vv Ww Xx Yy Zz • 0123456789",
        "bg_start": (15, 23, 42),
        "bg_end": (76, 29, 149),
        "accent_color": (192, 132, 252),
        "footer_text": "SIL Open Font License • Casual Handwriting Script • Natural Curves",
        "main_key_size": 52,
        "hint_key_size": 20,
        "space_key_size": 22,
        "sample_font_size": 44,
        "chars_font_size": 24,
    },
    {
        "id": "press-start-2p",
        "name": "Press Start 2P",
        "subtitle": "Retro 8-bit arcade bitmap font inspired by 1980s graphics",
        "font_path": FONTS_DIR / "press-start-2p.ttf",
        "output_path": PREVIEWS_DIR / "press-start-2p-grid.jpg",
        "sample_text": "PRESS START TO PLAY 1985",
        "specimen_chars": "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z • 0123456789",
        "bg_start": (15, 23, 42),
        "bg_end": (124, 45, 18),
        "accent_color": (251, 146, 60),
        "footer_text": "SIL Open Font License • Retro 8-Bit Pixel Font • Arcade Graphic Style",
        "main_key_size": 26,
        "hint_key_size": 13,
        "space_key_size": 15,
        "sample_font_size": 26,
        "chars_font_size": 14,
    },
    {
        "id": "wm-font",
        "name": "WM Font",
        "subtitle": "Handwriting script with Latin, Greek, math symbols & fractions",
        "font_path": FONTS_DIR / "wm-font.ttf",
        "output_path": PREVIEWS_DIR / "wm_font-grid.jpg",
        "sample_text": "Handwriting & Math: α β γ  ∑ ∫ x²  ½ ¾",
        "specimen_chars": "Aa Bb Cc Dd Ee Ff Gg Hh Ii Jj Kk Ll Mm Nn Oo Pp Qq Rr Ss Tt Uu Vv Ww Xx Yy Zz • 0123456789",
        "bg_start": (15, 23, 42),
        "bg_end": (112, 26, 117),
        "accent_color": (232, 121, 249),
        "footer_text": "SIL Open Font License • Handwriting & Math Symbols • Latin & Greek",
        "main_key_size": 50,
        "hint_key_size": 19,
        "space_key_size": 20,
        "sample_font_size": 38,
        "chars_font_size": 22,
    },
]

# Standard QWERTY keyboard layout rows for rendering font in-keyboard mockups
QWERTY_ROWS = [
    [
        {"label": "1", "hint": "1"}, {"label": "2", "hint": "2"}, {"label": "3", "hint": "3"},
        {"label": "4", "hint": "4"}, {"label": "5", "hint": "5"}, {"label": "6", "hint": "6"},
        {"label": "7", "hint": "7"}, {"label": "8", "hint": "8"}, {"label": "9", "hint": "9"},
        {"label": "0", "hint": "0"}
    ],
    [
        {"label": "q"}, {"label": "w"}, {"label": "e", "hint": "è"}, {"label": "r"},
        {"label": "t"}, {"label": "y"}, {"label": "u", "hint": "ù"}, {"label": "i", "hint": "ì"},
        {"label": "o", "hint": "ò"}, {"label": "p"}
    ],
    [
        {"label": "a", "hint": "@"}, {"label": "s", "hint": "#"}, {"label": "d", "hint": "$"},
        {"label": "f", "hint": "-"}, {"label": "g", "hint": "&"}, {"label": "h", "hint": "+"},
        {"label": "j", "hint": "("}, {"label": "k", "hint": ")"}, {"label": "l", "hint": "/"}
    ],
    [
        {"label": "⇧", "width": 1.4, "action": "shift"},
        {"label": "z", "hint": "*"}, {"label": "x", "hint": "\""}, {"label": "c", "hint": "'"},
        {"label": "v", "hint": ":"}, {"label": "b", "hint": ";"}, {"label": "n", "hint": "!"},
        {"label": "m", "hint": "?"},
        {"label": "⌫", "width": 1.4, "action": "delete"}
    ],
    [
        {"label": "?123", "width": 1.5, "action": "symbols"},
        {"label": "🌐", "width": 1.0, "action": "language_switch"},
        {"label": " ", "width": 4.5, "action": "space"},
        {"label": ".", "width": 1.0},
        {"label": "⏎", "width": 1.5, "action": "enter"}
    ]
]


def draw_toolbar_icons(draw: ImageDraw.ImageDraw, top_x: int, top_y: int, kb_w: int):
    """Draw prominent vector icons with rounded circle backgrounds for the keyboard toolbar."""
    icon_color = (226, 232, 240)      # Slate 200
    circle_bg = (30, 41, 59)          # Slate 800
    circle_border = (51, 65, 85)      # Slate 700

    centers = [top_x + int(kb_w * factor) for factor in (0.2, 0.4, 0.6, 0.8)]
    cy = top_y + 26
    radius = 16

    for cx in centers:
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=circle_bg,
            outline=circle_border,
            width=1,
        )

    # 1. Grid Menu Icon
    cx1 = centers[0]
    for r in (-7, 2):
        for c in (-7, 2):
            draw.rounded_rectangle([cx1 + c, cy + r, cx1 + c + 5, cy + r + 5], radius=1, fill=icon_color)

    # 2. Clipboard Icon
    cx2 = centers[1]
    draw.rounded_rectangle([cx2 - 7, cy - 8, cx2 + 7, cy + 9], radius=2, outline=icon_color, width=1)
    draw.rectangle([cx2 - 4, cy - 10, cx2 + 4, cy - 7], fill=icon_color)

    # 3. Settings Gear Icon
    cx3 = centers[2]
    draw.ellipse([cx3 - 7, cy - 7, cx3 + 7, cy + 7], outline=icon_color, width=2)
    draw.ellipse([cx3 - 2, cy - 2, cx3 + 2, cy + 2], fill=icon_color)

    # 4. Emoji Smile Icon
    cx4 = centers[3]
    draw.ellipse([cx4 - 8, cy - 8, cx4 + 8, cy + 8], outline=icon_color, width=2)
    draw.ellipse([cx4 - 4, cy - 4, cx4 - 2, cy - 2], fill=icon_color)
    draw.ellipse([cx4 + 3, cy - 4, cx4 + 5, cy - 2], fill=icon_color)
    draw.arc([cx4 - 4, cy - 4, cx4 + 4, cy + 4], start=30, end=150, fill=icon_color, width=2)


def draw_globe_icon(draw: ImageDraw.ImageDraw, cx: float, cy: float, color: tuple):
    """Draw a vector globe icon on the language switch key."""
    draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], outline=color, width=2)
    draw.line([(cx - 10, cy), (cx + 10, cy)], fill=color, width=1)
    draw.ellipse([cx - 4.5, cy - 10, cx + 4.5, cy + 10], outline=color, width=1)


def render_keyboard_font_mockup(
    draw: ImageDraw.ImageDraw,
    top_x: int,
    top_y: int,
    kb_w: int,
    target_font_path: str,
    inter_font_path: str,
    font_id: str,
    accent_color: tuple,
    main_key_size: int,
    hint_key_size: int,
    space_key_size: int,
):
    """Render a full QWERTY keyboard mockup with HUGE legible key labels matching actual screenshots."""
    pad_x = 18
    pad_y = 16
    gap_x = 8
    gap_y = 10
    toolbar_h = 52

    num_rows = len(QWERTY_ROWS)
    key_h = 88
    kb_h = toolbar_h + pad_y * 2 + num_rows * key_h + (num_rows - 1) * gap_y

    # Keyboard Frame Outer Rectangle
    draw.rounded_rectangle(
        [top_x, top_y, top_x + kb_w, top_y + kb_h],
        radius=22,
        fill=(15, 23, 42),
        outline=(51, 65, 85),
        width=2,
    )

    # Toolbar Header & Icons
    draw_toolbar_icons(draw, top_x, top_y, kb_w)
    draw.line(
        [(top_x + pad_x, top_y + toolbar_h), (top_x + kb_w - pad_x, top_y + toolbar_h)],
        fill=(30, 41, 59),
        width=1,
    )

    # Fonts
    target_main_font = ImageFont.truetype(target_font_path, main_key_size)
    target_hint_font = ImageFont.truetype(target_font_path, hint_key_size)
    target_space_font = ImageFont.truetype(target_font_path, space_key_size)

    inter_action_font = ImageFont.truetype(inter_font_path, 28)
    inter_hint_font = ImageFont.truetype(inter_font_path, 16)

    usable_w = kb_w - (pad_x * 2)
    start_y = top_y + toolbar_h + pad_y

    for r_idx, row in enumerate(QWERTY_ROWS):
        curr_y = start_y + r_idx * (key_h + gap_y)

        total_units = sum(k.get("width", 1.0) for k in row)
        num_gaps = len(row) - 1
        total_gap_w = num_gaps * gap_x
        unit_w = (usable_w - total_gap_w) / total_units

        row_pixel_w = sum(k.get("width", 1.0) * unit_w for k in row) + total_gap_w
        row_start_x = top_x + pad_x + (usable_w - row_pixel_w) / 2
        curr_x = row_start_x

        for k in row:
            kw = k.get("width", 1.0) * unit_w
            kh = key_h
            label = k.get("label", "")
            action = k.get("action")
            hint = k.get("hint", "")

            # Keycap colors
            if action == "enter":
                bg_color = (14, 165, 233)
                border_color = (56, 189, 248)
                text_color = (255, 255, 255)
            elif action or label in ["⇧", "⌫", "?123", "🌐"]:
                bg_color = (24, 32, 47)
                border_color = (45, 58, 78)
                text_color = (203, 213, 225)
            elif action == "space" or label == " ":
                bg_color = (30, 41, 59)
                border_color = (51, 65, 85)
                text_color = (148, 163, 184)
            else:
                bg_color = (30, 41, 59)
                border_color = (51, 65, 85)
                text_color = (255, 255, 255)

            # Draw Keycap
            draw.rounded_rectangle(
                [curr_x, curr_y, curr_x + kw, curr_y + kh],
                radius=12,
                fill=bg_color,
                outline=border_color,
                width=1,
            )

            # 1. Long press corner hint
            if hint:
                use_hint_font = inter_hint_font if any(ord(c) > 127 for c in hint) else target_hint_font
                hw = draw.textlength(hint, font=use_hint_font)
                hx = curr_x + kw - hw - 8
                hy = curr_y + 6
                draw.text((hx, hy), hint, fill=(148, 163, 184), font=use_hint_font)

            # 2. Main Key Label
            if action == "language_switch" or label == "🌐":
                draw_globe_icon(draw, curr_x + kw / 2, curr_y + kh / 2, text_color)
            elif action in ["shift", "delete", "enter"]:
                lw = draw.textlength(label, font=inter_action_font)
                lx = curr_x + (kw - lw) / 2
                ly = curr_y + (kh - 28) / 2
                draw.text((lx, ly), label, fill=text_color, font=inter_action_font)
            elif action == "space" or label == " ":
                prefix, suffix = "<   ", "   >"
                full_space_text = f"{prefix}{font_id}{suffix}"
                stw = draw.textlength(full_space_text, font=target_space_font)
                stx = curr_x + (kw - stw) / 2
                sty = curr_y + (kh - 20) / 2
                draw.text((stx, sty), full_space_text, fill=(148, 163, 184), font=target_space_font)
            else:
                lw = draw.textlength(label, font=target_main_font)
                lx = curr_x + (kw - lw) / 2
                ly = curr_y + (kh - (20 if font_id == "press-start-2p" else 42)) / 2
                draw.text((lx, ly), label, fill=text_color, font=target_main_font)

            curr_x += kw + gap_x


def generate_font_preview(cfg: dict):
    """Generate 1080x900 showcase preview image for a font with huge, crystal-clear typography."""
    width, height = 1080, 900
    canvas = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(canvas)

    bg_start = cfg["bg_start"]
    bg_end = cfg["bg_end"]
    accent_color = cfg["accent_color"]

    # 1. Background Gradient
    for y in range(height):
        r = int(bg_start[0] + (bg_end[0] - bg_start[0]) * y / height)
        g = int(bg_start[1] + (bg_end[1] - bg_start[1]) * y / height)
        b = int(bg_start[2] + (bg_end[2] - bg_start[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 2. Header & Specimen Fonts
    inter_path = FONTS_DIR / "inter.ttf"
    title_font = ImageFont.truetype(str(inter_path), 46)
    subtitle_font = ImageFont.truetype(str(inter_path), 20)
    footer_font = ImageFont.truetype(str(inter_path), 16)

    font_path = cfg["font_path"]

    # 3. Header Title & Subtitle (Centered)
    title = cfg["name"]
    title_w = draw.textlength(title, font=title_font)
    draw.text(((width - title_w) // 2, 22), title, fill=(255, 255, 255), font=title_font)

    subtitle = cfg["subtitle"]
    sub_w = draw.textlength(subtitle, font=subtitle_font)
    draw.text(((width - sub_w) // 2, 78), subtitle, fill=(203, 213, 225), font=subtitle_font)

    # 4. Top Specimen Banner Card (Height 140px)
    spec_x, spec_y, spec_w, spec_h = 40, 110, 1000, 140
    draw.rounded_rectangle(
        [spec_x, spec_y, spec_x + spec_w, spec_y + spec_h],
        radius=18,
        fill=(24, 32, 47),
        outline=accent_color,
        width=2,
    )

    max_text_w = spec_w - 48  # 952px max width inside specimen box

    # Dynamic scaling for Line 1 (Sample Text) to guarantee ZERO overflow
    sample_text = cfg["sample_text"]
    sample_size = cfg["sample_font_size"]
    specimen_font = ImageFont.truetype(str(font_path), sample_size)
    while draw.textlength(sample_text, font=specimen_font) > max_text_w and sample_size > 14:
        sample_size -= 1
        specimen_font = ImageFont.truetype(str(font_path), sample_size)

    stw = draw.textlength(sample_text, font=specimen_font)
    stx = spec_x + (spec_w - stw) / 2
    sty = spec_y + 26
    draw.text((stx, sty), sample_text, fill=accent_color, font=specimen_font)

    # Dynamic scaling for Line 2 (Alphabet & Numbers) to guarantee ZERO overflow
    specimen_chars = cfg["specimen_chars"]
    chars_size = cfg["chars_font_size"]
    chars_font = ImageFont.truetype(str(font_path), chars_size)
    while draw.textlength(specimen_chars, font=chars_font) > max_text_w and chars_size > 10:
        chars_size -= 1
        chars_font = ImageFont.truetype(str(font_path), chars_size)

    alw = draw.textlength(specimen_chars, font=chars_font)
    alx = spec_x + (spec_w - alw) / 2
    aly = spec_y + 84
    draw.text((alx, aly), specimen_chars, fill=(241, 245, 249), font=chars_font)

    # 5. Render Full Keyboard UI Mockup
    kb_w = 1000
    kb_x = (width - kb_w) // 2
    kb_y = 264

    render_keyboard_font_mockup(
        draw=draw,
        top_x=kb_x,
        top_y=kb_y,
        kb_w=kb_w,
        target_font_path=str(font_path),
        inter_font_path=str(inter_path),
        font_id=cfg["id"],
        accent_color=accent_color,
        main_key_size=cfg["main_key_size"],
        hint_key_size=cfg["hint_key_size"],
        space_key_size=cfg["space_key_size"],
    )

    # 6. Footer Bar
    footer_text = cfg["footer_text"]
    fw = draw.textlength(footer_text, font=footer_font)
    draw.text(((width - fw) // 2, 860), footer_text, fill=(148, 163, 184), font=footer_font)

    # Save output JPEG image
    output_path = cfg["output_path"]
    canvas.save(output_path, "JPEG", quality=94)
    print(f"Successfully generated font preview grid image: {output_path.relative_to(ROOT)}", flush=True)


def main():
    PREVIEWS_DIR.mkdir(exist_ok=True)
    for cfg in FONT_CONFIGS:
        if cfg["font_path"].exists():
            generate_font_preview(cfg)


if __name__ == "__main__":
    main()
