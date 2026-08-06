#!/usr/bin/env python3
"""Standardized generator script for Layout showcase preview images (renders full keyboard UI mockup)."""

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PREVIEWS_DIR = ROOT / "previews"
LAYOUTS_DIR = ROOT / "layouts"
FONTS_DIR = ROOT / "fonts"


def draw_braille_cell(
    draw: ImageDraw.ImageDraw,
    center_x: float,
    center_y: float,
    braille_char: str,
    dot_radius: float = 5.5,
    spacing_x: float = 14.0,
    spacing_y: float = 13.0,
    active_color: tuple = (255, 255, 255),
    inactive_color: tuple = (50, 65, 85),
):
    """Draw a 6-dot Unicode Braille cell vector graphic directly."""
    val = ord(braille_char) - 0x2800 if 0x2800 <= ord(braille_char) <= 0x28FF else 0

    dot_map = [
        (0, 0, 0x01),  # Dot 1
        (0, 1, 0x02),  # Dot 2
        (0, 2, 0x04),  # Dot 3
        (1, 0, 0x08),  # Dot 4
        (1, 1, 0x10),  # Dot 5
        (1, 2, 0x20),  # Dot 6
    ]

    for col, row, mask in dot_map:
        dx = center_x - (spacing_x / 2) + col * spacing_x
        dy = center_y - spacing_y + row * spacing_y

        is_active = (val & mask) != 0
        if is_active:
            draw.ellipse(
                [dx - dot_radius, dy - dot_radius, dx + dot_radius, dy + dot_radius],
                fill=active_color,
                outline=None,
            )
        else:
            draw.ellipse(
                [dx - dot_radius + 1.5, dy - dot_radius + 1.5, dx + dot_radius - 1.5, dy + dot_radius - 1.5],
                fill=None,
                outline=inactive_color,
                width=1,
            )


def draw_toolbar_icons(draw: ImageDraw.ImageDraw, top_x: int, top_y: int, kb_w: int):
    """Draw prominent vector icons with rounded circle backgrounds for the keyboard toolbar."""
    icon_color = (226, 232, 240)      # Slate 200 (bright white/slate for high visibility)
    circle_bg = (30, 41, 59)          # Slate 800
    circle_border = (51, 65, 85)      # Slate 700

    centers = [top_x + int(kb_w * factor) for factor in (0.2, 0.4, 0.6, 0.8)]
    cy = top_y + 30
    radius = 18  # 36px diameter circle

    for cx in centers:
        # Draw Circle Background
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=circle_bg,
            outline=circle_border,
            width=1,
        )

    # 1. Grid Menu Icon
    cx1 = centers[0]
    for r in (-8, 2):
        for c in (-8, 2):
            draw.rounded_rectangle([cx1 + c, cy + r, cx1 + c + 6, cy + r + 6], radius=2, fill=icon_color)

    # 2. Clipboard Icon
    cx2 = centers[1]
    draw.rounded_rectangle([cx2 - 8, cy - 9, cx2 + 8, cy + 10], radius=3, outline=icon_color, width=2)
    draw.rectangle([cx2 - 5, cy - 11, cx2 + 5, cy - 8], fill=icon_color)

    # 3. Settings Gear Icon
    cx3 = centers[2]
    draw.ellipse([cx3 - 8, cy - 8, cx3 + 8, cy + 8], outline=icon_color, width=2)
    draw.ellipse([cx3 - 3, cy - 3, cx3 + 3, cy + 3], fill=icon_color)
    # Gear teeth
    for dx, dy in [(-10, 0), (10, 0), (0, -10), (0, 10), (-7, -7), (7, 7), (-7, 7), (7, -7)]:
        draw.rectangle([cx3 + dx - 1, cy + dy - 1, cx3 + dx + 1, cy + dy + 1], fill=icon_color)

    # 4. Emoji Smile Icon
    cx4 = centers[3]
    draw.ellipse([cx4 - 9, cy - 9, cx4 + 9, cy + 9], outline=icon_color, width=2)
    draw.ellipse([cx4 - 5, cy - 4, cx4 - 3, cy - 2], fill=icon_color)
    draw.ellipse([cx4 + 3, cy - 4, cx4 + 5, cy - 2], fill=icon_color)
    draw.arc([cx4 - 5, cy - 5, cx4 + 5, cy + 5], start=35, end=145, fill=icon_color, width=2)


