#!/usr/bin/env python3
"""Builds the word and sentence data of the Language Trainer plugin.

Writes plugins-src/language-trainer/concepts.py and one data_<code>.py per
language. The letter charts (letters_<code>.py) are written by hand and are
not touched here.

Sources, downloaded into --cache on the first run and reused after:

* Words: the translation tables of English Wiktionary, read from kaikki.org's
  per-word extracts (CC BY-SA 4.0). For each concept in
  tools/language_trainer/concepts.txt the sense with the most translations
  among our languages is used, or the sense its hint names; the first
  standard-variety translation in each language is taken, with Wiktionary's
  romanization. tools/language_trainer/word_overrides.json replaces picks
  that are rare, regional or the wrong sense. Japanese readings come from the
  ruby of the Japanese Wiktionary entry whose romanization matches.
* Sentences: Tatoeba (CC BY 2.0 FR), per-language exports. One pool of short
  English sentences translated into the most of our languages, so any two
  languages share most of their sentences through English; languages with
  few translations are topped up with more of their own. Sentences tagged
  @needs native check, @change, @check and the like are left out.

    python3 tools/build_language_trainer_data.py [--cache DIR]

Romanizations are brought in line with the plugin's letter charts: ʿ and ʾ
for Arabic, ch/chh for Hindi, Urdu and Bengali, ch/sh/zh/kh/ts for Russian
and Ukrainian, and Georgian spelled out from its chart.
"""

from __future__ import annotations

import argparse
import bz2
import collections
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "tools" / "language_trainer"
PLUGIN = ROOT / "plugins-src" / "language-trainer"

# Our code -> Tatoeba's.
TATOEBA = {
    "ja": "jpn", "ko": "kor", "ru": "rus", "el": "ell", "hi": "hin", "bn": "ben", "ar": "ara", "he": "heb",
    "th": "tha", "ka": "kat", "zh": "cmn", "es": "spa", "fr": "fra", "de": "deu", "pt": "por", "it": "ita",
    "tr": "tur", "ur": "urd", "id": "ind", "uk": "ukr", "vi": "vie",
}
CODES = list(TATOEBA)
TOPICS = [
    ("basics", "Basics"), ("numbers", "Numbers"), ("people", "People"), ("pronouns", "Pronouns"),
    ("body", "Body"), ("food", "Food and drink"), ("animals", "Animals"), ("nature", "Nature"),
    ("time", "Time"), ("days", "Days of the week"), ("colours", "Colours"), ("places", "Places"),
    ("things", "Things"), ("verbs", "Verbs"), ("adjectives", "Describing words"), ("questions", "Questions"),
]
POS = {"intj": {"intj", "phrase"}, "particle": {"particle", "intj", "adv"}, "num": {"num"}, "noun": {"noun"},
       "verb": {"verb"}, "adj": {"adj"}, "adv": {"adv"}, "pron": {"pron"}, "det": {"det", "adj", "pron"},
       "phrase": {"phrase", "intj"}}
UNWANTED_TAGS = {"archaic", "obsolete", "dated", "rare", "literary", "poetic", "slang", "vulgar", "dialectal",
                 "historical", "Traditional-Chinese", "Cantonese", "Hokkien", "Dungan", "Wu", "Hakka"}
SENTENCE_POOL = 360
SENTENCE_FLOOR = 250


def fetch(url: str, path: Path, pause: float = 0.6) -> bool:
    if path.exists() and path.stat().st_size > 0:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "wmkeyboard-addon-data-build"})
            path.write_bytes(urllib.request.urlopen(request, timeout=120).read())
            time.sleep(pause)
            return True
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return False
            time.sleep(3)
        except OSError:
            time.sleep(3)
    return False


def kaikki(cache: Path, dictionary: str, word: str) -> list[dict]:
    q = urllib.parse.quote
    url = f"https://kaikki.org/dictionary/{dictionary}/meaning/{q(word[0])}/{q(word[:2])}/{q(word)}.jsonl"
    path = cache / "kaikki" / dictionary / (word + ".jsonl")
    if not fetch(url, path):
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ------------------------------------------------------------------ words ---


