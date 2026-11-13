# Transitous (https://transitous.org), the community-run MOTIS 2 timetable
# service: request parameters in, small dicts out.
#
# Replies are cut down as they arrive so a pinned trip fits in storage and a
# draw stays cheap: no step-by-step walking directions, at most a few dozen
# points of each leg's line, and intermediate stops as name and time only.

import clock_text

BASE = "https://api.transitous.org/api/"
SOURCES = "https://transitous.org/sources/"

# Walking speeds in metres a second, as MOTIS takes them.
SPEEDS = {"slow": 0.9, "normal": 1.2, "fast": 1.6}

# What the mode chips ask MOTIS for.
MODE_GROUPS = {
    "rail": "HIGHSPEED_RAIL,LONG_DISTANCE,NIGHT_RAIL,REGIONAL_FAST_RAIL,REGIONAL_RAIL,RAIL,SUBURBAN",
    "metro": "SUBWAY,TRAM,FUNICULAR,AERIAL_LIFT",
    "bus": "BUS,COACH",
    "ferry": "FERRY",
}

ICONS = {
    "WALK": "directions_walk",
    "BIKE": "directions_bike",
    "CAR": "directions_car",
    "BUS": "directions_bus",
    "COACH": "directions_bus",
    "TRAM": "tram",
    "SUBWAY": "subway",
    "FERRY": "directions_boat",
    "AIRPLANE": "flight",
    "FUNICULAR": "funicular",
    "AERIAL_LIFT": "airline_seat_recline_normal",
}

MODE_WORDS = {
    "WALK": "Walk",
    "BIKE": "Cycle",
    "CAR": "Drive",
    "BUS": "Bus",
    "COACH": "Coach",
    "TRAM": "Tram",
    "SUBWAY": "Metro",
    "FERRY": "Ferry",
    "AIRPLANE": "Flight",
    "FUNICULAR": "Funicular",
    "AERIAL_LIFT": "Cable car",
}

STREET_MODES = ("WALK", "BIKE", "CAR", "RENTAL", "CAR_PARKING", "CAR_DROPOFF", "FLEX", "ODM", "RIDE_SHARING")

MOST_POINTS = 40
MOST_STOPS = 60


def icon(mode):
    return ICONS.get(mode, "train")


def mode_word(mode):
    if mode in MODE_WORDS:
        return MODE_WORDS[mode]
    return "Train"


def is_transit(leg):
    return leg.get("mode") not in STREET_MODES


# ---------------------------------------------------------------- places ----

def place_arg(p):
    """What fromPlace / toPlace / stopId take for a picked place."""
    if p.get("stop"):
        return p["stop"]
    return f"{p['lat']:.6f},{p['lon']:.6f}"


def area_of(r):
    """The most useful line under a place's name: its district and city."""
    names = []
    for a in r.get("areas") or []:
        name = a.get("name")
        if name and name != r.get("name") and (a.get("default") or a.get("unique")) and name not in names:
            names.append(name)
    if not names:
        for a in r.get("areas") or []:
            if a.get("adminLevel", 99) <= 8 and a.get("name") and a.get("name") not in names:
                names.append(a["name"])
    return ", ".join(names[:2])


def compact_place(r):
    kind = r.get("type", "PLACE")
    return {
        "name": r.get("name") or "?",
        "stop": r.get("id") if kind == "STOP" else None,
        "kind": kind,
        "lat": r.get("lat"),
        "lon": r.get("lon"),
        "tz": r.get("tz"),
        "area": area_of(r),
        "country": r.get("country"),
        "modes": r.get("modes") or [],
    }


def geocode_params(text, near=None, stops_only=False, language=None):
    params = {"text": text, "numResults": "8"}
    if stops_only:
        params["type"] = "STOP"
    if near:
        params["place"] = f"{near['lat']:.4f},{near['lon']:.4f}"
        params["placeBias"] = "1"
    if language:
        params["language"] = language
    return params


def geocode_results(data):
    out = []
    for r in data or []:
        if r.get("lat") is None or r.get("lon") is None:
            continue
        out.append(compact_place(r))
    return out


# ------------------------------------------------------------------ plan ----

