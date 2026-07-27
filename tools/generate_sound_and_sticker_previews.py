#!/usr/bin/env python3
"""Generate high-quality preview images for Stickers and Key Sounds addons."""

import os
import io
import math
import zipfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def create_gradient_background(width, height, colors):
    """Creates a smooth multi-stop linear/radial gradient background."""
    base = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(base)
    
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
        
    glow_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_overlay)
    
    if len(colors) > 3:
        glow_color = colors[3]
        glow_draw.ellipse([width * 0.3, -height * 0.25, width * 1.25, height * 0.65], fill=glow_color)
        glow_draw.ellipse([-width * 0.25, height * 0.35, width * 0.7, height * 1.2], fill=colors[4] if len(colors) > 4 else glow_color)
        glow_overlay = glow_overlay.filter(ImageFilter.GaussianBlur(radius=140))
        
    return Image.alpha_composite(base, glow_overlay)

def make_word_pill(text, font, text_color, fill_color, stroke_color, stroke_width=2, padding=(24, 12), radius=16, angle=0):
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

def generate_sticker_preview():
    scale = 2
    w, h = 720 * scale, 633 * scale
    
    bg_colors = [
        (13, 18, 30),       # Deep slate blue #0D121E
        (21, 29, 46),       # Navy #151D2E
        (16, 23, 38),       # Slate #101726
        (99, 102, 241, 50), # Indigo radial glow top right
        (56, 189, 248, 40)  # Cyan glow bottom left
    ]
    
    canvas = create_gradient_background(w, h, bg_colors)
    
    inter_bold = ImageFont.truetype("fonts/inter.ttf", 36 * scale)
    inter_semi = ImageFont.truetype("fonts/inter.ttf", 18 * scale)
    mono_small = ImageFont.truetype("fonts/jetbrains-mono.ttf", 15 * scale)
    mono_label = ImageFont.truetype("fonts/jetbrains-mono.ttf", 14 * scale)
    
    # 1. HEADER SECTION
    header_box = Image.new("RGBA", (w - 80 * scale, 145 * scale), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(header_box)
    
    h_draw.rounded_rectangle(
        [0, 0, w - 80 * scale, 135 * scale],
        radius=20 * scale,
        fill=(15, 23, 42, 220),
        outline=(99, 102, 241, 100),
        width=2 * scale
    )
    
    badge_img = make_word_pill(
        "STICKERS  •  40 VECTOR PACK", 
        mono_small, 
        text_color=(167, 139, 250, 255), 
        fill_color=(139, 92, 246, 40), 
        stroke_color=(167, 139, 250, 150), 
        stroke_width=1 * scale,
        padding=(14 * scale, 5 * scale),
        radius=8 * scale
    )
    header_box.paste(badge_img, (30 * scale, 18 * scale), badge_img)
    
    title_text = "unDraw Everyday Moments"
    h_draw.text((30 * scale, 52 * scale), title_text, fill=(248, 250, 252, 255), font=inter_bold)
    
    sub_text = "40 expressive vector illustrations for work, study, coding & moods"
    h_draw.text((30 * scale, 98 * scale), sub_text, fill=(148, 163, 184, 255), font=inter_semi)
    
    canvas.paste(header_box, (40 * scale, 35 * scale), header_box)
    
    # 2. STICKERS GRID (2 rows x 3 columns)
    featured_stickers = [
        ("stickers/to_the_moon.png", "To the Moon"),
        ("stickers/pair_programming.png", "Pair Coding"),
        ("stickers/skateboarding.png", "Skateboarding"),
        ("stickers/space_exploration.png", "Astronaut"),
        ("stickers/taking_selfie.png", "Selfie Mood"),
        ("stickers/reading.png", "Reading")
    ]
    
    card_w, card_h = 195 * scale, 190 * scale
    start_x, start_y = 45 * scale, 195 * scale
    gap_x, gap_y = 22 * scale, 20 * scale
    
    # Read stickers zip archive
    stickers_archive = zipfile.ZipFile("stickers/undraw-illustrations.wmstickers")
    
    for i, (stk_file, stk_label) in enumerate(featured_stickers):
        row = i // 3
        col = i % 3
        cx = start_x + col * (card_w + gap_x)
        cy = start_y + row * (card_h + gap_y)
        
        # Card background
        card_img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        c_draw = ImageDraw.Draw(card_img)
        
        # Soft dark card with subtle indigo outline
        c_draw.rounded_rectangle(
            [0, 0, card_w, card_h],
            radius=18 * scale,
            fill=(20, 27, 44, 230),
            outline=(51, 65, 85, 200),
            width=2 * scale
        )
        
        # Extract sticker image
        raw_png = stickers_archive.read(stk_file)
        stk_img = Image.open(io.BytesIO(raw_png)).convert("RGBA")
        
        # Resize sticker to fit card
        max_s = 135 * scale
        stk_w, stk_h = stk_img.size
        ratio = min(max_s / stk_w, max_s / stk_h)
        new_w, new_h = int(stk_w * ratio), int(stk_h * ratio)
        stk_resized = stk_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Paste sticker centered
        sx = (card_w - new_w) // 2
        sy = (card_h - 30 * scale - new_h) // 2 + 5 * scale
        card_img.paste(stk_resized, (sx, sy), stk_resized)
        
        # Label at bottom of card
        lbl_w = c_draw.textlength(stk_label, font=mono_label)
        c_draw.text(((card_w - lbl_w) // 2, card_h - 26 * scale), stk_label, fill=(148, 163, 184, 255), font=mono_label)
        
        canvas.paste(card_img, (cx, cy), card_img)
        
    stickers_archive.close()

    # 3. FOOTER
    footer_draw = ImageDraw.Draw(canvas)
    footer_text = "WM Keyboard Addon Repository • 40 Vector Illustrations • unDraw License"
    f_w = footer_draw.textlength(footer_text, font=inter_semi)
    footer_draw.text(((w - f_w) // 2, h - 40 * scale), footer_text, fill=(148, 163, 184, 255), font=inter_semi)

    final_img = canvas.resize((720, 633), Image.Resampling.LANCZOS).convert("RGB")
    final_img.save("previews/undraw-illustrations.png", "PNG")
    print("Generated previews/undraw-illustrations.png")

def generate_sound_preview(sound_id, title, subtitle, badge_text, bg_colors, primary_color, secondary_color, draw_center_art_fn):
    scale = 2
    w, h = 720 * scale, 633 * scale
    
    canvas = create_gradient_background(w, h, bg_colors)
    
    inter_bold = ImageFont.truetype("fonts/inter.ttf", 36 * scale)
    inter_semi = ImageFont.truetype("fonts/inter.ttf", 18 * scale)
    mono_small = ImageFont.truetype("fonts/jetbrains-mono.ttf", 15 * scale)
    
    # 1. HEADER SECTION
    header_box = Image.new("RGBA", (w - 80 * scale, 145 * scale), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(header_box)
    
    h_draw.rounded_rectangle(
        [0, 0, w - 80 * scale, 135 * scale],
        radius=20 * scale,
        fill=(bg_colors[0][0], bg_colors[0][1], bg_colors[0][2], 220),
        outline=primary_color,
        width=2 * scale
    )
    
    badge_img = make_word_pill(
        badge_text, 
        mono_small, 
        text_color=primary_color, 
        fill_color=(primary_color[0], primary_color[1], primary_color[2], 35), 
        stroke_color=(primary_color[0], primary_color[1], primary_color[2], 140), 
        stroke_width=1 * scale,
        padding=(14 * scale, 5 * scale),
        radius=8 * scale
    )
    header_box.paste(badge_img, (30 * scale, 18 * scale), badge_img)
    
    h_draw.text((30 * scale, 52 * scale), title, fill=(248, 250, 252, 255), font=inter_bold)
    h_draw.text((30 * scale, 98 * scale), subtitle, fill=(148, 163, 184, 255), font=inter_semi)
    
    canvas.paste(header_box, (40 * scale, 35 * scale), header_box)
    
    # 2. CENTER ARTWORK
    art_box = Image.new("RGBA", (w - 80 * scale, 370 * scale), (0, 0, 0, 0))
    draw_center_art_fn(art_box, scale, primary_color, secondary_color)
    canvas.paste(art_box, (40 * scale, 190 * scale), art_box)
    
    # 3. FOOTER
    footer_draw = ImageDraw.Draw(canvas)
    footer_text = f"🔊 Real-time Key Audio Feedback for WM Keyboard • CC0 License"
    f_w = footer_draw.textlength(footer_text, font=inter_semi)
    footer_draw.text(((w - f_w) // 2, h - 40 * scale), footer_text, fill=(148, 163, 184, 255), font=inter_semi)

    out_path = f"previews/{sound_id}.png"
    final_img = canvas.resize((720, 633), Image.Resampling.LANCZOS).convert("RGB")
    final_img.save(out_path, "PNG")
    print(f"Generated {out_path}")

# Artwork drawers for each sound
def draw_typewriter_art(art_box, scale, pri_col, sec_col):
    draw = ImageDraw.Draw(art_box)
    w, h = art_box.size
    
    # Background glass panel
    draw.rounded_rectangle([0, 0, w, h], radius=24 * scale, fill=(28, 20, 15, 200), outline=(180, 83, 9, 120), width=2 * scale)
    
    # Center typewriter key graphic
    cx, cy = w // 2, h // 2 - 10 * scale
    
    # Expanding sound wave rings
    for r in range(160 * scale, 60 * scale, -25 * scale):
        alpha = int(120 * (1 - r / (180 * scale)))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(245, 158, 11, alpha), width=3 * scale)
        
    # Vintage typewriter key cap
    key_r = 55 * scale
    draw.ellipse([cx - key_r - 4 * scale, cy - key_r - 4 * scale, cx + key_r + 4 * scale, cy + key_r + 4 * scale], fill=(120, 53, 15), outline=(245, 158, 11), width=4 * scale)
    draw.ellipse([cx - key_r, cy - key_r, cx + key_r, cy + key_r], fill=(15, 23, 42), outline=(217, 119, 6), width=3 * scale)
    
    # Key letter text "T"
    key_font = ImageFont.truetype("fonts/jetbrains-mono.ttf", 48 * scale)
    t_w = draw.textlength("T", font=key_font)
    draw.text((cx - t_w // 2, cy - 28 * scale), "T", fill=(253, 230, 138), font=key_font)
    
    # Audio waveform bars across bottom
    bars_y = h - 50 * scale
    num_bars = 32
    bar_w = 12 * scale
    gap = 6 * scale
    total_w = num_bars * (bar_w + gap) - gap
    start_bx = (w - total_w) // 2
    
    for i in range(num_bars):
        bx = start_bx + i * (bar_w + gap)
        dist = abs(i - num_bars / 2) / (num_bars / 2)
        bh = int((math.cos(dist * math.pi) * 0.5 + 0.5) * 60 * scale + (math.sin(i * 0.8) * 15 * scale))
        bh = max(10 * scale, bh)
        draw.rounded_rectangle([bx, bars_y - bh, bx + bar_w, bars_y], radius=4 * scale, fill=(245, 158, 11, 220))

def draw_marimba_art(art_box, scale, pri_col, sec_col):
    draw = ImageDraw.Draw(art_box)
    w, h = art_box.size
    
    draw.rounded_rectangle([0, 0, w, h], radius=24 * scale, fill=(15, 29, 23, 200), outline=(52, 211, 153, 120), width=2 * scale)
    
    # Marimba wooden bars
    cx, cy = w // 2, h // 2 - 20 * scale
    num_bars = 7
    bar_w = 40 * scale
    bar_gap = 16 * scale
    total_w = num_bars * (bar_w + bar_gap) - bar_gap
    start_x = (w - total_w) // 2
    
    for i in range(num_bars):
        bx = start_x + i * (bar_w + bar_gap)
        bar_h = (150 - i * 10) * scale
        by = cy - bar_h // 2
        
        # Wooden bar color
        is_hit = (i == 3)
        fill_col = (180, 83, 9, 240) if not is_hit else (245, 158, 11, 255)
        border_col = (52, 211, 153, 255) if is_hit else (217, 119, 6, 200)
        
        draw.rounded_rectangle([bx, by, bx + bar_w, by + bar_h], radius=10 * scale, fill=fill_col, outline=border_col, width=3 * scale if is_hit else 2 * scale)
        
        # Harmonic sound waves rising from hit bar
        if is_hit:
            # Mallet circle hitting bar
            draw.ellipse([bx + bar_w // 2 - 16 * scale, by + 30 * scale, bx + bar_w // 2 + 16 * scale, by + 62 * scale], fill=(52, 211, 153), outline=(255, 255, 255), width=2 * scale)
            # Ripple rings
            mcx, mcy = bx + bar_w // 2, by + 46 * scale
            for r in range(35 * scale, 120 * scale, 25 * scale):
                draw.ellipse([mcx - r, mcy - r, mcx + r, mcy + r], outline=(52, 211, 153, int(200 * (1 - r / 140))), width=2 * scale)
                
    # Warm sine wave across bottom
    wave_y = h - 45 * scale
    pts = []
    for x in range(40 * scale, w - 40 * scale, 4 * scale):
        t = x / w
        y = wave_y + math.sin(t * math.pi * 6) * 22 * scale * math.sin(t * math.pi)
        pts.append((x, y))
    if len(pts) > 1:
        draw.line(pts, fill=(52, 211, 153, 255), width=4 * scale)

def draw_droplet_art(art_box, scale, pri_col, sec_col):
    draw = ImageDraw.Draw(art_box)
    w, h = art_box.size
    
    draw.rounded_rectangle([0, 0, w, h], radius=24 * scale, fill=(11, 25, 44, 200), outline=(56, 189, 248, 120), width=2 * scale)
    
    cx, cy = w // 2, h // 2 - 10 * scale
    
    # Concentric water ripple ellipses
    for r in range(180 * scale, 30 * scale, -25 * scale):
        ry = int(r * 0.45)
        alpha = int(220 * (1 - r / (200 * scale)))
        draw.ellipse([cx - r, cy - ry, cx + r, cy + ry], outline=(56, 189, 248, alpha), width=3 * scale)
        
    # Water Drop icon in center
    drop_y = cy - 25 * scale
    # Draw drop tear shape
    drop_pts = [
        (cx, drop_y - 50 * scale),
        (cx + 30 * scale, drop_y + 10 * scale),
        (cx + 25 * scale, drop_y + 35 * scale),
        (cx, drop_y + 45 * scale),
        (cx - 25 * scale, drop_y + 35 * scale),
        (cx - 30 * scale, drop_y + 10 * scale),
    ]
    draw.polygon(drop_pts, fill=(56, 189, 248, 230), outline=(255, 255, 255, 255))
    
    # Upward pitch bend curve on right side
    curve_pts = []
    for i in range(50):
        t = i / 49
        x = cx + 80 * scale + t * 180 * scale
        y = cy + 40 * scale - (t ** 2) * 90 * scale
        curve_pts.append((x, y))
    draw.line(curve_pts, fill=(14, 165, 233, 255), width=4 * scale)
    
    # Frequency label next to curve
    mono_f = ImageFont.truetype("fonts/jetbrains-mono.ttf", 16 * scale)
    draw.text((cx + 180 * scale, cy - 65 * scale), "Pitch Bend ↗", fill=(56, 189, 248, 255), font=mono_f)

def draw_blip_art(art_box, scale, pri_col, sec_col):
    draw = ImageDraw.Draw(art_box)
    w, h = art_box.size
    
    draw.rounded_rectangle([0, 0, w, h], radius=24 * scale, fill=(28, 11, 43, 200), outline=(236, 72, 153, 120), width=2 * scale)
    
    cx, cy = w // 2, h // 2 - 10 * scale
    
    # 8-Bit Retro Square Wave
    sq_pts = []
    start_x = cx - 240 * scale
    wave_h = 50 * scale
    
    for i in range(8):
        bx = start_x + i * 60 * scale
        if i % 2 == 0:
            sq_pts.extend([(bx, cy + wave_h), (bx, cy - wave_h), (bx + 60 * scale, cy - wave_h)])
        else:
            sq_pts.extend([(bx, cy - wave_h), (bx, cy + wave_h), (bx + 60 * scale, cy + wave_h)])
            
    draw.line(sq_pts, fill=(236, 72, 153, 255), width=5 * scale)
    
    # Retro Pixel Stars around wave
    pixel_stars = [
        (cx - 200 * scale, cy - 80 * scale),
        (cx - 80 * scale, cy + 90 * scale),
        (cx + 100 * scale, cy - 90 * scale),
        (cx + 220 * scale, cy + 70 * scale),
    ]
    p_font = ImageFont.truetype("fonts/press-start-2p.ttf", 12 * scale)
    for px, py in pixel_stars:
        draw.text((px, py), "★", fill=(250, 204, 21, 255), font=p_font)
        
    # Retro arcade button badge
    btn_r = 30 * scale
    draw.ellipse([cx - btn_r, cy - btn_r, cx + btn_r, cy + btn_r], fill=(6, 182, 212, 230), outline=(255, 255, 255), width=3 * scale)
    draw.text((cx - 10 * scale, cy - 12 * scale), "A", fill=(255, 255, 255), font=p_font)

if __name__ == "__main__":
    os.makedirs("previews", exist_ok=True)
    
    # 1. Regenerate Sticker preview
    generate_sticker_preview()
    
    # 2. Sound Previews
    # Typewriter
    generate_sound_preview(
        sound_id="typewriter",
        title="Typewriter Sound",
        subtitle="Mechanical typebar strike: hard noise transient with a woody thunk",
        badge_text="KEY SOUND  •  MECHANICAL",
        bg_colors=[(28, 20, 15), (42, 26, 15), (30, 18, 12), (245, 158, 11, 55), (180, 83, 9, 45)],
        primary_color=(245, 158, 11, 255),
        secondary_color=(217, 119, 6, 255),
        draw_center_art_fn=draw_typewriter_art
    )
    
    # Marimba
    generate_sound_preview(
        sound_id="marimba",
        title="Marimba Sound",
        subtitle="Soft wooden mallet: warm fundamental tone with ringing 4th harmonic",
        badge_text="KEY SOUND  •  PERCUSSION",
        bg_colors=[(15, 29, 23), (22, 46, 36), (16, 32, 25), (52, 211, 153, 55), (16, 185, 129, 45)],
        primary_color=(52, 211, 153, 255),
        secondary_color=(16, 185, 129, 255),
        draw_center_art_fn=draw_marimba_art
    )
    
    # Droplet
    generate_sound_preview(
        sound_id="droplet",
        title="Droplet Sound",
        subtitle="Water drop: fast upward pitch bend, smooth & subtle transient",
        badge_text="KEY SOUND  •  FLUID WATER",
        bg_colors=[(11, 25, 44), (15, 41, 74), (12, 30, 54), (56, 189, 248, 55), (14, 165, 233, 45)],
        primary_color=(56, 189, 248, 255),
        secondary_color=(14, 165, 233, 255),
        draw_center_art_fn=draw_droplet_art
    )
    
    # Blip
    generate_sound_preview(
        sound_id="blip",
        title="Blip Sound",
        subtitle="Retro square-wave blip with an 8-bit handheld gaming flavour",
        badge_text="KEY SOUND  •  8-BIT RETRO",
        bg_colors=[(28, 11, 43), (46, 15, 69), (34, 12, 53), (236, 72, 153, 55), (6, 182, 212, 45)],
        primary_color=(236, 72, 153, 255),
        secondary_color=(6, 182, 212, 255),
        draw_center_art_fn=draw_blip_art
    )
