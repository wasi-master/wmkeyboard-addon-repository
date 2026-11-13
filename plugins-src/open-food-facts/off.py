"""Open Food Facts and its sister databases, for WM Keyboard plugins.

A small client with no user interface, so another plugin can copy this file
as it is. It needs the `network` permission and these hosts in plugin.json:

    "*.openfoodfacts.org", "*.openbeautyfacts.org",
    "*.openpetfoodfacts.org", "*.openproductsfacts.org"

(and "*.openfoodfacts.net" to send edits to the test server).

Every call takes then= and on_error= and returns at once, because the
keyboard draws nothing while a plugin waits:

    off.lookup("3017620422003", then=show, on_error=failed, lc="en")
    off.search("hazelnut spread", then=listed, on_error=failed)

Reads are limited to 15 a minute per phone (10 for searches), so look up on
a tap or a scan, never as the user types. The data is under the Open Database
Licence and photos under CC BY-SA: show "Open Food Facts" and a link to the
product's page wherever the data appears.
"""

import re

from wm import http

# The four databases share one server program, one barcode space and one
# account system. Asked with product_type=all, the food database sends a
# product of another kind on to its own database with a redirect.
DATABASES = [
    {"key": "food", "name": "Open Food Facts", "host": "world.openfoodfacts.org"},
    {"key": "beauty", "name": "Open Beauty Facts", "host": "world.openbeautyfacts.org"},
    {"key": "petfood", "name": "Open Pet Food Facts", "host": "world.openpetfoodfacts.org"},
    {"key": "product", "name": "Open Products Facts", "host": "world.openproductsfacts.org"},
]

# The staging server: its own accounts, data that is wiped now and then, and
# a fixed password on the whole site.
TEST_HOST = "world.openfoodfacts.net"
TEST_AUTH = "Basic b2ZmOm9mZg=="

SEARCH_URL = "https://search.openfoodfacts.org/search"

# 3.4: the Green-Score under its new name (environmental_score_*) and the
# nutrients still flat (fat_100g). 3.5 moves them somewhere still changing.
API = "/api/v3.4/product/"

FIELDS = [
    "code", "product_name", "brands", "quantity", "product_type", "lang",
    "image_front_small_url", "image_front_url", "image_ingredients_url", "image_nutrition_url",
    "nutriscore_grade", "nova_group", "environmental_score_grade",
    "ingredients_text", "allergens_tags", "traces_tags", "labels_tags", "additives_tags",
    "ingredients_analysis_tags", "nutriments", "nutrient_levels", "states_tags",
]
# Asked for again in the user's language: the server names the tags itself.
LOCAL_FIELDS = ["product_name", "ingredients_text"]
LOCAL_TAGS = ["allergens_tags", "traces_tags", "labels_tags", "additives_tags"]

NUTRIENTS = [
    ("energy-kcal", "Energy", "kcal"),
    ("fat", "Fat", "g"),
    ("saturated-fat", "Saturated fat", "g"),
    ("carbohydrates", "Carbohydrates", "g"),
    ("sugars", "Sugars", "g"),
    ("fiber", "Fibre", "g"),
    ("proteins", "Protein", "g"),
    ("salt", "Salt", "g"),
]

# Photos a product can have, as the image upload names them.
PHOTO_KINDS = ["front", "ingredients", "nutrition", "packaging"]


class OffError(Exception):
    """The server could not answer: busy, down, or it refused the request."""


class NotABarcode(ValueError):
    """The text is not a barcode the databases accept."""


# MARK: - addresses

def database(key):
    for db in DATABASES:
        if db["key"] == key:
            return db
    return DATABASES[0]


def database_of(url):
    """The database a reply came from, by the host it was sent from."""
    for db in DATABASES:
        if ("//" + db["host"]) in url:
            return db
    return DATABASES[0]


def product_url(code, key="food"):
    return "https://" + database(key)["host"] + "/product/" + code


def clean_code(text):
    """The digits of a barcode the user typed or scanned, or None. Also reads
    a product page's address, which some QR codes hold."""
    text = str(text or "").strip()
    if "/product/" in text:
        text = text.split("/product/")[1].split("/")[0]
    digits = "".join([c for c in text if c.isdigit()])
    if len(digits) < 6 or len(digits) > 14:
        return None
    rest = "".join([c for c in text if not c.isdigit() and c not in " -"])
    if rest:
        return None
    return digits


