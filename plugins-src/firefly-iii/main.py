"""Firefly III from the keyboard: scan a receipt and send it to your own
Firefly III, add spending by hand, keep entries for later when the server is
out of reach, and see balances and this month's spending."""

import time

import wm
from wm import plugin, ui, http, secrets, scan, ai

import firefly
import receipt

QUEUE_MAX = 30
LISTS_MAX_AGE = 6 * 3600
RAW_MAX = 1500

state = plugin.state(
    view="overview",
    busy=0,
    error=None,
    version=None,
    accounts=None,
    summary=None,
    by_category=None,
    recent=None,
    quick_amount="",
    quick_text="",
    form_error=None,
    reading=False,
    sending=False,
    picking=None,
    pick_filter="",
    token=None,
)
# Lists the form needs even with no connection, and the receipt being checked.
saved = plugin.state(persist=True, key="saved", accounts=[], categories=[], budgets=[], loaded_at=0,
                     last_source=None, draft=None)
# Entries waiting to be sent: [{"id", "draft", "error", "at"}].
queue = plugin.state(persist=True, key="queue", items=[], next_id=1)


# ---- connection ------------------------------------------------------------

def server():
    return plugin.settings.get("server", "") or ""


def token():
    """The Personal Access Token from the plugin's settings page (a secret
    row, kept in secrets under "token"), read once per opening."""
    if state.token is None:
        value = str(secrets.get("token", "") or "").strip()
        if value.lower().startswith("bearer "):
            value = value[7:].strip()
        state.token = value
    return state.token


def configured():
    return bool(firefly.base_url(server())) and bool(token())


def describe(error):
    """An exception from the keyboard or the network, in words for the user."""
    text = str(error)
    if isinstance(error, PermissionError):
        if "network.local" in text:
            return ("Your server is on your home network. On this plugin's page in WM Keyboard's settings, "
                    "turn on “Reach the server you type in its settings on your home network”.")
        if "risky permissions are turned off" in text:
            return "Risky permissions are off for all plugins. Turn on Allow risky permissions under Tools, Plugins."
        if "has not turned on" in text:
            return "Turn on internet access for this plugin on its page in WM Keyboard's settings."
        return "WM Keyboard did not allow this: " + text
    if isinstance(error, ValueError) and "https" in text:
        return ("Firefly III has to be at an https address, or on your home network "
                "(like http://192.168.1.20:8080). Check the address on the plugin's settings page.")
    if isinstance(error, TimeoutError):
        return "Firefly III did not answer in time."
    if isinstance(error, ConnectionError):
        return "Could not reach Firefly III. " + text
    return text


def request(method, path, then, params=None, body=None, bad=None, broke=None):
    """One API call without waiting. [then] gets the reply when it is OK;
    [bad] an error reply, [broke] an exception. Both default to showing the
    problem at the top of the panel."""
    state.busy = state.busy + 1

    def got(r):
        state.busy = max(0, state.busy - 1)
        if r.ok:
            then(r)
        elif bad is not None:
            bad(r)
        else:
            state.error = firefly.problem(r)

    def failed(e):
        state.busy = max(0, state.busy - 1)
        if broke is not None:
            broke(e)
        else:
            state.error = describe(e)

    http.request(method, firefly.api(server(), path), params=params, json=body,
                 headers=firefly.headers(token()), then=got, on_error=failed)


# ---- loading -----------------------------------------------------------------

def month_range():
    p = time.parts(time.time())
    first = wm.timestamp(p["year"], p["month"], 1)
    if p["month"] == 12:
        after = wm.timestamp(p["year"] + 1, 1, 1)
    else:
        after = wm.timestamp(p["year"], p["month"] + 1, 1)
    return time.format("yyyy-MM-dd", first), time.format("yyyy-MM-dd", after - 86400)


def refresh(lists=False):
    if not configured():
        return
    state.error = None
    start, end = month_range()
    request("GET", "/about", got_about)
    request("GET", "/accounts", got_accounts, params={"type": "asset", "limit": "100"})
    request("GET", "/summary/basic", got_summary, params={"start": start, "end": end})
    request("GET", "/insight/expense/category", got_insight, params={"start": start, "end": end})
    request("GET", "/transactions", got_recent, params={"limit": "15", "page": "1"})
    if lists or not saved.categories or time.time() - saved.loaded_at > LISTS_MAX_AGE:
        request("GET", "/categories", got_categories, params={"limit": "500"})
        request("GET", "/budgets", got_budgets, params={"limit": "200"})


