# Todo List: storage, due dates and reminders.
#
# Shows both capabilities a plugin can ask for, and the date widget.
#
# `wm.storage` is a small string-to-string map that belongs to this plugin
# alone, lives on this device only, and is deleted when the plugin is
# uninstalled. `wm.reminders` asks the app to show a notification at a time
# you pick. The app shows it, not this script: nothing here runs in the
# background, and the notification always carries the plugin's name. Both are
# declared in plugin.json, so the user sees them before installing.
#
# Note what is *not* here: no network, no reading your messages. This list
# cannot leave the phone, because there is nothing in the sandbox to send it
# with.

import json
import time

items = []           # dicts: id, text, done, due (seconds, absent when none), remind
next_id = 1
draft = ""
draft_due = None     # the due date for the next item, if any
draft_remind = True
selected = None      # the id of the item the Details page shows
notice = None        # one line about the last thing that went wrong

# wm.reminders is only there when plugin.json asks for the permission. The
# list still works without it.
try:
    has_reminders = wm.reminders is not None
except AttributeError:
    has_reminders = False

# ---------------------------------------------------------------- storage ---


def whole(value):
    """A stored number as a whole number of seconds or an id, or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def load():
    """Reads the saved list.

    Stored as JSON in one key, `items`, which is simpler than juggling a key
    per item and stays well inside the quota. The Lua versions of this plugin
    wrote the same shape, so a list saved by them loads here unchanged. Items
    saved by the first version have no id, so they get one here.
    """
    global items, next_id
    raw = wm.storage.get("items")
    if not raw:
        return
    try:
        decoded = json.loads(raw)
    except ValueError:
        return
    if not isinstance(decoded, list):
        return
    items = []
    for entry in decoded:
        if not isinstance(entry, dict):
            continue
        item = {
            "id": whole(entry.get("id")) or 0,
            "text": str(entry.get("text", "")),
            "done": bool(entry.get("done")),
            "remind": bool(entry.get("remind")),
        }
        due = whole(entry.get("due"))
        if due:
            item["due"] = due
        items.append(item)
    for item in items:
        if item["id"] >= next_id:
            next_id = item["id"] + 1
    for item in items:
        if item["id"] <= 0:
            item["id"] = next_id
            next_id += 1


def save():
    global notice
    try:
        wm.storage.set("items", json.dumps(items))
    except ValueError as error:
        # Over quota, most likely. Say so rather than silently losing an item.
        notice = "Could not save: " + str(error)
        wm.log("could not save:", error)


# Runs once, when the plugin is opened.
load()

# -------------------------------------------------------------- reminders ---


def reminder_id(item):
    """One reminder per item, named after it, so setting it again replaces it."""
    return "item:" + str(item["id"])


def sync(item):
    """Makes the app's reminder for an item match the item: set while it is
    due later, not done, and asked for; cancelled otherwise."""
    global notice
    if not has_reminders:
        return
    due = item.get("due")
    if item["remind"] and due and not item["done"] and due > time.time():
        try:
            wm.reminders.set(reminder_id(item), due, item["text"])
        except ValueError as error:
            notice = "No reminder: " + str(error)
    else:
        wm.reminders.cancel(reminder_id(item))


# ------------------------------------------------------------------ dates ---


def day_start(t):
    d = time.parts(t)
    return wm.timestamp(d["year"], d["month"], d["day"], 0)


def when(due):
    """"today 09:00", "tomorrow 18:30", or "Fri 24 Oct 09:00"."""
    today = day_start(time.time())
    d = time.parts(today)
    tomorrow = wm.timestamp(d["year"], d["month"], d["day"] + 1, 0)
    day = day_start(due)
    clock = time.format("HH:mm", due)
    if day == today:
        return "today " + clock
    if day == tomorrow:
        return "tomorrow " + clock
    return time.format("EEE d MMM", due) + " " + clock


def overdue(item):
    due = item.get("due")
    return due is not None and not item["done"] and due < time.time()


def status(item):
    """The line under an item's text, or None when it has no due date."""
    due = item.get("due")
    if not due:
        return None
    line = ("overdue, was due " if overdue(item) else "due ") + when(due)
    # Only while the app will actually show one: not for a time already past.
    if item["remind"] and not item["done"] and due > time.time() and has_reminders:
        line += " · reminder"
    return line


# ------------------------------------------------------------------ order ---


def order_key(item):
    due = item.get("due")
    return (item["done"], due is None, due or 0, item["id"])


def ordered():
    """Open items first, soonest due first and undated last; finished items
    after them. The saved list keeps the order things were added in."""
    return sorted(items, key=order_key)


def find(item_id):
    for item in items:
        if item["id"] == item_id:
            return item
    return None


def current():
    """The item the Details page shows: the one picked, or the first in order."""
    item = find(selected) if selected is not None else None
    if item:
        return item
    shown = ordered()
    return shown[0] if shown else None


