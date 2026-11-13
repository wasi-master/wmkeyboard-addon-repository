# Tests for Open Food Facts, run by tools/test_plugins.py under wm-python-cli.
# Network answers are real replies saved in tests/ (Nutella from Open Food
# Facts, a foundation from Open Beauty Facts, a search), handed back as the
# result events the keyboard would send.

import json

NUTELLA = plugin_test.read("tests/nutella.json")
BEAUTY = plugin_test.read("tests/beauty.json")
SEARCH = plugin_test.read("tests/search.json")
NOT_FOUND = json.dumps({"status": "failure", "result": {"id": "product_not_found"}, "errors": []})
ACCOUNT = json.dumps({"user": "alice", "password": "s3cret"})

OFF = "https://world.openfoodfacts.org"
OBF = "https://world.openbeautyfacts.org"


def session(signed_in=False, settings=None):
    mock = {"secrets.get": ACCOUNT if signed_in else None, "secrets.set": None, "secrets.remove": None,
            "share.open": None, "ui.toast": None}
    s = plugin_test.session(mock=mock, settings=settings or {})
    r = s["load"]()
    assert r["ok"], r
    return s


def text_of(r):
    assert r["ok"], r
    return json.dumps(r["ui"], ensure_ascii=False)


def calls(s, op):
    return [c for c in s["calls"]() if c["op"] == op]


def last(s, op):
    found = calls(s, op)
    assert found, "no " + op + " call"
    return found[-1]["args"]


def answer(s, args, value):
    return s["event"]({"type": "result", "token": args["async"], "value": value})


def store(s):
    """What the plugin saved, each value read back from its JSON."""
    return {k: json.loads(v) for k, v in s["storage"]().items()}


def reply(text, status=200, url=""):
    return {"status": status, "text": text, "url": url, "headers": {}}


def click(s, id):
    return s["event"]({"type": "click", "id": id})


def change(s, id, value):
    return s["event"]({"type": "change", "id": id, "value": value})


def ids(node, out):
    if isinstance(node, dict):
        if node.get("id"):
            out.append(node["id"])
        for v in node.values():
            ids(v, out)
    elif isinstance(node, list):
        for v in node:
            ids(v, out)
    return out


def scan_nutella(s):
    click(s, "scan")
    answer(s, last(s, "scan.qr"), "3017620422003")
    req = last(s, "http.request")
    return answer(s, req, reply(NUTELLA, url=OFF + "/api/v3.4/product/3017620422003"))


# A scanned barcode is looked up on Open Food Facts, asking it to send other
# kinds of product on to their own database.
s = session()
click(s, "scan")
answer(s, last(s, "scan.qr"), "3017620422003")
req = last(s, "http.request")
assert req["method"] == "GET", req
assert req["url"] == OFF + "/api/v3.4/product/3017620422003", req["url"]
assert req["params"]["product_type"] == "all", req["params"]
assert "environmental_score_grade" in req["params"]["fields"], req["params"]
assert "allergens_tags_en" in req["params"]["fields"], req["params"]
r = answer(s, req, reply(NUTELLA, url=req["url"]))
page = text_of(r)
assert r["host"]["canBack"], r["host"]
for want in ["Nutella", "Ferrero, Nutella · 400 g", "Nutri-Score", '"value": "E"', "Processed",
             "Green-Score", '"value": "F"', "Maybe", "Contains it", "Contains: Milk, Nuts, Soybeans",
             "Vegetarian", "Gluten-free", "Triman", "Saturated fat", "Open Food Facts · 3017620422003",
             "under the Open Database Licence"]:
    assert want in page, want + " not in " + page

# The summary to insert, in a chat-sized form.
assert "Nutella (Ferrero, Nutella, 400 g e)\\nNutri-Score E · NOVA 3 · Green-Score F\\nVegetarian · Contains palm oil\\nAllergens: Milk, Nuts, Soybeans\\nhttps://world.openfoodfacts.org/product/3017620422003" in page, page

