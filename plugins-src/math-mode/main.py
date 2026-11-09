# Math Mode: type math the way you say it and get real Unicode.
#
#   x^2 -> x²        sqrt(2) -> √2      pi -> π        int_0^1 -> ∫₀¹
#   1/2 -> ½         a/b -> a⁄b         H_2O -> H₂O    \frac{a}{b} -> a⁄b
#   x in RR -> x ∈ ℝ  bb(R) -> 𝐑        f'(x) -> f′(x) 30 deg -> 30°
#
# Anything it does not understand passes through untouched, and half-typed
# input never breaks: the whole box is converted again after every keystroke,
# so `x^` stays `x^` until the `2` arrives.
#
# Shape of the engine: a tokenizer, then one left-to-right pass over a stack
# of "pieces". Postfix things (^ _ ' ! /) look back at the piece before them;
# prefix things (sqrt, bb, \frac) wait on the stack until their argument
# closes. No recursion and no patterns over the whole text, so an 8 KB paste
# converts inside the per-event budget.
#
# The text is worked on as a list of characters. Plugin strings are made of
# characters as a person sees them (grapheme clusters), so "x̂" is one
# character; everything the engine looks for is ASCII, and anything else is
# carried through as it came. The pass keeps its state in module globals
# (the names starting with an underscore) rather than passing it around.

# ================================================================== tables ==

ASCII = set(chr(c) for c in range(128))
DIGIT = set("0123456789")
UPPER = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
LOWER = set("abcdefghijklmnopqrstuvwxyz")
ALPHA = UPPER | LOWER
ALNUM = ALPHA | DIGIT
# "\r\n" is a single character in plugin strings.
SPACE = {" ", "\t", "\n", "\r", "\r\n"}
NEWLINE = {"\n", "\r", "\r\n"}
OPEN = {"(", "[", "{"}
CLOSE = {")", "]", "}"}
PAIRS = {"(": ")", "[": "]", "{": "}"}

GREEK = {}
GREEK_NAMES = [
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa",
    "lambda", "mu", "nu", "xi", "omicron", "pi", "rho", "sigma", "tau", "upsilon", "phi",
    "chi", "psi", "omega",
]
GREEK_CPS = [
    0x3B1, 0x3B2, 0x3B3, 0x3B4, 0x3B5, 0x3B6, 0x3B7, 0x3B8, 0x3B9, 0x3BA,
    0x3BB, 0x3BC, 0x3BD, 0x3BE, 0x3BF, 0x3C0, 0x3C1, 0x3C3, 0x3C4, 0x3C5, 0x3C6,
    0x3C7, 0x3C8, 0x3C9,
]
for _name, _cp in zip(GREEK_NAMES, GREEK_CPS):
    GREEK[_name] = chr(_cp)
    GREEK[_name[0].upper() + _name[1:]] = chr(_cp - 0x20)
GREEK["varepsilon"] = "ε"
GREEK["vartheta"] = "ϑ"
GREEK["varpi"] = "ϖ"
GREEK["varrho"] = "ϱ"
GREEK["varsigma"] = "ς"
GREEK["varphi"] = "φ"

# LaTeX draws these two differently from the bare words.
GREEK_CMD = {"epsilon": "ϵ", "phi": "ϕ"}

# Words that become a symbol on their own. Anything here is an atom (it can
# carry ^ and _) unless it is also listed in OP_WORDS below.
SYM = {
    "oo": "∞", "infty": "∞", "infinity": "∞",
    "hbar": "ℏ", "ell": "ℓ", "aleph": "ℵ", "nabla": "∇", "grad": "∇", "del": "∂", "partial": "∂",
    "emptyset": "∅", "varnothing": "∅",
    "RR": "ℝ", "NN": "ℕ", "ZZ": "ℤ", "QQ": "ℚ", "CC": "ℂ", "HH": "ℍ", "PP": "ℙ", "FF": "𝔽",
    "AA": "∀", "EE": "∃",
    "times": "×", "cross": "×", "xx": "×", "cdot": "⋅", "div": "÷",
    "pm": "±", "mp": "∓", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠",
    "approx": "≈", "equiv": "≡", "propto": "∝", "sim": "∼", "simeq": "≃", "cong": "≅",
    "notin": "∉", "ni": "∋", "subset": "⊂", "subseteq": "⊆", "supset": "⊃", "supseteq": "⊇",
    "union": "∪", "cup": "∪", "intersect": "∩", "cap": "∩", "setminus": "∖",
    "bigcup": "⋃", "bigcap": "⋂", "bigoplus": "⨁", "bigotimes": "⨂", "oplus": "⊕", "otimes": "⊗",
    "forall": "∀", "exists": "∃", "nexists": "∄", "therefore": "∴", "because": "∵",
    "implies": "⇒", "iff": "⇔", "xor": "⊻", "nand": "⊼", "nor": "⊽", "neg": "¬",
    "top": "⊤", "bot": "⊥",
    "sum": "∑", "prod": "∏", "coprod": "∐", "int": "∫", "integral": "∫", "iint": "∬", "iiint": "∭",
    "oint": "∮",
    "perp": "⊥", "parallel": "∥", "circ": "∘", "bullet": "•", "star": "⋆", "dagger": "†",
    "cdots": "⋯", "vdots": "⋮", "ddots": "⋱", "ldots": "…",
    "permil": "‰", "qed": "∎", "blacksquare": "■", "triangle": "△", "diamond": "◇",
    "langle": "⟨", "rangle": "⟩", "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉",
}

# Only reachable with a backslash: too English, or LaTeX-only spellings.
SYM_CMD = {
    "to": "→", "in": "∈", "land": "∧", "lor": "∨", "lnot": "¬", "wedge": "∧", "vee": "∨",
    "rightarrow": "→", "leftarrow": "←", "Rightarrow": "⇒", "Leftarrow": "⇐",
    "leftrightarrow": "↔", "Leftrightarrow": "⇔", "mapsto": "↦", "longrightarrow": "⟶",
    "degree": "°", "prime": "′", "square": "□", "Box": "□", "dots": "…", "mid": "∣",
    "and": "∧", "or": "∨", "not": "¬", "vdash": "⊢", "models": "⊨",
}

# Symbols that behave as operators: never a base for ^ or _, never a fraction
# operand.
OP_WORDS = set([
    "times", "cross", "xx", "cdot", "div", "pm", "mp", "leq", "le", "geq", "ge", "neq", "ne",
    "approx", "equiv", "propto", "sim", "simeq", "cong", "notin", "ni", "subset", "subseteq",
    "supset", "supseteq", "union", "cup", "intersect", "cap", "setminus", "oplus", "otimes",
    "implies", "iff", "xor", "nand", "nor", "neg", "perp", "parallel", "circ", "bullet", "star",
    "forall", "exists", "nexists", "therefore", "because", "AA", "EE", "top", "bot",
    "to", "in", "land", "lor", "lnot", "wedge", "vee", "rightarrow", "leftarrow", "Rightarrow",
    "Leftarrow", "leftrightarrow", "Leftrightarrow", "mapsto", "longrightarrow", "and", "or",
    "not", "vdash", "models", "mid", "langle", "rangle", "lfloor", "rfloor", "lceil", "rceil",
])

# English words that are operators only when the user asks for it.
WORD_OPS = {"and": "∧", "or": "∨", "not": "¬", "to": "→"}

# Function names stay as text. They matter in two places: `sin^2` reads as
# sin², and `e^ln(x)` must not turn into eˡⁿ(x).
FUNCS = set([
    "sin", "cos", "tan", "sec", "csc", "cot", "arcsin", "arccos", "arctan", "sinh", "cosh",
    "tanh", "ln", "log", "exp", "lim", "max", "min", "sup", "inf", "det", "dim", "ker", "gcd",
    "lcm", "arg", "deg", "mod", "argmax", "argmin", "sgn", "tr", "rank", "span", "Re", "Im",
    "limsup", "liminf",
])
STRICT_FUNCS = set([
    "sin", "cos", "tan", "sec", "csc", "cot", "arcsin", "arccos", "arctan", "sinh", "cosh",
    "tanh", "ln", "log", "exp",
])

