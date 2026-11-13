import json

R = plugin_test.load("receipt.py", wm, ui)
F = plugin_test.load("firefly.py", wm, ui)


def near(a, b):
    return a is not None and abs(a - b) < 0.001


# ---- receipt.parse ----------------------------------------------------------------

US = """WALMART SUPERCENTER
Store #1234  Tel (555) 123-4567
11/09/2026 14:32
BANANAS          1.29
MILK 2% GAL      3.49
BREAD WHOLE WHEAT 2.99
2 x 1.50 EGGS     3.00
SUBTOTAL        10.77
TAX 6.5%         0.70
TOTAL           11.47
CASH            20.00
CHANGE           8.53
"""
r = R["parse"](US, True)
assert r["merchant"] == "Walmart Supercenter", r
assert near(r["total"], 11.47), r
assert r["date"] == "2026-11-09", r
assert r["currency"] is None, r
names = [i["name"] for i in r["items"]]
assert names == ["BANANAS", "MILK 2% GAL", "BREAD WHOLE WHEAT", "EGGS"], names
assert near(r["items"][3]["amount"], 3.00), r["items"]

DE = """Bäckerei Schmidt
Hauptstr. 5, 10115 Berlin
Datum: 14.11.2026 08:15
Brötchen 4x      2,40
Kaffee groß      3,20
Zwischensumme    5,60
MwSt 7%          0,37
SUMME EUR        5,60
Bar             10,00
Rückgeld         4,40
"""
r = R["parse"](DE)
assert r["merchant"] == "Bäckerei Schmidt", r
assert near(r["total"], 5.60), r
assert r["date"] == "2026-11-14", r
assert r["currency"] == "EUR", r
assert [i["name"] for i in r["items"]] == ["Brötchen 4x", "Kaffee groß"], r["items"]

BD = """Shwapno
Gulshan 2, Dhaka
Date: 03 Nov 2026
Rice 5kg        Tk 650
Lentils         Tk 180.00
Total           Tk 1,250
"""
r = R["parse"](BD)
assert near(r["total"], 1250), r
assert r["currency"] == "BDT", r
assert r["date"] == "2026-11-03", r

JP = """ローソン
2026年11月14日
おにぎり  ¥150
お茶      ¥130
合計      ¥280
"""
r = R["parse"](JP)
assert near(r["total"], 280), r
assert r["currency"] == "JPY", r

GRAND = """Cafe Luna
Nov 2, 2026
Latte 4.50
Tip 1.00
Total 5.50
Grand Total $5.50
"""
r = R["parse"](GRAND, True)
assert near(r["total"], 5.50) and r["date"] == "2026-11-02" and r["currency"] == "USD", r
assert [i["name"] for i in r["items"]] == ["Latte"], r["items"]

NOKEYWORD = """Corner Kiosk
Water 1.20
Crisps 2.30
Card no ****1234 99.99
"""
r = R["parse"](NOKEYWORD)
assert near(r["total"], 2.30), r

r = R["parse"]("")
assert r["merchant"] is None and r["total"] is None and r["items"] == [], r

assert near(R["amount_value"]("1.234,56"), 1234.56)
assert near(R["amount_value"]("1,234.56"), 1234.56)
assert near(R["amount_value"]("1 234,56"), 1234.56)
assert near(R["amount_value"]("1,250"), 1250)

# ---- merge_ai ---------------------------------------------------------------------

base = R["parse"](US, True)
reply = 'Here you go:\n```json\n{"merchant": "Walmart", "total": "11.47", "date": "2026-11-09", "currency": "usd", "items": [{"name": "Bananas", "amount": 1.29}]}\n```'
m = R["merge_ai"](base, reply)
assert m["merchant"] == "Walmart" and m["currency"] == "USD" and near(m["total"], 11.47), m
assert m["items"] == [{"name": "Bananas", "amount": 1.29}], m
assert R["merge_ai"](base, "no idea") == base
bad = R["merge_ai"](base, '{"total": -3, "date": "2026-02-30", "currency": "dollars"}')
assert near(bad["total"], 11.47) and bad["date"] == "2026-11-09" and bad["currency"] is None, bad

# ---- firefly request bodies -------------------------------------------------------

