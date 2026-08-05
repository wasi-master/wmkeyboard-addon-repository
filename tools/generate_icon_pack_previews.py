#!/usr/bin/env python3
"""Standardized generator script for Icon Pack preview grid images."""

import io
import json
import zipfile
from pathlib import Path
import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PREVIEWS_DIR = ROOT / "previews"
ICONS_DIR = ROOT / "icons"
FONTS_DIR = ROOT / "fonts"

# 20 representative tools with labels and custom accent colors
FEATURED_TOOLS = [
    # Row 1
    ("tool.emoji", "Emoji", (245, 158, 11)),         # Amber
    ("tool.gif", "GIFs", (249, 115, 22)),           # Coral
    ("tool.sticker", "Stickers", (234, 179, 8)),     # Yellow-orange
    ("tool.voice", "Voice", (244, 63, 94)),          # Rose
    ("tool.translate", "Translate", (56, 189, 248)),  # Sky
    # Row 2
    ("tool.snippets", "Snippets", (45, 212, 191)),   # Mint/Teal
    ("tool.text_edit", "Text Editing", (168, 85, 247)), # Purple
    ("tool.undo", "Undo", (148, 163, 184)),          # Slate
    ("tool.redo", "Redo", (148, 163, 184)),          # Slate
    ("tool.themes", "Themes", (236, 72, 153)),       # Pink
    # Row 3
    ("tool.web_search", "Search", (6, 182, 212)),    # Cyan
    ("tool.image_search", "Images", (16, 185, 129)), # Emerald
    ("tool.clipboard", "Clipboard", (245, 158, 11)), # Amber
    ("tool.settings", "Settings", (203, 213, 225)),  # Light Slate
    ("tool.camera", "Camera", (239, 68, 68)),        # Red
    # Row 4
    ("tool.dictionary", "Dictionary", (99, 102, 241)), # Indigo
    ("tool.numpad", "Numpad", (59, 130, 246)),       # Blue
    ("tool.handwriting", "Handwriting", (139, 92, 246)), # Violet
    ("tool.flashlight", "Flashlight", (250, 204, 21)), # Yellow
    ("tool.calendar", "Calendar", (20, 184, 166)),   # Teal
]

ICON_PACK_CONFIGS = [
    {
        "id": "lucide",
        "name": "Lucide",
        "badge": "OUTLINE STYLE",
        "subtitle": "Clean 24px stroke-only vector icon set for WM Keyboard",
        "bg_start": (15, 23, 42),
        "bg_end": (12, 74, 110),
        "accent_color": (56, 189, 248),
        "output_grid": PREVIEWS_DIR / "lucide-grid.jpg",
    },
    {
        "id": "bootstrap-icons",
        "name": "Bootstrap Icons",
        "badge": "VECTOR FILL / STROKE",
        "subtitle": "Official Bootstrap UI vector icon collection for WM Keyboard",
        "bg_start": (15, 23, 42),
        "bg_end": (76, 29, 149),
        "accent_color": (192, 132, 252),
        "output_grid": PREVIEWS_DIR / "bootstrap-icons-grid.jpg",
    },
    {
        "id": "boxicons",
        "name": "Boxicons",
        "badge": "CLEAN GEOMETRIC",
        "subtitle": "High quality 24px vector icons with clean geometry",
        "bg_start": (15, 23, 42),
        "bg_end": (6, 78, 59),
        "accent_color": (52, 211, 153),
        "output_grid": PREVIEWS_DIR / "boxicons-grid.jpg",
    },
    {
        "id": "fontawesome",
        "name": "Font Awesome",
        "badge": "ICONIC SOLID",
        "subtitle": "Fonticons iconic solid vector icon set for WM Keyboard",
        "bg_start": (15, 23, 42),
        "bg_end": (124, 45, 18),
        "accent_color": (253, 186, 116),
        "output_grid": PREVIEWS_DIR / "fontawesome-grid.jpg",
    },
]


def render_svg_icon(svg_data: bytes, accent_color: tuple, size: int = 56) -> Image.Image | None:
    """Render raw SVG data to a colored PIL RGBA image."""
    try:
        # Open SVG using fitz
        doc = fitz.open("svg", svg_data)
        page = doc[0]
        # Render high-resolution pixmap
        pix = page.get_pixmap(dpi=300, alpha=True)
        raw_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
        
        # Resize maintaining aspect ratio
        raw_img.thumbnail((size, size), Image.Resampling.LANCZOS)
        
        # Extract alpha as mask
        _, _, _, alpha = raw_img.split()
        
        # Create solid color image with accent color
        colored = Image.new("RGBA", raw_img.size, accent_color + (255,))
        
        # Apply alpha mask
        out = Image.new("RGBA", raw_img.size, (0, 0, 0, 0))
        out.paste(colored, (0, 0), alpha)
        return out
    except Exception as e:
        print(f"Error rendering SVG icon: {e}", flush=True)
        return None