ACCENT = {
    "vec": chr(0x20D7), "hat": chr(0x302), "bar": chr(0x304), "conj": chr(0x304),
    "dot": chr(0x307), "ddot": chr(0x308), "tilde": chr(0x303), "overline": chr(0x305),
    "underline": chr(0x332), "check": chr(0x30C), "breve": chr(0x306), "acute": chr(0x301),
    "grave": chr(0x300), "widehat": chr(0x302), "widetilde": chr(0x303),
}
WRAP = {
    "abs": ["|", "|"], "norm": ["‖", "‖"], "floor": ["⌊", "⌋"], "ceil": ["⌈", "⌉"],
}
STYLE = {
    "bold": {"up": 0x1D400, "lo": 0x1D41A, "dg": 0x1D7CE, "gup": 0x1D6A8, "glo": 0x1D6C2},
    "italic": {"up": 0x1D434, "lo": 0x1D44E, "gup": 0x1D6E2, "glo": 0x1D6FC, "ex": {"h": 0x210E}},
    "script": {
        "up": 0x1D49C, "lo": 0x1D4B6,
        "ex": {"B": 0x212C, "E": 0x2130, "F": 0x2131, "H": 0x210B, "I": 0x2110, "L": 0x2112,
               "M": 0x2133, "R": 0x211B, "e": 0x212F, "g": 0x210A, "o": 0x2134},
    },
    "fraktur": {"up": 0x1D504, "lo": 0x1D51E,
                "ex": {"C": 0x212D, "H": 0x210C, "I": 0x2111, "R": 0x211C, "Z": 0x2128}},
    "double": {
        "up": 0x1D538, "lo": 0x1D552, "dg": 0x1D7D8,
        "ex": {"C": 0x2102, "H": 0x210D, "N": 0x2115, "P": 0x2119, "Q": 0x211A, "R": 0x211D, "Z": 0x2124},
    },
    "sans": {"up": 0x1D5A0, "lo": 0x1D5BA, "dg": 0x1D7E2},
    "mono": {"up": 0x1D670, "lo": 0x1D68A, "dg": 0x1D7F6},
}
STYLE_NAME = {
    "bb": "bold", "bf": "bold", "mathbf": "bold", "textbf": "bold",
    "it": "italic", "mathit": "italic",
    "cc": "script", "cal": "script", "mathcal": "script", "mathscr": "script",
    "fr": "fraktur", "mathfrak": "fraktur",
    "bbb": "double", "mathbb": "double",
    "sf": "sans", "mathsf": "sans",
    "tt": "mono", "mathtt": "mono",
}
# \text{...} and friends: the inside is left exactly as typed.
VERBATIM_CMD = set(["text", "mathrm", "operatorname", "textrm", "mbox"])

# Prefix functions. `bare` ones also take a single atom without brackets
# (`sqrt 2`); `glyph` ones show their symbol as soon as they are typed.
PREFIX = set(["root", "abs", "norm", "floor", "ceil", "binom", "frac", "dfrac", "tfrac", "sqrt", "cbrt"])
PREFIX = PREFIX | set(ACCENT) | set(STYLE_NAME)
ROOT_GLYPH = {"sqrt": "√", "cbrt": "∛"}
ROOT_BY_INDEX = {"2": "√", "3": "∛", "4": "∜"}

SUP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
    "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ",
    "g": "ᵍ", "h": "ʰ", "i": "ⁱ", "j": "ʲ", "k": "ᵏ", "l": "ˡ",
    "m": "ᵐ", "n": "ⁿ", "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ",
    "t": "ᵗ", "u": "ᵘ", "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ",
    "z": "ᶻ",
    "A": "ᴬ", "B": "ᴮ", "D": "ᴰ", "E": "ᴱ", "G": "ᴳ", "H": "ᴴ",
    "I": "ᴵ", "J": "ᴶ", "K": "ᴷ", "L": "ᴸ", "M": "ᴹ", "N": "ᴺ",
    "O": "ᴼ", "P": "ᴾ", "R": "ᴿ", "T": "ᵀ", "U": "ᵁ", "V": "ⱽ",
    "W": "ᵂ",
    "β": "ᵝ", "γ": "ᵞ", "δ": "ᵟ", "ε": "ᵋ", "θ": "ᶿ", "ι": "ᶥ",
    "φ": "ᵠ", "χ": "ᵡ",
}
SUB = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
    "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ",
    "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "r": "ᵣ",
    "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
    "β": "ᵦ", "γ": "ᵧ", "ρ": "ᵨ", "φ": "ᵩ", "χ": "ᵪ",
}
SCRIPT_GLYPH = set(SUP.values()) | set(SUB.values())

VULGAR = {
    "1/2": "½", "1/3": "⅓", "2/3": "⅔", "1/4": "¼", "3/4": "¾",
    "1/5": "⅕", "2/5": "⅖", "3/5": "⅗", "4/5": "⅘", "1/6": "⅙", "5/6": "⅚",
    "1/7": "⅐", "1/8": "⅛", "3/8": "⅜", "5/8": "⅝", "7/8": "⅞", "1/9": "⅑",
    "1/10": "⅒",
}

# Longest match first. `<-` in front of a digit is handled in the tokenizer.
OPS = [
    ("<==>", "⇔"), ("<-->", "⟷"),
    ("<=>", "⇔"), ("<->", "↔"), ("-->", "⟶"), ("<--", "⟵"), ("==>", "⇒"),
    ("<==", "⇐"), ("|->", "↦"), ("|--", "⊢"), ("|==", "⊨"), ("===", "≡"),
    ("=/=", "≠"), ("+/-", "±"), ("-/+", "∓"), ("...", "…"),
    ("<=", "≤"), (">=", "≥"), ("!=", "≠"), ("<>", "≠"), ("~=", "≅"), ("~~", "≈"),
    ("->", "→"), ("<-", "←"), ("=>", "⇒"), ("+-", "±"), ("-+", "∓"), ("**", "**"),
    ("||", "‖"), ("<<", "≪"), (">>", "≫"), (":=", "≔"), ("=:", "≕"), ("-:", "÷"),
]

# OPS by first character, longest first as above. The tokenizer tries only
# the ones that can match here: walking all of OPS for every ASCII symbol
# was most of an 8 KB paste's budget.
OPS_BY_FIRST = {}
for _key, _glyph in OPS:
    OPS_BY_FIRST.setdefault(_key[0], []).append((_key, _glyph, len(_key)))

ELEMENTS = set("""H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn
  Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm
  Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U
  Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og""".split())

# ============================================================= characters ==


def first_cp(c):
    """The code point of a character that is one code point, else -1."""
    try:
        return ord(c)
    except TypeError:
        return -1


def is_combining(cp):
    return (0x300 <= cp <= 0x36F) or (0x20D0 <= cp <= 0x20FF)


def char_units(c):
    """UTF-16 units in one character, which is what every host limit counts."""
    if c in ASCII:
        return 1
    return len(c.encode("utf-16-le")) // 2


def at(cs, j):
    """The character at j, or "" past either end."""
    return cs[j] if 0 <= j < len(cs) else ""


def has_digit(s):
    for c in s:
        if c in DIGIT:
            return True
    return False


def has_two_lower(s):
    for j in range(len(s) - 1):
        if s[j] in LOWER and s[j + 1] in LOWER:
            return True
    return False


# ============================================================== tokenizer ==

MAX_SPLIT = 10  # longest word that splits off a digit: "varepsilon0"


