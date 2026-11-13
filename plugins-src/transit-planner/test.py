# Tests for Transit Planner, run by tools/test_plugins.py under
# wm-python-cli. The replies in tests/ are real Transitous answers (trimmed),
# with their times moved to "a few hours from now" so the tests never age.

import json
import time
import plugin_test

import clock_text as ct
import dhaka
import motis
import lta

NOW = int(time.time())


def shifted(value, by):
    """[value] with every ISO time string in it moved by [by] seconds."""
    if isinstance(value, dict):
        return {k: shifted(v, by) for k, v in value.items()}
    if isinstance(value, list):
        return [shifted(v, by) for v in value]
    if isinstance(value, str) and len(value) == 20 and value[4:5] == "-" and value[10:11] == "T" and value[-1] == "Z":
        t = ct.parse_iso(value)
        if t is not None:
            return ct.iso(t + by)
    return value


def fixture(name):
    return json.loads(plugin_test.read("tests/" + name))


PLAN_RAW = fixture("plan.json")
FIRST_START = ct.parse_iso(PLAN_RAW["itineraries"][0]["startTime"])
# The first trip leaves three hours from now, to the minute.
SHIFT = (NOW + 3 * 3600) // 60 * 60 - FIRST_START
PLAN = shifted(PLAN_RAW, SHIFT)
STOPTIMES = shifted(fixture("stoptimes.json"), SHIFT)
# LTA writes Singapore time with its offset.
def sgt(t):
    return ct.iso(t + 8 * 3600)[:19] + "+08:00"


LTA_TEXT = (plugin_test.read("tests/lta.json").replace("ARR1", sgt(NOW + 4 * 60 + 20))
            .replace("ARR2", sgt(NOW + 13 * 60 + 20)).replace("ARR3", sgt(NOW + 30)))

TOKYO = {"rows": [[-62135596800, 32400]]}


def ok(status, body):
    return {"status": status, "text": body if isinstance(body, str) else json.dumps(body), "headers": {}}


def route(url, body, status=200, **when):
    w = {"url": url}
    w.update(when)
    return {"when": w, "reply": ok(status, body)}


BASE = "https://api.transitous.org/api/"
MOCK = {
    "http.request": [
        route(BASE + "v1/geocode", fixture("geocode_shinjuku.json"), params={"text": "Shinjuku"}),
        route(BASE + "v1/geocode", fixture("geocode_tokyo.json"), params={"text": "Tokyo Station"}),
        route(BASE + "v1/geocode", fixture("geocode_sg.json"), params={"text": "Jurong East Int"}),
        route(BASE + "v6/plan", PLAN),
        route(BASE + "v6/stoptimes", STOPTIMES),
        route("https://datamall2.mytransport.sg/*", LTA_TEXT),
    ],
    "time.zone": TOKYO,
    "location.get": {"lat": 35.6896, "lon": 139.7006, "accuracy": 20, "time": NOW},
    "clock.alarm": None,
    "clock.timer": None,
    "share.open": None,
    "share.text": None,
    "secrets.get": None,
    "secrets.set": None,
    "secrets.remove": None,
    "ui.toast": None,
    "plugin.open_settings": None,
    "ui.dialog": None,
}


def text_of(tree):
    return json.dumps(tree, ensure_ascii=False)


def find(tree, pred):
    """Every widget dict in [tree] for which pred(widget) is true."""
    out = []
    if isinstance(tree, dict):
        if pred(tree):
            out.append(tree)
        for v in tree.values():
            out.extend(find(v, pred))
    elif isinstance(tree, list):
        for v in tree:
            out.extend(find(v, pred))
    return out


def ids(tree, prefix):
    return [w.get("id") for w in find(tree, lambda w: isinstance(w.get("id"), str) and w["id"].startswith(prefix))]


def check(r):
    assert r["ok"], r.get("error")
    return r


# ---------------------------------------------------------------- pure ----