def language_of(locale):
    """The two-letter language the databases use, from a tag such as bn-BD."""
    lc = str(locale or "en").split("-")[0].split("_")[0].lower()
    return lc if len(lc) == 2 else "en"


def fields_for(lc):
    out = list(FIELDS)
    if lc != "en":
        out += [f + "_" + lc for f in LOCAL_FIELDS]
    out += [t + "_" + lc for t in LOCAL_TAGS]
    out.append("ingredients_analysis_tags_" + lc)
    return ",".join(out)


def _reply(r):
    """The reply's JSON, or None. A busy server answers with HTML."""
    try:
        data = r.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _busy(r):
    return r.status_code == 429 or r.status_code >= 500


# MARK: - reading

def lookup(code, then, on_error=None, lc="en", everywhere=True):
    """Looks [code] up and calls then(product) with what parse() gives, or
    then(None) when no database has it. With [everywhere], a code that is not
    food is looked for in the beauty, pet food and products databases too."""
    order = DATABASES if everywhere else DATABASES[:1]
    fields = fields_for(lc)

    def fail(error):
        if on_error is not None:
            on_error(error)

    def attempt(i):
        db = order[i]
        params = {"fields": fields}
        if i == 0 and everywhere:
            params["product_type"] = "all"
        http.get("https://" + db["host"] + API + code, params=params,
                 then=lambda r: answered(i, r), on_error=fail)

    def answered(i, r):
        if _busy(r):
            fail(OffError(database_of(r.url)["name"] + " is busy. Try again in a minute."))
            return
        data = _reply(r) or {}
        product = data.get("product")
        if r.status_code == 200 and isinstance(product, dict):
            then(parse(product, database_of(r.url)["key"], lc))
            return
        for e in data.get("errors") or []:
            if ((e.get("message") or {}).get("id")) == "invalid_code":
                fail(NotABarcode(code + " is not a barcode."))
                return
        if r.status_code not in (200, 404):
            fail(OffError(f"{order[i]['name']} answered {r.status_code}."))
            return
        if i + 1 < len(order):
            attempt(i + 1)
        else:
            then(None)

    attempt(0)


def search(query, then, on_error=None, lc="en", size=20):
    """Food products whose name or brand matches [query]: then(list) with
    {"code", "name", "brands", "quantity", "nutriscore"} items."""
    langs = lc if lc == "en" else lc + ",en"

    def answered(r):
        if _busy(r):
            if on_error is not None:
                on_error(OffError("Search is busy. Try again in a minute."))
            return
        data = _reply(r) or {}
        out = []
        for hit in data.get("hits") or []:
            if not hit.get("code"):
                continue
            brands = hit.get("brands") or ""
            if isinstance(brands, list):
                brands = ", ".join([str(b) for b in brands])
            name = hit.get("product_name") or ""
            if isinstance(name, dict):
                name = name.get(lc) or name.get("en") or ""
            out.append({"code": str(hit["code"]), "name": str(name), "brands": brands,
                        "quantity": str(hit.get("quantity") or ""), "nutriscore": grade(hit.get("nutriscore_grade"))})
        then(out)

    http.get(SEARCH_URL, params={"q": query, "page_size": size, "langs": langs,
                                 "fields": "code,product_name,brands,quantity,nutriscore_grade"},
             then=answered, on_error=on_error)


# MARK: - what a product says

def grade(value):
    """"a" to "e" (or "a-plus" for the Green-Score), or None when unknown."""
    value = str(value or "").lower()
    if value in ("a-plus", "a", "b", "c", "d", "e", "f"):
        return value
    return None


def tag_name(tag):
    """A tag the server did not name, made readable: en:no-gluten → No gluten."""
    tag = str(tag)
    if ":" in tag:
        tag = tag.split(":", 1)[1]
    if re.match(r"^e[0-9]{3,4}[a-z]*$", tag):
        return tag.upper()
    tag = tag.replace("-", " ").strip()
    return tag[:1].upper() + tag[1:]


def _names(p, field, lc):
    local = p.get(field + "_" + lc)
    tags = p.get(field) or []
    if isinstance(local, list) and len(local) == len(tags) and local:
        return [str(n)[:1].upper() + str(n)[1:] for n in local]
    return [tag_name(t) for t in tags]


def _analysis(tags, thing):
    """What ingredients_analysis_tags say about [thing]: "yes", "no", "maybe"
    or None (unknown)."""
    if "en:" + thing in tags:
        return "yes"
    if "en:non-" + thing in tags:
        return "no"
    if "en:maybe-" + thing in tags:
        return "maybe"
    return None