def split_point(word):
    """`sqrt2` is `sqrt` and `2`; `DeltaH` is `Delta` and `H`. Never letter to
    letter (`pixel`, `sqrtx`), and only for names the engine knows."""
    n = len(word)
    limit = min(n - 1, MAX_SPLIT)
    for size in range(limit, 1, -1):
        head = word[:size]
        nb = word[size]
        if nb in DIGIT:
            if head in SYM or head in GREEK or head in PREFIX:
                return size
        elif nb in UPPER:
            if head in GREEK:
                return size
    # nZZ, xRR: a lowercase run followed by one of the blackboard sets
    if 3 <= n <= 4:
        tail = word[n - 2:]
        head = word[:n - 2]
        if tail in SYM and tail[0] in UPPER and tail[1] in UPPER and all(c in LOWER for c in head):
            return n - 2
    return None


def token(toks, k, v, s, e):
    t = {"k": k, "v": v, "s": s, "e": e}
    toks.append(t)
    return t


def tokenize(cs):
    """Splits a character list into tokens {k=kind, v=text, s=start, e=end}.
    Kinds: num word cmd quote verb op open close ws raw other."""
    toks = []
    n = len(cs)
    i = 0
    while i < n:
        c = cs[i]
        if c in SPACE:
            j = i
            nl = False
            while j < n:
                d = cs[j]
                if d in NEWLINE:
                    nl = True
                elif d != " " and d != "\t":
                    break
                j += 1
            token(toks, "ws", "".join(cs[i:j]), i, j - 1)["nl"] = nl
            i = j
        elif c in DIGIT or (c == "." and at(cs, i + 1) in DIGIT):
            j = i
            while at(cs, j) in DIGIT:
                j += 1
            if at(cs, j) == "." and at(cs, j + 1) in DIGIT:
                j += 1
                while at(cs, j) in DIGIT:
                    j += 1
            d = at(cs, j)
            if d == "e" or d == "E":
                k = j + 1
                if at(cs, k) == "+" or at(cs, k) == "-":
                    k += 1
                if at(cs, k) in DIGIT:
                    while at(cs, k) in DIGIT:
                        k += 1
                    j = k
            token(toks, "num", "".join(cs[i:j]), i, j - 1)
            i = j
        elif c in ALPHA:
            j = i + 1
            while at(cs, j) in ALNUM:
                j += 1
            word = "".join(cs[i:j])
            cut = split_point(word)
            if cut is not None:
                token(toks, "word", word[:cut], i, i + cut - 1)
                i += cut
            else:
                token(toks, "word", word, i, j - 1)
                i = j
        elif c == "\\":
            d = at(cs, i + 1)
            if d in ALPHA:
                j = i + 2
                while at(cs, j) in ALPHA:
                    j += 1
                token(toks, "cmd", "".join(cs[i + 1:j]), i, j - 1)
                i = j
            elif d != "" and d != "\\" and d != " " and d in ASCII and d not in ALNUM and d not in SPACE:
                token(toks, "cmd", d, i, i + 1)
                i += 2
            else:
                token(toks, "other", "\\", i, i)
                i += 1
        elif c == '"':
            # a "quoted" region is left exactly as typed
            j = i + 1
            while j < n and cs[j] != '"':
                j += 1
            if j < n:
                token(toks, "quote", "".join(cs[i + 1:j]), i, j)
                i = j + 1
            else:
                token(toks, "verb", "".join(cs[i:]), i, n - 1)
                i = n
        elif c in OPEN:
            token(toks, "open", c, i, i)
            i += 1
        elif c in CLOSE:
            token(toks, "close", c, i, i)
            i += 1
        elif c not in ASCII:
            j = i
            while j < n and cs[j] not in ASCII and cs[j] not in SPACE:
                j += 1
            run = "".join(cs[i:j])
            prev = toks[-1] if toks else None
            if (prev is not None and (prev["k"] == "word" or prev["k"] == "raw") and prev["e"] == i - 1
                    and is_combining(first_cp(c))):
                prev["v"] = prev["v"] + run
                prev["k"] = "raw"
                prev["e"] = j - 1
            else:
                token(toks, "raw", run, i, j - 1)
            i = j
        else:
            matched = False
            for key, glyph, size in OPS_BY_FIRST.get(c, ()):
                if "".join(cs[i:i + size]) == key:
                    j = i + size
                    if key == "..." and at(cs, j) == ".":
                        while at(cs, j) == ".":
                            j += 1
                        token(toks, "other", "".join(cs[i:j]), i, j - 1)
                    elif key == "**" and at(cs, j) == "*":
                        while at(cs, j) == "*":
                            j += 1
                        token(toks, "other", "".join(cs[i:j]), i, j - 1)
                    elif key == "<-" and (at(cs, j) in DIGIT or at(cs, j) == "."):
                        token(toks, "op", "<", i, i)
                        j = i + 1
                    else:
                        token(toks, "op", key, i, j - 1)["glyph"] = glyph
                    i = j
                    matched = True
                    break
            if not matched:
                token(toks, "op", c, i, i)
                i += 1
    return toks


# ================================================================ helpers ==


def scriptable(s, table):
    """Every character of s (spaces excepted) has a form in table."""
    if s == "":
        return False
    seen = False
    for c in s:
        if c != " " and c != "\t":
            if c not in table:
                return False
            seen = True
    return seen


def map_script(s, table):
    return "".join(table[c] for c in s if c != " " and c != "\t")


def all_script(s):
    """s consists only of superscript/subscript glyphs already."""
    if s == "":
        return False
    for c in s:
        if c not in SCRIPT_GLYPH:
            return False
    return True


def is_plain_digits(s):
    if s == "":
        return False
    for c in s:
        if c not in DIGIT:
            return False
    return True


def styled(s, style):
    st = STYLE[style]
    ex = st.get("ex", {})
    out = []
    for c in s:
        cp = None
        if c in ASCII:
            if c in ex:
                cp = ex[c]
            elif c in UPPER:
                cp = st["up"] + ord(c) - 65
            elif c in LOWER:
                cp = st["lo"] + ord(c) - 97
            elif c in DIGIT and "dg" in st:
                cp = st["dg"] + ord(c) - 48
        else:
            g = first_cp(c)
            if "glo" in st and 0x3B1 <= g <= 0x3C9:
                cp = st["glo"] + g - 0x3B1
            elif "gup" in st and 0x391 <= g <= 0x3A9:
                cp = st["gup"] + g - 0x391
        out.append(chr(cp) if cp is not None else c)
    return "".join(out)


def accented(s, mark):
    out = []
    for c in s:
        out.append(c)
        if c != " ":
            out.append(mark)
    return "".join(out)


def prime_run(n):
    out = []
    while n >= 4:
        out.append("⁗")
        n -= 4
    if n == 3:
        out.append("‴")
    elif n == 2:
        out.append("″")
    elif n == 1:
        out.append("′")
    return "".join(out)


def src_of(p):
    return p["src"] if p.get("src") is not None else p["t"]


# =============================================================== renderer ==

DEFAULTS = {
    "minus": True, "times": True, "frac": True, "small": True, "words": False,
    "prime": True, "chem": False, "italic": False, "rootline": False,
}
OPTION_KEYS = ["minus", "times", "frac", "small", "words", "prime", "chem", "italic", "rootline"]


def default_options():
    return dict(DEFAULTS)


MAX_DEPTH = 32
ATOM_START = set(["num", "word", "raw", "cmd", "open", "quote"])
JUXT_AFTER = set(["num", "word", "raw", "close", "quote"])
SCRIPTS = ("sup", "sub")

# The state of one conversion.
_cs = []      # the text, one character per item
_toks = []    # its tokens
_nt = 0       # how many
_out = []     # the piece stack
_opens = []   # indices of open-bracket markers in _out
_i = 0        # the token being looked at
_o = DEFAULTS # the options

# ---- small accessors -------------------------------------------------


def top():
    return _out[-1] if _out else None


def piece(k):
    return _out[k] if 0 <= k < len(_out) else None