# Civil dates both ways, and ISO with offsets.
assert ct.days_from_civil(1970, 1, 1) == 0
assert ct.civil_from_days(ct.days_from_civil(2024, 2, 29)) == (2024, 2, 29)
assert ct.parse_iso("2026-11-14T21:00:00Z") == ct.parse_iso("2026-11-15T05:00:00+08:00")
assert ct.parse_iso("2026-11-14T21:00:00.250Z") == ct.parse_iso("2026-11-14T21:00:00Z")
assert ct.iso(ct.parse_iso("2026-03-01T00:00:59Z")) == "2026-03-01T00:00:59Z"
assert ct.parse_iso("") is None and ct.parse_iso("yesterday") is None
assert ct.duration(14 * 60) == "14 min" and ct.duration(65 * 60) == "1 h 05 min"
assert ct.until(NOW + 4 * 60 + 5, NOW) == "in 4 min" and ct.until(NOW - 120, NOW) == "2 min ago"
# A fixed offset needs no zone look-up: Dhaka is UTC+6.
assert ct.hm(ct.parse_iso("2026-11-14T02:30:00Z"), 6 * 3600) == "08:30"

# Polylines: Google's documented example.
pts = motis.decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@", 5)
assert [[round(p[0], 3), round(p[1], 3)] for p in pts] == [[38.5, -120.2], [40.7, -120.95], [43.252, -126.453]], pts
assert len(motis.thin([[i, i] for i in range(100)], 10)) == 10

# Fares: a GTFS-Fares v2 answer, the cheapest default-rider product per leg.
fare = motis.fare_of({"fareTransfers": [{"rule": "A_AB_B", "effectiveFareLegProducts": [
    [[{"name": "Adult", "amount": 2.9, "currency": "EUR", "riderCategory": {"riderCategoryName": "Adult", "isDefaultFareCategory": True}},
      {"name": "Child", "amount": 1.5, "currency": "EUR", "riderCategory": {"riderCategoryName": "Child", "isDefaultFareCategory": False}}]],
    [[{"name": "Adult", "amount": 1.0, "currency": "EUR"}]]]}]})
assert fare == {"amount": 3.9, "currency": "EUR"}, fare
assert motis.fare_of({"fareTransfers": [{"effectiveFareLegProducts": [[]]}]}) is None
assert motis.money({"amount": 210, "currency": "JPY"}) == "¥210"

# Plan parameters follow the options.
params = motis.plan_params({"stop": "a"}, {"lat": 1.5, "lon": 103.25}, {"speed": "slow", "transfers": 1, "step_free": True,
                                                                         "modes": ["rail", "bus"], "transfer_minutes": 3})
assert params["fromPlace"] == "a" and params["toPlace"] == "1.500000,103.250000"
assert params["pedestrianSpeed"] == "0.9" and params["maxTransfers"] == "1" and params["pedestrianProfile"] == "WHEELCHAIR"
assert params["additionalTransferTime"] == "3" and "BUS" in params["transitModes"] and "FERRY" not in params["transitModes"]

# The real plan answer reads.
trips, earlier, later, direct = motis.plan_results(PLAN)
assert len(trips) == 3 and earlier and later
t0 = trips[0]
assert t0["start"] == NOW // 60 * 60 + 3 * 3600, (t0["start"], NOW)
assert t0["transfers"] == 0 and t0["sig"] == "jp-tokyo-rail_JR-East.ChuoRapid", t0["sig"]
ride = [l for l in t0["legs"] if motis.is_transit(l)][0]
assert ride["name"] == "JC" and ride["from"]["tz"] == "Asia/Tokyo" and len(ride["stops"]) >= 2
assert ride.get("line") and len(ride["line"]) <= motis.MOST_POINTS
summary = motis.summary(t0, "Shinjuku", "Tokyo")
assert summary.startswith("Shinjuku → Tokyo") and "JC" in summary, summary
quick = dict(t0)
quick["dur"] = 1
quick["id"] = "fast"
by_dur = motis.sort_trips(trips + [quick], "fastest")
assert by_dur[0]["id"] == "fast"

