# Lorem Ipsum: placeholder text, by the word, sentence or paragraph.
#
# A tab for each unit, a count you can type or pick, and the result ready to
# insert. Every change makes a fresh text; New text in the header rolls again
# with the same settings.

from wm import plugin, ui

import lorem

# unit: label, default count, quick picks, most
UNITS = {
    "words": ("Words", 50, [10, 25, 50, 100, 200], 400),
    "sentences": ("Sentences", 5, [1, 3, 5, 10, 15], 40),
    "paragraphs": ("Paragraphs", 3, [1, 2, 3, 4, 5], 10),
}
ORDER = ["words", "sentences", "paragraphs"]

saved = plugin.state(persist=True, counts={"words": 50, "sentences": 5, "paragraphs": 3}, classic=True)
view = plugin.state(unit="words", texts={}, typed={})


def count(unit):
    return saved.counts.get(unit, UNITS[unit][1])


def roll(unit):
    """A fresh text for [unit] at its count."""
    texts = dict(view.texts)
    texts[unit] = lorem.generate(unit, count(unit), saved.classic)
    view.texts = texts


def set_count(unit, n):
    counts = dict(saved.counts)
    counts[unit] = n
    saved.counts = counts
    roll(unit)


@plugin.command("New text", icon="refresh")
def new_text():
    roll(view.unit)


def tab_changed(index):
    view.unit = ORDER[index]


def classic_changed(on):
    saved.classic = on
    view.texts = {}


def unit_page(unit):
    label, _, picks, most = UNITS[unit]
    if unit not in view.texts:
        roll(unit)
    text = view.texts[unit]
    shown = lorem.fit(text)
    n = count(unit)
    name = label.lower() if n != 1 else label.lower()[:-1]

    def typed(value):
        typed_now = dict(view.typed)
        typed_now[unit] = value
        view.typed = typed_now
        got = lorem.count_of(value, most)
        if got is not None and got != count(unit):
            set_count(unit, got)

    def picked(value):
        typed_now = dict(view.typed)
        typed_now.pop(unit, None)
        view.typed = typed_now
        set_count(unit, int(value))

    children = [
        # The count itself is a box: any number, not just the steps.
        ui.input(label="How many " + label.lower(), value=view.typed.get(unit, str(n)), kind="number",
                 placeholder="1 to " + str(most), on_change=typed, key=unit + "_count"),
        ui.chips([(str(p), str(p)) for p in picks], value=str(n) if n in picks else None, on_change=picked,
                 key=unit + "_picks"),
        ui.output(shown, key=unit + "_text"),
    ]
    if len(shown) < len(text):
        children.append(ui.caption("Cut to the " + str(lorem.MOST_CHARACTERS) + " characters one block holds."))
    else:
        children.append(ui.caption(str(n) + " " + name + "."))
    return ui.page(label, *children)


def render():
    ui.toggle("Start with “Lorem ipsum dolor sit amet”", value=saved.classic, on_change=classic_changed, key="classic")
    ui.tabs(*[unit_page(u) for u in ORDER], on_change=tab_changed, key="units")
