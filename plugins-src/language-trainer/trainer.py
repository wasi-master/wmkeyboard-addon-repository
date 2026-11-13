# The trainer's logic, apart from drawing: letter tables, how well each item
# is known, which one to ask next, multiple-choice options and checking a
# typed answer. Nothing here talks to the keyboard, so the tests drive it
# directly.

import random

# ---------------------------------------------------------------- letters ---


def parse_table(text):
    """A category's table as [(glyph, romanization, note)]. Each line is
    "glyph romanization", then optionally " | note"."""
    rows = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        note = ""
        if " | " in line:
            line, note = line.split(" | ", 1)
        glyph, roman = line.split(" ", 1)
        rows.append((glyph, roman.strip(), note.strip()))
    return rows


def categories(module):
    """[(id, title, rows)] for a letters module."""
    return [(c[0], c[1], parse_table(c[2])) for c in module.CATEGORIES]


def shown_glyph(glyph, cased):
    """Both cases on a chart card: "Аа"."""
    if cased and glyph.upper() != glyph:
        return glyph.upper() + glyph
    return glyph


def label_for(rows, row):
    """A row's romanization, with its note when another row in the same table
    romanizes the same way, so a question never has two right answers that
    look alike."""
    same = 0
    for r in rows:
        if r[1] == row[1]:
            same += 1
    if same > 1 and row[2]:
        return row[1] + " (" + row[2] + ")"
    return row[1]


# --------------------------------------------------------------- progress ---

# Leitner boxes: 0 is new or just missed, 5 is known. How much more often a
# question from each box comes up, and how long after the last answer it is
# due again, in minutes.
BOX_WEIGHT = [8.0, 5.0, 3.0, 2.0, 1.2, 0.7]
BOX_WAIT = [0, 10, 60, 24 * 60, 3 * 24 * 60, 7 * 24 * 60]
NEW_WEIGHT = 4.0
KNOWN = 3


def record(progress, key):
    """[box, seen, right, last minute] for one item, or None."""
    return progress.get(key)


def mark(progress, key, right, now):
    """Moves an item up one box when answered right, back to the start when
    missed. [now] is in minutes."""
    r = progress.get(key)
    if r is None:
        r = [0, 0, 0, now]
    box, seen, good = r[0], r[1] + 1, r[2]
    if right:
        box = min(5, box + 1)
        good += 1
    else:
        box = 0
    progress[key] = [box, seen, good, now]
    return progress[key]


def weight(progress, key, now):
    r = progress.get(key)
    if r is None:
        return NEW_WEIGHT
    box = r[0]
    w = BOX_WEIGHT[box]
    wait = BOX_WAIT[box]
    if wait > 0:
        overdue = (now - r[3]) / wait
        w = w * (1 + min(3.0, max(0.0, overdue)))
    else:
        w = w * 2
    return w


def pick(keys, progress, now, recent=None, rng=None):
    """One key, drawn by weight: missed and long-unseen items far more often.
    Skips the [recent] keys while there are others."""
    rng = rng or random
    pool = keys
    if recent:
        others = [k for k in keys if k not in recent]
        if others:
            pool = others
    total = 0.0
    weights = []
    for k in pool:
        w = weight(progress, k, now)
        weights.append(w)
        total += w
    if total <= 0:
        return rng.choice(pool)
    at = rng.random() * total
    for i in range(len(pool)):
        at -= weights[i]
        if at <= 0:
            return pool[i]
    return pool[-1]


def mastery(progress, keys):
    """0..1: the share of the way to box 5, over [keys]."""
    if not keys:
        return 0.0
    total = 0
    for k in keys:
        r = progress.get(k)
        if r is not None:
            total += r[0]
    return total / (5.0 * len(keys))


def known_count(progress, keys):
    n = 0
    for k in keys:
        r = progress.get(k)
        if r is not None and r[0] >= KNOWN:
            n += 1
    return n


def weak(progress, keys, limit=10):
    """Seen items that are going worst: lowest box, then most missed."""
    rows = []
    for k in keys:
        r = progress.get(k)
        if r is None or r[1] == 0 or r[0] >= KNOWN:
            continue
        rows.append((r[0], -(r[1] - r[2]), k))
    rows.sort()
    return [row[2] for row in rows[:limit]]


