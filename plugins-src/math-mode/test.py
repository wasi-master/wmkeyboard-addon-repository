# Golden tests for Math Mode, run on the interpreter the keyboard ships:
#
#   wm-python-cli test plugins-src/math-mode
#
# (tools/test_plugins.py runs every plugin's test.py that way, or on CPython
# with stand-ins when the CLI is not installed.) The runner provides the
# `plugin_test` module: read(name) returns a file from this folder, and
# load(name, wm, ui) runs a plugin file with the given `wm` and `ui` and
# returns its globals. Both are stubbed here, the same shapes the keyboard
# passes. A failure raises, which makes the run exit non-zero.
#
# Newlines, carriage returns and tabs are written as ␊ ␍ ␉ in the corpus so
# that LaTeX backslashes need no escaping.

import time
import plugin_test

# ---- host stubs ----------------------------------------------------------


def kids(args):
    if len(args) == 1 and isinstance(args[0], list):
        return args[0]
    return list(args)


def u_column(*children):
    return {"type": "column", "children": kids(children)}


def u_row(*children):
    return {"type": "row", "children": kids(children)}


def u_label(text, style=None):
    return {"type": "label", "text": text, "style": style}


def u_output(text, id=None, mono=False, insertable=True, copyable=True):
    return {"type": "output", "id": id, "text": text, "mono": mono,
            "insertable": insertable, "copyable": copyable}


def u_button(id, text, style=None, enabled=True):
    return {"type": "button", "id": id, "text": text, "style": style, "enabled": enabled}


def u_toggle(id, label, checked=False):
    return {"type": "toggle", "id": id, "label": label, "checked": checked}


def u_input(id, label=None, placeholder=None):
    return {"type": "input", "id": id, "label": label, "placeholder": placeholder}


def u_date(id, label=None, value=None, time=False, step=15):
    return {"type": "date", "id": id, "label": label, "value": value, "time": time, "step": step}


def u_spacer(height=8):
    return {"type": "spacer", "height": height}


def u_divider():
    return {"type": "divider"}


def u_progress():
    return {"type": "progress"}


def u_tabs(id, *pages):
    return {"type": "tabs", "id": id, "pages": kids(pages)}


def u_page(title, *children):
    return {"type": "page", "title": title, "children": kids(children)}


ui = {
    "column": u_column, "row": u_row, "label": u_label, "output": u_output,
    "button": u_button, "toggle": u_toggle, "input": u_input, "date": u_date,
    "spacer": u_spacer, "divider": u_divider, "progress": u_progress,
    "tabs": u_tabs, "page": u_page,
}

store = {}
writes = []


def w_log(*values):
    pass


def w_set_input(id, text):
    writes.append([id, text])


def s_get(key, default=None):
    return store.get(key, default)


def s_set(key, value):
    store[key] = value


def s_remove(key):
    store.pop(key, None)


def s_keys():
    return sorted(store.keys())


wm = {
    "api_version": 4, "plugin_id": "com.wasimaster.mathmode", "plugin_version": "test",
    "log": w_log,
    "ui": {"set_input": w_set_input},
    "storage": {"get": s_get, "set": s_set, "remove": s_remove, "keys": s_keys},
}

# ---- load the plugin ----------------------------------------------------

plugin = plugin_test.load("main.py", wm, ui)
for name in ["convert", "default_options", "render", "on_event", "char_units"]:
    if not callable(plugin.get(name)):
        raise RuntimeError("main.py must define " + name + "()")
convert = plugin["convert"]
default_options = plugin["default_options"]
render = plugin["render"]
on_event = plugin["on_event"]
char_units = plugin["char_units"]

# ---- helpers -------------------------------------------------------------


def unescape(s):
    return s.replace("␊", "\n").replace("␍", "\r").replace("␉", "\t")


def show(s):
    return s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def utf16_units(s):
    n = 0
    for c in s:
        n += char_units(c)
    return n


OPT_FLAGS = {
    "chem": ["chem", True], "nominus": ["minus", False], "dot": ["times", False],
    "words": ["words", True], "rootline": ["rootline", True], "italic": ["italic", True],
    "noprime": ["prime", False], "nofrac": ["frac", False], "nosmall": ["small", False],
}

# ---- walk a rendered tree ----------------------------------------------


def outputs(tree):
    """The text of every output block, in order. Iterative, like the engine."""
    found = []
    stack = [tree]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        if node.get("type") == "output":
            found.append(node.get("text") or "")
        below = (node.get("children") or []) + (node.get("pages") or [])
        for child in reversed(below):
            stack.append(child)
    return found


def check_tree(tree, label, fails):
    nodes = 0
    deepest = 0
    stack = [[tree, 1]]
    while stack:
        node, depth = stack.pop()
        if not isinstance(node, dict):
            continue
        nodes += 1
        if depth > deepest:
            deepest = depth
        for key in ["text", "label", "placeholder", "title"]:
            s = node.get(key)
            if isinstance(s, str) and utf16_units(s) > 2048:
                fails.append(label + ": " + key + " has " + str(utf16_units(s)) + " units (limit 2048)")
        pages = node.get("pages") or []
        if len(pages) > 8:
            fails.append(label + ": more than 8 tabs")
        for child in (node.get("children") or []) + pages:
            stack.append([child, depth + 1])
    if nodes > 256:
        fails.append(label + ": " + str(nodes) + " nodes (limit 256)")
    if deepest > 12:
        fails.append(label + ": tree depth " + str(deepest) + " (limit 12)")