def plan_params(frm, to, opts, when=None, arrive=False, count=5, cursor=None, geometry=True):
    """Query parameters for /plan. [opts] holds the panel's options:
    speed, transfers (-1 for any), step_free, modes (chip names) and
    transfer_minutes."""
    p = {
        "fromPlace": place_arg(frm),
        "toPlace": place_arg(to),
        "numItineraries": str(count),
        "pedestrianSpeed": str(SPEEDS.get(opts.get("speed", "normal"), 1.2)),
        "detailedTransfers": "false",
        "detailedLegs": "true" if geometry else "false",
        "withFares": "true",
        "joinInterlinedLegs": "true",
    }
    if cursor:
        p["pageCursor"] = cursor
    if when is not None:
        p["time"] = clock_text.iso(when)
    if arrive:
        p["arriveBy"] = "true"
    transfers = opts.get("transfers", -1)
    if transfers is not None and transfers >= 0:
        p["maxTransfers"] = str(transfers)
    if opts.get("step_free"):
        p["pedestrianProfile"] = "WHEELCHAIR"
    minutes = opts.get("transfer_minutes", 0)
    if minutes:
        p["additionalTransferTime"] = str(int(minutes))
    modes = opts.get("modes") or []
    if modes and len(modes) < len(MODE_GROUPS):
        p["transitModes"] = ",".join([MODE_GROUPS[m] for m in modes if m in MODE_GROUPS])
    return p