def tok(k):
    return _toks[k] if 0 <= k < _nt else None


def peek(k):
    """Next non-whitespace token after index k, its index, whether any
    whitespace was skipped and whether it held a newline."""
    j = k + 1
    ws = False
    nl = False
    while j < _nt and _toks[j]["k"] == "ws":
        ws = True
        nl = nl or _toks[j]["nl"]
        j += 1
    return tok(j), j, ws, nl


def tok_is_atom_start(t):
    return t is not None and t["k"] in ATOM_START


def is_base(p):
    return p is not None and bool(p.get("atom") or p.get("bar")) and not p.get("pend")


def literal(t, src=None):
    if src is None:
        src = t
    return {"t": t, "src": src, "kind": "lit", "supok": src in SUP, "subok": src in SUB}


def atom(t, src, kind):
    return {"t": t, "src": src, "atom": True, "kind": kind,
            "supok": scriptable(src, SUP), "subok": scriptable(src, SUB)}


def literalize(p):
    p["pend"] = None
    p["atom"] = False
    p["kind"] = "lit"
    if p.get("ws_before") is not None:
        p["t"] = p["ws_before"] + p["t"]
    if p.get("ws_after") is not None:
        p["t"] = p["t"] + p["ws_after"]
    p["ws_before"] = None
    p["ws_after"] = None
    p["supok"] = False
    p["subok"] = False


def in_arg_group():
    return bool(_opens) and bool(_out[_opens[-1]].get("arg"))


# ---- building blocks -------------------------------------------------


def make_frac(left, right, chain, allow_small, parens_rule):
    """Builds a fraction piece from two operand pieces."""
    lt = left["t"]
    rt = right["t"]
    if parens_rule:
        if left.get("grp") and left.get("has_op"):
            lt = "(" + left["inner_t"] + ")"
        elif left.get("grp"):
            lt = left["inner_t"]
        if right.get("grp") and right.get("has_op"):
            rt = "(" + right["inner_t"] + ")"
        elif right.get("grp"):
            rt = right["inner_t"]
    p = {"atom": True, "kind": "frac", "mod": "frac", "supok": False, "subok": False}
    p["src"] = left["src"] + "/" + right["src"]
    plain = (not chain and allow_small and _o["small"]
             and left.get("kind") == "num" and right.get("kind") == "num"
             and not left.get("mod") and not right.get("mod")
             and not left.get("signed") and not right.get("signed") and not left.get("juxt")
             and is_plain_digits(left["src"]) and is_plain_digits(right["src"]))
    if plain:
        v = VULGAR.get(left["src"] + "/" + right["src"])
        p["t"] = v if v is not None else map_script(left["src"], SUP) + "⁄" + map_script(right["src"], SUB)
        p["vulgar"] = True
    elif chain:
        p["t"] = lt + "/" + rt
        p["chain"] = True
    elif _o["frac"]:
        p["t"] = lt + "⁄" + rt
    else:
        p["t"] = lt + "/" + rt
    return p


def make_binom(n, k):
    if n.get("supok") and k.get("subok"):
        return atom("(" + map_script(n["src"], SUP) + map_script(k["src"], SUB) + ")",
                    "(" + n["src"] + " " + k["src"] + ")", "binom")
    return None


def attach_at(k):
    """Merges base, pending ^/_, and argument at k-1, k, k+1 into one atom at k-1."""
    base = piece(k - 1)
    pend = _out[k]
    arg = _out[k + 1]
    sup = pend["pend"] == "sup"
    table = SUP if sup else SUB
    ok = arg.get("supok") if sup else arg.get("subok")
    if arg.get("guard"):
        ok = False
    m = {"atom": True, "kind": base.get("kind"), "mod": "sup" if sup else "sub",
         "bar": base.get("bar"), "supok": False, "subok": False}
    if arg.get("circ") and sup:
        m["t"] = base["t"] + "°"
    elif arg.get("primecmd") and sup:
        m["t"] = base["t"] + "′"
    elif arg.get("kind") == "raw" and all_script(arg["t"]):
        m["t"] = base["t"] + arg["t"]
    elif ok:
        bt = base["t"]
        if sup and base.get("kind") == "root" and not base.get("mod"):
            bt = "(" + bt + ")"
        m["t"] = bt + map_script(arg["inner_src"] if arg.get("grp") else arg["src"], table)
    else:
        if arg.get("grp"):
            inner = arg["inner_t"] if arg.get("single") else arg["t"]
        elif arg.get("mod") or arg.get("kind") == "frac":
            inner = "(" + arg["t"] + ")"
        else:
            inner = arg["t"]
        m["t"] = base["t"] + pend["t"] + inner
    m["src"] = base["src"] + pend["src"] + arg["src"]
    _out[k - 1] = m
    _out.pop(k + 1)
    _out.pop(k)


def consume(k, p):
    _out[k] = p
    _out.pop(k + 1)


def absorb(k):
    """A function with more than one argument keeps waiting, with this one."""
    fn = _out[k]
    arg = _out[k + 1]
    fn["t"] = fn["t"] + arg["t"]
    fn["src"] = fn["src"] + arg["src"]
    _out.pop(k + 1)


def apply_at(k):
    """Applies the pending prefix function at k to the atom at k+1. Returns
    True when it consumed the atom (or kept waiting with it absorbed)."""
    fn = _out[k]
    arg = _out[k + 1]
    name = fn.get("name")
    family = fn.get("family")
    if family == "root":
        if name == "root" and not fn.get("index"):
            if arg.get("grp"):
                fn["index"] = arg
                absorb(k)
                return True
            literalize(fn)
            return False
        if name == "sqrt" and not fn.get("index") and arg.get("grp") and arg.get("bracket") == "[":
            fn["index"] = arg
            absorb(k)
            return True
        if not arg.get("grp") and not fn.get("bare"):
            literalize(fn)
            return False
        glyph = fn.get("glyph")
        if fn.get("index"):
            idx = fn["index"]
            glyph = ROOT_BY_INDEX.get(idx["inner_src"]) if idx.get("single") else None
            if not glyph:
                if idx.get("supok"):
                    glyph = map_script(idx["inner_src"], SUP) + "√"
                else:
                    literalize(fn)
                    return False
        if arg.get("grp"):
            if (arg.get("single") and arg.get("inner_mod") != "sup" and arg.get("inner_mod") != "prime"
                    and arg.get("inner_kind") != "frac"):
                body = arg["inner_t"]
            elif _o["rootline"]:
                body = accented(arg["inner_t"], chr(0x305))
            else:
                body = "(" + arg["inner_t"] + ")"
        else:
            body = arg["t"]
        consume(k, {"t": glyph + body, "src": fn["src"] + arg["src"], "atom": True, "kind": "root",
                    "supok": False, "subok": False})
        return True
    if family == "accent":
        if arg.get("grp") and arg.get("simple"):
            consume(k, {"t": accented(arg["inner_t"], ACCENT[name]), "src": arg["inner_src"], "atom": True,
                        "kind": "accent", "supok": False, "subok": False})
            return True
        literalize(fn)
        return False
    if family == "wrap":
        if arg.get("grp"):
            w = WRAP[name]
            consume(k, {"t": w[0] + arg["inner_t"] + w[1], "src": fn["src"] + arg["src"], "atom": True,
                        "kind": "wrap", "supok": False, "subok": False})
            return True
        literalize(fn)
        return False
    if family == "style":
        if arg.get("grp") and arg["inner_t"] != "":
            consume(k, {"t": styled(arg["inner_t"], STYLE_NAME[name]), "src": arg["inner_src"], "atom": True,
                        "kind": "style", "supok": False, "subok": False})
            return True
        literalize(fn)
        return False
    if family == "binom":
        if not arg.get("grp"):
            literalize(fn)
            return False
        if arg.get("pair"):
            p = make_binom(arg["pair"][0], arg["pair"][1])
            if p:
                consume(k, p)
                return True
            literalize(fn)
            return False
        if not fn.get("num"):
            fn["num"] = arg
            absorb(k)
            return True
        num = fn["num"]["single_piece"] if fn["num"].get("single") else None
        den = arg["single_piece"] if arg.get("single") else None
        p = make_binom(num, den) if num and den else None
        if p:
            consume(k, p)
            return True
        literalize(fn)
        return False
    if family == "frac":
        if not arg.get("grp"):
            literalize(fn)
            return False
        if not fn.get("num"):
            fn["num"] = arg
            absorb(k)
            return True
        num = fn["num"]
        den = arg
        consume(k, make_frac(num["single_piece"] if num.get("single") else num,
                             den["single_piece"] if den.get("single") else den, False, True, True))
        return True
    literalize(fn)
    return False


