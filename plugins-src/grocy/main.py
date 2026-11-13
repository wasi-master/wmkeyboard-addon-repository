# Grocy: the shopping list, stock and chores of your own Grocy server, from
# the keyboard. Scan a barcode to buy, use or open something; scan a receipt
# to put a whole shop into stock at once.
#
# Grocy is https://grocy.info. The plugin talks to its REST API with a key
# the user makes in Grocy (Settings > Manage API keys).

import time
from urllib.parse import quote

from wm import plugin, ui, storage, scan, ai

import data
import grocy
import receipt

DUE_SOON_DAYS = 5
# Products come in pages: a whole row can be a few KB and a reply at most 1 MB.
PAGE = 200
# Products per stored chunk: a stored value holds at most 64 KB.
CHUNK = 150
MOST_ALIASES = 300
MOST_SUGGESTIONS = 6
RETRY_SECONDS = 15

saved = plugin.state(persist=True, key="prefs", list_id=1, filter="all", aliases={}, tick_off=True)
s = plugin.state(
    version=None, error="", busy=0, loaded=False,
    products={}, units={}, locations=[], lists=[], items=[], stock=[], volatile={}, chores=[],
    query="", stock_query="",
    # the product page
    detail=None, pid=None, amount=1.0, spoiled=False, due=None, price="", last=None,
    # a barcode Grocy does not know
    code="", suggested="", link_query="", new_name="", new_location=None, new_unit=None,
    # a receipt
    lines=[], matching=False, booking=False, booked=None, line=None, line_query="", waiting="",
    chore_undo=None,
)


# ------------------------------------------------------------ loading ----

def load_cache():
    """The products, units and places saved last time, so the panel has
    names to show before the server answers."""
    cache = storage.get("cache") or {}
    if s.products or cache.get("server") != grocy.base_url():
        return
    products = {}
    for n in range(int(cache.get("chunks", 0))):
        for p in storage.get(f"cache_p{n}") or []:
            products[str(p.get("id"))] = p
    s.products = products
    s.units = cache.get("units") or {}
    s.locations = cache.get("locations") or []


def save_cache():
    rows = [p for p in s.products.values()]
    chunks = [rows[i:i + CHUNK] for i in range(0, len(rows), CHUNK)]
    old = int((storage.get("cache") or {}).get("chunks", 0))
    try:
        for n, chunk in enumerate(chunks):
            storage[f"cache_p{n}"] = chunk
        for n in range(len(chunks), old):
            storage.pop(f"cache_p{n}", None)
        storage["cache"] = {"server": grocy.base_url(), "chunks": len(chunks), "units": s.units, "locations": s.locations}
    except ValueError:
        # Storage full: the names load from the server each time instead.
        storage.pop("cache", None)


def failed(text):
    """A load that failed: one less waiting, and the reason on screen."""
    s.busy = max(0, s.busy - 1)
    s.error = text


def oops(text):
    """Something the user did that Grocy refused."""
    s.error = text


def load(path, fn, params=None):
    s.busy += 1

    def done(body):
        s.busy = max(0, s.busy - 1)
        fn(body)

    grocy.get(path, done, failed, params=params)


def refresh():
    s.error = ""
    if not grocy.ready():
        return
    load("/system/info", got_info)


def got_info(info):
    v = data.version_of(info)
    if v is None:
        s.error = "That address did not answer like a Grocy server. Check the address on this plugin's page."
        return
    if v[0] < 3:
        s.error = f"This plugin needs Grocy 3.0 or newer. Your server runs {v[0]}.{v[1]}."
        return
    s.version = [v[0], v[1], v[2]]
    load_products(0, {})
    load("/objects/quantity_units", got_units)
    load("/objects/locations", got_locations)
    load("/objects/shopping_lists", got_lists)
    load_items()
    load_stock()
    load_chores()


def load_items():
    load("/objects/shopping_list", got_items)


def load_stock():
    load("/stock", got_stock)
    days = int(data.num(plugin.settings.get("due_soon_days", DUE_SOON_DAYS), DUE_SOON_DAYS))
    load("/stock/volatile", got_volatile, params={"due_soon_days": str(max(0, days))})


def load_chores():
    load("/chores", got_chores)


def load_products(offset, products):
    def got(rows):
        rows = rows or []
        for row in rows:
            p = data.slim_product(row)
            products[str(data.ident(p.get("id")))] = p
        if len(rows) >= PAGE:
            load_products(offset + PAGE, products)
            return
        s.products = products
        s.loaded = True
        save_cache()

    load("/objects/products", got,
         params={"query[]": "active=1", "order": "name", "limit": str(PAGE), "offset": str(offset)})


