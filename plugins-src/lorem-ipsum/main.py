# Lorem Ipsum: placeholder text, by the word, sentence or paragraph.
#
# Pick a unit, set how many, and the result is ready to insert. Every change
# makes a fresh text; "New text" rolls again with the same settings.

import random

# The vocabulary of the classic filler, which comes from Cicero's
# "De finibus bonorum et malorum" (45 BC) by way of a 1500s typesetter.
WORDS = (
    "a ac accumsan adipiscing aenean aliquam aliquet amet ante arcu at auctor "
    "augue bibendum blandit commodo condimentum congue consectetur consequat "
    "convallis cras cursus dapibus diam dictum dignissim dolor donec dui duis "
    "egestas eget eleifend elementum elit enim erat eros est et etiam eu euismod "
    "facilisis faucibus felis fermentum feugiat fringilla fusce gravida habitant "
    "hendrerit iaculis id imperdiet in integer interdum ipsum justo lacinia lacus "
    "laoreet lectus leo libero ligula lobortis lorem luctus maecenas magna "
    "malesuada massa mattis mauris metus mi molestie mollis morbi nam nec neque "
    "nibh nisi nisl non nulla nullam nunc odio orci ornare pellentesque pharetra "
    "phasellus placerat porta porttitor posuere praesent pretium proin pulvinar "
    "purus quam quis quisque rhoncus risus rutrum sagittis sapien scelerisque sed "
    "sem semper sit sodales sollicitudin suscipit suspendisse tellus tempor "
    "tempus tincidunt tortor tristique turpis ultrices ultricies urna ut varius "
    "vehicula vel velit venenatis vestibulum vitae vivamus viverra volutpat "
    "vulputate"
).split()

OPENING = "Lorem ipsum dolor sit amet, consectetur adipiscing elit"

# unit: [label, default count, step, most]
UNITS = {
    "words": ["Words", 50, 10, 250],
    "sentences": ["Sentences", 5, 1, 20],
    "paragraphs": ["Paragraphs", 3, 1, 5],
}

# One text block on the keyboard holds 2048 characters, so a longer result is
# cut back to the last whole sentence (or word) that fits.
MOST_CHARACTERS = 2048
ORDER = ["words", "sentences", "paragraphs"]

# ----------------------------------------------------------------- state ----

unit = "paragraphs"
counts = {"words": 50, "sentences": 5, "paragraphs": 3}
classic_start = True
output = ""
trimmed = False

# ----------------------------------------------------------- generating ----


def capital(word):
    return word[0].upper() + word[1:]


def some_words(n):
    return [random.choice(WORDS) for _ in range(n)]


def sentence():
    """6 to 14 words, maybe with a comma, capitalised, ending in a full stop."""
    words = some_words(random.randint(6, 14))
    if len(words) > 7 and random.random() < 0.5:
        at = random.randint(3, len(words) - 4)
        words[at] = words[at] + ","
    return capital(" ".join(words)) + "."


def paragraph(size):
    return " ".join([sentence() for _ in range(size)])


def generate():
    n = counts[unit]
    if unit == "words":
        words = some_words(n)
        if classic_start:
            opening = OPENING.replace(",", "").lower().split()
            words = (opening + words)[:n]
        text = " ".join(words)
        return capital(text) if classic_start else text

    if unit == "sentences":
        parts = [sentence() for _ in range(n)]
        if classic_start:
            parts[0] = OPENING + "."
        return " ".join(parts)

    parts = [paragraph(random.randint(4, 7)) for _ in range(n)]
    if classic_start:
        parts[0] = OPENING + ". " + parts[0]
    return "\n\n".join(parts)


def fit(text):
    """The text, cut to MOST_CHARACTERS at a sentence end, or a word end."""
    if len(text) <= MOST_CHARACTERS:
        return text
    head = text[:MOST_CHARACTERS]
    end = head.rfind(".")
    if end > 0:
        return head[:end + 1]
    return head[:head.rfind(" ")]


def refresh():
    global output, trimmed
    text = generate()
    output = fit(text)
    trimmed = len(output) < len(text)


# --------------------------------------------------------------- events ----


def on_event(e):
    global unit, classic_start
    kind = e["type"]
    eid = e["id"]
    if kind == "click":
        if eid in UNITS:
            unit = eid
        elif eid == "less" or eid == "more":
            step = UNITS[unit][2]
            n = counts[unit] + (step if eid == "more" else -step)
            if eid == "less" and counts[unit] <= step:
                n = 1
            elif eid == "more" and counts[unit] == 1 and step > 1:
                n = step
            counts[unit] = max(1, min(UNITS[unit][3], n))
        elif eid == "reset":
            counts[unit] = UNITS[unit][1]
        refresh()
    elif kind == "toggle" and eid == "classic":
        classic_start = e["value"]
        refresh()


# --------------------------------------------------------------- render ----


def unit_buttons():
    buttons = []
    for key in ORDER:
        buttons.append(ui.button(key, UNITS[key][0], style="primary" if key == unit else None))
    return ui.row(buttons)


def count_row():
    n = counts[unit]
    name = UNITS[unit][0].lower()
    if n == 1:
        name = name[:-1]
    return ui.row(
        ui.button("less", "−", enabled=n > 1),
        ui.button("reset", str(n) + " " + name),
        ui.button("more", "+", enabled=n < UNITS[unit][3]),
    )


def render():
    if output == "":
        refresh()
    shown = [
        unit_buttons(),
        count_row(),
        ui.toggle("classic", "Start with “Lorem ipsum dolor sit amet”", checked=classic_start),
        ui.button("new", "New text"),
        ui.output(output, id="result"),
    ]
    if trimmed:
        shown.append(ui.label("Cut to the " + str(MOST_CHARACTERS) + " characters one block holds.", style="caption"))
    return ui.column(shown)
