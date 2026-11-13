# Tests for the Grocy plugin, run by tools/test_plugins.py under
# wm-python-cli. A pretend Grocy 4.7 server answers every address with
# routed mocks; settle() delivers each answer the way the keyboard would.

import json
import time

import plugin_test

J = json.dumps
BASE = "https://grocy.example.com/api"
DAY = 86400
TODAY = time.format("yyyy-MM-dd", time.time())
IN_2 = time.format("yyyy-MM-dd", time.time() + 2 * DAY)
YESTERDAY = time.format("yyyy-MM-dd", time.time() - DAY)
SETTINGS = {"server": "grocy.example.com", "ai_receipts": True, "due_soon_days": 5}

fails = []


def expect(what, got, want):
    if got != want:
        fails.append(what + ": expected " + repr(want) + ", got " + repr(got))


def check(what, cond, detail=""):
    if not cond:
        fails.append(what + (": " + str(detail)[:400] if detail else ""))


def answer(body, status=200):
    return {"status": status, "reason": "OK" if status < 400 else "Bad Request", "url": "",
            "text": "" if body is None else J(body), "headers": {"content-type": "application/json"}}


def route(method, path, body, status=200):
    return {"when": {"method": method, "url": BASE + path}, "reply": answer(body, status)}


PRODUCTS = [
    {"id": 1, "name": "Milk", "location_id": 1, "qu_id_stock": 1, "qu_id_purchase": 1, "min_stock_amount": 2,
     "quick_consume_amount": 1, "quick_open_amount": 1, "default_best_before_days": 7, "active": 1,
     "userfields": None},
    {"id": 2, "name": "Bananas", "location_id": 2, "qu_id_stock": 2, "qu_id_purchase": 2,
     "quick_consume_amount": 2, "default_best_before_days": 0, "active": 1},
    {"id": 3, "name": "Eggs", "location_id": 1, "qu_id_stock": 2, "qu_id_purchase": 2,
     "default_best_before_days": -1, "active": 1, "disable_open": 1},
    {"id": 4, "name": "Natural yogurt", "location_id": 1, "qu_id_stock": 1, "qu_id_purchase": 1, "active": 1},
    {"id": 5, "name": "Tomatoes", "location_id": 2, "qu_id_stock": 2, "qu_id_purchase": 2, "active": 1},
]
UNITS = [{"id": 1, "name": "Pack", "name_plural": "Packs"}, {"id": 2, "name": "Piece", "name_plural": "Pieces"}]
LOCATIONS = [{"id": 1, "name": "Fridge"}, {"id": 2, "name": "Pantry"}]
LISTS = [{"id": 1, "name": "Shopping list"}, {"id": 2, "name": "Party"}]
ITEMS = [
    {"id": 10, "shopping_list_id": 1, "product_id": 1, "note": None, "amount": 2, "qu_id": 1, "done": 0},
    {"id": 11, "shopping_list_id": 1, "product_id": None, "note": "Birthday candles", "amount": 1, "done": 0},
    {"id": 12, "shopping_list_id": 1, "product_id": 2, "note": "", "amount": 6, "qu_id": 2, "done": 1},
    {"id": 13, "shopping_list_id": 2, "product_id": 3, "note": "", "amount": 12, "qu_id": 2, "done": 0},
    {"id": 14, "shopping_list_id": 1, "product_id": 5, "note": "", "amount": 4, "qu_id": 2, "done": 0},
]
STOCK = [
    {"product_id": 1, "amount": 1, "amount_aggregated": 1, "amount_opened": 1, "best_before_date": IN_2,
     "is_aggregated_amount": 0, "product": PRODUCTS[0]},
    {"product_id": 3, "amount": 10, "amount_aggregated": 10, "amount_opened": 0, "best_before_date": "2999-12-31",
     "is_aggregated_amount": 0, "product": PRODUCTS[2]},
]
VOLATILE = {
    "due_products": [STOCK[0]], "overdue_products": [], "expired_products": [],
    "missing_products": [{"id": 2, "name": "Bananas", "amount_missing": 4, "is_partly_in_stock": 0, "product": PRODUCTS[1]}],
}
CHORES = [
    {"id": 1, "chore_id": 7, "chore_name": "Bins", "next_estimated_execution_time": TODAY + " 23:59:59",
     "next_execution_assigned_user": None},
    {"id": 2, "chore_id": 5, "chore_name": "Vacuum", "next_estimated_execution_time": YESTERDAY + " 10:00:00",
     "next_execution_assigned_user": {"id": 1, "display_name": "Sam"}},
    {"id": 3, "chore_id": 6, "chore_name": "Water plants", "next_estimated_execution_time": None,
     "next_execution_assigned_user": None},
]
MILK_DETAIL = {
    "product": PRODUCTS[0], "product_barcodes": [{"product_id": 1, "barcode": "4011111", "amount": 2}],
    "stock_amount": 1, "stock_amount_opened": 1, "next_due_date": IN_2, "last_price": 1.19,
    "quantity_unit_stock": UNITS[0],
}
BOOKED = [{"id": 99, "product_id": 1, "amount": 1, "transaction_id": "tx-1", "transaction_type": "purchase"}]