def got_about(r):
    state.version = ((r.json() or {}).get("data") or {}).get("version")


def got_accounts(r):
    accounts = firefly.read_accounts(r.json())
    state.accounts = accounts
    saved.accounts = [{"id": a["id"], "name": a["name"], "currency": a["currency"], "symbol": a["symbol"]} for a in accounts]


def got_summary(r):
    state.summary = firefly.read_summary(r.json())


def got_insight(r):
    state.by_category = firefly.read_insight(r.json())


def got_recent(r):
    state.recent = firefly.read_groups(r.json())


def got_categories(r):
    saved.categories = firefly.read_named(r.json())
    saved.loaded_at = time.time()


def got_budgets(r):
    saved.budgets = firefly.read_named(r.json())


@plugin.on_open
def opened():
    if configured():
        refresh()


@plugin.command("Refresh", icon="refresh")
def refresh_all():
    state.token = None
    refresh(lists=True)


@plugin.command("Scan a receipt", icon="document_scanner")
def scan_command():
    start_scan()


# ---- drafts --------------------------------------------------------------------

def account(account_id):
    for a in saved.accounts:
        if a["id"] == account_id:
            return a
    return None


def default_source():
    if saved.last_source and account(saved.last_source):
        return saved.last_source
    return saved.accounts[0]["id"] if saved.accounts else ""


def new_draft(found=None, raw=None):
    found = found or {}
    when = time.time()
    if found.get("date"):
        y, m, d = found["date"].split("-")
        when = wm.timestamp(int(y), int(m), int(d), 12)
    total = found.get("total")
    source = default_source()
    acc = account(source)
    return {
        "description": found.get("merchant") or "",
        "destination": "",
        "amount": firefly.money(total) if total else "",
        "currency": found.get("currency") or (acc["currency"] if acc else ""),
        "account_amount": "",
        "date": when,
        "source_id": source,
        "category_id": "",
        "category": "",
        "budget_id": "",
        "items": found.get("items") or [],
        "split": False,
        "notes": "",
        "raw": str(raw or "")[:RAW_MAX],
        "scanned": raw is not None,
    }


def number(text):
    value = receipt.amount_value(str(text or "").replace("-", ""))
    return value if value is not None and value > 0 else None


def foreign_currency(d):
    acc = account(d.get("source_id"))
    cur = (d.get("currency") or "").strip().upper()
    if acc and cur and acc["currency"] and cur != acc["currency"]:
        return cur
    return None


def check(d):
    """Why [d] cannot be sent yet, or None."""
    if number(d.get("amount")) is None:
        return "Type the amount."
    if not d.get("source_id") or not account(d["source_id"]):
        return "Pick the account it was paid from."
    if foreign_currency(d) and number(d.get("account_amount")) is None:
        return "Type what it cost in the account's currency."
    return None


def notes_of(d):
    lines = []
    if d.get("notes", "").strip():
        lines.append(d["notes"].strip())
    if d.get("items") and not d.get("split"):
        lines.append("\n".join(f"- {i['name']}: {firefly.money(i['amount'])}" for i in d["items"]))
    if d.get("raw") and plugin.settings.get("keep_text", True):
        lines.append("Scanned text:\n" + d["raw"])
    return "\n\n".join(lines)


def body_of(d):
    tag = (plugin.settings.get("tag", "") or "").strip() if d.get("scanned") else ""
    draft = {
        "description": d.get("description"),
        "destination": d.get("destination"),
        "amount": number(d.get("amount")),
        "date": time.format("yyyy-MM-dd'T'HH:mm:ssXXX", d.get("date") or time.time()),
        "source_id": d.get("source_id"),
        "category_id": d.get("category_id"),
        "category": d.get("category"),
        "budget_id": d.get("budget_id"),
        "items": d.get("items"),
        "split": d.get("split"),
        "notes": notes_of(d),
        "foreign_currency": foreign_currency(d),
        "account_amount": number(d.get("account_amount")),
    }
    return firefly.withdrawal(draft, apply_rules=plugin.settings.get("apply_rules", True), tag=tag or None)


# ---- scanning ------------------------------------------------------------------

def start_scan():
    state.error = None
    scan.text(then=scanned, on_error=lambda e: setattr(state, "error", describe(e)))


def month_first():
    return str(plugin.locale or "").startswith("en-US")


def scanned(text):
    if not text:
        return
    found = receipt.parse(text, month_first=month_first())
    saved.draft = new_draft(found, text)
    open_form()
    if plugin.settings.get("ai", False):
        read_with_ai(found, text)


