#!/usr/bin/env python3
"""Standardized generator script for Plugin showcase preview grid images."""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
PREVIEWS_DIR = ROOT / "previews"
FONTS_DIR = ROOT / "fonts"

INTER_PATH = str(FONTS_DIR / "inter.ttf")
MONO_PATH = str(FONTS_DIR / "jetbrains-mono.ttf")


def create_gradient_background(width: int, height: int, colors: list) -> Image.Image:
    """Creates a multi-stop vertical gradient background with ambient radial glows."""
    base = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(base)

    c0, c1 = colors[0], colors[1]
    for y in range(height):
        t = y / (height - 1)
        r = int(c0[0] + (c1[0] - c0[0]) * t)
        g = int(c0[1] + (c1[1] - c0[1]) * t)
        b = int(c0[2] + (c1[2] - c0[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    glow_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_overlay)

    if len(colors) > 2:
        glow1 = colors[2]
        glow_draw.ellipse([width * 0.4, -height * 0.2, width * 1.2, height * 0.7], fill=glow1)
    if len(colors) > 3:
        glow2 = colors[3]
        glow_draw.ellipse([-width * 0.2, height * 0.3, width * 0.6, height * 1.1], fill=glow2)

    glow_overlay = glow_overlay.filter(ImageFilter.GaussianBlur(radius=120))
    return Image.alpha_composite(base, glow_overlay)


def make_badge_pill(
    text: str,
    font: ImageFont.FreeTypeFont,
    text_color: tuple,
    fill_color: tuple,
    border_color: tuple,
    padding: tuple = (16, 8),
    radius: int = 12,
) -> Image.Image:
    """Creates a standalone badge pill image."""
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pw, ph = padding
    w = tw + pw * 2
    h = th + ph * 2

    pill = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pill)
    draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=fill_color, outline=border_color, width=1)
    draw.text((pw - bbox[0], ph - bbox[1]), text, fill=text_color, font=font)
    return pill


