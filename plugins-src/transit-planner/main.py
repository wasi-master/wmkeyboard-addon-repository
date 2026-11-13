# Transit planner: trips, departures and live arrivals in the keyboard.
#
# Trips and departure boards come from Transitous, a free, community-run
# timetable service covering hundreds of cities (Japan's railways and
# Singapore's buses and MRT among them). Singapore's live bus arrivals come
# from LTA DataMall with the user's own key. Dhaka Metro Line 6 is answered
# from its published timetable, with no network at all.
#
# Tabs: Trips (plan, pinned trips first), Departures (a stop's board),
# SG bus, Dhaka Metro. Either of the last two can be hidden in settings.

import time

from wm import plugin, ui, http, storage, secrets, reminders, share, location

import clock_text
import dhaka
import lta
import motis

try:
    from wm import clock
except ImportError:
    clock = None

MOST_PINS = 6
MOST_RECENTS = 8
MOST_STOPS = 6
REQUESTS_A_MINUTE = 50

saved = plugin.state(
    persist=True,
    pins=[],
    recents=[],
    stops=[],
    sg_stops=[],
    frm=None,
    to=None,
    opts={"speed": "normal", "transfers": -1, "step_free": False, "modes": [], "transfer_minutes": 0},
    order="best",
    metro_from=0,
    metro_to=15,
)

state = plugin.state(
    tab=0,
    busy="",
    error="",
    notice="",
    # The two place boxes: what was typed, and what the search found.
    frm_text="",
    to_text="",
    frm_found=[],
    to_found=[],
    when_mode="now",
    when=None,
    trips=[],
    direct=[],
    earlier=None,
    later=None,
    planned_at=0,
    shown=None,
    same=[],
    same_title="",
    # Departures tab.
    board_stop=None,
    board_text="",
    board_found=[],
    board=[],
    board_earlier=None,
    board_later=None,
    board_at=0,
    leg_board=[],
    trip_view=None,
    # SG bus tab.
    sg_key="",
    sg_stop=None,
    sg_text="",
    sg_found=[],
    sg=[],
    sg_at=0,
    sg_error="",
)

_sent = []


def now():
    return int(time.time())


def apply_settings():
    clock_text.style[0] = plugin.settings.get("time_format", "24h")


apply_settings()


@plugin.setting_changed("time_format")
def time_format_changed(value):
    apply_settings()


def lead_minutes():
    try:
        return max(0, int(plugin.settings.get("lead", 10)))
    except (TypeError, ValueError):
        return 10


def show_sg():
    return bool(plugin.settings.get("sg_bus", True))


def show_metro():
    return bool(plugin.settings.get("dhaka_metro", True))


# ------------------------------------------------------------ requests ----

def allowed():
    """Keep well inside the keyboard's 60 requests a minute, so a burst of
    typing never locks the plugin out."""
    t = now()
    while _sent and _sent[0] < t - 60:
        _sent.pop(0)
    if len(_sent) >= REQUESTS_A_MINUTE:
        state.error = "Too many requests in a minute. Wait a moment and try again."
        return False
    _sent.append(t)
    return True


def failed(what):
    def handler(error):
        state.busy = ""
        if isinstance(error, PermissionError):
            state.error = "Allow internet access for Transit planner on its page in the keyboard's plugin settings."
        elif isinstance(error, TimeoutError):
            state.error = f"{what}: no answer in time. Try again."
        elif isinstance(error, ConnectionError):
            state.error = f"{what}: no connection ({error})."
        else:
            state.error = f"{what}: {error}"
    return handler


def get(url, params, then, what, headers=None):
    if not allowed():
        return False
    state.error = ""
    http.get(url, params=params, headers=headers, then=then, on_error=failed(what))
    return True


def reply_json(r, what):
    """The reply's JSON, or None after saying what went wrong."""
    if r.status_code == 429:
        state.error = f"{what}: the server is busy. Try again in a minute."
        return None
    if not r.ok:
        message = ""
        try:
            body = r.json()
            if isinstance(body, dict):
                message = body.get("error") or body.get("message") or ""
        except ValueError:
            pass
        state.error = f"{what}: the server said {r.status_code}" + (f" ({message})" if message else ".")
        return None
    try:
        return r.json()
    except ValueError:
        state.error = f"{what}: the server sent something unreadable."
        return None


# ------------------------------------------------------------- places ----

def place_line(p):
    bits = []
    if p.get("area"):
        bits.append(p["area"])
    if p.get("stop"):
        modes = [motis.mode_word(m) for m in (p.get("modes") or [])[:3]]
        bits.append("stop" + (" · " + ", ".join(modes) if modes else ""))
    return " · ".join(bits)


def remember_place(p):
    keep = [r for r in saved.recents if not same_place(r, p)]
    saved.recents = [p] + keep[:MOST_RECENTS - 1]


def same_place(a, b):
    if not a or not b:
        return False
    if a.get("stop") or b.get("stop"):
        return a.get("stop") == b.get("stop")
    return abs((a.get("lat") or 0) - (b.get("lat") or 0)) < 1e-4 and abs((a.get("lon") or 0) - (b.get("lon") or 0)) < 1e-4


def near_point():
    """Where to bias place searches: the other end of the trip, if known."""
    for p in (saved.frm, saved.to):
        if p and p.get("lat") is not None:
            return p
    return None