def got_units(rows):
    s.units = {str(data.ident(r.get("id"))): data.slim_unit(r) for r in rows or []}
    save_cache()


def got_locations(rows):
    s.locations = [{"id": data.ident(r.get("id")), "name": r.get("name") or ""} for r in rows or []]
    save_cache()


def got_lists(rows):
    s.lists = [{"id": data.ident(r.get("id")), "name": r.get("name") or ""} for r in rows or []]
    if s.lists and saved.list_id not in [l["id"] for l in s.lists]:
        saved.list_id = s.lists[0]["id"]


def got_items(rows):
    s.items = [{
        "id": data.ident(r.get("id")),
        "list": data.ident(r.get("shopping_list_id")) or 1,
        "pid": data.ident(r.get("product_id")),
        "note": r.get("note") or "",
        "amount": data.num(r.get("amount")),
        "qu": data.ident(r.get("qu_id")),
        "done": data.num(r.get("done")) == 1,
    } for r in rows or []]


def got_stock(rows):
    out = []
    for r in rows or []:
        p = r.get("product") or {}
        out.append({
            "pid": data.ident(r.get("product_id")),
            "name": p.get("name") or "",
            "amount": data.num(r.get("amount_aggregated") if data.num(r.get("is_aggregated_amount")) == 1 else r.get("amount")),
            "opened": data.num(r.get("amount_opened")),
            "due": r.get("best_before_date") or "",
            "qu": data.ident(p.get("qu_id_stock")),
        })
    s.stock = sorted(out, key=lambda x: x["name"].lower())


def got_volatile(body):
    body = body or {}
    ids = lambda rows: [data.ident(r.get("product_id")) for r in rows or []]
    s.volatile = {
        "due": ids(body.get("due_products")),
        "overdue": ids(body.get("overdue_products")),
        "expired": ids(body.get("expired_products")),
        "missing": [{
            "pid": data.ident(r.get("id")),
            "name": r.get("name") or "",
            "missing": data.num(r.get("amount_missing")),
            "partly": bool(r.get("is_partly_in_stock")),
        } for r in body.get("missing_products") or []],
    }


def got_chores(rows):
    out = []
    for r in rows or []:
        user = r.get("next_execution_assigned_user") or {}
        out.append({
            "id": data.ident(r.get("chore_id")),
            "name": r.get("chore_name") or "",
            "next": r.get("next_estimated_execution_time") or "",
            "who": user.get("display_name") or "" if isinstance(user, dict) else "",
        })

    def order(c):
        d = data.days_until(str(c["next"])[:10]) if c["next"] else None
        return (1 if d is None else 0, d if d is not None else 0, c["name"].lower())

    s.chores = sorted(out, key=order)


# ------------------------------------------------------------ helpers ----

def product(pid):
    return s.products.get(str(pid)) or {}


def product_name(pid, fallback=""):
    return product(pid).get("name") or fallback or "Product " + str(pid)


def product_pairs():
    return [(data.ident(p.get("id")), p.get("name") or "") for p in s.products.values()]


def find_products(text, most=MOST_SUGGESTIONS):
    """Products whose name fits [text] best: names that start with it first,
    then ones that hold it, then receipt-style word matches."""
    q = receipt.fold(text)
    if not q:
        return []
    scored = []
    for pid, name in product_pairs():
        f = receipt.fold(name)
        if f.startswith(q):
            score = 3.0
        elif q in f:
            score = 2.0
        else:
            score = receipt.score(text, name)
            if score < 0.45:
                continue
        scored.append((-score, name.lower(), pid))
    scored.sort()
    return [pid for _, _, pid in scored[:most]]


def location_name(lid):
    for l in s.locations:
        if l["id"] == data.ident(lid):
            return l["name"]
    return ""


def version_at_least(major):
    return s.version is not None and s.version[0] >= major


def toast(text):
    ui.toast(text)


def first_transaction(rows):
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows[0].get("transaction_id")
    return None


# ------------------------------------------------------------ setup ----

def save_key(text):
    grocy.save_key(text)
    if grocy.ready():
        refresh()


def setup_page():
    with ui.column():
        ui.title("Connect to Grocy")
        if not grocy.base_url():
            ui.markdown(
                "**1.** Type your Grocy server's address under **Grocy server** on this plugin's "
                "settings page, such as `grocy.example.com`, `example.com/grocy` or `192.168.1.20:9283`."
            )
            ui.caption("A server at home (an IP address, or a name like nas.local) also needs Local network access turned on there.")
            ui.button("Open settings", icon="settings", primary=True, on_click=plugin.open_settings)
        else:
            ui.label("Server: " + grocy.base_url(), style="caption")
        ui.markdown("**2.** In Grocy, open Settings › Manage API keys, add a key, and paste it here or under **API key** in the settings.")
        ui.input(label="API key", kind="password", key="api_key", on_submit=save_key, placeholder="Paste the key, then Enter")


