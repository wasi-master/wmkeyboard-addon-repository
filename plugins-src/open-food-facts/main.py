# Open Food Facts for WM Keyboard: scan a barcode or type a name, and see
# what the open databases know about the product. Signed in, add what is
# missing: the name, the ingredients read off the pack with the camera, and
# photos. Everything the databases say stays theirs (ODbL, photos CC BY-SA),
# so every screen names them and links to the product's page.

import json
import time
import uuid

from wm import plugin, ui, http, storage, secrets, scan, files, share, _

import off

LC = off.language_of(plugin.locale)
HISTORY_KEY = "history"
ACCOUNT_KEY = "account"
SIGN_UP_URL = "https://world.openfoodfacts.org/cgi/user.pl"

state = plugin.state(
    query="",
    busy=None,
    error=None,
    results=None,
    product=None,
    image=None,
    image_code=None,
    missing_code=None,
    form=None,
    photos={},
    notice=None,
    login_user="",
    login_password="",
    login_error=None,
)

# Language codes offered for the text on a pack, with the user's own first.
PACK_LANGUAGES = [
    ("en", "English"), ("fr", "French"), ("de", "German"), ("es", "Spanish"), ("it", "Italian"),
    ("nl", "Dutch"), ("pt", "Portuguese"), ("pl", "Polish"), ("tr", "Turkish"), ("ru", "Russian"),
    ("ar", "Arabic"), ("bn", "Bengali"), ("hi", "Hindi"), ("ur", "Urdu"), ("id", "Indonesian"),
    ("ja", "Japanese"), ("zh", "Chinese"), ("ko", "Korean"), ("th", "Thai"), ("vi", "Vietnamese"),
]

PHOTO_NAMES = {"front": "Front", "ingredients": "Ingredients", "nutrition": "Nutrition facts", "packaging": "Packaging"}

NUTRISCORE_WORDS = {"a": "Very good", "b": "Good", "c": "Average", "d": "Poor", "e": "Bad"}
NOVA_WORDS = {1: "Unprocessed", 2: "Culinary ingredient", 3: "Processed", 4: "Ultra-processed"}
GREENSCORE_WORDS = {"a-plus": "Very low impact", "a": "Very low impact", "b": "Low impact", "c": "Moderate impact",
                    "d": "High impact", "e": "Very high impact", "f": "Very high impact"}
LEVEL_WORDS = {"low": "Low", "moderate": "Moderate", "high": "High"}


# MARK: - settings, account, history

def flag(key, default):
    """A switch setting. The keyboard gives True or False; a value written
    as text ("false") is read the same way."""
    value = plugin.settings.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


def everywhere():
    return flag("everywhere", True)


def test_server():
    return flag("test_server", False)


def history_size():
    try:
        return max(5, min(200, int(plugin.settings.get("history", 50))))
    except Exception:
        return 50


