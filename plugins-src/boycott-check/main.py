# Boycott Check: is a brand on a boycott list, and why?
#
# Two lists, both cited on every result:
# - Tech for Palestine's boycott dataset on GitHub (brands, owners, reasons,
#   each with its own source links, and alternatives). Downloaded once, kept
#   on the phone in storage, and checked for a newer version once a week.
# - The BDS movement's own priority targets, in bds_targets.py.
# Barcodes go through Open Food Facts for the product's brand and owner.
# Photos go through the keyboard's text recognition, so only printed names
# can be matched: there is no logo or image search.

from wm import plugin, ui, http, storage, scan, share
import re
import time

import bds_targets
import match

REPO = "TechForPalestine/boycott-israeli-consumer-goods-dataset"
REPO_URL = "https://github.com/" + REPO
DATA_PATH = "output/json/data.json"
COMMITS_URL = "https://api.github.com/repos/" + REPO + "/commits"
RAW_URL = "https://raw.githubusercontent.com/" + REPO + "/"
OFF_API = "https://world.openfoodfacts.org/api/v2/product/"
OFF_PAGE = "https://world.openfoodfacts.org/product/"
OFF_FIELDS = "code,product_name,brands,brand_owner,origins,origins_tags,manufacturing_places,manufacturing_places_tags"
GS1_PREFIXES = "https://www.gs1.org/standards/id-keys/company-prefix"
WEEK = 7 * 86400
RECENT_MAX = 12

state = plugin.state(query="", busy=None, error=None, entry=None, product=None, photo=None)
saved = plugin.state(persist=True, key="recent", recent=[])

INDEX = [None]
SHARDS = {}


# MARK: - the stored list

# Bump when what build() stores changes shape: a list kept in an older
# shape is then treated as not downloaded.
FORMAT = 1


def meta():
    m = storage.get("tfp:meta")
    return m if m and m.get("format") == FORMAT else None


def load_index():
    idx = match.Index()
    m = meta()
    if m:
        for i in range(m.get("index", 0)):
            idx.add_tfp(storage.get("tfp:i:" + str(i)) or [])
    idx.add_bds(bds_targets.TARGETS)
    INDEX[0] = idx
    SHARDS.clear()


def index():
    if INDEX[0] is None:
        load_index()
    return INDEX[0]


def record(e):
    """The full Tech for Palestine record behind an index entry, or None."""
    shard = e.get("shard")
    if shard not in SHARDS:
        SHARDS[shard] = storage.get("tfp:s:" + str(shard)) or []
    for rec in SHARDS[shard]:
        if rec["id"] == e["id"] and rec["k"] == e["kind"]:
            return rec
    return None


def problem(error):
    if isinstance(error, ConnectionError):
        return "No connection, or Data saver is on."
    if isinstance(error, TimeoutError):
        return "No answer in time. Try again in a moment."
    return str(error) or "Something went wrong."


def failed(error):
    state.busy = None
    state.error = problem(error)


def check_for_update(force=False, quiet=False):
    """Ask GitHub for the dataset's latest commit; download only when it
    differs from the one kept. [force] downloads even when GitHub can't say."""
    if state.busy:
        return
    state.busy = "Checking for a newer list…"
    state.error = None
    http.get(COMMITS_URL, params={"path": DATA_PATH, "per_page": "1"},
             headers={"Accept": "application/vnd.github+json"},
             then=lambda r: got_commit(r, force, quiet),
             on_error=lambda e: got_commit(None, force, quiet))


def got_commit(r, force, quiet):
    sha = None
    date = None
    if r is not None and r.ok:
        try:
            latest = r.json()[0]
            sha = str(latest["sha"])
            date = str(latest["commit"]["committer"]["date"])[:10]
        except Exception:
            sha = None
    m = meta()
    if m and (m.get("sha") == sha or (sha is None and not force)):
        m["checked"] = time.time()
        storage["tfp:meta"] = m
        state.busy = None
        if not quiet:
            ui.toast("The list is up to date." if sha else "Couldn't reach GitHub; kept the list you have.")
        return
    download(sha or "main", date or (m or {}).get("date"), quiet)


def download(ref, date, quiet):
    state.busy = "Downloading the list…"
    http.get(RAW_URL + ref + "/" + DATA_PATH,
             then=lambda r: got_data(r, ref, date, quiet), on_error=failed)