# ---------------------------------------------------------- shopping ----

def list_items():
    return [i for i in s.items if i["list"] == saved.list_id]


def item_title(i):
    if i["pid"]:
        return product_name(i["pid"], i["note"])
    return i["note"] or "(empty)"


def item_subtitle(i):
    parts = []
    if i["pid"]:
        qu = i["qu"] or product(i["pid"]).get("qu_id_stock")
        if i["amount"]:
            parts.append(data.amount_with_unit(i["amount"], s.units, qu))
        if i["note"]:
            parts.append(i["note"])
    elif i["amount"]:
        parts.append(data.amount_text(i["amount"]))
    return " · ".join(parts) or None


def set_done(i, done):
    for row in s.items:
        if row["id"] == i["id"]:
            row["done"] = done
    grocy.put(f"/objects/shopping_list/{i['id']}", {"done": 1 if done else 0}, lambda _: None, oops)


def remove_item(i):
    s.items = [row for row in s.items if row["id"] != i["id"]]
    grocy.delete(f"/objects/shopping_list/{i['id']}", lambda _: None, oops)


def bought(i):
    """Book a shopping list row as bought and tick it off."""
    if not i["pid"]:
        set_done(i, True)
        return
    amount = i["amount"] if i["amount"] > 0 else 1

    def booked(rows):
        s.last = {"tid": first_transaction(rows), "text": f"Bought {data.amount_text(amount)} {item_title(i)}"}
        set_done(i, True)
        load_stock()
        toast(s.last["text"])

    grocy.post(f"/stock/products/{i['pid']}/add", {"amount": amount, "transaction_type": "purchase"}, booked, oops)


def add_to_list(pid, amount=1):
    s.query = ""
    name = product_name(pid)

    def added(_):
        toast(f"{name} is on the list")
        load_items()

    grocy.post("/stock/shoppinglist/add-product",
               {"product_id": pid, "list_id": saved.list_id, "product_amount": amount}, added, oops)


def add_note(text):
    text = str(text or "").strip()
    if not text:
        return
    s.query = ""

    def added(_):
        load_items()

    grocy.post("/objects/shopping_list", {"shopping_list_id": saved.list_id, "note": text, "amount": 1}, added, oops)


def submit_query(text):
    """Enter in the add box: the best product if one fits closely, else a note."""
    found = find_products(text, 1)
    if found and receipt.fold(product_name(found[0])) == receipt.fold(text):
        add_to_list(found[0])
    else:
        add_note(text)


def add_missing():
    def added(_):
        toast("Products below their minimum stock are on the list")
        load_items()

    grocy.post("/stock/shoppinglist/add-missing-products", {"list_id": saved.list_id}, added, oops)


def clear_done():
    s.items = [i for i in s.items if not (i["list"] == saved.list_id and i["done"])]
    grocy.post("/stock/shoppinglist/clear", {"list_id": saved.list_id, "done_only": True}, lambda _: load_items(), oops)


def set_list(value):
    saved.list_id = data.ident(value) or 1


def shopping_tab():
    if len(s.lists) > 1:
        ui.select([(l["id"], l["name"]) for l in s.lists], value=saved.list_id, on_change=set_list, label="List",
                  key="list_pick")
    ui.search(placeholder="Add a product or a note", value=s.query, key="add",
              on_change=lambda t: setattr(s, "query", t), on_submit=submit_query)
    if s.query.strip():
        rows = [ui.item(product_name(pid), subtitle="Add to the list", icon="add_shopping_cart", key=f"suggest-{pid}",
                        on_click=lambda pid=pid: add_to_list(pid)) for pid in find_products(s.query)]
        rows.append(ui.item(s.query.strip(), subtitle="Add as a note", icon="sticky_note_2", key="suggest-note",
                            on_click=lambda: add_note(s.query)))
        ui.list(rows)
        return
    items = list_items()
    todo = [i for i in items if not i["done"]]
    done = [i for i in items if i["done"]]
    rows = []
    for i in todo:
        rows.append(ui.item(item_title(i), subtitle=item_subtitle(i), icon="check_box_outline_blank", key=f"shop-{i['id']}",
                            on_click=lambda i=i: set_done(i, True),
                            actions={"Bought it": lambda i=i: bought(i), "Remove": lambda i=i: remove_item(i)}))
    for i in done:
        rows.append(ui.item(item_title(i), subtitle=item_subtitle(i), icon="check_box", key=f"shop-{i['id']}",
                            on_click=lambda i=i: set_done(i, False),
                            actions={"Remove": lambda i=i: remove_item(i)}))
    ui.list(rows, empty="The list is empty" if s.loaded else "Loading…", key="shopping")
    with ui.row():
        ui.button("Add missing", icon="playlist_add", on_click=add_missing)
        ui.button("Clear done", icon="done_all", on_click=clear_done, enabled=len(done) > 0)