def search_places(side, text, stops_only=False):
    text = text.strip()
    if len(text) < 2:
        setattr(state, side + "_found", [])
        return

    def got(r):
        state.busy = ""
        data = reply_json(r, "Place search")
        if data is None:
            return
        found = motis.geocode_results(data)
        setattr(state, side + "_found", found)
        if not found:
            state.notice = f"Nothing found for “{text}”."

    state.notice = ""
    if get(motis.BASE + "v1/geocode", motis.geocode_params(text, near_point(), stops_only, plugin.locale.split("-")[0]),
           got, "Place search"):
        state.busy = side


def typed(side, stops_only=False):
    """on_change for a place box: search after a short pause in typing."""
    def handler(text):
        setattr(state, side + "_text", text)
        plugin.cancel("find_" + side)
        if len(text.strip()) >= 3:
            plugin.after(0.6, lambda: search_places(side, getattr(state, side + "_text"), stops_only), name="find_" + side)
    return handler


def submitted(side, stops_only=False):
    def handler(text):
        setattr(state, side + "_text", text)
        plugin.cancel("find_" + side)
        search_places(side, text, stops_only)
    return handler


def pick(side, p):
    setattr(state, side + "_found", [])
    setattr(state, side + "_text", "")
    remember_place(p)
    if side == "frm":
        saved.frm = p
    elif side == "to":
        saved.to = p
    elif side == "board":
        state.board_stop = p
        remember_stop(p)
        load_board()
        return
    state.trips = []
    state.direct = []
    if saved.frm and saved.to:
        plan()


def from_here(side="frm"):
    def got(here):
        state.busy = ""
        if not here:
            return
        p = {"name": "My location", "stop": None, "kind": "HERE", "lat": here["lat"], "lon": here["lon"],
             "tz": None, "area": "", "country": None, "modes": []}
        if side == "board":
            nearest_stops(p)
            return
        pick(side, p)

    def refused(error):
        state.busy = ""
        if isinstance(error, PermissionError):
            state.error = "Allow location for Transit planner, then tap again."
        else:
            state.error = f"Location: {error}"

    state.busy = "here"
    location.get(accuracy="fine", then=got, on_error=refused)


def swap():
    saved.frm, saved.to = saved.to, saved.frm
    state.frm_found, state.to_found = state.to_found, state.frm_found
    state.trips = []
    if saved.frm and saved.to:
        plan()


# --------------------------------------------------------------- plan ----

def when_args():
    if state.when_mode == "now" or state.when is None:
        return None, False
    return state.when, state.when_mode == "arrive"


def plan(cursor=None, more=None):
    if not (saved.frm and saved.to):
        state.error = "Choose where from and where to."
        return
    when, arrive = when_args()
    count = int(plugin.settings.get("results", 5) or 5)
    params = motis.plan_params(saved.frm, saved.to, saved.opts, when, arrive, max(1, min(count, 8)), cursor)

    def got(r):
        state.busy = ""
        data = reply_json(r, "Trip search")
        if data is None:
            return
        trips, earlier, later, direct = motis.plan_results(data)
        ends(trips)
        ends(direct)
        if more == "earlier":
            state.trips = trips + [t for t in state.trips if t["id"] not in ids(trips)]
            state.earlier = earlier
        elif more == "later":
            state.trips = state.trips + [t for t in trips if t["id"] not in ids(state.trips)]
            state.later = later
        else:
            state.trips = trips
            state.direct = direct
            state.earlier = earlier
            state.later = later
        state.planned_at = now()
        if not state.trips and not state.direct:
            state.notice = "No trips found. The timetable may not cover this place, or try another time."
        else:
            state.notice = ""

    if get(motis.BASE + "v6/plan", params, got, "Trip search"):
        state.busy = "plan" if more is None else more


def ends(trips, frm=None, to=None):
    frm = frm or saved.frm or {}
    to = to or saved.to or {}
    return motis.name_ends(trips, frm.get("name"), to.get("name"))


def ids(trips):
    return set([t["id"] for t in trips])


def is_pinned(it):
    return any([p["trip"]["id"] == it["id"] for p in saved.pins])


def pin(it):
    if is_pinned(it):
        saved.pins = [p for p in saved.pins if p["trip"]["id"] != it["id"]]
        ui.toast("Unpinned")
        return
    entry = {"trip": slim(it), "frm": saved.frm, "to": saved.to, "at": now()}
    pins = [entry] + saved.pins
    saved.pins = pins[:MOST_PINS]
    try:
        saved.save()
        ui.toast("Pinned: it shows first when you open Transit planner")
    except ValueError:
        saved.pins = pins[1:]
        state.error = "Storage is full. Unpin a trip first."


def slim(it):
    """A trip as it is kept in storage: no line drawings, stops cut short."""
    out = dict(it)
    legs = []
    for l in it["legs"]:
        l2 = dict(l)
        l2.pop("line", None)
        if "stops" in l2:
            l2["stops"] = l2["stops"][:24]
        legs.append(l2)
    out["legs"] = legs
    return out


def drop_old_pins():
    """Pinned trips that ended more than six hours ago are let go."""
    t = now()
    keep = [p for p in saved.pins if (p["trip"].get("end") or 0) > t - 6 * 3600]
    if len(keep) != len(saved.pins):
        saved.pins = keep


def refresh_pin(entry):
    """Look the pinned trip up again for live times: the next trip on the
    same path from its departure time."""
    saved.frm = entry["frm"]
    saved.to = entry["to"]
    state.when_mode = "depart"
    state.when = entry["trip"]["start"] - 60
    old = entry["trip"]

    def replace(found):
        for p in saved.pins:
            if p["trip"]["id"] == old["id"]:
                p["trip"] = slim(found)
                p["at"] = now()
        saved.pins = list(saved.pins)

    same_path(old, "later", replace)


