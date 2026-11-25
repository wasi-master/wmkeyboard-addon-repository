# Office Viewer: Word, Excel and PowerPoint files (Office Open XML) and the
# OpenDocument ones, drawn in the file manager. Both kinds are zips of XML;
# the keyboard unzips and parses, this script walks the trees.

from wm import plugin, ui
from wm.preview import xml

MAX_BLOCKS = 600       # paragraphs and tables drawn from a document
MAX_ROWS = 200         # rows shown per sheet or table
MAX_COLUMNS = 30
MAX_SHEETS = 12
MAX_SLIDES = 80
THUMB_BYTES = 524288


# MARK: - shared

_names = {}


def _has(file, name):
    # Each preview runs in a fresh interpreter, so one file's names are cached.
    if "set" not in _names:
        try:
            _names["set"] = set(file.zip_names())
        except ValueError:
            _names["set"] = set()
    return name in _names["set"]


def _tree(file, name):
    if not _has(file, name):
        return None
    return xml(file.zip_read(name))


def _texts(element, tag="t"):
    """The text of every <tag> inside, joined: Word's w:t, DrawingML's a:t."""
    return "".join(t.text for t in element.iter(tag))


def _odf_text(element):
    """An OpenDocument paragraph's text: spans, tabs, line breaks and runs of spaces."""
    out = []
    stack = [element]
    while stack:
        n = stack.pop()
        if isinstance(n, str):
            out.append(n)
            continue
        if n.name == "tab":
            out.append("\t")
        elif n.name == "line-break":
            out.append("\n")
        elif n.name == "s":
            out.append(" " * int(n.get("c", "1") or "1"))
        elif n.name in ("note", "annotation"):
            continue
        i = len(n.nodes) - 1
        while i >= 0:
            stack.append(n.nodes[i])
            i = i - 1
    return "".join(out)


def _rels(file, name):
    """A .rels part as {id: target}."""
    tree = _tree(file, name)
    out = {}
    if tree is None:
        return out
    for r in tree.findall("Relationship"):
        out[r.get("Id")] = r.get("Target")
    return out


def _rid(element):
    """An element's relationship id, r:id, whatever its prefix: a slide's
    plain "id" attribute is a number, not the link."""
    for k, v in element.attrs.items():
        if k.endswith(":id"):
            return v
    return None


def _join(base, target):
    """A relationship target relative to [base]'s folder, as a zip path."""
    if target.startswith("/"):
        return target[1:]
    parts = base.split("/")[:-1]
    for piece in target.split("/"):
        if piece == "..":
            if parts:
                parts.pop()
        elif piece and piece != ".":
            parts.append(piece)
    return "/".join(parts)


def _square(rows):
    """Rows padded to one width, cut to MAX_COLUMNS, trailing empty columns dropped."""
    width = 0
    for r in rows:
        last = len(r)
        while last > 0 and not r[last - 1]:
            last = last - 1
        width = max(width, last)
    width = min(width, MAX_COLUMNS)
    return [(r + [""] * width)[:width] for r in rows]


def _table(rows):
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return
    rows = _square(rows)
    shown = rows[:MAX_ROWS + 1]
    ui.table(shown[1:], header=shown[0])
    if len(rows) > len(shown):
        ui.caption(f"{len(rows) - len(shown)} more rows")


def _about(file):
    """Title, author and dates from docProps/core.xml or meta.xml, as a caption."""
    bits = []
    core = _tree(file, "docProps/core.xml")
    if core is not None:
        for tag in ("title", "creator", "modified"):
            e = core.first(tag)
            if e is not None and e.text.strip():
                bits.append(e.text.strip()[:10] if tag == "modified" else e.text.strip())
    meta = _tree(file, "meta.xml")
    if meta is not None:
        for tag in ("title", "initial-creator", "creator", "date"):
            e = meta.first(tag)
            if e is not None and e.text.strip():
                text = e.text.strip()[:10] if tag == "date" else e.text.strip()
                if text not in bits:
                    bits.append(text)
    if bits:
        ui.caption(" · ".join(bits))


def _odf(file):
    return _has(file, "content.xml")


def _thumbnail(file):
    for name in ("docProps/thumbnail.jpeg", "docProps/thumbnail.jpg", "docProps/thumbnail.png", "Thumbnails/thumbnail.png"):
        if _has(file, name):
            try:
                return file.zip_read(name, max=THUMB_BYTES)
            except ValueError:
                return None
    return None


# MARK: - documents

def _word_rows(tbl):
    rows = []
    for tr in tbl.findall("tr"):
        rows.append([" ".join(_texts(p).strip() for p in tc.findall("p")).strip() for tc in tr.findall("tc")])
    return rows


def _word_style(p):
    pr = p.find("pPr")
    if pr is None:
        return "", False
    style = pr.find("pStyle")
    listed = pr.find("numPr") is not None
    return (style.get("val", "") if style is not None else ""), listed