# ------------------------------------------------------------- stock ----

FILTERS = [("all", "All"), ("missing", "Low"), ("due", "Due soon"), ("overdue", "Overdue"), ("expired", "Expired")]


def set_filter(value):
    saved.filter = value


def stock_row(r):
    bits = []
    if r["opened"] > 0:
        bits.append(data.amount_text(r["opened"]) + " opened")
    due = data.due_text(r["due"])
    if due:
        bits.append(due)
    return ui.item(r["name"], subtitle=" · ".join(bits) or None,
                   trailing=data.amount_with_unit(r["amount"], s.units, r["qu"]), key=f"stock-{r['pid']}",
                   on_click=lambda pid=r["pid"]: open_product(pid))


def stock_tab():
    v = s.volatile or {}
    counts = {"all": len(s.stock), "missing": len(v.get("missing", [])), "due": len(v.get("due", [])),
              "overdue": len(v.get("overdue", [])), "expired": len(v.get("expired", []))}
    ui.chips([(k, f"{label} {counts[k]}" if counts[k] and k != "all" else label) for k, label in FILTERS],
             value=saved.filter, on_change=set_filter, key="filter")
    ui.search(placeholder="Find in stock", value=s.stock_query, key="stock_find",
              on_change=lambda t: setattr(s, "stock_query", t))
    q = receipt.fold(s.stock_query)
    if saved.filter == "missing":
        rows = []
        for m in v.get("missing", []):
            if q and q not in receipt.fold(m["name"]):
                continue
            qu = product(m["pid"]).get("qu_id_stock")
            rows.append(ui.item(m["name"], subtitle="Some left" if m["partly"] else "None left",
                                trailing="need " + data.amount_with_unit(m["missing"], s.units, qu), key=f"low-{m['pid']}",
                                on_click=lambda pid=m["pid"]: open_product(pid),
                                actions={"Add to the list": lambda m=m: add_to_list(m["pid"], m["missing"])}))
        ui.list(rows, empty="Nothing is below its minimum", key="low")
        return
    wanted = None if saved.filter == "all" else set(v.get(saved.filter, []))
    rows = []
    for r in s.stock:
        if wanted is not None and r["pid"] not in wanted:
            continue
        if q and q not in receipt.fold(r["name"]):
            continue
        rows.append(stock_row(r))
        if len(rows) >= 150:
            break
    ui.list(rows, empty="Nothing here" if s.loaded else "Loading…", key="stock")


# ------------------------------------------------------ product page ----

def open_product(pid, amount=None):
    s.pid = pid
    s.detail = None
    s.spoiled = False
    s.price = ""
    p = product(pid)
    s.amount = amount or data.num(p.get("quick_consume_amount"), 1) or 1
    s.due = data.default_due(p)
    plugin.push(product_page, title=product_name(pid))
    load_detail()


def load_detail():
    pid = s.pid

    def got(detail):
        if s.pid != pid:
            return
        s.detail = detail
        prod = (detail or {}).get("product") or {}
        if prod:
            s.products[str(pid)] = data.slim_product(prod)
        if not s.price and (detail or {}).get("last_price") not in (None, ""):
            s.price = data.amount_text(detail.get("last_price"))

    load(f"/stock/products/{pid}", got)


def booked(verb, amount):
    name = product_name(s.pid)

    def done(rows):
        s.last = {"tid": first_transaction(rows), "text": f"{verb} {data.amount_text(amount)} · {name}"}
        toast(s.last["text"])
        load_detail()
        load_stock()

    return done


def consume():
    amount = s.amount
    body = {"amount": amount, "spoiled": bool(s.spoiled), "allow_subproduct_substitution": True}
    grocy.post(f"/stock/products/{s.pid}/consume", body, booked("Used", amount), oops)


def open_it():
    amount = data.num(product(s.pid).get("quick_open_amount"), 0) or s.amount
    grocy.post(f"/stock/products/{s.pid}/open", {"amount": amount, "allow_subproduct_substitution": True},
               booked("Opened", amount), oops)