def flush(lo):
    """Resolves every pending piece from the top of the stack down to index
    lo: attach what has an argument, spell out what does not."""
    k = len(_out) - 1
    while k >= lo:
        p = piece(k)
        if p is not None and p.get("pend"):
            nxt = piece(k + 1)
            if p["pend"] == "open":
                literalize(p)
            elif nxt is not None and nxt.get("atom"):
                if p["pend"] in SCRIPTS:
                    attach_at(k)
                elif p["pend"] == "fn":
                    apply_at(k)
                elif p["pend"] == "frac":
                    left = piece(k - 1)
                    if is_base(left):
                        _out[k - 1] = make_frac(left, nxt, False, not in_arg_group(), False)
                        _out.pop(k + 1)
                        _out.pop(k)
                    else:
                        literalize(p)
            else:
                literalize(p)
        k -= 1


def settle():
    """After an atom lands on top: attach pending ^ _ / and prefix functions
    below it, unless something to the right should bind first."""
    while True:
        k = len(_out) - 1
        a = piece(k)
        if a is None or not a.get("atom"):
            return
        below = piece(k - 1)
        bp = below.get("pend") if below is not None else None
        nxt, _j, ws, nl = peek(_i)
        if nxt is not None and nxt["k"] == "op" and (nxt["v"] == "'" or nxt["v"] == "!") and not ws:
            return
        coming = nxt is not None and nxt["k"] == "op" and nxt["v"] in ("^", "_", "**") and not nl
        if coming:
            if bp in SCRIPTS and not (bp == "sup" and nxt["v"] != "_"):
                attach_at(k - 1)
            elif bp == "fn":
                if not apply_at(k - 1):
                    return
            else:
                return
        elif bp:
            if bp in SCRIPTS:
                attach_at(k - 1)
            elif bp == "fn":
                if not apply_at(k - 1):
                    return
            elif bp == "frac":
                left = piece(k - 2)
                if is_base(left):
                    chain = nxt is not None and nxt["k"] == "op" and nxt["v"] == "/" and not ws
                    _out[k - 2] = make_frac(left, a, chain, not in_arg_group(), False)
                    _out.pop(k)
                    _out.pop(k - 1)
                else:
                    literalize(below)
                    return
            else:
                return
        else:
            return


def resolve_below(tp):
    """Before a postfix (' or !) lands on the top atom, anything pending right
    under it (a ^, a _, or a prefix function) binds first."""
    while tp is not None and tp.get("atom"):
        below = piece(len(_out) - 2)
        bp = below.get("pend") if below is not None else None
        if bp in SCRIPTS:
            attach_at(len(_out) - 2)
        elif bp == "fn":
            if not apply_at(len(_out) - 2):
                break
        else:
            break
        tp = top()
    return tp


def push_atom(p):
    """Pushes an atom, merging a waiting sign into it first."""
    tp = top()
    if tp is not None and tp.get("sign"):
        _out.pop()
        p["t"] = tp["t"] + p["t"]
        p["src"] = tp["src"] + p["src"]
        p["signed"] = True
    prev = tok(_i - 1)
    if prev is not None and prev["k"] in JUXT_AFTER:
        p["juxt"] = True
    _out.append(p)
    settle()


def skip_ws_after(p, want_atom):
    """Skips one whitespace run (no newline) after the current token when a
    usable argument follows; remembers it for the literal fallback."""
    global _i
    nx = tok(_i + 1)
    if nx is not None and nx["k"] == "ws" and not nx["nl"]:
        after = tok(_i + 2)
        if after is not None and (after["k"] == "open" or (want_atom and tok_is_atom_start(after))):
            p["ws_after"] = nx["v"]
            _i += 1


def push_prefix(name, family, t, src, glyph=None, bare=False):
    p = {"pend": "fn", "name": name, "family": family, "t": t, "src": src, "glyph": glyph, "bare": bare}
    _out.append(p)
    skip_ws_after(p, bare)


def symbol_for(word, is_cmd):
    """Symbol lookup for a word or a backslash command."""
    g = GREEK_CMD.get(word) if is_cmd else None
    if g is None:
        g = GREEK.get(word)
    if g is None:
        g = SYM.get(word)
    if g is None and is_cmd:
        g = SYM_CMD.get(word)
    return g


def push_symbol(word, glyph):
    if word in OP_WORDS:
        _out.append({"t": glyph, "src": word, "kind": "op"})
    else:
        p = atom(glyph, glyph, "sym")
        if word == "circ":
            p["circ"] = True
        push_atom(p)


def close_group(m, closer):
    """Closes the group whose marker sits at index m."""
    flush(m + 1)
    marker = _out[m]
    inner = _out[m + 1:]
    tt = []
    ss = []
    count = 0
    has_op = False
    simple = True
    supok = True
    subok = True
    last_atom = None
    for p in inner:
        tt.append(p["t"])
        ss.append(src_of(p))
        if p.get("kind") != "ws":
            count += 1
            if p.get("atom"):
                last_atom = p
                if p.get("mod") or p.get("kind") not in ("num", "word", "sym", "raw"):
                    simple = False
            else:
                has_op = True
                simple = False
            if not p.get("supok"):
                supok = False
            if not p.get("subok"):
                subok = False
        else:
            simple = False
    # (n choose k) and (a, b) shapes for binomials
    pair = None
    if (len(inner) == 5 and inner[0].get("atom") and inner[2].get("kind") == "word"
            and inner[2]["t"] == "choose" and inner[4].get("atom")):
        pair = [inner[0], inner[4]]
    elif len(inner) == 3 and inner[0].get("atom") and inner[1].get("src") == "," and inner[2].get("atom"):
        pair = [inner[0], inner[2]]
    while len(_out) > m:
        _out.pop()
    _opens.pop()
    inner_t = "".join(tt)
    inner_src = "".join(ss)
    g = {
        "atom": True, "grp": True, "bracket": marker["bracket"], "kind": "grp",
        "inner_t": inner_t, "inner_src": inner_src,
        "t": marker["bracket"] + inner_t + closer,
        "src": marker["bracket"] + inner_src + closer,
        "has_op": has_op, "simple": simple and count > 0,
        "single": count == 1 and last_atom is not None and not has_op,
        "supok": supok and count > 0, "subok": subok and count > 0,
        "pair": pair,
    }
    if g["single"]:
        g["single_piece"] = last_atom
        g["inner_mod"] = last_atom.get("mod")
        g["inner_kind"] = last_atom.get("kind")
        if last_atom.get("circ"):
            g["circ"] = True
        if last_atom.get("kind") == "frac":
            g["single"] = False
    if pair is not None and len(inner) == 5:
        b = make_binom(pair[0], pair[1])
        if b:
            push_atom(b)
            return
    push_atom(g)


# ---- one token at a time ----------------------------------------------


