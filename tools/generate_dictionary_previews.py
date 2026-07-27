#!/usr/bin/env python3
"""Generate beautiful, attractive preview images for Developer and Slang Dictionaries."""

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def create_gradient_background(width, height, colors):
    """Creates a smooth multi-stop linear/radial gradient background."""
    base = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(base)
    
    # Vertical gradient base
    c0, c1, c2 = colors[0], colors[1], colors[2]
    for y in range(height):
        t = y / (height - 1)
        if t < 0.5:
            factor = t * 2
            r = int(c0[0] + (c1[0] - c0[0]) * factor)
            g = int(c0[1] + (c1[1] - c0[1]) * factor)
            b = int(c0[2] + (c1[2] - c0[2]) * factor)
        else:
            factor = (t - 0.5) * 2
            r = int(c1[0] + (c2[0] - c1[0]) * factor)
            g = int(c1[1] + (c2[1] - c1[1]) * factor)
            b = int(c2[0] + (c2[2] - c1[2]) * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
        
    # Add subtle radial glowing spots
    glow_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_overlay)
    
    if len(colors) > 3:
        glow_color = colors[3]
        # Radial glow top-right
        glow_draw.ellipse([width * 0.35, -height * 0.2, width * 1.2, height * 0.6], fill=glow_color)
        # Radial glow bottom-left
        glow_draw.ellipse([-width * 0.2, height * 0.35, width * 0.65, height * 1.15], fill=colors[4] if len(colors) > 4 else glow_color)
        glow_overlay = glow_overlay.filter(ImageFilter.GaussianBlur(radius=140))
        
    return Image.alpha_composite(base, glow_overlay)

