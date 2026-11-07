#!/usr/bin/env python3
"""A stand-in for WM Keyboard's plugin host, for checking plugins on CPython.

Dev and CI helper only; nothing here ships. The keyboard runs plugins on
wm-python, a Rust port of PyMini. Until `wm-python-cli` is installed, this
module lets tools/test_plugins.py run a plugin on CPython with:

* stub `wm` and `ui` globals that follow the Python plugin API (API 4),
* a stub `time` module with PyMini's `time()`, `monotonic()`, `parts()` and
  `format(pattern)` (Unicode date patterns, English names),
* `check_subset()`, a lint that refuses Python PyMini does not have,
* `check_tree()`, the widget caps the host enforces,
* `smoke()`, which renders a plugin and touches every widget it shows,
* `run_test()`, which runs a plugin's test.py against a `plugin_test` module
  shaped like the one wm-python-cli provides.

CPython is not PyMini. The differences that matter for plugins:

* PyMini strings are sequences of grapheme clusters, CPython's of code points.
  `len`, indexing, slicing and iteration differ for text with combining marks,
  emoji sequences or "\\r\\n" (one cluster). `ord()` refuses a cluster of more
  than one code point.
* PyMini compares strings by canonical equivalence (NFC): "e\\u0301" == "é".
* `int("3.5")` is 3 in PyMini and a ValueError in CPython.
* `type(x)` returns a string in PyMini.
* `str.title()` is Foundation's `capitalized` in PyMini ("don't" stays
  "Don't"; CPython gives "Don'T").
* Dicts answer attribute reads in PyMini (`e.type`); on CPython only the
  dicts this module builds do.

Plugins should not lean on any of these; the lint catches the ones a parser can.

    python3 tools/pyplugin_host.py lint plugins-src/*/main.py
    python3 tools/pyplugin_host.py smoke plugins-src/cipher-tool
    python3 tools/pyplugin_host.py test plugins-src/math-mode
"""

from __future__ import annotations

import ast
import json
import sys
import time as _real_time
import types
from pathlib import Path

API_VERSION = 4

# ----------------------------------------------------------------- the lint --

BUILTINS = {
    "len", "str", "repr", "print", "int", "float", "bool", "abs", "round",
    "min", "max", "sum", "range", "sorted", "reversed", "list", "dict", "set",
    "tuple", "enumerate", "zip", "ord", "chr", "any", "all", "type",
    "map", "filter", "divmod", "pow", "hex", "bin", "oct", "format",
    "isinstance", "callable",
}
EXCEPTIONS = {
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "NameError", "ZeroDivisionError", "AttributeError", "RuntimeError", "StopIteration",
}
EXCEPT_CLAUSES = EXCEPTIONS | {"LookupError", "ArithmeticError"}
KWARG_BUILTINS = {"sorted", "min", "max", "round"}

MODULES = {
    "math": {
        "sqrt", "floor", "ceil", "trunc", "fabs", "pow", "exp", "log", "log2",
        "log10", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
        "degrees", "radians", "hypot", "gcd", "lcm", "factorial",
        "isnan", "isinf", "isfinite", "copysign", "fmod", "comb", "prod",
        "pi", "e", "tau", "inf", "nan",
    },
    "random": {"random", "randint", "randrange", "choice", "choices", "shuffle", "sample", "uniform", "seed"},
    "time": {"time", "monotonic", "parts", "format"},
    "json": {"dumps", "loads"},
    "re": {
        "search", "match", "fullmatch", "findall", "finditer", "sub", "subn", "split", "escape",
        "I", "IGNORECASE", "M", "MULTILINE", "S", "DOTALL",
    },
    "sys": {"version"},
}

# Every method PyMini has on str, list, dict, set and regex matches. A call to
# anything else on a value is refused, since the lint cannot tell the types.
METHODS = {
    # str
    "upper", "lower", "casefold", "title", "capitalize", "swapcase", "strip", "lstrip",
    "rstrip", "replace", "split", "rsplit", "splitlines", "join", "startswith", "endswith",
    "find", "rfind", "index", "rindex", "count", "partition", "rpartition", "zfill",
    "ljust", "rjust", "center", "isdigit", "isnumeric", "isalpha", "isalnum", "isspace",
    "isupper", "islower", "istitle", "removeprefix", "removesuffix", "format",
    # list
    "append", "extend", "pop", "insert", "remove", "sort", "reverse", "clear", "copy",
    # dict
    "keys", "values", "items", "get", "popitem", "setdefault", "update",
    # set
    "add", "discard", "union", "intersection", "difference", "symmetric_difference",
    "issubset", "issuperset", "isdisjoint",
    # re match
    "group", "groups", "groupdict", "start", "end", "span",
}

