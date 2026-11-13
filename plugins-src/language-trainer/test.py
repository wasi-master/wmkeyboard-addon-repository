# Tests for Language Trainer, run with `wm-python-cli test plugins-src/language-trainer`.
# They drive the panel as the keyboard does (events in, drawn widgets out) and
# check the logic in trainer.py directly.

import json

import concepts
import langs
import trainer

fails = []


def expect(what, ok, detail=""):
    if not ok:
        fails.append(what + (": " + str(detail) if detail else ""))


# ------------------------------------------------------------- the logic ---

expect("plain drops stress", trainer.check("вода", ["вода́"]) == "right")
expect("plain drops vowel points", trainer.check("מים", ["מַיִם"]) == "right")
expect("plain drops harakat", trainer.check("ماء", ["مَاء"]) == "right")
expect("accents are a near miss", trainer.check("arbol", ["árbol"]) == "accents")
expect("greek accents too", trainer.check("νερο", ["νερό"]) == "accents")
expect("reading counts", trainer.check("みず", ["水", "みず"]) == "right")
expect("nukta letter typed either way", trainer.check("क़लम", ["क़लम"]) == "right")
expect("punctuation and case", trainer.check(" Hola! ", ["hola"]) == "right")
expect("wrong is wrong", trainer.check("x", ["y"]) is None)
expect("empty is nothing", trainer.check("  ", ["y"]) is None)

opts = trainer.options("a", ["b", "c", "a", "d", "e", "b"])
expect("four options", len(opts) == 4, opts)
expect("answer among options", "a" in opts, opts)
expect("options unique", len(set(opts)) == 4, opts)
expect("short pools still work", sorted(trainer.options("a", ["b"])) == ["a", "b"])

p = {}
trainer.mark(p, "x", True, 100)
trainer.mark(p, "x", True, 100)
expect("two rights is box 2", p["x"][0] == 2, p)
trainer.mark(p, "x", False, 100)
expect("a miss goes back to box 0", p["x"] == [0, 3, 2, 100], p)

# A missed item comes up far more often than known ones.
p = {}
keys = ["k" + str(i) for i in range(10)]
for k in keys:
    p[k] = [5, 5, 5, 1000]
p["k3"] = [0, 4, 1, 1000]
hits = 0
for _ in range(300):
    if trainer.pick(keys, p, 1000) == "k3":
        hits += 1
expect("weak item drawn most", hits > 100, hits)
expect("recent skipped", trainer.pick(["a", "b"], {}, 0, recent=["a"]) == "b")
expect("weak list", trainer.weak(p, keys) == ["k3"], trainer.weak(p, keys))
expect("mastery", 0.85 < trainer.mastery(p, keys) < 0.95, trainer.mastery(p, keys))

expect("tokens", trainer.tokens("I am  here.") == ["I", "am", "here."])

# Every chart parses, and no letter shows twice in a category.
for code, _, _, _, has, _ in langs.LANGS:
    if not has:
        expect(code + " has no chart", langs.letters(code) is None)
        continue
    mod = langs.letters(code)
    cats = trainer.categories(mod)
    expect(code + " has categories", len(cats) >= 2, code)
    for cid, title, rows in cats:
        glyphs = [r[0] for r in rows]
        expect(code + "/" + cid + " unique glyphs", len(set(glyphs)) == len(glyphs), glyphs)
        expect(code + "/" + cid + " romanized", all(r[1] for r in rows), cid)
        labels = [trainer.label_for(rows, r) for r in rows]
        for r in rows:
            twins = [x for x in rows if x[1] == r[1]]
            if len(twins) > 1:
                expect(code + "/" + cid + " " + r[0] + " has a note to tell twins apart", r[2] != "", r)

# Every data module agrees with the concept list.
all_keys = []
for t in concepts.TOPICS:
    all_keys = all_keys + t[2]