# ---------------------------------------------------------------- options ---


def options(answer, candidates, n=4, rng=None):
    """[answer] and up to n-1 different texts from [candidates], shuffled."""
    rng = rng or random
    seen = {answer}
    others = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            others.append(c)
    rng.shuffle(others)
    chosen = others[:n - 1] + [answer]
    rng.shuffle(chosen)
    return chosen


# ----------------------------------------------------------------- typing ---

# Marks ordinary writing leaves out: the stress mark dictionaries put on
# Russian and Ukrainian, Hebrew vowel points, Arabic short vowels and
# tatweel. A typed answer without them is simply right.
_OPTIONAL_RANGES = [
    (0x0301, 0x0301),
    (0x0591, 0x05C7),
    (0x0610, 0x061A),
    (0x064B, 0x065F),
    (0x0670, 0x0670),
    (0x06D6, 0x06ED),
    (0x0640, 0x0640),
]

# Accents that are part of the spelling. Missing them still counts, with a
# note: "Mind the marks".
_ACCENT_RANGES = [(0x0300, 0x036F)]

_FOLD = {}
for _pair in ("áa àa âa äa ãa åa āa ăa ąa ée èe êe ëe ēe ěe ęe íi ìi îi ïi īi óo òo ôo öo õo ōo øo "
              "úu ùu ûu üu ūu ůu ýy ÿy ñn ńn ňn çc ćc čc śs šs şs źz żz žz ğg łl řr ťt ďd "
              "άα έε ήη ίι όο ύυ ώω ϊι ϋυ ΐι ΰυ ёе їі").split(" "):
    _FOLD[_pair[0]] = _pair[1]

# Letters Unicode keeps apart as one code point that keyboards type as two:
# Devanagari and Bengali nukta letters.
_SPLIT = {
    "\u0958": "\u0915\u093c", "\u0959": "\u0916\u093c", "\u095a": "\u0917\u093c", "\u095b": "\u091c\u093c",
    "\u095c": "\u0921\u093c", "\u095d": "\u0922\u093c", "\u095e": "\u092b\u093c", "\u095f": "\u092f\u093c",
    "\u09dc": "\u09a1\u09bc", "\u09dd": "\u09a2\u09bc", "\u09df": "\u09af\u09bc",
}

_PUNCT = " .,!?;:¡¿。、！？，「」『』・…\"'()-–—«»“”‘’؟،۔।॥"


# Strings here are grapheme clusters, so a mark never stands alone in one:
# marks come out with replace(), which works on code points.
def _chars(ranges):
    out = []
    for lo, hi in ranges:
        for c in range(lo, hi + 1):
            out.append(chr(c))
    return out


_OPTIONAL = _chars(_OPTIONAL_RANGES)
_ACCENTS = _chars(_ACCENT_RANGES)


def plain(text):
    """[text] as typed answers are compared: lower case, without punctuation,
    extra spaces or marks ordinary writing leaves out, and with nukta letters
    written as two code points."""
    s = text.lower()
    for m in _OPTIONAL:
        s = s.replace(m, "")
    out = []
    for ch in s:
        out.append(_SPLIT.get(ch, ch))
    s = "".join(out)
    words = []
    for w in s.split():
        w = w.strip(_PUNCT)
        if w:
            words.append(w)
    return " ".join(words)


def folded(text):
    """[plain] with accents dropped too."""
    s = plain(text)
    for m in _ACCENTS:
        s = s.replace(m, "")
    out = []
    for ch in s:
        out.append(_FOLD.get(ch, ch))
    return "".join(out)


def check(typed, answers):
    """"right" when [typed] matches one of [answers] as written, "accents"
    when it matches once accents and vowel marks are left out, else None."""
    t = plain(typed)
    if not t:
        return None
    for a in answers:
        if a and plain(a) == t:
            return "right"
    f = folded(typed)
    for a in answers:
        if a and folded(a) == f:
            return "accents"
    return None


# ------------------------------------------------------------ word order ---


def tokens(sentence):
    """A sentence as the pieces a word-order drill shuffles."""
    return [w for w in sentence.split(" ") if w]


def shuffled(items, rng=None):
    rng = rng or random
    out = list(items)
    for _ in range(4):
        rng.shuffle(out)
        if out != items or len(out) < 2:
            break
    return out
