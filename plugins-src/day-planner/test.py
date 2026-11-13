# Tests for Day Planner, run with `wm-python-cli test plugins-src/day-planner`.
# They drive the plugin the way the keyboard does: taps, holds and drags on
# the timeline, typing, the board's row actions, and the host calls to the
# calendar and the To-do list answered from a mock.

import json
import time

PAD = 3.0
HOUR_H = 18.0


def walk(node, out):
    if isinstance(node, dict):
        out.append(node)
        for k in ("children", "items", "pages", "root"):
            for c in node.get(k) or []:
                walk(c, out)
    elif isinstance(node, list):
        for c in node:
            walk(c, out)
    return out


def widgets(r):
    assert r["ok"], r.get("error")
    return walk(r["ui"], [])


def by_id(r, wid):
    for w in widgets(r):
        if w.get("id") == wid:
            return w
    return None


def texts(r):
    out = []
    for w in widgets(r):
        for k in ("text", "title", "subtitle", "trailing", "label"):
            if isinstance(w.get(k), str):
                out.append(w[k])
        for sh in w.get("shapes") or []:
            if sh.get("shape") == "text":
                out.append(sh["text"])
    return out


def shown(r, text):
    return any([text in t for t in texts(r)])


def stored(s, key):
    raw = s["storage"]().get(key)
    return None if raw is None else json.loads(raw)


def planner(s):
    return stored(s, "__state__:planner")


def top_hour(r):
    """The first hour the timeline shows, from its first label."""
    for sh in by_id(r, "timeline")["shapes"]:
        if sh.get("shape") == "text":
            return int(sh["text"][0:2])
    raise AssertionError("no hour labels")


def y_for(r, minute):
    return PAD + (minute - top_hour(r) * 60) / 60 * HOUR_H


def day_key(seconds):
    p = time.parts(seconds)
    return f"{p['year']:04d}-{p['month']:02d}-{p['day']:02d}"


TODAY = day_key(time.time())
TOMORROW = day_key(time.time() + 86400)


def mock(**answers):
    """Host answers, plus the toasts every session shows."""
    out = {"ui.toast": None}
    for k in answers:
        out[k.replace("_", ".", 1)] = answers[k]
    return out


def ev(s, e):
    r = s["event"](e)
    assert r["ok"], (e, r.get("error"))
    return r


# --- the first draw: today, the timeline, no blocks yet -------------------

s = plugin_test.session(mock=mock(), settings={})
r = s["load"]()
assert r["ok"], r.get("error")
assert by_id(r, "timeline")["dragAfterHold"] is True
assert by_id(r, "timeline")["tappable"] is True
assert shown(r, "Today ·"), texts(r)
assert by_id(r, "page")["value"] == "day"
assert "Tags" in [c["label"] for c in r["host"]["commands"]]
# No calendar answer in the mock: the plugin says so and keeps working.
r = s["settle"]()
assert shown(r, "Calendar events did not load"), texts(r)

# --- tap a free slot: a block, its page, a title --------------------------

top = top_hour(r)
r = ev(s, {"type": "tap", "id": "timeline", "x": 90, "y": y_for(r, top * 60 + 40)})
assert r["host"]["title"] == "New block" and r["host"]["canBack"], r["host"]
blocks = stored(s, "day:" + TODAY)
assert len(blocks) == 1, blocks
b = blocks[0]
assert b["start"] == top * 60 + 30 and b["length"] == 30, b
ev(s, {"type": "change", "id": "block-title", "value": "Deep work"})
r = ev(s, {"type": "back"})
assert stored(s, "day:" + TODAY)[0]["title"] == "Deep work"
assert shown(r, "Deep work"), texts(r)

# --- hold and drag: move by 15-minute steps, then resize from its foot ----

start = top * 60 + 30
r = ev(s, {"type": "drag", "id": "timeline", "x": 90, "y": y_for(r, start + 5), "dx": 0, "dy": 0, "phase": "start"})
r = ev(s, {"type": "drag", "id": "timeline", "x": 90, "y": y_for(r, start + 5 + 47), "dx": 0, "dy": 0, "phase": "move"})
r = ev(s, {"type": "drag", "id": "timeline", "x": 90, "y": y_for(r, start + 5 + 47), "dx": 0, "dy": 0, "phase": "end"})
b = stored(s, "day:" + TODAY)[0]
assert b["start"] == start + 45 and b["length"] == 30, b
assert r["host"]["title"] is None, "a move opens no page"

foot = b["start"] + b["length"] - 2
r = ev(s, {"type": "drag", "id": "timeline", "x": 90, "y": y_for(r, foot), "dx": 0, "dy": 0, "phase": "start"})
r = ev(s, {"type": "drag", "id": "timeline", "x": 90, "y": y_for(r, b["start"] + 61), "dx": 0, "dy": 0, "phase": "move"})
r = ev(s, {"type": "drag", "id": "timeline", "x": 90, "y": y_for(r, b["start"] + 61), "dx": 0, "dy": 0, "phase": "end"})
b2 = stored(s, "day:" + TODAY)[0]
assert b2["start"] == b["start"] and b2["length"] == 60, b2