expect("concepts unique", len(set(all_keys)) == len(all_keys))
for code, _, _, _, _, _ in langs.LANGS:
    d = langs.data(code)
    expect(code + " words", len(d.WORDS) >= 190, len(d.WORDS))
    expect(code + " sentences", len(d.SENTENCES) >= 240, len(d.SENTENCES))
    for k in d.WORDS:
        entry = d.WORDS[k]
        expect(code + " word " + k + " known", k in all_keys)
        expect(code + " word " + k + " written", entry[0] != "")
    for k in d.SENTENCES:
        expect(code + " sentence " + str(k) + " text", d.SENTENCES[k][1] != "")

# The pair from the issue: Japanese with Hindi.
ja = langs.data("ja").SENTENCES
hi = langs.data("hi").SENTENCES
shared = [k for k in ja if k in hi]
expect("Japanese and Hindi share sentences", len(shared) >= 100, len(shared))


# ------------------------------------------------------------- the panel ---

PAIRS = json.dumps([{"t": "안녕하세요.", "s": "Hello."}, {"t": "고마워요.", "s": "Thanks."},
                    {"t": "물 주세요.", "s": "Water, please."}, {"t": "어디예요?", "s": "Where is it?"},
                    {"t": "좋아요.", "s": "Good."}])
MOCK = {
    "ui.toast": None,
    "device.speak": None,
    "keyboard.use": "Japanese Romaji",
    "keyboard.restore": None,
    "ui.dialog": "Reset",
    "ai.ask": [
        {"when": {"prompt": "Write 5*"}, "reply": {"text": "Here you go:\n```json\n" + PAIRS + "\n```"}},
        {"reply": {"text": "mizu: water. A plain noun."}},
    ],
}

S = plugin_test.session(mock=MOCK, settings={"round": 10, "speak": False, "romanization": True})
worst = {}


def check(r, what):
    if not r["ok"]:
        fails.append(what + ": " + str(r.get("error")))
        raise RuntimeError(what + ": " + str(r.get("error")))
    for ph in r.get("phases", []):
        share = ph["steps"] / ph["stepsLimit"]
        if share > worst.get(ph["phase"], (0, ""))[0]:
            worst[ph["phase"]] = (share, what)
        expect(what + " within " + ph["phase"] + " steps", share < 0.5, ph)
    expect(what + " no repairs", not r["ui"].get("repairs"), r["ui"].get("repairs"))
    return r


def walk(node, out):
    if isinstance(node, dict):
        if "type" in node:
            out.append(node)
        for v in node.values():
            walk(v, out)
    elif isinstance(node, list):
        for x in node:
            walk(x, out)


def widgets(r, kind=None):
    out = []
    walk(r["ui"]["root"], out)
    return [w for w in out if kind is None or w["type"] == kind]


def texts(r, kind):
    return [w.get("text") or w.get("label") or "" for w in widgets(r, kind)]


def by_id(r, wid):
    for w in widgets(r):
        if w.get("id") == wid:
            return w
    return None


def event(e, what=None):
    return check(S["event"](e), what or json.dumps(e, ensure_ascii=False))


def click(wid):
    return event({"type": "click", "id": wid})


def change(wid, value):
    return event({"type": "change", "id": wid, "value": value})


def prompt(r):
    for w in widgets(r, "label"):
        if w.get("style") in ("headline", "title"):
            return w["text"]
    return None


def options(r):
    return [w["text"] for w in widgets(r, "button") if (w.get("id") or "").startswith("opt:")]


def said(r, text):
    return any(text in t for t in texts(r, "label"))


def calls(op):
    return [c for c in S["calls"]() if c["op"] == op]


r = check(S["load"](), "load")
expect("opens on Japanese letters", by_id(r, "target")["value"] == "ja")
expect("hiragana chart has 46 letters", len([w for w in widgets(r) if (w.get("id") or "").startswith("card:")]) == 46)

# Every chart, every category, draws.
for code, _, _, _, has, _ in langs.LANGS:
    if not has:
        continue
    r = change("target", code)
    expect(code + " letters section", by_id(r, "section")["value"] == "letters")
    cats = trainer.categories(langs.letters(code))
    for cid, title, rows in cats:
        r = change("category", cid)
        cards = [w for w in widgets(r) if (w.get("id") or "").startswith("card:")]
        expect(code + "/" + cid + " cards", len(cards) == len(rows), (len(cards), len(rows)))