# Members of the host's own globals, for the "is this a real API?" check.
HOST_API = {
    "wm": {
        "log", "plugin_id", "plugin_version", "api_version", "ui", "storage", "reminders",
        "timestamp",
    },
    "wm.ui": {"set_input"},
    "wm.storage": {"get", "set", "remove", "keys"},
    "wm.reminders": {"set", "cancel", "list"},
    "ui": {
        "column", "row", "label", "output", "button", "toggle", "input", "date",
        "spacer", "divider", "progress", "tabs", "page",
    },
}

HOOKS = {"render", "on_event", "transform"}


def _dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def check_subset(path: Path, host_globals: bool = True) -> list[str]:
    """Problems that would stop `path` running on PyMini, as "file:line: what"."""
    source = path.read_text(encoding="utf-8")
    problems: list[str] = []

    def bad(node: ast.AST, what: str) -> None:
        problems.append(f"{path}:{getattr(node, 'lineno', 0)}: {what}")

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        return [f"{path}:{error.lineno}: {error.msg}"]

    allowed = dict(MODULES)
    if not host_globals:
        # test.py runs under wm-python-cli, which adds this module.
        allowed["plugin_test"] = {"read", "load"}
    bound: set[str] = set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in allowed:
                    bad(node, f"module {alias.name!r} is not available (only {', '.join(sorted(allowed))})")
                bound.add(alias.asname or alias.name)
                if not alias.asname:
                    modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module not in allowed:
                bad(node, f"module {node.module!r} is not available")
            for alias in node.names:
                if alias.name == "*":
                    bad(node, "'from … import *' is not supported")
                elif node.module in allowed and alias.name not in allowed[node.module]:
                    bad(node, f"{node.module}.{alias.name} does not exist in PyMini")
                bound.add(alias.asname or alias.name)

    known = bound | BUILTINS | EXCEPTIONS | ({"wm", "ui"} if host_globals else set())

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bad(node, "'class' is not supported")
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            bad(node, "'with' is not supported")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await)):
            bad(node, "async is not supported")
        elif isinstance(node, (ast.Yield, ast.YieldFrom)):
            bad(node, "'yield' is not supported")
        elif isinstance(node, ast.Nonlocal):
            bad(node, "'nonlocal' is not supported; keep state in module globals")
        elif isinstance(node, ast.Assert):
            bad(node, "'assert' is not supported")
        elif isinstance(node, ast.Match):
            bad(node, "'match' is not supported")
        elif isinstance(node, ast.NamedExpr):
            bad(node, "':=' is not supported")
        elif isinstance(node, ast.FunctionDef):
            if node.decorator_list:
                bad(node, "decorators are not supported")
            a = node.args
            if a.kwarg:
                bad(node, "**kwargs is not supported")
            if a.kwonlyargs or a.posonlyargs:
                bad(node, "keyword-only and positional-only parameters are not supported")
        elif isinstance(node, ast.Lambda):
            a = node.args
            if a.kwarg or a.kwonlyargs or a.posonlyargs:
                bad(node, "lambda parameters beyond a, b=1, *rest are not supported")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.LShift, ast.RShift, ast.MatMult)):
            bad(node, f"operator {type(node.op).__name__} is not supported")
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
            bad(node, "'~' is not supported")
        elif isinstance(node, ast.AugAssign) and not isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.FloorDiv, ast.Pow)
        ):
            bad(node, f"augmented {type(node.op).__name__} is not supported")
        elif isinstance(node, ast.Starred) and isinstance(node.ctx, ast.Store):
            bad(node, "starred assignment targets are not supported")
        elif isinstance(node, ast.Constant) and isinstance(node.value, (bytes, complex)):
            bad(node, "bytes and complex literals are not supported")
        elif isinstance(node, ast.ExceptHandler) and node.type is not None:
            types_ = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
            for t in types_:
                if not isinstance(t, ast.Name) or t.id not in EXCEPT_CLAUSES:
                    bad(node, f"except {ast.unparse(t)}: PyMini only knows {', '.join(sorted(EXCEPT_CLAUSES))}")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in known:
                bad(node, f"name {node.id!r} is not defined in PyMini")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BUILTINS and func.id not in bound:
                if node.keywords and func.id not in KWARG_BUILTINS:
                    bad(node, f"{func.id}() takes no keyword arguments in PyMini")
                if func.id == "type":
                    bad(node, "type() returns a string in PyMini; use isinstance()")
            if any(k.arg is None for k in node.keywords):
                bad(node, "**mapping in a call is not supported")
            if isinstance(func, ast.Attribute):
                dotted = _dotted(func.value)
                root = dotted.split(".")[0] if dotted else None
                if dotted in modules and root not in bound - modules:
                    if func.attr not in allowed[dotted]:
                        bad(node, f"{dotted}.{func.attr}() does not exist in PyMini")
                elif dotted in HOST_API and host_globals and root not in bound:
                    if func.attr not in HOST_API[dotted]:
                        bad(node, f"{dotted}.{func.attr}() is not part of the plugin API")
                elif func.attr not in METHODS:
                    bad(node, f".{func.attr}() is not a PyMini method on str, list, dict or set")
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            dotted = _dotted(node.value)
            if dotted in HOST_API and host_globals and dotted.split(".")[0] not in bound:
                if node.attr not in HOST_API[dotted]:
                    bad(node, f"{dotted}.{node.attr} is not part of the plugin API")
    return problems


