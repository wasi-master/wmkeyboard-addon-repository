# Language Trainer: alphabets, words and sentences of another language, drilled
# both ways, with the keyboard switched to that language while you type.
#
# Pick the language to learn and the one to learn it with (English, or any
# other here: Japanese with Hindi works). Letters shows the alphabet by
# category; tap a letter to hear it. Each drill is multiple choice or typed,
# and every answer moves the item up or down a Leitner box, so the letters
# and words you miss come back more often.

import json
import time

from wm import plugin, ui, storage, device, ai

try:
    from wm import keyboard
except ImportError:
    # A keyboard from before keyboard.use_language: drills still work, on
    # whatever layout is up.
    keyboard = None

import concepts
import langs
import trainer

saved = plugin.state(
    persist=True,
    target="ja",
    second="en",
    section="letters",
    category={},
    topic="basics",
    word_mode="t2s",
    sentence_mode="t2s",
)
s = plugin.state(quiz=None, typed="", explain=None, busy=False)

SECTIONS = [("letters", "Letters"), ("words", "Words"), ("sentences", "Sentences"), ("progress", "Progress")]
MC_MODES = ("g2r", "r2g", "t2s", "s2t")
AI_KEEP = 60

if not langs.known(saved.target):
    saved.target = "ja"
if not langs.known(saved.second) or saved.second == saved.target:
    saved.second = "en" if saved.target != "en" else "es"