rows, _, _ = motis.stoptimes_results(STOPTIMES)
assert rows and rows[0]["name"] and rows[0]["tz"] == "Asia/Tokyo"

# LTA: stop codes from ids, and the arrivals.
assert lta.stop_code("sg-LTA_28009") == "28009" and lta.stop_code("83139") == "83139" and lta.stop_code("sg-LTA_EW24") is None
services = lta.services(json.loads(LTA_TEXT), NOW)
assert [s["no"] for s in services] == ["51", "98", "143M"], [s["no"] for s in services]
s98 = services[1]
assert s98["buses"][0]["load"] == "Seats" and s98["buses"][0]["step_free"] and s98["buses"][0]["live"]
assert s98["buses"][0]["type"] == "double deck" and len(s98["buses"]) == 2
assert lta.arrival_text(services[2]["buses"][0]) == "Arr" and services[0]["buses"] == []

# Dhaka Metro: the fare chart is symmetric and bounded, and the timetable runs.
for a in range(16):
    for b in range(16):
        assert dhaka.fare(a, b) == dhaka.fare(b, a)
        assert (dhaka.fare(a, b) == 0) == (a == b)
        assert a == b or 20 <= dhaka.fare(a, b) <= 100
assert dhaka.fare(0, 15) == 100 and dhaka.fare(0, 8) == 60 and dhaka.card_fare(0, 15) == 90
assert dhaka.ride_minutes(0, 15) == 31 and dhaka.ride_minutes(0, 8) == 17
# Wednesday 2026-11-18 at 06:00 Dhaka: the first train south leaves Uttara North at 06:30.
wed_6 = ct.parse_iso("2026-11-18T00:00:00Z")
assert dhaka.day_kind((wed_6 + dhaka.OFFSET) // 86400) == "sun_thu"
dep, arr = dhaka.next_trains(0, 15, wed_6, 1)[0]
assert ct.hm(dep, dhaka.ZONE) == "06:30" and arr - dep == 31 * 60, (ct.hm(dep, dhaka.ZONE), arr - dep)
first, last = dhaka.first_last(15, 0, wed_6)
assert ct.hm(first, dhaka.ZONE) == "07:15" and ct.hm(last, dhaka.ZONE) == "22:30"
# Friday: nothing until three in the afternoon.
fri_9 = ct.parse_iso("2026-11-20T03:00:00Z")
assert dhaka.day_kind((fri_9 + dhaka.OFFSET) // 86400) == "fri"
assert ct.hm(dhaka.next_trains(0, 15, fri_9, 1)[0][0], dhaka.ZONE) == "15:00"
# Eight minutes apart at 11:00 on a weekday, from Agargaon southwards.
assert dhaka.headway_now(8, 15, ct.parse_iso("2026-11-18T05:00:00Z")) == 8
# After the last train the next one is tomorrow's first.
late = ct.parse_iso("2026-11-18T17:00:00Z")
assert ct.hm(dhaka.next_trains(0, 15, late, 1)[0][0], dhaka.ZONE) == "06:30"

# ------------------------------------------------------------- session ----

s = plugin_test.session(mock=MOCK, settings={"time_format": "24h", "lead": 10, "results": 5,
                                             "sg_bus": True, "dhaka_metro": True})
r = check(s["load"]())
tree = r["ui"]
assert "Find trips" in text_of(tree) and "Dhaka Metro" in text_of(tree) and "SG bus" in text_of(tree)

# From: type, pause, pick. To: submit, pick. The plan follows by itself.
check(s["event"]({"type": "submit", "id": "frm_box", "value": "Shinjuku"}))
r = check(s["settle"]())
assert "jp-tokyo-rail_Shinjuku" not in text_of(r["ui"]) and "item:Shinjuku" in ids(r["ui"], "item:Shinjuku"), ids(r["ui"], "item")
check(s["event"]({"type": "click", "id": "item:Shinjuku"}))
check(s["event"]({"type": "submit", "id": "to_box", "value": "Tokyo Station"}))
check(s["settle"]())
check(s["event"]({"type": "click", "id": "item:Tokyo Station"}))
r = check(s["settle"]())
plans = [c for c in s["calls"]() if c["op"] == "http.request" and c["args"]["url"].endswith("/plan")]
assert len(plans) == 1
p = plans[0]["args"]["params"]
assert p["fromPlace"] == "jp-tokyo-rail_Shinjuku" and "," in p["toPlace"] and p["pedestrianSpeed"] == "1.2", p
shown = text_of(r["ui"])
# 00:00 UTC + 9 h is shown in Tokyo time, whatever the phone's zone.
assert ct.hm(t0["start"], 9 * 3600) in shown, shown[:2000]
assert "direct" in shown and "JC" in shown

# Sorting chips and the walking-speed option.
check(s["event"]({"type": "change", "id": "order", "value": "transfers"}))
check(s["event"]({"type": "change", "id": "speed", "value": "fast"}))
check(s["event"]({"type": "click", "id": "find"}))
r = check(s["settle"]())
plans = [c for c in s["calls"]() if c["op"] == "http.request" and c["args"]["url"].endswith("/plan")]
assert plans[-1]["args"]["params"]["pedestrianSpeed"] == "1.6"

# Open the first trip.
trip_items = [i for i in ids(r["ui"], "item:") if ":" in i]
first = [w for w in find(r["ui"], lambda w: w.get("type") == "item" and "→" in str(w.get("title")))][0]
check(s["event"]({"type": "click", "id": first["id"]}))
r = check(s["render"]())
shown = text_of(r["ui"])
assert "Rail JC" in shown or "Train JC" in shown, shown[:3000]
assert "Shinjuku → Tokyo" in shown and "Other departures" in shown
summary_widgets = find(r["ui"], lambda w: w.get("id") == "summary")
assert summary_widgets and "JC" in summary_widgets[0]["text"]
assert find(r["ui"], lambda w: w.get("type") == "canvas"), "the trip's sketch"

# Pin it: it is saved, and shows first next time.
check(s["event"]({"type": "click", "id": "pin"}))
saved = s["storage"]()
pins = json.loads(saved["__state__:state"])["pins"]
assert len(saved["__state__:state"]) < 16000, len(saved["__state__:state"])
assert pins and pins[0]["trip"]["sig"] == t0["sig"] and "line" not in pins[0]["trip"]["legs"][0], saved.keys()

# A reminder before leaving, through the dialog.
check(s["event"]({"type": "click", "id": "remind"}))
dialogs = [c for c in s["calls"]() if c["op"] == "ui.dialog"]
token = dialogs[-1]["args"]["async"]
check(s["event"]({"type": "result", "token": token, "value": "Before leaving"}))
r = check(s["render"]())
listed = [c for c in s["calls"]() if c["op"].startswith("reminders")]

# An alarm before arriving, in the keyboard's Clock.
check(s["event"]({"type": "click", "id": "alarm"}))
token = [c for c in s["calls"]() if c["op"] == "ui.dialog"][-1]["args"]["async"]
check(s["event"]({"type": "result", "token": token, "value": "Before arriving"}))
alarms = [c for c in s["calls"]() if c["op"] == "clock.alarm"]
assert alarms and abs(alarms[0]["args"]["at"] - (t0["end"] - 600)) < 1, alarms
assert alarms[0]["args"]["label"].startswith("Arriving at "), alarms[0]["args"]

# A timer before leaving.
check(s["event"]({"type": "click", "id": "timer"}))
token = [c for c in s["calls"]() if c["op"] == "ui.dialog"][-1]["args"]["async"]
check(s["event"]({"type": "result", "token": token, "value": "Before leaving"}))
timers = [c for c in s["calls"]() if c["op"] == "clock.timer"]
assert timers and abs(timers[0]["args"]["seconds"] - (t0["start"] - 600 - NOW)) < 120, timers

# Later on the same route.
check(s["event"]({"type": "click", "id": "same_later"}))
r = check(s["settle"]())
assert "Later on this route" in text_of(r["ui"]), text_of(r["ui"])[:1500]
check(s["event"]({"type": "click", "id": "last"}))
r = check(s["settle"]())
last_call = [c for c in s["calls"]() if c["op"] == "http.request"][-1]["args"]["params"]
assert last_call["arriveBy"] == "true" and last_call["numItineraries"] == "1"

# Other departures of the leg's line.
check(s["event"]({"type": "click", "id": "button:Other departures"}))
r = check(s["settle"]())
assert "JC" in text_of(r["ui"])

# Back to the panel: the pinned trip is first.
check(s["event"]({"type": "back"}))
check(s["event"]({"type": "back"}))
r = check(s["render"]())
assert ids(r["ui"], "pins"), "pinned list"

# ------------------------------------------------------------ SG bus ----

check(s["event"]({"type": "change", "id": "tabs", "value": 2}))
r = check(s["render"]())
assert "Open settings" in text_of(r["ui"])
check(s["event"]({"type": "click", "id": "sg_settings"}))
assert [c for c in s["calls"]() if c["op"] == "plugin.open_settings"]
# The user types the key on the settings page.
check(s["event"]({"type": "setting", "key": "lta_key", "value": "  my-key  "}))
check(s["event"]({"type": "submit", "id": "sg_box", "value": "Jurong East Int"}))
r = check(s["settle"]())
check(s["event"]({"type": "click", "id": "item:Jurong East Int"}))
r = check(s["settle"]())
lta_calls = [c for c in s["calls"]() if c["op"] == "http.request" and "datamall" in c["args"]["url"]]
assert lta_calls and lta_calls[-1]["args"]["params"]["BusStopCode"] == "28009"
assert lta_calls[-1]["args"]["headers"]["AccountKey"] == "my-key"
shown = text_of(r["ui"])
assert "143M" in shown and "Arr" in shown and "Not in service now" in shown, shown[:2000]
# The key from the settings page is the same secret.
check(s["event"]({"type": "setting", "key": "lta_key", "value": "other-key"}))
check(s["settle"]())
assert [c for c in s["calls"]() if c["op"] == "http.request"][-1]["args"]["headers"]["AccountKey"] == "other-key"
# A five-digit code works without a search.
check(s["event"]({"type": "submit", "id": "sg_box", "value": "83139"}))
check(s["settle"]())
assert [c for c in s["calls"]() if c["op"] == "http.request"][-1]["args"]["params"]["BusStopCode"] == "83139"

# ------------------------------------------------------------ Dhaka ----

check(s["event"]({"type": "change", "id": "tabs", "value": 3}))
check(s["event"]({"type": "change", "id": "metro_from", "value": "8"}))
check(s["event"]({"type": "change", "id": "metro_to", "value": "15"}))
r = check(s["render"]())
shown = text_of(r["ui"])
assert "৳50" in shown and "৳45 with a card" in shown and "14 min" in shown, shown[-2500:]

# Hiding tabs in settings.
s2 = plugin_test.session(mock=MOCK, settings={"sg_bus": False, "dhaka_metro": False})
r = check(s2["load"]())
assert "Dhaka Metro" not in text_of(r["ui"]) and "SG bus" not in text_of(r["ui"])

# @transit Shinjuku to Tokyo Station searches both ends.
check(s2["event"]({"type": "keyword", "id": "transit", "value": "Shinjuku to Tokyo Station"}))
check(s2["settle"]())
texts = [c["args"]["params"]["text"] for c in s2["calls"]() if c["op"] == "http.request" and "geocode" in c["args"]["url"]]
assert texts == ["Shinjuku", "Tokyo Station"], texts

print("transit planner: all tests passed")
