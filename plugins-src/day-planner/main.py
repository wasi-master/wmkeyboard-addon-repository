"""Day Planner: time blocking for one day at a time.

A day is a timeline of blocks. Tap a free slot to add one, hold a block and
drag to move it, hold its lower edge to make it longer or shorter, all in
15-minute steps. Tasks have steps to tick off and can be scheduled into a
block. The board moves tasks and blocks between today, tomorrow and later,
and the week page adds up the time each tag took.

With the risky permissions turned on, the phone's calendar events show on
the timeline (calendar) and tasks are shared with the keyboard's own To-do
list (todo). Without them everything else works.
"""

import time
import wm
from wm import plugin, ui, storage, reminders, calendar, todo

STEP = 15
DAY_MIN = 24 * 60

# The timeline, in canvas units: W wide, an hour HOUR_H high. Text on a
# canvas is at least 4 units, so the canvas is wide enough for that to be small.
W = 160.0
LEFT = 24.0
RIGHT = 158.0
PAD = 3.0
HOUR_H = 18.0
# How much of a block's foot resizes it rather than moving it.
EDGE = 4.0
LABEL = 4.4
TITLE = 5.2
SMALL = 4.2
# Where scheduling looks for room on a day that is not today.
DAY_BEGINS = 9 * 60
KEEP_DAYS = 35

ROLES = ["primary", "secondary", "accent", "success", "warning", "danger", "muted"]
ROLE_NAMES = {"primary": "Blue", "secondary": "Teal", "accent": "Pink", "success": "Green",
              "warning": "Amber", "danger": "Red", "muted": "Grey"}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def default_tags():
    return [
        {"id": "work", "name": "Work", "color": "primary"},
        {"id": "personal", "name": "Personal", "color": "success"},
        {"id": "health", "name": "Health", "color": "accent"},
        {"id": "learning", "name": "Learning", "color": "secondary"},
        {"id": "errands", "name": "Errands", "color": "warning"},
    ]


saved = plugin.state(persist=True, key="planner", tags=default_tags(), tasks=[], next_id=1)
view = plugin.state(day="", top=8, page="day", week="", drag=None, editing=None, events={}, events_note="",
                    sync_note="", task_text="", step_text="", tag_text="")

# Blocks by day, read from storage ("day:YYYY-MM-DD") the first time a day is drawn.
_blocks = {}


# MARK: - dates and times

def day_key(seconds):
    p = time.parts(seconds)
    return f"{p['year']:04d}-{p['month']:02d}-{p['day']:02d}"


def ymd(day):
    return int(day[0:4]), int(day[5:7]), int(day[8:10])


def today():
    return day_key(time.time())


def add_days(day, n):
    y, m, d = ymd(day)
    # Noon, so a daylight-saving hour never tips it into the wrong date.
    return day_key(wm.timestamp(y, m, d, 12) + n * 86400)


