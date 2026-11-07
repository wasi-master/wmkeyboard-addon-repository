# Selection actions: buttons on the bar over text you select.
#
# plugin.json lists them under "actions", and asks for the "selection"
# permission. Tapping one calls transform(text, action) with the selected
# text and the action's id, and the string it returns takes the selection's
# place. Returning None leaves the text as it was. Undo on the bar takes the
# change back.
#
# The panel picks the quotes that Wrap in quotes uses. The choice is kept in
# wm.storage, which an action can read as well as the panel.

STYLES = [
    {"id": "curly", "open": "“", "close": "”", "label": "“Curly”"},
    {"id": "straight", "open": '"', "close": '"', "label": '"Straight"'},
    {"id": "guillemets", "open": "«", "close": "»", "label": "«Guillemets»"},
    {"id": "corner", "open": "「", "close": "」", "label": "「Corner」"},
]

UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWER = "abcdefghijklmnopqrstuvwxyz"


def current_style():
    chosen = wm.storage.get("quotes", "curly")
    for style in STYLES:
        if style["id"] == chosen:
            return style
    return STYLES[0]


def rot13(text):
    """Each Latin letter moves 13 places along the alphabet, so the same
    action undoes itself."""
    out = []
    for c in text:
        if c in UPPER:
            out.append(UPPER[(UPPER.index(c) + 13) % 26])
        elif c in LOWER:
            out.append(LOWER[(LOWER.index(c) + 13) % 26])
        else:
            out.append(c)
    return "".join(out)


def transform(text, action):
    if action == "rot13":
        return rot13(text)
    if action == "quote":
        style = current_style()
        return style["open"] + text + style["close"]
    return None


def render():
    chosen = current_style()
    rows = [ui.label("Quotes for Wrap in quotes", style="title")]
    for style in STYLES:
        rows.append(ui.button(
            style["id"],
            style["label"],
            style="primary" if style["id"] == chosen["id"] else None,
        ))
    rows.append(ui.label(
        "Select some text, then tap ROT13 or Wrap in quotes on the bar.",
        style="caption",
    ))
    return ui.column(rows)


def on_event(e):
    if e["type"] == "click":
        wm.storage.set("quotes", e["id"])