assert F["base_url"]("money.example.com/") == "https://money.example.com"
assert F["base_url"]("http://192.168.1.20:8080/firefly/api/v1/") == "http://192.168.1.20:8080/firefly"
assert F["host_of"]("http://192.168.1.20:8080/firefly") == "192.168.1.20:8080"
assert F["base_url"]("  ") is None

draft = {"description": "Walmart", "amount": 11.47, "date": "2026-11-09T12:00:00+00:00", "source_id": "1",
         "items": [{"name": "Bananas", "amount": 1.29}, {"name": "Milk", "amount": 3.49}], "split": True,
         "category_id": "4", "budget_id": "2", "notes": "n"}
body = F["withdrawal"](draft, True, "receipt")
splits = body["transactions"]
assert [s["description"] for s in splits] == ["Bananas", "Milk", "Tax and other"], splits
assert [s["amount"] for s in splits] == ["1.29", "3.49", "6.69"], splits
assert body["group_title"] == "Walmart" and body["error_if_duplicate_hash"] is True
assert all(s["destination_name"] == "Walmart" and s["source_id"] == "1" and s["tags"] == ["receipt"] for s in splits)
assert splits[0]["notes"] == "n" and "notes" not in splits[1]
assert splits[0]["category_id"] == "4" and splits[0]["budget_id"] == "2"

one = F["withdrawal"]({"description": "", "amount": 4.5, "date": "d", "source_id": "1", "category": "Snacks"}, False, None)
assert len(one["transactions"]) == 1 and "group_title" not in one and one["apply_rules"] is False
t = one["transactions"][0]
assert t["description"] == "Receipt" and t["amount"] == "4.50" and t["category_name"] == "Snacks" and "tags" not in t

fx = F["withdrawal"]({"description": "Hotel", "amount": 100, "date": "d", "source_id": "1",
                      "foreign_currency": "USD", "account_amount": 92.5}, True, None)["transactions"][0]
assert fx["amount"] == "92.50" and fx["foreign_amount"] == "100.00" and fx["foreign_currency_code"] == "USD", fx

assert not F["can_split"]([{"name": "a", "amount": 9}], 5)
group = {"id": "7", "splits": [{"journal": "70"}, {"journal": "71"}]}
upd = F["recategorise"](group, "71", category_id="3")
assert upd["transactions"] == [{"transaction_journal_id": "70"}, {"transaction_journal_id": "71", "category_id": "3"}], upd

summary = F["read_summary"]({"data": {
    "spent-in-EUR": {"key": "spent-in-EUR", "monetary_value": -120.5, "currency_code": "EUR", "value_parsed": "-€120.50"},
    "left-to-spend-in-EUR": {"monetary_value": 79.5, "currency_code": "EUR", "value_parsed": "€79.50"},
    "spent-in-USD": {"monetary_value": -3, "currency_code": "USD", "value_parsed": "-$3.00"},
}})
assert F["pick"](summary["spent"], "USD")["text"] == "-$3.00"
assert F["pick"](summary["left"], "EUR")["text"] == "€79.50"
assert F["read_insight"]({"data": [{"name": "Food", "difference": "-50.5", "difference_float": -50.5},
                                   {"name": "Rent", "difference_float": -700}]}) == [("Rent", 700.0), ("Food", 50.5)]

# ---- the plugin as the keyboard runs it ---------------------------------------------

SERVER = "http://192.168.1.20:8080"
B = SERVER + "/api/v1"
SETTINGS = {"server": SERVER, "ai": False, "keep_text": True, "tag": "receipt", "apply_rules": True}


def ok(data, status=200):
    return {"status": status, "reason": "OK", "text": json.dumps(data), "headers": {}}


GROUPS = {"data": [{"id": "7", "attributes": {"group_title": "Big shop", "transactions": [
    {"transaction_journal_id": "70", "type": "withdrawal", "date": "2026-11-12T10:00:00+00:00", "amount": "10.00",
     "description": "Food", "category_id": "1", "category_name": "Groceries", "source_name": "Checking",
     "destination_name": "Shop", "currency_symbol": "€", "currency_code": "EUR"},
    {"transaction_journal_id": "71", "type": "withdrawal", "date": "2026-11-12T10:00:00+00:00", "amount": "5.00",
     "description": "Soap", "currency_symbol": "€", "currency_code": "EUR"}]}}]}

