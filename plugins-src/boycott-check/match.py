# Names to keys, the Tech for Palestine dataset to a compact index, and
# lookups by typed name, by brand and owner from Open Food Facts, and by text
# read from a photo. Pure functions: main.py does the storage and the drawing.

import re

# Corporate words that differ between how a list and a label write one name.
SUFFIXES = {
    "inc", "incorporated", "ltd", "limited", "llc", "plc", "co", "corp", "corporation",
    "company", "companies", "group", "sa", "ag", "gmbh", "nv", "bv", "spa", "srl",
    "holding", "holdings", "international", "brands", "the",
}

FOLD = {
    "à": "a", "á": "a", "â": "a", "ã": "a", "ä": "a", "å": "a", "ā": "a", "ă": "a", "ą": "a",
    "ç": "c", "ć": "c", "č": "c", "ď": "d", "è": "e", "é": "e", "ê": "e", "ë": "e", "ē": "e",
    "ę": "e", "ě": "e", "ğ": "g", "ì": "i", "í": "i", "î": "i", "ï": "i", "ī": "i", "ı": "i",
    "ł": "l", "ñ": "n", "ń": "n", "ň": "n", "ò": "o", "ó": "o", "ô": "o", "õ": "o", "ö": "o",
    "ø": "o", "ō": "o", "ő": "o", "ř": "r", "ś": "s", "š": "s", "ş": "s", "ș": "s", "ť": "t",
    "ț": "t", "ù": "u", "ú": "u", "û": "u", "ü": "u", "ū": "u", "ů": "u", "ű": "u", "ý": "y",
    "ÿ": "y", "ź": "z", "ż": "z", "ž": "z", "ß": "ss", "æ": "ae", "œ": "oe",
}

# Shard and index values stay well under storage's 64 KB a value.
CHUNK = 40000

REASONS = {
    "operations_in_israel": "Operates in Israel",
    "operations_in_settlements": "Operates in illegal Israeli settlements",
    "executive_supports_israel": "Its leadership supports Israel",
    "hiring_discrimination": "Discriminatory hiring",
}


def fold(text):
    text = str(text).lower()
    if not re.search(r"[^\x00-\x7f]", text):
        return text
    return "".join([FOLD.get(ch, ch) for ch in text])


def words(text):
    """The words of a name, lowercase and unaccented: "L'Oréal S.A." -> ["loreal"]."""
    text = fold(text)
    text = text.replace("&", " and ").replace("+", " plus ")
    text = re.sub(r"['’`´]", "", text)
    out = re.findall(r"[a-z0-9]+", text)
    while out and out[0] == "the":
        out = out[1:]
    while len(out) > 1 and out[-1] in SUFFIXES:
        out = out[:-1]
    return out


def key(text):
    """One name's matching key: its words run together, so "Coca-Cola",
    "Coca Cola" and "COCA-COLA" all give "cocacola"."""
    return "".join(words(text))


def variants(name):
    """The names one list entry goes by. "Dior / Christian Dior" is two;
    "(...)" notes such as "Dove (Mars)" or "Aldi Nord (not UK)" are not
    names, so they are dropped for matching (and kept on screen)."""
    out = []
    for part in str(name).split(" / "):
        bare = re.sub(r"\([^)]*\)", " ", part).strip()
        if bare and bare not in out:
            out.append(bare)
    return out or [str(name)]


def owner_name(owner_id):
    """An owner the dataset names only by id: "the-coca-cola-company"."""
    return str(owner_id).replace("-", " ")


# MARK: - the dataset to an index and shards

def split_sources(description):
    """The description without its footnote lines, and their links in order.
    "[^1]" marks in the text become "[1]"."""
    links = []
    for m in re.finditer(r"\[\^(\d+)\]:\s*(\S+)", description):
        links.append(m.group(2))
    body = re.sub(r"\n*\[\^\d+\]:\s*\S+[^\n]*", "", description)
    body = re.sub(r"\[\^(\d+)\]", r"[\1]", body).strip()
    return body, links