def read_with_ai(found, text):
    try:
        if not ai.available():
            return
    except Exception:
        return
    state.reading = True

    def answered(reply):
        state.reading = False
        better = receipt.merge_ai(found, reply)
        d = saved.draft
        if d is None:
            return
        # Keep what the user already changed; fill in what the model read better.
        fresh = new_draft(better, text)
        touched = d.get("touched") or []
        for key in ("description", "amount", "currency", "date", "items"):
            if key not in touched:
                d[key] = fresh[key]
        saved.draft = d

    def failed(e):
        state.reading = False

    ai.ask(receipt.ai_prompt(text), system=receipt.AI_SYSTEM, then=answered, on_error=failed)


def open_form(title="Check and send"):
    state.form_error = None
    plugin.push(form_page, title=title)


def set_field(key, value):
    d = saved.draft
    if d is None:
        return
    d[key] = value
    if key not in (d.get("touched") or []):
        d["touched"] = (d.get("touched") or []) + [key]
    if key == "source_id":
        acc = account(value)
        if acc and not foreign_currency(d) and not d.get("scanned"):
            d["currency"] = acc["currency"]
    saved.draft = d


def set_category(value):
    if value == "__new":
        set_field("category_id", "")
        set_field("category", " ")
    else:
        set_field("category", "")
        set_field("category_id", value)


def finish_form():
    saved.draft = None
    state.form_error = None
    plugin.back()


def send_draft():
    d = saved.draft
    if d is None:
        return
    why = check(d)
    if why:
        state.form_error = why
        return
    if d.get("category"):
        d["category"] = d["category"].strip()
    saved.last_source = d["source_id"]
    entry = {"id": queue.next_id, "draft": d, "error": None, "at": time.time()}
    queue.next_id = queue.next_id + 1
    state.sending = True

    def done(message):
        state.sending = False
        ui.toast(message)
        finish_form()
        refresh()

    def kept(message):
        state.sending = False
        entry["error"] = message
        add_to_queue(entry)
        ui.toast("Kept for later: " + message)
        finish_form()

    def refused(message):
        state.sending = False
        state.form_error = message

    post(entry, done, kept, refused)


def keep_draft():
    d = saved.draft
    if d is None:
        return
    add_to_queue({"id": queue.next_id, "draft": d, "error": None, "at": time.time()})
    queue.next_id = queue.next_id + 1
    ui.toast("Kept for later. Send it from Waiting.")
    finish_form()


def discard_draft():
    ui.dialog("Discard this entry?", None, buttons=("Discard", "Keep editing"), on_result=discard_answer)


def discard_answer(choice):
    if choice == "Discard":
        finish_form()


def post(entry, done, kept, refused):
    """Send [entry]'s draft. [done] hears success (or that Firefly already had
    it), [kept] a failure worth trying again, [refused] a reply the user must
    fix the entry for."""
    if not configured():
        kept("no server or token set up yet")
        return

    def bad(r):
        if firefly.is_duplicate(r):
            done("Firefly III already has this one.")
        elif r.status_code in (401, 408, 429) or r.status_code >= 500:
            kept(firefly.problem(r))
        else:
            refused(firefly.problem(r))

    request("POST", "/transactions", lambda r: done("Saved in Firefly III."), body=body_of(entry["draft"]),
            bad=bad, broke=lambda e: kept(describe(e)))


# ---- the queue -------------------------------------------------------------------

def add_to_queue(entry):
    items = [e for e in queue.items if e["id"] != entry["id"]]
    items.append(entry)
    if len(items) > QUEUE_MAX:
        items = items[-QUEUE_MAX:]
    queue.items = items


def drop(entry_id):
    queue.items = [e for e in queue.items if e["id"] != entry_id]


def send_waiting(ids=None):
    """Send the waiting entries one after another; each failure stays."""
    todo = ids if ids is not None else [e["id"] for e in queue.items]
    if not todo:
        return
    state.sending = True
    send_one(todo, 0, [0, 0])


