# Hangul with Revised Romanization. "glyph romanization | name". The
# syllable table is put together from the letters below, the way Hangul
# builds every syllable. Hand-written for this plugin (MIT).

TITLE = "Hangul"
CASED = False

CATEGORIES = [
    ("consonants", "Consonants", """
ㄱ g | giyeok, k at the end
ㄴ n | nieun
ㄷ d | digeut, t at the end
ㄹ r | rieul, l at the end
ㅁ m | mieum
ㅂ b | bieup, p at the end
ㅅ s | siot
ㅇ ng | ieung, silent at the start
ㅈ j | jieut
ㅊ ch | chieut
ㅋ k | kieuk
ㅌ t | tieut
ㅍ p | pieup
ㅎ h | hieut
"""),
    ("doubles", "Double consonants", """
ㄲ kk | ssanggiyeok
ㄸ tt | ssangdigeut
ㅃ pp | ssangbieup
ㅆ ss | ssangsiot
ㅉ jj | ssangjieut
"""),
    ("vowels", "Vowels", """
ㅏ a
ㅑ ya
ㅓ eo
ㅕ yeo
ㅗ o
ㅛ yo
ㅜ u
ㅠ yu
ㅡ eu
ㅣ i
"""),
    ("compound", "Compound vowels", """
ㅐ ae
ㅒ yae
ㅔ e
ㅖ ye
ㅘ wa
ㅙ wae
ㅚ oe
ㅝ wo
ㅞ we
ㅟ wi
ㅢ ui
"""),
    ("finals", "Final consonants", """
악 ak | ㄱ ㅋ ㄲ at the end
안 an | ㄴ at the end
앋 at | ㄷ ㅅ ㅈ ㅊ ㅌ ㅎ at the end
알 al | ㄹ at the end
암 am | ㅁ at the end
압 ap | ㅂ ㅍ at the end
앙 ang | ㅇ at the end
"""),
]

# Syllables: each starting consonant with each basic vowel, as Unicode
# composes them (0xAC00 + (initial * 21 + vowel) * 28).
_INITIALS = [(0, "g"), (2, "n"), (3, "d"), (5, "r"), (6, "m"), (7, "b"), (9, "s"), (11, ""),
             (12, "j"), (14, "ch"), (15, "k"), (16, "t"), (17, "p"), (18, "h")]
_VOWELS = [(0, "a"), (2, "ya"), (4, "eo"), (6, "yeo"), (8, "o"), (12, "yo"), (13, "u"), (17, "yu"),
           (18, "eu"), (20, "i")]


def _syllables(vowels):
    lines = []
    for i, ri in _INITIALS:
        for v, rv in vowels:
            lines.append(chr(0xAC00 + (i * 21 + v) * 28) + " " + ri + rv)
    return "\n".join(lines)


CATEGORIES.append(("syll_a", "Syllables: a ya eo yeo o", _syllables(_VOWELS[:5])))
CATEGORIES.append(("syll_u", "Syllables: yo u yu eu i", _syllables(_VOWELS[5:])))