def position(item, in_order):
    for index, other in enumerate(in_order):
        if other["id"] == item["id"]:
            return index
    return 0


def step(by):
    """Moves the Details page by one item, round the end."""
    global selected
    in_order = ordered()
    if not in_order:
        return
    at = (position(current(), in_order) + by) % len(in_order)
    selected = in_order[at]["id"]


# ----------------------------------------------------------------- events ---


def set_done(item, done):
    item["done"] = done
    sync(item)
    save()


def delete(item):
    global items, selected
    if has_reminders:
        wm.reminders.cancel(reminder_id(item))
    items = [other for other in items if other["id"] != item["id"]]
    if selected == item["id"]:
        selected = None
    save()


def set_due(item, value):
    if value is None:
        item.pop("due", None)
    else:
        item["due"] = int(value)


def on_event(e):
    global notice, draft, draft_due, draft_remind, next_id, items
    notice = None
    kind = e["type"]
    eid = e["id"]

    if kind == "input_changed" and eid == "draft":
        draft = e["value"]

    elif kind == "date_changed":
        value = e.get("value")
        if eid == "draft_due":
            draft_due = int(value) if value is not None else None
        elif eid == "due":
            item = current()
            if item:
                set_due(item, value)
                sync(item)
                save()

    elif kind == "toggle":
        # Toggle ids on the list are "done:<id>", so the number says which item.
        if eid.startswith("done:"):
            item = find(int(eid[5:]))
            if item:
                set_done(item, e["value"])
        elif eid == "draft_remind":
            draft_remind = e["value"]
        elif eid == "remind":
            item = current()
            if item:
                item["remind"] = e["value"]
                sync(item)
                save()
        elif eid == "detail_done":
            item = current()
            if item:
                set_done(item, e["value"])

    elif kind == "click":
        if eid == "add" and draft != "":
            item = {
                "id": next_id,
                "text": draft,
                "done": False,
                "remind": draft_due is not None and draft_remind,
            }
            set_due(item, draft_due)
            next_id += 1
            items.append(item)
            sync(item)
            draft = ""
            draft_due = None
            wm.ui.set_input("draft", "")
            save()

        elif eid == "clear_done":
            items = [item for item in items if not item["done"]]
            save()

        elif eid == "previous":
            step(-1)
        elif eid == "next":
            step(1)
        elif eid == "delete":
            item = current()
            if item:
                delete(item)


# ----------------------------------------------------------------- render ---


def list_page():
    rows = [
        ui.row(
            ui.input("draft", placeholder="Something to do"),
            ui.button("add", "Add", style="primary"),
        ),
        ui.date("draft_due", label="Due (optional)", value=draft_due, time=True),
    ]
    if draft_due is not None and has_reminders:
        rows.append(ui.toggle("draft_remind", "Remind me when it is due", checked=draft_remind))
    rows.append(ui.divider())
    if notice:
        rows.append(ui.label(notice, style="caption"))

    if not items:
        rows.append(ui.label("Nothing on the list.", style="caption"))
        return rows

    remaining = 0
    late = 0
    for item in ordered():
        if not item["done"]:
            remaining += 1
        if overdue(item):
            late += 1
        line = status(item)
        rows.append(ui.toggle(
            "done:" + str(item["id"]),
            item["text"] + "\n" + line if line else item["text"],
            checked=item["done"],
        ))
    summary = str(remaining) + " of " + str(len(items)) + " left"
    if late > 0:
        summary += ", " + str(late) + " overdue"
    rows.append(ui.label(summary, style="caption"))
    rows.append(ui.button("clear_done", "Clear finished"))
    return rows


def details_page():
    item = current()
    if not item:
        return [ui.label("Add something on the List page first.", style="caption")]
    in_order = ordered()
    at = position(item, in_order) + 1

    rows = [
        ui.row(
            ui.button("previous", "‹ Previous", enabled=len(in_order) > 1),
            ui.label(str(at) + " of " + str(len(in_order)), style="caption"),
            ui.button("next", "Next ›", enabled=len(in_order) > 1),
        ),
        ui.label(item["text"], style="title"),
    ]
    if notice:
        rows.append(ui.label(notice, style="caption"))
    rows.append(ui.date("due", label="Due", value=item.get("due"), time=True))
    if has_reminders:
        if item.get("due"):
            rows.append(ui.toggle("remind", "Remind me when it is due", checked=item["remind"]))
        else:
            rows.append(ui.label("Set a due date to get a reminder.", style="caption"))
    rows.append(ui.toggle("detail_done", "Done", checked=item["done"]))
    rows.append(ui.button("delete", "Delete"))
    return rows


def render():
    return ui.tabs(
        "pages",
        ui.page("List", *list_page()),
        ui.page("Details", *details_page()),
    )
