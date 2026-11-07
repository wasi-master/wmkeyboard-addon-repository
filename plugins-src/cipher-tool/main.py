# Cipher Tool: Caesar and Vigenere, encode and decode.
#
# This is the plugin the getting-started guide builds step by step, so it
# sticks to the plainest Python that does the job.
#
# The shape every plugin has:
#   * some state in variables at the top of the file,
#   * on_event(e) to change that state when the user does something,
#   * render() to describe what should be on screen right now.
#
# The keyboard calls render() after every event, so you never update the UI
# yourself: you change a variable and describe the result.

# ----------------------------------------------------------------- state ----

# What the user has typed into each box. The keyboard owns the boxes; it
# tells us the contents through input_changed events.
message = ""
shift = "3"
keyword = ""
output = ""

# --------------------------------------------------------------- ciphers ----

UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWER = "abcdefghijklmnopqrstuvwxyz"


def caesar(text, by):
    """Shifts every letter by `by`, wrapping within its own case."""
    out = []
    for c in text:
        if c in UPPER:
            out.append(UPPER[(UPPER.index(c) + by) % 26])
        elif c in LOWER:
            out.append(LOWER[(LOWER.index(c) + by) % 26])
        else:
            out.append(c)
    return "".join(out)


def vigenere(text, key, direction):
    """Vigenere: the same idea, but the shift comes from a repeating keyword."""
    shifts = [LOWER.index(c) for c in key.lower() if c in LOWER]
    if not shifts:
        return text
    out = []
    used = 0
    for c in text:
        if c in UPPER or c in LOWER:
            out.append(caesar(c, direction * shifts[used % len(shifts)]))
            used += 1
        else:
            out.append(c)
    return "".join(out)


def whole_number(text):
    """The number in a box, or 0. Only plain digits count, with an optional minus."""
    text = text.strip()
    digits = text[1:] if text.startswith("-") else text
    if digits == "" or any(c not in "0123456789" for c in digits):
        return 0
    return int(text)


# --------------------------------------------------------------- events ----


def on_event(e):
    global message, shift, keyword, output
    if e["type"] == "input_changed":
        if e["id"] == "message":
            message = e["value"]
        if e["id"] == "shift":
            shift = e["value"]
        if e["id"] == "keyword":
            keyword = e["value"]

    elif e["type"] == "click":
        by = whole_number(shift)
        if e["id"] == "caesar_encode":
            output = caesar(message, by)
        if e["id"] == "caesar_decode":
            output = caesar(message, -by)
        if e["id"] == "vigenere_encode":
            output = vigenere(message, keyword, 1)
        if e["id"] == "vigenere_decode":
            output = vigenere(message, keyword, -1)

    elif e["type"] == "tab_selected":
        # Switching tabs clears a result that belonged to the other cipher.
        output = ""


# --------------------------------------------------------------- render ----


def result():
    """The result box. Shared by both tabs, so it lives in its own function."""
    if output == "":
        return ui.label("Type something and pick a button.", style="caption")
    # insertable (on by default) puts the keyboard's own Insert button under
    # the text, which is how a result reaches whatever the user is writing in.
    # A plugin cannot type on its own: the user taps Insert.
    return ui.output(output, id="result", mono=True)


def render():
    return ui.tabs(
        "cipher",
        ui.page(
            "Caesar",
            ui.input("message", label="Message", placeholder="Type or paste"),
            ui.input("shift", label="Shift", placeholder="3"),
            ui.row(
                ui.button("caesar_encode", "Encode", style="primary"),
                ui.button("caesar_decode", "Decode"),
            ),
            result(),
        ),
        ui.page(
            "Vigenere",
            ui.input("message", label="Message", placeholder="Type or paste"),
            ui.input("keyword", label="Keyword", placeholder="lemon"),
            ui.row(
                ui.button("vigenere_encode", "Encode", style="primary"),
                ui.button("vigenere_decode", "Decode"),
            ),
            result(),
        ),
    )