def show_word(body):
    drawn = 0
    for block in body.children:
        if drawn >= MAX_BLOCKS:
            ui.caption("The rest of the document is not shown.")
            return
        if block.name == "tbl":
            _table(_word_rows(block))
            drawn = drawn + 1
        elif block.name == "p":
            text = _texts(block).strip()
            if not text:
                continue
            style, listed = _word_style(block)
            low = style.lower()
            if low == "title":
                ui.label(text, style="headline")
            elif low.startswith("heading") or low == "subtitle":
                ui.label(text, style="title")
            elif listed or low.startswith("list"):
                ui.label("•  " + text)
            else:
                ui.label(text)
            drawn = drawn + 1
        elif block.name == "sdt":
            content = block.find("sdtContent")
            if content is not None:
                text = _texts(content).strip()
                if text:
                    ui.label(text)
                    drawn = drawn + 1


def _odf_rows(table):
    rows = []
    for row in table.iter("table-row"):
        cells = []
        for cell in row.children:
            if cell.name not in ("table-cell", "covered-table-cell"):
                continue
            text = " ".join(_odf_text(p).strip() for p in cell.findall("p")).strip()
            repeat = min(int(cell.get("number-columns-repeated", "1") or "1"), MAX_COLUMNS)
            cells.extend([text] * repeat)
        repeat = min(int(row.get("number-rows-repeated", "1") or "1"), MAX_ROWS)
        if not any(cells):
            repeat = 1
        for _ in range(repeat):
            rows.append(list(cells))
        if len(rows) > MAX_ROWS * 2:
            break
    return rows


def show_odt(office_text):
    drawn = 0
    stack = list(reversed(office_text.children))
    while stack and drawn < MAX_BLOCKS:
        block = stack.pop()
        if block.name == "h":
            text = _odf_text(block).strip()
            if text:
                level = block.get("outline-level", "1")
                ui.label(text, style="headline" if level == "1" else "title")
                drawn = drawn + 1
        elif block.name == "p":
            text = _odf_text(block).strip()
            if text:
                ui.label(text)
                drawn = drawn + 1
        elif block.name == "list":
            for item in block.findall("list-item"):
                for p in item.children:
                    if p.name in ("p", "h"):
                        text = _odf_text(p).strip()
                        if text:
                            ui.label("•  " + text)
                            drawn = drawn + 1
        elif block.name == "table":
            _table(_odf_rows(block))
            drawn = drawn + 1
        elif block.name == "section":
            stack.extend(reversed(block.children))
    if stack:
        ui.caption("The rest of the document is not shown.")


@plugin.preview("word")
def preview_word(file):
    _about(file)
    if _odf(file):
        body = _tree(file, "content.xml").first("text")
        if body is None:
            ui.empty("This document has no text.")
            return
        show_odt(body)
        return
    if not _has(file, "word/document.xml"):
        ui.empty("This is not a Word document.")
        return
    body = _tree(file, "word/document.xml").first("body")
    if body is None or not body.children:
        ui.empty("This document has no text.")
        return
    show_word(body)


@plugin.thumbnail("word")
def thumb_word(file):
    return _thumbnail(file)


# MARK: - spreadsheets

def _column(ref):
    """The 0-based column of a cell reference such as "AB12"."""
    n = 0
    for ch in ref:
        if "A" <= ch <= "Z":
            n = n * 26 + (ord(ch) - 64)
        else:
            break
    return n - 1


def _shared_strings(file):
    tree = _tree(file, "xl/sharedStrings.xml")
    if tree is None:
        return []
    out = []
    for si in tree.findall("si"):
        # Phonetic guides (rPh) hold readings, not the cell's text.
        parts = []
        for r in si.children:
            if r.name in ("t", "r"):
                for t in r.iter("t"):
                    parts.append(t.text)
        out.append("".join(parts))
    return out


def _xlsx_sheet(tree, strings):
    rows = []
    data = tree.first("sheetData")
    if data is None:
        return rows
    for row in data.findall("row"):
        if len(rows) > MAX_ROWS:
            break
        at = int(row.get("r", str(len(rows) + 1)) or "1") - 1
        while len(rows) < at and len(rows) <= MAX_ROWS:
            rows.append([])
        cells = []
        for c in row.findall("c"):
            col = _column(c.get("r", "")) if c.get("r") else len(cells)
            if col < 0 or col >= MAX_COLUMNS:
                continue
            kind = c.get("t", "n")
            v = c.find("v")
            raw = v.text if v is not None else ""
            if kind == "s" and raw:
                i = int(raw)
                value = strings[i] if i < len(strings) else ""
            elif kind == "inlineStr":
                value = _texts(c)
            elif kind == "b":
                value = "TRUE" if raw == "1" else "FALSE"
            else:
                value = raw
            while len(cells) < col:
                cells.append("")
            cells.append(value)
        rows.append(cells)
    return rows


