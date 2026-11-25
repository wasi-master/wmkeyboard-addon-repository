# E-book Viewer: EPUB (a zip of XHTML with an OPF package file), FictionBook
# (one XML file, pictures in base64) and CBZ (a zip of page pictures).

from wm import plugin, ui
from wm.preview import xml

PICTURE = (".jpg", ".jpeg", ".png", ".webp", ".gif")
COVER_BYTES = 524288
OPENING_CHARS = 1500
MAX_CONTENTS = 60
TEXT_TAGS = ("p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "div")

_cache = {}


# MARK: - EPUB

def _names(file):
    if "names" not in _cache:
        try:
            _cache["names"] = file.zip_names()
        except ValueError:
            _cache["names"] = []
    return _cache["names"]


def _join(base, target):
    target = target.split("#")[0]
    if target.startswith("/"):
        return target[1:]
    parts = base.split("/")[:-1]
    for piece in target.split("/"):
        if piece == "..":
            if parts:
                parts.pop()
        elif piece and piece != ".":
            parts.append(_unquote(piece))
    return "/".join(parts)


def _unquote(text):
    """%20 and the like in a link, as the zip names them."""
    if "%" not in text:
        return text
    out = []
    i = 0
    while i < len(text):
        if text[i] == "%" and i + 2 < len(text) + 0 and _hex(text[i + 1:i + 3]):
            out.append(chr(int(text[i + 1:i + 3], 16)))
            i = i + 3
        else:
            out.append(text[i])
            i = i + 1
    return "".join(out)


def _hex(pair):
    if len(pair) != 2:
        return False
    for ch in pair:
        if ch not in "0123456789abcdefABCDEF":
            return False
    return True


def package(file):
    """The EPUB's OPF: {"path", "meta", "manifest": {id: (href, type, props)}, "spine": [ids], "cover"}."""
    if "package" in _cache:
        return _cache["package"]
    names = _names(file)
    opf_path = None
    if "META-INF/container.xml" in names:
        root = xml(file.zip_read("META-INF/container.xml")).first("rootfile")
        if root is not None:
            opf_path = root.get("full-path")
    if opf_path is None or opf_path not in names:
        for n in names:
            if n.lower().endswith(".opf"):
                opf_path = n
                break
    if opf_path is None:
        _cache["package"] = None
        return None
    opf = xml(file.zip_read(opf_path))
    meta = {}
    cover_id = None
    md = opf.first("metadata")
    if md is not None:
        for e in md.children:
            if e.name == "meta":
                if e.get("name") == "cover":
                    cover_id = e.get("content")
                continue
            text = e.all_text().strip()
            if text and e.name not in meta:
                meta[e.name] = text
            elif text and e.name == "creator":
                meta["creator"] = meta["creator"] + ", " + text
    manifest = {}
    cover = None
    mf = opf.first("manifest")
    for item in (mf.findall("item") if mf is not None else []):
        href = _join(opf_path, item.get("href", ""))
        props = item.get("properties", "")
        manifest[item.get("id")] = (href, item.get("media-type", ""), props)
        if "cover-image" in props.split(" "):
            cover = href
    if cover is None and cover_id in manifest:
        cover = manifest[cover_id][0]
    if cover is None:
        for href, kind, props in manifest.values():
            low = href.lower()
            if "cover" in low and low.endswith(PICTURE):
                cover = href
                break
    spine = []
    sp = opf.first("spine")
    for ref in (sp.findall("itemref") if sp is not None else []):
        if ref.get("idref") in manifest and ref.get("linear") != "no":
            spine.append(ref.get("idref"))
    found = {"path": opf_path, "meta": meta, "manifest": manifest, "spine": spine, "cover": cover,
             "toc": sp.get("toc") if sp is not None else None}
    _cache["package"] = found
    return found


def contents(file, pack):
    """[(depth, title)] from the EPUB 3 nav document, else the EPUB 2 NCX."""
    for href, kind, props in pack["manifest"].values():
        if "nav" in props.split(" "):
            nav = xml(file.zip_read(href))
            for n in nav.iter("nav"):
                kind_attr = n.get("type", "")
                if kind_attr and kind_attr != "toc":
                    continue
                out = []
                _nav_list(n.find("ol") or n.first("ol"), 0, out)
                if out:
                    return out
    toc = pack["manifest"].get(pack["toc"]) if pack["toc"] else None
    if toc is None:
        for href, kind, props in pack["manifest"].values():
            if kind == "application/x-dtbncx+xml":
                toc = (href, kind, props)
    if toc is None:
        return []
    out = []
    nav_map = xml(file.zip_read(toc[0])).first("navMap")
    if nav_map is not None:
        _ncx(nav_map, 0, out)
    return out


def _nav_list(ol, depth, out):
    if ol is None or depth > 4:
        return
    for li in ol.findall("li"):
        if len(out) >= MAX_CONTENTS:
            return
        label = li.find("a") or li.find("span")
        if label is not None:
            out.append((depth, " ".join(label.all_text().split())))
        _nav_list(li.find("ol"), depth + 1, out)


def _ncx(parent, depth, out):
    if depth > 4:
        return
    for point in parent.findall("navPoint"):
        if len(out) >= MAX_CONTENTS:
            return
        label = point.first("text")
        if label is not None:
            out.append((depth, " ".join(label.text.split())))
        _ncx(point, depth + 1, out)


def opening(file, pack):
    """The first chapter's opening paragraphs: the first spine page with real text."""
    for idref in pack["spine"][:8]:
        href, kind, props = pack["manifest"][idref]
        if href not in _names(file):
            continue
        body = xml(file.zip_read(href, max=2097152)).first("body")
        if body is None:
            continue
        paragraphs = _paragraphs(body)
        if sum(len(p) for p in paragraphs) >= 200:
            return paragraphs
    return []


def _paragraphs(body):
    out = []
    total = 0
    stack = [body]
    while stack and total < OPENING_CHARS:
        e = stack.pop()
        if e.name in TEXT_TAGS and not any(c.name in TEXT_TAGS for c in e.children):
            text = " ".join(e.all_text().split())
            if text:
                out.append(text)
                total = total + len(text)
            continue
        if e.name in ("script", "style", "head"):
            continue
        kids = e.children
        i = len(kids) - 1
        while i >= 0:
            stack.append(kids[i])
            i = i - 1
    return out


def _cover_bytes(file, href):
    if not href or href not in _names(file):
        return None
    try:
        return file.zip_read(href, max=COVER_BYTES)
    except ValueError:
        return None


def _cover_from_page(file, pack):
    """Old EPUBs with no cover image named: the picture on the first page."""
    if not pack["spine"]:
        return None
    href = pack["manifest"][pack["spine"][0]][0]
    if href not in _names(file):
        return None
    page = xml(file.zip_read(href, max=262144))
    for tag in ("img", "image"):
        e = page.first(tag)
        if e is not None:
            src = e.get("src") or e.get("href")
            if src:
                return _cover_bytes(file, _join(href, src))
    return None


def show_epub(file):
    pack = package(file)
    if pack is None:
        ui.empty("This is not an EPUB book.")
        return
    meta = pack["meta"]
    cover = _cover_bytes(file, pack["cover"]) or _cover_from_page(file, pack)
    if cover:
        ui.image(cover, alt="Cover", height=220)
    ui.label(meta.get("title", file.name), style="headline")
    if "creator" in meta:
        ui.label(meta["creator"], style="title")
    facts = []
    for key in ("publisher", "date", "language"):
        if key in meta:
            facts.append(meta[key][:10] if key == "date" else meta[key])
    if facts:
        ui.caption(" · ".join(facts))
    if "description" in meta:
        ui.markdown(_plain(meta["description"]))
    toc = contents(file, pack)
    if toc:
        with ui.section("Contents", collapsible=True, open=False):
            for depth, title in toc:
                ui.label("    " * depth + title)
    words = opening(file, pack)
    if words:
        with ui.section("Opening", collapsible=True, open=True):
            for p in words:
                ui.label(p)


def _plain(text):
    """A description's HTML as plain text."""
    if "<" not in text:
        return text
    return " ".join(xml("<d>" + text + "</d>").all_text().split())


# MARK: - FictionBook

def show_fb2(file):
    book = xml(file.data, max_nodes=60000)
    info = book.first("title-info")
    binaries = {}
    for b in book.findall("binary"):
        binaries[b.get("id")] = b
    if info is not None:
        cover = info.first("coverpage")
        image = cover.first("image") if cover is not None else None
        ref = image.get("href", "").lstrip("#") if image is not None else ""
        if ref in binaries:
            import base64
            try:
                ui.image(base64.b64decode("".join(binaries[ref].text.split())), alt="Cover", height=220)
            except ValueError:
                pass
        title = info.find("book-title")
        ui.label(title.all_text().strip() if title is not None else file.name, style="headline")
        authors = []
        for a in info.findall("author"):
            parts = [a.find(k).all_text().strip() for k in ("first-name", "middle-name", "last-name") if a.find(k) is not None]
            name = " ".join(p for p in parts if p)
            if name:
                authors.append(name)
        if authors:
            ui.label(", ".join(authors), style="title")
        lang = info.find("lang")
        if lang is not None:
            ui.caption(lang.text.strip())
        note = info.find("annotation")
        if note is not None:
            ui.markdown(" ".join(note.all_text().split()))
    body = book.find("body")
    if body is None:
        return
    titles = [(0, " ".join(s.find("title").all_text().split())) for s in body.findall("section") if s.find("title") is not None]
    if titles:
        with ui.section("Contents", collapsible=True, open=False):
            for depth, title in titles[:MAX_CONTENTS]:
                ui.label(title)
    with ui.section("Opening", collapsible=True, open=True):
        total = 0
        for p in body.iter("p"):
            text = " ".join(p.all_text().split())
            if text:
                ui.label(text)
                total = total + len(text)
            if total >= OPENING_CHARS:
                break


# MARK: - comics

def _pages(file):
    pages = [n for n in _names(file) if n.lower().endswith(PICTURE) and not n.startswith("__MACOSX/")]
    return sorted(pages, key=_natural)


def _natural(name):
    """Page 2 before page 10: digits compared as numbers."""
    key = []
    digits = ""
    for ch in name.lower():
        if "0" <= ch <= "9":
            digits = digits + ch
        else:
            if digits:
                key.append(digits.zfill(8))
                digits = ""
            key.append(ch)
    if digits:
        key.append(digits.zfill(8))
    return "".join(key)


def show_comic(file):
    pages = _pages(file)
    if not pages:
        ui.empty("This comic has no pages.")
        return
    info = None
    for n in _names(file):
        if n.lower() == "comicinfo.xml":
            info = xml(file.zip_read(n))
    if info is not None:
        for tag, style in (("Series", "headline"), ("Title", "title"), ("Writer", None), ("Summary", None)):
            e = info.first(tag)
            if e is not None and e.text.strip():
                ui.label(e.text.strip(), style=style)
    ui.caption(f"{len(pages)} pages")
    for name in pages[:4]:
        picture = _cover_bytes(file, name)
        if picture:
            ui.image(picture, alt=name)
    if len(pages) > 4:
        ui.caption(f"{len(pages) - 4} more pages")


# MARK: - entry points

@plugin.preview("epub")
def preview_book(file):
    if file.extension == "fb2" or file.data[:200].find(b"FictionBook") >= 0:
        show_fb2(file)
    else:
        show_epub(file)


@plugin.thumbnail("epub")
def book_cover(file):
    if file.extension == "fb2":
        return None
    pack = package(file)
    if pack is None:
        return None
    return _cover_bytes(file, pack["cover"]) or _cover_from_page(file, pack)


@plugin.preview("comic")
def preview_comic(file):
    show_comic(file)


@plugin.thumbnail("comic")
def comic_cover(file):
    pages = _pages(file)
    return _cover_bytes(file, pages[0]) if pages else None