def same_path(it, direction, done=None):
    """The trips before or after [it] that ride the same routes."""
    frm = saved.frm or place_of(it["legs"][0]["from"])
    to = saved.to or place_of(it["legs"][-1]["to"])
    if direction == "later":
        params = motis.plan_params(frm, to, saved.opts, it["start"] + (0 if done else 60), False, 6, geometry=False)
    else:
        params = motis.plan_params(frm, to, saved.opts, it["end"] - 60, True, 6, geometry=False)

    def got(r):
        state.busy = ""
        data = reply_json(r, "Same route")
        if data is None:
            return
        trips, _, _, _ = motis.plan_results(data)
        ends(trips, frm, to)
        if done:
            fits = [t for t in trips if t["sig"] == it["sig"]]
        else:
            fits = [t for t in trips if t["sig"] == it["sig"] and t["id"] != it["id"]]
        if done:
            if fits:
                done(fits[0])
                ui.toast("Times brought up to date")
            else:
                state.notice = "That trip is no longer in the timetable."
            return
        if direction == "earlier":
            fits.reverse()
        state.same = fits[:4]
        state.same_title = "Earlier on this route" if direction == "earlier" else "Later on this route"
        if not fits:
            state.notice = "No other trip on exactly this route in that window."

    if get(motis.BASE + "v6/plan", params, got, "Same route"):
        state.busy = "same"


def first_last(it, which):
    """The first trip of the day from 03:00, or the last one arriving
    before 03:00 the next morning."""
    frm = saved.frm or place_of(it["legs"][0]["from"])
    to = saved.to or place_of(it["legs"][-1]["to"])
    zone = motis.first_zone(it)
    if which == "first":
        params = motis.plan_params(frm, to, saved.opts, clock_text.day_start(it["start"], zone, 3), False, 1, geometry=False)
    else:
        params = motis.plan_params(frm, to, saved.opts, clock_text.day_start(it["start"], zone, 3) + 86400, True, 1,
                                   geometry=False)

    def got(r):
        state.busy = ""
        data = reply_json(r, "First and last")
        if data is None:
            return
        trips, _, _, _ = motis.plan_results(data)
        ends(trips, frm, to)
        state.same = trips[:1]
        state.same_title = "First trip of the day" if which == "first" else "Last trip of the day"
        if not trips:
            state.notice = "The timetable has no trip that day."

    if get(motis.BASE + "v6/plan", params, got, "First and last"):
        state.busy = "same"


def place_of(stop):
    return {"name": stop["name"], "stop": stop.get("parent") or stop.get("stop"), "lat": stop.get("lat"),
            "lon": stop.get("lon"), "tz": stop.get("tz"), "kind": "STOP", "area": "", "modes": []}


# ---------------------------------------------------- reminders, alarms ----

def remind(it, which):
    lead = lead_minutes()
    zone = motis.first_zone(it)
    legs = it["legs"]
    if which == "leave":
        at = it["start"] - lead * 60
        text = f"Leave now for the {clock_text.hm(it['start'], zone)} trip to {legs[-1]['to']['name']}"
    else:
        last = [l for l in legs if motis.is_transit(l)]
        stop = (last[-1]["to"] if last else legs[-1]["to"])
        at = stop["t"] - lead * 60
        text = f"{stop['name']} in {lead} min: get ready to get off"
    if at <= now():
        state.error = "That time has already passed."
        return
    try:
        reminders.set(f"{which}:{it['id'][:40]}", at, text)
        ui.toast(f"Reminder at {clock_text.hm(at, zone)}")
    except ValueError as e:
        state.error = f"Reminder: {e}"


def alarm(it, which):
    lead = lead_minutes()
    zone = motis.first_zone(it)
    stop = it["legs"][0]["from"] if which == "leave" else it["legs"][-1]["to"]
    at = (it["start"] if which == "leave" else stop["t"]) - lead * 60
    if at <= now():
        state.error = "That time has already passed."
        return
    label = f"Trip to {it['legs'][-1]['to']['name']}" if which == "leave" else f"Arriving at {stop['name']}"
    try:
        clock.alarm(at, label)
        ui.toast(f"Alarm set for {clock_text.hm(at, zone)}")
    except ValueError as e:
        state.error = f"Alarm: {e}"
    except PermissionError:
        state.error = "Allow Clock for Transit planner on its page in the keyboard's plugin settings."


def timer(it, which):
    lead = lead_minutes()
    target = it["start"] if which == "leave" else it["end"]
    seconds = target - lead * 60 - now()
    if seconds < 60:
        state.error = "That is less than a minute away."
        return
    label = "Time to leave" if which == "leave" else f"{it['legs'][-1]['to']['name']} soon"
    try:
        clock.timer(seconds, label)
        ui.toast(f"Timer: {clock_text.duration(seconds)}")
    except ValueError as e:
        state.error = f"Timer: {e}"
    except PermissionError:
        state.error = "Allow Clock for Transit planner on its page in the keyboard's plugin settings."


def ask_when(title, fn, it):
    lead = lead_minutes()

    def chosen(button):
        if button == "Before leaving":
            fn(it, "leave")
        elif button == "Before arriving":
            fn(it, "arrive")

    ui.dialog(title, f"{lead} minutes before (change this in the plugin's settings).",
              buttons=("Before leaving", "Before arriving", "Cancel"), on_result=chosen)