def show_xlsx(file):
    book = _tree(file, "xl/workbook.xml")
    rels = _rels(file, "xl/_rels/workbook.xml.rels")
    strings = _shared_strings(file)
    sheets = book.first("sheets").findall("sheet") if book is not None and book.first("sheets") is not None else []
    if not sheets:
        ui.empty("This workbook has no sheets.")
        return
    ui.caption(f"{len(sheets)} sheet" + ("" if len(sheets) == 1 else "s"))
    for i, sheet in enumerate(sheets[:MAX_SHEETS]):
        target = rels.get(_rid(sheet))
        path = _join("xl/workbook.xml", target) if target else ""
        with ui.section(sheet.get("name", f"Sheet {i + 1}"), collapsible=True, open=i == 0):
            tree = _tree(file, path) if path else None
            rows = _xlsx_sheet(tree, strings) if tree is not None else []
            if any(any(c for c in r) for r in rows):
                _table(rows)
            else:
                ui.caption("Empty")


def show_ods(file):
    sheet_root = _tree(file, "content.xml").first("spreadsheet")
    tables = sheet_root.findall("table") if sheet_root is not None else []
    if not tables:
        ui.empty("This spreadsheet has no sheets.")
        return
    ui.caption(f"{len(tables)} sheet" + ("" if len(tables) == 1 else "s"))
    for i, table in enumerate(tables[:MAX_SHEETS]):
        with ui.section(table.get("name", f"Sheet {i + 1}"), collapsible=True, open=i == 0):
            rows = _odf_rows(table)
            if any(any(c for c in r) for r in rows):
                _table(rows)
            else:
                ui.caption("Empty")


@plugin.preview("sheet")
def preview_sheet(file):
    _about(file)
    if _odf(file):
        show_ods(file)
    elif _has(file, "xl/workbook.xml"):
        show_xlsx(file)
    else:
        ui.empty("This is not a spreadsheet.")


@plugin.thumbnail("sheet")
def thumb_sheet(file):
    return _thumbnail(file)


# MARK: - slides

def _slide_parts(shapes):
    """(title, [lines]) from a slide's shapes."""
    title = ""
    lines = []
    for sp in shapes.iter("sp"):
        ph = sp.first("ph")
        kind = ph.get("type", "") if ph is not None else ""
        body = sp.find("txBody")
        if body is None:
            continue
        paragraphs = [_texts(p).strip() for p in body.findall("p")]
        paragraphs = [p for p in paragraphs if p]
        if not paragraphs:
            continue
        if kind in ("title", "ctrTitle") and not title:
            title = " ".join(paragraphs)
        else:
            lines.extend(paragraphs)
    return title, lines


def show_pptx(file):
    pres = _tree(file, "ppt/presentation.xml")
    rels = _rels(file, "ppt/_rels/presentation.xml.rels")
    ids = pres.first("sldIdLst") if pres is not None else None
    slides = ids.findall("sldId") if ids is not None else []
    if not slides:
        ui.empty("This presentation has no slides.")
        return
    ui.caption(f"{len(slides)} slide" + ("" if len(slides) == 1 else "s"))
    for n, sid in enumerate(slides[:MAX_SLIDES]):
        target = rels.get(_rid(sid))
        tree = _tree(file, _join("ppt/presentation.xml", target)) if target else None
        title, lines = _slide_parts(tree) if tree is not None else ("", [])
        _slide_card(n + 1, title, lines)
    if len(slides) > MAX_SLIDES:
        ui.caption(f"{len(slides) - MAX_SLIDES} more slides")


def _slide_card(number, title, lines):
    with ui.card(title=f"{number}. {title}" if title else f"Slide {number}"):
        for line in lines[:12]:
            ui.label("•  " + line)
        if len(lines) > 12:
            ui.caption(f"{len(lines) - 12} more lines")
        if not lines and not title:
            ui.caption("No text")


def show_odp(file):
    pres = _tree(file, "content.xml").first("presentation")
    pages = pres.findall("page") if pres is not None else []
    if not pages:
        ui.empty("This presentation has no slides.")
        return
    ui.caption(f"{len(pages)} slide" + ("" if len(pages) == 1 else "s"))
    for n, page in enumerate(pages[:MAX_SLIDES]):
        title = ""
        lines = []
        for frame in page.findall("frame"):
            texts = [_odf_text(p).strip() for p in frame.iter("p")]
            texts = [t for t in texts if t]
            if frame.get("class") == "title" and not title:
                title = " ".join(texts)
            elif frame.get("class") not in ("page-number", "footer", "date-time", "notes"):
                lines.extend(texts)
        _slide_card(n + 1, title, lines)


@plugin.preview("slides")
def preview_slides(file):
    _about(file)
    if _odf(file):
        show_odp(file)
    elif _has(file, "ppt/presentation.xml"):
        show_pptx(file)
    else:
        ui.empty("This is not a presentation.")


@plugin.thumbnail("slides")
def thumb_slides(file):
    return _thumbnail(file)