# Tapping a letter reads it aloud.
r = change("target", "ja")
r = change("category", "hira")
before = len(calls("device.speak"))
r = click("card:か")
expect("tap speaks", len(calls("device.speak")) == before + 1)
expect("speaks Japanese", calls("device.speak")[-1]["args"]["language"] == "ja-JP")


def letter_rows(code, cid):
    for c in trainer.categories(langs.letters(code)):
        if c[0] == cid:
            return c[2]
    return []


# Letter -> sound, all right.
rows = letter_rows("ja", "hira")
r = click("button:Letter → sound")
for n in range(10):
    shown = prompt(r)
    row = [x for x in rows if x[0] == shown][0]
    answer = trainer.label_for(rows, row)
    expect("option offered", answer in options(r), (answer, options(r)))
    r = click("opt:" + answer)
    expect("right " + shown, said(r, "Right!"), texts(r, "label"))
    r = click("button:" + ("Next" if n < 9 else "Finish"))
expect("round done", said(r, "Round done"))
saved_p = json.loads(S["storage"]().get("p:ja", "{}"))
expect("progress saved", len(saved_p) >= 5, saved_p)
r = click("button:Done")

# Sound -> letter on Greek, where η and ι both sound i.
r = change("target", "el")
r = change("category", "vowels")
rows = letter_rows("el", "vowels")
r = click("button:Sound → letter")
for n in range(10):
    label = prompt(r)
    good = [trainer.shown_glyph(x[0], True) for x in rows if trainer.label_for(rows, x) == label]
    expect("label names one letter", len(good) == 1, (label, good))
    expect("letter offered", good[0] in options(r), (good, options(r)))
    r = click("opt:" + good[0])
    expect("right " + label, said(r, "Right!"))
    r = click("button:" + ("Next" if n < 9 else "Finish"))
r = click("button:Done")

# A miss, then the miss shows as a weak spot.
r = change("category", "consonants")
rows = letter_rows("el", "consonants")
r = click("button:Letter → sound")
shown = prompt(r)
row = [x for x in rows if trainer.shown_glyph(x[0], True) == shown][0]
wrong = [o for o in options(r) if o != trainer.label_for(rows, row)][0]
r = click("opt:" + wrong)
expect("not quite", said(r, "Not quite."))
colors = {w["text"]: w.get("color") for w in widgets(r, "button") if (w.get("id") or "").startswith("opt:")}
expect("right one green", colors[trainer.label_for(rows, row)] == "success", colors)
expect("chosen one red", colors[wrong] == "danger", colors)
r = click("button:End")
r = change("section", "progress")
expect("weak spot listed", any(row[0] in (w.get("title") or "") for w in widgets(r, "item")), texts(r, "item"))
r = click("button:Practise weak spots")
expect("weak practice starts", prompt(r) is not None and len(options(r)) >= 2)
r = click("button:End")

# Typing a letter puts the target language's keys up, and End gives them back.
r = change("target", "ja")
r = change("section", "letters")
r = change("category", "kata")
rows = letter_rows("ja", "kata")
r = click("button:Type it")
uses = calls("keyboard.use")
expect("keys switched", uses and uses[-1]["args"]["language"] == "ja", uses)
label = prompt(r)
glyph = [x[0] for x in rows if trainer.label_for(rows, x) == label][0]
r = change("answer1", glyph)
r = event({"type": "submit", "id": "answer1", "value": glyph})
expect("typed letter right", said(r, "Right!"), texts(r, "label"))
r = click("button:Next")
r = click("button:Show answer")
expect("giving up shows the answer", said(r, "Not quite."))
restores = len(calls("keyboard.restore"))
r = click("button:End")
expect("keys given back", len(calls("keyboard.restore")) == restores + 1)

# Words: Japanese with Hindi, as the issue asks.
r = change("second", "hi")
r = change("section", "words")
r = change("topic", "food")
r = change("word_mode", "t2s")
JA = langs.data("ja").WORDS
HI = langs.data("hi").WORDS
r = click("button:Start")
for n in range(4):
    word = prompt(r)
    keys = [k for k in JA if JA[k][0] == word and k in HI]
    good = [HI[k][0] for k in keys if HI[k][0] in options(r)]
    expect("hindi meaning offered for " + word, len(good) == 1, (word, options(r)))
    r = click("opt:" + good[0])
    expect("right " + word, said(r, "Right!"))
    r = click("button:Next")