def server(version="4.7.1", extra=None):
    routes = list(extra or [])
    routes += [
        route("GET", "/system/info", {"grocy_version": {"Version": version, "ReleaseDate": "2026-09-04"}}),
        route("GET", "/objects/products", PRODUCTS),
        route("GET", "/objects/quantity_units", UNITS),
        route("GET", "/objects/locations", LOCATIONS),
        route("GET", "/objects/shopping_lists", LISTS),
        route("GET", "/objects/shopping_list", ITEMS),
        route("GET", "/stock", STOCK),
        route("GET", "/stock/volatile", VOLATILE),
        route("GET", "/chores", CHORES),
        route("GET", "/stock/products/1", MILK_DETAIL),
        route("GET", "/stock/products/by-barcode/4011111", MILK_DETAIL),
        route("GET", "/stock/products/by-barcode/999", {"error_message": "No product with barcode 999 found"}, 400),
        route("GET", "/stock/barcodes/external-lookup/999", {"name": "Choco spread", "location_id": 2, "qu_id_stock": 1}),
        route("POST", "/stock/products/*", BOOKED),
        route("POST", "/stock/transactions/*", None, 204),
        route("PUT", "/objects/shopping_list/*", None, 204),
        route("DELETE", "/objects/shopping_list/*", None, 204),
        route("POST", "/objects/shopping_list", {"created_object_id": 20}),
        route("POST", "/stock/shoppinglist/*", None, 204),
        route("POST", "/objects/product_barcodes", {"created_object_id": 30}),
        route("POST", "/objects/products", {"created_object_id": 6}),
        route("POST", "/chores/executions/*", None, 204),
        route("POST", "/chores/*", {"id": 77, "chore_id": 5, "skipped": 0}),
    ]
    return routes


def session(routes=None, settings=None, extra=None, key="test-key"):
    mock = {"http.request": routes or server(), "secrets.get": key, "ui.toast": None}
    if extra:
        for k, v in extra.items():
            mock[k] = v
    return plugin_test.session(mock=mock, settings=settings or SETTINGS)


def widgets(node, out=None):
    """Every widget dict in a drawn tree, depth first."""
    if out is None:
        out = []
    if isinstance(node, list):
        for x in node:
            widgets(x, out)
    elif isinstance(node, dict):
        if "type" in node:
            out.append(node)
        for k in ("root", "children", "pages", "items"):
            if k in node:
                widgets(node[k], out)
    return out


def find(r, **fields):
    for w in widgets(r.get("ui") or {}):
        if all(w.get(k) == v for k, v in fields.items()):
            return w
    return None


def text_of(r):
    return J(r.get("ui"))


def requests(s, method=None, path=None):
    out = []
    for c in s["calls"]():
        if c["op"] != "http.request":
            continue
        a = c["args"]
        if method and a["method"] != method:
            continue
        if path and a["url"] != BASE + path:
            continue
        out.append(a)
    return out


def body(a):
    return json.loads(a["body"]) if a.get("body") else None


def opened(s):
    r = s["load"]()
    check("loads", r["ok"], r.get("error"))
    r = s["settle"]()
    check("first draw after loading", r["ok"], r.get("error"))
    return r


# ------------------------------------------------------------- setup ----

s = plugin_test.session(mock={"secrets.get": None, "plugin.open_settings": None},
                        settings={"server": "", "ai_receipts": True, "due_soon_days": 5})