def add_grid_pattern(img, grid_size=40, line_color=(255, 255, 255, 12)):
    """Draws a subtle tech grid pattern overlay."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    for x in range(0, w, grid_size):
        draw.line([(x, 0), (x, h)], fill=line_color, width=1)
    for y in range(0, h, grid_size):
        draw.line([(0, y), (w, y)], fill=line_color, width=1)
    return Image.alpha_composite(img, overlay)

def make_word_pill(text, font, text_color, fill_color, stroke_color, stroke_width=2, padding=(24, 12), radius=16, angle=0):
    """Creates a rendered word pill image with optional rotation."""
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    pw, ph = padding
    w = int(tw + pw * 2) + stroke_width * 4
    h = int(th + ph * 2) + stroke_width * 4
    
    pill_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pill_img)
    
    rect = [stroke_width * 2, stroke_width * 2, w - stroke_width * 2, h - stroke_width * 2]
    
    if fill_color:
        draw.rounded_rectangle(rect, radius=radius, fill=fill_color, outline=stroke_color, width=stroke_width)
    
    tx = (w - tw) // 2 - bbox[0]
    ty = (h - th) // 2 - bbox[1]
    draw.text((tx, ty), text, fill=text_color, font=font)
    
    if angle != 0:
        pill_img = pill_img.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        
    return pill_img

def generate_developer_preview():
    scale = 2
    w, h = 720 * scale, 633 * scale
    
    bg_colors = [
        (10, 15, 28),       # Deep slate base #0A0F1C
        (15, 23, 42),       # Slate 900 #0F172A
        (20, 30, 52),       # Dark Slate Navy
        (14, 165, 233, 45), # Cyan glow top right
        (99, 102, 241, 40)  # Indigo glow bottom left
    ]
    
    canvas = create_gradient_background(w, h, bg_colors)
    canvas = add_grid_pattern(canvas, grid_size=45 * scale, line_color=(56, 189, 248, 15))
    
    inter_bold = ImageFont.truetype("fonts/inter.ttf", 36 * scale)
    inter_semi = ImageFont.truetype("fonts/inter.ttf", 18 * scale)
    mono_bold = ImageFont.truetype("fonts/jetbrains-mono.ttf", 22 * scale)
    mono_hero = ImageFont.truetype("fonts/jetbrains-mono.ttf", 28 * scale)
    mono_small = ImageFont.truetype("fonts/jetbrains-mono.ttf", 15 * scale)
    mono_bg = ImageFont.truetype("fonts/jetbrains-mono.ttf", 20 * scale)
    
    # -------------------------------------------------------------
    # 1. HEADER SECTION
    # -------------------------------------------------------------
    header_box = Image.new("RGBA", (w - 80 * scale, 145 * scale), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(header_box)
    
    h_draw.rounded_rectangle(
        [0, 0, w - 80 * scale, 135 * scale],
        radius=20 * scale,
        fill=(15, 23, 42, 215),
        outline=(56, 189, 248, 90),
        width=2 * scale
    )
    
    badge_img = make_word_pill(
        "DICTIONARY  •  DEV EN", 
        mono_small, 
        text_color=(56, 189, 248, 255), 
        fill_color=(14, 165, 233, 35), 
        stroke_color=(56, 189, 248, 140), 
        stroke_width=1 * scale,
        padding=(14 * scale, 5 * scale),
        radius=8 * scale
    )
    header_box.paste(badge_img, (30 * scale, 18 * scale), badge_img)
    
    title_text = "Developer Dictionary"
    h_draw.text((30 * scale, 52 * scale), title_text, fill=(248, 250, 252, 255), font=inter_bold)
    
    sub_text = "1,450+ programming terms, syntax keywords, frameworks & tools"
    h_draw.text((30 * scale, 98 * scale), sub_text, fill=(148, 163, 184, 255), font=inter_semi)
    
    canvas.paste(header_box, (40 * scale, 35 * scale), header_box)
    
    # -------------------------------------------------------------
    # 2. SCATTERED BACKGROUND WORDS (Layer 1: Ambient text)
    # -------------------------------------------------------------
    bg_words = [
        ("const", 80, 215, -12, (148, 163, 184, 55)),
        ("return", 550, 210, 10, (148, 163, 184, 50)),
        ("function", 320, 198, -5, (56, 189, 248, 45)),
        ("struct", 60, 360, 15, (148, 163, 184, 50)),
        ("interface", 520, 340, -8, (167, 139, 250, 50)),
        ("pipeline", 240, 540, 6, (148, 163, 184, 40)),
        ("middleware", 400, 535, -10, (52, 211, 153, 45)),
        ("boolean", 580, 525, 12, (148, 163, 184, 45)),
        ("endpoint", 50, 530, -14, (148, 163, 184, 40)),
        ("callback", 350, 390, 8, (148, 163, 184, 40)),
    ]
    
    for word, x_p, y_p, ang, col in bg_words:
        pill = make_word_pill(
            word, mono_bg, text_color=col, fill_color=None, stroke_color=None, angle=ang
        )
        canvas.paste(pill, (x_p * scale, y_p * scale), pill)

    # -------------------------------------------------------------
    # 3. MIDGROUND & FOREGROUND SCATTERED WORDS / PILLS
    # -------------------------------------------------------------
    hero_pills = [
        ("async / await", 50, 255, -6, mono_hero, (56, 189, 248, 255), (15, 23, 42, 240), (56, 189, 248, 220)),
        ("kubernetes", 310, 250, 4, mono_hero, (52, 211, 153, 255), (15, 23, 42, 240), (52, 211, 153, 220)),
        ("typescript", 500, 265, -4, mono_bold, (167, 139, 250, 255), (30, 27, 75, 240), (167, 139, 250, 200)),
        ("docker", 140, 325, 5, mono_hero, (56, 189, 248, 255), (14, 116, 144, 210), (56, 189, 248, 255)),
        ("postgres", 350, 315, -5, mono_bold, (251, 191, 36, 255), (15, 23, 42, 240), (251, 191, 36, 200)),
        ("graphql", 540, 365, 7, mono_bold, (244, 114, 182, 255), (15, 23, 42, 240), (244, 114, 182, 200)),
        ("git commit", 40, 405, -4, mono_hero, (52, 211, 153, 255), (6, 78, 59, 220), (52, 211, 153, 255)),
        ("microservice", 250, 395, 3, mono_bold, (56, 189, 248, 255), (15, 23, 42, 240), (56, 189, 248, 180)),
        ("refactor", 480, 435, -6, mono_hero, (167, 139, 250, 255), (88, 28, 135, 220), (167, 139, 250, 255)),
        ("localhost", 90, 480, 5, mono_bold, (251, 191, 36, 255), (15, 23, 42, 240), (251, 191, 36, 180)),
        ("payload", 290, 470, -3, mono_bold, (52, 211, 153, 255), (15, 23, 42, 240), (52, 211, 153, 180)),
        ("lambda", 470, 495, 5, mono_bold, (56, 189, 248, 255), (15, 23, 42, 240), (56, 189, 248, 180)),
        ("webpack", 220, 535, -5, mono_bold, (244, 114, 182, 255), (15, 23, 42, 240), (244, 114, 182, 180)),
    ]
    
    for text, x, y, ang, font, txt_col, bg_col, brd_col in hero_pills:
        pill = make_word_pill(
            text, 
            font, 
            text_color=txt_col, 
            fill_color=bg_col, 
            stroke_color=brd_col,
            stroke_width=2 * scale,
            padding=(20 * scale, 10 * scale),
            radius=14 * scale,
            angle=ang
        )
        canvas.paste(pill, (x * scale, y * scale), pill)

    # -------------------------------------------------------------
    # 4. FOOTER TAGLINE
    # -------------------------------------------------------------
    footer_draw = ImageDraw.Draw(canvas)
    footer_text = "Instant Auto-Completion & Code Suggestions for WM Keyboard"
    f_w = footer_draw.textlength(footer_text, font=inter_semi)
    footer_draw.text(((w - f_w) // 2, h - 40 * scale), footer_text, fill=(148, 163, 184, 255), font=inter_semi)

    final_img = canvas.resize((720, 633), Image.Resampling.LANCZOS).convert("RGB")
    final_img.save("previews/en-developer.png", "PNG")
    print("Generated previews/en-developer.png")

def generate_slang_preview():
    scale = 2
    w, h = 720 * scale, 633 * scale
    
    bg_colors = [
        (18, 9, 36),        # Deep dark violet
        (34, 14, 61),       # Deep indigo purple
        (26, 10, 50),       # Dark plum
        (236, 72, 153, 60),  # Hot pink radial glow top right
        (168, 85, 247, 55)   # Neon violet glow bottom left
    ]
    
    canvas = create_gradient_background(w, h, bg_colors)
    
    inter_bold = ImageFont.truetype("fonts/inter.ttf", 36 * scale)
    inter_semi = ImageFont.truetype("fonts/inter.ttf", 18 * scale)
    press_start = ImageFont.truetype("fonts/press-start-2p.ttf", 13 * scale)
    mono_bold = ImageFont.truetype("fonts/jetbrains-mono.ttf", 22 * scale)
    mono_hero = ImageFont.truetype("fonts/jetbrains-mono.ttf", 28 * scale)
    mono_small = ImageFont.truetype("fonts/jetbrains-mono.ttf", 15 * scale)
    mono_bg = ImageFont.truetype("fonts/jetbrains-mono.ttf", 20 * scale)
    
    # -------------------------------------------------------------
    # 1. HEADER SECTION
    # -------------------------------------------------------------
    header_box = Image.new("RGBA", (w - 80 * scale, 145 * scale), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(header_box)
    
    h_draw.rounded_rectangle(
        [0, 0, w - 80 * scale, 135 * scale],
        radius=20 * scale,
        fill=(24, 10, 48, 220),
        outline=(236, 72, 153, 110),
        width=2 * scale
    )
    
    badge_img = make_word_pill(
        "DICTIONARY  •  SLANG & URBAN", 
        mono_small, 
        text_color=(244, 114, 182, 255), 
        fill_color=(236, 72, 153, 40), 
        stroke_color=(244, 114, 182, 150), 
        stroke_width=1 * scale,
        padding=(14 * scale, 5 * scale),
        radius=8 * scale
    )
    header_box.paste(badge_img, (30 * scale, 18 * scale), badge_img)
    
    title_text = "Internet Slang Dictionary"
    h_draw.text((30 * scale, 52 * scale), title_text, fill=(253, 242, 248, 255), font=inter_bold)
    
    sub_text = "500+ Gen Z, Gen Alpha, Twitch emotes, TikTok trends & brainrot"
    h_draw.text((30 * scale, 98 * scale), sub_text, fill=(216, 180, 254, 255), font=inter_semi)
    
    canvas.paste(header_box, (40 * scale, 35 * scale), header_box)
    
    # -------------------------------------------------------------
    # 2. SCATTERED BACKGROUND WORDS (Layer 1)
    # -------------------------------------------------------------
    bg_words = [
        ("afk", 90, 215, -15, (216, 180, 254, 65)),
        ("brb", 580, 210, 12, (244, 114, 182, 55)),
        ("tbh", 350, 198, -6, (168, 85, 247, 50)),
        ("ngl", 60, 360, 14, (216, 180, 254, 55)),
        ("smh", 550, 340, -10, (244, 114, 182, 55)),
        ("oof", 220, 530, 8, (216, 180, 254, 45)),
        ("uwu", 420, 525, -12, (244, 114, 182, 55)),
        ("bet", 590, 520, 10, (168, 85, 247, 50)),
        ("cap", 50, 530, -10, (216, 180, 254, 45)),
    ]
    
    for word, x_p, y_p, ang, col in bg_words:
        pill = make_word_pill(
            word, mono_bg, text_color=col, fill_color=None, stroke_color=None, angle=ang
        )
        canvas.paste(pill, (x_p * scale, y_p * scale), pill)

    # -------------------------------------------------------------
    # 3. MIDGROUND & FOREGROUND SLANG WORDS / PILLS
    # -------------------------------------------------------------
    hero_pills = [
        ("rizz", 60, 250, -8, mono_hero, (255, 255, 255, 255), (219, 39, 119, 235), (244, 114, 182, 255)),
        ("skibidi", 210, 245, 5, mono_hero, (34, 211, 238, 255), (15, 23, 42, 240), (34, 211, 238, 220)),
        ("brainrot", 440, 255, -5, mono_hero, (250, 204, 21, 255), (34, 14, 61, 240), (250, 204, 21, 220)),
        ("gigachad", 50, 325, 6, mono_hero, (192, 132, 252, 255), (88, 28, 135, 220), (192, 132, 252, 255)),
        ("mewing", 270, 315, -4, mono_bold, (244, 114, 182, 255), (34, 14, 61, 240), (244, 114, 182, 200)),
        ("aura +1000", 470, 335, 7, mono_hero, (34, 211, 238, 255), (8, 145, 178, 220), (34, 211, 238, 255)),
        ("frfr", 40, 405, -5, mono_bold, (250, 204, 21, 255), (34, 14, 61, 240), (250, 204, 21, 200)),
        ("poggers", 190, 390, 4, mono_hero, (244, 114, 182, 255), (157, 23, 77, 220), (244, 114, 182, 255)),
        ("iykyk", 410, 425, -6, mono_bold, (192, 132, 252, 255), (34, 14, 61, 240), (192, 132, 252, 200)),
        ("banger", 560, 415, 5, mono_bold, (244, 114, 182, 255), (34, 14, 61, 240), (244, 114, 182, 200)),
        ("based", 85, 480, 6, mono_bold, (34, 211, 238, 255), (34, 14, 61, 240), (34, 211, 238, 180)),
        ("yeet!", 230, 465, -5, mono_hero, (250, 204, 21, 255), (161, 98, 7, 220), (250, 204, 21, 255)),
        ("fanum-tax", 400, 490, 4, mono_bold, (244, 114, 182, 255), (34, 14, 61, 240), (244, 114, 182, 180)),
        ("w-rizz", 210, 530, -4, mono_bold, (192, 132, 252, 255), (34, 14, 61, 240), (192, 132, 252, 180)),
    ]
    
    for text, x, y, ang, font, txt_col, bg_col, brd_col in hero_pills:
        pill = make_word_pill(
            text, 
            font, 
            text_color=txt_col, 
            fill_color=bg_col, 
            stroke_color=brd_col,
            stroke_width=2 * scale,
            padding=(20 * scale, 10 * scale),
            radius=14 * scale,
            angle=ang
        )
        canvas.paste(pill, (x * scale, y * scale), pill)

    retro_pill = make_word_pill(
        "BRAINROT READY", press_start, (250, 204, 21, 255), (34, 14, 61, 240), (250, 204, 21, 255),
        stroke_width=2 * scale, padding=(12 * scale, 8 * scale), radius=6 * scale, angle=-3
    )
    canvas.paste(retro_pill, (460 * scale, 530 * scale), retro_pill)

    # -------------------------------------------------------------
    # 4. FOOTER TAGLINE
    # -------------------------------------------------------------
    footer_draw = ImageDraw.Draw(canvas)
    footer_text = "Auto-complete the freshest slang & emotes directly on WM Keyboard"
    f_w = footer_draw.textlength(footer_text, font=inter_semi)
    footer_draw.text(((w - f_w) // 2, h - 40 * scale), footer_text, fill=(216, 180, 254, 255), font=inter_semi)

    final_img = canvas.resize((720, 633), Image.Resampling.LANCZOS).convert("RGB")
    final_img.save("previews/en-slang.png", "PNG")
    print("Generated previews/en-slang.png")

if __name__ == "__main__":
    os.makedirs("previews", exist_ok=True)
    generate_developer_preview()
    generate_slang_preview()