def at_minute(day, minute):
    y, m, d = ymd(day)
    return wm.timestamp(y, m, d, minute // 60, minute % 60, 0)


def day_start(day):
    return at_minute(day, 0)


def minute_of(seconds, day):
    """Minutes into `day` of a moment, held to the day itself."""
    if seconds <= day_start(day):
        return 0
    if seconds >= day_start(add_days(day, 1)):
        return DAY_MIN
    p = time.parts(seconds)
    return p["hour"] * 60 + p["minute"]


def now_minute():
    p = time.parts(time.time())
    return p["hour"] * 60 + p["minute"]


def monday_of(day):
    y, m, d = ymd(day)
    wd = time.parts(wm.timestamp(y, m, d, 12))["weekday"]
    return add_days(day, -wd)


def setting(key, default):
    try:
        return plugin.settings.get(key, default)
    except Exception:
        return default


def twelve_hour():
    return setting("clock", "24-hour") == "12-hour"


def hm(minute):
    minute = int(minute)
    h = (minute // 60) % 24
    m = minute % 60
    if twelve_hour():
        suffix = "am" if h < 12 else "pm"
        return f"{h % 12 or 12}:{m:02d} {suffix}"
    return f"{h:02d}:{m:02d}"


def hour_label(h):
    if twelve_hour():
        return f"{h % 12 or 12} {'am' if h % 24 < 12 else 'pm'}"
    return f"{h % 24:02d}:00"


def span(minutes):
    minutes = int(minutes)
    if minutes < 60:
        return f"{minutes} min"
    if minutes % 60 == 0:
        return f"{minutes // 60} h"
    return f"{minutes // 60} h {minutes % 60:02d}"


def day_name(day):
    t = today()
    if day == t:
        word = "Today"
    elif day == add_days(t, 1):
        word = "Tomorrow"
    elif day == add_days(t, -1):
        word = "Yesterday"
    else:
        word = None
    shown = time.format("EEE d MMM", wm.timestamp(*ymd(day)))
    return f"{word} · {shown}" if word else shown


def hours_shown():
    try:
        return max(2, min(24, int(str(setting("hours", "6")))))
    except ValueError:
        return 6


def new_length():
    try:
        return max(STEP, int(str(setting("block_minutes", "30"))))
    except ValueError:
        return 30


def remind_lead():
    """Minutes before a block its reminder comes, or None for no reminders."""
    text = str(setting("remind", "5 minutes before"))
    if text == "Off":
        return None
    if text.startswith("When"):
        return 0
    try:
        return int(text.split(" ")[0])
    except ValueError:
        return 5


def snap_down(minute):
    return max(0, min(DAY_MIN - STEP, int(minute // STEP) * STEP))


def snap_near(minute):
    return int((minute + STEP / 2) // STEP) * STEP


def fresh_id():
    n = saved.next_id
    saved.next_id = n + 1
    return n


# MARK: - tags

def tag_of(tid):
    for t in saved.tags:
        if t["id"] == tid:
            return t
    return None


def tag_color(tid):
    t = tag_of(tid)
    return t["color"] if t else "muted"


def tag_name(tid):
    t = tag_of(tid)
    return t["name"] if t else "No tag"


def tag_options():
    return [(t["id"], t["name"]) for t in saved.tags] + [("", "No tag")]


def first_tag():
    return saved.tags[0]["id"] if saved.tags else ""


# MARK: - blocks

def blocks(day):
    if day not in _blocks:
        _blocks[day] = [dict(b) for b in storage.get("day:" + day, [])]
    return _blocks[day]


def save_blocks(day):
    items = sorted(blocks(day), key=lambda b: b["start"])
    _blocks[day] = items
    try:
        if items:
            storage["day:" + day] = items
        elif ("day:" + day) in storage:
            del storage["day:" + day]
    except ValueError:
        ui.toast("Storage is full: delete some old blocks or tasks first")
    rearm()


def find_block(bid):
    for day, items in _blocks.items():
        for b in items:
            if b["id"] == bid:
                return day, b
    return None, None


def block_title(b):
    if b.get("title"):
        return b["title"]
    t = task_of(b.get("task"))
    return t["title"] if t else "Untitled block"


def free_slot(day, length, earliest):
    """The first start from `earliest` where `length` minutes fit between the day's blocks and events."""
    busy = [(b["start"], b["start"] + b["length"]) for b in blocks(day)]
    for e in view.events.get(day, []):
        if not e.get("all_day"):
            busy.append((minute_of(e["start"], day), minute_of(e["end"], day)))
    busy.sort()
    start = earliest
    for s, e in busy:
        if s >= start + length:
            break
        if e > start:
            start = max(start, e)
    if start + length > DAY_MIN:
        return None
    return start


def add_block(day, start, length, title="", tag=None, task=None):
    b = {"id": fresh_id(), "start": start, "length": length, "title": title,
         "tag": first_tag() if tag is None else tag, "task": task}
    blocks(day).append(b)
    save_blocks(day)
    return b


def move_block(bid, to_day):
    day, b = find_block(bid)
    if b is None or day == to_day:
        return
    blocks(day).remove(b)
    save_blocks(day)
    blocks(to_day).append(b)
    save_blocks(to_day)


def delete_block(bid):
    day, b = find_block(bid)
    if b is None:
        return
    blocks(day).remove(b)
    save_blocks(day)
    if view.editing == bid:
        view.editing = None
        plugin.back()


# MARK: - reminders

def rearm():
    """One reminder per block in the coming week, `remind` minutes before it starts."""
    lead = remind_lead()
    wanted = {}
    if lead is not None:
        now = time.time()
        t = today()
        for n in range(7):
            day = add_days(t, n)
            for b in blocks(day):
                at = at_minute(day, b["start"]) - lead * 60
                if at > now + 30 and len(wanted) < 60:
                    when = "now" if lead == 0 else f"at {hm(b['start'])}"
                    wanted["b" + str(b["id"])] = (at, f"{block_title(b)} starts {when}"[:200])
    try:
        current = {}
        for r in reminders.list():
            current[r["id"]] = r
        for rid in current:
            if rid.startswith("b") and rid not in wanted:
                reminders.cancel(rid)
        for rid, pair in wanted.items():
            c = current.get(rid)
            if c is None or abs(c["time"] - pair[0]) > 1 or c["text"] != pair[1]:
                reminders.set(rid, pair[0], pair[1])
    except (PermissionError, ValueError) as err:
        wm.log("reminders:", err)


# MARK: - tasks

def task_of(tid):
    if tid is None:
        return None
    for t in saved.tasks:
        if t["id"] == tid:
            return t
    return None


def tasks_on(day):
    return [t for t in saved.tasks if t["day"] == day]


def steps_done(t):
    return len([s for s in t["steps"] if s["done"]])


def task_subtitle(t):
    parts = [tag_name(t["tag"])]
    if t["steps"]:
        parts.append(f"{steps_done(t)}/{len(t['steps'])} steps")
    if t.get("estimate"):
        parts.append(span(t["estimate"]))
    if t["day"] not in ("later", today(), add_days(today(), 1)):
        parts.append(day_name(t["day"]))
    if t["day"] != "later":
        starts = [b["start"] for b in blocks(t["day"]) if b.get("task") == t["id"]]
        if starts:
            parts.append(f"at {hm(min(starts))}")
    return " · ".join(parts)


def add_task(title, day, tag=None):
    title = str(title).strip()
    if not title:
        return None
    t = {"id": fresh_id(), "title": title[:200], "tag": first_tag() if tag is None else tag, "day": day,
         "done": False, "steps": [], "estimate": 0, "todo": None}
    saved.tasks.append(t)
    if sync_on():
        share_task(t)
    return t


def set_task_done(t, done):
    t["done"] = bool(done)
    if done:
        for s in t["steps"]:
            s["done"] = True
    to_todo(lambda: todo.update(t["todo"], done=bool(done)), t)


def set_task_day(t, day):
    old = t["day"]
    if old == day:
        return
    t["day"] = day
    if day == "later":
        to_todo(lambda: todo.update(t["todo"], due=None), t)
    else:
        to_todo(lambda: todo.update(t["todo"], due=day_start(day), all_day=True), t)
    # Its blocks go with it, at the same time of day.
    if day != "later" and old != "later":
        for b in list(blocks(old)):
            if b.get("task") == t["id"]:
                move_block(b["id"], day)


def delete_task(t):
    if t in saved.tasks:
        saved.tasks.remove(t)
    to_todo(lambda: todo.remove(t["todo"]), t)
    if t["day"] != "later":
        changed = False
        for b in blocks(t["day"]):
            if b.get("task") == t["id"]:
                b["task"] = None
                changed = True
        if changed:
            save_blocks(t["day"])


def schedule(t):
    """Puts a task into the first free slot of its day (today for a later one)."""
    day = today() if t["day"] == "later" else t["day"]
    if t["day"] == "later":
        set_task_day(t, day)
    length = t.get("estimate") or new_length()
    earliest = DAY_BEGINS
    if day == today():
        earliest = max(snap_down(now_minute()) + STEP, 0)
    start = free_slot(day, length, earliest)
    if start is None:
        ui.toast(f"No free {span(length)} left on {day_name(day)}")
        return
    add_block(day, start, length, title="", tag=t["tag"], task=t["id"])
    view.day = day
    view.page = "day"
    view.top = max(0, min(24 - hours_shown(), start // 60 - 1))
    ui.toast(f"{t['title']} at {hm(start)}")


def roll_over():
    if not setting("roll_over", True):
        return
    t = today()
    for task in saved.tasks:
        if not task["done"] and task["day"] != "later" and task["day"] < t:
            set_task_day(task, t)


def prune():
    """Forgets blocks and finished tasks older than KEEP_DAYS."""
    cutoff = add_days(today(), -KEEP_DAYS)
    old = [k for k in storage.keys() if k.startswith("day:") and k[4:] < cutoff]
    for k in old:
        del storage[k]
    saved.tasks = [t for t in saved.tasks if not (t["done"] and t["day"] != "later" and t["day"] < cutoff)]


# MARK: - the To-do list

def sync_on():
    return bool(setting("todo_sync", False)) and "todo" in plugin.permissions


def to_todo(change, t=None):
    """One change to the To-do list, for a task shared with it."""
    if not sync_on() or (t is not None and t.get("todo") is None):
        return None
    try:
        view.sync_note = ""
        return change()
    except Exception as err:
        view.sync_note = f"The To-do list did not take that: {err}"
        return None


def share_task(t):
    made = to_todo(lambda: todo.add(t["title"], due=None if t["day"] == "later" else day_start(t["day"]),
                                    all_day=t["day"] != "later"))
    if made:
        t["todo"] = made["id"]
        for s in t["steps"]:
            step = to_todo(lambda s=s: todo.add(s["text"], parent=made["id"]))
            if step:
                s["todo"] = step["id"]
                if s["done"]:
                    to_todo(lambda s=s: todo.update(s["todo"], done=True))
        if t["done"]:
            to_todo(lambda: todo.update(made["id"], done=True))


def pull():
    """Brings the To-do list and the planner's tasks together: ticks and steps
    from the list, text typed here, open tasks from either side in both."""
    if not sync_on():
        return
    try:
        items = todo.list(done=True)
        view.sync_note = ""
    except Exception as err:
        view.sync_note = f"The To-do list is not shared: {err}"
        return
    by_id = {}
    for it in items:
        by_id[it["id"]] = it
    linked = set()
    for t in saved.tasks:
        if t.get("todo") is None:
            continue
        it = by_id.get(t["todo"])
        if it is None:
            # Gone from the list: keep it here, no longer shared.
            t["todo"] = None
            continue
        linked.add(it["id"])
        if t.get("dirty"):
            to_todo(lambda t=t: todo.update(t["todo"], text=t["title"]), t)
            t["dirty"] = False
        else:
            t["title"] = it["text"]
        t["done"] = bool(it["done"])
        t["steps"] = [{"text": s["text"], "done": bool(s["done"]), "todo": s["id"]} for s in it["steps"]]
    for it in items:
        if it["id"] in linked or it["done"]:
            continue
        day = day_key(it["due"]) if it.get("due") else "later"
        t = {"id": fresh_id(), "title": it["text"], "tag": first_tag(), "day": day, "done": False,
             "steps": [{"text": s["text"], "done": bool(s["done"]), "todo": s["id"]} for s in it["steps"]],
             "estimate": 0, "todo": it["id"]}
        saved.tasks.append(t)
    for t in saved.tasks:
        if t.get("todo") is None and not t["done"]:
            share_task(t)


def flush_titles():
    for t in saved.tasks:
        if t.get("dirty"):
            to_todo(lambda t=t: todo.update(t["todo"], text=t["title"]), t)
            t["dirty"] = False


# MARK: - calendar events

def events_on():
    return bool(setting("show_events", True)) and "calendar" in plugin.permissions


def load_events(day, again=False):
    if not events_on() or (day in view.events and not again):
        return
    try:
        calendar.events(day_start(day), day_start(add_days(day, 1)),
                        then=lambda found, d=day: got_events(d, found), on_error=events_failed)
    except Exception as err:
        events_failed(err)


def got_events(day, found):
    events = dict(view.events)
    events[day] = [e for e in (found or [])][:60]
    view.events = events
    view.events_note = ""


def events_failed(err):
    if isinstance(err, PermissionError):
        view.events_note = "Allow the calendar permission to see your events here."
    else:
        view.events_note = f"Calendar events did not load: {err}"


def add_to_calendar(b, day):
    try:
        calendar.add(block_title(b), at_minute(day, b["start"]), at_minute(day, b["start"] + b["length"]))
        ui.toast("Added to your calendar")
        load_events(day, again=True)
    except Exception as err:
        ui.toast(f"Not added: {err}")


# MARK: - the timeline

def layout(day):
    """Blocks and timed events with their lanes: overlapping ones sit side by side."""
    items = []
    for b in blocks(day):
        items.append({"kind": "block", "start": b["start"], "end": b["start"] + b["length"], "ref": b})
    for e in view.events.get(day, []):
        if e.get("all_day"):
            continue
        s = minute_of(e["start"], day)
        items.append({"kind": "event", "start": s, "end": max(s + STEP, minute_of(e["end"], day)), "ref": e})
    items.sort(key=lambda it: (it["start"], -it["end"]))
    cluster = []
    ends = []
    cluster_end = -1
    for it in items:
        if cluster and it["start"] >= cluster_end:
            for c in cluster:
                c["lanes"] = len(ends)
            cluster = []
            ends = []
        lane = -1
        for i in range(len(ends)):
            if ends[i] <= it["start"]:
                lane = i
                break
        if lane < 0:
            lane = len(ends)
            ends.append(it["end"])
        else:
            ends[lane] = it["end"]
        it["lane"] = lane
        cluster.append(it)
        cluster_end = max(cluster_end, it["end"])
    for c in cluster:
        c["lanes"] = len(ends)
    return items


def y_of(minute):
    return PAD + (minute - view.top * 60) / 60 * HOUR_H


def minute_at(y):
    return view.top * 60 + (y - PAD) / HOUR_H * 60


def canvas_height():
    return PAD * 2 + hours_shown() * HOUR_H


def box(it):
    width = (RIGHT - LEFT) / it["lanes"]
    x = LEFT + it["lane"] * width
    return x, y_of(it["start"]), width - 1.0, (it["end"] - it["start"]) / 60 * HOUR_H - 0.6


def hit(x, y):
    found = None
    for it in layout(view.day):
        bx, by, bw, bh = box(it)
        if bx <= x <= bx + bw and by <= y <= by + bh:
            # A block over an event, the later one over the earlier.
            if found is None or it["kind"] == "block":
                found = it
    return found


def short(text, room, size):
    fits = max(1, int(room / (size * 0.52)))
    return text if len(text) <= fits else text[:max(1, fits - 1)] + "…"


def timeline_shapes():
    day = view.day
    hours = hours_shown()
    first = view.top * 60
    last = first + hours * 60
    shapes = []
    for h in range(view.top, view.top + hours + 1):
        y = y_of(h * 60)
        shapes.append(ui.line(LEFT - 2, y, RIGHT, y, "muted", 0.25))
        if h < 24:
            shapes.append(ui.text_at(1, y - LABEL / 2, hour_label(h), "muted", LABEL))
    dragging = view.drag["id"] if view.drag else None
    for it in layout(day):
        if it["end"] <= first or it["start"] >= last:
            continue
        x, y, w, h = box(it)
        top = max(y, PAD)
        bottom = min(y + h, PAD + hours * HOUR_H)
        h = bottom - top
        if h <= 0.3:
            continue
        if it["kind"] == "event":
            e = it["ref"]
            shapes.append(ui.rect(x, top, w, h, "muted", radius=1.6, fill=False))
            if h >= SMALL + 1:
                shapes.append(ui.text_at(x + 2, top + 0.6, short(e["title"], w - 3, SMALL), "muted", SMALL))
            continue
        b = it["ref"]
        color = tag_color(b.get("tag"))
        t = task_of(b.get("task"))
        done = t is not None and t["done"]
        if done:
            color = "muted"
        shapes.append(ui.rect(x, top, w, h, color, radius=2.0, fill=False))
        shapes.append(ui.rect(x, top, 3.4 if b["id"] == dragging else 1.6, h, color, radius=0.6))
        when = f"{hm(b['start'])}–{hm(b['start'] + b['length'])}"
        mark = ("✓ " if done else "○ ") if t is not None else ""
        if h >= TITLE + SMALL + 2:
            shapes.append(ui.text_at(x + 3.4, top + 0.8, short(mark + block_title(b), w - 5, TITLE), color, TITLE))
            shapes.append(ui.text_at(x + 3.4, top + TITLE + 1.6, short(when, w - 5, SMALL), "muted", SMALL))
        elif b["id"] == dragging:
            # While it moves, a short block shows its new time instead of its name.
            shapes.append(ui.text_at(x + 3.4, top + 0.2, short(when, w - 5, SMALL), color, SMALL))
        elif h >= SMALL + 0.4:
            size = TITLE if h >= TITLE + 0.4 else SMALL
            shapes.append(ui.text_at(x + 3.4, top + 0.2, short(mark + block_title(b), w - 5, size), color, size))
    if day == today():
        n = now_minute()
        if first <= n <= last:
            y = y_of(n)
            shapes.append(ui.line(LEFT - 2, y, RIGHT, y, "danger", 0.6))
            shapes.append(ui.circle(LEFT - 2, y, 1.3, "danger"))
    return shapes


def tapped(x, y):
    it = hit(x, y)
    if it is None:
        if x < LEFT - 2:
            return
        start = snap_down(minute_at(y))
        b = add_block(view.day, start, min(new_length(), DAY_MIN - start))
        open_block(b["id"], fresh=True)
    elif it["kind"] == "block":
        open_block(it["ref"]["id"])
    else:
        e = it["ref"]
        s = minute_of(e["start"], view.day)
        ui.toast(f"{e['title']}, {hm(s)}–{hm(minute_of(e['end'], view.day))}, from your calendar")


def dragged(d):
    phase = d["phase"]
    m = minute_at(d["y"])
    if phase == "start":
        it = hit(d["x"], d["y"])
        if it is None:
            if d["x"] < LEFT - 2:
                return
            b = add_block(view.day, snap_down(m), STEP)
            view.drag = {"id": b["id"], "mode": "new", "offset": 0}
        elif it["kind"] == "block":
            b = it["ref"]
            _, by, _, bh = box(it)
            mode = "resize" if d["y"] >= by + bh - EDGE else "move"
            view.drag = {"id": b["id"], "mode": mode, "offset": m - b["start"]}
        else:
            ui.toast("Calendar events move in the Calendar tool")
        return
    if view.drag is None:
        return
    day, b = find_block(view.drag["id"])
    if b is None:
        view.drag = None
        return
    if phase == "move":
        if view.drag["mode"] == "move":
            b["start"] = max(0, min(DAY_MIN - b["length"], snap_near(m - view.drag["offset"])))
        else:
            end = max(b["start"] + STEP, min(DAY_MIN, snap_near(m)))
            b["length"] = end - b["start"]
        # Near an edge, the window follows the finger.
        if d["y"] < PAD + 1 and view.top > 0:
            view.top = view.top - 1
        elif d["y"] > canvas_height() - PAD - 1 and view.top + hours_shown() < 24:
            view.top = view.top + 1
        return
    if phase == "end":
        mode = view.drag["mode"]
        view.drag = None
        save_blocks(day)
        if mode == "new":
            open_block(b["id"], fresh=True)


# MARK: - pages

def go_day(n):
    view.day = add_days(view.day, n)
    load_events(view.day)


def go_today():
    view.day = today()
    view.page = "day"
    view.top = max(0, min(24 - hours_shown(), now_minute() // 60 - 1))
    load_events(view.day)


def scroll_hours(n):
    view.top = max(0, min(24 - hours_shown(), view.top + n))


def submit_task(text):
    t = add_task(text, view.day)
    view.task_text = ""
    if t:
        ui.toast(f"Added {t['title']}")


def task_row(t, board=False):
    t_day = today()
    moves = {}
    if t["day"] != t_day:
        moves["Today"] = lambda t=t: set_task_day(t, t_day)
    if t["day"] != add_days(t_day, 1):
        moves["Tomorrow"] = lambda t=t: set_task_day(t, add_days(t_day, 1))
    if t["day"] != "later":
        moves["Later"] = lambda t=t: set_task_day(t, "later")
    acts = {"Undo" if t["done"] else "Done": lambda t=t: set_task_done(t, not t["done"])}
    if not t["done"]:
        acts["Schedule"] = lambda t=t: schedule(t)
    for k in moves:
        acts[k] = moves[k]
    acts["Delete"] = lambda t=t: delete_task(t)
    return ui.item(t["title"], subtitle=task_subtitle(t),
                   icon="check_circle" if t["done"] else "radio_button_unchecked",
                   on_click=lambda t=t: open_task(t["id"]), actions=acts,
                   key=("board-task-" if board else "task-") + str(t["id"]))


def day_page():
    with ui.row(weights=[1, 6, 1, 1, 1], align="center"):
        ui.icon_button("chevron_left", on_click=lambda: go_day(-1), label="Day before", key="prev-day")
        ui.label(day_name(view.day), style="title", key="day-name")
        ui.icon_button("chevron_right", on_click=lambda: go_day(1), label="Day after", key="next-day")
        ui.icon_button("expand_less", on_click=lambda: scroll_hours(-2), label="Earlier", enabled=view.top > 0,
                       key="earlier")
        ui.icon_button("expand_more", on_click=lambda: scroll_hours(2), label="Later",
                       enabled=view.top + hours_shown() < 24, key="later")
    all_day = [e for e in view.events.get(view.day, []) if e.get("all_day")]
    if all_day:
        ui.caption("All day: " + ", ".join([e["title"] for e in all_day]))
    ui.canvas(W, canvas_height(), timeline_shapes(), on_tap=tapped, on_drag=dragged, drag_after_hold=True,
              key="timeline")
    if view.events_note:
        ui.caption(view.events_note)
    planned = sum([b["length"] for b in blocks(view.day)])
    ui.caption(f"{span(planned)} planned. Tap a free time to add a block; hold a block to move it, or its lower edge to change its length.")
    with ui.section("Tasks", key="tasks"):
        ui.list([task_row(t) for t in tasks_on(view.day)], empty="No tasks for this day yet.", key="task-list")
        ui.input(placeholder="Add a task for this day", value=view.task_text,
                 on_change=lambda v: setattr(view, "task_text", v), on_submit=submit_task, key="new-task")
    if view.sync_note:
        ui.caption(view.sync_note)


def block_row(b, day):
    acts = {}
    for label, target in (("Today", today()), ("Tomorrow", add_days(today(), 1))):
        if day != target:
            acts[label] = lambda b=b, target=target: move_block(b["id"], target)
    acts["Delete"] = lambda b=b: delete_block(b["id"])
    return ui.item(block_title(b), subtitle=f"{hm(b['start'])}–{hm(b['start'] + b['length'])} · {tag_name(b.get('tag'))}",
                   icon="schedule", on_click=lambda b=b: open_block(b["id"]), actions=acts,
                   key="board-block-" + str(b["id"]))


def board_column(title, day, tasks):
    rows = [task_row(t, board=True) for t in tasks]
    planned = 0
    if day is not None:
        for b in blocks(day):
            if not b.get("task"):
                rows.append(block_row(b, day))
            planned += b["length"]
    open_count = len([t for t in tasks if not t["done"]])
    head = f"{title} · {open_count} open" + (f", {span(planned)} planned" if planned else "")
    with ui.section(head, collapsible=True, key="col-" + title.lower()):
        ui.list(rows, empty="Nothing here.", key="list-" + title.lower())


def board_page():
    t = today()
    tomorrow = add_days(t, 1)
    board_column("Today", t, tasks_on(t))
    board_column("Tomorrow", tomorrow, tasks_on(tomorrow))
    later = [x for x in saved.tasks if x["day"] == "later" or x["day"] > tomorrow]
    board_column("Later", None, later)
    earlier = [x for x in saved.tasks if x["day"] != "later" and x["day"] < t and not x["done"]]
    if earlier:
        board_column("Earlier", None, earlier)
    ui.caption("Press ⋯ on a row to move it to another day.")


def week_page():
    start = view.week or monday_of(view.day or today())
    days = [add_days(start, n) for n in range(7)]
    per_tag = {}
    totals = {}
    for i in range(7):
        for b in blocks(days[i]):
            tid = b.get("tag") or ""
            if tid not in per_tag:
                per_tag[tid] = [0.0] * 7
                totals[tid] = 0
            per_tag[tid][i] = per_tag[tid][i] + b["length"] / 60
            totals[tid] = totals[tid] + b["length"]
    with ui.row(weights=[1, 6, 1], align="center"):
        ui.icon_button("chevron_left", on_click=lambda: setattr(view, "week", add_days(start, -7)),
                       label="Week before", key="prev-week")
        ui.label(f"Week of {time.format('d MMM', wm.timestamp(*ymd(start)))}", style="title", key="week-name")
        ui.icon_button("chevron_right", on_click=lambda: setattr(view, "week", add_days(start, 7)),
                       label="Week after", key="next-week")
    if not totals:
        ui.empty("Nothing planned this week. Blocks you add on the timeline are counted here.", icon="bar_chart")
        return
    order = sorted(totals.keys(), key=lambda k: -totals[k])
    planned = sum([totals[k] for k in order])
    week_tasks = [x for x in saved.tasks if x["day"] in days]
    with ui.grid(columns=2):
        ui.stat("Planned", span(planned), caption="in blocks", key="stat-planned")
        ui.stat("Tasks done", f"{len([x for x in week_tasks if x['done']])} of {len(week_tasks)}", key="stat-done")
    ui.chart([round(totals[k] / 60, 2) for k in order], kind="bar", labels=[tag_name(k) for k in order],
             key="chart-tags")
    series = {}
    for k in order:
        series[tag_name(k)] = [round(v, 2) for v in per_tag[k]]
    ui.chart(series, kind="bar", labels=WEEKDAYS, key="chart-days")
    ui.list([ui.item(tag_name(k), icon="sell", trailing=f"{span(totals[k])} · {round(totals[k] * 100 / planned)}%",
                     key="week-tag-" + (k or "none"))
             for k in order], key="week-tags")


def render():
    ui.select([("day", "Day"), ("board", "Board"), ("week", "Week")], value=view.page, style="segmented",
              on_change=lambda v: setattr(view, "page", v), key="page")
    if view.page == "board":
        board_page()
    elif view.page == "week":
        week_page()
    else:
        day_page()


# MARK: - the block page

def open_block(bid, fresh=False):
    view.editing = bid
    plugin.push(block_page, title="New block" if fresh else "Block")


def edit_block(change):
    day, b = find_block(view.editing)
    if b is None:
        return
    change(b)
    save_blocks(day)


def set_block_start(seconds):
    if seconds is None:
        return
    day, b = find_block(view.editing)
    if b is None:
        return
    to_day = day_key(seconds)
    p = time.parts(seconds)
    b["start"] = max(0, min(DAY_MIN - b["length"], snap_near(p["hour"] * 60 + p["minute"])))
    if to_day != day:
        move_block(b["id"], to_day)
        view.day = to_day
        load_events(to_day)
    else:
        save_blocks(day)


def set_block_length(v):
    edit_block(lambda b: b.update({"length": max(STEP, min(DAY_MIN - b["start"], int(v)))}))


def set_block_task(v):
    edit_block(lambda b: b.update({"task": int(v) if v else None}))


def block_page():
    day, b = find_block(view.editing)
    if b is None:
        ui.empty("This block is gone.", icon="event_busy")
        return
    ui.input(label="What", value=b["title"], placeholder=block_title(b),
             on_change=lambda v: edit_block(lambda x: x.update({"title": v[:200]})), key="block-title")
    ui.chips(tag_options(), value=b.get("tag") or "", on_change=lambda v: edit_block(lambda x: x.update({"tag": v})),
             key="block-tag")
    ui.date(label="Starts", value=at_minute(day, b["start"]), time=True, step=STEP, on_change=set_block_start,
            key="block-start")
    ui.stepper(b["length"], min=STEP, max=DAY_MIN - b["start"], step=STEP, label="Minutes",
               on_change=set_block_length, key="block-length")
    open_tasks = [t for t in saved.tasks if (t["day"] in (day, "later") and not t["done"]) or t["id"] == b.get("task")]
    ui.select([("", "No task")] + [(str(t["id"]), t["title"]) for t in open_tasks],
              value=str(b["task"]) if b.get("task") else "", label="Task", on_change=set_block_task, key="block-task")
    t = task_of(b.get("task"))
    if t is not None:
        ui.checkbox(f"{t['title']} is done", value=t["done"], on_change=lambda v, t=t: set_task_done(t, v),
                    key="block-task-done")
    with ui.row():
        ui.button("Done", on_click=plugin.back, primary=True, key="block-done")
        if events_on():
            ui.button("Add to calendar", icon="event", on_click=lambda: add_to_calendar(b, day), key="block-calendar")
        ui.button("Delete", color="danger", icon="delete", on_click=lambda: delete_block(b["id"]), key="block-delete")


# MARK: - the task page

def open_task(tid):
    view.editing = tid
    view.step_text = ""
    t = task_of(tid)
    plugin.push(task_page, title=t["title"] if t else "Task")


def rename_task(t, text):
    t["title"] = text[:200]
    if t.get("todo") is not None:
        t["dirty"] = True


def add_step(t, text):
    text = str(text).strip()
    view.step_text = ""
    if not text:
        return
    s = {"text": text[:200], "done": False, "todo": None}
    t["steps"].append(s)
    if t.get("todo") is not None:
        made = to_todo(lambda: todo.add(s["text"], parent=t["todo"]), t)
        if made:
            s["todo"] = made["id"]


def tick_step(t, i):
    s = t["steps"][i]
    s["done"] = not s["done"]
    if not s["done"]:
        t["done"] = False
    if s.get("todo") is not None:
        to_todo(lambda: todo.update(s["todo"], done=s["done"]), t)


def delete_step(t, i):
    s = t["steps"].pop(i)
    if s.get("todo") is not None:
        to_todo(lambda: todo.remove(s["todo"]), t)


def task_page():
    t = task_of(view.editing)
    if t is None:
        ui.empty("This task is gone.", icon="task_alt")
        return
    ui.input(label="Task", value=t["title"], on_change=lambda v: rename_task(t, v), key="task-title")
    ui.chips(tag_options(), value=t["tag"] or "", on_change=lambda v: t.update({"tag": v}), key="task-tag")
    t_day = today()
    choices = [(t_day, "Today"), (add_days(t_day, 1), "Tomorrow"), ("later", "Later")]
    if t["day"] not in (t_day, add_days(t_day, 1), "later"):
        choices.append((t["day"], day_name(t["day"])))
    ui.select(choices, value=t["day"], style="segmented", on_change=lambda v: set_task_day(t, v), key="task-day")
    ui.stepper(t.get("estimate") or 0, min=0, max=8 * 60, step=STEP, label="Estimate, minutes",
               on_change=lambda v: t.update({"estimate": int(v)}), key="task-estimate")
    rows = []
    for i in range(len(t["steps"])):
        s = t["steps"][i]
        rows.append(ui.item(s["text"], icon="check_box" if s["done"] else "check_box_outline_blank",
                            on_click=lambda i=i: tick_step(t, i), actions={"Delete": lambda i=i: delete_step(t, i)},
                            key=f"step-{i}"))
    with ui.section(f"Steps · {steps_done(t)}/{len(t['steps'])}" if t["steps"] else "Steps", key="steps"):
        ui.list(rows, empty="Break it into steps you can tick off.", key="step-list")
        ui.input(placeholder="Add a step", value=view.step_text, on_change=lambda v: setattr(view, "step_text", v),
                 on_submit=lambda v: add_step(t, v), key="new-step")
    with ui.row():
        ui.button("Not done" if t["done"] else "Done", primary=not t["done"], icon="check",
                  on_click=lambda: set_task_done(t, not t["done"]), key="task-done")
        if not t["done"]:
            ui.button("Schedule", icon="schedule", on_click=lambda: schedule_and_close(t), key="task-schedule")
        ui.button("Delete", color="danger", icon="delete", on_click=lambda: delete_and_close(t), key="task-delete")


def schedule_and_close(t):
    plugin.back()
    schedule(t)


def delete_and_close(t):
    plugin.back()
    delete_task(t)


# MARK: - the tags page

def tags_page():
    for i in range(len(saved.tags)):
        t = saved.tags[i]
        with ui.row(weights=[4, 3, 1], align="center"):
            ui.input(value=t["name"], on_change=lambda v, t=t: t.update({"name": v[:40] or t["name"]}),
                     key=f"tag-name-{t['id']}")
            ui.select([(r, ROLE_NAMES[r]) for r in ROLES], value=t["color"],
                      on_change=lambda v, t=t: t.update({"color": v}), key=f"tag-color-{t['id']}")
            ui.icon_button("delete", on_click=lambda t=t: delete_tag(t), label="Delete tag",
                           key=f"tag-delete-{t['id']}")
    ui.input(placeholder="Add a tag", value=view.tag_text, on_change=lambda v: setattr(view, "tag_text", v),
             on_submit=add_tag, key="new-tag")
    ui.caption("Each tag's colour marks its blocks on the timeline. The week page adds up time by tag.")


def add_tag(text):
    text = str(text).strip()[:40]
    view.tag_text = ""
    if not text:
        return
    color = ROLES[len(saved.tags) % (len(ROLES) - 1)]
    saved.tags.append({"id": "t" + str(fresh_id()), "name": text, "color": color})


def delete_tag(t):
    if t in saved.tags:
        saved.tags.remove(t)


@plugin.command("Today", icon="today")
def today_command():
    go_today()


@plugin.command("Tags", icon="sell")
def tags_command():
    plugin.push(tags_page, title="Tags")


@plugin.keyword("plan")
def from_keyword(text):
    view.page = "day"
    view.day = today()
    if text.strip():
        t = add_task(text, view.day)
        ui.toast(f"Added {t['title']} to today")


@plugin.setting_changed("show_events")
def events_setting(value):
    view.events = {}
    load_events(view.day)


@plugin.setting_changed("todo_sync")
def sync_setting(value):
    pull()


@plugin.setting_changed("remind")
def remind_setting(value):
    rearm()


@plugin.on_open
def opened():
    go_today()
    prune()
    roll_over()
    pull()
    rearm()


@plugin.on_close
def closed():
    flush_titles()