def now():
    return int(time.time() // 60)


def setting(key, default):
    return plugin.settings.get(key, default)


def round_length():
    try:
        n = int(setting("round", 10))
    except (TypeError, ValueError):
        n = 10
    return max(3, min(50, n))


def romanize():
    return bool(setting("romanization", True))


# ---------------------------------------------------------------- progress ---

_progress = {}


def progress(code):
    """How well each item of [code] is known: {key: [box, seen, right, minute]}."""
    p = _progress.get(code)
    if p is None:
        p = storage.get("p:" + code) or {}
        _progress[code] = p
    return p


def save_progress(code):
    try:
        storage["p:" + code] = progress(code)
    except ValueError:
        ui.toast("Storage is full, so this answer was not saved.")


def reset_progress(code):
    _progress[code] = {}
    if ("p:" + code) in storage:
        del storage["p:" + code]


# ------------------------------------------------------------------ speech ---


def say(text, code):
    try:
        device.speak(text, language=langs.voice(code))
    except Exception as error:  # no voice, or the permission is off
        ui.toast("Can't read it aloud: " + str(error))


# ---------------------------------------------------------------- the keys ---


def use_keys(code):
    """Puts the keys of [code] up while the drill runs. The layout's name, or None."""
    if keyboard is None or code == "en":
        return None
    try:
        return keyboard.use_language(code)
    except Exception:
        return None


def give_keys_back():
    if keyboard is None:
        return
    try:
        keyboard.restore()
    except Exception:
        pass


# ----------------------------------------------------------------- letters ---


def letter_categories(code):
    mod = langs.letters(code)
    if mod is None:
        return [], False
    return trainer.categories(mod), mod.CASED


def current_category(cats):
    want = saved.category.get(saved.target)
    for c in cats:
        if c[0] == want:
            return c
    return cats[0]


def letter_items(cats, rows, cased):
    """Questions for [rows]: one item per letter. Wrong options come from the
    same category first, and from the rest of the script when it is small."""
    inside = {}
    for r in rows:
        inside[r[0]] = True
    outside = []
    for c in cats:
        for r in c[2]:
            if r[0] not in inside:
                outside.append(r)
    labels = [trainer.label_for(rows, r) for r in rows]
    shown = [trainer.shown_glyph(r[0], cased) for r in rows]
    items = {}
    for i in range(len(rows)):
        row = rows[i]
        same = [r[0] for r in rows if r[1] == row[1]]
        items["L" + row[0]] = {
            "kind": "letter",
            "glyph": row[0],
            "shown": shown[i],
            "label": labels[i],
            "note": row[2],
            "glyphs": [shown[j] for j in range(len(rows)) if rows[j][1] != row[1]],
            "glyphs_far": [trainer.shown_glyph(r[0], cased) for r in outside if r[1] != row[1]],
            "labels": labels,
            "labels_far": [r[1] for r in outside],
            "accept": same,
            "accept_shown": [trainer.shown_glyph(g, cased) for g in same],
        }
    return items


def near_first(answer, near, far):
    """[near] when it holds three wrong options, else [near] and [far]."""
    others = {}
    for x in near:
        if x != answer:
            others[x] = True
    return near if len(others) >= 3 else near + far


# ------------------------------------------------------------ words, sentences ---


def word_text(entry):
    return entry[0]


def word_caption(entry, code):
    """The reading and romanization under a word, as the settings allow."""
    parts = []
    if len(entry) > 2 and entry[2]:
        parts.append(entry[2])
    if romanize() and entry[1] and entry[1] != entry[0]:
        parts.append(entry[1])
    return " · ".join(parts)


def topic_keys(topic):
    if topic == "all":
        out = []
        for t in concepts.TOPICS:
            out = out + t[2]
        return out
    for t in concepts.TOPICS:
        if t[0] == topic:
            return t[2]
    return concepts.TOPICS[0][2]


def word_items(t, so, keys):
    T = langs.data(t).WORDS
    S = langs.data(so).WORDS
    items = {}
    for k in keys:
        if k in T and k in S:
            items["W" + k] = {"kind": "word", "id": k, "t": T[k], "s": S[k]}
    return items


def ai_sentences(t, so):
    return storage.get("ai:" + t + ":" + so) or []


def sentence_items(t, so):
    T = langs.data(t).SENTENCES
    S = langs.data(so).SENTENCES
    items = {}
    for k in T:
        if k in S:
            items["S" + str(k)] = {"kind": "sentence", "id": k, "t": T[k][1], "s": S[k][1], "ai": False}
    n = 0
    for pair in ai_sentences(t, so):
        items["A" + str(n)] = {"kind": "sentence", "id": "A" + str(n), "t": pair[0], "s": pair[1], "ai": True}
        n += 1
    return items


# ------------------------------------------------------------------ quizzes ---


def start(kind, mode, items, keys=None):
    if not items:
        ui.toast("Nothing to practise here yet.")
        return
    quiz = {
        "kind": kind,
        "mode": mode,
        "items": items,
        "keys": keys or sorted(items.keys()),
        "n": 0,
        "total": round_length(),
        "right": 0,
        "recent": [],
        "q": None,
        "answered": None,
        "switched": False,
        "done": False,
        "missed": [],
    }
    if mode == "type":
        name = use_keys(saved.target)
        quiz["switched"] = True
        if name:
            ui.toast("Typing on " + name)
    s.quiz = quiz
    s.explain = None
    next_question()


def end_quiz():
    quiz = s.quiz
    s.quiz = None
    s.explain = None
    s.busy = False
    if quiz is not None and quiz["switched"]:
        give_keys_back()


def next_question():
    quiz = s.quiz
    if quiz is None:
        return
    if quiz["n"] >= quiz["total"]:
        quiz["done"] = True
        return
    p = progress(saved.target)
    key = trainer.pick(quiz["keys"], p, now(), quiz["recent"])
    quiz["recent"] = (quiz["recent"] + [key])[-3:]
    quiz["q"] = question(quiz, key)
    quiz["answered"] = None
    quiz["n"] = quiz["n"] + 1
    s.typed = ""
    s.explain = None
    if setting("speak", False) and quiz["q"]["speak"]:
        say(quiz["q"]["speak"][0], quiz["q"]["speak"][1])


def question(quiz, key):
    """What to show for item [key] in the quiz's mode."""
    item = quiz["items"][key]
    mode = quiz["mode"]
    t, so = saved.target, saved.second
    q = {"key": key, "prompt": "", "caption": "", "speak": None, "options": [], "answer": "",
         "accept": [], "solution": "", "tokens": [], "built": [], "kind": item["kind"]}
    if item["kind"] == "letter":
        if mode == "g2r":
            q["prompt"] = item["shown"]
            q["speak"] = (item["glyph"], t)
            q["answer"] = item["label"]
            q["options"] = trainer.options(item["label"], near_first(item["label"], item["labels"], item["labels_far"]))
        else:
            q["prompt"] = item["label"]
            q["answer"] = item["shown"]
            # Typed answers are compared in lower case; buttons show both cases.
            q["accept"] = item["accept"] if mode == "type" else item["accept_shown"]
            q["options"] = trainer.options(item["shown"], near_first(item["shown"], item["glyphs"], item["glyphs_far"]))
        q["solution"] = item["shown"] + "  " + item["label"] + ("  · " + item["note"] if item["note"] else "")
        return q
    if item["kind"] == "word":
        tw, sw = item["t"], item["s"]
        same_t = [x for x in quiz["keys"] if quiz["items"][x]["t"][0] == tw[0]]
        if mode == "t2s":
            q["prompt"] = tw[0]
            q["caption"] = word_caption(tw, t)
            q["speak"] = (tw[0], t)
            q["answer"] = sw[0]
            q["options"] = trainer.options(sw[0], word_candidates(quiz, key, "s", same_t))
        elif mode == "s2t":
            q["prompt"] = sw[0]
            q["caption"] = word_caption(sw, so) if so != "en" else ""
            q["answer"] = tw[0]
            q["options"] = trainer.options(tw[0], word_candidates(quiz, key, "t", same_t))
        else:
            q["prompt"] = sw[0]
            q["caption"] = word_caption(sw, so) if so != "en" else ""
            q["answer"] = tw[0]
            q["accept"] = [tw[0]] + ([tw[2]] if len(tw) > 2 and tw[2] else [])
        caption = word_caption(tw, t)
        q["solution"] = tw[0] + ("  " + caption if caption else "") + "  =  " + sw[0]
        return q
    # A sentence.
    if mode == "t2s":
        q["prompt"] = item["t"]
        q["speak"] = (item["t"], t)
        q["answer"] = item["s"]
        q["options"] = trainer.options(item["s"], sentence_candidates(quiz, key, "s"))
    elif mode == "s2t":
        q["prompt"] = item["s"]
        q["answer"] = item["t"]
        q["options"] = trainer.options(item["t"], sentence_candidates(quiz, key, "t"))
    else:
        q["prompt"] = item["s"]
        q["answer"] = item["t"]
        q["tokens"] = trainer.shuffled(trainer.tokens(item["t"]))
    q["solution"] = item["t"] + "  =  " + item["s"]
    return q


def word_candidates(quiz, key, side, same_t):
    """Other words' texts on [side], from the same topic first, never one that
    shares the prompt's target word (those would be right too)."""
    item = quiz["items"][key]
    topic = None
    for t in concepts.TOPICS:
        if item["id"] in t[2]:
            topic = t[2]
    near, far = [], []
    for k in quiz["keys"]:
        if k == key or k in same_t:
            continue
        other = quiz["items"][k]
        text = other[side][0]
        if topic is not None and other["id"] in topic:
            near.append(text)
        else:
            far.append(text)
    if len(set(near)) >= 3:
        return near
    return near + far


def sentence_candidates(quiz, key, side):
    item = quiz["items"][key]
    out = []
    for k in quiz["keys"]:
        other = quiz["items"][k]
        if k != key and other["t"] != item["t"] and other["s"] != item["s"]:
            out.append(other[side])
    return out


def answered(ok, chosen, note=""):
    quiz = s.quiz
    q = quiz["q"]
    quiz["answered"] = {"ok": ok, "chosen": chosen, "note": note}
    if ok:
        quiz["right"] = quiz["right"] + 1
    else:
        quiz["missed"] = quiz["missed"] + [q["solution"]]
    trainer.mark(progress(saved.target), q["key"], ok, now())
    save_progress(saved.target)


def choose(option):
    quiz = s.quiz
    if quiz is None or quiz["answered"] is not None:
        return
    q = quiz["q"]
    ok = option == q["answer"] or (q["accept"] and option in [x for x in q["accept"]])
    answered(ok, option)
    if ok and q["speak"] is None and quiz["kind"] == "letter" and quiz["mode"] == "r2g":
        say(item_glyph(quiz, q), saved.target)


def item_glyph(quiz, q):
    return quiz["items"][q["key"]]["glyph"]


def submit_typed(text=None):
    quiz = s.quiz
    if quiz is None or quiz["answered"] is not None:
        return
    typed = s.typed if text is None else text
    s.typed = typed
    if not typed.strip():
        ui.toast("Type your answer first.")
        return
    q = quiz["q"]
    accept = q["accept"] or [q["answer"]]
    verdict = trainer.check(typed, accept)
    if verdict == "right":
        answered(True, typed)
    elif verdict == "accents":
        answered(True, typed, "Mind the marks: " + q["answer"])
    else:
        answered(False, typed)


def give_up():
    quiz = s.quiz
    if quiz is None or quiz["answered"] is not None:
        return
    answered(False, "")


def add_token(token):
    quiz = s.quiz
    if quiz is None or quiz["answered"] is not None:
        return
    q = quiz["q"]
    if token in q["tokens"]:
        q["tokens"].remove(token)
        q["built"].append(token)


def undo_token():
    quiz = s.quiz
    if quiz is None or quiz["answered"] is not None:
        return
    q = quiz["q"]
    if q["built"]:
        q["tokens"].append(q["built"].pop())


def check_order():
    quiz = s.quiz
    if quiz is None or quiz["answered"] is not None:
        return
    q = quiz["q"]
    built = " ".join(q["built"])
    answered(trainer.plain(built) == trainer.plain(q["answer"]), built)


# --------------------------------------------------------------------- AI ---


def explain():
    quiz = s.quiz
    if quiz is None:
        return
    q = quiz["q"]
    t, so = langs.name(saved.target), langs.name(saved.second)
    prompt = (
        "I am learning " + t + ". Explain this briefly for a beginner: " + q["solution"] + ". "
        + "Give the romanization, a word-by-word breakdown, and one note on grammar or usage. "
        + "Answer in English, in under 120 words, as plain text with short lines."
    )
    s.busy = True
    s.explain = None
    try:
        ai.ask(prompt, system="You are a patient " + t + " teacher for a speaker of " + so + ".",
               then=explained, on_error=ai_failed)
    except Exception as error:
        ai_failed(error)


def explained(reply):
    s.busy = False
    s.explain = (reply or "").strip() or "The model sent no answer."


def ai_failed(error):
    s.busy = False
    ui.toast("AI: " + str(error))


def more_sentences():
    t, so = saved.target, saved.second
    prompt = (
        "Write 5 short, everyday sentences for a beginner learning " + langs.name(t)
        + ", each with its translation into " + langs.name(so) + ". "
        + "Reply with only a JSON array of objects with the keys \"t\" (the " + langs.name(t)
        + " sentence) and \"s\" (the " + langs.name(so) + " translation)."
    )
    s.busy = True
    try:
        ai.ask(prompt, then=got_sentences, on_error=ai_failed)
    except Exception as error:
        ai_failed(error)


def parse_pairs(reply):
    """The [{"t", "s"}] list in a model's reply, as [[t, s]]; [] when there is none."""
    text = reply or ""
    start_at = text.find("[")
    end_at = text.rfind("]")
    if start_at < 0 or end_at <= start_at:
        return []
    try:
        rows = json.loads(text[start_at:end_at + 1])
    except ValueError:
        return []
    out = []
    if not isinstance(rows, list):
        return []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("t"), str) and isinstance(row.get("s"), str):
            if row["t"].strip() and row["s"].strip():
                out.append([row["t"].strip()[:200], row["s"].strip()[:200]])
    return out