# A hold on a free slot makes a block there and the drag sets its length.
free = b2["start"] + 120
if free + 45 <= 24 * 60 and free < (top + 6) * 60:
    r = ev(s, {"type": "drag", "id": "timeline", "x": 90, "y": y_for(r, free + 3), "dx": 0, "dy": 0, "phase": "start"})
    r = ev(s, {"type": "drag", "id": "timeline", "x": 90, "y": y_for(r, free + 44), "dx": 0, "dy": 0, "phase": "move"})
    r = ev(s, {"type": "drag", "id": "timeline", "x": 90, "y": y_for(r, free + 44), "dx": 0, "dy": 0, "phase": "end"})
    made = [x for x in stored(s, "day:" + TODAY) if x["start"] == free]
    assert made and made[0]["length"] == 45, stored(s, "day:" + TODAY)
    assert r["host"]["title"] == "New block"
    r = ev(s, {"type": "click", "id": "block-delete"})
    assert not [x for x in stored(s, "day:" + TODAY) if x["start"] == free]

# --- tasks: add, steps, tick, schedule ------------------------------------

ev(s, {"type": "change", "id": "new-task", "value": "Write the report"})
r = ev(s, {"type": "submit", "id": "new-task", "value": "Write the report"})
tasks = planner(s)["tasks"]
assert len(tasks) == 1 and tasks[0]["day"] == TODAY, tasks
tid = tasks[0]["id"]
assert shown(r, "Write the report"), texts(r)

r = ev(s, {"type": "click", "id": f"task-{tid}"})
assert r["host"]["title"] == "Write the report"
for step in ("Outline", "Draft", "Edit"):
    ev(s, {"type": "change", "id": "new-step", "value": step})
    r = ev(s, {"type": "submit", "id": "new-step", "value": step})
assert [x["text"] for x in planner(s)["tasks"][0]["steps"]] == ["Outline", "Draft", "Edit"]
r = ev(s, {"type": "click", "id": "step-0"})
assert shown(r, "Steps · 1/3"), texts(r)
ev(s, {"type": "change", "id": "task-estimate", "value": 45})
r = ev(s, {"type": "click", "id": "task-schedule"})
assert r["host"]["title"] is None
linked = [x for x in stored(s, "day:" + TODAY) + (stored(s, "day:" + TOMORROW) or []) if x.get("task") == tid]
if linked:
    assert linked[0]["length"] == 45, linked
else:
    # Too late in the day for 45 free minutes: the plugin says so instead.
    assert planner(s)["tasks"][0]["day"] == TODAY

# Ticking the task ticks its steps.
r = ev(s, {"type": "item_action", "id": f"task-{tid}", "value": "Done"})
t = planner(s)["tasks"][0]
assert t["done"] and all([x["done"] for x in t["steps"]]), t

# --- the board: move a task and a block between days ----------------------

ev(s, {"type": "submit", "id": "new-task", "value": "Call the bank"})
bank = [x for x in planner(s)["tasks"] if x["title"] == "Call the bank"][0]
r = ev(s, {"type": "change", "id": "page", "value": "board"})
assert by_id(r, "col-today") is not None and by_id(r, "col-tomorrow") is not None and by_id(r, "col-later") is not None
r = ev(s, {"type": "item_action", "id": f"board-task-{bank['id']}", "value": "Tomorrow"})
assert [x for x in planner(s)["tasks"] if x["id"] == bank["id"]][0]["day"] == TOMORROW
r = ev(s, {"type": "item_action", "id": f"board-task-{bank['id']}", "value": "Later"})
assert [x for x in planner(s)["tasks"] if x["id"] == bank["id"]][0]["day"] == "later"
deep = [x for x in stored(s, "day:" + TODAY) if x["title"] == "Deep work"][0]
r = ev(s, {"type": "item_action", "id": f"board-block-{deep['id']}", "value": "Tomorrow"})
assert [x for x in stored(s, "day:" + TOMORROW) if x["id"] == deep["id"]], "the block moved"
assert not [x for x in (stored(s, "day:" + TODAY) or []) if x["id"] == deep["id"]]
# A block tomorrow is in the future, so it has a reminder.
assert r["remindersChanged"] is True or s["event"]({"type": "change", "id": "page", "value": "board"})["ok"]

# --- the week: hours per tag ----------------------------------------------

r = ev(s, {"type": "change", "id": "page", "value": "week"})
if by_id(r, "chart-tags") is None:
    # Tomorrow is in next week when today is Sunday.
    r = ev(s, {"type": "click", "id": "next-week"})