def purchase():
    amount = s.amount
    body = {"amount": amount, "transaction_type": "purchase"}
    if s.due:
        body["best_before_date"] = s.due
    price = data.num(s.price, -1)
    if price >= 0 and str(s.price).strip():
        body["price"] = price
    grocy.post(f"/stock/products/{s.pid}/add", body, booked("Bought", amount), oops)


def undo_last():
    last = s.last
    if not last or not last.get("tid"):
        return

    def undone(_):
        toast("Undone: " + last["text"])
        s.last = None
        if s.pid:
            load_detail()
        load_stock()
        load_items()

    grocy.post(f"/stock/transactions/{last['tid']}/undo", None, undone, oops)


def set_due(seconds):
    s.due = time.format("yyyy-MM-dd", seconds) if seconds else None


def product_page():
    p = product(s.pid)
    d = s.detail or {}
    with ui.column():
        if s.error:
            error_banner()
        if not d:
            ui.progress()
        else:
            qu = p.get("qu_id_stock")
            caption = []
            if data.num(d.get("stock_amount_opened")) > 0:
                caption.append(data.amount_text(d.get("stock_amount_opened")) + " opened")
            due = data.due_text(d.get("next_due_date") or d.get("next_best_before_date"))
            if due:
                caption.append(due)
            where = location_name(p.get("location_id"))
            if where:
                caption.append(where)
            ui.stat("In stock", data.amount_with_unit(d.get("stock_amount"), s.units, qu), caption=" · ".join(caption) or None)
        quick = data.num(p.get("quick_consume_amount"), 1)
        ui.stepper(s.amount, min=0, step=quick if 0 < quick < 1 else 1, label="Amount", key="amount",
                   on_change=lambda v: setattr(s, "amount", max(0, data.num(v))))
        enough = s.amount > 0
        with ui.row():
            ui.button("Use", icon="restaurant", primary=True, on_click=consume, enabled=enough)
            if not p.get("disable_open"):
                ui.button("Open", icon="package_2", on_click=open_it, enabled=enough)
            ui.button("Buy", icon="add_shopping_cart", on_click=purchase, enabled=enough)
        ui.toggle("Spoiled (when using)", value=s.spoiled, on_change=lambda v: setattr(s, "spoiled", bool(v)))
        with ui.section("When buying", collapsible=True, open=False):
            if s.due == data.NEVER:
                ui.label("Never goes off", style="caption")
            ui.date(label="Best before", value=data.stamp(s.due) if s.due and s.due != data.NEVER else None,
                    on_change=set_due, key="due")
            ui.input(label="Price per unit", kind="number", value=s.price, key="price",
                     on_change=lambda t: setattr(s, "price", t))
        ui.button("Add to the shopping list", icon="add_shopping_cart", on_click=lambda: add_to_list(s.pid, s.amount or 1))
        undo_row()


def undo_row():
    if s.last and s.last.get("tid"):
        with ui.row():
            ui.label(s.last["text"], style="caption")
            ui.button("Undo", icon="undo", on_click=undo_last)


# ------------------------------------------------------ barcode scan ----

def scan_barcode():
    if not grocy.ready():
        toast("Connect to Grocy first")
        return
    scan.barcode(then=got_code, on_error=lambda e: oops(str(e)))


def got_code(code):
    code = str(code or "").strip()
    if not code:
        return
    s.code = code
    path = "/stock/products/by-barcode/" + quote(code, safe="")
    load_code(path, code)


def load_code(path, code):
    s.busy += 1

    def found(detail):
        s.busy = max(0, s.busy - 1)
        prod = (detail or {}).get("product") or {}
        pid = data.ident(prod.get("id"))
        if pid is None:
            s.error = "Grocy sent a product without an id."
            return
        s.products[str(pid)] = data.slim_product(prod)
        amount = None
        for b in (detail or {}).get("product_barcodes") or []:
            if str(b.get("barcode", "")).lower() == code.lower() and data.num(b.get("amount")) > 0:
                amount = data.num(b.get("amount"))
        open_product(pid, amount)
        s.detail = detail

    def unknown(message):
        s.busy = max(0, s.busy - 1)
        if "no product with barcode" in message.lower():
            new_barcode(code)
        else:
            s.error = message

    grocy.get(path, found, failed, on_status={400: unknown})