# The front photo is fetched as bytes for the panel.
img = last(s, "http.request")
assert img["url"].startswith("https://images.openfoodfacts.org/") and img["binary"], img

# The product is remembered, with a copy to open offline.
stored = store(s)
assert stored["history"][0]["code"] == "3017620422003", stored
assert stored["history"][0]["nutriscore"] == "e", stored
assert stored["p:3017620422003"]["name"] == "Nutella", stored

# Back home, the history lists it, and a tap opens the saved copy without a request.
s["event"]({"type": "back"})
home = s["render"]()
assert "Recent" in text_of(home), text_of(home)
before = len(calls(s, "http.request"))
row = [i for i in ids(home["ui"], []) if i.startswith("item:Nutella")]
assert row, ids(home["ui"], [])
r = click(s, row[0])
assert "Contains: Milk, Nuts, Soybeans" in text_of(r)
assert len(calls(s, "http.request")) == before + 1  # only the photo
assert last(s, "http.request")["binary"]

# A barcode that is not food: Open Food Facts sends it on to Open Beauty Facts.
s = session()
change(s, "query", "3600523614417")
click(s, "look_up")
req = last(s, "http.request")
r = answer(s, req, reply(BEAUTY, url=OBF + "/api/v3.4/product/3600523614417"))
page = text_of(r)
assert "L'Oreal Infallible" in page or "Infallible" in page, page
assert "Open Beauty Facts · 3600523614417" in page, page
assert "Nutri-Score" not in page, page
assert "E171 - Titanium dioxide" in page, page

# Not in any database: food, then beauty, pet food and products, then an offer to add it.
s = session()
change(s, "query", "0000000000017")
s["event"]({"type": "submit", "id": "query", "value": "0000000000017"})
urls = []
for host in ["openfoodfacts", "openbeautyfacts", "openpetfoodfacts", "openproductsfacts"]:
    req = last(s, "http.request")
    assert ("world." + host + ".org/api/v3.4/product/0000000000017") in req["url"], req["url"]
    urls.append(req["url"])
    r = answer(s, req, reply(NOT_FOUND, status=404, url=req["url"]))
assert "product_type" not in calls(s, "http.request")[1]["args"]["params"]
page = text_of(r)
assert "0000000000017 is not in Open Food Facts and its sister databases yet." in page, page
assert "Add this product" in page

# With "Look beyond food" off, only Open Food Facts is asked.
s = session(settings={"everywhere": False})
s["event"]({"type": "submit", "id": "query", "value": "0000000000017"})
req = last(s, "http.request")
assert "product_type" not in req["params"], req
r = answer(s, req, reply(NOT_FOUND, status=404, url=req["url"]))
assert len(calls(s, "http.request")) == 1
assert "is not in Open Food Facts yet." in text_of(r)

# A busy server says so instead of "not found".
s = session()
s["event"]({"type": "submit", "id": "query", "value": "3017620422003"})
r = answer(s, last(s, "http.request"), reply("<html>busy</html>", status=503, url=OFF + "/api/v3.4/product/3017620422003"))
assert "Open Food Facts is busy. Try again in a minute." in text_of(r), text_of(r)
assert len(calls(s, "http.request")) == 1

# A failed connection is explained.
s = session()
s["event"]({"type": "submit", "id": "query", "value": "3017620422003"})
r = answer(s, last(s, "http.request"), {"error": {"kind": "ConnectionError", "message": "Data saver is on"}})
assert "Could not reach Open Food Facts: Data saver is on" in text_of(r), text_of(r)

# A QR code holding a product page's address works like its barcode; other text does not.
s = session()
click(s, "scan")
answer(s, last(s, "scan.qr"), "https://world.openfoodfacts.org/product/3017620422003/nutella-ferrero")
assert last(s, "http.request")["url"].endswith("/product/3017620422003")
s = session()
click(s, "scan")
r = answer(s, last(s, "scan.qr"), "WIFI:S:home;T:WPA;P:x;;")
assert "That code is not a product barcode" in text_of(r)
assert not calls(s, "http.request")
r = click(s, "scan")
r = answer(s, last(s, "scan.qr"), None)
assert r["ok"] and not calls(s, "http.request")