# -------------------------------------------------------------- dict access --


class AttrDict(dict):
    """A dict that also answers attribute reads, keys first, as PyMini's do."""

    def __getattribute__(self, name):
        if not name.startswith("__") and dict.__contains__(self, name):
            return dict.__getitem__(self, name)
        return dict.__getattribute__(self, name)


def attr_tree(value):
    """Wraps every dict under `value` so attribute reads work on CPython."""
    if isinstance(value, dict):
        return AttrDict({k: attr_tree(v) for k, v in value.items()})
    return value


# ------------------------------------------------------------- stub `time` --

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _parts(t=None):
    lt = _real_time.localtime(_real_time.time() if t is None else t)
    return {
        "year": lt.tm_year, "month": lt.tm_mon, "day": lt.tm_mday,
        "hour": lt.tm_hour, "minute": lt.tm_min, "second": lt.tm_sec,
        "weekday": lt.tm_wday, "yearday": lt.tm_yday,
    }


def _format(pattern, t=None):
    """A Unicode date pattern ("EEE d MMM yyyy, HH:mm"), as PyMini's time.format."""
    if not isinstance(pattern, str):
        raise TypeError('time.format() needs a pattern like "yyyy-MM-dd"')
    p = _parts(t)
    out = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "'":
            j = pattern.find("'", i + 1)
            if j == i + 1:
                out.append("'")
                i += 2
                continue
            if j < 0:
                raise ValueError("invalid date pattern: unterminated quote")
            out.append(pattern[i + 1:j])
            i = j + 1
            continue
        if not c.isalpha():
            out.append(c)
            i += 1
            continue
        j = i
        while j < len(pattern) and pattern[j] == c:
            j += 1
        n = j - i
        i = j
        hour12 = p["hour"] % 12 or 12
        if c == "y":
            out.append(str(p["year"] % 100).zfill(2) if n == 2 else str(p["year"]).zfill(n))
        elif c == "M":
            out.append(MONTHS[p["month"] - 1] if n >= 4 else MONTHS[p["month"] - 1][:3] if n == 3
                       else str(p["month"]).zfill(n))
        elif c == "d":
            out.append(str(p["day"]).zfill(n))
        elif c == "E":
            out.append(DAYS[p["weekday"]] if n >= 4 else DAYS[p["weekday"]][:3])
        elif c == "H":
            out.append(str(p["hour"]).zfill(n))
        elif c == "h":
            out.append(str(hour12).zfill(n))
        elif c == "m":
            out.append(str(p["minute"]).zfill(n))
        elif c == "s":
            out.append(str(p["second"]).zfill(n))
        elif c == "a":
            out.append("AM" if p["hour"] < 12 else "PM")
        elif c == "D":
            out.append(str(p["yearday"]).zfill(n))
        else:
            raise ValueError(f"invalid date pattern letter {c!r}")
    return "".join(out)