def new_barcode(code):
    s.code = code
    s.suggested = ""
    s.link_query = ""
    s.new_name = ""
    s.new_location = s.locations[0]["id"] if s.locations else None
    units = sorted(s.units.values(), key=lambda u: u["name"].lower())
    s.new_unit = units[0]["id"] if units else None
    plugin.push(barcode_page, title="New barcode")

    def looked_up(body):
        if isinstance(body, dict) and body.get("name"):
            s.suggested = str(body.get("name"))
            if not s.new_name:
                s.new_name = s.suggested
                s.link_query = s.suggested
            lid = data.ident(body.get("location_id"))
            if lid and location_name(lid):
                s.new_location = lid
            qu = data.ident(body.get("qu_id_stock"))
            if qu and str(qu) in s.units:
                s.new_unit = qu

    # Grocy's own lookup (Open Food Facts from 4.4 on). Not set up, or nothing
    # found: no suggestion, and the user types a name.
    grocy.get("/stock/barcodes/external-lookup/" + quote(code, safe=""), looked_up, lambda _: None,
              params={"add": "false"}, on_status={400: lambda _: None, 500: lambda _: None})


def link_to(pid):
    code = s.code

    def linked(_):
        toast(f"{code} is now {product_name(pid)}")
        plugin.back()
        open_product(pid)

    grocy.post("/objects/product_barcodes", {"product_id": pid, "barcode": code}, linked, oops)


def create_product():
    name = s.new_name.strip()
    if not name:
        toast("Give the product a name")
        return
    if s.new_location is None or s.new_unit is None:
        toast("Grocy needs a location and a quantity unit first")
        return
    body = {"name": name, "location_id": s.new_location, "qu_id_purchase": s.new_unit, "qu_id_stock": s.new_unit}
    if not version_at_least(4):
        body["qu_factor_purchase_to_stock"] = 1

    def created(answer):
        pid = data.ident((answer or {}).get("created_object_id"))
        if pid is None:
            s.error = "Grocy did not say which product it made."
            return
        s.products[str(pid)] = {"id": pid, "name": name, "location_id": s.new_location,
                                "qu_id_stock": s.new_unit, "qu_id_purchase": s.new_unit}
        save_cache()
        link_to(pid)

    grocy.post("/objects/products", body, created, oops)


def barcode_page():
    with ui.column():
        if s.error:
            error_banner()
        ui.label("Grocy does not know " + s.code + " yet.")
        if s.suggested:
            ui.label("Looked up: " + s.suggested, style="caption")
        with ui.section("It is one of my products"):
            ui.search(placeholder="Find a product", value=s.link_query, key="link",
                      on_change=lambda t: setattr(s, "link_query", t))
            found = find_products(s.link_query)
            ui.list([ui.item(product_name(pid), subtitle="Link this barcode", icon="link", key=f"link-{pid}",
                             on_click=lambda pid=pid: link_to(pid)) for pid in found],
                    empty="Type a name to find it" if not s.link_query.strip() else "No product by that name")
        with ui.section("Add a new product"):
            ui.input(label="Name", value=s.new_name, key="new_name", on_change=lambda t: setattr(s, "new_name", t))
            if s.locations:
                ui.select([(l["id"], l["name"]) for l in s.locations], value=s.new_location, label="Location",
                          on_change=lambda v: setattr(s, "new_location", data.ident(v)))
            units = sorted(s.units.values(), key=lambda u: u["name"].lower())
            if units:
                ui.select([(u["id"], u["name"]) for u in units], value=s.new_unit, label="Unit",
                          on_change=lambda v: setattr(s, "new_unit", data.ident(v)))
            ui.button("Create and link", icon="add_circle", primary=True, on_click=create_product,
                      enabled=bool(s.new_name.strip()))


# ----------------------------------------------------------- receipt ----

def scan_receipt():
    if not grocy.ready():
        toast("Connect to Grocy first")
        return
    scan.text(then=got_receipt, on_error=lambda e: oops(str(e)))


def got_receipt(text):
    if not text:
        return
    items = receipt.parse(text)
    if not items:
        toast("No bought items found in that text")
        return
    pairs = product_pairs()
    lines = []
    for it in items:
        pid = receipt.best_match(it["name"], pairs, saved.aliases)
        lines.append({"text": it["text"], "name": it["name"], "amount": it["amount"], "price": it["price"],
                      "pid": pid, "by": "match" if pid else "", "on": pid is not None})
    s.lines = lines
    s.booked = None
    s.waiting = ""
    plugin.push(receipt_page, title="Receipt")
    match_with_ai(items, pairs)


def match_with_ai(items, pairs):
    if not plugin.settings.get("ai_receipts", True) or not pairs:
        return
    try:
        if not ai.available():
            return
    except Exception:
        return  # AI not allowed or not set up: the word matches stand.
    prompt, system = receipt.ai_prompt(items, pairs)
    s.matching = True
    ai.ask(prompt, system=system, then=got_ai, on_error=ai_failed)