def got_sentences(reply):
    s.busy = False
    pairs = parse_pairs(reply)
    if not pairs:
        ui.toast("The model's answer had no sentences in it. Try again.")
        return
    key = "ai:" + saved.target + ":" + saved.second
    kept = (ai_sentences(saved.target, saved.second) + pairs)[-AI_KEEP:]
    try:
        storage[key] = kept
    except ValueError:
        ui.toast("Storage is full.")
        return
    ui.toast(str(len(pairs)) + " new sentences added.")


def forget_ai_sentences():
    key = "ai:" + saved.target + ":" + saved.second
    if key in storage:
        del storage[key]


# ------------------------------------------------------------------ events ---


def set_target(code):
    if not langs.known(code):
        return
    saved.target = code
    if saved.second == code:
        saved.second = "en" if code != "en" else "es"
    if saved.section == "letters" and not langs.has_letters(code):
        saved.section = "words"


def set_second(code):
    if langs.known(code) and code != saved.target:
        saved.second = code


def set_section(value):
    saved.section = value


def set_category(value):
    saved.category[saved.target] = value


def set_topic(value):
    saved.topic = value


def set_word_mode(value):
    saved.word_mode = value


def set_sentence_mode(value):
    saved.sentence_mode = value


def set_typed(text):
    s.typed = text