r = s["load"]()
check("setup draws", r["ok"], r.get("error"))
check("setup asks for the server", "Grocy server" in text_of(r), text_of(r))
check("setup asks for the key", "API key" in text_of(r), text_of(r))
s["event"]({"type": "click", "id": "button:Open settings"})
expect("opens the settings page", [c["op"] for c in s["calls"]()][-1:], ["plugin.open_settings"])
expect("setup sends nothing", len(requests(s)), 0)

s = session(key=None, settings=SETTINGS)
r = s["load"]()
check("server set, no key: asks for it", "Manage API keys" in text_of(r) and find(r, id="button:Open settings") is not None, text_of(r))
check("server is shown", "https://grocy.example.com" in text_of(r))

# A key typed on the settings page later: read again, and the panel loads.
s = session(key=None)
s["load"]()
keyed = session()
keyed["load"]()
keyed["settle"]()
before = len(requests(keyed, "GET", "/system/info"))
keyed["event"]({"type": "setting", "key": "api_key", "value": "new"})
expect("a new key loads again", len(requests(keyed, "GET", "/system/info")), before + 1)
keyed["settle"]()

# ------------------------------------------------------- the server ----

s = session()
r = opened(s)
first = requests(s)[0]
expect("first call is the version", first["url"], BASE + "/system/info")
expect("key header", first["headers"]["GROCY-API-KEY"], "test-key")
expect("asks for JSON", first["headers"]["Accept"], "application/json")
products_call = requests(s, "GET", "/objects/products")[0]
expect("only active products, in pages", products_call["params"],
       {"query[]": "active=1", "order": "name", "limit": "200", "offset": "0"})
expect("due soon days from the setting", requests(s, "GET", "/stock/volatile")[0]["params"], {"due_soon_days": "5"})
check("product cache saved", "Milk" in J(s["storage"]()), s["storage"]())

for raw, want in [("http://192.168.1.20:9283/grocy/", "http://192.168.1.20:9283/grocy/api/system/info"),
                  ("https://grocy.example.com/api", "https://grocy.example.com/api/system/info"),
                  ("nas.local:9283", "https://nas.local:9283/api/system/info")]:
    t = plugin_test.session(mock={"secrets.get": "k", "http.request": [{"reply": answer({"grocy_version": {"Version": "4.0.0"}})}]},
                            settings={"server": raw, "ai_receipts": False, "due_soon_days": 5})
    t["load"]()
    sent = [c["args"]["url"] for c in t["calls"]() if c["op"] == "http.request"]
    expect("address " + raw, sent[:1], [want])

# A big household: products come in pages and are cached in chunks.
MANY = [{"id": n, "name": "Thing %03d" % n, "location_id": 1, "qu_id_stock": 1, "qu_id_purchase": 1, "active": 1}
        for n in range(1, 204)]
big = server()
big.insert(0, {"when": {"url": BASE + "/objects/products", "params": {"offset": "0"}}, "reply": answer(MANY[:200])})
big.insert(1, {"when": {"url": BASE + "/objects/products", "params": {"offset": "200"}}, "reply": answer(MANY[200:])})
t = session(routes=big)
opened(t)
expect("two pages asked for", len(requests(t, "GET", "/objects/products")), 2)
kept = t["storage"]()
expect("cached in two chunks", json.loads(kept["cache"])["chunks"], 2)
expect("chunk sizes", [len(json.loads(kept["cache_p0"])), len(json.loads(kept["cache_p1"]))], [150, 53])
t["event"]({"type": "change", "id": "add", "value": "thing 203"})
check("a product from the second page", "Thing 203" in text_of(t["render"]()))

# ---------------------------------------------------------- shopping ----

shopping = find(r, id="shopping")
titles = [i["title"] for i in shopping["items"]]
expect("this list's rows, open ones first", titles, ["Milk", "Birthday candles", "Tomatoes", "Bananas"])
expect("amount with unit", shopping["items"][0]["subtitle"], "2 Packs")
expect("done row is ticked", shopping["items"][3]["icon"], "check_box")
check("list picker with two lists", find(r, type="select") is not None)

r = s["event"]({"type": "click", "id": "shop-10"})
put = requests(s, "PUT")
expect("tick sends done", (put[-1]["url"], body(put[-1])), (BASE + "/objects/shopping_list/10", {"done": 1}))
s["settle"]()
expect("ticked row moves down", find(s["render"](), id="shopping")["items"][2]["title"], "Milk")