# AI explains a word.
r = click("opt:" + options(r)[0])
r = click("button:Explain")
r = check(S["settle"](), "settle explain")
expect("explanation shown", any("mizu" in (w.get("text") or "") for w in widgets(r, "markdown")), widgets(r, "markdown"))
r = click("button:End")

# Hindi -> Japanese.
r = change("word_mode", "s2t")
r = click("button:Start")
word = prompt(r)
keys = [k for k in HI if HI[k][0] == word and k in JA]
good = [JA[k][0] for k in keys if JA[k][0] in options(r)]
expect("japanese offered for " + word, len(good) >= 1, (word, options(r)))
r = click("opt:" + good[0])
expect("right " + word, said(r, "Right!"))
r = click("button:End")

# Typing a Korean word, with Korean keys.
r = change("target", "ko")
r = change("second", "en")
r = change("word_mode", "type")
KO = langs.data("ko").WORDS
EN = langs.data("en").WORDS
r = click("button:Start")
expect("korean keys", calls("keyboard.use")[-1]["args"]["language"] == "ko")
word = prompt(r)
k = [k for k in EN if EN[k][0] == word][0]
r = change("answer1", KO[k][0])
r = event({"type": "submit", "id": "answer1", "value": KO[k][0]})
expect("typed word right", said(r, "Right!"), texts(r, "label"))
r = click("button:End")

# Sentences in order, Korean from English.
r = change("section", "sentences")
expect("korean english count", any("sentences in both Korean and English" in t for t in texts(r, "label")))
r = change("sentence_mode", "order")
KS = langs.data("ko").SENTENCES
ES = langs.data("en").SENTENCES
r = click("button:Start")
english = prompt(r)
target = [KS[k][1] for k in KS if k in ES and ES[k][1] == english][0]
for token in trainer.tokens(target):
    keys_widget = [w for w in widgets(r, "keys")][0]
    r = event({"type": "press", "id": keys_widget["id"], "value": token})
r = click("button:Check")
expect("sentence built right", said(r, "Right!"), texts(r, "label"))
r = click("button:End")

# The model writes five more Korean sentences.
r = click("button:5 more with AI")
r = check(S["settle"](), "settle more")
expect("ai sentences kept", len(json.loads(S["storage"]().get("ai:ko:en", "[]"))) == 5, S["storage"]().get("ai:ko:en"))
expect("caption counts them", any("5 of them written by AI" in t for t in texts(r, "label")), texts(r, "label"))
r = change("sentence_mode", "t2s")
r = click("button:Start")
expect("sentence quiz runs", prompt(r) is not None and len(options(r)) == 4, options(r))
r = click("button:End")

# Japanese has no spaces between words, so no word-order drill.
r = change("target", "ja")
modes = [o["value"] for o in by_id(r, "sentence_mode")["options"]]
expect("no order drill for japanese", "order" not in modes, modes)

# Reset forgets the language's progress after asking.
r = change("section", "progress")
expect("progress before reset", "p:ja" in S["storage"]())
r = click("button:Reset")
r = check(S["settle"](), "settle reset")
expect("reset forgets", "p:ja" not in S["storage"](), S["storage"]().keys())

# Every language and section draws within budget.
for code, _, _, _, has, _ in langs.LANGS:
    r = change("target", code)
    for section in ("letters", "words", "sentences", "progress"):
        r = change("section", section)
    r = change("topic", "all")

# Without keyboard.use (an older keyboard, or the web preview's absence), typing drills still run.
S = plugin_test.session(mock={"ui.toast": None, "device.speak": None}, settings={})
r = check(S["load"](), "load without keyboard")
r = event({"type": "click", "id": "button:Type it"})
expect("typing drill without keys", prompt(r) is not None)

print("worst step share:", worst)
if fails:
    for line in fails[:40]:
        print("  " + line)
    raise RuntimeError("language-trainer: " + str(len(fails)) + " checks failed")
print("language-trainer: all checks passed")