def make_time_module() -> types.ModuleType:
    m = types.ModuleType("time")
    m.time = _real_time.time
    m.monotonic = _real_time.monotonic
    m.parts = _parts
    m.format = _format
    return m


# ------------------------------------------------------------ stub `ui`/`wm` --


def _children(args):
    if len(args) == 1 and isinstance(args[0], list):
        return list(args[0])
    return list(args)


def make_ui():
    """The `ui` builders. Each returns a plain dict, as the host's do."""

    def column(*children):
        return {"type": "column", "children": _children(children)}

    def row(*children):
        return {"type": "row", "children": _children(children)}

    def label(text, style=None):
        return {"type": "label", "text": text, "style": style}

    def output(text, id=None, mono=False, insertable=True, copyable=True):
        return {"type": "output", "id": id, "text": text, "mono": mono,
                "insertable": insertable, "copyable": copyable}

    def button(id, text, style=None, enabled=True):
        return {"type": "button", "id": id, "text": text, "style": style, "enabled": enabled}

    def toggle(id, label, checked=False):
        return {"type": "toggle", "id": id, "label": label, "checked": checked}

    def input(id, label=None, placeholder=None):
        return {"type": "input", "id": id, "label": label, "placeholder": placeholder}

    def date(id, label=None, value=None, time=False, step=15):
        return {"type": "date", "id": id, "label": label, "value": value, "time": time, "step": step}

    def spacer(height=8):
        return {"type": "spacer", "height": height}

    def divider():
        return {"type": "divider"}

    def progress():
        return {"type": "progress"}

    def tabs(id, *pages):
        return {"type": "tabs", "id": id, "pages": _children(pages)}

    def page(title, *children):
        return {"type": "page", "title": title, "children": _children(children)}

    return attr_tree({name: fn for name, fn in locals().items() if callable(fn)})


STORAGE_QUOTA = 64 * 1024
REMINDER_CAP = 64


class Host:
    """The state behind one stub `wm`: storage, reminders, log, input writes."""

    def __init__(self, plugin_id="test.plugin", version="0.0.0", permissions=(), storage=None):
        self.storage = dict(storage or {})
        self.reminders: dict[str, tuple[int, str]] = {}
        self.log: list[str] = []
        self.inputs: list[tuple[str, str]] = []
        self.permissions = set(permissions)
        self.plugin_id = plugin_id
        self.version = version

    def wm(self):
        host = self

        def log(*values):
            host.log.append(" ".join(str(v) for v in values)[:512])

        def set_input(id, text):
            if not isinstance(text, str):
                raise TypeError("set_input() needs a string")
            host.inputs.append((id, text[:8192]))

        def get(key, default=None):
            return host.storage.get(key, default)

        def set_(key, value):
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError("storage keys and values are strings")
            used = sum(len(k) + len(v) for k, v in host.storage.items() if k != key)
            if used + len(key) + len(value) > STORAGE_QUOTA:
                raise ValueError("storage quota exceeded")
            host.storage[key] = value

        def remove(key):
            host.storage.pop(key, None)

        def keys():
            return sorted(host.storage)

        def r_set(id, seconds, text):
            if not isinstance(seconds, (int, float)) or seconds <= _real_time.time():
                raise ValueError("a reminder needs a time in the future")
            if id not in host.reminders and len(host.reminders) >= REMINDER_CAP:
                raise ValueError("too many reminders")
            host.reminders[str(id)] = (int(seconds), str(text))

        def r_cancel(id):
            return host.reminders.pop(str(id), None) is not None

        def r_list():
            return [{"id": k, "time": t, "text": x} for k, (t, x) in sorted(host.reminders.items())]

        def timestamp(year, month, day, hour=12, minute=0, second=0):
            return int(_real_time.mktime((year, month, day, hour, minute, second, 0, 0, -1)))

        w = {
            "api_version": API_VERSION,
            "plugin_id": self.plugin_id,
            "plugin_version": self.version,
            "log": log,
            "timestamp": timestamp,
            "ui": {"set_input": set_input},
        }
        if "storage" in self.permissions:
            w["storage"] = {"get": get, "set": set_, "remove": remove, "keys": keys}
        if "reminders" in self.permissions:
            w["reminders"] = {"set": r_set, "cancel": r_cancel, "list": r_list}
        return attr_tree(w)