def on_word(v):
    global _i
    nxt, _j, ws_after, nl_after = peek(_i)
    prev = tok(_i - 1)
    prev_ws = prev is not None and prev["k"] == "ws"
    prev_tok = tok(_i - 2) if prev_ws else prev
    tp = top()

    # chemistry: H2O
    if _o["chem"] and v[0] in UPPER and has_digit(v) and not has_two_lower(v):
        okc = True
        parts = []
        j = 0
        while j < len(v):
            sym = v[j]
            if j + 1 < len(v) and v[j + 1] in LOWER:
                sym = sym + v[j + 1]
            if not (sym[0] in UPPER and sym in ELEMENTS):
                okc = False
                break
            j += len(sym)
            ds = j
            while j < len(v) and v[j] in DIGIT:
                j += 1
            parts.append(sym + map_script(v[ds:j], SUB))
        if okc:
            p = atom("".join(parts), v, "word")
            p["mod"] = "sub"
            p["supok"] = False
            p["subok"] = False
            push_atom(p)
            return

    if (v == "x" and prev_ws and not prev.get("nl") and prev_tok is not None and prev_tok["k"] == "num"
            and ws_after and not nl_after and nxt is not None and nxt["k"] == "num"):
        _out.append({"t": "×", "src": "x", "kind": "op"})
    elif (v == "in" and prev_ws and prev_tok is not None and prev_tok["k"] in ("num", "word", "raw", "close")
          and ws_after and nxt is not None
          and ((nxt["k"] == "word" and (nxt["v"][0] in UPPER or nxt["v"] in SYM or nxt["v"] in GREEK))
               or nxt["k"] in ("open", "raw", "cmd"))):
        # x in RR, x in {1,2}, x not in A
        below = piece(len(_out) - 2)
        if (tp is not None and tp.get("kind") == "ws" and below is not None and below.get("kind") == "word"
                and below.get("src") == "not" and not below.get("mod")):
            _out.pop()
            _out[len(_out) - 1] = {"t": "∉", "src": "notin", "kind": "op"}
        else:
            _out.append({"t": "∈", "src": "in", "kind": "op"})
    elif (v in ("deg", "degree", "degrees") and tp is not None
          and ((tp.get("atom") and tp.get("kind") == "num" and not prev_ws)
               or (tp.get("kind") == "ws" and not prev.get("nl") and piece(len(_out) - 2) is not None
                   and piece(len(_out) - 2).get("atom") and piece(len(_out) - 2).get("kind") == "num"))):
        unit = None
        if nxt is not None and nxt["k"] == "word" and nxt["v"] in ("C", "F") and ws_after and not nl_after:
            unit = nxt["v"]
        if unit is not None:
            _out.append({"t": "°" + unit, "src": "deg" + unit, "kind": "unit"})
            _i += 2
        else:
            if tp.get("kind") == "ws":
                _out.pop()
            num = _out[len(_out) - 1]
            num["t"] = num["t"] + "°"
            num["src"] = num["src"] + "deg"
            num["supok"] = False
            num["subok"] = False
            num["mod"] = "unit"
    elif v == "degC" or v == "degF":
        _out.append({"t": "°" + v[3], "src": v, "kind": "unit"})
    elif v == "angle" and ws_after and not nl_after and nxt is not None and nxt["k"] == "word" and nxt["v"][0] in UPPER:
        _out.append({"t": "∠", "src": v, "kind": "op"})
    elif v == "dot" and not (nxt is not None and nxt["k"] == "open" and not ws_after):
        if prev_ws and ws_after:
            _out.append({"t": "⋅", "src": v, "kind": "op"})
        else:
            push_atom(atom(v, v, "word"))
    elif (v in WORD_OPS and _o["words"] and (prev_ws or _i == 0 or (prev is not None and prev["k"] == "open"))
          and (ws_after or (v == "not" and nxt is not None and nxt["k"] == "open"))):
        _out.append({"t": WORD_OPS[v], "src": v, "kind": "op"})
    elif v in PREFIX:
        if v in ROOT_GLYPH:
            push_prefix(v, "root", ROOT_GLYPH[v], v, ROOT_GLYPH[v], True)
        elif v == "root":
            push_prefix(v, "root", v, v, None, False)
        elif v in ACCENT:
            push_prefix(v, "accent", v, v)
        elif v in WRAP:
            push_prefix(v, "wrap", v, v)
        elif v in STYLE_NAME:
            push_prefix(v, "style", v, v)
        elif v == "binom":
            push_prefix(v, "binom", v, v)
        else:
            push_prefix(v, "frac", v, v)
    elif symbol_for(v, False) is not None:
        push_symbol(v, symbol_for(v, False))
    else:
        p = atom(v, v, "word")
        if v in FUNCS:
            nx = tok(_i + 1)
            if ((nx is not None and nx["k"] == "open")
                    or (v in STRICT_FUNCS and ws_after and not nl_after and tok_is_atom_start(nxt))):
                p["guard"] = True
        if (_o["italic"] and len(v) <= 2 and v not in FUNCS and not has_digit(v)
                and not (len(v) == 2 and v[0] == "d")
                and not (tp is not None and tp.get("pend") in SCRIPTS) and not in_arg_group()):
            p["t"] = styled(v, "italic")
        push_atom(p)


def on_cmd(v):
    global _i
    tp = top()
    if v[0] not in ALPHA:
        # \, \; \: are thin spaces, \! is nothing, anything else is itself
        if v == "," or v == ";" or v == ":":
            _out.append({"t": " ", "src": " ", "kind": "ws", "supok": True, "subok": True})
        elif v != "!":
            _out.append(literal(v))
    elif v == "left" or v == "right":
        nx = tok(_i + 1)
        if nx is not None and nx["k"] == "op" and nx["v"] == ".":
            _i += 1
    elif v == "quad":
        _out.append({"t": chr(0x2003), "src": " ", "kind": "ws", "supok": True, "subok": True})
    elif v == "qquad":
        _out.append({"t": chr(0x2003) + chr(0x2003), "src": " ", "kind": "ws", "supok": True, "subok": True})
    elif v in VERBATIM_CMD:
        nx = tok(_i + 1)
        if nx is not None and nx["k"] == "open" and nx["v"] == "{":
            depth = 0
            j = _i + 1
            closed = None
            while j < _nt:
                t = _toks[j]
                if t["k"] == "open" and t["v"] == "{":
                    depth += 1
                elif t["k"] == "close" and t["v"] == "}":
                    depth -= 1
                    if depth == 0:
                        closed = j
                        break
                j += 1
            if closed is not None:
                body = "".join(_cs[_toks[_i + 1]["e"] + 1:_toks[closed]["s"]])
                p = atom(body, body, "quote")
                p["supok"] = False
                p["subok"] = False
                push_atom(p)
                _i = closed
            else:
                _out.append(literal("\\" + v))
        else:
            _out.append(literal("\\" + v))
    elif v == "circ" and tp is not None and (tp.get("pend") == "sup" or (tp.get("pend") == "open" and tp.get("arg"))):
        push_atom({"t": "∘", "src": "circ", "atom": True, "kind": "sym", "circ": True, "supok": False, "subok": False})
    elif v == "prime":
        if tp is not None and tp.get("pend") == "sup":
            push_atom({"t": "′", "src": "prime", "atom": True, "kind": "sym", "primecmd": True,
                       "supok": False, "subok": False})
        else:
            _out.append({"t": "′", "src": v, "kind": "op"})
    elif v == "sqrt":
        push_prefix("sqrt", "root", "√", "\\sqrt", "√", True)
    elif v == "frac" or v == "dfrac" or v == "tfrac":
        push_prefix(v, "frac", "\\" + v, "\\" + v)
    elif v == "binom":
        push_prefix(v, "binom", "\\" + v, "\\" + v)
    elif v in ACCENT:
        push_prefix(v, "accent", "\\" + v, "\\" + v)
    elif v in STYLE_NAME:
        push_prefix(v, "style", "\\" + v, "\\" + v)
    elif v in WRAP:
        push_prefix(v, "wrap", "\\" + v, "\\" + v)
    elif symbol_for(v, True) is not None:
        push_symbol(v, symbol_for(v, True))
    elif v in FUNCS:
        push_atom(atom(v, v, "word"))
    else:
        _out.append(literal("\\" + v))