READS = [
    {"when": {"method": "GET", "url": B + "/about"}, "reply": ok({"data": {"version": "6.1.21"}})},
    {"when": {"method": "GET", "url": B + "/accounts"}, "reply": ok({"data": [
        {"id": "1", "attributes": {"name": "Checking", "current_balance": "1234.50", "currency_code": "EUR",
                                   "currency_symbol": "€", "active": True}},
        {"id": "2", "attributes": {"name": "Old", "current_balance": "0", "currency_code": "EUR", "active": False}}]})},
    {"when": {"method": "GET", "url": B + "/summary/basic"}, "reply": ok({"data": {
        "spent-in-EUR": {"monetary_value": -120.5, "currency_code": "EUR", "value_parsed": "-€120.50"},
        "left-to-spend-in-EUR": {"monetary_value": 79.5, "currency_code": "EUR", "value_parsed": "€79.50"}}})},
    {"when": {"method": "GET", "url": B + "/insight/expense/category"}, "reply": ok([
        {"id": "1", "name": "Groceries", "difference": "-80", "difference_float": -80, "currency_code": "EUR"},
        {"id": "2", "name": "Coffee", "difference": "-40.5", "difference_float": -40.5, "currency_code": "EUR"}])},
    {"when": {"method": "GET", "url": B + "/transactions"}, "reply": ok(GROUPS)},
    {"when": {"method": "GET", "url": B + "/categories"}, "reply": ok({"data": [
        {"id": "1", "attributes": {"name": "Groceries"}}, {"id": "3", "attributes": {"name": "Coffee"}}]})},
    {"when": {"method": "GET", "url": B + "/budgets"}, "reply": ok({"data": [{"id": "2", "attributes": {"name": "Daily"}}]})},
    {"when": {"method": "PUT", "url": B + "/transactions/7"}, "reply": ok({"data": {}})},
    {"when": {"method": "DELETE", "url": B + "/transactions/7"}, "reply": {"status": 204, "text": "", "headers": {}}},
]
STORED = {"when": {"method": "POST", "url": B + "/transactions"}, "reply": ok({"data": {"id": "9"}})}
BASE_MOCK = {"secrets.get": "tok", "secrets.set": None, "secrets.remove": None, "ui.toast": None,
             "ui.dialog": "Delete", "ai.available": True}


def merged(a, b):
    out = dict(a)
    out.update(b)
    return out


# What each text box shows: the panel sends a box's text only when it changes.
SHOWN = {}


def seen(r):
    for wid, value in r.get("inputs") or []:
        SHOWN[wid] = value
    return r


def start(mock, settings=None):
    SHOWN.clear()
    s = plugin_test.session(mock=mock, settings=settings or SETTINGS)
    r = seen(s["load"]())
    assert r["ok"], r
    r = seen(s["settle"]())
    assert r["ok"], r
    return s, r


def session(posts=None, extra=None):
    mock = dict(BASE_MOCK)
    mock["http.request"] = list(posts or [STORED]) + READS
    for k, v in (extra or {}).items():
        mock[k] = v
    return start(mock)


def text(r):
    return json.dumps(r["ui"], ensure_ascii=False)


def find(node, wid):
    """The widget with id [wid] in a drawn tree."""
    if isinstance(node, dict):
        if node.get("id") == wid:
            return node
        for v in node.values():
            got = find(v, wid)
            if got is not None:
                return got
    elif isinstance(node, list):
        for v in node:
            got = find(v, wid)
            if got is not None:
                return got
    return None


def waiting(s):
    """The entries kept for later, from the plugin's saved state."""
    raw = s["storage"]().get("__state__:queue")
    return json.loads(raw)["items"] if raw else []


def posted(s):
    return [c["args"] for c in s["calls"]() if c["op"] == "http.request" and c["args"]["method"] == "POST"]


def ev(s, kind, wid, value=None):
    e = {"type": kind, "id": wid}
    if value is not None:
        e["value"] = value
    r = seen(s["event"](e))
    assert r["ok"], r
    r = seen(s["settle"]())
    assert r["ok"], r
    return r