def concepts() -> list[list[str]]:
    rows = []
    for line in (HERE / "concepts.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        rows.append((line.split("\t") + ["", ""])[:5])
    return rows


def pick_translations(entries: list[dict], word: str, pos: str, hint: str) -> tuple[str, dict]:
    entries = [e for e in entries if e.get("word") == word and e.get("translations")]
    matching = [e for e in entries if e.get("pos") in POS[pos]]
    entry = (matching or entries)[0]
    if hint:
        hinted = [e for e in entries if any(hint in (t.get("sense") or "") for t in e["translations"])]
        entry = (hinted or [entry])[0]
    score = collections.Counter(t.get("sense") for t in entry["translations"] if t.get("code") in CODES + ["cmn"])
    sense = score.most_common(1)[0][0]
    if hint:
        sense = next((s for s, _ in score.most_common() if hint in (s or "")), sense)
    picks = {}
    for code in CODES:
        codes = ("zh", "cmn") if code == "zh" else (code,)
        pool = [t for t in entry["translations"] if t.get("code") in codes and t.get("sense") == sense and t.get("word")]
        if code == "zh":
            pool = [t for t in pool if t.get("lang") in ("Chinese Mandarin", "Mandarin")]
        if code == "ar":
            pool = [t for t in pool if not any("Arabic" in tag for tag in t.get("tags") or [])]
        good = [t for t in pool if not set(t.get("tags") or []) & UNWANTED_TAGS]
        chosen = (good or pool or [None])[0]
        if chosen is not None:
            picks[code] = [chosen["word"], chosen.get("roman") or ""]
    return sense, picks


def clean_word(code: str, word: str) -> str:
    word = re.sub(r"\{\{t\+?\|[^|]+\|([^|}]+)[^}]*\}+", r"\1", word)
    word = re.sub(r"\s*\([^)]*\)", "", word)
    word = re.split(r"\s+imperfective:|\s+[mf] or\s+|\s+or\s+", word)[0]
    word = word.split("/")[-1] if code == "zh" else word.split("/")[0]
    return word.strip().strip(",").lstrip(".…").strip()


def georgian_chart() -> dict[str, str]:
    chart = {}
    for line in (PLUGIN / "letters_ka.py").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\S) (\S+)( \|.*)?$", line)
        if m and 0x10D0 <= ord(m.group(1)) <= 0x10FF:
            chart[m.group(1)] = m.group(2)
    return chart


def clean_roman(code: str, roman: str, word: str, georgian: dict[str, str]) -> str:
    roman = unicodedata.normalize("NFC", roman)
    roman = re.sub(r"\s*\([^)]*\)", "", roman).split("/")[0].split(",")[0].strip()
    if code == "ar":
        for a, b in (("ʕ", "ʿ"), ("ʔ", "ʾ"), ("š", "sh"), ("ḡ", "gh"), ("ḵ", "kh"), ("ḏ", "dh"), ("ṯ", "th"), ("ǧ", "j")):
            roman = roman.replace(a, b)
    elif code in ("hi", "ur", "bn"):
        roman = roman.replace("ch", "\x01").replace("c", "ch").replace("\x01", "chh")
        if code == "bn":
            for a, b in (("ś", "sh"), ("ẏ", "y"), ("ō", "o"), ("ẇ", "w")):
                roman = roman.replace(a, b)
        else:
            roman = roman.replace("ś", "sh").replace("ṣ", "ṣh").replace("ŕ", "ri")
    elif code in ("ru", "uk"):
        for a, b in (("c", "ts"), ("š", "sh"), ("č", "ch"), ("ž", "zh"), ("x", "kh"), ("ɛ", "e")):
            roman = roman.replace(a, b)
    elif code == "ka":
        roman = "".join(georgian.get(ch, ch) for ch in word)
    return roman


def squash(roman: str) -> str:
    return re.sub(r"[\s\-'’.]", "", unicodedata.normalize("NFC", roman).lower())