def send_one(ids, at, tally):
    if at >= len(ids):
        state.sending = False
        sent, left = tally
        if sent:
            ui.toast(f"Sent {sent}." + (f" {left} still waiting." if left else ""))
            refresh()
        elif left:
            ui.toast("Nothing sent. Look at the reasons under each entry.")
        return
    entry = None
    for e in queue.items:
        if e["id"] == ids[at]:
            entry = e
    if entry is None:
        send_one(ids, at + 1, tally)
        return
    if not entry["draft"].get("source_id"):
        entry["draft"]["source_id"] = default_source()

    def done(message):
        drop(entry["id"])
        send_one(ids, at + 1, [tally[0] + 1, tally[1]])

    def failed(message):
        entry["error"] = message
        add_to_queue(entry)
        send_one(ids, at + 1, [tally[0], tally[1] + 1])

    why = check(entry["draft"])
    if why:
        failed(why)
        return
    post(entry, done, failed, failed)


def edit_waiting(entry):
    drop(entry["id"])
    saved.draft = entry["draft"]
    open_form("Edit and send")


# ---- quick entry and the keyword -------------------------------------------------

def quick_save():
    amount = number(state.quick_amount)
    if amount is None:
        state.error = "Type an amount first."
        return
    d = new_draft()
    d["amount"] = firefly.money(amount)
    d["description"] = state.quick_text.strip()
    why = check(d)
    if why:
        state.error = why
        return
    state.error = None
    saved.last_source = d["source_id"]
    entry = {"id": queue.next_id, "draft": d, "error": None, "at": time.time()}
    queue.next_id = queue.next_id + 1

    def done(message):
        state.quick_amount = ""
        state.quick_text = ""
        ui.toast(message)
        refresh()

    def kept(message):
        entry["error"] = message
        add_to_queue(entry)
        state.quick_amount = ""
        state.quick_text = ""
        ui.toast("Kept for later: " + message)

    post(entry, done, kept, lambda message: setattr(state, "error", message))


def quick_more():
    d = new_draft()
    amount = number(state.quick_amount)
    if amount is not None:
        d["amount"] = firefly.money(amount)
    d["description"] = state.quick_text.strip()
    saved.draft = d
    open_form("New entry")


@plugin.keyword("firefly")
def from_keyword(text):
    """`@firefly 4.50 coffee`: the form, filled in."""
    words = str(text or "").split()
    amount = None
    rest = []
    for w in words:
        value = number(w) if amount is None else None
        if value is not None:
            amount = value
        else:
            rest.append(w)
    d = new_draft()
    if amount is not None:
        d["amount"] = firefly.money(amount)
    d["description"] = " ".join(rest)
    saved.draft = d
    state.view = "add"
    open_form("New entry")


# ---- changing a transaction ------------------------------------------------------

def start_pick(group, split, kind):
    state.picking = {"group": group, "journal": split["journal"], "kind": kind}
    state.pick_filter = ""
    plugin.push(pick_page, title="Category" if kind == "category" else "Budget")


def picked(item_id):
    p = state.picking
    if p is None:
        return
    if p["kind"] == "category":
        body = firefly.recategorise(p["group"], p["journal"], category_id=item_id)
    else:
        body = firefly.recategorise(p["group"], p["journal"], budget_id=item_id)
    state.picking = None
    plugin.back()

    def changed(r):
        ui.toast("Changed.")
        refresh()

    request("PUT", "/transactions/" + p["group"]["id"], changed, body=body)


def ask_delete(group):
    ui.dialog("Delete “" + group["title"] + "”?", "It is deleted in Firefly III too.",
              buttons=("Delete", "Cancel"), on_result=lambda choice: delete_answer(group, choice))


def delete_answer(group, choice):
    if choice != "Delete":
        return

    def deleted(r):
        ui.toast("Deleted.")
        refresh()

    request("DELETE", "/transactions/" + group["id"], deleted)


# ---- drawing ---------------------------------------------------------------------

def bind(fn, *args):
    """A callback that calls fn(*args), for rows drawn in a loop: each row
    keeps its own values without relying on lambda defaults."""
    def call():
        return fn(*args)
    return call


def fmt(value, symbol=""):
    text = f"{abs(value):.2f}"
    return ("-" if value < 0 else "") + (symbol or "") + text


def set_view(value):
    state.view = value


def render():
    with ui.column():
        if not firefly.base_url(server()):
            ui.empty("Type your Firefly III address on this plugin's settings page. "
                     "It can be an https address, or a server on your home network like http://192.168.1.20:8080.",
                     icon="dns")
            return
        if not token():
            setup()
            return
        waiting = len(queue.items)
        ui.select([("overview", "Overview"), ("add", "Add"), ("queue", f"Waiting ({waiting})" if waiting else "Waiting")],
                  value=state.view, on_change=set_view, style="segmented", key="view")
        if state.error:
            ui.label(state.error, color="danger")
        if state.busy or state.sending:
            ui.progress()
        if saved.draft is not None:
            with ui.card(title="An entry you have not sent", on_click=lambda: open_form()):
                ui.caption(saved.draft.get("description") or "Receipt")
        if state.view == "add":
            add_view()
        elif state.view == "queue":
            queue_view()
        else:
            overview()