# Overview: balances, this month, a chart and recent entries.
s, r = session()
t = text(r)
assert "-€120.50" in t and "€79.50" in t, t
assert "€1234.50" in t and "Old" not in t, t
assert "Big shop" in t and "€15.00" in t, t
assert find(r["ui"], "chart")["type"] == "chart", r["ui"]
assert "Firefly III 6.1.21 at 192.168.1.20:8080" in t
gets = [c["args"] for c in s["calls"]() if c["op"] == "http.request"]
assert all(a["headers"]["Authorization"] == "Bearer tok" for a in gets)
assert len([c for c in s["calls"]() if c["op"] == "secrets.get"]) == 1, "the token is read once"

# Recategorise one split of a split transaction: both journals go along.
r = ev(s, "item_action", "tx7", "Change category")
assert r["host"]["canBack"], r["host"]
r = ev(s, "click", "pick3")
put = [c["args"] for c in s["calls"]() if c["op"] == "http.request" and c["args"]["method"] == "PUT"][-1]
assert put["url"] == B + "/transactions/7"
assert json.loads(put["body"])["transactions"] == [{"transaction_journal_id": "70", "category_id": "3"},
                                                    {"transaction_journal_id": "71"}], put["body"]
assert not r["host"]["canBack"]

# Delete asks first, then deletes.
r = ev(s, "item_action", "tx7", "Delete")
assert any(c["args"]["method"] == "DELETE" for c in s["calls"]() if c["op"] == "http.request")

# A scanned receipt: parsed, checked, sent as a withdrawal from the right account.
s, r = session(extra={"scan.text": DE})
r = ev(s, "change", "view", "add")
r = ev(s, "click", "scan")
assert r["host"]["canBack"], r["host"]
assert SHOWN["f_desc"] == "Bäckerei Schmidt" and SHOWN["f_amount"] == "5.60" and SHOWN["f_currency"] == "EUR", SHOWN
r = ev(s, "change", "f_category", "3")
r = ev(s, "change", "f_budget", "2")
r = ev(s, "click", "f_send")
assert not r["host"]["canBack"], r["host"]
sent = posted(s)
assert len(sent) == 1 and sent[0]["url"] == B + "/transactions", sent
body = json.loads(sent[0]["body"])
t0 = body["transactions"][0]
assert t0["type"] == "withdrawal" and t0["amount"] == "5.60" and t0["source_id"] == "1", t0
assert t0["category_id"] == "3" and t0["budget_id"] == "2" and t0["tags"] == ["receipt"], t0
assert t0["destination_name"] == "Bäckerei Schmidt" and t0["date"].startswith("2026-11-14T12:00:00"), t0
assert "Brötchen 4x: 2.40" in t0["notes"] and "Scanned text:" in t0["notes"], t0["notes"]
assert waiting(s) == []

# One entry per item.
s, r = session(extra={"scan.text": US})
r = ev(s, "command", "scan_command")
r = ev(s, "change", "f_split", True)
r = ev(s, "click", "f_send")
splits = json.loads(posted(s)[0]["body"])["transactions"]
assert [x["description"] for x in splits] == ["BANANAS", "MILK 2% GAL", "BREAD WHOLE WHEAT", "EGGS", "Tax and other"], splits
assert splits[-1]["amount"] == "0.70", splits

# The model reads it better; what the user typed is kept.
s, r = start(merged(BASE_MOCK, {"http.request": [STORED] + READS, "scan.text": US,
                                 "ai.ask": {"text": '{"merchant": "Walmart", "total": 12.00}'}}),
             merged(SETTINGS, {"ai": True}))
r = ev(s, "command", "scan_command")
assert SHOWN["f_desc"] == "Walmart" and SHOWN["f_amount"] == "12.00", SHOWN
assert any(c["op"] == "ai.ask" for c in s["calls"]())
# Typed before the model answered: kept.
s, r = start(merged(BASE_MOCK, {"http.request": [STORED] + READS, "scan.text": US,
                                 "ai.ask": {"text": '{"merchant": "Walmart", "total": 12.00}'}}),
             merged(SETTINGS, {"ai": True}))
