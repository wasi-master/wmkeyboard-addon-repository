# Text Tools: change case, encode, and count.
#
# Everything here works on text the user typed or pasted into the box at the
# top. That is how any plugin gets text: there is no API for reading what
# you are writing, so the user hands it over on purpose, and can see exactly
# what they handed over.

text = ""
output = ""

DIGITS = "0123456789"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWER = "abcdefghijklmnopqrstuvwxyz"
ALNUM = UPPER + LOWER + DIGITS
HEX = "0123456789abcdefABCDEF"

# ------------------------------------------------------------------ bytes ---
#
# Base64, hex and URL encoding work on the UTF-8 bytes of the text, which
# s.encode() gives. Decoding goes back through bytes(...).decode(); a byte
# that is not part of valid UTF-8 comes out as �.


def text_of(data):
    return bytes(data).decode("utf-8", errors="replace")


# ----------------------------------------------------------------- base64 ---

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def base64_encode(s):
    data = s.encode("utf-8")
    out = []
    for i in range(0, len(data), 3):
        chunk = data[i:i + 3]
        n = chunk[0] * 65536
        if len(chunk) > 1:
            n += chunk[1] * 256
        if len(chunk) > 2:
            n += chunk[2]
        sextets = [n // 262144 % 64, n // 4096 % 64, n // 64 % 64, n % 64]
        # Two padding cases: one leftover byte gives two '=', two gives one.
        keep = len(chunk) + 1
        for j in range(keep):
            out.append(ALPHABET[sextets[j]])
        out.append("=" * (4 - keep))
    return "".join(out)


def base64_decode(s):
    data = []
    bits = 0
    count = 0
    for c in s:
        if c == "=" or c not in ALPHABET:
            continue
        bits = bits * 64 + ALPHABET.index(c)
        count += 6
        if count >= 8:
            count -= 8
            data.append(bits // 2 ** count % 256)
            # Drop the bits just spent, so `bits` stays small.
            bits = bits % 2 ** count
    return text_of(data)


# -------------------------------------------------------------- hex & url ---


def hex_encode(s):
    return s.encode("utf-8").hex()


def hex_decode(s):
    data = "".join(s.split()).encode("utf-8")
    out = []
    i = 0
    while i < len(data):
        if i + 1 < len(data) and chr(data[i]) in HEX and chr(data[i + 1]) in HEX:
            out.append(int(chr(data[i]) + chr(data[i + 1]), 16))
            i += 2
        else:
            out.append(data[i])
            i += 1
    return text_of(out)


def url_encode(s):
    out = []
    for b in s.encode("utf-8"):
        c = chr(b)
        if b < 0x80 and (c in ALNUM or c in "-._~"):
            out.append(c)
        else:
            out.append("%" + ("%02X" % b))
    return "".join(out)


def url_decode(s):
    data = s.encode("utf-8")
    out = []
    i = 0
    while i < len(data):
        if data[i] == 37 and i + 2 < len(data) and chr(data[i + 1]) in HEX and chr(data[i + 2]) in HEX:
            out.append(int(chr(data[i + 1]) + chr(data[i + 2]), 16))
            i += 3
        else:
            out.append(data[i])
            i += 1
    return text_of(out)


# --------------------------------------------------------------- the rest ---


def title_case(s):
    """The first letter of each word up, the rest of the word down."""
    out = []
    in_word = False
    for c in s:
        if in_word and (c in ALNUM or c == "'"):
            out.append(c.lower())
        elif c in UPPER or c in LOWER:
            out.append(c.upper())
            in_word = True
        else:
            out.append(c)
            in_word = False
    return "".join(out)


def statistics(s):
    words = len(s.split())
    lines = s.count("\n") + 1 if s else 0
    letters = 0
    for c in s:
        if c.isalpha():
            letters += 1
    return "%d characters\n%d letters\n%d words\n%d lines" % (len(s), letters, words, lines)


ACTIONS = {
    "upper": lambda s: s.upper(),
    "lower": lambda s: s.lower(),
    "title": title_case,
    "reverse": lambda s: s[::-1],
    "b64_encode": base64_encode,
    "b64_decode": base64_decode,
    "hex_encode": hex_encode,
    "hex_decode": hex_decode,
    "url_encode": url_encode,
    "url_decode": url_decode,
    "stats": statistics,
}

# ----------------------------------------------------------------- events ---


def on_event(e):
    global text, output
    if e["type"] == "input_changed" and e["id"] == "text":
        text = e["value"]
    elif e["type"] == "click":
        action = ACTIONS.get(e["id"])
        if action:
            output = action(text)
        if e["id"] == "clear":
            text = ""
            output = ""
            # Ask the keyboard to empty the box; we do not own it ourselves.
            wm.ui.set_input("text", "")


def render():
    if output != "":
        result = ui.output(output, id="out", mono=True)
    else:
        result = ui.label("Results appear here.", style="caption")
    return ui.column(
        ui.input("text", label="Text", placeholder="Type or paste, then pick an action"),
        ui.tabs(
            "tools",
            ui.page(
                "Case",
                ui.row(ui.button("upper", "UPPER"), ui.button("lower", "lower")),
                ui.row(ui.button("title", "Title Case"), ui.button("reverse", "esreveR")),
            ),
            ui.page(
                "Encode",
                ui.row(ui.button("b64_encode", "Base64"), ui.button("b64_decode", "un-Base64")),
                ui.row(ui.button("hex_encode", "Hex"), ui.button("hex_decode", "un-Hex")),
                ui.row(ui.button("url_encode", "URL"), ui.button("url_decode", "un-URL")),
            ),
            ui.page(
                "Count",
                ui.button("stats", "Count it", style="primary"),
            ),
        ),
        ui.divider(),
        result,
        ui.button("clear", "Clear"),
    )
