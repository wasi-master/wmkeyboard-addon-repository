#!/usr/bin/env python3
"""Generate a beautiful, professional preview image for Texting Shortcuts."""

from PIL import Image, ImageDraw, ImageFont
import os

def main():
    # Dimensions matching the existing preview images (720x633)
    width, height = 720, 633
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # 1. Background Gradient (deep slate/navy to deep indigo/navy)
    start_color = (15, 23, 42)    # Slate 900
    end_color = (30, 27, 75)      # Indigo 950
    for y in range(height):
        r = int(start_color[0] + (end_color[0] - start_color[0]) * y / height)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * y / height)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Load Fonts
    font_dir = "fonts"
    inter_path = os.path.join(font_dir, "inter.ttf")
    mono_path = os.path.join(font_dir, "jetbrains-mono.ttf")

    title_font = ImageFont.truetype(inter_path, 40)
    subtitle_font = ImageFont.truetype(inter_path, 20)
    label_font = ImageFont.truetype(inter_path, 22)
    trigger_font = ImageFont.truetype(mono_path, 18)

    # Draw Title
    title_text = "Texting Shortcuts"
    title_w = draw.textlength(title_text, font=title_font)
    draw.text(((width - title_w) // 2, 50), title_text, fill=(248, 250, 252), font=title_font) # Slate 50

    # Draw Subtitle
    subtitle_text = "Type less, say more with 40+ chat expansions"
    subtitle_w = draw.textlength(subtitle_text, font=subtitle_font)
    draw.text(((width - subtitle_w) // 2, 105), subtitle_text, fill=(148, 163, 184), font=subtitle_font) # Slate 400

    # Draw separator line
    draw.line([(80, 145), (width - 80, 145)], fill=(51, 65, 85), width=1) # Slate 700

    # Sample data to display
    samples = [
        ("omw", "On my way!"),
        ("brb", "Be right back!"),
        ("lmk", "Let me know!"),
        ("btw", "By the way,"),
        ("tbh", "To be honest,")
    ]

    card_x_start = 70
    card_x_end = width - 70
    card_h = 60
    spacing = 20
    start_y = 175

    for i, (trigger, expansion) in enumerate(samples):
        card_y_start = start_y + i * (card_h + spacing)
        card_y_end = card_y_start + card_h

        # Draw card container (Slate 800 background, Slate 700 border)
        draw.rounded_rectangle(
            [card_x_start, card_y_start, card_x_end, card_y_end],
            radius=12,
            fill=(30, 41, 59),
            outline=(51, 65, 85),
            width=1
        )

        # Draw trigger pill container on the left (Slate 900 background)
        pill_x_start = card_x_start + 20
        pill_x_end = pill_x_start + 100
        pill_y_start = card_y_start + 12
        pill_y_end = card_y_end - 12
        draw.rounded_rectangle(
            [pill_x_start, pill_y_start, pill_x_end, pill_y_end],
            radius=8,
            fill=(15, 23, 42),
            outline=(14, 165, 233), # Sky 500 outline
            width=1
        )

        # Draw trigger text (mono font, centered in pill)
        trig_w = draw.textlength(trigger, font=trigger_font)
        # Use text anchor or compute manual center
        trig_x = pill_x_start + (pill_x_end - pill_x_start - trig_w) / 2
        # Y alignment offset (approximate font bounding box offset)
        trig_y = pill_y_start + 6
        draw.text((trig_x, trig_y), trigger, fill=(56, 189, 248), font=trigger_font) # Cyan 400

        # Draw arrow "→" in the middle
        arrow_text = "→"
        arrow_w = draw.textlength(arrow_text, font=label_font)
        arrow_x = pill_x_end + 30
        arrow_y = card_y_start + 16
        draw.text((arrow_x, arrow_y), arrow_text, fill=(100, 116, 139), font=label_font) # Slate 500

        # Draw expansion text on the right
        exp_x = arrow_x + arrow_w + 30
        exp_y = card_y_start + 16
        draw.text((exp_x, exp_y), expansion, fill=(248, 250, 252), font=label_font) # Slate 50

    # Ensure the previews directory exists
    os.makedirs("previews", exist_ok=True)
    
    # Save the output image
    output_path = os.path.join("previews", "texting-shortcuts.png")
    img.save(output_path, "PNG")
    print(f"Successfully generated preview image: {output_path}")

    # Generate pattern replies and pattern formatters previews
    generate_pattern_replies_preview()
    generate_pattern_formatters_preview()

    # Generate layout, font, plugin, dictionary, sticker and sound preview images
    try:
        from generate_layout_previews import main as generate_layout_previews_main
        from generate_font_previews import main as generate_font_previews_main
        from generate_plugin_previews import main as generate_plugin_previews_main
        from generate_dictionary_previews import generate_developer_preview, generate_slang_preview
        from generate_sound_and_sticker_previews import generate_sticker_preview
        generate_layout_previews_main()
        generate_font_previews_main()
        generate_plugin_previews_main()
        generate_developer_preview()
        generate_slang_preview()
        generate_sticker_preview()
    except ImportError:
        import sys
        sys.path.append(os.path.dirname(__file__))
        from generate_layout_previews import main as generate_layout_previews_main
        from generate_font_previews import main as generate_font_previews_main
        from generate_plugin_previews import main as generate_plugin_previews_main
        from generate_dictionary_previews import generate_developer_preview, generate_slang_preview
        from generate_sound_and_sticker_previews import generate_sticker_preview
        generate_layout_previews_main()
        generate_font_previews_main()
        generate_plugin_previews_main()
        generate_developer_preview()
        generate_slang_preview()
        generate_sticker_preview()

def generate_pattern_replies_preview():
    width, height = 720, 633
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # 1. Gradient Background (Deep Slate to Emerald accent)
    start_color = (15, 23, 42)    # Slate 900
    end_color = (6, 78, 59)       # Emerald 900
    for y in range(height):
        r = int(start_color[0] + (end_color[0] - start_color[0]) * y / height)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * y / height)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    font_dir = "fonts"
    inter_path = os.path.join(font_dir, "inter.ttf")
    mono_path = os.path.join(font_dir, "jetbrains-mono.ttf")

    title_font = ImageFont.truetype(inter_path, 36)
    subtitle_font = ImageFont.truetype(inter_path, 18)
    label_font = ImageFont.truetype(inter_path, 16)
    arrow_font = ImageFont.truetype(inter_path, 18)
    trigger_font = ImageFont.truetype(mono_path, 15)
    pattern_font = ImageFont.truetype(mono_path, 11)

    title_text = "Pattern Replies"
    title_w = draw.textlength(title_text, font=title_font)
    draw.text(((width - title_w) // 2, 42), title_text, fill=(248, 250, 252), font=title_font)

    subtitle_text = "Context-aware template responses triggered by regex patterns"
    subtitle_w = draw.textlength(subtitle_text, font=subtitle_font)
    draw.text(((width - subtitle_w) // 2, 92), subtitle_text, fill=(167, 243, 208), font=subtitle_font)

    draw.line([(50, 130), (width - 50, 130)], fill=(51, 65, 85), width=1)

    samples = [
        ("hello John", "^hello (.+)$", "Hello, John! Nice to meet you."),
        ("thanks Sarah", "^thanks (.+)$", "Dear Sarah,\nThank you for your message..."),
        ("bday Alex", "^bday (.+)$", "Happy birthday, Alex! Have a great day."),
        ("eta 15 mins", "^eta (.+)$", "Sorry, running late! Be there in 15 mins."),
        ("meet tomorrow 3pm", "^meet (.+) (.+)$", "Would tomorrow at 3pm work for you?"),
    ]

    card_x_start = 40
    card_x_end = width - 40
    card_h = 75
    spacing = 15
    start_y = 152

    for i, (typed, pattern, expansion) in enumerate(samples):
        card_y_start = start_y + i * (card_h + spacing)
        card_y_end = card_y_start + card_h

        draw.rounded_rectangle(
            [card_x_start, card_y_start, card_x_end, card_y_end],
            radius=12,
            fill=(30, 41, 59),
            outline=(51, 65, 85),
            width=1
        )

        pill_x_start = card_x_start + 12
        pill_x_end = pill_x_start + 175
        pill_y_start = card_y_start + 10
        pill_y_end = card_y_end - 10

        draw.rounded_rectangle(
            [pill_x_start, pill_y_start, pill_x_end, pill_y_end],
            radius=8,
            fill=(15, 23, 42),
            outline=(16, 185, 129),
            width=1
        )

        trig_w = draw.textlength(typed, font=trigger_font)
        trig_x = pill_x_start + (pill_x_end - pill_x_start - trig_w) / 2
        trig_y = pill_y_start + 8
        draw.text((trig_x, trig_y), typed, fill=(52, 211, 153), font=trigger_font)

        pat_w = draw.textlength(pattern, font=pattern_font)
        pat_x = pill_x_start + (pill_x_end - pill_x_start - pat_w) / 2
        pat_y = pill_y_start + 30
        draw.text((pat_x, pat_y), pattern, fill=(148, 163, 184), font=pattern_font)

        arrow_text = "→"
        arrow_w = draw.textlength(arrow_text, font=arrow_font)
        arrow_x = pill_x_end + 12
        arrow_y = card_y_start + 26
        draw.text((arrow_x, arrow_y), arrow_text, fill=(100, 116, 139), font=arrow_font)

        exp_x = arrow_x + arrow_w + 12
        lines = expansion.split("\n")
        if len(lines) == 1:
            exp_y = card_y_start + 28
            draw.text((exp_x, exp_y), lines[0], fill=(248, 250, 252), font=label_font)
        else:
            exp_y = card_y_start + 16
            for j, line in enumerate(lines[:2]):
                draw.text((exp_x, exp_y + j * 22), line, fill=(248, 250, 252), font=label_font)

    os.makedirs("previews", exist_ok=True)
    output_path = os.path.join("previews", "pattern-replies.png")
    img.save(output_path, "PNG")
    print(f"Successfully generated preview image: {output_path}")

def generate_pattern_formatters_preview():
    width, height = 720, 633
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # 1. Gradient Background (Deep Slate to Purple accent)
    start_color = (15, 23, 42)    # Slate 900
    end_color = (88, 28, 135)     # Purple 900
    for y in range(height):
        r = int(start_color[0] + (end_color[0] - start_color[0]) * y / height)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * y / height)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    font_dir = "fonts"
    inter_path = os.path.join(font_dir, "inter.ttf")
    mono_path = os.path.join(font_dir, "jetbrains-mono.ttf")

    title_font = ImageFont.truetype(inter_path, 36)
    subtitle_font = ImageFont.truetype(inter_path, 18)
    label_font = ImageFont.truetype(inter_path, 16)
    arrow_font = ImageFont.truetype(inter_path, 18)
    trigger_font = ImageFont.truetype(mono_path, 15)
    pattern_font = ImageFont.truetype(mono_path, 11)

    title_text = "Pattern Formatters"
    title_w = draw.textlength(title_text, font=title_font)
    draw.text(((width - title_w) // 2, 42), title_text, fill=(248, 250, 252), font=title_font)

    subtitle_text = "Slash commands to format text, wrap Markdown & expand links"
    subtitle_w = draw.textlength(subtitle_text, font=subtitle_font)
    draw.text(((width - subtitle_w) // 2, 92), subtitle_text, fill=(233, 213, 255), font=subtitle_font)

    draw.line([(50, 130), (width - 50, 130)], fill=(51, 65, 85), width=1)

    samples = [
        ("/up hello world", "^/up (.+)$", "HELLO WORLD"),
        ("/bold important", "^/bold (.+)$", "**important**"),
        ("/link Docs site.com", "^/link (.+) (\\S+)$", "[Docs](site.com)"),
        ("/gh wasi-master", "^/gh (\\S+)$", "https://github.com/wasi-master"),
        ("/todo Buy coffee", "^/todo (.+)$", "- [ ] Buy coffee"),
    ]

    card_x_start = 40
    card_x_end = width - 40
    card_h = 75
    spacing = 15
    start_y = 152

    for i, (typed, pattern, expansion) in enumerate(samples):
        card_y_start = start_y + i * (card_h + spacing)
        card_y_end = card_y_start + card_h

        draw.rounded_rectangle(
            [card_x_start, card_y_start, card_x_end, card_y_end],
            radius=12,
            fill=(30, 41, 59),
            outline=(51, 65, 85),
            width=1
        )

        pill_x_start = card_x_start + 12
        pill_x_end = pill_x_start + 195
        pill_y_start = card_y_start + 10
        pill_y_end = card_y_end - 10

        draw.rounded_rectangle(
            [pill_x_start, pill_y_start, pill_x_end, pill_y_end],
            radius=8,
            fill=(15, 23, 42),
            outline=(168, 85, 247),
            width=1
        )

        trig_w = draw.textlength(typed, font=trigger_font)
        trig_x = pill_x_start + (pill_x_end - pill_x_start - trig_w) / 2
        trig_y = pill_y_start + 8
        draw.text((trig_x, trig_y), typed, fill=(216, 180, 254), font=trigger_font)

        pat_w = draw.textlength(pattern, font=pattern_font)
        pat_x = pill_x_start + (pill_x_end - pill_x_start - pat_w) / 2
        pat_y = pill_y_start + 30
        draw.text((pat_x, pat_y), pattern, fill=(148, 163, 184), font=pattern_font)

        arrow_text = "→"
        arrow_w = draw.textlength(arrow_text, font=arrow_font)
        arrow_x = pill_x_end + 12
        arrow_y = card_y_start + 26
        draw.text((arrow_x, arrow_y), arrow_text, fill=(100, 116, 139), font=arrow_font)

        exp_x = arrow_x + arrow_w + 12
        exp_y = card_y_start + 28
        draw.text((exp_x, exp_y), expansion, fill=(248, 250, 252), font=label_font)

    os.makedirs("previews", exist_ok=True)
    output_path = os.path.join("previews", "pattern-formatters.png")
    img.save(output_path, "PNG")
    print(f"Successfully generated preview image: {output_path}")

if __name__ == "__main__":
    main()