def on_op(tk, v):
    global _i
    tp = top()
    nx = tok(_i + 1)
    prev = tok(_i - 1)

    if v == "^" or v == "_" or v == "**":
        base = tp
        ws_before = None
        if tp is not None and tp.get("kind") == "ws" and not prev.get("nl") and is_base(piece(len(_out) - 2)):
            ws_before = tp["t"]
            base = piece(len(_out) - 2)
        if is_base(base) and v != "_" and nx is not None and nx["k"] == "op" and nx["v"] == "*":
            if ws_before is not None:
                _out.pop()
            base["t"] = base["t"] + "*"
            base["src"] = base["src"] + "*"
            base["mod"] = "sup"
            base["supok"] = False
            base["subok"] = False
            _i += 1
        elif is_base(base):
            if ws_before is not None:
                _out.pop()
            p = {"pend": "sub" if v == "_" else "sup", "t": v, "src": v, "ws_before": ws_before}
            _out.append(p)
            skip_ws_after(p, True)
        else:
            _out.append(literal(v))

    elif v == "/":
        if (is_base(tp) and prev is not None and prev["k"] != "ws" and nx is not None and nx["k"] != "ws"
                and not (nx["k"] == "op" and nx["v"] == "/")):
            below = piece(len(_out) - 2)
            if tp.get("chain") or (below is not None and below.get("chainslash")):
                _out.append({"t": "/", "src": "/", "kind": "lit", "chainslash": True})
            else:
                _out.append({"pend": "frac", "t": "/", "src": "/"})
        else:
            _out.append(literal("/"))

    elif v == "-" or v == "+":
        glyph = "−" if (v == "-" and _o["minus"]) else v
        if tp is not None and tp.get("pend") in ("sup", "sub", "frac"):
            if tok_is_atom_start(nx):
                _out.append({"t": glyph, "src": v, "sign": True, "kind": "sign"})
            else:
                push_atom({"t": glyph, "src": v, "atom": True, "kind": "sign", "supok": True, "subok": True})
        elif (_o["chem"] and tp is not None and tp.get("atom") and tp.get("mod") == "sup" and tp.get("justsup")
              and not tok_is_atom_start(nx)):
            tp["t"] = tp["t"] + SUP[v]
            tp["src"] = tp["src"] + v
        elif v == "-":
            at_line_start = (_i == 0) or (prev is not None and prev["k"] == "ws" and (prev["nl"] or _i == 1))
            if at_line_start and nx is not None and nx["k"] == "ws":
                _out.append(literal("-"))
            elif (prev is not None and prev["k"] == "word" and nx is not None and nx["k"] == "word"
                  and len(nx["v"]) >= 2 and nx["v"] not in SYM and nx["v"] not in GREEK):
                _out.append(literal("-"))
            else:
                _out.append({"t": glyph, "src": "-", "kind": "op", "supok": True, "subok": True})
        else:
            _out.append({"t": "+", "src": "+", "kind": "op", "supok": True, "subok": True})

    elif v == "*":
        _out.append({"t": "×" if _o["times"] else "⋅", "src": "*", "kind": "op"})

    elif v == "'":
        tp = resolve_below(tp)
        j = _i
        while tok(j + 1) is not None and tok(j + 1)["k"] == "op" and tok(j + 1)["v"] == "'":
            j += 1
        n = j - _i + 1
        after = tok(j + 1)
        ok = (_o["prime"] and tp is not None and tp.get("atom") and not tp.get("pend")
              and ((tp.get("kind") == "word" and len(tp["src"]) == 1) or tp.get("grp") or tp.get("mod")
                   or tp.get("kind") in ("raw", "sym", "root", "accent", "wrap", "style"))
              and not (after is not None and after["k"] == "word"))
        if ok:
            tp["t"] = tp["t"] + prime_run(n)
            tp["src"] = tp["src"] + "'" * n
            tp["mod"] = "prime"
            tp["supok"] = False
            tp["subok"] = False
            _i = j
            settle()
        else:
            for _ in range(n):
                _out.append(literal("'"))
            _i = j

    elif v == "!":
        tp = resolve_below(tp)
        if nx is not None and nx["k"] == "word" and nx["v"] == "in":
            _out.append({"t": "∉", "src": "!in", "kind": "op"})
            _i += 1
        elif tp is not None and tp.get("atom") and not tp.get("pend"):
            tp["t"] = tp["t"] + "!"
            tp["src"] = tp["src"] + "!"
            tp["supok"] = False
            tp["subok"] = False
            if not tp.get("mod"):
                tp["mod"] = "fact"
            settle()
        else:
            _out.append(literal("!"))

    elif v == "|" or v == "||":
        _out.append({"t": "‖" if v == "||" else "|", "src": v, "kind": "op", "bar": True})

    elif tk.get("glyph") is not None:
        g = tk["glyph"]
        if v == "<=>" and _o["chem"]:
            g = "⇌"
        _out.append({"t": g, "src": v, "kind": "op"})

    else:
        _out.append(literal(v))


# ---- the pass ---------------------------------------------------------


def render_math(text, o):
    """The engine. Text in, Unicode out."""
    global _cs, _toks, _nt, _out, _opens, _i, _o
    _o = o
    _cs = list(text)
    _toks = tokenize(_cs)
    _nt = len(_toks)
    _out = []
    _opens = []
    _i = 0

    while _i < _nt:
        tk = _toks[_i]
        k = tk["k"]
        v = tk["v"]

        if k == "ws":
            _out.append({"t": v, "src": v, "kind": "ws", "supok": True, "subok": True})

        elif k == "num":
            p = atom(v, v, "num")
            prev = tok(_i - 1)
            if _o["chem"] and prev is not None and prev["k"] == "close" and is_plain_digits(v):
                p["t"] = map_script(v, SUB)
                p["mod"] = "sub"
                p["supok"] = False
                p["subok"] = False
            push_atom(p)

        elif k == "raw" or k == "quote" or k == "verb":
            if k == "quote" and v == "":
                _out.append(literal('""'))
            else:
                p = atom(v, v, "raw" if k == "raw" else "quote")
                if k != "raw":
                    p["supok"] = False
                    p["subok"] = False
                push_atom(p)

        elif k == "open":
            if len(_opens) >= MAX_DEPTH:
                _out.append(literal(v))
            else:
                tp = top()
                marker = {"pend": "open", "bracket": v, "t": v, "src": v}
                if tp is not None and tp.get("pend") in SCRIPTS:
                    marker["arg"] = True
                _out.append(marker)
                _opens.append(len(_out) - 1)

        elif k == "close":
            m = _opens[-1] if _opens else None
            bracket = _out[m].get("bracket") if m is not None else None
            if bracket is not None and PAIRS[bracket] == v:
                close_group(m, v)
            else:
                _out.append(literal(v))

        elif k == "word":
            on_word(v)

        elif k == "cmd":
            on_cmd(v)

        elif k == "other":
            _out.append(literal(v))

        elif k == "op":
            on_op(tk, v)

        # chem: remember an atom that just took a superscript so a trailing
        # sign can join it
        tp = top()
        if tp is not None and tp.get("atom"):
            tp["justsup"] = tp.get("mod") == "sup" and k in ("num", "word", "close", "raw")
        _i += 1

    flush(0)
    return "".join(p["t"] for p in _out)


def convert(text, opts=None):
    """Public entry: never raises."""
    if text is None or text == "":
        return ""
    o = opts if opts is not None else DEFAULTS
    try:
        return render_math(text, o)
    except Exception as error:
        wm.log("convert failed:", error)
        return text


# ================================================================ chunking ==

OUTPUT_LIMIT = 2000
BREAKS = set(["\n", " ", "\r\n"])