def start_letters(mode):
    cats, cased = letter_categories(saved.target)
    if not cats:
        return
    cat = current_category(cats)
    start("letter", mode, letter_items(cats, cat[2], cased))


def start_words():
    items = word_items(saved.target, saved.second, topic_keys(saved.topic))
    start("word", saved.word_mode, items)


def start_sentences():
    items = sentence_items(saved.target, saved.second)
    mode = saved.sentence_mode
    if mode == "order" and not langs.spaced(saved.target):
        mode = "t2s"
    if len(items) < 4:
        ui.toast("Too few sentences in both languages yet.")
        return
    start("sentence", mode, items)


def practise_weak():
    t = saved.target
    p = progress(t)
    items = {}
    cats, cased = letter_categories(t)
    for c in cats:
        for key, item in letter_items(cats, c[2], cased).items():
            items[key] = item
    words = word_items(t, saved.second, topic_keys("all"))
    for key in words:
        items[key] = words[key]
    weak = trainer.weak(p, list(items.keys()), limit=20)
    if not weak:
        ui.toast("No weak spots yet: practise a little first.")
        return
    letters_only = [k for k in weak if k.startswith("L")]
    if len(letters_only) >= len(weak) / 2 and len(letters_only) >= 2:
        start("letter", "g2r", {k: items[k] for k in letters_only})
    else:
        start("word", "t2s", {k: items[k] for k in weak if k.startswith("W")} or items)