def got_data(r, ref, date, quiet):
    if not r.ok:
        failed(RuntimeError("GitHub answered " + str(r.status_code) + " for the list."))
        return
    try:
        idx_chunks, shards, counts = match.build(r.json())
    except Exception as error:
        failed(RuntimeError("The list could not be read: " + str(error)))
        return
    if counts["brands"] == 0:
        failed(RuntimeError("The list came back empty; kept the one you have."))
        return
    old = storage.get("tfp:meta") or {}
    try:
        for i, shard in enumerate(shards):
            storage["tfp:s:" + str(i)] = shard
        for i, rows in enumerate(idx_chunks):
            storage["tfp:i:" + str(i)] = rows
        for i in range(len(shards), old.get("shards", 0)):
            storage.remove("tfp:s:" + str(i))
        for i in range(len(idx_chunks), old.get("index", 0)):
            storage.remove("tfp:i:" + str(i))
        storage["tfp:meta"] = {"format": FORMAT, "sha": None if ref == "main" else ref, "date": date, "checked": time.time(),
                               "shards": len(shards), "index": len(idx_chunks), "counts": counts}
    except ValueError as error:
        failed(RuntimeError("Not enough plugin storage for the list: " + str(error)))
        return
    load_index()
    state.busy = None
    if not quiet:
        ui.toast("List updated: " + str(counts["brands"]) + " brands.")


# MARK: - looking things up

def set_query(text):
    state.query = text or ""


def open_entry(at):
    e = index().entries[at]
    state.entry = at
    remember({"t": "entry", "src": e["src"], "id": e["id"], "name": e["name"]})
    plugin.push(entry_page, title=e["name"])


def remember(item):
    same = [r for r in saved.recent
            if r.get("t") == item["t"] and r.get("id") == item.get("id") and r.get("src") == item.get("src")
            and r.get("code") == item.get("code")]
    rest = [r for r in saved.recent if r not in same]
    saved.recent = ([item] + rest)[:RECENT_MAX]


def open_recent(item):
    if item["t"] == "product":
        look_up_product(item["code"])
        return
    at = index().locate(item["src"], item["id"])
    if at is None:
        ui.toast("That entry is no longer on the list.")
        return
    open_entry(at)


def scan_barcode():
    state.error = None
    scan.barcode(then=got_code, on_error=failed)


def got_code(code):
    if code is None:
        return
    digits = str(code).strip()
    if not re.fullmatch(r"\d{6,14}", digits):
        state.error = "That code isn't a product barcode."
        return
    look_up_product(digits)


def look_up_product(code):
    state.busy = "Looking up " + code + "…"
    state.error = None
    http.get(OFF_API + code + ".json", params={"fields": OFF_FIELDS},
             then=lambda r: got_product(r, code), on_error=failed)


def got_product(r, code):
    state.busy = None
    product = None
    if r.ok or r.status_code == 404:
        try:
            body = r.json()
            if body.get("product") and body.get("status") in (1, "success", None):
                product = body["product"]
        except Exception:
            product = None
    elif r.status_code >= 500 or r.status_code == 429:
        state.error = "Open Food Facts is busy (" + str(r.status_code) + "). Try again in a moment."
        return
    state.product = {"code": code, "found": product is not None, "p": product or {}}
    name = (product or {}).get("product_name") or code
    remember({"t": "product", "code": code, "name": name})
    plugin.push(product_page, title=name)


def read_label():
    state.error = None
    scan.text(then=got_text, on_error=failed)


def got_text(text):
    if text is None:
        return
    found = match.names_in_text(index(), text)
    state.photo = {"text": str(text), "found": [[at, words] for at, words in found]}
    plugin.push(photo_page, title="From the photo")


# MARK: - drawing

def verdict(e):
    if e["src"] == "bds":
        tier = e["tier"]
        if tier == "consumer":
            return "BDS consumer boycott target", "danger"
        if tier == "organic":
            return "Grassroots boycott the BDS movement supports", "danger"
        return "BDS pressure target", "warning"
    if e["status"] == "avoid":
        return "Boycott: on Tech for Palestine's list", "danger"
    if e["status"] == "support":
        return "Alternative: Tech for Palestine lists it to support", "success"
    return "Neutral on Tech for Palestine's list", "muted"


def entry_item(at, note=None):
    e = index().entries[at]
    text, color = verdict(e)
    company = e["kind"] == "company"
    return ui.item(e["name"], subtitle=text + (" · company" if company else "") + (" · " + note if note else ""),
                   icon="block" if color == "danger" else ("verified" if color == "success" else "help"),
                   on_click=lambda at=at: open_entry(at),
                   key="entry:" + e["src"] + ":" + e["id"] + (":company" if company else ""))


def link_items(urls, key, prefix=""):
    """Rows that open each link. Keys are short: the panel cuts long ids."""
    items = []
    for n, url in enumerate(urls):
        host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        label = prefix + str(n + 1) + ". " + host if prefix is not None else host
        if url.startswith("https://"):
            items.append(ui.item(label, subtitle=url, icon="open_in_new",
                                 on_click=lambda url=url: share.open(url), key="link:" + key + ":" + str(n)))
        else:
            # share.open takes https only; an old http source can still be handed on.
            items.append(ui.item(label, subtitle=url + " (not https: tap to share the link)", icon="share",
                                 on_click=lambda url=url: share.text(url), key="link:" + key + ":" + str(n)))
    return items


