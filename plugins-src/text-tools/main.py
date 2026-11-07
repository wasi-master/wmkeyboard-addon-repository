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
# Base64, hex and URL encoding work on the UTF-8 bytes of the text. Plugin
# strings are made of characters as a person sees them (grapheme clusters):
# "কি" is one character of two code points, and ord() only takes a
# character that is a single code point. scalars() gets the code points of
# any character, which is all UTF-8 needs.


def code_point(index):
    """The index-th Unicode scalar value: every code point but the surrogates."""
    return index if index < 0xD800 else index + 0x800


def scalars(ch):
    """The code points of one character, in order."""
    if ch in ALNUM:
        return [ord(ch)]
    try:
        return [ord(ch)]
    except TypeError:
        pass
    # Several code points in one character. Strings compare code point by
    # code point, so each one can be found by bisection: the largest c for
    # which what we have so far plus chr(c) still sorts at or before ch.
    found = []
    so_far = ""
    while so_far != ch and len(found) < 64:
        lo = 0
        hi = 0x10FFFF - 0x800
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if so_far + chr(code_point(mid)) <= ch:
                lo = mid
            else:
                hi = mid - 1
        if lo == 0:
            break
        found.append(code_point(lo))
        so_far = so_far + chr(code_point(lo))
    return found


def utf8(s):
    """The UTF-8 bytes of s, as a list of numbers."""
    out = []
    for ch in s:
        for cp in scalars(ch):
            if cp < 0x80:
                out.append(cp)
            elif cp < 0x800:
                out.extend([0xC0 + cp // 64, 0x80 + cp % 64])
            elif cp < 0x10000:
                out.extend([0xE0 + cp // 4096, 0x80 + cp // 64 % 64, 0x80 + cp % 64])
            else:
                out.extend([0xF0 + cp // 262144, 0x80 + cp // 4096 % 64, 0x80 + cp // 64 % 64, 0x80 + cp % 64])
    return out


def from_utf8(data):
    """Text from UTF-8 bytes. A byte that is not part of valid UTF-8 becomes �."""
    out = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b < 0x80:
            out.append(chr(b))
            i += 1
            continue
        if 0xC2 <= b <= 0xDF:
            need, cp, least = 1, b - 0xC0, 0x80
        elif 0xE0 <= b <= 0xEF:
            need, cp, least = 2, b - 0xE0, 0x800
        elif 0xF0 <= b <= 0xF4:
            need, cp, least = 3, b - 0xF0, 0x10000
        else:
            out.append("�")
            i += 1
            continue
        j = i + 1
        while j <= i + need and j < n and 0x80 <= data[j] <= 0xBF:
            cp = cp * 64 + data[j] - 0x80
            j += 1
        if j != i + need + 1 or cp < least or cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
            out.append("�")
            i += 1
            continue
        out.append(chr(cp))
        i = j
    return "".join(out)


# ----------------------------------------------------------------- base64 ---

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def base64_encode(s):
    data = utf8(s)
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
    return from_utf8(data)


# -------------------------------------------------------------- hex & url ---


def hex_encode(s):
    return "".join("%02x" % b for b in utf8(s))


def hex_decode(s):
    data = utf8("".join(s.split()))
    out = []
    i = 0
    while i < len(data):
        if i + 1 < len(data) and chr(data[i]) in HEX and chr(data[i + 1]) in HEX:
            out.append(int(chr(data[i]) + chr(data[i + 1]), 16))
            i += 2
        else:
            out.append(data[i])
            i += 1
    return from_utf8(out)


def url_encode(s):
    out = []
    for b in utf8(s):
        c = chr(b)
        if b < 0x80 and (c in ALNUM or c in "-._~"):
            out.append(c)
        else:
            out.append("%" + ("%02X" % b))
    return "".join(out)


def url_decode(s):
    data = utf8(s)
    out = []
    i = 0
    while i < len(data):
        if data[i] == 37 and i + 2 < len(data) and chr(data[i + 1]) in HEX and chr(data[i + 2]) in HEX:
            out.append(int(chr(data[i + 1]) + chr(data[i + 2]), 16))
            i += 3
        else:
            out.append(data[i])
            i += 1
    return from_utf8(out)


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