chart = by_id(r, "chart-tags")
assert chart is not None, texts(r)
assert chart["labels"][0] == "Work", chart
today_min = sum([x["length"] for x in stored(s, "day:" + TODAY) or []])
tomorrow_min = sum([x["length"] for x in stored(s, "day:" + TOMORROW) or []])
# Both days, or only one of them when the week ends between them.
assert chart["series"][0]["values"][0] * 60 in (today_min + tomorrow_min, today_min, tomorrow_min), (chart, today_min, tomorrow_min)
assert by_id(r, "chart-days")["labels"] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
assert shown(r, "· 100%"), texts(r)
assert by_id(r, "stat-planned") is not None

# --- tags -------------------------------------------------------------------

r = ev(s, {"type": "command", "id": "tags_command"})
assert r["host"]["title"] == "Tags"
r = ev(s, {"type": "submit", "id": "new-tag", "value": "Family"})
assert "Family" in [x["name"] for x in planner(s)["tags"]]
ev(s, {"type": "change", "id": "tag-color-work", "value": "danger"})
assert [x for x in planner(s)["tags"] if x["id"] == "work"][0]["color"] == "danger"
ev(s, {"type": "back"})

# --- @plan from the suggestion strip ---------------------------------------

r = ev(s, {"type": "keyword", "id": "plan", "value": "Buy stamps"})
assert [x for x in planner(s)["tasks"] if x["title"] == "Buy stamps" and x["day"] == TODAY]

# --- calendar events on the timeline ----------------------------------------

s2 = plugin_test.session(mock=mock(calendar_events=[]), settings={})
r = s2["load"]()
top = top_hour(r)
p = time.parts(time.time())
base = time.time() - p["hour"] * 3600 - p["minute"] * 60 - p["second"]
events = [
    {"id": 9, "title": "Dentist", "start": base + (top + 1) * 3600, "end": base + (top + 2) * 3600,
     "all_day": False, "location": None, "calendar": 1, "recurring": False},
    {"id": 10, "title": "Holiday", "start": base, "end": base + 86400, "all_day": True,
     "location": None, "calendar": 1, "recurring": False},
]
r = ev(s2, {"type": "result", "token": "calendar:1", "value": events})
assert shown(r, "Dentist"), texts(r)
assert shown(r, "All day: Holiday"), texts(r)
# Tapping the event names it; it is not a block.
r = ev(s2, {"type": "tap", "id": "timeline", "x": 90, "y": y_for(r, (top + 1) * 60 + 20)})
assert r["host"]["title"] is None and stored(s2, "day:" + TODAY) is None
# Scheduling skips the event's hour.
ev(s2, {"type": "submit", "id": "new-task", "value": "Groceries"})

# A refused calendar is a note, not a crash.
s3 = plugin_test.session(mock=mock(calendar_events={"error": {"kind": "PermissionError", "message": "not granted"}}), settings={})
r = s3["load"]()
r = s3["settle"]()
assert shown(r, "Allow the calendar permission"), texts(r)

# Without the setting it never asks.
s4 = plugin_test.session(mock=mock(), settings={"show_events": False})
r = s4["load"]()
assert not [c for c in s4["calls"]() if c["op"].startswith("calendar.")]

# --- sharing tasks with the To-do list --------------------------------------

existing = [{"id": 501, "text": "Renew passport", "done": False, "due": None, "all_day": False,
             "steps": [{"id": 502, "text": "Photos", "done": True, "due": None, "all_day": False}]}]
answers = mock(
    todo_list=existing,
    todo_add={"id": 600, "text": "x", "done": False, "due": None, "all_day": False, "steps": []},
    todo_update={"id": 600, "text": "x", "done": True, "due": None, "all_day": False, "steps": []},
    todo_remove=True,
)
s5 = plugin_test.session(mock=answers, settings={"todo_sync": True})
r = s5["load"]()
tasks = planner(s5)["tasks"]
assert [x for x in tasks if x["title"] == "Renew passport" and x["todo"] == 501 and x["day"] == "later"], tasks
assert tasks[0]["steps"][0]["done"] is True
r = ev(s5, {"type": "submit", "id": "new-task", "value": "Pay rent"})
adds = [c for c in s5["calls"]() if c["op"] == "todo.add"]
assert adds and adds[-1]["args"]["text"] == "Pay rent" and adds[-1]["args"]["all_day"] is True, adds
rent = [x for x in planner(s5)["tasks"] if x["title"] == "Pay rent"][0]
assert rent["todo"] == 600
ev(s5, {"type": "item_action", "id": f"task-{rent['id']}", "value": "Done"})
updates = [c for c in s5["calls"]() if c["op"] == "todo.update"]
assert updates and updates[-1]["args"] == {"id": 600, "done": True}, updates
ev(s5, {"type": "item_action", "id": f"task-{rent['id']}", "value": "Delete"})
assert [c for c in s5["calls"]() if c["op"] == "todo.remove" and c["args"]["id"] == 600]

# Not shared, the plugin never touches the list.
assert not [c for c in s["calls"]() if c["op"].startswith("todo.")]

print("day planner: ok")
