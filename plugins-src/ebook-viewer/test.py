# Tests for E-book Viewer, run by tools/test_plugins.py under wm-python-cli.
# tests/ holds an EPUB 3 book, an EPUB 2 one, a FictionBook and a comic.

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


# MARK: - EPUB 3: nav document, cover-image, several authors

root = shown("epub", "river.epub")
text = words(root)
has(text, "The Slow River", "Ayesha Karim, Tom Lee", "Small Press · 2024-05-01 · en", "A quiet novel.",
    "Part One", "    The bridge", "The river ran slow", "She waited by the bridge.")
assert find(root, "image")[0]["src"].startswith("data:iVBORw0KGgo"), "the cover, its %20 name undone"

# MARK: - EPUB 2: NCX contents and <meta name="cover">

root = shown("epub", "old.epub")
has(words(root), "Old Tales", "Chapter 1", "    Scene A", "The river ran slow")
assert find(root, "image"), "the cover named by meta"

# MARK: - FictionBook

root = shown("epub", "tale.fb2")
has(words(root), "Winter Tale", "Anna Petrova", "ru", "A short story.", "One", "Two", "The river ran slow")
assert find(root, "image"), "the base64 cover"

# MARK: - comics, pages in number order

root = shown("comic", "hero.cbz")
has(words(root), "Hero", "Issue 1", "Sam", "3 pages")
alts = [i["alt"] for i in find(root, "image")]
assert alts == ["page1.png", "page2.png", "page10.png"], alts

# MARK: - covers for the grid

for name in ("river.epub", "old.epub"):
    t = plugin_test.thumbnail("epub", "tests/" + name)
    assert t["ok"] and t["value"].startswith("iVBORw0KGgo"), name
assert plugin_test.thumbnail("comic", "tests/hero.cbz")["value"].startswith("iVBORw0KGgo")
assert plugin_test.thumbnail("epub", "tests/tale.fb2")["value"] is None
