# Tests for Lorem Ipsum, run by tools/test_plugins.py (on wm-python-cli, or
# on CPython stand-ins). The text is random, so these check its shape: how
# many words, sentences and paragraphs, how it starts, and that it fits.

import plugin_test


def kids(args):
    if len(args) == 1 and isinstance(args[0], list):
        return args[0]
    return list(args)


def u_column(*children):
    return {"type": "column", "children": kids(children)}


def u_row(*children):
    return {"type": "row", "children": kids(children)}


def u_label(text, style=None):
    return {"type": "label", "text": text, "style": style}


def u_output(text, id=None, mono=False, insertable=True, copyable=True):
    return {"type": "output", "id": id, "text": text}


def u_button(id, text, style=None, enabled=True):
    return {"type": "button", "id": id, "text": text, "style": style, "enabled": enabled}


def u_toggle(id, label, checked=False):
    return {"type": "toggle", "id": id, "label": label, "checked": checked}


def u_spacer(height=8):
    return {"type": "spacer", "height": height}


ui = {
    "column": u_column, "row": u_row, "label": u_label, "output": u_output,
    "button": u_button, "toggle": u_toggle, "spacer": u_spacer,
}


def w_log(*values):
    pass


wm = {
    "api_version": 4, "plugin_id": "com.wasimaster.loremipsum", "plugin_version": "test",
    "log": w_log,
}

plugin = plugin_test.load("main.py", wm, ui)
fails = []


def expect(what, got, want):
    if got != want:
        fails.append(what + ": expected " + repr(want) + ", got " + repr(got))


# Read the text from what render() draws, not from the plugin's globals:
# wm-python-cli hands back a copy of them taken at load time.
def shown():
    return plugin["render"]()["children"][4]["text"]


def click(eid, times=1):
    for _ in range(times):
        plugin["on_event"]({"type": "click", "id": eid})
    return shown()


def classic(on):
    plugin["on_event"]({"type": "toggle", "id": "classic", "value": on})
    return shown()


def sentences(text):
    return text.count(".")


first = shown()
expect("opens with three paragraphs", len(first.split("\n\n")), 3)
expect("opens with the classic line", first.startswith("Lorem ipsum dolor sit amet, consectetur adipiscing elit. "), True)

text = click("words")
expect("50 words", len(text.split(" ")), 50)
expect("words start with the classic words", text.startswith("Lorem ipsum dolor sit amet consectetur"), True)
expect("words have no full stop", "." in text, False)
expect("10 more words", len(click("more").split(" ")), 60)
expect("down to 1 word", len(click("less", 10).split(" ")), 1)
expect("1 word is Lorem", shown(), "Lorem")
expect("1 is the floor", len(click("less").split(" ")), 1)
expect("up from 1 goes to 10", len(click("more").split(" ")), 10)
text = classic(False)
expect("no classic start", text.startswith("Lorem ipsum dolor"), False)
expect("still 10 words", len(text.split(" ")), 10)
classic(True)

text = click("sentences")
expect("5 sentences", sentences(text), 5)
expect("sentences start classic", text.startswith("Lorem ipsum dolor sit amet, consectetur adipiscing elit. "), True)
expect("2 sentences", sentences(click("less", 3)), 2)
expect("reset puts 5 back", sentences(click("reset")), 5)

expect("paragraphs remembers 3", len(click("paragraphs").split("\n\n")), 3)
for unit in ["words", "sentences", "paragraphs"]:
    click(unit)
    text = click("more", 400)
    expect(unit + " fits one block", len(text) <= 2048, True)
    expect(unit + " ends whole", text.endswith(".") or unit == "words", True)
    expect(unit + " never ends on a space", text.endswith(" "), False)
    expect(unit + " + is greyed at the top", plugin["render"]()["children"][1]["children"][2]["enabled"], False)

before = shown()
expect("new text rolls again", click("new") != before, True)

if fails:
    for message in fails:
        print("  " + message)
    raise RuntimeError("lorem-ipsum: " + str(len(fails)) + " checks failed")
print("lorem-ipsum: all checks passed")