def chunk(s):
    """Splits s into pieces of at most OUTPUT_LIMIT UTF-16 units, cutting at a
    newline or space where one is near."""
    pieces = []
    cs = list(s)
    n = len(cs)
    start = 0
    count = 0
    last_break = None
    k = 0
    while k < n:
        c = cs[k]
        u = char_units(c)
        if count + u > OUTPUT_LIMIT:
            cut = last_break if last_break is not None else k - 1
            pieces.append("".join(cs[start:cut + 1]))
            start = cut + 1
            count = 0
            last_break = None
            k = start
        else:
            count += u
            if c in BREAKS:
                last_break = k
            k += 1
    if start < n:
        pieces.append("".join(cs[start:]))
    return pieces


# =================================================================== panel ==

opts = default_options()
expr = ""
output = ""
chunks = []

try:
    has_storage = wm.storage is not None
except AttributeError:
    has_storage = False


def encode_opts():
    return ";".join(key + "=" + ("1" if opts[key] else "0") for key in OPTION_KEYS)


def decode_opts(s):
    if not isinstance(s, str):
        return
    for part in s.split(";"):
        key, _sep, val = part.partition("=")
        if key in DEFAULTS and val[:1] in DIGIT:
            opts[key] = val[:1] == "1"


def save_opts():
    if has_storage:
        try:
            wm.storage.set("options", encode_opts())
        except ValueError as error:
            wm.log("could not save options:", error)


def reconvert():
    global output, chunks
    output = convert(expr, opts)
    chunks = chunk(output)


if has_storage:
    try:
        decode_opts(wm.storage.get("options"))
    except Exception as error:
        wm.log("could not read options:", error)

SYMBOL_ROWS = [
    ["α", "β", "γ", "δ", "ε", "θ"],
    ["λ", "μ", "π", "σ", "φ", "ω"],
    ["Δ", "Σ", "Π", "Ω", "∞", "∂"],
    ["±", "×", "÷", "⋅", "√", "∛"],
    ["≤", "≥", "≠", "≈", "≡", "∝"],
    ["→", "←", "↔", "⇒", "⇔", "↦"],
    ["∫", "∬", "∮", "∑", "∏", "∇"],
    ["∈", "∉", "⊂", "⊆", "∪", "∩"],
    ["∀", "∃", "∧", "∨", "¬", "∴"],
    ["ℝ", "ℕ", "ℤ", "ℚ", "ℂ", "∅"],
    ["°", "′", "″", "∠", "⊥", "⁄"],
]

OPTION_LABELS = {
    "minus": "Typographic minus (−)",
    "times": "Multiply with × (off: ⋅)",
    "frac": "Fraction slash a⁄b (off: a/b)",
    "small": "Small number fractions ½ ³⁄₄",
    "words": "Word operators: and, or, not, to",
    "prime": "Apostrophe as prime f′",
    "chem": "Chemistry: H2O → H₂O",
    "italic": "Italic variables 𝑥𝑦",
    "rootline": "Overline after √ (experimental)",
}

HELP = [
    ["Powers and indices", "x^2 → x²   x_1 → x₁   x^(n+1) → xⁿ⁺¹   10^-3 → 10⁻³   A^T → Aᵀ\nBraces work too: x^{10}. What has no small form stays as x^(…)."],
    ["Roots", "sqrt(2) → √2   sqrt(x+1) → √(x+1)   cbrt(8) → ∛8   root(n)(x) → ⁿ√x"],
    ["Fractions", "1/2 → ½   22/7 → ²²⁄₇   a/b → a⁄b   (a+b)/(c+d) → (a+b)⁄(c+d)\nSpaced 1 / 2 and chains a/b/c are left alone. \\frac{a}{b} works."],
    ["Greek", "alpha beta gamma … omega → α β γ … ω, Delta Omega → Δ Ω, pi → π, vartheta → ϑ"],
    ["Operators", "<= >= != → ≤ ≥ ≠   +- → ±   ~~ → ≈   ~= → ≅   === → ≡   := → ≔\n* → ×   a - b → a − b   ... → …   ||v|| → ‖v‖   2 x 3 → 2 × 3"],
    ["Arrows", "-> → →   <- → ←   <-> → ↔   => → ⇒   <=> → ⇔   |-> → ↦   --> → ⟶"],
    ["Calculus", "int_0^1 → ∫₀¹   sum_(i=1)^n → ∑ᵢ₌₁ⁿ   prod, oint, iint\nlim_(x->oo) → lim_(x→∞)   partial → ∂   nabla → ∇   oo → ∞   d/dx → d⁄dx"],
    ["Sets and logic", "x in RR → x ∈ ℝ   notin subset subseteq union intersect setminus\nforall exists therefore implies iff → ∀ ∃ ∴ ⇒ ⇔   RR NN ZZ QQ CC → ℝ ℕ ℤ ℚ ℂ\nand, or, not, to convert only with the option on."],
    ["Functions and marks", "f'(x) → f′(x)   sin^2(x) → sin²(x)   abs(x) → |x|   norm(v) → ‖v‖   floor ceil\nvec(v) hat(x) bar(x) dot(x) ddot(x) tilde(x) → v⃗ x̂ x̄ ẋ ẍ x̃   30 deg → 30°"],
    ["Styles", "bb(A) → 𝐀   bbb(R) → ℝ   cc(L) → ℒ   fr(g) → 𝔤   sf(A) → 𝖠   tt(x) → 𝚡   it(x) → 𝑥"],
    ["LaTeX", "\\alpha \\frac{1}{2} \\sqrt{2} \\int_0^\\infty \\mathbb{R} \\hat{x} \\text{words} all work.\n\\left \\right are dropped; \\, is a space."],
    ["Leave things alone", "\"quoted text\" is never converted. \\* \\/ \\^ \\_ give the plain character."],
]


def on_event(e):
    global expr, opts
    kind = e["type"]
    eid = e["id"]
    if kind == "input_changed" and eid == "expr":
        expr = e.get("value") or ""
        reconvert()
    elif kind == "toggle":
        if eid in DEFAULTS:
            opts[eid] = bool(e.get("value"))
            save_opts()
            reconvert()
    elif kind == "click":
        if eid.startswith("sym:") and len(eid) > 4:
            expr = expr + eid[4:]
            wm.ui.set_input("expr", expr)
            reconvert()
        elif eid == "clear":
            expr = ""
            wm.ui.set_input("expr", "")
            reconvert()
        elif eid == "reset_opts":
            opts = default_options()
            save_opts()
            reconvert()


def symbols_page():
    rows = [ui.row([ui.button("sym:" + s, s) for s in row]) for row in SYMBOL_ROWS]
    rows.append(ui.label("Tap to add to the box above.", style="caption"))
    return ui.page("Symbols", *rows)


def options_page():
    rows = [ui.toggle(key, OPTION_LABELS[key], checked=opts[key]) for key in OPTION_KEYS]
    rows.append(ui.button("reset_opts", "Reset options"))
    return ui.page("Options", *rows)


def help_page():
    rows = []
    for title, body in HELP:
        rows.append(ui.label(title, style="title"))
        rows.append(ui.label(body, style="caption"))
    return ui.page("Help", *rows)


def render():
    col = [ui.input("expr", label="Math", placeholder="x^2 + sqrt(2) = pi/4")]
    if expr == "":
        col.append(ui.label(
            "Type math the way you say it: x^2, sqrt(2), pi, 1/2, int_0^1, x in RR. "
            "The Unicode version appears here, ready to insert.",
            style="caption",
        ))
    else:
        for n, c in enumerate(chunks):
            col.append(ui.output(c, id="out" if n == 0 else "out" + str(n + 1)))
        if len(chunks) > 1:
            col.append(ui.label("Long result, shown in " + str(len(chunks)) + " parts.", style="caption"))
    col.append(ui.tabs("tabs", symbols_page(), options_page(), help_page()))
    col.append(ui.button("clear", "Clear"))
    return ui.column(col)