def japanese_reading(cache: Path, word: str, roman: str) -> str:
    """The kana reading of [word] whose romanization matches [roman]."""
    if not re.search(r"[一-鿿]", word):
        return ""
    stem, suffix = word, ""
    if word.endswith(("な", "の")) and len(word) > 1:
        stem, suffix = word[:-1], word[-1]
    readings, redirects = [], []
    for entry in kaikki(cache, "Japanese", stem):
        # A kanji spelling whose page sends the reader to the kana one.
        for target in entry.get("redirects") or []:
            if re.fullmatch(r"[\u3040-\u30ff]+", target):
                redirects.append(target)
        forms = entry.get("forms") or []
        canonical = next((f for f in forms if "canonical" in (f.get("tags") or []) and f.get("ruby")), None)
        if canonical is None or canonical.get("form") != stem:
            continue
        reading = stem
        for base, kana in canonical["ruby"]:
            reading = reading.replace(base, kana, 1)
        romans = [f["form"] for f in forms if (f.get("tags") or []) == ["romanization"]]
        readings.append((reading, [squash(r) for r in romans]))
    target = squash(roman)
    if suffix and target.endswith(("na", "no")):
        target = target[:-2]
    for reading, romans in readings:
        if target in romans or squash(roman) in romans:
            return reading + suffix
    if readings:
        return readings[0][0] + suffix
    return redirects[0] + suffix if redirects else ""


def build_words(cache: Path) -> tuple[list[tuple[str, str]], dict[str, dict]]:
    overrides = json.loads((HERE / "word_overrides.json").read_text(encoding="utf-8"))
    georgian = georgian_chart()
    order, data = [], {code: {} for code in CODES + ["en"]}
    for topic, word, pos, hint, source in concepts():
        entries = kaikki(cache, "English", source or word)
        _, picks = pick_translations(entries, source or word, pos, hint)
        order.append((topic, word))
        data["en"][word] = [word, "", ""]
        for code, (w, r) in picks.items():
            w = clean_word(code, w)
            data[code][word] = [w, clean_roman(code, r, w, georgian), ""]
        for code, (w, r) in overrides.get(word, {}).items():
            data[code][word] = [w, clean_roman(code, r, w, georgian) if code in ("hi", "ur", "ka") else r, ""]
        if word in data["ja"]:
            w, r, _ = data["ja"][word]
            data["ja"][word][2] = japanese_reading(cache, w, r)
    return order, data


# -------------------------------------------------------------- sentences ---


def build_sentences(cache: Path) -> dict[str, dict[int, list]]:
    base = "https://downloads.tatoeba.org/exports"
    folder = cache / "tatoeba"
    fetch(f"{base}/per_language/eng/eng_sentences.tsv.bz2", folder / "eng_sentences.tsv.bz2", 0)
    fetch(f"{base}/tags.tar.bz2", folder / "tags.tar.bz2", 0)
    for iso in TATOEBA.values():
        fetch(f"{base}/per_language/{iso}/{iso}_sentences.tsv.bz2", folder / f"{iso}_sentences.tsv.bz2", 0)
        fetch(f"{base}/per_language/eng/eng-{iso}_links.tsv.bz2", folder / f"eng-{iso}_links.tsv.bz2", 0)
    if not (folder / "tags.csv").exists():
        import tarfile
        with tarfile.open(folder / "tags.tar.bz2") as archive:
            archive.extract("tags.csv", folder, filter="data")

    def rows(name):
        with bz2.open(folder / name, "rt", encoding="utf-8") as f:
            for line in f:
                yield line.rstrip("\n").split("\t")

    english = {int(i): t for i, _, t in rows("eng_sentences.tsv.bz2")}
    flagged, ok = set(), set()
    for line in (folder / "tags.csv").read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            if parts[1].startswith("@"):
                flagged.add(int(parts[0]))
            elif parts[1] == "OK":
                ok.add(int(parts[0]))
    text, links = {}, collections.defaultdict(dict)
    for code, iso in TATOEBA.items():
        for i, _, t in rows(f"{iso}_sentences.tsv.bz2"):
            text[int(i)] = t
        for a, b in rows(f"eng-{iso}_links.tsv.bz2"):
            a, b = int(a), int(b)
            if a in english and b in text and a not in flagged and b not in flagged:
                links[a].setdefault(code, []).append(b)

    traditional = set("這們個說會來時對過還麼裡學電車開關樣愛書東見長門問話聽讀寫買賣認識覺歡飯號應該從現點兒歲頭臉")
    candidates = []
    for a, by in links.items():
        t = english[a]
        words = t.split()
        if not 3 <= len(words) <= 9 or len(t) > 60 or not re.search(r"[.?!]$", t) or re.search(r"\d", t):
            continue
        names = sum(1 for w in words[1:] if w[:1].isupper() and not w.startswith("I"))
        candidates.append((len(by), names > 0, len(t), a))
    candidates.sort(key=lambda c: (-c[0], c[1], c[2], c[3]))

    def key(s):
        return re.sub(r"[^a-z ]", "", s.lower()).strip()

    seen, pool = set(), []
    for _, _, _, a in candidates:
        if key(english[a]) not in seen:
            seen.add(key(english[a]))
            pool.append(a)
        if len(pool) >= SENTENCE_POOL:
            break
    pooled = set(pool)
    out = {"en": {}}
    for code in CODES:
        ids = [a for a in pool if code in links[a]]
        used = {key(english[a]) for a in ids}
        for _, _, _, a in candidates:
            if len(ids) >= SENTENCE_FLOOR:
                break
            if a not in pooled and code in links[a] and key(english[a]) not in used:
                used.add(key(english[a]))
                ids.append(a)
        chosen = {}
        for a in ids:
            options = links[a][code]
            if code == "zh":
                options = sorted(options, key=lambda b: (sum(ch in traditional for ch in text[b]), b not in ok, b))
            else:
                options = sorted(options, key=lambda b: (b not in ok, b))
            chosen[a] = [options[0], text[options[0]]]
            out["en"][a] = [a, english[a]]
        out[code] = chosen
    return out