# -----------------------------------------------------------------------------
# 1. CIPHER TOOL PREVIEW
# -----------------------------------------------------------------------------
def generate_cipher_tool_preview():
    w, h = 1080, 900
    bg_colors = [
        (10, 15, 30),       # Deep slate navy
        (16, 37, 66),       # Cyan navy
        (56, 189, 248, 45), # Sky cyan top-right glow
        (16, 185, 129, 35), # Emerald bottom-left glow
    ]
    canvas = create_gradient_background(w, h, bg_colors)
    draw = ImageDraw.Draw(canvas)

    font_title = ImageFont.truetype(INTER_PATH, 42)
    font_sub = ImageFont.truetype(INTER_PATH, 19)
    font_badge = ImageFont.truetype(INTER_PATH, 14)
    font_label = ImageFont.truetype(INTER_PATH, 17)
    font_body = ImageFont.truetype(INTER_PATH, 18)
    font_mono = ImageFont.truetype(MONO_PATH, 22)
    font_mono_small = ImageFont.truetype(MONO_PATH, 16)

    # Header
    badge = make_badge_pill(
        "LUA PLUGIN  •  ENCRYPTION DEMO",
        font_badge,
        (56, 189, 248),
        (15, 23, 42, 230),
        (56, 189, 248, 120),
    )
    canvas.paste(badge, (60, 45), badge)

    draw.text((60, 95), "Cipher Tool", fill=(248, 250, 252), font=font_title)
    draw.text((60, 150), "Caesar & Vigenère ciphers — real-time text encryption right inside your keyboard", fill=(148, 163, 184), font=font_sub)

    # Main UI Card Container
    card_x, card_y, card_w, card_h = 60, 195, 960, 455
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=20,
        fill=(15, 23, 42, 235),
        outline=(51, 65, 85),
        width=2,
    )

    # Tabs
    tab_y = card_y + 20
    draw.rounded_rectangle([card_x + 20, tab_y, card_x + 180, tab_y + 40], radius=10, fill=(16, 185, 129, 230), outline=None)
    draw.text((card_x + 65, tab_y + 9), "Caesar", fill=(255, 255, 255), font=font_label)

    draw.rounded_rectangle([card_x + 195, tab_y, card_x + 365, tab_y + 40], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((card_x + 242, tab_y + 9), "Vigenère", fill=(148, 163, 184), font=font_label)

    # Input Fields
    in1_y = tab_y + 55
    draw.text((card_x + 25, in1_y), "Message", fill=(148, 163, 184), font=font_badge)
    draw.rounded_rectangle([card_x + 20, in1_y + 24, card_x + card_w - 20, in1_y + 70], radius=12, fill=(30, 41, 59), outline=(56, 189, 248, 180), width=2)
    draw.text((card_x + 36, in1_y + 35), "SECRET MEETING AT 9PM", fill=(248, 250, 252), font=font_body)

    in2_y = in1_y + 80
    draw.text((card_x + 25, in2_y), "Shift Amount", fill=(148, 163, 184), font=font_badge)
    draw.rounded_rectangle([card_x + 20, in2_y + 24, card_x + 220, in2_y + 68], radius=12, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((card_x + 36, in2_y + 34), "7", fill=(56, 189, 248), font=font_mono)

    # Buttons
    btn_y = in2_y + 24
    draw.rounded_rectangle([card_x + 240, btn_y, card_x + 440, btn_y + 44], radius=10, fill=(16, 185, 129), outline=None)
    draw.text((card_x + 305, btn_y + 10), "Encode", fill=(255, 255, 255), font=font_label)

    draw.rounded_rectangle([card_x + 455, btn_y, card_x + 635, btn_y + 44], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((card_x + 512, btn_y + 10), "Decode", fill=(226, 232, 240), font=font_label)

    # Transformation Result Box
    res_y = in2_y + 85
    draw.rounded_rectangle(
        [card_x + 20, res_y, card_x + card_w - 20, res_y + 115],
        radius=14,
        fill=(10, 18, 34),
        outline=(16, 185, 129, 140),
        width=1,
    )
    draw.text((card_x + 36, res_y + 14), "RESULT (CAESAR SHIFT +7)", fill=(16, 185, 129), font=font_badge)
    draw.text((card_x + 36, res_y + 44), "ZLJYLA TLLAPUN HA 9WT", fill=(52, 211, 153), font=font_mono)

    # Insert Button in result
    draw.rounded_rectangle([card_x + card_w - 150, res_y + 40, card_x + card_w - 36, res_y + 85], radius=8, fill=(16, 185, 129), outline=None)
    draw.text((card_x + card_w - 116, res_y + 51), "Insert", fill=(255, 255, 255), font=font_label)

    # Bottom Cards (2-column showcase)
    b_y = card_y + card_h + 20
    b_w = 468
    b_h = 180

    # Column 1: Vigenere Card
    draw.rounded_rectangle([card_x, b_y, card_x + b_w, b_y + b_h], radius=16, fill=(15, 23, 42, 220), outline=(51, 65, 85))
    badge_v = make_badge_pill("VIGENÈRE CIPHER", font_badge, (192, 132, 252), (30, 41, 59), (192, 132, 252, 100))
    canvas.paste(badge_v, (card_x + 20, b_y + 20), badge_v)
    draw.text((card_x + 20, b_y + 65), "Keyword: LEMON", fill=(148, 163, 184), font=font_sub)
    draw.text((card_x + 20, b_y + 98), "ATTACK AT DAWN", fill=(226, 232, 240), font=font_mono_small)
    draw.text((card_x + 20, b_y + 128), "→ LXFOPV EF RNHR", fill=(192, 132, 252), font=font_mono_small)

    # Column 2: Architecture Card
    draw.rounded_rectangle([card_x + b_w + 24, b_y, card_x + card_w, b_y + b_h], radius=16, fill=(15, 23, 42, 220), outline=(51, 65, 85))
    badge_a = make_badge_pill("ARCHITECTURE", font_badge, (56, 189, 248), (30, 41, 59), (56, 189, 248, 100))
    canvas.paste(badge_a, (card_x + b_w + 44, b_y + 20), badge_a)
    draw.text((card_x + b_w + 44, b_y + 65), "Lua 5.4 Sandbox", fill=(248, 250, 252), font=font_body)
    draw.text((card_x + b_w + 44, b_y + 98), "• Zero network permissions required", fill=(148, 163, 184), font=font_sub)
    draw.text((card_x + b_w + 44, b_y + 128), "• Direct 1-tap insert into any app", fill=(148, 163, 184), font=font_sub)

    out_file = PREVIEWS_DIR / "cipher-tool-grid.jpg"
    canvas.convert("RGB").save(out_file, "JPEG", quality=95)
    print(f"Generated {out_file.relative_to(ROOT)}")


# -----------------------------------------------------------------------------
# 2. UI KITCHEN SINK PREVIEW
# -----------------------------------------------------------------------------
def generate_ui_kitchen_sink_preview():
    w, h = 1080, 900
    bg_colors = [
        (15, 23, 42),       # Deep slate
        (49, 16, 74),       # Deep purple
        (192, 132, 252, 45),# Purple top-right glow
        (236, 72, 153, 35), # Pink bottom-left glow
    ]
    canvas = create_gradient_background(w, h, bg_colors)
    draw = ImageDraw.Draw(canvas)

    font_title = ImageFont.truetype(INTER_PATH, 42)
    font_sub = ImageFont.truetype(INTER_PATH, 19)
    font_badge = ImageFont.truetype(INTER_PATH, 14)
    font_label = ImageFont.truetype(INTER_PATH, 17)
    font_body = ImageFont.truetype(INTER_PATH, 18)
    font_mono = ImageFont.truetype(MONO_PATH, 16)

    # Header
    badge = make_badge_pill(
        "LUA PLUGIN  •  WIDGET GALLERY & REFERENCE",
        font_badge,
        (192, 132, 252),
        (15, 23, 42, 230),
        (192, 132, 252, 120),
    )
    canvas.paste(badge, (60, 45), badge)

    draw.text((60, 95), "UI Kitchen Sink", fill=(248, 250, 252), font=font_title)
    draw.text((60, 150), "Every plugin widget, layout row/column, and event listener in one reference", fill=(148, 163, 184), font=font_sub)

    card_x, card_y, card_w, card_h = 60, 195, 960, 655
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=20,
        fill=(15, 23, 42, 235),
        outline=(51, 65, 85),
        width=2,
    )

    # Main Tab Bar Mockup
    tab_y = card_y + 20
    tabs = [
        ("Text", False),
        ("Controls", True),
        ("Input", False),
        ("Layout", False),
        ("Events", False),
    ]
    tx = card_x + 20
    for name, is_active in tabs:
        tw = 160
        if is_active:
            draw.rounded_rectangle([tx, tab_y, tx + tw, tab_y + 40], radius=10, fill=(147, 51, 234), outline=None)
            draw.text((tx + 45, tab_y + 9), name, fill=(255, 255, 255), font=font_label)
        else:
            draw.rounded_rectangle([tx, tab_y, tx + tw, tab_y + 40], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
            draw.text((tx + 55, tab_y + 9), name, fill=(148, 163, 184), font=font_label)
        tx += tw + 15

    # 4 Inner Component Panels Grid
    grid_y = tab_y + 60
    col_w = 445
    col_h = 250

    # Panel 1: Buttons & Toggles
    draw.rounded_rectangle([card_x + 20, grid_y, card_x + 20 + col_w, grid_y + col_h], radius=14, fill=(24, 33, 52), outline=(51, 65, 85))
    draw.text((card_x + 40, grid_y + 16), "BUTTONS & TOGGLES", fill=(192, 132, 252), font=font_badge)

    draw.rounded_rectangle([card_x + 40, grid_y + 48, card_x + 230, grid_y + 92], radius=10, fill=(147, 51, 234), outline=None)
    draw.text((card_x + 62, grid_y + 59), "Primary Button", fill=(255, 255, 255), font=font_label)

    draw.rounded_rectangle([card_x + 245, grid_y + 48, card_x + 430, grid_y + 92], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((card_x + 262, grid_y + 59), "Secondary Button", fill=(226, 232, 240), font=font_label)

    # Toggle Row
    draw.rounded_rectangle([card_x + 40, grid_y + 110, card_x + 430, grid_y + 158], radius=10, fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((card_x + 60, grid_y + 124), "Demo Toggle State", fill=(226, 232, 240), font=font_body)

    # Toggle Switch Pill (ON)
    draw.rounded_rectangle([card_x + 350, grid_y + 120, card_x + 410, grid_y + 148], radius=14, fill=(147, 51, 234), outline=None)
    draw.ellipse([card_x + 382, grid_y + 122, card_x + 408, grid_y + 146], fill=(255, 255, 255))

    draw.text((card_x + 40, grid_y + 175), "Status: The toggle is ON", fill=(192, 132, 252), font=font_sub)

    # Panel 2: Inputs & Rows
    draw.rounded_rectangle([card_x + 495, grid_y, card_x + 495 + col_w, grid_y + col_h], radius=14, fill=(24, 33, 52), outline=(51, 65, 85))
    draw.text((card_x + 515, grid_y + 16), "TEXT INPUTS & FLEX ROWS", fill=(56, 189, 248), font=font_badge)

    draw.rounded_rectangle([card_x + 515, grid_y + 48, card_x + 915, grid_y + 92], radius=10, fill=(15, 23, 42), outline=(56, 189, 248, 150))
    draw.text((card_x + 530, grid_y + 59), "Type or paste here...", fill=(100, 116, 139), font=font_body)

    # Row with 3 buttons
    rw = 124
    rx = card_x + 515
    for lbl in ["One", "Two", "Three"]:
        draw.rounded_rectangle([rx, grid_y + 110, rx + rw, grid_y + 154], radius=8, fill=(30, 41, 59), outline=(51, 65, 85))
        draw.text((rx + 42, grid_y + 122), lbl, fill=(226, 232, 240), font=font_label)
        rx += rw + 13

    draw.text((card_x + 515, grid_y + 175), "ui.row splits width evenly across children", fill=(148, 163, 184), font=font_sub)

    # Lower Panel: Live Event Stream Terminal
    term_y = grid_y + col_h + 20
    draw.rounded_rectangle([card_x + 20, term_y, card_x + card_w - 20, term_y + 245], radius=14, fill=(10, 15, 28), outline=(147, 51, 234, 150), width=2)

    draw.text((card_x + 40, term_y + 16), "REAL-TIME EVENT LOG (on_event)", fill=(192, 132, 252), font=font_badge)

    events = [
        "input box = \"WM Keyboard plugin sandbox\"",
        "toggle demo_toggle = true",
        "click primary",
        "tab sink #2",
        "click toggle_enabled",
    ]
    ey = term_y + 48
    for ev in events:
        draw.text((card_x + 40, ey), f"• {ev}", fill=(226, 232, 240), font=font_mono)
        ey += 32

    out_file = PREVIEWS_DIR / "ui-kitchen-sink-grid.jpg"
    canvas.convert("RGB").save(out_file, "JPEG", quality=95)
    print(f"Generated {out_file.relative_to(ROOT)}")


# -----------------------------------------------------------------------------
# 3. TODO LIST PREVIEW
# -----------------------------------------------------------------------------
def generate_todo_list_preview():
    w, h = 1080, 900
    bg_colors = [
        (13, 22, 38),       # Dark slate
        (6, 78, 59),        # Emerald green
        (45, 212, 191, 45), # Teal top-right glow
        (16, 185, 129, 35), # Mint bottom-left glow
    ]
    canvas = create_gradient_background(w, h, bg_colors)
    draw = ImageDraw.Draw(canvas)

    font_title = ImageFont.truetype(INTER_PATH, 42)
    font_sub = ImageFont.truetype(INTER_PATH, 19)
    font_badge = ImageFont.truetype(INTER_PATH, 14)
    font_label = ImageFont.truetype(INTER_PATH, 17)
    font_body = ImageFont.truetype(INTER_PATH, 18)
    font_mono = ImageFont.truetype(MONO_PATH, 16)

    # Header
    badge = make_badge_pill(
        "LUA PLUGIN  •  PERSISTENT STORAGE DEMO",
        font_badge,
        (45, 212, 191),
        (15, 23, 42, 230),
        (45, 212, 191, 120),
    )
    canvas.paste(badge, (60, 45), badge)

    draw.text((60, 95), "Todo List", fill=(248, 250, 252), font=font_title)
    draw.text((60, 150), "A checklist that remembers itself — demonstrating wm.storage local persistence", fill=(148, 163, 184), font=font_sub)

    card_x, card_y, card_w, card_h = 60, 195, 960, 655
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=20,
        fill=(15, 23, 42, 235),
        outline=(51, 65, 85),
        width=2,
    )

    # Add item row mockup
    add_y = card_y + 25
    draw.rounded_rectangle([card_x + 20, add_y, card_x + 720, add_y + 48], radius=10, fill=(30, 41, 59), outline=(45, 212, 191, 150))
    draw.text((card_x + 36, add_y + 14), "Buy coffee & matcha", fill=(248, 250, 252), font=font_body)

    draw.rounded_rectangle([card_x + 735, add_y, card_x + card_w - 20, add_y + 48], radius=10, fill=(13, 148, 136), outline=None)
    draw.text((card_x + 798, add_y + 14), "Add", fill=(255, 255, 255), font=font_label)

    # Divider
    div_y = add_y + 68
    draw.line([(card_x + 20, div_y), (card_x + card_w - 20, div_y)], fill=(51, 65, 85), width=1)

    # Items Stack
    items = [
        ("Finish WM Keyboard Lua plugin guide", True),
        ("Test local storage quota limits", False),
        ("Export repo manifest with build_index.py", True),
        ("Publish plugin preview images to repository", False),
    ]

    iy = div_y + 20
    for text, is_done in items:
        draw.rounded_rectangle([card_x + 20, iy, card_x + card_w - 20, iy + 56], radius=12, fill=(24, 33, 52), outline=(51, 65, 85))

        if is_done:
            # Checked Box
            draw.rounded_rectangle([card_x + 36, iy + 14, card_x + 64, iy + 42], radius=6, fill=(13, 148, 136), outline=None)
            draw.text((card_x + 42, iy + 17), "✓", fill=(255, 255, 255), font=font_label)
            draw.text((card_x + 80, iy + 16), text, fill=(100, 116, 139), font=font_body)
            # Strike-through line
            t_len = draw.textlength(text, font=font_body)
            draw.line([(card_x + 80, iy + 28), (card_x + 80 + t_len, iy + 28)], fill=(100, 116, 139), width=2)
        else:
            # Unchecked Box
            draw.rounded_rectangle([card_x + 36, iy + 14, card_x + 64, iy + 42], radius=6, fill=(30, 41, 59), outline=(45, 212, 191), width=1)
            draw.text((card_x + 80, iy + 16), text, fill=(248, 250, 252), font=font_body)

        iy += 68

    # Status Bar
    stat_y = iy + 10
    draw.text((card_x + 25, stat_y + 10), "2 of 4 items left", fill=(148, 163, 184), font=font_sub)

    draw.rounded_rectangle([card_x + card_w - 200, stat_y, card_x + card_w - 20, stat_y + 44], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((card_x + card_w - 165, stat_y + 11), "Clear finished", fill=(226, 232, 240), font=font_label)

    # Architecture Bottom Box
    arch_y = stat_y + 70
    draw.rounded_rectangle([card_x + 20, arch_y, card_x + card_w - 20, arch_y + 120], radius=14, fill=(10, 18, 30), outline=(45, 212, 191, 140), width=2)
    draw.text((card_x + 40, arch_y + 16), "STORAGE ARCHITECTURE (wm.storage)", fill=(45, 212, 191), font=font_badge)
    draw.text((card_x + 40, arch_y + 46), "wm.storage.get(\"items\")  ↔  wm.storage.set(\"items\", json)", fill=(45, 212, 191), font=font_mono)
    draw.text((card_x + 40, arch_y + 80), "• 100% On-Device  • Persists across app restarts  • Zero permissions", fill=(148, 163, 184), font=font_sub)

    out_file = PREVIEWS_DIR / "todo-list-grid.jpg"
    canvas.convert("RGB").save(out_file, "JPEG", quality=95)
    print(f"Generated {out_file.relative_to(ROOT)}")


# -----------------------------------------------------------------------------
# 4. TEXT TOOLS PREVIEW
# -----------------------------------------------------------------------------
def generate_text_tools_preview():
    w, h = 1080, 900
    bg_colors = [
        (15, 23, 42),       # Dark slate
        (30, 58, 138),      # Deep blue
        (56, 189, 248, 45), # Sky blue top-right glow
        (249, 115, 22, 30), # Coral bottom-left glow
    ]
    canvas = create_gradient_background(w, h, bg_colors)
    draw = ImageDraw.Draw(canvas)

    font_title = ImageFont.truetype(INTER_PATH, 42)
    font_sub = ImageFont.truetype(INTER_PATH, 19)
    font_badge = ImageFont.truetype(INTER_PATH, 14)
    font_label = ImageFont.truetype(INTER_PATH, 17)
    font_body = ImageFont.truetype(INTER_PATH, 18)
    font_mono = ImageFont.truetype(MONO_PATH, 18)

    # Header
    badge = make_badge_pill(
        "LUA PLUGIN  •  MULTI-FUNCTION TEXT UTILITY",
        font_badge,
        (56, 189, 248),
        (15, 23, 42, 230),
        (56, 189, 248, 120),
    )
    canvas.paste(badge, (60, 45), badge)

    draw.text((60, 95), "Text Tools", fill=(248, 250, 252), font=font_title)
    draw.text((60, 150), "Change case, encode Base64/Hex/URL, and count words directly on keyboard", fill=(148, 163, 184), font=font_sub)

    card_x, card_y, card_w, card_h = 60, 195, 960, 655
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=20,
        fill=(15, 23, 42, 235),
        outline=(51, 65, 85),
        width=2,
    )

    # Input Box
    in_y = card_y + 20
    draw.text((card_x + 25, in_y), "Text Input", fill=(148, 163, 184), font=font_badge)
    draw.rounded_rectangle([card_x + 20, in_y + 24, card_x + card_w - 20, in_y + 70], radius=12, fill=(30, 41, 59), outline=(56, 189, 248, 180), width=2)
    draw.text((card_x + 36, in_y + 35), "WM Keyboard 2026 Release", fill=(248, 250, 252), font=font_body)

    # Tabs
    tab_y = in_y + 85
    tabs = [("Case", False), ("Encode", True), ("Count", False)]
    tx = card_x + 20
    for name, is_active in tabs:
        tw = 160
        if is_active:
            draw.rounded_rectangle([tx, tab_y, tx + tw, tab_y + 40], radius=10, fill=(2, 132, 199), outline=None)
            draw.text((tx + 50, tab_y + 9), name, fill=(255, 255, 255), font=font_label)
        else:
            draw.rounded_rectangle([tx, tab_y, tx + tw, tab_y + 40], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
            draw.text((tx + 55, tab_y + 9), name, fill=(148, 163, 184), font=font_label)
        tx += tw + 15

    # Encode Actions Grid
    act_y = tab_y + 55
    btn_w = 445
    btn_h = 44

    # Row 1: Base64
    draw.rounded_rectangle([card_x + 20, act_y, card_x + 20 + btn_w, act_y + btn_h], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((card_x + 205, act_y + 11), "Base64", fill=(248, 250, 252), font=font_label)

    draw.rounded_rectangle([card_x + 495, act_y, card_x + 495 + btn_w, act_y + btn_h], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((card_x + 670, act_y + 11), "un-Base64", fill=(248, 250, 252), font=font_label)

    # Row 2: Hex
    act_y2 = act_y + 56
    draw.rounded_rectangle([card_x + 20, act_y2, card_x + 20 + btn_w, act_y2 + btn_h], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((card_x + 215, act_y2 + 11), "Hex", fill=(248, 250, 252), font=font_label)

    draw.rounded_rectangle([card_x + 495, act_y2, card_x + 495 + btn_w, act_y2 + btn_h], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((card_x + 680, act_y2 + 11), "un-Hex", fill=(248, 250, 252), font=font_label)

    # Row 3: URL
    act_y3 = act_y2 + 56
    draw.rounded_rectangle([card_x + 20, act_y3, card_x + 20 + btn_w, act_y3 + btn_h], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((card_x + 215, act_y3 + 11), "URL", fill=(248, 250, 252), font=font_label)

    draw.rounded_rectangle([card_x + 495, act_y3, card_x + 495 + btn_w, act_y3 + btn_h], radius=10, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.text((card_x + 680, act_y3 + 11), "un-URL", fill=(248, 250, 252), font=font_label)

    # Result Block
    res_y = act_y3 + 68
    draw.rounded_rectangle([card_x + 20, res_y, card_x + card_w - 20, res_y + 110], radius=14, fill=(10, 18, 34), outline=(56, 189, 248, 150), width=2)
    draw.text((card_x + 36, res_y + 14), "RESULT (BASE64 ENCODED)", fill=(56, 189, 248), font=font_badge)
    draw.text((card_x + 36, res_y + 44), "V00gS2V5Ym9hcmQgMjAyNiBSZWxlYXNl", fill=(56, 189, 248), font=font_mono)

    draw.rounded_rectangle([card_x + card_w - 150, res_y + 38, card_x + card_w - 36, res_y + 82], radius=8, fill=(2, 132, 199), outline=None)
    draw.text((card_x + card_w - 116, res_y + 49), "Insert", fill=(255, 255, 255), font=font_label)

    # Case & Stats Showcase Cards
    b_y = res_y + 125
    b_w = 445
    b_h = 100

    draw.rounded_rectangle([card_x + 20, b_y, card_x + 20 + b_w, b_y + b_h], radius=14, fill=(24, 33, 52), outline=(51, 65, 85))
    draw.text((card_x + 36, b_y + 14), "CASE CONVERSION", fill=(148, 163, 184), font=font_badge)
    draw.text((card_x + 36, b_y + 42), "UPPER  •  lower  •  Title Case  •  esreveR", fill=(248, 250, 252), font=font_body)

    draw.rounded_rectangle([card_x + 495, b_y, card_x + 495 + b_w, b_y + b_h], radius=14, fill=(24, 33, 52), outline=(51, 65, 85))
    draw.text((card_x + 511, b_y + 14), "TEXT STATISTICS", fill=(148, 163, 184), font=font_badge)
    draw.text((card_x + 511, b_y + 42), "24 chars  •  21 letters  •  4 words  •  1 line", fill=(248, 250, 252), font=font_body)

    out_file = PREVIEWS_DIR / "text-tools-grid.jpg"
    canvas.convert("RGB").save(out_file, "JPEG", quality=95)
    print(f"Generated {out_file.relative_to(ROOT)}")


def main():
    PREVIEWS_DIR.mkdir(exist_ok=True)
    generate_cipher_tool_preview()
    generate_ui_kitchen_sink_preview()
    generate_todo_list_preview()
    generate_text_tools_preview()


if __name__ == "__main__":
    main()
