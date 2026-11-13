# The languages the trainer knows, and loading their data. Each language's
# words and sentences sit in data_<code>.py and its letter chart, when it has
# one, in letters_<code>.py. A module is imported only when it is needed, so
# a session reads just the two languages it drills.

# code, English name, own name, voice, has a letter chart, written with
# spaces between words
LANGS = [
    ("ja", "Japanese", "日本語", "ja-JP", True, False),
    ("ko", "Korean", "한국어", "ko-KR", True, True),
    ("ru", "Russian", "Русский", "ru-RU", True, True),
    ("el", "Greek", "Ελληνικά", "el-GR", True, True),
    ("hi", "Hindi", "हिन्दी", "hi-IN", True, True),
    ("bn", "Bengali", "বাংলা", "bn-BD", True, True),
    ("ar", "Arabic", "العربية", "ar", True, True),
    ("he", "Hebrew", "עברית", "he-IL", True, True),
    ("th", "Thai", "ไทย", "th-TH", True, False),
    ("ka", "Georgian", "ქართული", "ka-GE", True, True),
    ("zh", "Chinese", "中文", "zh-CN", False, False),
    ("ur", "Urdu", "اردو", "ur-PK", False, True),
    ("es", "Spanish", "Español", "es-ES", False, True),
    ("fr", "French", "Français", "fr-FR", False, True),
    ("de", "German", "Deutsch", "de-DE", False, True),
    ("pt", "Portuguese", "Português", "pt-BR", False, True),
    ("it", "Italian", "Italiano", "it-IT", False, True),
    ("tr", "Turkish", "Türkçe", "tr-TR", False, True),
    ("id", "Indonesian", "Bahasa Indonesia", "id-ID", False, True),
    ("uk", "Ukrainian", "Українська", "uk-UA", False, True),
    ("vi", "Vietnamese", "Tiếng Việt", "vi-VN", False, True),
    ("en", "English", "English", "en-US", False, True),
]

_BY_CODE = {}
for _row in LANGS:
    _BY_CODE[_row[0]] = _row


def known(code):
    return code in _BY_CODE


def name(code):
    return _BY_CODE[code][1]


def own_name(code):
    return _BY_CODE[code][2]


def voice(code):
    return _BY_CODE[code][3]


def has_letters(code):
    return _BY_CODE[code][4]


def spaced(code):
    return _BY_CODE[code][5]


def choices(exclude=None):
    """(code, "English name · own name") for a picker."""
    out = []
    for row in LANGS:
        if row[0] == exclude:
            continue
        label = row[1] if row[1] == row[2] else row[1] + " · " + row[2]
        out.append((row[0], label))
    return out


def letters(code):
    """The letter chart module, or None."""
    if code == "ja":
        import letters_ja
        return letters_ja
    if code == "ko":
        import letters_ko
        return letters_ko
    if code == "ru":
        import letters_ru
        return letters_ru
    if code == "el":
        import letters_el
        return letters_el
    if code == "hi":
        import letters_hi
        return letters_hi
    if code == "bn":
        import letters_bn
        return letters_bn
    if code == "ar":
        import letters_ar
        return letters_ar
    if code == "he":
        import letters_he
        return letters_he
    if code == "th":
        import letters_th
        return letters_th
    if code == "ka":
        import letters_ka
        return letters_ka
    return None


def data(code):
    """The words and sentences module."""
    if code == "ja":
        import data_ja
        return data_ja
    if code == "ko":
        import data_ko
        return data_ko
    if code == "ru":
        import data_ru
        return data_ru
    if code == "el":
        import data_el
        return data_el
    if code == "hi":
        import data_hi
        return data_hi
    if code == "bn":
        import data_bn
        return data_bn
    if code == "ar":
        import data_ar
        return data_ar
    if code == "he":
        import data_he
        return data_he
    if code == "th":
        import data_th
        return data_th
    if code == "ka":
        import data_ka
        return data_ka
    if code == "zh":
        import data_zh
        return data_zh
    if code == "ur":
        import data_ur
        return data_ur
    if code == "es":
        import data_es
        return data_es
    if code == "fr":
        import data_fr
        return data_fr
    if code == "de":
        import data_de
        return data_de
    if code == "pt":
        import data_pt
        return data_pt
    if code == "it":
        import data_it
        return data_it
    if code == "tr":
        import data_tr
        return data_tr
    if code == "id":
        import data_id
        return data_id
    if code == "uk":
        import data_uk
        return data_uk
    if code == "vi":
        import data_vi
        return data_vi
    import data_en
    return data_en