def owner_items(idx, owners, me):
    items = []
    for o in owners:
        at = idx.locate("tfp", o)
        if at is None:
            found = [f for f in idx.find(match.owner_name(o)) if idx.entries[f]["src"] == "tfp"]
            at = found[0] if found else None
        if at is None or at in me:
            items.append(ui.item(match.owner_name(o), subtitle="Owner, not listed separately", icon="domain"))
        else:
            items.append(entry_item(at, "owner"))
    return items


def tfp_card(e, me=()):
    rec = record(e)
    text, color = verdict(e)
    idx = index()
    m = meta() or {}
    with ui.card(title="Tech for Palestine" + (" (company)" if e["kind"] == "company" else "")):
        ui.label(text, color=color)
        if rec is None:
            ui.caption("The details aren't on the phone. Update the list from the header.")
            return
        if rec.get("r"):
            ui.markdown("\n".join(["- " + match.REASONS.get(r, r.replace("_", " ")) for r in rec["r"]]))
        if rec.get("o"):
            ui.caption("Owned by")
            ui.list(owner_items(idx, rec["o"], me))
        body, sources = match.split_sources(rec.get("d") or "")
        if body:
            ui.markdown(body)
        if sources:
            ui.caption("Sources")
            ui.list(link_items(sources, e["kind"][0] + ":" + e["id"][:40]))
        alts = []
        for a in rec.get("a") or []:
            at = idx.locate("tfp", a)
            if at is not None:
                alts.append(entry_item(at))
        if alts or rec.get("at"):
            ui.caption("Alternatives")
            if alts:
                ui.list(alts)
            if rec.get("at"):
                ui.markdown(rec["at"])
        ui.caption("From Tech for Palestine's boycott dataset" +
                   (", last changed " + m["date"] if m.get("date") else "") + ".")
        ui.list([ui.item("The dataset on GitHub", subtitle=REPO_URL, icon="open_in_new",
                         on_click=lambda: share.open(REPO_URL), key="link:dataset")])


def bds_card(e):
    t = e["target"]
    text, color = verdict(e)
    with ui.card(title="BDS movement"):
        ui.label(text, color=color)
        if t["aliases"]:
            ui.caption("Also: " + ", ".join(t["aliases"]))
        ui.label(t["reason"])
        ui.list(link_items(t["links"], "bds:" + e["id"]))
        ui.caption("From the BDS National Committee's boycott guide, as read on " + bds_targets.CHECKED + ".")


def entry_page():
    idx = index()
    if state.entry is None or state.entry >= len(idx.entries):
        ui.label("Nothing to show.")
        return
    shown = idx.related(state.entry)
    with ui.column():
        for at in shown:
            e = idx.entries[at]
            if e["src"] == "tfp":
                tfp_card(e, shown)
            else:
                bds_card(e)


def product_page():
    pr = state.product or {}
    code = pr.get("code", "")
    p = pr.get("p") or {}
    idx = index()
    with ui.column():
        if not pr.get("found"):
            ui.title(code)
            ui.label("Open Food Facts doesn't know this barcode yet. Search for the brand by name instead.")
            ui.button("Add it on Open Food Facts", icon="add", on_click=lambda: share.open(OFF_PAGE + code), key="off-add")
        else:
            brands = [n for n, where in match.brand_names(p) if where == "brand"]
            owner = str(p.get("brand_owner") or "").strip()
            if brands or owner:
                ui.caption(("Brand: " + ", ".join(brands) if brands else "") +
                           (" · " if brands and owner else "") + ("Owner: " + owner if owner else ""))
            else:
                ui.caption("Open Food Facts has no brand for this product.")
            found = match.match_product(idx, p)
            israel = match.made_in_israel(p)
            direct = [f for f in found if f["how"] in ("brand", "owner")]
            listed = [f for f in direct if idx.entries[f["at"]]["status"] == "avoid"]
            if listed or israel:
                ui.label("On a boycott list", color="danger")
            elif found:
                ui.label("Not listed itself, but related names are", color="warning")
            else:
                ui.label("Not on these lists", color="success")
                ui.caption("Not being listed doesn't mean a company has no ties: the lists are not complete.")
            notes = {"brand": "brand", "owner": "this product's owner", "owner of": "same owner",
                     "partly": "similar name"}
            items = [entry_item(f["at"], notes[f["how"]] + " " + f["name"]) for f in found]
            if israel:
                at = idx.locate("bds", "israeli-produce")
                items.append(entry_item(at, "Open Food Facts gives Israel as its " + " and ".join(israel)))
            if items:
                ui.list(items)
            if any([f["how"] == "partly" for f in found]):
                ui.caption("A similar name only shares the start of the brand's name, so check the owner before you decide.")
            ui.button("Open on Open Food Facts", icon="open_in_new", on_click=lambda: share.open(OFF_PAGE + code), key="off-open")
        if code.startswith("729"):
            ui.caption("This barcode starts with 729, the prefix GS1 Israel gives out. It says where the barcode "
                       "was registered, which isn't always where the product was made.")
            ui.list([ui.item("GS1 company prefixes", subtitle=GS1_PREFIXES, icon="open_in_new",
                             on_click=lambda: share.open(GS1_PREFIXES), key="link:gs1")])