# ------------------------------------------------------------ departures ----

def remember_stop(p):
    keep = [s for s in saved.stops if s.get("stop") != p.get("stop")]
    saved.stops = [p] + keep[:MOST_STOPS - 1]


def nearest_stops(here):
    """Stops near the phone: a reverse look-up, stops only."""
    def got(r):
        state.busy = ""
        data = reply_json(r, "Nearby stops")
        if data is None:
            return
        found = [p for p in motis.geocode_results(data) if p.get("stop")]
        state.board_found = found
        if not found:
            state.notice = "No stops nearby in the timetable."

    params = {"place": f"{here['lat']:.6f},{here['lon']:.6f}", "type": "STOP"}
    if get(motis.BASE + "v1/reverse-geocode", params, got, "Nearby stops"):
        state.busy = "board"


def load_board(direction=None):
    stop = state.board_stop
    if not stop:
        return
    cursor = None
    if direction == "earlier":
        cursor = state.board_earlier
    elif direction == "later":
        cursor = state.board_later

    def got(r):
        state.busy = ""
        data = reply_json(r, "Departures")
        if data is None:
            return
        rows, earlier, later = motis.stoptimes_results(data)
        if direction == "earlier":
            state.board = rows + state.board
            state.board_earlier = earlier
        elif direction == "later":
            state.board = state.board + rows
            state.board_later = later
        else:
            state.board = rows
            state.board_earlier = earlier
            state.board_later = later
        state.board_at = now()

    if get(motis.BASE + "v6/stoptimes", motis.stoptimes_params(stop["stop"], count=20, cursor=cursor), got, "Departures"):
        state.busy = "board"


def leg_departures(leg):
    """Other departures of the same line from the leg's stop, around its time."""
    def got(r):
        state.busy = ""
        data = reply_json(r, "Departures")
        if data is None:
            return
        rows, _, _ = motis.stoptimes_results(data)
        same = [s for s in rows if s["route"] == leg.get("route") and s["dir"] == leg.get("dir")]
        state.leg_board = same or rows
        plugin.push(leg_board_page, title=f"{leg['name']} from {leg['from']['name']}")

    params = motis.stoptimes_params(leg["from"]["stop"], when=leg["from"]["t"] - 30 * 60, count=40)
    if get(motis.BASE + "v6/stoptimes", params, got, "Departures"):
        state.busy = "leg"


def open_trip(row):
    def got(r):
        state.busy = ""
        data = reply_json(r, "Trip")
        if data is None:
            return
        trips, _, _, _ = motis.plan_results({"itineraries": [data]})
        if trips:
            state.trip_view = trips[0]
            plugin.push(trip_page, title=f"{row['name']} to {row['headsign']}")

    if get(motis.BASE + "v6/trip", {"tripId": row["trip"], "detailedLegs": "false"}, got, "Trip"):
        state.busy = "trip"


# --------------------------------------------------------------- SG bus ----

def load_sg():
    code = lta.stop_code((state.sg_stop or {}).get("code") or (state.sg_stop or {}).get("stop"))
    if not code or not state.sg_key:
        return

    def got(r):
        state.busy = ""
        if r.status_code in (401, 403):
            state.sg_error = "LTA did not accept the key. Check it, or ask LTA for a new one."
            return
        data = reply_json(r, "Bus arrivals")
        if data is None:
            return
        state.sg_error = ""
        state.sg = lta.services(data, now())
        state.sg_at = now()

    if get(lta.URL, {"BusStopCode": code}, got, "Bus arrivals", headers={"AccountKey": state.sg_key, "accept": "application/json"}):
        state.busy = "sg"


def sg_pick(p):
    code = lta.stop_code(p.get("stop") or p.get("code"))
    if not code:
        state.notice = "That is not a bus stop with a five-digit code."
        return
    p = dict(p)
    p["code"] = code
    state.sg_stop = p
    state.sg_found = []
    state.sg_text = ""
    keep = [s for s in saved.sg_stops if s.get("code") != code]
    saved.sg_stops = [p] + keep[:MOST_STOPS - 1]
    state.sg = []
    load_sg()


def sg_typed(text):
    code = lta.stop_code(text)
    if code and text.strip() == code:
        sg_pick({"name": f"Stop {code}", "code": code, "stop": None, "lat": None, "lon": None, "area": ""})
        return
    search_places("sg", text, stops_only=True)


@plugin.setting_changed("lta_key")
def key_changed(value):
    """The key typed on the settings page is the same secret."""
    state.sg_key = (value or "").strip()
    state.sg = []
    if state.sg_key:
        load_sg()


# ---------------------------------------------------------------- events ----

@plugin.on_open
def opened():
    try:
        state.sg_key = secrets.get("lta_key", "") or ""
    except (PermissionError, NotImplementedError):
        state.sg_key = ""
    drop_old_pins()


@plugin.every(seconds=30, name="tick")
def tick():
    """Countdowns move on; live boards look again now and then."""
    t = now()
    sg_tab = 2 if show_sg() else -1
    if state.tab == sg_tab and state.sg_stop and state.sg_key and t - state.sg_at >= 30 and not state.busy:
        load_sg()
    if state.tab == 1 and state.board_stop and t - state.board_at >= 90 and not state.busy:
        load_board()


@plugin.command("Refresh", icon="refresh")
def refresh():
    if state.tab == 0:
        if state.trips:
            plan()
        elif saved.pins:
            refresh_pin(saved.pins[0])
    elif state.tab == 1:
        load_board()
    elif show_sg() and state.tab == 2:
        load_sg()