def got_ai(reply):
    s.matching = False
    table = receipt.read_ai_reply(reply, s.lines, [pid for pid, _ in product_pairs()])
    for i, line in enumerate(s.lines):
        if i not in table or line["by"] == "you":
            continue
        pid, amount = table[i]
        if pid is None:
            continue
        line["pid"] = pid
        line["by"] = "ai"
        line["on"] = True
        if line["amount"] == 1 and amount > 1:
            line["amount"] = amount


def ai_failed(e):
    s.matching = False
    toast("AI matching failed: " + str(e))


def line_title(line):
    if line["pid"]:
        return product_name(line["pid"])
    return "Not matched: " + line["name"]


def line_subtitle(line):
    bits = [line["text"]]
    if line["by"] == "ai":
        bits.append("matched by AI")
    return " · ".join(bits)


def toggle_line(i):
    line = s.lines[i]
    line["on"] = not line["on"] and line["pid"] is not None


def edit_line(i):
    s.line = i
    s.line_query = ""
    plugin.push(line_page, title="Receipt line")


def choose_for_line(pid):
    line = s.lines[s.line]
    line["pid"] = pid
    line["by"] = "you"
    line["on"] = True
    plugin.back()


def line_page():
    line = s.lines[s.line]
    with ui.column():
        ui.label(line["text"], style="caption")
        ui.stepper(line["amount"], min=1, step=1, label="How many", key="line_amount",
                   on_change=lambda v: line.update({"amount": max(1, data.num(v, 1))}))
        ui.toggle("Add this line", value=line["on"], on_change=lambda v: line.update({"on": bool(v) and line["pid"] is not None}))
        ui.search(placeholder="Which product is it?", value=s.line_query, key="line_find",
                  on_change=lambda t: setattr(s, "line_query", t))
        found = find_products(s.line_query or line["name"], 8)
        ui.list([ui.item(product_name(pid), icon="check" if pid == line["pid"] else "inventory_2", key=f"pick-{pid}",
                         selected=pid == line["pid"], on_click=lambda pid=pid: choose_for_line(pid))
                 for pid in found], empty="No product fits; search for it")


def remember(line):
    if line["by"] == "match" or not line["pid"]:
        return
    aliases = dict(saved.aliases)
    aliases[receipt.fold(line["name"])] = line["pid"]
    if len(aliases) > MOST_ALIASES:
        for k in list(aliases.keys())[:len(aliases) - MOST_ALIASES]:
            del aliases[k]
    saved.aliases = aliases


def book_receipt():
    s.booking = True
    s.booked = {"count": 0, "tids": [], "failed": []}
    book_line(0)


def book_line(i):
    while i < len(s.lines) and not (s.lines[i]["on"] and s.lines[i]["pid"]):
        i += 1
    if i >= len(s.lines):
        s.booking = False
        s.waiting = ""
        n = s.booked["count"]
        toast(f"Added {n} item{'s' if n != 1 else ''} to stock")
        load_stock()
        load_items()
        return
    line = s.lines[i]
    body = {"amount": line["amount"], "transaction_type": "purchase"}
    if line["price"] is not None and line["amount"] > 0:
        body["price"] = round(line["price"] / line["amount"], 4)

    def done(rows):
        s.booked["count"] += 1
        tid = first_transaction(rows)
        if tid:
            s.booked["tids"].append(tid)
        remember(line)
        if saved.tick_off:
            for row in list_items():
                if row["pid"] == line["pid"] and not row["done"]:
                    set_done(row, True)
                    break
        book_line(i + 1)

    def fail(text):
        if "too many requests" in text:
            # The keyboard allows 60 requests a minute; wait and go on.
            s.waiting = f"Waiting {RETRY_SECONDS} s for the request limit…"
            plugin.after(RETRY_SECONDS, lambda: book_line(i))
            return
        s.booked["failed"].append(line["name"] + ": " + text)
        book_line(i + 1)

    grocy.post(f"/stock/products/{line['pid']}/add", body, done, fail)


def undo_receipt():
    tids = list((s.booked or {}).get("tids") or [])
    if not tids:
        return

    def undo_next(k):
        if k >= len(tids):
            toast("Receipt undone")
            s.booked = None
            load_stock()
            load_items()
            return
        grocy.post(f"/stock/transactions/{tids[k]}/undo", None, lambda _: undo_next(k + 1),
                   lambda text: (oops(text), undo_next(k + 1)))

    undo_next(0)


