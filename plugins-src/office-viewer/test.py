# Tests for Office Viewer, run by tools/test_plugins.py under wm-python-cli.
# The files in tests/ are small hand-made documents of each kind.

import json


def shown(preview, name):
    r = plugin_test.preview(preview, "tests/" + name)
    assert r["ok"], name + ": " + json.dumps(r.get("error"))
    return r["ui"]["root"]


def words(tree):
    """Every string in the widget tree, in order, one per line."""
    out = []
    stack = [tree]
    while stack:
        n = stack.pop()
        if isinstance(n, str):
            out.append(n)
        elif isinstance(n, list):
            stack.extend(reversed(n))
        elif isinstance(n, dict):
            stack.extend(reversed([v for k, v in n.items() if k != "type"]))
    return "\n".join(out)


def find(tree, kind):
    found = []
    stack = [tree]
    while stack:
        n = stack.pop()
        if isinstance(n, list):
            stack.extend(reversed(n))
        elif isinstance(n, dict):
            if n.get("type") == kind:
                found.append(n)
            stack.extend(reversed(list(n.values())))
    return found


def has(text, *needles):
    for needle in needles:
        assert needle in text, "missing " + json.dumps(needle) + " in:\n" + text


# MARK: - Word

root = shown("word", "report.docx")
text = words(root)
has(text, "Quarterly report · Rahim · 2026-03-04", "Sales rose & costs fell.", "•  First point")
labels = [l for l in find(root, "label") if l.get("style") != "caption"]
assert labels[0]["text"] == "Quarterly report" and labels[0]["style"] == "headline", labels[0]
assert labels[1]["text"] == "Sales" and labels[1]["style"] == "title", labels[1]
table = find(root, "table")[0]
assert table["header"] == ["Region", "Total"] and table["rows"] == [["North", "120"]], table

root = shown("word", "letter.odt")
text = words(root)
has(text, "Letter · Mina", "Dear friend", "Hello\tthere  !", "•  One")
table = find(root, "table")[0]
assert table["rows"] == [["c", "c"]], table

text = words(plugin_test.preview("word", "tests/notes.txt", name="notes.docx")["ui"]["root"])
has(text, "This is not a Word document.")

# MARK: - spreadsheets

root = shown("sheet", "budget.xlsx")
text = words(root)
has(text, "2 sheets", "Budget", "Notes", "Empty")
table = find(root, "table")[0]
assert table["header"] == ["Item", "Cost", "", ""], table
assert table["rows"] == [["Rent", "900", "", "TRUE"], ["Food", "300", "", ""]], table

root = shown("sheet", "stock.ods")
table = find(root, "table")[0]
assert table["header"] == ["Fruit", "Count"] and table["rows"] == [["Apple", "3"]], table

# MARK: - slides

root = shown("slides", "deck.pptx")
text = words(root)
has(text, "2 slides", "1. Welcome", "•  Agenda", "•  Numbers", "2. Plan", "•  Ship it")

text = words(shown("slides", "talk.odp"))
has(text, "1. Hello", "•  Point A")

# MARK: - thumbnails

t = plugin_test.thumbnail("word", "tests/report.docx")
assert t["ok"] and t["value"], t
assert t["value"].startswith("iVBORw0KGgo"), "the saved first-page picture, a PNG in base64"
assert plugin_test.thumbnail("word", "tests/letter.odt")["value"], "OpenDocument's Thumbnails/thumbnail.png"
assert plugin_test.thumbnail("slides", "tests/deck.pptx")["value"] is None, "no picture saved"