# A name searches; a result opens the product.
s = session()
s["event"]({"type": "submit", "id": "query", "value": "nutella"})
req = last(s, "http.request")
assert req["url"] == "https://search.openfoodfacts.org/search", req
assert req["params"]["q"] == "nutella" and req["params"]["langs"] == "en", req
r = answer(s, req, reply(SEARCH))
page = text_of(r)
assert "Nutella & go! hazelnut spread + breadsticks" in page and "Nutri-Score E" in page, page
row = [i for i in ids(r["ui"], []) if i.startswith("item:Nutella & go")]
click(s, row[0])
assert last(s, "http.request")["url"].endswith("/product/0009800800049"), last(s, "http.request")

# The @food chip looks up what follows it.
s = session()
s["event"]({"type": "keyword", "id": "food", "value": "3017620422003"})
assert last(s, "http.request")["url"].endswith("/product/3017620422003")

# Signing in checks the password with Open Food Facts before keeping it.
s = session()
r = s["event"]({"type": "command", "id": "account"})
page = text_of(r)
assert "Sign in with your Open Food Facts account" in page, page
change(s, "login_user", "alice@example.com")
change(s, "login_password", "s3cret")
r = click(s, "sign_in")
assert "Use your user name, not your email address." in text_of(r)
change(s, "login_user", "alice")
click(s, "sign_in")
req = last(s, "http.request")
assert req["method"] == "POST" and req["url"] == OFF + "/cgi/auth.pl", req
assert req["form"] == {"user_id": "alice", "password": "s3cret", "body": "1"}, req
r = answer(s, req, reply(json.dumps({"status": 0, "status_verbose": "user not signed-in"}), status=403))
assert "That user name and password did not work." in text_of(r)
assert not calls(s, "secrets.set")
click(s, "sign_in")
r = answer(s, last(s, "http.request"), reply(json.dumps({"status": 1, "user_id": "alice"})))
saved = last(s, "secrets.set")
assert saved["name"] == "account" and json.loads(saved["value"]) == {"user": "alice", "password": "s3cret"}, saved
assert not r["host"]["canBack"], r["host"]

# Editing needs an account; signed out, the form says so and Save is off.
s = session()
scan_nutella(s)
r = click(s, "edit")
page = text_of(r)
assert "Sign in first" in page, page
assert '"id": "save"' in page and '"enabled": false' in page

# Signed in: read the ingredients with the camera, check them, save.
s = session(signed_in=True)
scan_nutella(s)
r = click(s, "edit")
assert "Sign in first" not in text_of(r)
click(s, "ocr")
r = answer(s, last(s, "scan.text"), "Ingredients: sugar, palm\noil,  hazelnuts 13%")
assert ["ingredients_text", "sugar, palm oil, hazelnuts 13%"] in r["inputs"], r["inputs"]
change(s, "quantity", "750 g")
click(s, "save")
req = last(s, "http.request")
assert req["url"] == OFF + "/cgi/product_jqm2.pl", req
form = req["form"]
assert form["code"] == "3017620422003" and form["user_id"] == "alice" and form["password"] == "s3cret", form
assert form["ingredients_text_en"] == "sugar, palm oil, hazelnuts 13%" and form["quantity"] == "750 g", form
assert "product_name_en" not in form and "brands" not in form and "lang" not in form, form
assert form["lc"] == "en" and form["app_name"] == "WM Keyboard" and len(form["app_uuid"]) == 32, form
assert "Authorization" not in (req.get("headers") or {}), req
r = answer(s, req, reply(json.dumps({"status": 1, "status_verbose": "fields saved"})))
assert "Saved. Thank you" in text_of(r), text_of(r)
assert last(s, "http.request")["url"].endswith("/api/v3.4/product/3017620422003")  # fresh copy
r = click(s, "save")
assert len(calls(s, "ui.toast")) == 1  # "Nothing has changed."