def decode_polyline(points, precision=6):
    """Google's encoded polyline as [[lat, lon], ...]."""
    out = []
    if not points:
        return out
    factor = 10 ** precision
    i = 0
    lat = 0
    lon = 0
    n = len(points)
    while i < n:
        values = []
        while len(values) < 2 and i < n:
            # Five bits a character, lowest first; this Python has no shifts,
            # so they are multiplied into place.
            place = 1
            result = 0
            while i < n:
                b = ord(points[i]) - 63
                i += 1
                result += (b & 31) * place
                place *= 32
                if b < 32:
                    break
            values.append(-(result // 2) - 1 if result & 1 else result // 2)
        if len(values) < 2:
            break
        lat += values[0]
        lon += values[1]
        out.append([lat / factor, lon / factor])
    return out


def thin(points, most=MOST_POINTS):
    """At most [most] points, keeping both ends."""
    if len(points) <= most:
        return points
    step = (len(points) - 1) / (most - 1)
    out = []
    k = 0
    while k < most - 1:
        out.append(points[int(round(k * step))])
        k += 1
    out.append(points[-1])
    return out


def compact_stop(s, side):
    """A leg end: name, times (planned and expected), platform, zone."""
    t = clock_text.parse_iso(s.get(side) or "")
    planned = clock_text.parse_iso(s.get("scheduled" + side[0].upper() + side[1:]) or "")
    return {
        "name": s.get("name") or "?",
        "stop": s.get("stopId"),
        "parent": s.get("parentId"),
        "code": s.get("stopCode"),
        "t": t,
        "planned": planned if planned is not None else t,
        "track": s.get("track"),
        "planned_track": s.get("scheduledTrack"),
        "tz": s.get("tz"),
        "lat": s.get("lat"),
        "lon": s.get("lon"),
        "cancelled": bool(s.get("cancelled")),
    }


def compact_leg(l):
    mode = l.get("mode", "WALK")
    leg = {
        "mode": mode,
        "from": compact_stop(l.get("from") or {}, "departure"),
        "to": compact_stop(l.get("to") or {}, "arrival"),
        "dur": l.get("duration", 0),
        "dist": l.get("distance"),
    }
    # A leg's start and end times are the ones to trust: a walk's ends do not
    # always carry departure / arrival.
    start = clock_text.parse_iso(l.get("startTime") or "")
    end = clock_text.parse_iso(l.get("endTime") or "")
    if start is not None:
        leg["from"]["t"] = start
        planned = clock_text.parse_iso(l.get("scheduledStartTime") or "")
        leg["from"]["planned"] = planned if planned is not None else start
    if end is not None:
        leg["to"]["t"] = end
        planned = clock_text.parse_iso(l.get("scheduledEndTime") or "")
        leg["to"]["planned"] = planned if planned is not None else end
    if mode not in STREET_MODES:
        leg.update({
            "name": l.get("displayName") or l.get("routeShortName") or l.get("tripShortName") or mode_word(mode),
            "long": l.get("routeLongName") or "",
            "trip_no": l.get("tripShortName") or "",
            "headsign": l.get("headsign") or (l.get("tripTo") or {}).get("name") or "",
            "agency": l.get("agencyName") or "",
            "route": l.get("routeId"),
            "dir": l.get("directionId"),
            "trip": l.get("tripId"),
            "rt": bool(l.get("realTime")),
            "cancelled": bool(l.get("cancelled")),
            "step_free": l.get("wheelchairAccessible") == "ACCESSIBLE",
            "fare_transfer": l.get("fareTransferIndex"),
            "fare_leg": l.get("effectiveFareLegIndex"),
        })
        stops = []
        for s in (l.get("intermediateStops") or [])[:MOST_STOPS]:
            stops.append([s.get("name") or "?", clock_text.parse_iso(s.get("arrival") or s.get("departure") or "")])
        leg["stops"] = stops
    geo = l.get("legGeometry") or {}
    if geo.get("points"):
        leg["line"] = thin(decode_polyline(geo["points"], geo.get("precision", 6)))
    return leg


def _products(value, out):
    """Every FareProduct in a nested list (MOTIS nests them two or three deep)."""
    if isinstance(value, dict):
        if "amount" in value:
            out.append(value)
        return out
    if isinstance(value, list):
        for v in value:
            _products(v, out)
    return out


def _cheapest(options):
    """The cheapest product for the default rider, else the cheapest at all."""
    best = None
    for p in options:
        rider = p.get("riderCategory") or {}
        if rider and not rider.get("isDefaultFareCategory", True):
            continue
        if best is None or p["amount"] < best["amount"]:
            best = p
    if best is None:
        for p in options:
            if best is None or p["amount"] < best["amount"]:
                best = p
    return best


def fare_of(it):
    """{"amount", "currency"} for a whole itinerary, or None when the
    timetable does not say what every part of it costs."""
    transfers = it.get("fareTransfers")
    if not transfers:
        return None
    total = 0.0
    currency = None
    for ft in transfers:
        rule = ft.get("rule")
        parts = []
        transfer = _cheapest(_products(ft.get("transferProducts") or [], []))
        if transfer is not None:
            parts.append(transfer)
        if rule != "AB":
            legs = ft.get("effectiveFareLegProducts") or []
            if rule == "A_AB":
                legs = legs[:1]
            for options in legs:
                p = _cheapest(_products(options, []))
                if p is None:
                    return None
                parts.append(p)
        if not parts:
            return None
        for p in parts:
            if currency is None:
                currency = p.get("currency")
            elif p.get("currency") != currency:
                return None
            total += p["amount"]
    return {"amount": total, "currency": currency}


def compact_itinerary(it):
    legs = [compact_leg(l) for l in it.get("legs") or []]
    start = clock_text.parse_iso(it.get("startTime") or "")
    end = clock_text.parse_iso(it.get("endTime") or "")
    out = {
        "id": it.get("id") or "",
        "start": start,
        "end": end,
        "dur": it.get("duration", (end or 0) - (start or 0)),
        "transfers": it.get("transfers", 0),
        "legs": legs,
        "fare": fare_of(it),
    }
    out["sig"] = signature(out)
    return out


def signature(it):
    """The routes an itinerary rides, in order: two trips with the same
    signature take the same path at different times."""
    return "|".join([str(l.get("route") or l.get("name")) for l in it["legs"] if is_transit(l)])


def name_ends(trips, frm_name, to_name):
    """MOTIS calls a trip's two ends START and END when they are map points;
    give them the names the user picked."""
    for it in trips:
        legs = it["legs"]
        if legs and frm_name and legs[0]["from"]["name"] in ("START", "?"):
            legs[0]["from"]["name"] = frm_name
        if legs and to_name and legs[-1]["to"]["name"] in ("END", "?"):
            legs[-1]["to"]["name"] = to_name
    return trips


def plan_results(data):
    """(itineraries, earlier cursor, later cursor, direct street trips)."""
    data = data or {}
    its = [compact_itinerary(i) for i in data.get("itineraries") or []]
    direct = [compact_itinerary(i) for i in data.get("direct") or []]
    return its, data.get("previousPageCursor"), data.get("nextPageCursor"), direct


def walk_minutes(it):
    return sum([l["dur"] for l in it["legs"] if not is_transit(l)]) // 60


def sort_trips(its, order):
    """Sort a copy of [its]: "best" keeps the timetable's order (earliest
    arrival first), "fastest", "transfers", "cheapest", "walk"."""
    out = list(its)
    if order == "fastest":
        out.sort(key=lambda i: (i["dur"], i["transfers"], i["start"] or 0))
    elif order == "transfers":
        out.sort(key=lambda i: (i["transfers"], i["dur"], i["start"] or 0))
    elif order == "cheapest":
        out.sort(key=lambda i: ((i["fare"] or {}).get("amount", 1e12), i["dur"]))
    elif order == "walk":
        out.sort(key=lambda i: (walk_minutes(i), i["dur"]))
    return out


def trip_title(it, now):
    zone = first_zone(it)
    return f"{clock_text.hm(it['start'], zone)} → {clock_text.hm(it['end'], last_zone(it))}"


def first_zone(it):
    for l in it["legs"]:
        if l["from"].get("tz"):
            return l["from"]["tz"]
    return None


def last_zone(it):
    i = len(it["legs"]) - 1
    while i >= 0:
        if it["legs"][i]["to"].get("tz"):
            return it["legs"][i]["to"]["tz"]
        i -= 1
    return first_zone(it)


def money(fare):
    if not fare:
        return ""
    amount = fare["amount"]
    whole = amount == int(amount)
    shown = str(int(amount)) if whole else f"{amount:.2f}"
    symbols = {"EUR": "€", "USD": "$", "GBP": "£", "JPY": "¥", "SGD": "S$", "BDT": "৳", "INR": "₹", "CHF": "CHF "}
    symbol = symbols.get(fare.get("currency"))
    if symbol:
        return symbol + shown
    return shown + " " + str(fare.get("currency") or "")


def leg_chain(it):
    """"JC › G › walk" for a results row."""
    parts = []
    for l in it["legs"]:
        if is_transit(l):
            parts.append(l["name"])
    if not parts:
        return mode_word(it["legs"][0]["mode"]) if it["legs"] else ""
    return " › ".join(parts)


def changes_text(n):
    if n == 0:
        return "direct"
    if n == 1:
        return "1 change"
    return f"{n} changes"


def delay_minutes(stop):
    if stop.get("t") is None or stop.get("planned") is None:
        return 0
    return int((stop["t"] - stop["planned"]) // 60)


def platform_text(stop):
    track = stop.get("track")
    if not track:
        return ""
    planned = stop.get("planned_track")
    if planned and planned != track:
        return f"platform {track} (was {planned})"
    return f"platform {track}"


# ------------------------------------------------------------- stoptimes ----

def stoptimes_params(stop, when=None, count=20, cursor=None, arrive=False):
    p = {"stopId": stop, "n": str(count)}
    if cursor:
        p["pageCursor"] = cursor
    elif when is not None:
        p["time"] = clock_text.iso(when)
    if arrive:
        p["arriveBy"] = "true"
    return p


def compact_stoptime(s):
    place = s.get("place") or {}
    t = clock_text.parse_iso(place.get("departure") or place.get("arrival") or "")
    planned = clock_text.parse_iso(place.get("scheduledDeparture") or place.get("scheduledArrival") or "")
    return {
        "t": t,
        "planned": planned if planned is not None else t,
        "mode": s.get("mode"),
        "name": s.get("displayName") or s.get("routeShortName") or mode_word(s.get("mode")),
        "headsign": s.get("headsign") or (s.get("tripTo") or {}).get("name") or "",
        "route": s.get("routeId"),
        "dir": s.get("directionId"),
        "trip": s.get("tripId"),
        "agency": s.get("agencyName") or "",
        "track": place.get("track"),
        "planned_track": place.get("scheduledTrack"),
        "stop": place.get("stopId"),
        "stop_name": place.get("name") or "",
        "tz": place.get("tz"),
        "rt": bool(s.get("realTime")),
        "cancelled": bool(s.get("cancelled") or s.get("tripCancelled")),
    }


def stoptimes_results(data):
    data = data or {}
    return ([compact_stoptime(s) for s in data.get("stopTimes") or []],
            data.get("previousPageCursor"), data.get("nextPageCursor"))


# -------------------------------------------------------------- summary ----

def summary(it, frm_name=None, to_name=None):
    """The trip as plain text, for Insert, Copy and Share."""
    zone = first_zone(it)
    legs = it["legs"]
    a = frm_name or (legs[0]["from"]["name"] if legs else "")
    b = to_name or (legs[-1]["to"]["name"] if legs else "")
    head = f"{a} → {b}"
    span = f"{clock_text.hm(it['start'], zone)}–{clock_text.hm(it['end'], last_zone(it))}"
    facts = [clock_text.duration(it["dur"]), changes_text(it["transfers"])]
    if it.get("fare"):
        facts.append(money(it["fare"]))
    lines = [head, f"{clock_text.day_label(it['start'], zone)}, {span} ({', '.join(facts)})"]
    for l in legs:
        if is_transit(l):
            where = platform_text(l["from"])
            line = f"{clock_text.hm(l['from']['t'], l['from'].get('tz'))} {l['from']['name']}"
            if where:
                line += f" ({where})"
            line += f": {mode_word(l['mode'])} {l['name']}"
            if l.get("headsign"):
                line += f" towards {l['headsign']}"
            lines.append(line)
            lines.append(f"{clock_text.hm(l['to']['t'], l['to'].get('tz'))} {l['to']['name']}")
        elif l["dur"] >= 60:
            lines.append(f"Walk {clock_text.duration(l['dur'])}")
    return "\n".join(lines)
