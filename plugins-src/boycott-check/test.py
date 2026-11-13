# Tests for Boycott Check, run by tools/test_plugins.py under
# `wm-python-cli test plugins-src/boycott-check`. Every host call is mocked:
# GitHub (the list's latest commit and data.json), Open Food Facts, the
# scanners and share.open. tests/data.json is a slice of the real Tech for
# Palestine dataset, so the matching runs on real names.

import json

import plugin_test

COMMITS = "https://api.github.com/repos/TechForPalestine/boycott-israeli-consumer-goods-dataset/commits"
RAW = "https://raw.githubusercontent.com/TechForPalestine/boycott-israeli-consumer-goods-dataset/"
OFF = "https://world.openfoodfacts.org/api/v2/product/"
DATA = plugin_test.read("tests/data.json")


def commit(sha):
    return {"status": 200, "headers": {},
            "text": json.dumps([{"sha": sha, "commit": {"committer": {"date": "2024-02-19T23:45:47Z"}}}])}


def product(code, **fields):
    p = {"code": code}
    p.update(fields)
    return {"status": 200, "headers": {}, "text": json.dumps({"code": code, "status": 1, "product": p})}


UNKNOWN = {"status": 404, "headers": {}, "text": json.dumps({"code": "0", "status": 0, "status_verbose": "product not found"})}

PRODUCTS = [
    {"when": {"url": OFF + "7613036249928.json"},
     "reply": product("7613036249928", product_name="Gold Blend", brands="Nescafé, Nestlé", brand_owner="Nestlé")},
    {"when": {"url": OFF + "5449000131805.json"},
     "reply": product("5449000131805", product_name="Coca-Cola Zero", brands="Coca-Cola Zero")},
    {"when": {"url": OFF + "5000112637922.json"},
     "reply": product("5000112637922", product_name="Powerade", brands="Powerade", brand_owner="The Coca-Cola Company")},
    {"when": {"url": OFF + "1234567890128.json"},
     "reply": product("1234567890128", product_name="Medjool dates", brands="Desert Farm", origins_tags=["en:israel"])},
    {"when": {"url": OFF + "4006040000001.json"},
     "reply": product("4006040000001", product_name="Oat drink", brands="Some Small Farm", brand_owner="Small Farm GmbH")},
    {"when": {"url": OFF + "*"}, "reply": UNKNOWN},
]


def mock(sha="abc123", code="7613036249928", text="NESCAFÉ\nGold Blend\nNestlé", products=None):
    return {
        "http.request": [
            {"when": {"url": COMMITS}, "reply": commit(sha)},
            {"when": {"url": RAW + "*"}, "reply": {"status": 200, "headers": {}, "text": DATA}},
        ] + (products or PRODUCTS),
        "scan.qr": code,
        "scan.text": text,
        "share.open": None,
        "ui.toast": None,
    }


def walk(node, out):
    if isinstance(node, dict):
        out.append(node)
        for v in node.values():
            walk(v, out)
    elif isinstance(node, list):
        for v in node:
            walk(v, out)
    return out


def ids(r):
    return [n.get("id") for n in walk(r["ui"], []) if n.get("id")]


def text_of(r):
    out = []
    for n in walk(r["ui"], []):
        for f in ("text", "title", "subtitle", "label", "empty"):
            v = n.get(f)
            if isinstance(v, str):
                out.append(v)
    return "\n".join(out)


def ok(r, what):
    assert r["ok"], what + ": " + str(r.get("error"))
    return r


def fresh(**kw):
    """A session with the list downloaded."""
    s = plugin_test.session(mock=mock(**kw), settings={"auto_update": True})
    ok(s["load"](), "load")
    ok(s["event"]({"type": "click", "id": "download"}), "download")
    ok(s["settle"](), "settle download")
    return s


def stored(s, k):
    v = s["storage"]()[k]
    return json.loads(v) if isinstance(v, str) else v


def search(s, q):
    return ok(s["event"]({"type": "change", "id": "query", "value": q}), "search " + q)


