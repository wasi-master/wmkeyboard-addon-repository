# Data Viewer: CSV and TSV, JSON and JSON Lines, Jupyter notebooks and SQLite
# databases, drawn as tables and folding sections.

import json

from wm import plugin, ui, formats

import sqlite

MAX_ROWS = 300
MAX_COLUMNS = 30
MAX_WIDGETS = 1500
MAX_CELL = 200


def _cell(value):
    """A JSON value as one table cell."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    return text if len(text) <= MAX_CELL else text[:MAX_CELL - 1] + "…"


def _number(text):
    if not text:
        return True
    t = text.replace(",", "").replace("_", "").strip()
    if t[:1] in "+-":
        t = t[1:]
    if not t:
        return False
    dots = 0
    for ch in t:
        if ch == ".":
            dots = dots + 1
        elif not ("0" <= ch <= "9"):
            return False
    return dots <= 1


def _align(rows):
    """Numbers to the end of their column, as a spreadsheet lines them up."""
    if not rows:
        return None
    width = max(len(r) for r in rows)
    out = []
    for c in range(width):
        cells = [r[c] for r in rows if c < len(r)]
        numeric = any(cells) and all(_number(x) for x in cells)
        out.append("end" if numeric else "start")
    return out


def _grid(rows, header):
    width = min(max([len(header)] + [len(r) for r in rows]), MAX_COLUMNS)
    header = (list(header) + [""] * width)[:width]
    rows = [(list(r) + [""] * width)[:width] for r in rows]
    ui.table(rows, header=header, align=_align(rows))


# MARK: - CSV

@plugin.preview("table")
def show_table(file):
    text = file.text().replace("\r\n", "\n")
    if not text.strip():
        ui.empty("This file is empty.")
        return
    delimiter = "\t" if file.extension in ("tsv", "tab") else ("|" if file.extension == "psv" else None)
    rows = formats.csv(text, delimiter, MAX_ROWS + 2)
    whole = len(rows) <= MAX_ROWS + 1 and not file.truncated
    rows = [r for r in rows if any(c.strip() for c in r)]
    header = rows[0]
    body = rows[1:MAX_ROWS + 1]
    if whole:
        count = _about(len(body)) + " rows"
    else:
        # Past what was parsed, lines are a fair count of rows.
        lines = text.count("\n") + (0 if text.endswith("\n") else 1)
        if file.truncated and len(text) > 0:
            lines = lines * file.size // len(file.data)
        count = "about " + _about(lines - 1) + " rows"
    ui.caption(f"{count} · {len(header)} columns")
    _grid(body, header)
    if not whole:
        ui.caption(f"The first {len(body)} rows are shown.")


def _about(n):
    return f"{n:,}"


# MARK: - JSON

class Budget:
    def __init__(self):
        self.left = MAX_WIDGETS

    def spend(self, n=1):
        self.left = self.left - n
        return self.left > 0


def _records(items):
    """A list of objects as (header, rows), or None when it is not one."""
    if not items or not all(isinstance(x, dict) for x in items[:50]):
        return None
    keys = []
    for x in items[:50]:
        for k in x.keys():
            if k not in keys and len(keys) < MAX_COLUMNS:
                keys.append(k)
    rows = [[_cell(x.get(k)) if isinstance(x, dict) else _cell(x) for k in keys] for x in items[:MAX_ROWS]]
    return keys, rows


def _scalar(v):
    return not isinstance(v, (dict, list))


def show_value(value, budget, depth):
    if not budget.spend():
        return
    if isinstance(value, dict):
        plain = [(k, v) for k, v in value.items() if _scalar(v)]
        nested = [(k, v) for k, v in value.items() if not _scalar(v)]
        if plain:
            ui.table([[str(k), _cell(v)] for k, v in plain[:MAX_ROWS]], header=["Key", "Value"])
            budget.spend(len(plain) // 20)
        for k, v in nested:
            if budget.left <= 0:
                ui.caption("The rest is not shown.")
                return
            size = f"{len(v)} item" + ("" if len(v) == 1 else "s")
            with ui.section(f"{k}  ·  {size}", collapsible=True, open=depth == 0 and len(nested) <= 3):
                if depth >= 6:
                    ui.code(json.dumps(v, indent=2, ensure_ascii=False)[:20000], language="json")
                else:
                    show_value(v, budget, depth + 1)
        if not value:
            ui.caption("{}")
        return
    if isinstance(value, list):
        if not value:
            ui.caption("[]")
            return
        table = _records(value)
        if table is not None:
            _grid(table[1], table[0])
            budget.spend(len(table[1]) // 20)
        elif all(_scalar(v) for v in value[:MAX_ROWS]):
            ui.table([[str(i), _cell(v)] for i, v in enumerate(value[:MAX_ROWS])], header=["#", "Value"])
        else:
            for i, v in enumerate(value[:100]):
                if budget.left <= 0:
                    break
                with ui.section(f"[{i}]", collapsible=True, open=False):
                    show_value(v, budget, depth + 1)
        if len(value) > MAX_ROWS:
            ui.caption(f"{len(value) - MAX_ROWS} more items")
        return
    ui.output(_cell(value), mono=True)


def _lines(text):
    out = []
    bad = 0
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            bad = bad + 1
        if len(out) > MAX_ROWS:
            break
    return out, bad


@plugin.preview("json")
def show_json(file):
    text = file.text().lstrip("﻿")
    if not text.strip():
        ui.empty("This file is empty.")
        return
    if file.extension in ("jsonl", "ndjson"):
        items, bad = _lines(text)
        ui.caption(f"{_about(len(items))} records" + (f" · {bad} lines are not JSON" if bad else ""))
        show_value(items, Budget(), 0)
        return
    try:
        value = json.loads(text)
    except ValueError as error:
        if file.truncated:
            ui.caption("Only the first part of this file fits; it is shown as text.")
        else:
            ui.caption(f"Not valid JSON: {error}")
        ui.code(text[:200000], language="json")
        return
    if isinstance(value, dict):
        ui.caption(f"{len(value)} keys")
    elif isinstance(value, list):
        ui.caption(f"{_about(len(value))} items")
    show_value(value, Budget(), 0)


# MARK: - notebooks

def _source(cell):
    s = cell.get("source", "")
    return "".join(s) if isinstance(s, list) else str(s)


def _output(out, language):
    kind = out.get("output_type")
    if kind == "stream":
        ui.code(_source({"source": out.get("text", "")})[:20000], line_numbers=False)
    elif kind in ("execute_result", "display_data"):
        data = out.get("data", {})
        picture = data.get("image/png") or data.get("image/jpeg")
        if picture:
            picture = "".join(picture) if isinstance(picture, list) else picture
            picture = "".join(picture.split())
            if len(picture) < 690000:
                ui.image("data:" + picture, alt="Output")
                return
        if "text/markdown" in data:
            ui.markdown(_source({"source": data["text/markdown"]})[:20000])
        elif "text/plain" in data:
            ui.code(_source({"source": data["text/plain"]})[:20000], line_numbers=False)
    elif kind == "error":
        ui.label(f"{out.get('ename', 'Error')}: {out.get('evalue', '')}", color="danger")


@plugin.preview("notebook")
def show_notebook(file):
    try:
        book = file.json()
    except ValueError:
        ui.empty("This notebook is not valid JSON.")
        return
    meta = book.get("metadata", {})
    language = (meta.get("language_info") or {}).get("name") or (meta.get("kernelspec") or {}).get("language") or "python"
    ext = {"python": "py", "r": "r", "julia": "jl", "javascript": "js", "typescript": "ts", "scala": "scala",
           "kotlin": "kt", "rust": "rs", "c++": "cpp", "go": "go", "bash": "sh", "sql": "sql"}.get(language.lower(), language.lower())
    cells = book.get("cells", [])
    if not cells:
        for sheet in book.get("worksheets", []):
            cells = cells + sheet.get("cells", [])
    kernel = (meta.get("kernelspec") or {}).get("display_name")
    ui.caption(f"{len(cells)} cells" + (f" · {kernel}" if kernel else ""))
    budget = Budget()
    for cell in cells:
        if not budget.spend(3):
            ui.caption("The rest of the notebook is not shown.")
            return
        kind = cell.get("cell_type")
        text = _source(cell)
        if kind == "markdown":
            ui.markdown(text[:20000])
        elif kind == "code":
            count = cell.get("execution_count")
            ui.caption(f"In [{count if count is not None else ' '}]")
            ui.code(text[:20000], language=ext)
            for out in cell.get("outputs", [])[:6]:
                _output(out, ext)
        elif text.strip():
            ui.code(text[:20000], line_numbers=False)


# MARK: - SQLite

@plugin.preview("sqlite")
def show_sqlite(file):
    try:
        db = sqlite.Database(file)
    except ValueError as error:
        ui.empty(str(error))
        return
    tables = db.tables()
    views = [t for t in tables if t["type"] == "view"]
    tables = [t for t in tables if t["type"] == "table" and not t["name"].startswith("sqlite_")]
    ui.caption(f"{len(tables)} tables" + (f" · {len(views)} views" if views else "") + f" · SQLite, {db.page_size}-byte pages")
    if not tables:
        ui.empty("This database has no tables.")
    for i, t in enumerate(tables[:40]):
        with ui.section(t["name"], collapsible=True, open=i == 0):
            columns = sqlite.columns(t["sql"])
            try:
                rows = db.rows(t["rootpage"], 100)
            except ValueError as error:
                ui.caption(str(error))
                continue
            if not rows:
                ui.caption("No rows")
            else:
                width = max(len(r) for r in rows)
                header = (columns + [f"col{n + 1}" for n in range(width)])[:max(width, len(columns))]
                _grid([[sqlite.cell(v) for v in r] for r in rows], header)
                if len(rows) == 100:
                    ui.caption("The first 100 rows are shown.")
            if t["sql"]:
                ui.code(t["sql"], language="sql", line_numbers=False)
    for v in views[:20]:
        with ui.section(v["name"] + " (view)", collapsible=True, open=False):
            ui.code(v["sql"] or "", language="sql", line_numbers=False)