def setup():
    with ui.card(title="Connect to Firefly III"):
        ui.markdown("In Firefly III, open **Options → Profile → OAuth**, and under "
                    "**Personal Access Tokens** press **Create new token**. Copy the whole token "
                    "and paste it into **Personal Access Token** on this plugin's settings page.")
        ui.caption("It is kept encrypted on this phone, and sent only to " + firefly.host_of(server()) + ".")
        ui.button("I have pasted it", icon="refresh", on_click=refresh_all, key="recheck")


def overview():
    s = state.summary
    if s:
        cur = state.accounts[0]["currency"] if state.accounts else None
        spent = firefly.pick(s["spent"], cur)
        left = firefly.pick(s["left"], cur)
        net = firefly.pick(s["net"], cur) or firefly.pick(s["balance"], cur)
        with ui.grid(columns=2):
            ui.stat("Spent this month", spent["text"] if spent else "0", key="spent")
            if left:
                ui.stat("Left to spend", left["text"], key="left")
            elif net:
                ui.stat("Net worth", net["text"], key="net")
    if state.by_category:
        top = state.by_category[:6]
        ui.chart([round(v, 2) for _, v in top], kind="bar", labels=[n[:12] for n, _ in top], key="chart")
        ui.caption("Spending by category this month")
    if state.accounts:
        with ui.section("Accounts", collapsible=True):
            ui.list([ui.item(a["name"], icon="account_balance", trailing=fmt(a["balance"], a["symbol"]))
                     for a in state.accounts])
    if state.recent is not None:
        with ui.section("Recent", collapsible=True):
            rows = []
            for g in state.recent:
                first = g["splits"][0]
                sign = "-" if first["type"] == "withdrawal" else ("+" if first["type"] == "deposit" else "")
                bits = [first["date"]]
                if first["category"]:
                    bits.append(first["category"])
                if first["budget"]:
                    bits.append(first["budget"])
                actions = {}
                if first["type"] == "withdrawal":
                    actions["Change category"] = bind(start_pick, g, first, "category")
                    if saved.budgets:
                        actions["Change budget"] = bind(start_pick, g, first, "budget")
                actions["Delete"] = bind(ask_delete, g)
                rows.append(ui.item(g["title"], subtitle=" · ".join(bits), key="tx" + g["id"],
                                    icon="receipt_long" if first["type"] == "withdrawal" else "swap_horiz",
                                    trailing=sign + fmt(firefly.group_total(g), first["symbol"]), actions=actions))
            ui.list(rows, empty="No transactions yet")
    if state.version:
        ui.caption("Firefly III " + str(state.version) + " at " + firefly.host_of(server()))


def add_view():
    with ui.card(title="Scan a receipt"):
        ui.caption("The keyboard reads the receipt. You check every field before anything is sent.")
        ui.button("Scan receipt", icon="document_scanner", primary=True, on_click=start_scan, key="scan")
    with ui.card(title="Quick entry"):
        with ui.row(weights=[1, 2]):
            ui.input(label="Amount", value=state.quick_amount, kind="number",
                     on_change=lambda v: setattr(state, "quick_amount", v), key="quick_amount")
            ui.input(label="What for", value=state.quick_text,
                     on_change=lambda v: setattr(state, "quick_text", v), key="quick_text")
        acc = account(default_source())
        if acc:
            ui.caption("Paid from " + acc["name"])
        with ui.row():
            ui.button("Save", primary=True, on_click=quick_save, key="quick_save")
            ui.button("More details", on_click=quick_more, key="quick_more")


def queue_view():
    if not queue.items:
        ui.empty("Nothing waiting. Entries that could not be sent wait here until you send them again.",
                 icon="cloud_done")
        return
    rows = []
    for e in queue.items:
        d = e["draft"]
        bits = [time.format("d MMM", d.get("date") or e["at"])]
        if e.get("error"):
            bits.append(e["error"])
        rows.append(ui.item(d.get("description") or "Receipt", subtitle=" · ".join(bits), key="q" + str(e["id"]),
                            icon="error" if e.get("error") else "schedule",
                            trailing=(d.get("amount") or "?") + " " + (d.get("currency") or ""),
                            on_click=bind(edit_waiting, e),
                            actions={"Send now": bind(send_waiting, [e["id"]]),
                                     "Edit": bind(edit_waiting, e),
                                     "Delete": bind(drop, e["id"])}))
    ui.list(rows)
    ui.button("Send all", icon="cloud_upload", primary=True, on_click=lambda: send_waiting(), key="send_all",
              enabled=not state.sending)