r = s["event"]({"type": "change", "id": "add", "value": "yog"})
check("typing suggests a product", "Natural yogurt" in text_of(r), text_of(r))
r = s["event"]({"type": "click", "id": "suggest-4"})
add = requests(s, "POST", "/stock/shoppinglist/add-product")
expect("adds the product", body(add[-1]), {"product_id": 4, "list_id": 1, "product_amount": 1})
s["settle"]()

s["event"]({"type": "submit", "id": "add", "value": "Napkins"})
note = requests(s, "POST", "/objects/shopping_list")
expect("free text becomes a note", body(note[-1]), {"shopping_list_id": 1, "note": "Napkins", "amount": 1})
s["settle"]()

s["event"]({"type": "item_action", "id": "shop-14", "value": "Bought it"})
s["settle"]()
buy = requests(s, "POST", "/stock/products/5/add")
expect("bought it books a purchase", body(buy[-1]), {"amount": 4, "transaction_type": "purchase"})
expect("and ticks the row", body(requests(s, "PUT")[-1]), {"done": 1})

s["event"]({"type": "click", "id": "button:Add missing"})
expect("add missing", body(requests(s, "POST", "/stock/shoppinglist/add-missing-products")[-1]), {"list_id": 1})
s["settle"]()
s["event"]({"type": "click", "id": "button:Clear done"})
expect("clear done", body(requests(s, "POST", "/stock/shoppinglist/clear")[-1]), {"list_id": 1, "done_only": True})
s["settle"]()

r = s["event"]({"type": "change", "id": "list_pick", "value": "2"})
check("the other list", "Eggs" in J(find(r, id="shopping")), find(r, id="shopping"))
s["event"]({"type": "change", "id": "list_pick", "value": "1"})

# ------------------------------------------------------------- stock ----

r = s["render"]()
stock = find(r, id="stock")
expect("stock rows", [i["title"] for i in stock["items"]], ["Eggs", "Milk"])
milk = stock["items"][1]
expect("milk trailing", milk["trailing"], "1 Pack")
expect("milk subtitle", milk["subtitle"], "1 opened · due in 2 days")
expect("eggs never go off", stock["items"][0]["subtitle"], "")
chips = find(r, id="filter")
expect("filter counts", [o["label"] for o in chips["options"]], ["All", "Low 1", "Due soon 1", "Overdue", "Expired"])

r = s["event"]({"type": "change", "id": "filter", "value": "missing"})
low = find(r, id="low")
expect("low row", (low["items"][0]["title"], low["items"][0]["trailing"]), ("Bananas", "need 4 Pieces"))
s["event"]({"type": "item_action", "id": "low-2", "value": "Add to the list"})
expect("low to list", body(requests(s, "POST", "/stock/shoppinglist/add-product")[-1]),
       {"product_id": 2, "list_id": 1, "product_amount": 4})
s["settle"]()
r = s["event"]({"type": "change", "id": "filter", "value": "due"})
expect("due soon", [i["title"] for i in find(r, id="stock")["items"]], ["Milk"])
s["event"]({"type": "change", "id": "filter", "value": "all"})

# ------------------------------------------------------ product page ----

r = s["event"]({"type": "click", "id": "stock-1"})
r = s["settle"]()
check("product page", r["host"]["canBack"] and r["host"]["title"] == "Milk", r["host"])
stat = find(r, type="stat")
check("in stock", stat is not None and stat["value"] == "1 Pack", stat)
check("stat caption", stat is not None and stat["caption"] == "1 opened · due in 2 days · Fridge", stat)
expect("price from the last purchase", find(r, id="price")["kind"], "number")

s["event"]({"type": "change", "id": "amount", "value": 2})
s["event"]({"type": "click", "id": "button:Use"})
use = requests(s, "POST", "/stock/products/1/consume")
expect("consume body", body(use[-1]), {"amount": 2, "spoiled": False, "allow_subproduct_substitution": True})
r = s["settle"]()
check("undo offered", find(r, id="button:Undo") is not None, text_of(r))
s["event"]({"type": "click", "id": "button:Undo"})
expect("undo the booking", requests(s, "POST")[-1]["url"], BASE + "/stock/transactions/tx-1/undo")
s["settle"]()