def account():
    """{"user", "password"} from the encrypted secrets, or None."""
    raw = secrets.get(ACCOUNT_KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not data.get("user") or not data.get("password"):
        return None
    return data


def app_info():
    """Who the edit comes from, as Open Food Facts asks apps to say. The id is
    random and stays on the phone: moderators can tell this phone's edits
    apart without knowing who it is."""
    app_id = storage.get("app_uuid")
    if not app_id:
        app_id = uuid.uuid4().hex
        storage["app_uuid"] = app_id
    return {"app_name": "WM Keyboard", "app_version": plugin.version, "app_uuid": app_id}


def history():
    return storage.get(HISTORY_KEY, [])


def remember(info):
    """Puts [info] first in the history and keeps a copy to open offline."""
    entries = [e for e in history() if e.get("code") != info["code"]]
    entries.insert(0, {"code": info["code"], "name": info["name"], "brands": info["brands"],
                       "nutriscore": info["nutriscore"], "db": info["db"], "time": int(time.time())})
    dropped = entries[history_size():]
    entries = entries[:history_size()]
    try:
        for e in dropped:
            storage.pop("p:" + e["code"], None)
        storage[HISTORY_KEY] = entries
        storage["p:" + info["code"]] = info
    except ValueError:
        # Over the storage quota: keep the list, drop the copies.
        for key in list(storage.keys()):
            if key.startswith("p:"):
                del storage[key]
        try:
            storage[HISTORY_KEY] = entries
        except ValueError:
            pass


def forget(code):
    storage[HISTORY_KEY] = [e for e in history() if e.get("code") != code]
    storage.pop("p:" + code, None)


# MARK: - errors and waiting

def friendly(error):
    if isinstance(error, (off.OffError, off.NotABarcode)):
        return str(error)
    if isinstance(error, PermissionError):
        text = str(error)
        if "Open Food Facts" in text:
            return text
        if "files" in text:
            return _("Allow Files for this plugin on its page to add photos.")
        return _("Allow internet access for this plugin on its page, then try again.")
    if isinstance(error, TimeoutError):
        return _("Open Food Facts took too long to answer. Try again.")
    if isinstance(error, ConnectionError):
        return _("Could not reach Open Food Facts: {why}", why=str(error))
    return str(error)


def failed(error):
    state.busy = None
    state.error = friendly(error)


def working(text):
    state.busy = text
    state.error = None
    state.notice = None


# MARK: - looking things up

def submit(text):
    text = str(text or "").strip()
    state.query = text
    if not text:
        return
    code = off.clean_code(text)
    if code:
        look_up(code)
    else:
        find(text)


def scan_barcode():
    state.error = None
    scan.barcode(then=scanned, on_error=failed)


def scanned(text):
    if text is None:
        return
    code = off.clean_code(text)
    if code is None:
        state.error = _("That code is not a product barcode: {what}", what=str(text)[:60])
        return
    state.query = code
    look_up(code)


def look_up(code, push=True):
    working(_("Looking up {code}…", code=code))
    off.lookup(code, then=lambda info: looked_up(code, info, push), on_error=failed, lc=LC, everywhere=everywhere())


def looked_up(code, info, push):
    state.busy = None
    if info is None:
        state.missing_code = code
        plugin.push(render_missing, title=_("Not found"))
        return
    show(info, push)


def show(info, push=True):
    state.product = info
    state.results = None
    remember(info)
    fetch_image(info)
    if push:
        plugin.push(render_product, title=short(info["name"]) or info["code"])


def short(text, n=28):
    text = str(text or "")
    return text if len(text) <= n else text[:n - 1] + "…"


def fetch_image(info):
    if not info.get("image"):
        state.image, state.image_code = None, None
        return
    if state.image_code == info["code"] and state.image is not None:
        return
    state.image, state.image_code = None, info["code"]
    http.get(info["image"], binary=True, then=lambda r: got_image(info["code"], r), on_error=lambda e: None)


def got_image(code, r):
    if r.ok and state.image_code == code:
        state.image = r.content


def find(text):
    working(_("Searching…"))
    off.search(text, then=found, on_error=failed, lc=LC)


def found(results):
    state.busy = None
    state.results = results


def open_code(code):
    """A row in the history or the results: the saved copy when there is one."""
    cached = storage.get("p:" + code)
    if cached:
        show(cached)
    else:
        look_up(code)


def reload():
    if state.product:
        look_up(state.product["code"], push=False)


# MARK: - the home page

def render():
    ui.search(placeholder=_("Barcode or product name"), value=state.query,
              on_change=lambda v: state.update(query=v), on_submit=submit, key="query")
    with ui.row():
        ui.button(_("Scan a barcode"), icon="barcode_scanner", primary=True, on_click=scan_barcode, key="scan")
        ui.button(_("Look up"), icon="search", on_click=lambda: submit(state.query), key="look_up")
    status()
    if state.results is not None:
        with ui.section(_("Results")):
            ui.list([ui.item(r["name"] or r["code"], subtitle=" · ".join([x for x in (r["brands"], r["quantity"]) if x]) or None,
                             trailing=nutriscore_chip(r["nutriscore"]), on_click=opener(r["code"]))
                     for r in state.results], empty=_("No products match. Try the barcode instead."), key="results")
    entries = history()
    if entries:
        with ui.section(_("Recent")):
            ui.list([ui.item(e["name"] or e["code"], subtitle=history_subtitle(e),
                             trailing=nutriscore_chip(e.get("nutriscore")),
                             on_click=opener(e["code"]),
                             actions={_("Remove"): forgetter(e["code"])})
                     for e in entries], key="history")
    elif state.results is None:
        ui.empty(_("Scan a product's barcode to see its Nutri-Score, ingredients, allergens and labels."), icon="barcode_scanner")
    ui.caption(_("Data from Open Food Facts and its sister databases, under the Open Database Licence."))


# Callbacks for one row or one photo kind. A function per value, rather than
# lambda x=x, so each keeps its own value on every interpreter version.
def opener(code):
    return lambda: open_code(code)


def forgetter(code):
    return lambda: forget(code)


def photographer(kind, start):
    return lambda: start(kind)


def status():
    if state.busy:
        ui.progress()
        ui.caption(state.busy)
    if state.error:
        ui.label(state.error, color="danger")
    if state.notice:
        ui.label(state.notice, color="success")


def nutriscore_chip(value):
    return ("Nutri-Score " + off.score_text(value)) if value else None


def history_subtitle(e):
    parts = [e["brands"]] if e.get("brands") else []
    if e.get("db") and e["db"] != "food":
        parts.append(off.database(e["db"])["name"])
    return " · ".join(parts) or e["code"]


# MARK: - a product

def render_product():
    p = state.product
    if p is None:
        ui.empty(_("Nothing to show."))
        return
    status()
    with ui.row(weights=[1, 2]):
        if state.image is not None and state.image_code == p["code"]:
            ui.image(state.image, alt=p["name"], height=120)
        else:
            ui.icon("image", size=48, color="muted")
        with ui.column():
            ui.title(p["name"] or _("A product with no name yet"))
            line = " · ".join([x for x in (p["brands"], p["quantity"]) if x])
            if line:
                ui.label(line)
            ui.caption(off.database(p["db"])["name"] + " · " + p["code"])

    if p["kind"] == "food" or p["nutriscore"] or p["nova"] or p["greenscore"]:
        with ui.grid(columns=3):
            ui.stat(_("Nutri-Score"), off.score_text(p["nutriscore"]),
                    caption=_(NUTRISCORE_WORDS[p["nutriscore"]]) if p["nutriscore"] in NUTRISCORE_WORDS else _("Not computed"))
            ui.stat(_("NOVA"), str(p["nova"]) if p["nova"] else "?",
                    caption=_(NOVA_WORDS[p["nova"]]) if p["nova"] in NOVA_WORDS else _("Not computed"))
            ui.stat(_("Green-Score"), off.score_text(p["greenscore"]),
                    caption=_(GREENSCORE_WORDS[p["greenscore"]]) if p["greenscore"] in GREENSCORE_WORDS else _("Not computed"))

    if p["kind"] in ("food", "petfood") or p["vegan"] or p["palm_oil"]:
        with ui.section(_("Diet")):
            ui.list([
                ui.item(_("Vegan"), icon="eco", trailing=answer(p["vegan"])),
                ui.item(_("Vegetarian"), icon="egg_alt", trailing=answer(p["vegetarian"])),
                ui.item(_("Palm oil"), icon="water_drop", trailing=palm_answer(p["palm_oil"])),
            ], key="diet")
            if not p["ingredients"]:
                ui.caption(_("Worked out from the ingredients, which this product does not list yet."))

    if p["flags"] or p["labels"]:
        with ui.section(_("Labels")):
            if p["flags"]:
                ui.list([ui.item(_(f["name"]), icon="verified") for f in p["flags"]], key="flags")
            others = [l for l in p["labels"] if l.lower() not in [f["name"].lower() for f in p["flags"]]]
            if others:
                ui.caption(", ".join(others))

    with ui.section(_("Allergens")):
        if p["allergens"]:
            ui.label(_("Contains: {list}", list=", ".join(p["allergens"])), color="warning")
        elif p["ingredients"]:
            ui.label(_("None listed."))
        else:
            ui.label(_("Not known until the ingredients are added."), color="muted")
        if p["traces"]:
            ui.label(_("May contain: {list}", list=", ".join(p["traces"])))

    with ui.section(_("Ingredients"), collapsible=True, open=bool(p["ingredients"]), key="ingredients"):
        if p["ingredients"]:
            ui.text(p["ingredients"])
        else:
            ui.label(_("Not added yet."), color="muted")
        if p["additives"]:
            ui.caption(_("Additives: {list}", list=", ".join(p["additives"])))

    if p["nutrition"]:
        with ui.section(_("Nutrition per 100 g or 100 ml"), collapsible=True, open=False, key="nutrition"):
            ui.list([ui.item(_(n["name"]), subtitle=_(LEVEL_WORDS[n["level"]]) if n["level"] in LEVEL_WORDS else None,
                             trailing=number(n["value"]) + " " + n["unit"]) for n in p["nutrition"]], key="nutrients")

    if p["missing"]:
        with ui.card(title=_("Help complete this product")):
            ui.label(_("Missing: {list}", list=", ".join([_(missing_name(m)) for m in p["missing"]])))
            ui.button(_("Add what's missing"), icon="edit", primary=True, on_click=lambda: open_editor(p), key="complete")

    with ui.section(_("Share"), collapsible=True, open=False, key="share"):
        ui.output(off.summary(p), key="summary")

    with ui.row():
        ui.button(_("Open the page"), icon="open_in_new", on_click=lambda: share.open(p["url"]), key="open_page")
        ui.button(_("Edit"), icon="edit", on_click=lambda: open_editor(p), key="edit")
        ui.button(_("Reload"), icon="refresh", on_click=reload, key="reload")
    ui.caption(_("From {db}, under the Open Database Licence. Photos under CC BY-SA.", db=off.database(p["db"])["name"]))


def answer(value):
    return {"yes": _("Yes"), "no": _("No"), "maybe": _("Maybe")}.get(value, _("Unknown"))


def palm_answer(value):
    return {"yes": _("Contains it"), "no": _("None"), "maybe": _("Maybe")}.get(value, _("Unknown"))


def missing_name(key):
    return {"name": "name", "ingredients": "ingredients", "front": "front photo", "nutrition": "nutrition facts"}.get(key, key)


def number(value):
    if value == int(value):
        return str(int(value))
    text = str(round(value, 2))
    return text


# MARK: - not found

def render_missing():
    code = state.missing_code or ""
    where = _("Open Food Facts and its sister databases") if everywhere() else _("Open Food Facts")
    ui.empty(_("{code} is not in {where} yet.", code=code, where=where), icon="search_off")
    ui.label(_("You can add it: a name, the ingredients and a photo of the front take a minute."))
    ui.button(_("Add this product"), icon="add", primary=True, on_click=lambda: open_editor(None, code), key="add")


# MARK: - adding and editing

def open_editor(info, code=None):
    """The form for [info], or for a new product with [code]."""
    if info is None:
        state.form = {"code": code, "db": "food", "new": True, "name": "", "brands": "", "quantity": "",
                      "ingredients": "", "lc": LC, "was": {}}
    else:
        was = {"name": info["name"], "brands": info["brands"], "quantity": info["quantity"], "ingredients": info["ingredients"]}
        state.form = {"code": info["code"], "db": info["db"], "new": False, "lc": LC, "was": was,
                      "name": info["name"], "brands": info["brands"], "quantity": info["quantity"],
                      "ingredients": info["ingredients"]}
    state.photos = {}
    state.notice = None
    state.error = None
    plugin.push(render_edit, title=_("Add a product") if info is None else _("Improve"))


def set_form(field, value):
    state.form[field] = value


def render_edit():
    f = state.form
    if f is None:
        ui.empty(_("Nothing to edit."))
        return
    acct = account()
    status()
    if acct is None:
        with ui.card(title=_("Sign in first")):
            ui.label(_("Changes go to Open Food Facts under your own account."))
            ui.button(_("Sign in"), icon="login", primary=True, on_click=open_account, key="sign_in_first")
    elif test_server():
        ui.caption(_("Sending to the test server, world.openfoodfacts.net. Nothing reaches the real database."))
    ui.caption(f["code"])
    if f["new"]:
        ui.select([(db["key"], db["name"]) for db in off.DATABASES], value=f["db"],
                  on_change=lambda v: set_form("db", v), label=_("Which database"), key="db")
    ui.select(pack_languages(), value=f["lc"], on_change=lambda v: set_form("lc", v),
              label=_("Language on the pack"), key="lc")
    ui.input(label=_("Name"), value=f["name"], on_change=lambda v: set_form("name", v), key="name")
    ui.input(label=_("Brand"), value=f["brands"], on_change=lambda v: set_form("brands", v), key="brands")
    ui.input(label=_("Quantity"), value=f["quantity"], placeholder="400 g",
             on_change=lambda v: set_form("quantity", v), key="quantity")
    ui.input(label=_("Ingredients"), value=f["ingredients"], multiline=True,
             on_change=lambda v: set_form("ingredients", v), key="ingredients_text")
    ui.button(_("Read the ingredients with the camera"), icon="document_scanner", on_click=read_ingredients, key="ocr")
    ui.caption(_("Check what the camera read before saving, and keep the words as the pack writes them."))
    ui.button(_("Save"), icon="cloud_upload", primary=True, enabled=acct is not None, on_click=save_form, key="save")

    with ui.section(_("Photos")):
        for kind in ("front", "ingredients", "nutrition"):
            with ui.row(weights=[2, 1, 1]):
                ui.label(_(PHOTO_NAMES[kind]) + photo_state(kind))
                ui.button(_("Camera"), icon="photo_camera", enabled=acct is not None,
                          on_click=photographer(kind, take_photo), key="camera_" + kind)
                ui.button(_("Files"), icon="image", enabled=acct is not None,
                          on_click=photographer(kind, pick_photo), key="pick_" + kind)
    ui.caption(_("What you send is published under your user name, the text under the Open Database Licence and photos under CC BY-SA."))


def pack_languages():
    """The languages to pick from, with the user's own first even when it is
    not in the list."""
    known = [pair[0] for pair in PACK_LANGUAGES]
    out = [] if LC in known else [(LC, LC)]
    return out + PACK_LANGUAGES


def photo_state(kind):
    s = state.photos.get(kind)
    return (" · " + s) if s else ""


def read_ingredients():
    state.error = None
    scan.text(then=read_text, on_error=failed)


def read_text(text):
    if not text:
        return
    state.form["ingredients"] = tidy_ingredients(text)


def tidy_ingredients(text):
    """OCR text as one paragraph, without the "Ingredients:" heading."""
    flat = " ".join([line.strip() for line in str(text).replace("\r", "\n").split("\n") if line.strip()])
    while "  " in flat:
        flat = flat.replace("  ", " ")
    flat = flat.replace("- ", "") if flat.count("- ") > 2 else flat
    low = flat.lower()
    for head in ("ingredients:", "ingredients :", "ingrédients :", "ingrédients:", "zutaten:", "ingredientes:", "ingredienti:"):
        if low.startswith(head):
            flat = flat[len(head):].strip()
            break
    return flat


def changes(f):
    """The form's fields that differ from the product, as the server names them."""
    lc = f["lc"] or LC
    was = f["was"]
    out = {}
    pairs = [("name", "product_name_" + lc), ("brands", "brands"), ("quantity", "quantity"),
             ("ingredients", "ingredients_text_" + lc)]
    for field, server_name in pairs:
        value = str(f[field] or "").strip()
        if value and value != str(was.get(field) or "").strip():
            out[server_name] = value
    if out and f["new"]:
        out["lang"] = lc
    if out:
        out["lc"] = lc
    return out


def save_form():
    f = state.form
    acct = account()
    if acct is None:
        open_account()
        return
    fields = changes(f)
    if not fields:
        ui.toast(_("Nothing has changed."))
        return
    working(_("Saving…"))
    off.save(f["code"], f["db"], fields, acct, app_info(), then=saved, on_error=failed, test=test_server())


def saved(ok):
    state.busy = None
    f = state.form
    for field in ("name", "brands", "quantity", "ingredients"):
        f["was"][field] = f[field]
    f["new"] = False
    if test_server():
        state.notice = _("Saved on the test server.")
        return
    state.notice = _("Saved. Thank you for adding to Open Food Facts!")
    off.lookup(f["code"], then=refreshed, on_error=lambda e: None, lc=LC, everywhere=everywhere())


def refreshed(info):
    if info is not None:
        state.product = info
        remember(info)
        fetch_image(info)


def take_photo(kind):
    state.error = None
    files.photo(then=lambda ph: got_photo(kind, ph), on_error=failed)


def pick_photo(kind):
    state.error = None
    files.pick(kind="image", then=lambda ph: got_photo(kind, ph), on_error=failed)


def got_photo(kind, photo):
    if photo is None:
        return
    acct = account()
    f = state.form
    if acct is None or f is None:
        return
    state.photos[kind] = _("sending…")
    off.upload_photo(f["code"], f["db"], kind, f["lc"] or LC, photo, acct, app_info(),
                     then=lambda imgid: photo_sent(kind), on_error=lambda e: photo_failed(kind, e), test=test_server())


def photo_sent(kind):
    state.photos[kind] = _("sent")
    state.form["new"] = False


def photo_failed(kind, error):
    state.photos[kind] = _("not sent")
    state.error = friendly(error)


# MARK: - the account

def open_account():
    state.login_error = None
    plugin.push(render_account, title=_("Account"))


def render_account():
    acct = account()
    if acct is not None:
        ui.label(_("Signed in as {user}.", user=acct["user"]))
        if test_server():
            ui.caption(_("Edits go to the test server, which has its own accounts."))
        ui.button(_("Sign out"), icon="logout", on_click=sign_out, key="sign_out")
        return
    ui.markdown(_("Sign in with your Open Food Facts account to add products, ingredients and photos. "
                  "The same account works on Open Beauty Facts and the others. "
                  "Your password stays on this phone, encrypted."))
    if test_server():
        ui.caption(_("The test server has its own accounts: sign up there first."))
    ui.input(label=_("User name"), value=state.login_user, placeholder=_("Not your email address"),
             on_change=lambda v: state.update(login_user=v), key="login_user")
    ui.input(label=_("Password"), value=state.login_password, kind="password",
             on_change=lambda v: state.update(login_password=v), on_submit=sign_in, key="login_password")
    if state.busy:
        ui.progress()
    if state.login_error:
        ui.label(state.login_error, color="danger")
    with ui.row():
        ui.button(_("Sign in"), icon="login", primary=True, on_click=sign_in, key="sign_in")
        ui.button(_("Create an account"), icon="person_add", on_click=sign_up, key="sign_up")


def sign_up():
    share.open(("https://" + off.TEST_HOST + "/cgi/user.pl") if test_server() else SIGN_UP_URL)


def sign_in(_value=None):
    user = str(state.login_user or "").strip()
    password = str(state.login_password or "")
    if not user or not password:
        state.login_error = _("Type your user name and password.")
        return
    if "@" in user:
        state.login_error = _("Use your user name, not your email address.")
        return
    state.busy = _("Signing in…")
    state.login_error = None
    off.check_login({"user": user, "password": password}, then=lambda ok: signed_in(user, password, ok),
                    on_error=login_failed, test=test_server())


def signed_in(user, password, ok):
    state.busy = None
    if not ok:
        state.login_error = _("That user name and password did not work.")
        return
    secrets.set(ACCOUNT_KEY, json.dumps({"user": user, "password": password}))
    state.login_password = ""
    ui.toast(_("Signed in as {user}.", user=user))
    plugin.back()


def login_failed(error):
    state.busy = None
    state.login_error = friendly(error)


def sign_out():
    secrets.remove(ACCOUNT_KEY)
    ui.toast(_("Signed out."))


# MARK: - header buttons and the @food chip

@plugin.command(_("Account"), icon="account_circle", id="account")
def account_command():
    open_account()


@plugin.command(_("Clear history"), icon="delete_sweep", id="clear_history")
def clear_command():
    ui.dialog(_("Clear history?"), _("The products you looked up are forgotten on this phone."),
              buttons=(_("Clear"), _("Cancel")), on_result=cleared)


def cleared(choice):
    if choice != _("Clear"):
        return
    for key in list(storage.keys()):
        if key.startswith("p:"):
            del storage[key]
    storage[HISTORY_KEY] = []


@plugin.keyword("food")
def keyword(text):
    submit(text)