@plugin.keyword("transit")
def from_keyword(text):
    """@transit Shibuya, or @transit Shinjuku to Tokyo."""
    text = text.strip()
    if not text:
        return
    state.tab = 0
    lower = text.lower()
    at = lower.find(" to ")
    if at > 0:
        state.frm_text = text[:at]
        state.to_text = text[at + 4:]
        search_places("frm", state.frm_text)
        search_places("to", state.to_text)
    else:
        state.to_text = text
        search_places("to", text)


def tab_changed(i):
    state.tab = i
    state.error = ""
    state.notice = ""


# -------------------------------------------------------------- drawing ----

def status_line():
    if state.error:
        ui.label(state.error, color="danger")
    elif state.notice:
        ui.caption(state.notice)


def place_box(side, label, current):
    text = getattr(state, side + "_text")
    found = getattr(state, side + "_found")
    with ui.row(weights=[1, 0]):
        ui.search(placeholder=(current["name"] if current else label), value=text, on_change=typed(side),
                  on_submit=submitted(side), key=side + "_box")
        ui.icon_button("my_location", on_click=lambda: from_here(side), label="Use my location", key=side + "_here")
    if current and not found and not text:
        ui.caption(f"{label}: {current['name']}" + (f" · {current['area']}" if current.get("area") else ""))
    if state.busy == side:
        ui.progress()
    if found:
        ui.list([ui.item(p["name"], subtitle=place_line(p), icon=("train" if p.get("stop") else "place"),
                         on_click=lambda p=p: pick(side, p)) for p in found], key=side + "_found")


def recents_chips(side):
    if not saved.recents or getattr(state, side + "_found") or getattr(state, side + "_text"):
        return
    options = [(str(i), r["name"][:24]) for i, r in enumerate(saved.recents)]

    def chosen(value):
        pick(side, saved.recents[int(value)])

    ui.chips(options, value=None, on_change=chosen, key=side + "_recent")


def options_section():
    opts = saved.opts

    def set_opt(name):
        def handler(value):
            o = dict(saved.opts)
            o[name] = value
            saved.opts = o
        return handler

    def set_transfers(value):
        set_opt("transfers")(int(value))

    with ui.section("Options", collapsible=True, open=False, key="options"):
        ui.select([("slow", "Slow"), ("normal", "Normal"), ("fast", "Fast")], value=opts.get("speed", "normal"),
                  on_change=set_opt("speed"), label="Walking speed", style="segmented", key="speed")
        ui.select([("-1", "Any"), ("0", "None"), ("1", "1"), ("2", "2"), ("3", "3")],
                  value=str(opts.get("transfers", -1)), on_change=set_transfers, label="Most changes",
                  style="segmented", key="transfers")
        ui.chips([("rail", "Train"), ("metro", "Metro and tram"), ("bus", "Bus"), ("ferry", "Ferry")],
                 value=opts.get("modes") or [], on_change=set_opt("modes"), multi=True, key="modes")
        ui.caption("No mode picked means every mode.")
        ui.stepper(opts.get("transfer_minutes", 0), min=0, max=20, step=1, on_change=set_opt("transfer_minutes"),
                   label="Extra minutes at each change", key="transfer_minutes")
        ui.toggle("Step-free (lifts, no stairs)", value=bool(opts.get("step_free")), on_change=set_opt("step_free"),
                  key="step_free")


def when_row():
    def set_mode(value):
        state.when_mode = value
        if value != "now" and state.when is None:
            state.when = now() + 15 * 60

    ui.select([("now", "Now"), ("depart", "Leave at"), ("arrive", "Arrive by")], value=state.when_mode,
              on_change=set_mode, style="segmented", key="when_mode")
    if state.when_mode != "now":
        def set_when(value):
            state.when = value
        ui.date(label="Time", value=state.when, time=True, step=5, on_change=set_when, key="when")


def trip_item(it, t, on_click, pinned=False):
    zone = motis.first_zone(it)
    bits = [clock_text.duration(it["dur"]), motis.changes_text(it["transfers"]), motis.leg_chain(it)]
    if it.get("fare"):
        bits.append(motis.money(it["fare"]))
    late = max([motis.delay_minutes(l["from"]) for l in it["legs"] if motis.is_transit(l)] or [0])
    if late > 0:
        bits.append(f"+{late} min late")
    cancelled = any([l.get("cancelled") for l in it["legs"]])
    title = motis.trip_title(it, t)
    if not clock_text.same_day(it["start"], t, zone):
        title = clock_text.day_label(it["start"], zone) + " " + title
    return ui.item(title, subtitle=("Cancelled · " if cancelled else "") + " · ".join(bits),
                   icon=("push_pin" if pinned else motis.icon(first_mode(it))),
                   trailing=clock_text.until(it["start"], t), on_click=on_click)


def first_mode(it):
    for l in it["legs"]:
        if motis.is_transit(l):
            return l["mode"]
    return "WALK"


def show_trip(it, frm=None, to=None):
    state.shown = {"trip": it, "frm": frm or saved.frm, "to": to or saved.to}
    state.same = []
    state.same_title = ""
    plugin.push(trip_detail_page, title=f"{(frm or saved.frm or {}).get('name', '')} → {(to or saved.to or {}).get('name', '')}")