seen(s["event"]({"type": "command", "id": "scan_command"}))
token = [c["args"]["async"] for c in s["calls"]() if c["op"] == "scan.text"][-1]
seen(s["event"]({"type": "result", "token": token, "value": US}))
seen(s["event"]({"type": "change", "id": "f_desc", "value": "Weekly shop"}))
seen(s["settle"]())
r = ev(s, "click", "f_send")
t0 = json.loads(posted(s)[0]["body"])["transactions"][0]
assert t0["description"] == "Weekly shop" and t0["amount"] == "12.00", t0


# A server out of reach: the entry waits, and Send all sends it later.
OFFLINE = {"when": {"method": "POST", "headers": {"Authorization": "Bearer tok"}},
           "reply": {"error": {"kind": "ConnectionError", "message": "failed to connect to /192.168.1.20"}}}
GOOD = {"when": {"method": "POST", "headers": {"Authorization": "Bearer new"}}, "reply": ok({"data": {"id": "9"}})}
s, r = session(posts=[OFFLINE, GOOD], extra={"scan.text": GRAND})
r = ev(s, "command", "scan_command")
r = ev(s, "click", "f_send")
assert "Type what it cost in the account's currency." in text(r) and r["host"]["canBack"]
r = ev(s, "change", "f_account_amount", "5,10")
r = ev(s, "click", "f_send")
kept = waiting(s)
assert len(kept) == 1 and "Could not reach Firefly III" in kept[0]["error"], kept
assert "Waiting (1)" in text(r)
r = ev(s, "command", "scan_command")
r = ev(s, "change", "f_account_amount", "5.10")
r = ev(s, "click", "f_later")
assert len(waiting(s)) == 2
# A new token answers; both go.
r = ev(s, "change", "view", "overview")
r = ev(s, "click", "forget")
r = ev(s, "submit", "token", "Bearer new")
r = ev(s, "change", "view", "queue")
r = ev(s, "click", "send_all")
assert waiting(s) == [], waiting(s)
assert len(posted(s)) == 3
fx = json.loads(posted(s)[1]["body"])["transactions"][0]
assert fx["amount"] == "5.10" and fx["foreign_amount"] == "5.50" and fx["foreign_currency_code"] == "USD", fx

# A reply the user must fix stays on the form.
INVALID = {"when": {"method": "POST"}, "reply": ok({"message": "The given data was invalid.",
                                                   "errors": {"transactions.0.amount": ["The amount must be more than zero."]}}, 422)}
s, r = session(posts=[INVALID])
r = ev(s, "keyword", "firefly", "4.50 flat white")
assert SHOWN["f_amount"] == "4.50" and SHOWN["f_desc"] == "flat white", SHOWN
r = ev(s, "click", "f_send")
assert r["host"]["canBack"] and "The amount must be more than zero." in text(r), text(r)
assert waiting(s) == []

# Firefly already had it (sent before a timeout): counts as sent.
DUP = {"when": {"method": "POST"}, "reply": ok({"message": "Duplicate of transaction #9."}, 422)}
s, r = session(posts=[DUP])
r = ev(s, "change", "view", "add")
r = ev(s, "change", "quick_amount", "3")
r = ev(s, "change", "quick_text", "Bus")
r = ev(s, "click", "quick_save")
assert "Type an amount" not in text(r) and waiting(s) == []
assert json.loads(posted(s)[0]["body"])["transactions"][0]["description"] == "Bus"

# A local server without network.local granted: the message says what to turn on.
REFUSED = {"when": {"method": "GET"}, "reply": {"error": {"kind": "PermissionError",
           "message": "the user has not turned on 'network.local' for this plugin, which 192.168.1.20 needs"}}}
s, r = start(merged(BASE_MOCK, {"http.request": [REFUSED]}))
assert "home network" in text(r), text(r)

# Nothing set up yet.
s, r = start(BASE_MOCK, merged(SETTINGS, {"server": ""}))
assert "settings page" in text(r) and not [c for c in s["calls"]() if c["op"] == "http.request"]
s, r = start(merged(BASE_MOCK, {"secrets.get": "", "http.request": [STORED] + READS}))
assert "Personal Access Token" in text(r)
r = ev(s, "submit", "token", "  abc  ")
assert any(c["op"] == "secrets.set" and c["args"]["value"] == "abc" for c in s["calls"]())
assert "€1234.50" in text(r)

print("firefly-iii: all tests passed")
