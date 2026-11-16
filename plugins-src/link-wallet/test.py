# Tests for Link wallet, run by tools/test_plugins.py under wm-python-cli:
# the link rules on their own, then the panel driven as the keyboard drives
# it, with the phone's answers mocked.

import json

import links


def expect(got, want, what):
    assert got == want, what + ": got " + json.dumps(got) + ", want " + json.dumps(want)


# MARK: - what counts as a link

expect(links.normalise("example.com"), "https://example.com", "bare name")
expect(links.normalise("  docs.example.org/a?b=1#c "), "https://docs.example.org/a?b=1#c", "bare name with a path")
expect(links.normalise("http://example.com/x"), "http://example.com/x", "http kept")
expect(links.normalise("HTTPS://Example.com"), "https://Example.com", "scheme in small letters")
expect(links.normalise("192.168.1.20:8080/admin"), "http://192.168.1.20:8080/admin", "home address is http")
expect(links.normalise("localhost:3000"), "http://localhost:3000", "localhost is http")
expect(links.normalise("nas.local:5000"), "http://nas.local:5000", "host and port")
expect(links.normalise("https://"), None, "no site")
expect(links.normalise("https://user@evil.example"), None, "user name in front")
expect(links.normalise("javascript:alert(1)"), None, "javascript")
expect(links.normalise("mailto:a@example.com"), None, "mailto is not a web link")
expect(links.normalise("file:///sdcard/x"), None, "file")
expect(links.normalise("two words.com"), None, "spaces")
expect(links.normalise("hello"), None, "a word")
expect(links.normalise(""), None, "nothing")

expect(links.first_link_in("look at https://example.com/a, it's good"), "https://example.com/a", "link in a message")
expect(links.first_link_in("(see example.org)."), "https://example.org", "bare name in brackets")
expect(links.first_link_in("no link here"), None, "message without a link")

expect(links.host_of("https://www.example.com/a?b"), "example.com", "host without www")
expect(links.host_of("http://192.168.1.20:8080/x"), "192.168.1.20:8080", "host with port")
expect(links.clean_title("  My \n  bank ", "https://bank.example"), "My bank", "title on one line")
expect(links.clean_title("", "https://www.bank.example/login"), "bank.example", "title from the site")
expect(len(links.clean_title("x" * 200, "https://a.example")), links.MOST_TITLE, "title cut")


# MARK: - the panel

def walk(node, out):
    if isinstance(node, dict):
        out.append(node)
        for value in node.values():
            walk(value, out)
    elif isinstance(node, list):
        for value in node:
            walk(value, out)
    return out


def widgets(r, kind=None):
    return [w for w in walk(r["ui"], []) if "type" in w and (kind is None or w["type"] == kind)]


def texts(r):
    out = []
    for w in widgets(r):
        for k in ("text", "title", "label", "subtitle", "action"):
            if isinstance(w.get(k), str):
                out.append(w[k])
    return " | ".join(out)


def ok(r, what):
    assert r["ok"], what + ": " + json.dumps(r.get("error"))
    return r


def ops(s, op):
    return [c["args"] for c in s["calls"]() if c["op"] == op]


def item_id(r, title):
    for w in widgets(r, "item"):
        if w.get("title") == title:
            return w["id"]
    raise AssertionError("no row " + title + " in " + texts(r))


def add(s, typed, name=None):
    ok(s["event"]({"type": "command", "id": "add"}), "Add")
    ok(s["event"]({"type": "change", "id": "url", "value": typed}), "type the address")
    r = ok(s["event"]({"type": "click", "id": "next"}), "Next")
    if name is not None:
        ok(s["event"]({"type": "change", "id": "title", "value": name}), "type the name")
    return ok(s["event"]({"type": "click", "id": "save"}), "Save")


mock = {
    "ui.toast": None,
    "share.visit": None,
    "share.text": None,
    "field.insert": None,
    "clipboard.set": None,
    "clipboard.get": "Here: https://news.example.com/today and more",
}
s = plugin_test.session(mock=mock)
r = ok(s["load"](), "load")
assert "No links yet" in texts(r), texts(r)