def receipt_page():
    chosen = [l for l in s.lines if l["on"] and l["pid"]]
    with ui.column():
        if s.error:
            error_banner()
        if s.booked is not None and not s.booking:
            ui.label(f"Added {s.booked['count']} to stock.", style="title")
            for f in s.booked["failed"]:
                ui.label(f, color="danger")
            with ui.row():
                ui.button("Undo all", icon="undo", on_click=undo_receipt, enabled=len(s.booked["tids"]) > 0)
                ui.button("Done", primary=True, on_click=plugin.back)
            return
        if s.matching:
            ui.progress()
            ui.caption("Matching lines with your AI model…")
        elif s.booking:
            ui.progress()
            ui.caption(s.waiting or f"Adding {s.booked['count'] + 1} of {len(chosen)}…")
        else:
            ui.caption("Check each line. Tap one to pick another product or change how many.")
        rows = []
        for i, line in enumerate(s.lines):
            trailing = "×" + data.amount_text(line["amount"])
            if line["price"] is not None:
                trailing = trailing + " · " + data.amount_text(line["price"])
            rows.append(ui.item(line_title(line), subtitle=line_subtitle(line), trailing=trailing,
                                icon="check_box" if line["on"] else "check_box_outline_blank", key=f"line-{i}",
                                on_click=lambda i=i: edit_line(i),
                                actions={("Skip" if line["on"] else "Add"): lambda i=i: toggle_line(i)}))
        ui.list(rows)
        ui.toggle("Tick bought items off the shopping list", value=saved.tick_off,
                  on_change=lambda v: setattr(saved, "tick_off", bool(v)))
        ui.button(f"Add {len(chosen)} to stock", icon="inventory", primary=True, on_click=book_receipt,
                  enabled=len(chosen) > 0 and not s.booking)


# ------------------------------------------------------------ chores ----

def track(chore, skipped=False):
    body = {"skipped": True} if skipped else {}

    def tracked(row):
        s.chore_undo = {"id": data.ident((row or {}).get("id")), "text": ("Skipped " if skipped else "Done: ") + chore["name"]}
        toast(s.chore_undo["text"])
        load_chores()

    grocy.post(f"/chores/{chore['id']}/execute", body, tracked, oops)


def undo_chore():
    u = s.chore_undo
    if not u or u.get("id") is None:
        return

    def undone(_):
        s.chore_undo = None
        toast("Undone")
        load_chores()

    grocy.post(f"/chores/executions/{u['id']}/undo", None, undone, oops)


def chores_tab():
    if s.chore_undo:
        with ui.row():
            ui.label(s.chore_undo["text"], style="caption")
            ui.button("Undo", icon="undo", on_click=undo_chore)
    rows = []
    for c in s.chores:
        when = data.when_text(c["next"])
        late = "overdue" in when
        sub = when + (" · " + c["who"] if c["who"] else "")
        rows.append(ui.item(c["name"], subtitle=sub, icon="warning" if late else ("today" if when == "today" else "event"),
                            key=f"chore-{c['id']}",
                            on_click=lambda c=c: track(c),
                            actions={"Done now": lambda c=c: track(c), "Skip": lambda c=c: track(c, True)}))
    ui.list(rows, empty="No chores" if s.loaded else "Loading…", key="chores")
    if rows:
        ui.caption("Tap a chore when it is done.")


# ------------------------------------------------------------- panel ----

def error_banner():
    with ui.card():
        ui.label(s.error, color="danger")
        with ui.row():
            ui.button("Try again", icon="refresh", on_click=refresh)
            ui.button("Hide", on_click=lambda: setattr(s, "error", ""))


@plugin.on_open
def opened():
    load_cache()
    refresh()


@plugin.command("Scan", icon="barcode_scanner")
def command_scan():
    scan_barcode()


@plugin.command("Receipt", icon="receipt_long")
def command_receipt():
    scan_receipt()


@plugin.command("Refresh", icon="refresh")
def command_refresh():
    refresh()


@plugin.keyword("grocy")
def from_keyword(text):
    s.query = str(text or "").strip()


@plugin.setting_changed("server")
def server_changed(_):
    s.products = {}
    s.loaded = False
    refresh()


@plugin.setting_changed("api_key")
def key_changed(_):
    grocy.forget_key()
    refresh()


def render():
    if not grocy.ready():
        setup_page()
        return
    with ui.column():
        if s.error:
            error_banner()
        elif s.busy and not s.loaded:
            ui.progress()
        shop = ui.page("Shopping")
        with shop:
            shopping_tab()
        stock = ui.page("Stock")
        with stock:
            stock_tab()
        chores = ui.page("Chores")
        with chores:
            chores_tab()
        ui.tabs(shop, stock, chores, key="tabs")
        if s.last and s.last.get("tid"):
            undo_row()