def set_options(opts):
    for key in opts:
        on_event({"type": "toggle", "id": key, "value": opts[key]})


# ---- the corpus ---------------------------------------------------------

fails = []
total = 0
lineno = 0
for line in plugin_test.read("cases.txt").split("\n"):
    lineno += 1
    if line.endswith("\r"):
        line = line[:-1]
    if line == "" or line.startswith("#"):
        continue
    fields = line.split("\t")
    opts = default_options()
    if fields[0].startswith("@"):
        for name in fields[0][1:].split(","):
            if name not in OPT_FLAGS:
                raise RuntimeError("line " + str(lineno) + ": unknown option tag " + name)
            opts[OPT_FLAGS[name][0]] = OPT_FLAGS[name][1]
        fields = fields[1:]
    if len(fields) < 2:
        raise RuntimeError("line " + str(lineno) + ": expected two tab-separated columns")
    source = unescape(fields[0])
    expected = unescape(fields[1])
    total += 1

    # 1. the engine directly
    got = convert(source, opts)
    if got != expected:
        fails.append("line %d: %s\n    expected  %s\n    got       %s" % (lineno, show(source), show(expected), show(got)))

    # 2. the real event path: toggles, then a keystroke, then render()
    set_options(opts)
    on_event({"type": "input_changed", "id": "expr", "value": source})
    tree = render()
    joined = "".join(outputs(tree))
    if joined != expected:
        fails.append("line %d (event path): %s\n    expected  %s\n    got       %s" % (lineno, show(source), show(expected), show(joined)))
    check_tree(tree, "line " + str(lineno), fails)

# reset options for the rest
set_options(default_options())

# ---- adversarial inputs ---------------------------------------------------

# The host gives an event 2 seconds; a conversion runs inside one.
TIME_LIMIT = 2.0


def big(name, source, expect_unchanged=False):
    global total
    total += 1
    t0 = time.monotonic()
    try:
        got = convert(source, default_options())
    except Exception as error:
        fails.append(name + ": convert raised " + str(error))
        return None
    took = time.monotonic() - t0
    if expect_unchanged and got != source:
        fails.append(name + ": expected the input back unchanged")
    if took > TIME_LIMIT:
        fails.append("%s: took %.2fs" % (name, took))
    on_event({"type": "input_changed", "id": "expr", "value": source})
    tree = render()
    n = 0
    for o in outputs(tree):
        n += 1
        if utf16_units(o) > 2000:
            fails.append(name + ": output chunk " + str(n) + " has " + str(utf16_units(o)) + " units")
    check_tree(tree, name, fails)
    return got


big("8K carets", "^" * 8192, True)
big("8K opens", "(" * 8192, True)
big("deep nest", "(" * 4096 + "x" + ")" * 4096 + "^2", True)
big("caret chain", "a" + "^b" * 2000)
big("slash chain", "1" + "/2" * 2000, True)
big("8K word", "z" * 8192, True)
big("frac chain", "\\frac{" * 1000, True)
big("quotes", '"' * 4000)
big("emoji", "😀" * 2048, True)

many = "x^2\n" * 2000
if big("many lines", many) != "x²\n" * 2000:
    fails.append("many lines: wrong conversion")
on_event({"type": "input_changed", "id": "expr", "value": many})
outs = outputs(render())
if len(outs) < 2:
    fails.append("many lines: expected the output to be chunked, got " + str(len(outs)) + " block(s)")
if "".join(outs) != "x²\n" * 2000:
    fails.append("many lines: chunks do not join back to the whole")

# ---- panel behaviour ------------------------------------------------------

total += 1
on_event({"type": "click", "id": "clear"})
on_event({"type": "input_changed", "id": "expr", "value": "x^2"})
writes.clear()
on_event({"type": "click", "id": "sym:π"})
if len(writes) != 1 or writes[0][0] != "expr" or writes[0][1] != "x^2π":
    fails.append("symbol tap: expected one set_input('expr', 'x^2π'), got " + str(len(writes)))
if "".join(outputs(render())) != "x²π":
    fails.append("symbol tap: output did not update")

total += 1
on_event({"type": "toggle", "id": "chem", "value": True})
if "chem=1" not in store.get("options", ""):
    fails.append("toggle: chem=1 was not written to storage (" + str(store.get("options")) + ")")
on_event({"type": "click", "id": "reset_opts"})
if "chem=0" not in store.get("options", ""):
    fails.append("reset: chem=0 was not written to storage")

total += 1
on_event({"type": "click", "id": "clear"})
empty = render()
if len(outputs(empty)) != 0:
    fails.append("empty box should show a caption, not an output block")
check_tree(empty, "empty panel", fails)

# ---- report ---------------------------------------------------------------

if fails:
    print("%d of %d checks failed:" % (len(fails), total))
    for message in fails:
        print("  " + message)
    raise RuntimeError("math-mode: " + str(len(fails)) + " checks failed")
print("math-mode: %d checks passed" % total)