def trips_tab():
    t = now()
    if saved.pins:
        with ui.section("Pinned", key="pinned"):
            ui.list([trip_item(p["trip"], t, (lambda p=p: show_trip(p["trip"], p["frm"], p["to"])), pinned=True)
                     for p in saved.pins], key="pins")
    place_box("frm", "From", saved.frm)
    recents_chips("frm")
    with ui.row(weights=[1, 0]):
        ui.spacer(1)
        ui.icon_button("swap_vert", on_click=swap, label="Swap", key="swap")
    place_box("to", "To", saved.to)
    recents_chips("to")
    when_row()
    options_section()
    ui.button("Find trips", on_click=lambda: plan(), primary=True, enabled=bool(saved.frm and saved.to),
              icon="search", key="find")
    status_line()
    if state.busy == "plan":
        ui.progress()
    if state.trips:
        has_fares = any([i.get("fare") for i in state.trips])
        orders = [("best", "Earliest"), ("fastest", "Fastest"), ("transfers", "Fewest changes"), ("walk", "Least walking")]
        if has_fares:
            orders.append(("cheapest", "Cheapest"))

        def set_order(value):
            saved.order = value

        order = saved.order if (saved.order != "cheapest" or has_fares) else "best"
        ui.chips(orders, value=order, on_change=set_order, key="order")
        if state.earlier:
            ui.button("Earlier", on_click=lambda: plan(state.earlier, "earlier"), icon="expand_less", key="earlier")
        ui.list([trip_item(it, t, (lambda it=it: show_trip(it))) for it in motis.sort_trips(state.trips, order)],
                key="trips")
        if state.later:
            ui.button("Later", on_click=lambda: plan(state.later, "later"), icon="expand_more", key="later")
    for it in state.direct[:1]:
        ui.caption(f"Walking all the way: {clock_text.duration(it['dur'])}")
    attribution()


def attribution():
    with ui.row(weights=[1, 0]):
        ui.caption("Timetables: Transitous and its sources, map data © OpenStreetMap contributors.")
        ui.button("Sources", on_click=lambda: share.open(motis.SOURCES), key="sources")


def leg_card(l, it_zone):
    zone = l["from"].get("tz") or it_zone
    if not motis.is_transit(l):
        dist = l.get("dist")
        text = f"{motis.mode_word(l['mode'])} {clock_text.duration(l['dur'])}"
        if dist:
            text += f" · {int(round(dist))} m" if dist < 1000 else f" · {dist / 1000:.1f} km"
        with ui.row(weights=[0, 1]):
            ui.icon(motis.icon(l["mode"]), color="muted")
            ui.caption(text)
        return
    title = f"{motis.mode_word(l['mode'])} {l['name']}" + (f" towards {l['headsign']}" if l.get("headsign") else "")
    with ui.card(title=title):
        late = motis.delay_minutes(l["from"])
        where = motis.platform_text(l["from"])
        line = f"{clock_text.hm(l['from']['t'], zone)}  {l['from']['name']}" + (f" · {where}" if where else "")
        ui.label(line, color=("danger" if l.get("cancelled") else None))
        if late:
            ui.caption(f"Planned {clock_text.hm(l['from']['planned'], zone)}, {'+' if late > 0 else ''}{late} min")
        n = len(l.get("stops") or [])
        info = [clock_text.duration(l["dur"]), f"{n + 1} stop" + ("" if n == 0 else "s")]
        if l.get("long") and l["long"] != l["name"]:
            info.append(l["long"])
        if l.get("trip_no") and l["trip_no"] != l["name"]:
            info.append(f"no. {l['trip_no']}")
        if l.get("agency"):
            info.append(l["agency"])
        if l.get("step_free"):
            info.append("step-free")
        if l.get("rt"):
            info.append("live")
        ui.caption(" · ".join(info))
        if l.get("stops"):
            with ui.section("Stops on the way", collapsible=True, open=False):
                for s in l["stops"]:
                    ui.caption(f"{clock_text.hm(s[1], zone) if s[1] else '     '}  {s[0]}")
        to_zone = l["to"].get("tz") or zone
        where = motis.platform_text(l["to"])
        ui.label(f"{clock_text.hm(l['to']['t'], to_zone)}  {l['to']['name']}" + (f" · {where}" if where else ""))
        if l["from"].get("stop"):
            ui.button("Other departures", on_click=lambda: leg_departures(l), icon="schedule")


def sketch(it):
    """The trip's path, drawn small: rides thick, walks thin."""
    points = []
    for l in it["legs"]:
        points.extend(l.get("line") or [])
    if len(points) < 2:
        return
    lat0 = min([p[0] for p in points])
    lat1 = max([p[0] for p in points])
    lon0 = min([p[1] for p in points])
    lon1 = max([p[1] for p in points])
    import math
    squeeze = math.cos(math.radians((lat0 + lat1) / 2))
    span_x = max((lon1 - lon0) * squeeze, 1e-6)
    span_y = max(lat1 - lat0, 1e-6)
    w, h, pad = 320, 150, 14
    scale = min((w - 2 * pad) / span_x, (h - 2 * pad) / span_y)
    ox = (w - span_x * scale) / 2
    oy = (h - span_y * scale) / 2

    def xy(p):
        return ox + (p[1] - lon0) * squeeze * scale, h - (oy + (p[0] - lat0) * scale)

    shapes = []
    for l in it["legs"]:
        line = l.get("line") or []
        ride = motis.is_transit(l)
        k = 1
        while k < len(line):
            x1, y1 = xy(line[k - 1])
            x2, y2 = xy(line[k])
            shapes.append(ui.line(x1, y1, x2, y2, color=("primary" if ride else "muted"), width=(4 if ride else 2)))
            k += 1
        if ride and line:
            x, y = xy(line[0])
            shapes.append(ui.circle(x, y, 5, color="accent"))
    sx, sy = xy(points[0])
    ex, ey = xy(points[-1])
    shapes.append(ui.circle(sx, sy, 6, color="success"))
    shapes.append(ui.circle(ex, ey, 6, color="danger"))
    ui.canvas(w, h, shapes, key="sketch")