def photo_page():
    ph = state.photo or {"text": "", "found": []}
    with ui.column():
        if ph["found"]:
            ui.label("Listed names in the text the camera read:")
            ui.list([entry_item(at, "read as \"" + w + "\"") for at, w in ph["found"]])
            ui.caption("These are names that match words on the label. Open one to check it is the same company.")
        else:
            ui.label("No listed name in the text the camera read.")
        ui.caption("The camera reads printed words only. A logo without a readable name can't be "
                   "recognised, so type the name in the search box if nothing matched.")
        ui.section("Text read", ui.label(ph["text"] or "(none)"), collapsible=True, open=False, key="text-read")


def about_page():
    m = meta()
    with ui.column():
        ui.markdown("**Where the answers come from**")
        if m:
            c = m.get("counts") or {}
            ui.label("Tech for Palestine's boycott dataset: " + str(c.get("brands", 0)) + " brands (" +
                     str(c.get("flagged", 0)) + " to boycott) and " + str(c.get("companies", 0)) +
                     " companies" + (", last changed " + m["date"] if m.get("date") else "") +
                     ". Checked " + time.format("d MMM yyyy", m.get("checked") or time.time()) + ".")
        else:
            ui.label("Tech for Palestine's boycott dataset: not downloaded yet.")
        ui.label("The BDS movement's own boycott targets: " + str(len(bds_targets.TARGETS)) +
                 " companies, as read on " + bds_targets.CHECKED + ".")
        ui.label("Product names, brands and owners: Open Food Facts.")
        ui.list(link_items([REPO_URL, bds_targets.GUIDE, "https://world.openfoodfacts.org"], "about", prefix=None))
        ui.caption("The plugin shows what these lists say and links to their sources; it adds nothing of its "
                   "own. Being absent from them doesn't mean a company has no ties.")
        ui.caption("Photos: the keyboard reads printed text. Logos without a readable name can't be recognised.")


def render():
    idx = index()
    m = meta()
    with ui.column():
        ui.search(placeholder="Brand or company", value=state.query, on_change=set_query,
                  on_submit=set_query, key="query")
        with ui.row():
            ui.button("Scan barcode", icon="barcode_scanner", primary=True, on_click=scan_barcode, key="scan")
            ui.button("Read a label", icon="document_scanner", on_click=read_label, key="read")
        if state.busy:
            ui.progress()
            ui.caption(state.busy)
        if state.error:
            ui.label(state.error, color="danger")
        if state.query.strip():
            hits = idx.search(state.query)
            ui.list([entry_item(at) for at in hits],
                    empty="Not on these lists." + ("" if m else " Download the full list for more."),
                    key="results")
            return
        if not m and not state.busy:
            with ui.card(title="Get the full list"):
                ui.label("Tech for Palestine's dataset has about 880 brands with the reasons and sources for each. "
                         "It downloads once (about 0.8 MB) and then works offline.")
                ui.button("Download the list", icon="download", primary=True,
                          on_click=lambda: check_for_update(force=True), key="download")
                ui.caption("Until then, search covers the BDS movement's " + str(len(bds_targets.TARGETS)) +
                           " priority targets.")
        if saved.recent:
            ui.caption("Recent")
            ui.list([ui.item(r.get("name") or r.get("code") or "?",
                             subtitle="Barcode " + r["code"] if r["t"] == "product" else None,
                             icon="barcode" if r["t"] == "product" else "history",
                             on_click=lambda r=r: open_recent(r), key="recent:" + str(i))
                     for i, r in enumerate(saved.recent)])
        else:
            ui.empty("Scan a product's barcode, read its label, or type a brand.", icon="remove_shopping_cart")


@plugin.on_open
def opened():
    m = meta()
    if m and plugin.settings.get("auto_update", True) and time.time() - (m.get("checked") or 0) > WEEK:
        check_for_update(quiet=True)


@plugin.command("Update list", icon="sync", id="update")
def update_now():
    check_for_update(force=True)


@plugin.command("Sources", icon="info", id="about")
def show_about():
    plugin.push(about_page, title="Sources")


@plugin.keyword("boycott")
def from_keyword(text):
    state.query = text or ""


load_index()