def generate_grid_preview(
    wmicons_path: Path,
    output_path: Path,
    title: str,
    subtitle: str,
    bg_start: tuple,
    bg_end: tuple,
    accent_color: tuple,
):
    """Generate 1080x900 showcase preview image for an icon pack."""
    width, height = 1080, 900
    canvas = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(canvas)

    # 1. Background Gradient
    for y in range(height):
        r = int(bg_start[0] + (bg_end[0] - bg_start[0]) * y / height)
        g = int(bg_start[1] + (bg_end[1] - bg_start[1]) * y / height)
        b = int(bg_start[2] + (bg_end[2] - bg_start[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 2. Fonts
    inter_path = FONTS_DIR / "inter.ttf"
    title_font = ImageFont.truetype(str(inter_path), 56)
    subtitle_font = ImageFont.truetype(str(inter_path), 24)
    label_font = ImageFont.truetype(str(inter_path), 15)
    footer_font = ImageFont.truetype(str(inter_path), 16)

    # 3. Title & Subtitle (Centered, matching emoji previews layout)
    title_w = draw.textlength(title, font=title_font)
    draw.text(((width - title_w) // 2, 55), title, fill=(255, 255, 255), font=title_font)

    sub_w = draw.textlength(subtitle, font=subtitle_font)
    draw.text(((width - sub_w) // 2, 130), subtitle, fill=(203, 213, 225), font=subtitle_font)

    # 4. Divider Line
    draw.line([(100, 180), (width - 100, 180)], fill=(51, 65, 85), width=2)

    # 6. Load icons from archive
    icon_svgs = {}
    with zipfile.ZipFile(wmicons_path) as z:
        for tool_slot, label, color in FEATURED_TOOLS:
            svg_filename = f"icons/{tool_slot}.svg"
            if svg_filename in z.namelist():
                icon_svgs[tool_slot] = z.read(svg_filename)

    # 7. Render 5x4 Card Grid
    cols = 5
    card_w, card_h = 166, 136
    gap_x, gap_y = 21, 20
    grid_w = cols * card_w + (cols - 1) * gap_x
    start_x = (width - grid_w) // 2
    start_y = 205

    for idx, (tool_slot, label, color) in enumerate(FEATURED_TOOLS):
        r_idx = idx // cols
        c_idx = idx % cols
        x = start_x + c_idx * (card_w + gap_x)
        y = start_y + r_idx * (card_h + gap_y)

        # Card container with subtle glass/dark fill & accent outline
        draw.rounded_rectangle(
            [x, y, x + card_w, y + card_h],
            radius=16,
            fill=(24, 32, 47),
            outline=(51, 65, 85),
            width=1,
        )

        # Inner subtle glow outline on top
        draw.rounded_rectangle(
            [x + 1, y + 1, x + card_w - 1, y + card_h - 1],
            radius=15,
            fill=None,
            outline=(30, 41, 59),
            width=1,
        )

        # Render Icon
        if tool_slot in icon_svgs:
            icon_img = render_svg_icon(icon_svgs[tool_slot], color, size=52)
            if icon_img:
                iw, ih = icon_img.size
                ix = x + (card_w - iw) // 2
                iy = y + 18 + (52 - ih) // 2
                canvas.paste(icon_img, (ix, iy), icon_img)

        # Draw Tool Label
        lw = draw.textlength(label, font=label_font)
        lx = x + (card_w - lw) // 2
        ly = y + card_h - 32
        draw.text((lx, ly), label, fill=(241, 245, 249), font=label_font)

    # 8. Footer Bar
    footer_text = "Vector SVG • Adaptive to Active Theme & Per-Tool Accents • 62 Tools & Key Glyphs"
    fw = draw.textlength(footer_text, font=footer_font)
    draw.text(((width - fw) // 2, 850), footer_text, fill=(148, 163, 184), font=footer_font)

    # Save PNG/JPEG
    canvas.save(output_path, "JPEG", quality=93)
    print(f"Successfully generated showcase grid preview: {output_path.relative_to(ROOT)}", flush=True)


def main():
    PREVIEWS_DIR.mkdir(exist_ok=True)
    for cfg in ICON_PACK_CONFIGS:
        wmicons_file = ICONS_DIR / f"{cfg['id']}.wmicons"
        if wmicons_file.exists():
            generate_grid_preview(
                wmicons_path=wmicons_file,
                output_path=cfg["output_grid"],
                title=cfg["name"],
                subtitle=cfg["subtitle"],
                bg_start=cfg["bg_start"],
                bg_end=cfg["bg_end"],
                accent_color=cfg["accent_color"],
            )
        else:
            print(f"Warning: {wmicons_file} not found!", flush=True)


if __name__ == "__main__":
    main()
