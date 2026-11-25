# Tests for Data Viewer, run by tools/test_plugins.py under wm-python-cli.

import json

import sqlite


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


# MARK: - CSV and TSV

root = shown("table", "sales.csv")
has(words(root), "3 rows · 3 columns")
t = find(root, "table")[0]
assert t["header"] == ["name", "city", "total"], t
assert t["rows"] == [["Lee, Ann", "Dhaka", "1200.50"], ["Bo", "New\nYork", "-30"], ["Cy", "Paris", "7"]], t
assert t["align"] == ["start", "start", "end"], t["align"]

t = find(shown("table", "plain.tsv"), "table")[0]
assert t["header"] == ["a", "b"] and t["rows"] == [["x", "1"]], t

# MARK: - JSON

root = shown("json", "config.json")
text = words(root)
has(text, "7 keys", "users  ·  2 items", "ports  ·  2 items", "deep  ·  1 item")
tables = find(root, "table")
assert tables[0]["rows"] == [["name", "demo"], ["version", "3"], ["debug", "false"], ["owner", "null"]], tables[0]
assert tables[1]["header"] == ["id", "name", "tags", "admin"], tables[1]
assert tables[1]["rows"] == [["1", "Ann", "[\"a\"]", "null"], ["2", "Bo", "null", "true"]], tables[1]

root = shown("json", "events.jsonl")
has(words(root), "2 records · 1 lines are not JSON")
assert find(root, "table")[0]["rows"] == [["1", "start"], ["2", "stop"]]

root = shown("json", "broken.json")
has(words(root), "Not valid JSON")
assert find(root, "code")[0]["text"] == "{\"a\": 1,"

# MARK: - notebooks

root = shown("notebook", "analysis.ipynb")
text = words(root)
has(text, "3 cells · Python 3", "# Analysis\nSome *notes*.", "In [3]", "print('hi')\n1 + 1", "hi\n", "ValueError: bad", "raw text")
assert find(root, "image")[0]["src"] == "data:iVBORw0KGgo=", "picture output"
assert find(root, "code")[0]["language"] == "py"

# MARK: - SQLite

assert sqlite.columns("CREATE TABLE t (\"a b\" TEXT, c INT DEFAULT (1+2), PRIMARY KEY (c))") == ["a b", "c"]
assert sqlite.varint(b"\x81\x00", 0) == (128, 2)

root = shown("sqlite", "shop.db")
text = words(root)
has(text, "2 tables · 1 views · SQLite, 1024-byte pages", "items", "empty", "No rows", "cheap (view)",
    "The first 100 rows are shown.", "CREATE TABLE items")
t = find(root, "table")[0]
assert t["header"] == ["id", "name", "price", "photo", "note"], t["header"]
assert t["rows"][0][:2] == ["-5", "Neg"], t["rows"][0]
pen = t["rows"][1]
assert pen[:4] == ["1", "Pen", "0.5", "‹2 bytes›"] and pen[4] == "x" * 199 + "…", pen
assert t["rows"][2][:3] == ["2", "Item 2", "2.5"], t["rows"][2]
assert len(t["rows"]) == 100

r = plugin_test.preview("sqlite", "tests/sales.csv", name="x.db")
has(words(r["ui"]["root"]), "This is not an SQLite database.")