def options(rows, none_label):
    return [("", none_label)] + [(r["id"], r["name"]) for r in rows]


def form_page():
    d = saved.draft
    if d is None:
        ui.empty("Nothing to check.", icon="check")
        return
    with ui.column():
        if state.form_error:
            ui.label(state.form_error, color="danger")
        if state.reading:
            ui.progress()
            ui.caption("Reading the receipt with AI…")
        ui.input(label="Description", value=d.get("description", ""), placeholder="Shop or what it was for",
                 on_change=lambda v: set_field("description", v), key="f_desc")
        with ui.row(weights=[2, 1]):
            ui.input(label="Amount", value=d.get("amount", ""), kind="number",
                     on_change=lambda v: set_field("amount", v), key="f_amount")
            ui.input(label="Currency", value=d.get("currency", ""),
                     on_change=lambda v: set_field("currency", v.strip().upper()[:3]), key="f_currency")
        foreign = foreign_currency(d)
        acc = account(d.get("source_id"))
        if foreign and acc:
            ui.input(label="Cost in " + acc["currency"], value=d.get("account_amount", ""), kind="number",
                     on_change=lambda v: set_field("account_amount", v), key="f_account_amount")
            ui.caption(f"The receipt is in {foreign}; Firefly III books {acc['name']} in {acc['currency']}.")
        ui.date(label="Date", value=d.get("date"), on_change=lambda v: set_field("date", v or time.time()), key="f_date")
        if saved.accounts:
            ui.select([(a["id"], a["name"]) for a in saved.accounts], value=d.get("source_id"), label="Paid from",
                      on_change=lambda v: set_field("source_id", v), key="f_source")
        else:
            ui.caption("Accounts load when Firefly III can be reached. You can keep this for later meanwhile.")
        ui.input(label="Paid to", value=d.get("destination", ""), placeholder=d.get("description") or "Shop",
                 on_change=lambda v: set_field("destination", v), key="f_dest")
        cats = options(saved.categories, "No category") + [("__new", "New category…")]
        current = "__new" if d.get("category") else (d.get("category_id") or "")
        ui.select(cats, value=current, label="Category", on_change=set_category, key="f_category")
        if current == "__new":
            ui.input(label="New category", value=d.get("category", "").strip(),
                     on_change=lambda v: set_field("category", v or " "), key="f_new_category")
        if saved.budgets:
            ui.select(options(saved.budgets, "No budget"), value=d.get("budget_id") or "", label="Budget",
                      on_change=lambda v: set_field("budget_id", v), key="f_budget")
        items = d.get("items") or []
        if items:
            with ui.section(f"{len(items)} items on the receipt", collapsible=True, open=False):
                ui.list([ui.item(i["name"], trailing=firefly.money(i["amount"])) for i in items])
            total = number(d.get("amount")) or 0
            if firefly.can_split(items, total):
                ui.toggle("One entry per item", value=bool(d.get("split")),
                          on_change=lambda v: set_field("split", v), key="f_split")
            else:
                ui.caption("The items add up to more than the amount, so they go in the notes.")
        ui.input(label="Notes", value=d.get("notes", ""), multiline=True,
                 on_change=lambda v: set_field("notes", v), key="f_notes")
        with ui.row():
            ui.button("Send", icon="send", primary=True, on_click=send_draft, key="f_send", enabled=not state.sending)
            ui.button("Later", icon="schedule", on_click=keep_draft, key="f_later")
        ui.button("Discard", color="danger", on_click=discard_draft, key="f_discard")


def pick_page():
    p = state.picking
    if p is None:
        ui.empty("Nothing to change.", icon="check")
        return
    rows = saved.categories if p["kind"] == "category" else saved.budgets
    q = state.pick_filter.strip().lower()
    shown = [r for r in rows if q in r["name"].lower()][:100]
    with ui.column():
        ui.search(placeholder="Find", value=state.pick_filter,
                  on_change=lambda v: setattr(state, "pick_filter", v), key="pick_search")
        ui.list([ui.item(r["name"], key="pick" + r["id"], on_click=bind(picked, r["id"])) for r in shown],
                empty="None found. Add it in Firefly III first.")