def trip_detail_page():
    shown = state.shown
    if not shown:
        ui.empty("No trip")
        return
    it = shown["trip"]
    t = now()
    zone = motis.first_zone(it)
    pinned = is_pinned(it)
    with ui.row():
        ui.stat("Leave", clock_text.hm(it["start"], zone), caption=clock_text.until(it["start"], t))
        ui.stat("Arrive", clock_text.hm(it["end"], motis.last_zone(it)), caption=clock_text.duration(it["dur"]))
        ui.stat("Changes", str(it["transfers"]), caption=motis.money(it.get("fare")) or None)
    if not clock_text.same_day(it["start"], t, zone):
        ui.caption(clock_text.day_label(it["start"], zone))
    with ui.row():
        ui.button("Unpin" if pinned else "Pin", on_click=lambda: pin(it), icon="push_pin", key="pin")
        ui.button("Remind", on_click=lambda: ask_when("Remind me", remind, it), icon="notifications", key="remind")
        if clock is not None:
            ui.button("Alarm", on_click=lambda: ask_when("Set an alarm", alarm, it), icon="alarm", key="alarm")
            ui.button("Timer", on_click=lambda: ask_when("Start a timer", timer, it), icon="timer", key="timer")
    status_line()
    for l in it["legs"]:
        leg_card(l, zone)
    sketch(it)
    with ui.section("This journey at other times", key="other_times"):
        with ui.grid(columns=2):
            ui.button("Earlier, same route", on_click=lambda: same_path(it, "earlier"), key="same_earlier")
            ui.button("Later, same route", on_click=lambda: same_path(it, "later"), key="same_later")
            ui.button("First of the day", on_click=lambda: first_last(it, "first"), key="first")
            ui.button("Last of the day", on_click=lambda: first_last(it, "last"), key="last")
        if state.busy == "same":
            ui.progress()
        if state.same:
            ui.caption(state.same_title)
            ui.list([trip_item(o, t, (lambda o=o: show_trip(o, shown["frm"], shown["to"]))) for o in state.same],
                    key="same")
    text = motis.summary(it, (shown.get("frm") or {}).get("name"), (shown.get("to") or {}).get("name"))
    ui.output(text, key="summary")
    ui.button("Share", on_click=lambda: share.text(text, title="Trip"), icon="share", key="share")


def board_row(s, t):
    zone = s.get("tz")
    late = motis.delay_minutes(s)
    bits = [s["headsign"]] if s.get("headsign") else []
    where = motis.platform_text(s)
    if where:
        bits.append(where)
    if s.get("cancelled"):
        bits.insert(0, "Cancelled")
    elif late > 0:
        bits.append(f"+{late} min")
    elif s.get("rt"):
        bits.append("on time")
    return ui.item(f"{clock_text.hm(s['t'], zone)}  {s['name']}", subtitle=" · ".join(bits),
                   icon=motis.icon(s.get("mode")), trailing=clock_text.until(s["t"], t),
                   on_click=lambda: open_trip(s))


def leg_board_page():
    t = now()
    status_line()
    ui.list([board_row(s, t) for s in state.leg_board], empty="No departures in this hour.", key="leg_board")


def trip_page():
    it = state.trip_view
    if not it:
        return
    for l in it["legs"]:
        if not motis.is_transit(l):
            continue
        zone = l["from"].get("tz")
        rows = [ui.item(l["from"]["name"], trailing=clock_text.hm(l["from"]["t"], zone))]
        for s in l.get("stops") or []:
            rows.append(ui.item(s[0], trailing=clock_text.hm(s[1], zone) if s[1] else ""))
        rows.append(ui.item(l["to"]["name"], trailing=clock_text.hm(l["to"]["t"], zone)))
        ui.caption(" · ".join([b for b in [l.get("long"), l.get("agency")] if b]))
        ui.list(rows, key="trip_stops")


def departures_tab():
    t = now()
    with ui.row(weights=[1, 0]):
        ui.search(placeholder="Station or stop", value=state.board_text, on_change=typed("board", True),
                  on_submit=submitted("board", True), key="board_box")
        ui.icon_button("near_me", on_click=lambda: from_here("board"), label="Stops near me", key="board_here")
    if not state.board_found and not state.board_text and saved.stops:
        options = [(str(i), s["name"][:24]) for i, s in enumerate(saved.stops)]

        def chosen(value):
            pick("board", saved.stops[int(value)])

        ui.chips(options, value=None, on_change=chosen, key="board_recent")
    if state.board_found:
        ui.list([ui.item(p["name"], subtitle=place_line(p), icon="train", on_click=lambda p=p: pick("board", p))
                 for p in state.board_found], key="board_found")
    status_line()
    if state.busy == "board":
        ui.progress()
    if state.board_stop:
        ui.label(state.board_stop["name"], style="title")
        if state.board_earlier:
            ui.button("Earlier", on_click=lambda: load_board("earlier"), icon="expand_less", key="board_earlier")
        ui.list([board_row(s, t) for s in state.board], empty="No departures soon.", key="board")
        if state.board_later:
            ui.button("Later", on_click=lambda: load_board("later"), icon="expand_more", key="board_later")
    elif not state.board_found:
        ui.empty("Find a station to see what leaves next.", icon="departure_board")
    attribution()


