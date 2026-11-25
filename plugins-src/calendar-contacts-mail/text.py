"""Decoding shared by calendars, contacts and mail: folded lines, property
parameters, quoted-printable, RFC 2047 encoded words, and charsets."""

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def unfold(text, keep=False):
    """Lines with their continuations (a leading space or tab) joined back on.
    iCalendar drops that one space; mail headers keep it ([keep])."""
    out = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] = out[-1] + (" " + line.lstrip() if keep else line[1:])
        else:
            out.append(line)
    return out


def unfold_qp(lines):
    """vCard 2.1's quoted-printable values end a line with "=" to go on."""
    out = []
    joining = False
    for line in lines:
        if joining and out:
            out[-1] = out[-1][:-1] + line
        else:
            out.append(line)
        joining = "QUOTED-PRINTABLE" in out[-1].upper() and out[-1].endswith("=")
    return out


def _split_unquoted(text, sep):
    parts = []
    cur = []
    quoted = False
    for ch in text:
        if ch == "\"":
            quoted = not quoted
        if ch == sep and not quoted:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def prop(line):
    """("NAME", {"PARAM": "value"}, "value") for a content line, or None."""
    colon = -1
    quoted = False
    for i, ch in enumerate(line):
        if ch == "\"":
            quoted = not quoted
        elif ch == ":" and not quoted:
            colon = i
            break
    if colon <= 0:
        return None
    head = _split_unquoted(line[:colon], ";")
    name = head[0].upper()
    dot = name.rfind(".")
    if dot >= 0:
        name = name[dot + 1:]
    params = {}
    for p in head[1:]:
        eq = p.find("=")
        if eq < 0:
            params.setdefault("TYPE", "")
            params["TYPE"] = (params["TYPE"] + "," + p).strip(",")
        else:
            key = p[:eq].upper()
            value = p[eq + 1:].strip("\"")
            params[key] = (params[key] + "," + value) if key in params else value
    return name, params, line[colon + 1:]


def unescape(value):
    """iCalendar and vCard text: \\n, \\, \\; and \\\\."""
    if "\\" not in value:
        return value
    out = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            out.append("\n" if nxt in "nN" else nxt)
            i = i + 2
        else:
            out.append(ch)
            i = i + 1
    return "".join(out)


def charset(raw, name):
    """Bytes as text in charset [name]; UTF-8 unless it names Latin-1 or Windows-1252."""
    name = (name or "utf-8").lower().replace("_", "-")
    if name in ("iso-8859-1", "latin1", "latin-1", "windows-1252", "cp1252", "us-ascii", "ascii"):
        return "".join(chr(b) for b in raw)
    return raw.decode("utf-8", "replace")


def _hexval(ch):
    o = ord(ch)
    if 48 <= o <= 57:
        return o - 48
    if 65 <= o <= 70:
        return o - 55
    if 97 <= o <= 102:
        return o - 87
    return -1


def quoted_printable(text, header=False):
    """Quoted-printable to bytes; in a header word, "_" is a space."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "=":
            if i + 1 < n and text[i + 1] == "\n":
                i = i + 2
                continue
            hi = _hexval(text[i + 1]) if i + 1 < n else -1
            lo = _hexval(text[i + 2]) if i + 2 < n else -1
            if hi >= 0 and lo >= 0:
                out.append(hi * 16 + lo)
                i = i + 3
                continue
            if i + 1 == n:
                i = i + 1
                continue
        if header and ch == "_":
            out.append(32)
        else:
            for b in ch.encode("utf-8"):
                out.append(b)
        i = i + 1
    return bytes(out)


def b64(text):
    import base64
    try:
        return base64.b64decode("".join(text.split()))
    except ValueError:
        return b""


def words(text):
    """A header with RFC 2047 encoded words (=?UTF-8?B?...?=) decoded."""
    if "=?" not in text:
        return text
    out = []
    i = 0
    last_was_word = False
    while i < len(text):
        start = text.find("=?", i)
        if start < 0:
            out.append(text[i:])
            break
        q1 = text.find("?", start + 2)
        q2 = text.find("?", q1 + 1) if q1 > 0 else -1
        end = text.find("?=", q2 + 1) if q2 > 0 else -1
        if end < 0:
            out.append(text[i:])
            break
        between = text[i:start]
        if not (last_was_word and not between.strip()):
            out.append(between)
        cs = text[start + 2:q1]
        kind = text[q1 + 1:q2].upper()
        body = text[q2 + 1:end]
        raw = b64(body) if kind == "B" else quoted_printable(body, header=True)
        out.append(charset(raw, cs.split("*")[0]))
        last_was_word = True
        i = end + 2
    return "".join(out)


def weekday(y, m, d):
    """0 for Monday: Sakamoto's method."""
    offsets = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
    if m < 3:
        y = y - 1
    return (y + y // 4 - y // 100 + y // 400 + offsets[m - 1] + d + 6) % 7


def when(value, params=None):
    """An iCalendar or vCard date or date-time as readable text."""
    params = params or {}
    v = value.strip()
    if len(v) >= 10 and v[4] == "-":
        v = v.replace("-", "").replace(":", "")
    if len(v) < 8 or not v[:8].isdigit():
        return value
    y, m, d = int(v[:4]), int(v[4:6]), int(v[6:8])
    if not 1 <= m <= 12:
        return value
    text = DAYS[weekday(y, m, d)] + f" {d} {MONTHS[m - 1]} {y}"
    if len(v) >= 13 and v[8] == "T":
        text = text + ", " + v[9:11] + ":" + v[11:13]
        if v.endswith("Z"):
            text = text + " UTC"
        elif "TZID" in params:
            text = text + " (" + params["TZID"] + ")"
    return text


def sort_key(value):
    v = value.replace("-", "").replace(":", "")
    return v[:15]