def draw_globe_icon(draw: ImageDraw.ImageDraw, cx: float, cy: float, color: tuple):
    """Draw a vector globe icon on the language switch key."""
    draw.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=color, width=2)
    draw.line([(cx - 9, cy), (cx + 9, cy)], fill=color, width=1)
    draw.ellipse([cx - 4, cy - 9, cx + 4, cy + 9], outline=color, width=1)


def render_keyboard_mockup(
    layout_data: dict,
    draw: ImageDraw.ImageDraw,
    top_x: int,
    top_y: int,
    kb_w: int,
    inter_font_path: str,
    mono_font_path: str,
    accent_color: tuple = (14, 165, 233),
):
    """Render a full on-screen keyboard mockup directly onto the canvas."""
    layer = layout_data["layout"]["layers"]["letters"]
    rows = layer["rows"]
    number_row = layer.get("numberRow", [])

    pad_x = 18
    pad_y = 18
    gap_x = 8
    gap_y = 10
    toolbar_h = 60

    all_rows = [number_row] + rows
    num_rows = len(all_rows)

    key_h = 74
    kb_h = toolbar_h + pad_y * 2 + num_rows * key_h + (num_rows - 1) * gap_y

    # Outer Keyboard Glass Frame
    kb_rect = [top_x, top_y, top_x + kb_w, top_y + kb_h]
    draw.rounded_rectangle(
        kb_rect,
        radius=24,
        fill=(15, 23, 42),
        outline=(51, 65, 85),
        width=2,
    )

    # Toolbar Header & Icons with Circle Backgrounds
    draw_toolbar_icons(draw, top_x, top_y, kb_w)
    draw.line(
        [(top_x + pad_x, top_y + toolbar_h), (top_x + kb_w - pad_x, top_y + toolbar_h)],
        fill=(30, 41, 59),
        width=1,
    )

    # Keys Area
    usable_w = kb_w - (pad_x * 2)
    start_y = top_y + toolbar_h + pad_y

    # Fonts
    hint_font = ImageFont.truetype(mono_font_path, 14)
    label_font = ImageFont.truetype(inter_font_path, 20)
    space_font = ImageFont.truetype(inter_font_path, 16)

    for r_idx, row in enumerate(all_rows):
        if not row:
            continue

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
            action = k.get("action", {}).get("type")
            long_press = k.get("longPress", [])
            hint = long_press[0] if long_press else ""

            # Keycap colors
            if action == "enter":
                bg_color = (14, 165, 233)  # Sky blue accent for Enter key
                border_color = (56, 189, 248)
                text_color = (255, 255, 255)
            elif action or label in ["⇧", "⌫", "?123", "🌐"]:
                bg_color = (24, 32, 47)    # Special key background
                border_color = (45, 58, 78)
                text_color = (203, 213, 225)
            elif action == "space" or label == " ":
                bg_color = (30, 41, 59)
                border_color = (51, 65, 85)
                text_color = (148, 163, 184)
            else:
                bg_color = (30, 41, 59)    # Regular keycap
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

            # 1. Corner Hint (top-right of keycap)
            if hint and hint != label:
                hw = draw.textlength(hint, font=hint_font)
                hx = curr_x + kw - hw - 8
                hy = curr_y + 6
                draw.text((hx, hy), hint, fill=(148, 163, 184), font=hint_font)

            # 2. Main Key Label / Content
            if label and 0x2800 <= ord(label[0]) <= 0x28FF:
                cx = curr_x + (kw / 2)
                cy = curr_y + (kh / 2)
                draw_braille_cell(
                    draw=draw,
                    center_x=cx,
                    center_y=cy,
                    braille_char=label,
                    dot_radius=5.5,
                    spacing_x=14.0,
                    spacing_y=13.0,
                    active_color=(255, 255, 255),
                    inactive_color=(60, 75, 100),
                )
            elif action == "language_switch" or label == "🌐":
                draw_globe_icon(draw, curr_x + kw / 2, curr_y + kh / 2, text_color)
            elif action == "space" or label == " ":
                space_text = "◄  English (Braille (Unicode))  ►"
                stw = draw.textlength(space_text, font=space_font)
                stx = curr_x + (kw - stw) / 2
                sty = curr_y + (kh - 18) / 2
                draw.text((stx, sty), space_text, fill=(148, 163, 184), font=space_font)
            else:
                lw = draw.textlength(label, font=label_font)
                lx = curr_x + (kw - lw) / 2
                ly = curr_y + (kh - 22) / 2
                draw.text((lx, ly), label, fill=text_color, font=label_font)

            curr_x += kw + gap_x