s["event"]({"type": "click", "id": "button:Open"})
expect("open uses quick open amount", body(requests(s, "POST", "/stock/products/1/open")[-1]),
       {"amount": 1, "allow_subproduct_substitution": True})
s["settle"]()

s["event"]({"type": "change", "id": "price", "value": "1.25"})
s["event"]({"type": "click", "id": "button:Buy"})
bought = body(requests(s, "POST", "/stock/products/1/add")[-1])
expect("buy amount", bought["amount"], 2)
expect("buy price", bought["price"], 1.25)
check("buy best before is today + 7", bought.get("best_before_date") == time.format("yyyy-MM-dd", time.time() + 7 * DAY), bought)
s["settle"]()
s["event"]({"type": "back"})

# ------------------------------------------------------------ chores ----

r = s["render"]()
chores = find(r, id="chores")
expect("overdue first, whenever last", [i["title"] for i in chores["items"]], ["Vacuum", "Bins", "Water plants"])
expect("overdue words", chores["items"][0]["subtitle"], "1 day overdue · Sam")
expect("whenever", chores["items"][2]["subtitle"], "whenever")
s["event"]({"type": "click", "id": "chore-5"})
expect("track", requests(s, "POST")[-1]["url"], BASE + "/chores/5/execute")
r = s["settle"]()
check("chore undo", "Done: Vacuum" in text_of(r), text_of(r))
s["event"]({"type": "click", "id": "button:Undo"})
expect("undo chore", requests(s, "POST")[-1]["url"], BASE + "/chores/executions/77/undo")
s["settle"]()
s["event"]({"type": "item_action", "id": "chore-7", "value": "Skip"})
expect("skip", body(requests(s, "POST", "/chores/7/execute")[-1]), {"skipped": True})
s["settle"]()

# ----------------------------------------------------------- barcodes ----

s = session(extra={"scan.qr": "4011111"})
opened(s)
s["event"]({"type": "command", "id": "command_scan"})
r = s["settle"]()
check("known code opens the product", r["host"]["title"] == "Milk", r["host"])
expect("barcode amount", find(r, id="amount")["value"], 2)
expect("looked up by barcode", len(requests(s, "GET", "/stock/products/by-barcode/4011111")), 1)

s = session(extra={"scan.qr": "999"})
opened(s)
s["event"]({"type": "command", "id": "command_scan"})
r = s["settle"]()
check("unknown code page", r["host"]["title"] == "New barcode", r)
check("lookup suggestion", "Choco spread" in text_of(r), text_of(r))
expect("lookup without adding", requests(s, "GET", "/stock/barcodes/external-lookup/999")[0]["params"], {"add": "false"})
s["event"]({"type": "change", "id": "link", "value": "milk"})
s["event"]({"type": "click", "id": "link-1"})
expect("link barcode", body(requests(s, "POST", "/objects/product_barcodes")[-1]), {"product_id": 1, "barcode": "999"})
r = s["settle"]()
check("then the product page", r["host"]["title"] == "Milk", r["host"])

s = session(extra={"scan.qr": "999"})
opened(s)
s["event"]({"type": "command", "id": "command_scan"})
r = s["settle"]()
expect("name prefilled", find(r, id="new_name") is not None, True)
s["event"]({"type": "click", "id": "button:Create and link"})
made = body(requests(s, "POST", "/objects/products")[-1])
expect("create body (4.x)", made, {"name": "Choco spread", "location_id": 2, "qu_id_purchase": 1, "qu_id_stock": 1})
r = s["settle"]()
expect("new product linked", body(requests(s, "POST", "/objects/product_barcodes")[-1]), {"product_id": 6, "barcode": "999"})
check("new product page", r["host"]["title"] == "Choco spread", r["host"])

old = session(routes=server(version="3.3.2"), extra={"scan.qr": "999"})
opened(old)
old["event"]({"type": "command", "id": "command_scan"})
old["settle"]()
old["event"]({"type": "click", "id": "button:Create and link"})
check("Grocy 3 gets the factor", body(requests(old, "POST", "/objects/products")[-1]).get("qu_factor_purchase_to_stock") == 1)
old["settle"]()

s = session(extra={"scan.qr": None})
opened(s)
s["event"]({"type": "command", "id": "command_scan"})
r = s["settle"]()
check("closing the scanner does nothing", not r["host"]["canBack"] and not r.get("error"), r)

