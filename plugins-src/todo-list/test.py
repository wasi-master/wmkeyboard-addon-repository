# Tests for Todo List, run by tools/test_plugins.py (on wm-python-cli, or on
# CPython stand-ins). `plugin_test` is the runner's module: load(name, wm, ui)
# runs a plugin file with the given host and returns its globals.
#
# What matters most here is the storage key `items`: the Lua versions wrote
# it, the app's Todo import reads it, and both must keep working. It holds a
# JSON array of {id, text, done, due, remind}, with `due` a whole number of
# seconds and left out when there is none.

import json
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
reminders = {}
quota_full = [False]


def w_log(*values):
    pass


def w_set_input(id, text):
    writes.append([id, text])


def s_get(key, default=None):
    return store.get(key, default)


def s_set(key, value):
    if quota_full[0]:
        raise ValueError("storage quota exceeded")
    if not isinstance(value, str):
        raise TypeError("storage values are strings")
    store[key] = value


def s_remove(key):
    store.pop(key, None)


def s_keys():
    return sorted(store.keys())


def r_set(id, seconds, text):
    if seconds <= time.time():
        raise ValueError("a reminder needs a time in the future")
    reminders[id] = [seconds, text]


def r_cancel(id):
    return reminders.pop(id, None) is not None


def r_list():
    return [{"id": k, "time": reminders[k][0], "text": reminders[k][1]} for k in sorted(reminders.keys())]


def stamp(year, month, day, hour=12, minute=0, second=0):
    # Good enough for the test: the plugin only compares days with it.
    return int(time.time()) // 86400 * 86400 + (day - time.parts()["day"]) * 86400 + hour * 3600


wm = {
    "api_version": 4, "plugin_id": "com.wasimaster.todo", "plugin_version": "test",
    "log": w_log, "timestamp": stamp,
    "ui": {"set_input": w_set_input},
    "storage": {"get": s_get, "set": s_set, "remove": s_remove, "keys": s_keys},
    "reminders": {"set": r_set, "cancel": r_cancel, "list": r_list},
}

fails = []


def expect(what, got, want):
    if got != want:
        fails.append(what + ": expected " + repr(want) + ", got " + repr(got))


def saved():
    return json.loads(store["items"])


def check_shape(items):
    for item in items:
        for key in ["id", "text", "done", "remind"]:
            if key not in item:
                fails.append("saved item " + repr(item) + " has no " + key)
        if not isinstance(item.get("id"), int) or isinstance(item.get("id"), bool):
            fails.append("id is not a whole number: " + repr(item))
        if not isinstance(item.get("done"), bool) or not isinstance(item.get("remind"), bool):
            fails.append("done and remind must be true or false: " + repr(item))
        if "due" in item and (not isinstance(item["due"], int) or isinstance(item["due"], bool)):
            fails.append("due must be whole seconds (the app's import drops anything else): " + repr(item))


# A list as the Lua version saved it: one item from the first version with no
# id, and a due date that came back from Lua's JSON as a float.
later = int(time.time()) + 7 * 86400
store["items"] = json.dumps([
    {"id": 1, "text": "Buy milk", "done": False, "remind": False},
    {"text": "From version one", "done": True, "remind": False},
    {"id": 4, "text": "Call home", "done": False, "due": later + 0.0, "remind": True},
])

plugin = plugin_test.load("main.py", wm, ui)
send = plugin["on_event"]
items = plugin["items"]
expect("items loaded", len(items), 3)
expect("an item with no id gets the next free one", items[1]["id"], 5)
expect("a float due date loads as whole seconds", items[2]["due"], later)

tree = plugin["render"]()
if tree.get("type") != "tabs" or len(tree.get("pages") or []) != 2:
    fails.append("render() should give two tabs")

# Add one with a due date and a reminder.
due = int(time.time()) + 3 * 86400
send({"type": "input_changed", "id": "draft", "value": "Water plants"})
send({"type": "date_changed", "id": "draft_due", "value": due})
send({"type": "click", "id": "add"})
expect("the draft box is emptied", writes[-1], ["draft", ""])
data = saved()
check_shape(data)
expect("four items saved", len(data), 4)
expect("the new item", [data[3]["id"], data[3]["text"], data[3]["due"], data[3]["remind"]], [6, "Water plants", due, True])
expect("its reminder", reminders.get("item:6"), [due, "Water plants"])

# Tick it off: the reminder goes.
send({"type": "toggle", "id": "done:6", "value": True})
expect("done is saved", saved()[3]["done"], True)
expect("a finished item has no reminder", "item:6" in reminders, False)

# Clear the due date on the Details page of the first item in order.
send({"type": "click", "id": "next"})
send({"type": "date_changed", "id": "due", "value": None})
check_shape(saved())

send({"type": "click", "id": "clear_done"})
data = saved()
check_shape(data)
expect("finished items cleared", [item["text"] for item in data], ["Buy milk", "Call home"])

# Over quota: the plugin says so instead of losing the item.
quota_full[0] = True
send({"type": "input_changed", "id": "draft", "value": "One too many"})
send({"type": "click", "id": "add"})
if "quota" not in str(plugin["notice"]):
    fails.append("a failed save should show a notice, got " + repr(plugin["notice"]))

if fails:
    for message in fails:
        print("  " + message)
    raise RuntimeError("todo-list: " + str(len(fails)) + " checks failed")
print("todo-list: all checks passed")