def ask_reset():
    ui.dialog(
        "Reset progress?",
        "Forget what you have learned in " + langs.name(saved.target) + ". This can't be undone.",
        buttons=("Reset", "Cancel"),
        on_result=reset_answer,
    )


def reset_answer(button):
    if button == "Reset":
        reset_progress(saved.target)
        ui.toast("Progress reset.")


@plugin.on_close
def closed():
    if s.quiz is not None and s.quiz["switched"]:
        give_keys_back()


@plugin.command("Sources", icon="info")
def show_sources():
    plugin.push(sources_page, title="Sources")


# ------------------------------------------------------------------ drawing ---


def render():
    if s.quiz is not None:
        return quiz_page()
    t = saved.target
    with ui.row():
        ui.select(langs.choices(), value=t, on_change=set_target, label="Learn", key="target")
        ui.select(langs.choices(exclude=t), value=saved.second, on_change=set_second, label="With", key="second")
    sections = [x for x in SECTIONS if x[0] != "letters" or langs.has_letters(t)]
    section = saved.section if saved.section in [x[0] for x in sections] else sections[0][0]
    ui.select(sections, value=section, on_change=set_section, style="segmented", key="section")
    if section == "letters":
        letters_view()
    elif section == "words":
        words_view()
    elif section == "sentences":
        sentences_view()
    else:
        progress_view()


def letters_view():
    t = saved.target
    cats, cased = letter_categories(t)
    cat = current_category(cats)
    rows = cat[2]
    p = progress(t)
    keys = ["L" + r[0] for r in rows]
    ui.chips([(c[0], c[1]) for c in cats], value=cat[0], on_change=set_category, key="category")
    ui.caption(str(trainer.known_count(p, keys)) + " of " + str(len(rows)) + " learned. Tap a letter to hear it.")
    with ui.row():
        ui.button("Letter → sound", on_click=lambda: start_letters("g2r"), primary=True)
        ui.button("Sound → letter", on_click=lambda: start_letters("r2g"))
        ui.button("Type it", on_click=lambda: start_letters("type"), icon="keyboard")
    wide = False
    for r in rows:
        if len(r[0]) > 2 or len(r[1]) > 5:
            wide = True
    with ui.grid(columns=4 if wide else 5):
        for r in rows:
            letter_card(r, cased, p)


def letter_card(row, cased, p):
    rec = trainer.record(p, "L" + row[0])
    color = None
    if rec is not None:
        color = "success" if rec[0] >= trainer.KNOWN else ("danger" if rec[0] == 0 else None)
    ui.card(
        ui.label(trainer.shown_glyph(row[0], cased), style="headline", color=color),
        ui.caption(row[1]),
        on_click=lambda: tap_letter(row),
        key="card:" + row[0],
    )


def tap_letter(row):
    say(row[0], saved.target)
    if row[2]:
        ui.toast(row[0] + "  " + row[1] + ": " + row[2])