# ----------------------------------------------------------- receipts ----

RECEIPT = "\n".join([
    "SUPERMARKT",
    "MILCH 3,5% 1L     1,19 A",
    "TOMATEN           3,00 A",
    "  2 x 1,50",
    "NAT JOGHURT       0,89 A",
    "SCHOKOLADE        1,99 A",
    "SUMME          EUR 7,07",
    "Geg. EC-Karte  EUR 7,07",
])
AI_REPLY = J([{"line": 0, "product": 1, "amount": 1}, {"line": 2, "product": 4, "amount": 1},
              {"line": 3, "product": 999, "amount": 1}])

s = session(extra={"scan.text": RECEIPT, "ai.available": True, "ai.ask": {"text": AI_REPLY}})
opened(s)
s["event"]({"type": "command", "id": "command_receipt"})
r = s["settle"]()
check("receipt page", r["host"]["title"] == "Receipt", r["host"])
lines = find(r, type="list")["items"]
expect("receipt lines", [i["title"] for i in lines], ["Milk", "Tomatoes", "Natural yogurt", "Not matched: SCHOKOLADE"])
expect("ai marks its match", lines[0]["subtitle"].endswith("matched by AI"), True)
expect("tomatoes counted", lines[1]["trailing"], "×2 · 3")
asked = [c for c in s["calls"]() if c["op"] == "ai.ask"]
check("ai saw the products", len(asked) == 1 and "4: Natural yogurt" in asked[0]["args"]["prompt"], asked)
check("unmatched line is off", lines[3]["icon"] == "check_box_outline_blank", lines[3])

s["event"]({"type": "click", "id": "line-3"})
r = s["render"]()
check("line page", r["host"]["title"] == "Receipt line", r["host"])
s["event"]({"type": "change", "id": "line_find", "value": "egg"})
s["event"]({"type": "click", "id": "pick-3"})
r = s["render"]()
expect("picked by hand", find(r, type="list")["items"][3]["title"], "Eggs")

s["event"]({"type": "click", "id": "button:Add 4 to stock"})
r = s["settle"]()
adds = [a for a in requests(s, "POST") if a["url"].endswith("/add")]
expect("four purchases", [a["url"].split("/")[-2] for a in adds], ["1", "5", "4", "3"])
expect("price per unit", body(adds[1]), {"amount": 2, "transaction_type": "purchase", "price": 1.5})
ticks = [a["url"] for a in requests(s, "PUT")]
check("tomatoes ticked off", BASE + "/objects/shopping_list/14" in ticks, ticks)
check("summary", "Added 4 to stock." in text_of(r), text_of(r))
aliases = s["storage"]()
check("hand match remembered", "schokolade" in J(aliases), aliases)

s["event"]({"type": "click", "id": "button:Undo all"})
s["settle"]()
undos = [a["url"] for a in requests(s, "POST") if a["url"].endswith("/undo")]
expect("undo every booking", len(undos), 4)

# The same line on the next receipt: the remembered match wins.
s["event"]({"type": "click", "id": "button:Done"})
s["event"]({"type": "command", "id": "command_receipt"})
r = s["settle"]()
check("remembered match", "Eggs" in J(find(r, type="list")), find(r, type="list"))

# ------------------------------------------------------------ failures ----

s = session(routes=[route("GET", "/system/info", None, 401)])
r = opened(s)
check("bad key message", "refused the API key" in text_of(r), text_of(r))

s = session(routes=[{"when": {"url": BASE + "/system/info"}, "reply": {"status": 200, "text": "<html>login</html>",
                                                                       "headers": {"content-type": "text/html"}}}])
r = opened(s)
check("web page instead of API", "web page" in text_of(r), text_of(r))

s = session(routes=[{"when": {"url": BASE + "/system/info"},
                     "reply": {"error": {"kind": "PermissionError", "message": "the user has not turned on 'network.local' for this plugin"}}}])
r = opened(s)
check("local network not allowed", "Local network" in text_of(r) or "local network" in text_of(r), text_of(r))

s = session(routes=server(version="2.7.1"))
r = opened(s)
check("too old", "Grocy 3.0 or newer" in text_of(r), text_of(r))

if fails:
    for f in fails:
        print("  " + f)
    raise RuntimeError("grocy: " + str(len(fails)) + " checks failed")
print("grocy: all checks passed")