def sg_tab():
    t = now()
    if not state.sg_key:
        ui.markdown("Live bus arrivals come from **LTA DataMall**. Ask LTA for a free AccountKey, "
                    "then enter it on this plugin's settings page. It stays on this phone, out of backups.")
        with ui.row():
            ui.button("Get a key from LTA", on_click=lambda: share.open(lta.SIGN_UP), icon="open_in_new", key="sg_signup")
            ui.button("Open settings", on_click=plugin.open_settings, primary=True, icon="settings", key="sg_settings")
        if state.sg_error:
            ui.label(state.sg_error, color="danger")
        return
    ui.search(placeholder="Bus stop name or 5-digit code", value=state.sg_text, on_submit=sg_typed, key="sg_box")
    if not state.sg_found and saved.sg_stops:
        options = [(s["code"], (s["name"] + " " + s["code"])[:28]) for s in saved.sg_stops]

        def chosen(value):
            for s in saved.sg_stops:
                if s["code"] == value:
                    sg_pick(s)

        ui.chips(options, value=(state.sg_stop or {}).get("code"), on_change=chosen, key="sg_recent")
    if state.sg_found:
        found = [p for p in state.sg_found if p.get("country") in (None, "SG") and lta.stop_code(p.get("stop"))]
        ui.list([ui.item(p["name"], subtitle=f"{lta.stop_code(p['stop'])} · {p.get('area') or ''}", icon="directions_bus",
                         on_click=lambda p=p: sg_pick(p)) for p in found],
                empty="No Singapore bus stop by that name.", key="sg_found")
    if state.sg_error:
        ui.label(state.sg_error, color="danger")
    status_line()
    if state.busy == "sg":
        ui.progress()
    stop = state.sg_stop
    if stop:
        ui.label(f"{stop['name']} ({stop['code']})", style="title")
        rows = []
        for s in state.sg:
            buses = s["buses"]
            if not buses:
                rows.append(ui.item(s["no"], subtitle="Not in service now", icon="directions_bus"))
                continue
            first = buses[0]
            subtitle = " · ".join([b for b in [first["load"], first["type"], "step-free" if first["step_free"] else "",
                                                "" if first["live"] else "timetable"] if b])
            later = ", ".join([lta.arrival_text(b) for b in buses[1:]])
            rows.append(ui.item(s["no"], subtitle=subtitle + (f" · then {later}" if later else ""),
                                icon="directions_bus", trailing=lta.arrival_text(first)))
        ui.list(rows, empty="No buses at this stop right now.", key="sg_services")
        if state.sg_at:
            ui.caption(f"Updated {clock_text.until(state.sg_at, t)}. Looks again every 30 seconds while this tab is open.")
    ui.caption("Contains information from LTA DataMall accessed under the Singapore Open Data Licence.")


def metro_tab():
    t = now()
    names = [(str(i), s["name"]) for i, s in enumerate(dhaka.STATIONS)]

    def set_from(value):
        saved.metro_from = int(value)

    def set_to(value):
        saved.metro_to = int(value)

    def flip():
        saved.metro_from, saved.metro_to = saved.metro_to, saved.metro_from

    a = saved.metro_from
    b = saved.metro_to
    with ui.row(weights=[1, 0, 1]):
        ui.select(names, value=str(a), on_change=set_from, label="From", key="metro_from")
        ui.icon_button("swap_horiz", on_click=flip, label="Swap", key="metro_swap")
        ui.select(names, value=str(b), on_change=set_to, label="To", key="metro_to")
    if a == b:
        ui.caption("Pick two different stations.")
        return
    trains = dhaka.next_trains(a, b, t, 4)
    fare = dhaka.fare(a, b)
    with ui.row():
        ui.stat("Fare", f"৳{fare}", caption=f"৳{dhaka.card_fare(a, b)} with a card")
        ui.stat("Ride", f"{dhaka.ride_minutes(a, b)} min", caption=f"{abs(b - a)} stops")
    if trains:
        rows = []
        for dep, arr in trains:
            rows.append(ui.item(f"{clock_text.hm(dep, dhaka.ZONE)} → {clock_text.hm(arr, dhaka.ZONE)}",
                                subtitle=f"towards {dhaka.STATIONS[dhaka.terminus(a, b)]['name']}",
                                icon="subway", trailing=clock_text.until(dep, t)))
        ui.list(rows, key="metro_trains")
    else:
        ui.empty("No more trains today.", icon="subway")
    first, last = dhaka.first_last(a, b, t)
    if first is not None:
        line = f"Today: first train {clock_text.hm(first, dhaka.ZONE)}, last {clock_text.hm(last, dhaka.ZONE)}."
        every = dhaka.headway_now(a, b, t)
        if every:
            line += f" Every {every} min now."
        ui.caption(line)
    ui.caption(dhaka.NOTE)


def render():
    tabs = [ui.page("Trips", *collect(trips_tab)), ui.page("Departures", *collect(departures_tab))]
    if show_sg():
        tabs.append(ui.page("SG bus", *collect(sg_tab)))
    if show_metro():
        tabs.append(ui.page("Dhaka Metro", *collect(metro_tab)))
    ui.tabs(*tabs, on_change=tab_changed, key="tabs")


def collect(draw):
    """What [draw] puts on screen, as a list for ui.page."""
    with ui.column() as box:
        draw()
    return [box]