def generate_layout_preview(
    layout_file: Path,
    output_path: Path,
    title: str,
    subtitle: str,
    bg_start: tuple,
    bg_end: tuple,
    accent_color: tuple,
    footer_text: str,
):
    """Generate 1080x900 showcase preview image rendering the full keyboard layout UI."""
    layout_data = json.loads(layout_file.read_text(encoding="utf-8"))

    width, height = 1080, 900
    canvas = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(canvas)

    # 1. Background Gradient
    for y in range(height):
        r = int(bg_start[0] + (bg_end[0] - bg_start[0]) * y / height)
        g = int(bg_start[1] + (bg_end[1] - bg_start[1]) * y / height)
        b = int(bg_start[2] + (bg_end[2] - bg_start[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 2. Load Fonts
    inter_path = FONTS_DIR / "inter.ttf"
    mono_path = FONTS_DIR / "jetbrains-mono.ttf"

    title_font = ImageFont.truetype(str(inter_path), 52)
    subtitle_font = ImageFont.truetype(str(inter_path), 22)
    footer_font = ImageFont.truetype(str(inter_path), 16)

    # 3. Header Title & Subtitle (Centered)
    title_w = draw.textlength(title, font=title_font)
    draw.text(((width - title_w) // 2, 40), title, fill=(255, 255, 255), font=title_font)

    sub_w = draw.textlength(subtitle, font=subtitle_font)
    draw.text(((width - sub_w) // 2, 108), subtitle, fill=(203, 213, 225), font=subtitle_font)

    # 4. Divider Line
    draw.line([(80, 150), (width - 80, 150)], fill=(51, 65, 85), width=2)

    # 5. Render Full Keyboard UI Mockup
    kb_w = 980
    kb_x = (width - kb_w) // 2
    kb_y = 175

    render_keyboard_mockup(
        layout_data=layout_data,
        draw=draw,
        top_x=kb_x,
        top_y=kb_y,
        kb_w=kb_w,
        inter_font_path=str(inter_path),
        mono_font_path=str(mono_path),
        accent_color=accent_color,
    )

    # 6. Footer Bar
    fw = draw.textlength(footer_text, font=footer_font)
    draw.text(((width - fw) // 2, 855), footer_text, fill=(148, 163, 184), font=footer_font)

    # Save JPEG
    canvas.save(output_path, "JPEG", quality=93)
    print(f"Successfully generated keyboard layout preview: {output_path.relative_to(ROOT)}", flush=True)


LAYOUT_CONFIGS = [
    {
        "layout_file": LAYOUTS_DIR / "braille.wmlayout.json",
        "output_grid": PREVIEWS_DIR / "braille-grid.jpg",
        "title": "Braille (Unicode)",
        "subtitle": "Types Unicode braille cells from QWERTY key positions",
        "bg_start": (15, 23, 42),      # Slate 900
        "bg_end": (12, 74, 110),       # Sky/Navy gradient
        "accent_color": (56, 189, 248), # Sky 400
        "footer_text": "Unicode Braille Patterns • Standard QWERTY Mapping • Full Keyboard Layout Spec",
    }
]


def main():
    PREVIEWS_DIR.mkdir(exist_ok=True)
    for cfg in LAYOUT_CONFIGS:
        if cfg["layout_file"].exists():
            generate_layout_preview(
                layout_file=cfg["layout_file"],
                output_path=cfg["output_grid"],
                title=cfg["title"],
                subtitle=cfg["subtitle"],
                bg_start=cfg["bg_start"],
                bg_end=cfg["bg_end"],
                accent_color=cfg["accent_color"],
                footer_text=cfg["footer_text"],
            )


if __name__ == "__main__":
    main()