def _palm_oil(tags):
    """"yes" when it has palm oil, "no" when free of it, "maybe", or None."""
    if "en:palm-oil" in tags:
        return "yes"
    if "en:palm-oil-free" in tags:
        return "no"
    if "en:may-contain-palm-oil" in tags:
        return "maybe"
    return None


# The labels worth showing at a glance, by words in their tags.
LABEL_FLAGS = [
    ("halal", "Halal", ["halal"]),
    ("kosher", "Kosher", ["kosher"]),
    ("organic", "Organic", ["organic", "bio"]),
    ("fair_trade", "Fair trade", ["fair-trade", "fairtrade"]),
    ("vegan", "Vegan", ["vegan"]),
    ("vegetarian", "Vegetarian", ["vegetarian"]),
    ("gluten_free", "Gluten-free", ["no-gluten", "gluten-free"]),
]


def label_flags(tags):
    out = []
    for key, name, words in LABEL_FLAGS:
        for tag in tags:
            bare = str(tag).split(":", 1)[-1]
            if any([bare == w or bare.startswith(w + "-") or bare.endswith("-" + w) or ("-" + w + "-") in bare for w in words]):
                out.append({"key": key, "name": name})
                break
    return out


def _number(value):
    try:
        return float(value)
    except Exception:
        return None


def parse(p, key="food", lc="en"):
    """The parts of a product reply a screen shows, in one flat dict."""
    code = str(p.get("code") or "")
    analysis = p.get("ingredients_analysis_tags") or []
    nutriments = p.get("nutriments") or {}
    levels = p.get("nutrient_levels") or {}
    kind = p.get("product_type") or key
    nutrition = []
    for nkey, name, unit in NUTRIENTS:
        value = _number(nutriments.get(nkey + "_100g"))
        if value is not None:
            nutrition.append({"key": nkey, "name": name, "value": value, "unit": unit, "level": levels.get(nkey)})
    name = p.get("product_name_" + lc) or p.get("product_name") or ""
    ingredients = p.get("ingredients_text_" + lc) or p.get("ingredients_text") or ""
    labels = p.get("labels_tags") or []
    info = {
        "code": code,
        "db": key,
        "kind": kind,
        "name": str(name).strip(),
        "brands": str(p.get("brands") or "").strip(),
        "quantity": str(p.get("quantity") or "").strip(),
        "image": p.get("image_front_small_url") or "",
        "has_front": bool(p.get("image_front_url") or p.get("image_front_small_url")),
        "has_ingredients_photo": bool(p.get("image_ingredients_url")),
        "has_nutrition_photo": bool(p.get("image_nutrition_url")),
        "nutriscore": grade(p.get("nutriscore_grade")),
        "nova": p.get("nova_group") if p.get("nova_group") in (1, 2, 3, 4) else None,
        "greenscore": grade(p.get("environmental_score_grade")),
        "ingredients": str(ingredients).strip(),
        "allergens": _names(p, "allergens_tags", lc),
        "traces": _names(p, "traces_tags", lc),
        "labels": _names(p, "labels_tags", lc),
        "flags": label_flags(labels),
        "additives": _names(p, "additives_tags", lc),
        "vegan": _analysis(analysis, "vegan"),
        "vegetarian": _analysis(analysis, "vegetarian"),
        "palm_oil": _palm_oil(analysis),
        "nutrition": nutrition,
        "url": product_url(code, key),
    }
    info["missing"] = missing(info)
    return info


def missing(info):
    """What the product still lacks that a user can add from the phone."""
    out = []
    if not info["name"]:
        out.append("name")
    if not info["ingredients"] and info["kind"] in ("food", "beauty", "petfood"):
        out.append("ingredients")
    if not info["has_front"]:
        out.append("front")
    if info["kind"] == "food" and not info["nutrition"] and not info["has_nutrition_photo"]:
        out.append("nutrition")
    return out


def score_text(value):
    """A grade as printed on the pack: A, B, ... or A+."""
    if value is None:
        return "?"
    return "A+" if value == "a-plus" else value.upper()