def load(path: Path, wm, ui) -> dict:
    """Runs a plugin file with the given `wm` and `ui`, returns its globals."""
    path = Path(path)
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    saved = sys.modules.get("time")
    sys.modules["time"] = make_time_module()
    host_print = None
    try:
        log = wm["log"] if isinstance(wm, dict) else wm.log
        host_print = log
    except (KeyError, AttributeError):
        pass
    scope = {"wm": attr_tree(wm), "ui": attr_tree(ui), "__name__": "plugin"}
    if host_print:
        scope["print"] = host_print
    try:
        exec(code, scope)
    finally:
        if saved is not None:
            sys.modules["time"] = saved
    return scope


def load_plugin(folder: Path, host: Host | None = None):
    """Loads plugins-src/<folder> as the keyboard would. Returns (globals, host)."""
    folder = Path(folder)
    manifest = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
    if host is None:
        host = Host(manifest["id"], manifest.get("pluginVersion", "0"), manifest.get("permissions", []))
    entry = folder / manifest.get("entry", "main.py")
    return load(entry, host.wm(), make_ui()), host


# --------------------------------------------------------------- tree caps --

MAX_NODES = 256
MAX_DEPTH = 12
MAX_TEXT = 2048
MAX_TOTAL_TEXT = 64 * 1024
MAX_TABS = 8
TEXT_KEYS = ("text", "label", "placeholder", "title")
KINDS = {"column", "row", "label", "output", "button", "toggle", "input", "date",
         "spacer", "divider", "progress", "tabs", "page"}