# ------------------------------------------------------------------ write ---


def literal(value) -> str:
    """A Python literal the plugin interpreter reads. Its lexer works on
    grapheme clusters, so no string may start with a combining mark."""
    if isinstance(value, str):
        if value and unicodedata.category(value[0]).startswith("M"):
            raise ValueError(f"starts with a combining mark: {value!r}")
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(literal(v) for v in value) + "]"
    return json.dumps(value)


HEADER = """# Language Trainer data: {name}. Generated by tools/build_language_trainer_data.py,
# do not edit by hand.
#
# WORDS: concept -> [word, romanization, reading]. From the translation tables of
# English Wiktionary (https://en.wiktionary.org), CC BY-SA 4.0, through
# kaikki.org's extracts; a few picks replaced by hand.
#
# SENTENCES: English Tatoeba sentence id -> [sentence id, text]. From Tatoeba
# (https://tatoeba.org), CC BY 2.0 FR; each sentence is at
# https://tatoeba.org/sentences/show/<id>.
"""
NAMES = {"en": "English", "ja": "Japanese", "ko": "Korean", "ru": "Russian", "el": "Greek", "hi": "Hindi",
         "bn": "Bengali", "ar": "Arabic", "he": "Hebrew", "th": "Thai", "ka": "Georgian", "zh": "Chinese",
         "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese", "it": "Italian", "tr": "Turkish",
         "ur": "Urdu", "id": "Indonesian", "uk": "Ukrainian", "vi": "Vietnamese"}


def write(order, words, sentences) -> None:
    lines = ["# The word list's topics, in order. Generated by tools/build_language_trainer_data.py.", "",
             "TOPICS = ["]
    by_topic = collections.defaultdict(list)
    for topic, word in order:
        by_topic[topic].append(word)
    for topic, title in TOPICS:
        lines.append(f"    ({literal(topic)}, {literal(title)}, {literal(by_topic[topic])}),")
    lines.append("]")
    (PLUGIN / "concepts.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for code in ["en"] + CODES:
        out = [HEADER.format(name=NAMES[code]), "WORDS = {"]
        for _, word in order:
            if word in words[code]:
                out.append(f"    {literal(word)}: {literal(words[code][word])},")
        out.append("}")
        out.append("")
        out.append("SENTENCES = {")
        for a in sorted(sentences[code]):
            out.append(f"    {a}: {literal(sentences[code][a])},")
        out.append("}")
        (PLUGIN / f"data_{code}.py").write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"data_{code}.py: {len(words[code])} words, {len(sentences[code])} sentences")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "wmkb-language-trainer")
    args = parser.parse_args()
    order, words = build_words(args.cache)
    sentences = build_sentences(args.cache)
    write(order, words, sentences)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