def summary(info):
    """A few lines to paste into a chat."""
    head = info["name"] or ("Product " + info["code"])
    extra = [x for x in (info["brands"], info["quantity"]) if x]
    lines = [head + (" (" + ", ".join(extra) + ")" if extra else "")]
    scores = []
    if info["nutriscore"]:
        scores.append("Nutri-Score " + score_text(info["nutriscore"]))
    if info["nova"]:
        scores.append("NOVA " + str(info["nova"]))
    if info["greenscore"]:
        scores.append("Green-Score " + score_text(info["greenscore"]))
    if scores:
        lines.append(" · ".join(scores))
    diet = []
    if info["vegan"] == "yes":
        diet.append("Vegan")
    elif info["vegetarian"] == "yes":
        diet.append("Vegetarian")
    elif info["vegetarian"] == "no":
        diet.append("Not vegetarian")
    if info["palm_oil"] == "yes":
        diet.append("Contains palm oil")
    elif info["palm_oil"] == "no":
        diet.append("No palm oil")
    diet += [f["name"] for f in info["flags"] if f["key"] in ("halal", "kosher", "organic", "fair_trade")]
    if diet:
        lines.append(" · ".join(diet))
    if info["allergens"]:
        lines.append("Allergens: " + ", ".join(info["allergens"]))
    lines.append(info["url"])
    return "\n".join(lines)


# MARK: - contributing

def _site(key, test):
    if test:
        return "https://" + TEST_HOST
    return "https://" + database(key)["host"]


def _headers(test):
    return {"Authorization": TEST_AUTH} if test else None


def _account_fields(account, app):
    out = {"user_id": account["user"], "password": account["password"]}
    for k in ("app_name", "app_version", "app_uuid"):
        if app.get(k):
            out[k] = app[k]
    return out


def check_login(account, then, on_error=None, test=False):
    """then(True) when the user name and password work, then(False) when not."""
    def answered(r):
        if _busy(r):
            if on_error is not None:
                on_error(OffError("Open Food Facts is busy. Try again in a minute."))
            return
        data = _reply(r) or {}
        then(r.status_code == 200 and data.get("status") == 1)

    http.post(_site("food", test) + "/cgi/auth.pl",
              data={"user_id": account["user"], "password": account["password"], "body": "1"},
              headers=_headers(test), then=answered, on_error=on_error)


def save(code, key, fields, account, app, then, on_error=None, test=False):
    """Saves [fields] (product_name_en, brands, quantity, ingredients_text_en,
    lang ...) on the product, making it if it is new. then(True) once saved."""
    data = {"code": code, "comment": "From WM Keyboard's Open Food Facts plugin"}
    data.update(_account_fields(account, app))
    data.update(fields)

    def answered(r):
        body = _reply(r) or {}
        if r.status_code == 200 and body.get("status") == 1:
            then(True)
        elif r.status_code in (401, 403):
            if on_error is not None:
                on_error(PermissionError("Open Food Facts did not accept your user name and password."))
        elif on_error is not None:
            on_error(OffError(str(body.get("status_verbose") or f"The server answered {r.status_code}.")))

    http.post(_site(key, test) + "/cgi/product_jqm2.pl", data=data, headers=_headers(test),
              then=answered, on_error=on_error)


def upload_photo(code, key, kind, lc, photo, account, app, then, on_error=None, test=False):
    """Uploads [photo] ({"name", "mime", "data"}, as files.photo gives it)
    as the product's [kind] photo in language [lc], and selects it so it
    shows. then(image id) once both are done."""
    field = kind + "_" + lc
    site = _site(key, test)
    auth = _account_fields(account, app)

    def fail(error):
        if on_error is not None:
            on_error(error)

    def uploaded(r):
        body = _reply(r) or {}
        if r.status_code in (401, 403):
            fail(PermissionError("Open Food Facts did not accept your user name and password."))
            return
        if body.get("status") != "status ok" or not body.get("imgid"):
            if body.get("error") or body.get("debug"):
                fail(OffError(str(body.get("error") or body.get("debug"))))
            else:
                fail(OffError(f"The photo was not taken: the server answered {r.status_code}."))
            return
        imgid = str(body["imgid"])
        select = {"code": code, "imgid": imgid, "id": field}
        select.update(auth)
        http.post(site + "/cgi/product_image_crop.pl", data=select, headers=_headers(test),
                  then=lambda s: then(imgid) if s.status_code == 200 else fail(OffError("The photo was uploaded, but could not be set as the " + kind + " photo.")),
                  on_error=fail)

    data = {"code": code, "imagefield": field}
    data.update(auth)
    http.post(site + "/cgi/product_image_upload.pl", data=data, files={"imgupload_" + field: photo},
              headers=_headers(test), then=uploaded, on_error=fail)