def utf16_units(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def check_tree(tree) -> list[str]:
    """The host's widget caps, as problems. `tree` is what render() returned."""
    problems: list[str] = []
    stats = {"nodes": 0, "text": 0}

    def visit(node, depth, where):
        if node is None or node is False:
            return
        if isinstance(node, list):
            for i, child in enumerate(node):
                visit(child, depth, f"{where}[{i}]")
            return
        if not isinstance(node, dict) or node.get("type") not in KINDS:
            problems.append(f"{where}: not a widget: {node!r:.80}")
            return
        stats["nodes"] += 1
        if depth > MAX_DEPTH:
            problems.append(f"{where}: deeper than {MAX_DEPTH}")
        for key in TEXT_KEYS:
            s = node.get(key)
            if s is None:
                continue
            if not isinstance(s, str):
                problems.append(f"{where}.{key}: not a string: {s!r:.40}")
                continue
            n = utf16_units(s)
            stats["text"] += n
            if n > MAX_TEXT:
                problems.append(f"{where}.{key}: {n} UTF-16 units (limit {MAX_TEXT})")
        if node["type"] == "tabs":
            pages = node.get("pages") or []
            if len(pages) > MAX_TABS:
                problems.append(f"{where}: {len(pages)} tabs (limit {MAX_TABS})")
            for i, p in enumerate(pages):
                if not isinstance(p, dict) or p.get("type") != "page":
                    problems.append(f"{where}.pages[{i}]: not a page")
                visit(p, depth + 1, f"{where}.pages[{i}]")
        for i, child in enumerate(node.get("children") or []):
            visit(child, depth + 1, f"{where}.{node['type']}[{i}]")

    visit(tree, 1, "render()")
    if stats["nodes"] > MAX_NODES:
        problems.append(f"render(): {stats['nodes']} widgets (limit {MAX_NODES})")
    if stats["text"] > MAX_TOTAL_TEXT:
        problems.append(f"render(): {stats['text']} UTF-16 units of text (limit {MAX_TOTAL_TEXT})")
    return problems


def widgets(tree, kind=None):
    """Every widget in a rendered tree, depth first, optionally of one type."""
    found = []

    def visit(node):
        if isinstance(node, list):
            for c in node:
                visit(c)
            return
        if not isinstance(node, dict):
            return
        if kind is None or node.get("type") == kind:
            found.append(node)
        for c in node.get("pages") or []:
            visit(c)
        for c in node.get("children") or []:
            visit(c)

    visit(tree)
    return found


# ------------------------------------------------------------------ smoke --

SAMPLE_INPUTS = ["Hello, World 42", "3", "x^2 + sqrt(2) = pi/4", "কিবোর্ড é \U0001F600", ""]


def event(type_, id_, value=None, index=None):
    e = {"type": type_, "id": id_}
    if value is not None or type_ == "date_changed":
        e["value"] = value
    if index is not None:
        e["index"] = index
    return AttrDict(e)


def smoke(folder: Path, rounds: int = 2) -> list[str]:
    """Renders the plugin and touches everything it shows, checking each tree."""
    folder = Path(folder)
    problems: list[str] = []
    try:
        plugin, host = load_plugin(folder)
    except Exception as error:  # noqa: BLE001 - report, don't crash the run
        return [f"{folder.name}: load raised {error!r}"]
    if "render" not in plugin:
        if "transform" in plugin:
            return problems
        return [f"{folder.name}: no render()"]

    def render(label):
        try:
            tree = plugin["render"]()
        except Exception as error:  # noqa: BLE001
            problems.append(f"{folder.name}: render() after {label} raised {error!r}")
            return None
        for p in check_tree(tree):
            problems.append(f"{folder.name} after {label}: {p}")
        return tree

    def send(e, label):
        try:
            plugin["on_event"](e)
        except Exception as error:  # noqa: BLE001
            problems.append(f"{folder.name}: on_event({dict(e)}) raised {error!r}")
        return render(label)

    tree = render("load")
    if tree is None:
        return problems
    tomorrow = int(_real_time.time()) + 86400
    for r in range(rounds):
        for text in SAMPLE_INPUTS:
            for w in widgets(tree, "input"):
                tree = send(event("input_changed", w["id"], text), f"typing {text!r}") or tree
            for w in widgets(tree, "date"):
                tree = send(event("date_changed", w["id"], tomorrow + r * 3600), "a date") or tree
            for w in widgets(tree, "toggle"):
                tree = send(event("toggle", w["id"], not w.get("checked")), f"toggle {w['id']}") or tree
            for w in widgets(tree, "button"):
                if w.get("enabled", True) is not False:
                    tree = send(event("click", w["id"]), f"click {w['id']}") or tree
            for w in widgets(tree, "tabs"):
                for i, _ in enumerate(w.get("pages") or []):
                    tree = send(event("tab_selected", w["id"], index=i), f"tab {i}") or tree
        for w in widgets(tree, "date"):
            tree = send(event("date_changed", w["id"], None), "clearing a date") or tree
    return problems


# ------------------------------------------------------------- test.py runs --


def run_test(folder: Path) -> int:
    """Runs folder/test.py on CPython with the `plugin_test` module the CLI offers."""
    folder = Path(folder)
    module = types.ModuleType("plugin_test")
    module.read = lambda name: (folder / name).read_text(encoding="utf-8")
    module.load = lambda name, wm, ui: load(folder / name, wm, ui)
    saved_test = sys.modules.get("plugin_test")
    saved_time = sys.modules.get("time")
    sys.modules["plugin_test"] = module
    sys.modules["time"] = make_time_module()
    code = compile((folder / "test.py").read_text(encoding="utf-8"), str(folder / "test.py"), "exec")
    try:
        exec(code, {"__name__": "test"})
    except Exception as error:  # noqa: BLE001
        print(f"   {type(error).__name__}: {error}")
        return 1
    finally:
        sys.modules["time"] = saved_time
        if saved_test is None:
            sys.modules.pop("plugin_test", None)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in {"lint", "smoke", "test"}:
        print(__doc__)
        return 2
    failed = 0
    for arg in argv[1:]:
        path = Path(arg)
        if argv[0] == "lint":
            problems = check_subset(path, host_globals=path.name != "test.py")
        elif argv[0] == "smoke":
            problems = smoke(path)
        else:
            problems = ["test.py failed"] if run_test(path) else []
        for p in problems:
            print(p)
        failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