def results(r):
    return [i for i in ids(r) if i.startswith("entry:")]


# First open: no list yet, but the BDS targets already answer.
s = plugin_test.session(mock=mock(), settings={"auto_update": True})
r = ok(s["load"](), "load")
assert "download" in ids(r), ids(r)
assert results(search(s, "intel")) == ["entry:bds:intel"], results(search(s, "intel"))
assert "Download the full list" in text_of(search(s, "zzzz")), text_of(search(s, "zzzz"))
search(s, "")

# Download: the raw file is fetched at the commit GitHub named, and kept in storage.
ok(s["event"]({"type": "click", "id": "download"}), "download")
ok(s["settle"](), "settle")
store = s["storage"]()
meta = stored(s, "tfp:meta")
assert meta["sha"] == "abc123" and meta["date"] == "2024-02-19", meta
assert meta["counts"] == {"brands": 14, "flagged": 13, "companies": 2}, meta["counts"]
urls = [c["args"]["url"] for c in s["calls"]() if c["op"] == "http.request"]
assert urls == [COMMITS, RAW + "abc123/output/json/data.json"], urls
for k in store:
    assert len(store[k] if isinstance(store[k], str) else json.dumps(store[k])) < 64000, k
assert "download" not in ids(s["render"]())

# Typed search: case, accents, apostrophes and the "(Mars)" note don't matter.
assert results(search(s, "DOVE")) == ["entry:tfp:dove", "entry:tfp:dovemars"], results(search(s, "DOVE"))
assert results(search(s, "l'oréal")) == ["entry:tfp:lorealloreal"], results(search(s, "l'oréal"))
assert results(search(s, "loreal")) == ["entry:tfp:lorealloreal"]
coke = results(search(s, "coca-cola"))
assert coke[:2] == ["entry:bds:coca-cola", "entry:tfp:cocacola"], coke
assert "entry:tfp:nescafe" in results(search(s, "nes")), results(search(s, "nes"))
assert results(search(s, "qwertyuiop")) == []
assert "Not on these lists." in text_of(search(s, "qwertyuiop"))

# An entry's page: both lists, reasons, owner, sources and alternatives.
search(s, "coca cola")
r = ok(s["event"]({"type": "click", "id": "entry:tfp:cocacola"}), "open coca cola")
t = text_of(r)
assert "Tech for Palestine" in t and "BDS movement" in t, t
assert "Grassroots boycott the BDS movement supports" in t, t
assert "Operates in illegal Israeli settlements" in t, t
assert "the coca cola company" in t and "Owner, not listed separately" in t, t
assert "not https: tap to share" in t, t
s["event"]({"type": "back"})
search(s, "kitkat")
r = ok(s["event"]({"type": "click", "id": "entry:tfp:kitkat"}), "open kitkat")
assert "entry:tfp:ulker" in ids(r) and "entry:tfp:nestle" in ids(r), ids(r)
source = [n for n in walk(r["ui"], []) if n.get("id") == "link:b:kitkat:0"]
assert source and source[0]["subtitle"].startswith("https://"), ids(r)
ok(s["event"]({"type": "click", "id": "link:b:kitkat:0"}), "open a source")
opened = [c["args"]["url"] for c in s["calls"]() if c["op"] == "share.open"]
assert opened == [source[0]["subtitle"]], opened
ok(s["event"]({"type": "click", "id": "entry:tfp:ulker"}), "open the alternative")
assert "Alternative: Tech for Palestine lists it to support" in text_of(s["render"]())
s["event"]({"type": "back"})
s["event"]({"type": "back"})
search(s, "")
assert "recent:0" in ids(s["render"]())

# The weekly check finds the same commit and downloads nothing.
before = len(s["calls"]())
ok(s["event"]({"type": "command", "id": "update"}), "update")
ok(s["settle"](), "settle update")
after = [c["args"]["url"] for c in s["calls"]()[before:] if c["op"] == "http.request"]
assert after == [COMMITS], after