def words_view():
    t, so = saved.target, saved.second
    T = langs.data(t).WORDS
    S = langs.data(so).WORDS
    topics = [("all", "All")] + [(x[0], x[1]) for x in concepts.TOPICS]
    ui.chips(topics, value=saved.topic, on_change=set_topic, key="topic")
    modes = [("t2s", langs.name(t) + " → " + langs.name(so)), ("s2t", langs.name(so) + " → " + langs.name(t)),
             ("type", "Type " + langs.name(t))]
    mode = saved.word_mode if saved.word_mode in [m[0] for m in modes] else "t2s"
    ui.select(modes, value=mode, on_change=set_word_mode, style="segmented", key="word_mode")
    keys = [k for k in topic_keys(saved.topic) if k in T and k in S]
    p = progress(t)
    ui.caption(str(trainer.known_count(p, ["W" + k for k in keys])) + " of " + str(len(keys)) + " learned")
    ui.button("Start", on_click=start_words, primary=True, enabled=len(keys) >= 2, icon="play_arrow")
    rows = []
    for k in keys:
        caption = word_caption(T[k], t)
        sub = (caption + "  ·  " if caption else "") + S[k][0]
        rows.append(ui.item(T[k][0], subtitle=sub, on_click=lambda k=k: say(T[k][0], t), key="w:" + k))
    ui.list(rows, empty="No words in both languages here.")


def sentences_view():
    t, so = saved.target, saved.second
    items = sentence_items(t, so)
    made = len(ai_sentences(t, so))
    modes = [("t2s", "Pick the meaning"), ("s2t", "Pick the " + langs.name(t))]
    if langs.spaced(t):
        modes.append(("order", "Put in order"))
    mode = saved.sentence_mode if saved.sentence_mode in [m[0] for m in modes] else "t2s"
    ui.select(modes, value=mode, on_change=set_sentence_mode, style="segmented", key="sentence_mode")
    line = str(len(items)) + " sentences in both " + langs.name(t) + " and " + langs.name(so)
    if made:
        line = line + ", " + str(made) + " of them written by AI"
    ui.caption(line)
    with ui.row():
        ui.button("Start", on_click=start_sentences, primary=True, enabled=len(items) >= 4, icon="play_arrow")
        ui.button("Browse", on_click=lambda: plugin.push(browse_page, title="Sentences"), icon="list")
    if "ai" in plugin.permissions:
        with ui.row():
            ui.button("5 more with AI", on_click=more_sentences, enabled=not s.busy, icon="auto_awesome")
            if made:
                ui.button("Forget AI sentences", on_click=forget_ai_sentences)
        if s.busy:
            ui.progress()


def browse_page():
    t, so = saved.target, saved.second
    items = sentence_items(t, so)
    rows = []
    for key in sorted(items.keys())[:150]:
        item = items[key]
        rows.append(ui.item(item["t"], subtitle=item["s"] + ("  (AI)" if item["ai"] else ""),
                            on_click=lambda text=item["t"]: say(text, t), key="b:" + key))
    ui.list(rows, empty="No sentences in both languages yet.")


def progress_view():
    t = saved.target
    p = progress(t)
    letter_keys = []
    cats, cased = letter_categories(t)
    for c in cats:
        letter_keys = letter_keys + ["L" + r[0] for r in c[2]]
    word_keys = ["W" + k for k in topic_keys("all") if k in langs.data(t).WORDS]
    sentence_keys = [k for k in p if k.startswith("S") or k.startswith("A")]
    with ui.row():
        if letter_keys:
            ui.ring(trainer.mastery(p, letter_keys), label="Letters",
                    caption=str(trainer.known_count(p, letter_keys)) + " of " + str(len(letter_keys)))
        ui.ring(trainer.mastery(p, word_keys), label="Words",
                caption=str(trainer.known_count(p, word_keys)) + " of " + str(len(word_keys)))
        ui.stat("Sentences", str(trainer.known_count(p, sentence_keys)), caption="learned")
    weak = trainer.weak(p, letter_keys + word_keys, limit=10)
    ui.label("Weak spots", style="title")
    words = langs.data(t).WORDS
    rows = []
    for k in weak:
        rec = p[k]
        what = k[1:]
        if k.startswith("W") and what in words:
            what = words[what][0]
        rows.append(ui.item(what, subtitle=str(rec[2]) + " of " + str(rec[1]) + " right", key="weak:" + k))
    ui.list(rows, empty="Nothing missed yet.")
    with ui.row():
        ui.button("Practise weak spots", on_click=practise_weak, primary=True, enabled=len(weak) > 0)
        ui.button("Reset", on_click=ask_reset, color="danger")