def records(data):
    """Every brand and company in Tech for Palestine's data.json, as compact
    records: id, kind ("brand" or "company"), name, status, text (with its
    footnotes, split by split_sources when shown), reasons, owners,
    alternatives."""
    out = []
    for kind, field in (("brand", "brands"), ("company", "companies")):
        group = data.get(field) or {}
        for ident in group:
            e = group[ident]
            if not isinstance(e, dict) or not e.get("name"):
                continue
            rec = {"id": str(e.get("id") or ident), "k": kind, "n": str(e["name"]),
                   "s": str(e.get("status") or "avoid"), "d": str(e.get("description") or "")}
            if e.get("reasons"):
                rec["r"] = [str(r) for r in e["reasons"]]
            owners = [str(s.get("id")) for s in (e.get("stakeholders") or [])
                      if isinstance(s, dict) and s.get("type") == "owner" and s.get("id")]
            if owners:
                rec["o"] = owners
            if e.get("alternatives"):
                rec["a"] = [str(a) for a in e["alternatives"]]
            if e.get("alternatives_text"):
                rec["at"] = str(e["alternatives_text"])
            out.append(rec)
    return out


def size_of(item):
    """About how long [item] is as JSON: its text plus a little for each
    value. Cheaper than json.dumps on every record."""
    if isinstance(item, str):
        return len(item) + 8
    if isinstance(item, dict):
        return sum([size_of(v) + len(k) + 4 for k, v in item.items()]) + 2
    if isinstance(item, (list, tuple)):
        return sum([size_of(v) + 1 for v in item]) + 2
    return 12


def chunked(items, limit=CHUNK):
    """Items in lists whose JSON stays under [limit] characters (estimated
    generously; storage's own limit is 64 KB a value)."""
    out = []
    current = []
    size = 2
    for it in items:
        n = size_of(it) + 1
        if current and size + n > limit:
            out.append(current)
            current = []
            size = 2
        current.append(it)
        size = size + n
    if current:
        out.append(current)
    return out


def build(data):
    """(index chunks, record shards, counts) for storage. The matching keys
    are worked out here, once per download, so opening the panel only reads
    them. An index row is [id, kind, name, status, shard, owners, the words
    of each name, extra keys, owner keys]."""
    recs = records(data)
    shards = chunked(recs)
    rows = []
    owner_keys = {}
    for number, shard in enumerate(shards):
        for rec in shard:
            wordsets = []
            for v in variants(rec["n"]):
                w = " ".join(words(v))
                if w and w not in wordsets:
                    wordsets.append(w)
            # A company's id names it too ("bookingcom").
            extra = key(owner_name(rec["id"]))
            okeys = []
            for o in rec.get("o") or []:
                if o not in owner_keys:
                    owner_keys[o] = key(owner_name(o))
                okeys.append(owner_keys[o])
            rows.append([rec["id"], rec["k"], rec["n"], rec["s"], number, rec.get("o") or [], wordsets,
                         [extra] if extra and extra not in [w.replace(" ", "") for w in wordsets] else [], okeys])
    brands = len([r for r in recs if r["k"] == "brand"])
    flagged = len([r for r in recs if r["k"] == "brand" and r["s"] == "avoid"])
    return chunked(rows), shards, {"brands": brands, "flagged": flagged, "companies": len(recs) - brands}


# MARK: - the in-memory index