# Add starts from the copied link and names it after the site.
r = ok(s["event"]({"type": "command", "id": "add"}), "Add from the clipboard")
expect(r["inputs"], [["url", "https://news.example.com/today"]], "address from the clip")
r = ok(s["event"]({"type": "click", "id": "next"}), "Next")
expect(r["inputs"], [["title", "news.example.com"]], "name from the site")
r = ok(s["event"]({"type": "click", "id": "save"}), "Save")
cards = widgets(r, "card")
expect(len(cards), 1, "one button")
expect(cards[0]["holdable"], True, "button can be held")
expect(cards[0]["clickable"], True, "button can be tapped")

# A wrong address stays in the box with a note under it.
ok(s["event"]({"type": "command", "id": "add"}), "Add again")
ok(s["event"]({"type": "change", "id": "url", "value": "not a link"}), "type junk")
r = ok(s["event"]({"type": "click", "id": "next"}), "Next on junk")
assert "isn't a web address" in texts(r), texts(r)
ok(s["event"]({"type": "click", "id": "cancel"}), "Cancel")

r = add(s, "bank.example/login", "My bank")
r = add(s, "192.168.1.20:8123", "Home")
cards = widgets(r, "card")
expect([c["id"] for c in cards], ["link1", "link2", "link3"], "three buttons in order")
assert "My bank" in texts(r) and "bank.example" in texts(r), texts(r)

# A tap opens the link straight away.
ok(s["event"]({"type": "click", "id": "link2"}), "tap")
expect(ops(s, "share.visit"), [{"url": "https://bank.example/login"}], "opened directly")

# A hold opens the link's page.
r = ok(s["event"]({"type": "hold", "id": "link2", "x": 0, "y": 0}), "hold")
assert "Type it" in texts(r) and "Place 2 of 3." in texts(r), texts(r)
ok(s["event"]({"type": "click", "id": item_id(r, "Move forward")}), "move forward")
r = ok(s["render"](), "after the move")
assert "Place 3 of 3." in texts(r), texts(r)
assert "Move forward" not in texts(r), texts(r)
ok(s["event"]({"type": "click", "id": item_id(r, "Type it")}), "type it")
expect(ops(s, "field.insert"), [{"text": "https://bank.example/login"}], "typed")
r = ok(s["render"](), "back on the buttons")
expect([c["id"] for c in widgets(r, "card")], ["link1", "link3", "link2"], "moved to the end")

# Rename keeps the address.
r = ok(s["event"]({"type": "hold", "id": "link3", "x": 0, "y": 0}), "hold Home")
ok(s["event"]({"type": "click", "id": item_id(r, "Rename")}), "rename")
ok(s["event"]({"type": "change", "id": "title", "value": "Home Assistant"}), "new name")
ok(s["event"]({"type": "click", "id": "save"}), "save name")
r = ok(s["event"]({"type": "click", "id": item_id(s["render"](), "Copy")}), "copy")
expect(ops(s, "clipboard.set"), [{"text": "http://192.168.1.20:8123"}], "copied the address")
assert "Home Assistant" in texts(r), texts(r)

# Change link swaps the address and keeps the name.
r = ok(s["event"]({"type": "hold", "id": "link1", "x": 0, "y": 0}), "hold news")
ok(s["event"]({"type": "click", "id": item_id(r, "Change link")}), "change link")
ok(s["event"]({"type": "change", "id": "url", "value": "news.example.org"}), "new address")
ok(s["event"]({"type": "click", "id": "next"}), "next")
ok(s["event"]({"type": "click", "id": "save"}), "save link")
r = s["render"]()
ok(s["event"]({"type": "click", "id": item_id(r, "Share")}), "share")
expect(ops(s, "share.text")[-1]["text"], "https://news.example.org", "shared the new address")

# Delete, then Undo puts it back in its place.
r = ok(s["event"]({"type": "click", "id": item_id(s["render"](), "Delete")}), "delete")
expect([c["id"] for c in widgets(r, "card")], ["link3", "link2"], "deleted")
assert "Deleted news.example.com" in texts(r), texts(r)
r = ok(s["event"]({"type": "click", "id": "undo"}), "undo")
expect([c["id"] for c in widgets(r, "card")], ["link1", "link3", "link2"], "back in its place")

# The links are kept for the next open.
stored = json.dumps(s["storage"]())
assert "Home Assistant" in stored and "news.example.org" in stored, stored

print("link-wallet: ok")