# A newer commit replaces the list: answer the check by hand with another sha.
def last_token(s):
    return [c for c in s["calls"]() if "async" in c["args"]][-1]["args"]["async"]


s2 = fresh()
s2["event"]({"type": "command", "id": "update"})
ok(s2["event"]({"type": "result", "token": last_token(s2), "value": commit("def456")}), "newer commit")
ok(s2["settle"](), "settle newer")
assert stored(s2, "tfp:meta")["sha"] == "def456", stored(s2, "tfp:meta")
assert [c for c in s2["calls"]() if c["op"] == "http.request"][-1]["args"]["url"] == RAW + "def456/output/json/data.json"

# Barcodes through Open Food Facts.
s = fresh()
ok(s["event"]({"type": "click", "id": "scan"}), "scan")
r = ok(s["settle"](), "settle scan")
t = text_of(r)
assert "On a boycott list" in t, t
assert "entry:tfp:nescafe" in ids(r) and "entry:tfp:nestle" in ids(r), ids(r)
assert "Owner: Nestlé" in t, t
offs = [c["args"] for c in s["calls"]() if c["op"] == "http.request" and c["args"]["url"].startswith(OFF)]
assert offs[0]["params"]["fields"].startswith("code,product_name,brands,brand_owner"), offs

s = fresh(code="5449000131805")
s["event"]({"type": "click", "id": "scan"})
r = s["settle"]()
t = text_of(r)
assert "Not listed itself, but related names are" in t, t
assert "similar name Coca-Cola Zero" in t and "check the owner" in t, t

s = fresh(code="5000112637922")
s["event"]({"type": "click", "id": "scan"})
r = s["settle"]()
assert "On a boycott list" in text_of(r) and "entry:tfp:cocacola" in ids(r), text_of(r)
assert "this product's owner The Coca-Cola Company" in text_of(r), text_of(r)

s = fresh(code="1234567890128")
s["event"]({"type": "click", "id": "scan"})
r = s["settle"]()
assert "On a boycott list" in text_of(r) and "entry:bds:israeli-produce" in ids(r), text_of(r)
assert "Open Food Facts gives Israel as its origin" in text_of(r), text_of(r)

s = fresh(code="4006040000001")
s["event"]({"type": "click", "id": "scan"})
r = s["settle"]()
assert "Not on these lists" in text_of(r) and results(r) == [], text_of(r)

s = fresh(code="7290000000001")
s["event"]({"type": "click", "id": "scan"})
r = s["settle"]()
assert "doesn't know this barcode" in text_of(r), text_of(r)
assert "GS1 Israel" in text_of(r), text_of(r)

s = fresh(code="https://example.com/not-a-product")
s["event"]({"type": "click", "id": "scan"})
r = s["settle"]()
assert "isn't a product barcode" in text_of(r), text_of(r)

s = fresh()
s["event"]({"type": "click", "id": "scan"})
s["event"]({"type": "result", "token": last_token(s), "value": "7613036249928"})
r = s["event"]({"type": "result", "token": last_token(s),
                "value": {"error": {"kind": "ConnectionError", "message": "offline"}}})
assert "No connection" in text_of(r), text_of(r)

# Reading a label: names found in the text, and an honest nothing.
s = fresh()
s["event"]({"type": "click", "id": "read"})
r = s["settle"]()
found = results(r)
assert "entry:tfp:nescafe" in found and "entry:tfp:nestle" in found, found
assert "logo without a readable name" in text_of(r), text_of(r)
s = fresh(text="Fresh whole milk\n1 litre")
s["event"]({"type": "click", "id": "read"})
r = s["settle"]()
assert results(r) == [] and "No listed name" in text_of(r), text_of(r)

# @boycott chip.
s = fresh()
r = ok(s["event"]({"type": "keyword", "id": "boycott", "value": "starbucks"}), "keyword")
assert results(r) == ["entry:tfp:starbucks"], results(r)

print("boycott-check: all checks passed")