class Index:
    """Every entry the plugin can show, from the Tech for Palestine rows and
    the BDS targets, and the keys that find them."""

    def __init__(self):
        self.entries = []
        self.by_key = {}
        self.by_owner = {}
        self.by_id = {}

    def _add_key(self, k, at):
        if not k:
            return
        found = self.by_key.get(k)
        if found is None:
            self.by_key[k] = [at]
        elif at not in found:
            found.append(at)

    def add(self, entry, wordlists):
        at = len(self.entries)
        entry["keys"] = []
        entry["words"] = []
        for w in wordlists:
            k = "".join(w)
            if k and k not in entry["keys"]:
                entry["keys"].append(k)
                entry["words"].append(w)
                self._add_key(k, at)
        self.entries.append(entry)
        place = entry["src"] + ":" + entry["id"]
        if place not in self.by_id:
            self.by_id[place] = at
        return at

    def locate(self, src, ident):
        """The entry with this id in one source, or None."""
        return self.by_id.get(str(src) + ":" + str(ident))

    def add_tfp(self, rows):
        for row in rows:
            at = self.add({"src": "tfp", "id": row[0], "kind": row[1], "name": row[2], "status": row[3],
                           "shard": row[4], "owners": row[5]}, [w.split(" ") for w in row[6]])
            for k in row[7]:
                self._add_key(k, at)
            for ok in row[8]:
                found = self.by_owner.get(ok)
                if found is None:
                    self.by_owner[ok] = [at]
                elif at not in found:
                    found.append(at)

    def add_bds(self, targets):
        for t in targets:
            self.add({"src": "bds", "id": t["id"], "kind": "target", "name": t["name"], "tier": t["tier"],
                      "status": "avoid", "target": t}, [words(n) for n in [t["name"]] + list(t["aliases"])])

    def find(self, name):
        """Entries listed under exactly this name."""
        return list(self.by_key.get(key(name)) or [])

    def owned_by(self, name):
        """Entries whose owner the dataset gives as this name."""
        return list(self.by_owner.get(key(name)) or [])

    def related(self, at):
        """Every entry sharing a key with entry [at], itself first."""
        out = [at]
        for k in self.entries[at]["keys"]:
            for other in self.by_key.get(k) or []:
                if other not in out:
                    out.append(other)
        return out

    def search(self, query, limit=40):
        """Entries for a typed name, best first: the whole name, then names
        that start with it, then names with a word that starts with it, then
        names that contain it."""
        q = words(query)
        if not q:
            return []
        qk = "".join(q)
        ranked = []
        for at, e in enumerate(self.entries):
            best = 9
            for w in e["words"]:
                k = "".join(w)
                if k == qk:
                    best = 0
                elif k.startswith(qk):
                    best = min(best, 1)
                elif len(qk) >= 2 and any(["".join(w[i:]).startswith(qk) for i in range(1, len(w))]):
                    best = min(best, 2)
                elif len(qk) >= 3 and qk in k:
                    best = min(best, 3)
            if best < 9:
                ranked.append((best, 0 if e["src"] == "bds" else 1, e["name"].lower(), at))
        ranked.sort()
        return [r[3] for r in ranked[:limit]]


# MARK: - products and photos

def brand_names(product):
    """The brand and owner names Open Food Facts gives for one product,
    each with where it came from."""
    out = []
    for b in str(product.get("brands") or "").split(","):
        b = b.strip()
        if b:
            out.append((b, "brand"))
    owner = str(product.get("brand_owner") or "").strip()
    if owner:
        out.append((owner, "owner"))
    return out


def match_product(index, product):
    """What the lists say about one product: a list of
    {"at", "how", "name"} where how is "brand", "owner", "owner of" (the
    dataset lists a brand this owner owns) or "partly" (only the start of a
    longer brand name, such as "Coca-Cola" in "Coca-Cola Zero")."""
    found = []
    seen = []

    def note(at, how, name):
        if at not in seen:
            seen.append(at)
            found.append({"at": at, "how": how, "name": name})

    names = brand_names(product)
    for name, where in names:
        for at in index.find(name):
            note(at, where, name)
    for name, where in names:
        for at in index.owned_by(name):
            note(at, "owner of", name)
    if not found:
        for name, where in names:
            w = words(name)
            n = len(w) - 1
            while n >= 1:
                k = "".join(w[:n])
                if len(k) >= 4 and index.by_key.get(k):
                    for at in index.by_key[k]:
                        note(at, "partly", name)
                    break
                n = n - 1
    return found


def made_in_israel(product):
    """Which of the product's Open Food Facts fields name Israel."""
    out = []
    for field, label in (("origins_tags", "origin"), ("manufacturing_places_tags", "made in")):
        tags = product.get(field) or []
        if isinstance(tags, str):
            tags = [tags]
        if any([str(t).lower() in ("en:israel", "israel") for t in tags]):
            out.append(label)
    for field, label in (("origins", "origin"), ("manufacturing_places", "made in")):
        if label not in out and re.search(r"\bisra[eë]l\b", fold(product.get(field) or "")):
            out.append(label)
    return out


def names_in_text(index, text, limit=30):
    """Listed names that appear in [text], as (entry index, the words that
    matched), longest names first, each entry once."""
    found = []
    seen = []
    for line in str(text).splitlines():
        w = words(line)
        n = 3
        while n >= 1:
            i = 0
            while i + n <= len(w):
                k = "".join(w[i:i + n])
                if len(k) >= 3:
                    for at in index.by_key.get(k) or []:
                        if at not in seen:
                            seen.append(at)
                            found.append((at, " ".join(w[i:i + n])))
                i = i + 1
            n = n - 1
        if len(found) >= limit:
            break
    return found[:limit]