def quiz_page():
    quiz = s.quiz
    if quiz["done"]:
        return summary_page(quiz)
    q = quiz["q"]
    ans = quiz["answered"]
    with ui.row():
        ui.caption("Question " + str(quiz["n"]) + " of " + str(quiz["total"]) + " · " + str(quiz["right"]) + " right")
        ui.button("End", on_click=end_quiz)
    ui.progress(quiz["n"] / quiz["total"])
    ui.label(q["prompt"], style="headline" if len(q["prompt"]) <= 16 else "title")
    if q["caption"]:
        ui.caption(q["caption"])
    if q["speak"] is not None:
        ui.icon_button("volume_up", on_click=lambda: say(q["speak"][0], q["speak"][1]), label="Hear it")
    mode = quiz["mode"]
    if mode in MC_MODES:
        columns = 1 if quiz["kind"] == "sentence" else 2
        with ui.grid(columns=columns):
            for option in q["options"]:
                option_button(option, q, ans)
    elif mode == "type":
        ui.input(label="In " + langs.name(saved.target), value=s.typed, on_change=set_typed,
                 on_submit=submit_typed, placeholder="Type, then Enter", key="answer" + str(quiz["n"]))
        if ans is None:
            with ui.row():
                ui.button("Check", on_click=lambda: submit_typed(None), primary=True)
                ui.button("Show answer", on_click=give_up)
    else:
        ui.label(" ".join(q["built"]) or "Tap the words in order.", style="title" if q["built"] else "body")
        if ans is None:
            ui.keys(chunks(q["tokens"], 4), on_press=add_token, key="tokens" + str(quiz["n"]))
            with ui.row():
                ui.button("Undo", on_click=undo_token, enabled=len(q["built"]) > 0)
                ui.button("Check", on_click=check_order, primary=True, enabled=len(q["tokens"]) == 0)
    if ans is not None:
        feedback(quiz, q, ans)


def option_button(option, q, ans):
    color = None
    if ans is not None:
        if option == q["answer"] or option in q["accept"]:
            color = "success"
        elif option == ans["chosen"]:
            color = "danger"
    ui.button(option, on_click=lambda: choose(option), color=color, enabled=ans is None, key="opt:" + option)


def feedback(quiz, q, ans):
    if ans["ok"]:
        ui.label(ans["note"] or "Right!", color="success", style="title")
    else:
        ui.label("Not quite.", color="danger", style="title")
    ui.label(q["solution"])
    with ui.row():
        ui.button("Next" if quiz["n"] < quiz["total"] else "Finish", on_click=next_question, primary=True)
        if q["kind"] != "letter" and "ai" in plugin.permissions:
            ui.button("Explain", on_click=explain, enabled=not s.busy, icon="auto_awesome")
    if s.busy:
        ui.progress()
    if s.explain:
        ui.markdown(s.explain)


def summary_page(quiz):
    ui.label("Round done", style="headline")
    ui.ring(quiz["right"] / max(1, quiz["total"]), label=str(quiz["right"]) + " of " + str(quiz["total"]) + " right")
    if quiz["missed"]:
        ui.label("To look at again", style="title")
        for line in quiz["missed"][:10]:
            ui.label(line)
    with ui.row():
        ui.button("Again", on_click=again, primary=True)
        ui.button("Done", on_click=end_quiz)


def again():
    quiz = s.quiz
    quiz["n"] = 0
    quiz["right"] = 0
    quiz["missed"] = []
    quiz["done"] = False
    next_question()


def chunks(items, size):
    rows = []
    for i in range(0, len(items), size):
        rows.append(items[i:i + size])
    return rows or [[]]


def sources_page():
    ui.markdown(
        "**Letter charts** were written for this plugin, with Hepburn romanization for Japanese, "
        "Revised Romanization for Korean, ELOT 743 for Greek, the Royal Thai General System for Thai "
        "and the national system for Georgian.\n\n"
        "**Words** come from the translation tables of English Wiktionary (wiktionary.org), "
        "by its contributors, under CC BY-SA 4.0, through kaikki.org. A few were picked by hand.\n\n"
        "**Sentences** come from Tatoeba (tatoeba.org) under CC BY 2.0 FR. Each one's number "
        "is in the plugin's data files, and tatoeba.org/sentences/show/<number> shows who wrote it.\n\n"
        "Two languages are paired through English, so a Japanese sentence and its Hindi match are "
        "both translations of the same English one.\n\n"
        "The plugin's code is MIT licensed."
    )
