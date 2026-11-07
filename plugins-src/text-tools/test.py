# Tests for Text Tools, run by tools/test_plugins.py (on wm-python-cli, or
# on CPython stand-ins). `plugin_test` is the runner's module: load(name, wm,
# ui) runs a plugin file with the given host and returns its globals.
#
# The encoders work on UTF-8 bytes, and plugin strings are grapheme clusters,
# so the cases include characters made of several code points ("কি", "x̂").

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

writes = []


def w_log(*values):
    pass


def w_set_input(id, text):
    writes.append([id, text])


wm = {
    "api_version": 4, "plugin_id": "com.wasimaster.texttools", "plugin_version": "test",
    "log": w_log, "ui": {"set_input": w_set_input},
}

plugin = plugin_test.load("main.py", wm, ui)
fails = []


def expect(what, got, want):
    if got != want:
        fails.append(what + ": expected " + repr(want) + ", got " + repr(got))


def run(action, text):
    plugin["on_event"]({"type": "input_changed", "id": "text", "value": text})
    plugin["on_event"]({"type": "click", "id": action})
    return plugin["output"]


CASES = [
    ["Hello, World", "SGVsbG8sIFdvcmxk", "48656c6c6f2c20576f726c64", "Hello%2C%20World"],
    ["কি", "4KaV4Ka/", "e0a695e0a6bf", "%E0%A6%95%E0%A6%BF"],
    ["😀", "8J+YgA==", "f09f9880", "%F0%9F%98%80"],
    ["x̂", "eMyC", "78cc82", "x%CC%82"],
]
for case in CASES:
    source = case[0]
    expect("base64 " + source, run("b64_encode", source), case[1])
    expect("hex " + source, run("hex_encode", source), case[2])
    expect("url " + source, run("url_encode", source), case[3])
    expect("un-base64 " + source, run("b64_decode", case[1]), source)
    expect("un-hex " + source, run("hex_decode", case[2]), source)
    expect("un-url " + source, run("url_decode", case[3]), source)

expect("un-hex keeps what is not hex", run("hex_decode", "48 zz 69"), "Hzzi")
expect("un-base64 of junk", run("b64_decode", "!!"), "")
expect("bad UTF-8 becomes U+FFFD", run("hex_decode", "ff41"), "\uFFFDA")
expect("upper", run("upper", "abc def"), "ABC DEF")
expect("lower", run("lower", "ABC DEF"), "abc def")
expect("title", run("title", "don't STOP 3rd time"), "Don't Stop 3Rd Time")
expect("reverse", run("reverse", "abc"), "cba")
expect("count", run("stats", "two words\nnext"), "14 characters\n12 letters\n3 words\n2 lines")
expect("count nothing", run("stats", ""), "0 characters\n0 letters\n0 words\n0 lines")

plugin["on_event"]({"type": "click", "id": "clear"})
expect("clear empties the box", writes[-1], ["text", ""])
expect("clear empties the result", plugin["output"], "")

if fails:
    for message in fails:
        print("  " + message)
    raise RuntimeError("text-tools: " + str(len(fails)) + " checks failed")
print("text-tools: all checks passed")