# A photo from the keyboard's camera goes up as a multipart form, then is selected.
s = session(signed_in=True)
scan_nutella(s)
click(s, "edit")
click(s, "camera_front")
req = last(s, "files.photo")
answer(s, req, {"name": "IMG_1.jpg", "mime": "image/jpeg", "data": "/9j/AAE="})
req = last(s, "http.request")
assert req["url"] == OFF + "/cgi/product_image_upload.pl", req
kind = req["headers"]["Content-Type"]
assert kind.startswith("multipart/form-data; boundary="), req["headers"]
assert "bodyBytes" in req and "form" not in req, req
r = answer(s, req, reply(json.dumps({"status": "status ok", "imgid": 7, "imagefield": "front_en"})))
assert "Front · sending…" in text_of(r), text_of(r)
req = last(s, "http.request")
assert req["url"] == OFF + "/cgi/product_image_crop.pl", req
assert req["form"]["imgid"] == "7" and req["form"]["id"] == "front_en" and req["form"]["code"] == "3017620422003", req
r = answer(s, req, reply("{}"))
assert "Front · sent" in text_of(r), text_of(r)

# A refused upload says why, and the photo is marked as not sent.
click(s, "pick_nutrition")
answer(s, last(s, "files.pick"), {"name": "n.png", "mime": "image/png", "data": "iVBORw=="})
r = answer(s, last(s, "http.request"), reply(json.dumps({"status": "status not ok", "error": "This picture has already been sent."})))
assert "Nutrition facts · not sent" in text_of(r) and "already been sent" in text_of(r), text_of(r)

# A missing product: added from the not-found page into the chosen database.
s = session(signed_in=True)
s["event"]({"type": "submit", "id": "query", "value": "2000000000017"})
for i in range(4):
    req = last(s, "http.request")
    answer(s, req, reply(NOT_FOUND, status=404, url=req["url"]))
click(s, "add")
change(s, "db", "beauty")
change(s, "lc", "fr")
change(s, "name", "Crème de jour")
click(s, "save")
req = last(s, "http.request")
assert req["url"] == OBF + "/cgi/product_jqm2.pl", req
assert req["form"]["product_name_fr"] == "Crème de jour" and req["form"]["lang"] == "fr", req["form"]

# The test server: edits go to world.openfoodfacts.net with its site password.
s = session(signed_in=True, settings={"test_server": True})
scan_nutella(s)
click(s, "edit")
change(s, "brands", "Ferrero")
click(s, "save")
req = last(s, "http.request")
assert req["url"] == "https://world.openfoodfacts.net/cgi/product_jqm2.pl", req
assert req["headers"]["Authorization"] == "Basic b2ZmOm9mZg==", req
r = answer(s, req, reply(json.dumps({"status": 1})))
assert "Saved on the test server." in text_of(r)
assert last(s, "http.request")["url"].endswith("product_jqm2.pl")  # no re-read from the real database

# With two products remembered, each row opens its own.
s = session()
scan_nutella(s)
s["event"]({"type": "back"})
change(s, "query", "3600523614417")
click(s, "look_up")
req = last(s, "http.request")
answer(s, req, reply(BEAUTY, url=OBF + "/api/v3.4/product/3600523614417"))
s["event"]({"type": "back"})
home = s["render"]()
rows = [i for i in ids(home["ui"], []) if i.startswith("item:")]
assert len(rows) == 2 and "Infallible" in rows[0], rows
assert "Contains: Milk, Nuts, Soybeans" in text_of(click(s, rows[1]))
s["event"]({"type": "back"})
assert "Open Beauty Facts · 3600523614417" in text_of(click(s, rows[0]))

# Removing a row from the history forgets its copy too.
s = session()
scan_nutella(s)
s["event"]({"type": "back"})
home = s["render"]()
row = [i for i in ids(home["ui"], []) if i.startswith("item:Nutella")][0]
s["event"]({"type": "item_action", "id": row, "value": "Remove"})
stored = store(s)
assert stored["history"] == [] and "p:3017620422003" not in stored, stored

print("open-food-facts: all tests passed")
