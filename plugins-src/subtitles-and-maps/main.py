# Subtitles and Maps: timed text (SRT, WebVTT, ASS/SSA, LRC, SBV) as a list of
# cues, and GPS files (GPX, KML, GeoJSON, TCX) as a drawn route with numbers.

import json
import math

from wm import plugin, ui
from wm.preview import xml

from units import clock, stamp, seconds_of, metres

MAX_CUES = 500
DRAWN = 300           # points kept for the drawing and the chart


# MARK: - subtitles

def _strip_tags(text):
    """<i>, <font …>, <c.yellow> and ASS {\\pos(…)} overrides out of a cue."""
    out = []
    depth_angle = False
    depth_brace = False
    for ch in text:
        if ch == "<":
            depth_angle = True
        elif ch == ">" and depth_angle:
            depth_angle = False
        elif ch == "{":
            depth_brace = True
        elif ch == "}" and depth_brace:
            depth_brace = False
        elif not depth_angle and not depth_brace:
            out.append(ch)
    return "".join(out).replace("\\N", "\n").replace("\\n", "\n").replace("\\h", " ").strip()


def srt(lines):
    """SRT, WebVTT and SBV: blocks with a "start --> end" (or "start,end") line."""
    cues = []
    i = 0
    n = len(lines)
    while i < n and len(cues) < MAX_CUES * 4:
        line = lines[i]
        arrow = line.find("-->")
        sbv = arrow < 0 and line.count(",") == 1 and line.count(":") >= 2 and clock(line.split(",")[0]) is not None
        if arrow < 0 and not sbv:
            i = i + 1
            continue
        if sbv:
            start, end = line.split(",")
        else:
            start = line[:arrow]
            end = line[arrow + 3:].strip().split(" ")[0]
        body = []
        i = i + 1
        while i < n and lines[i].strip():
            body.append(lines[i])
            i = i + 1
        cues.append((clock(start), clock(end), _strip_tags("\n".join(body))))
    return cues


def ass(lines):
    """ASS and SSA: the [Events] section's Dialogue lines, read by its Format line."""
    cues = []
    title = ""
    fields = ["layer", "start", "end", "style", "name", "marginl", "marginr", "marginv", "effect", "text"]
    section = ""
    for line in lines:
        s = line.strip()
        if s.startswith("["):
            section = s.lower()
            continue
        if section == "[script info]" and s.lower().startswith("title:"):
            title = s[6:].strip()
        if section != "[events]":
            continue
        if s.lower().startswith("format:"):
            fields = [f.strip().lower() for f in s[7:].split(",")]
            continue
        if s.lower().startswith("dialogue:"):
            values = s[9:].split(",", len(fields) - 1)
            row = {}
            for k, v in zip(fields, values):
                row[k] = v.strip()
            cues.append((clock(row.get("start", "")), clock(row.get("end", "")), _strip_tags(row.get("text", ""))))
    return title, sorted(cues, key=lambda c: c[0] or 0)


def lrc(lines):
    """Synced lyrics: [mm:ss.xx] text, a line may carry several times."""
    cues = []
    tags = {}
    for line in lines:
        rest = line.strip()
        times = []
        while rest.startswith("["):
            close = rest.find("]")
            if close < 0:
                break
            inside = rest[1:close]
            rest = rest[close + 1:]
            colon = inside.find(":")
            seconds = clock(inside) if colon > 0 and inside[:colon].strip().isdigit() else None
            if seconds is not None:
                times.append(seconds)
            elif colon > 0:
                tags[inside[:colon].strip().lower()] = inside[colon + 1:].strip()
        for at in times:
            cues.append((at, None, rest.strip()))
    return tags, sorted(cues, key=lambda c: c[0])


@plugin.preview("subtitles")
def show_subtitles(file):
    # "\r\n" is one character to the interpreter, so splitlines() keeps it whole.
    lines = file.text().replace("\r\n", "\n").replace("\r", "\n").split("\n")
    title = ""
    if file.extension in ("ass", "ssa") or (lines and lines[0].strip().lower() == "[script info]"):
        title, cues = ass(lines)
    elif file.extension == "lrc":
        tags, cues = lrc(lines)
        title = " · ".join(x for x in (tags.get("ti", ""), tags.get("ar", ""), tags.get("al", "")) if x)
    else:
        cues = srt(lines)
    cues = [c for c in cues if c[2]]
    if not cues:
        ui.empty("No timed lines were found in this file.")
        return
    if title:
        ui.label(title, style="title")
    last = max((c[1] or c[0] or 0) for c in cues)
    words = sum(len(c[2].split()) for c in cues)
    ui.caption(f"{len(cues)} lines · {stamp(last)} long · {words:,} words")
    rows = [[stamp(c[0]), c[2]] for c in cues[:MAX_CUES]]
    ui.table(rows, header=["Time", "Text"])
    if len(cues) > MAX_CUES:
        ui.caption(f"The first {MAX_CUES} lines are shown.")


# MARK: - tracks

class Track:
    """What a GPS file holds: lines of points, named places, a name."""

    def __init__(self):
        self.name = ""
        self.about = ""
        self.lines = []       # [[(lat, lon, ele or None, time or None)]]
        self.places = []      # [(name, lat, lon)]
        self.shapes = {}      # GeoJSON geometry kinds and their counts
        self.features = []    # GeoJSON features, for their properties

    def add_line(self, points):
        if len(points) >= 1:
            self.lines.append(points)


def _float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def gpx(file):
    tr = Track()
    root = file.xml()
    meta = root.find("metadata")
    named = (meta.find("name") if meta is not None else None) or root.first("name")
    if named is not None:
        tr.name = named.all_text().strip()
    desc = root.first("desc")
    if desc is not None:
        tr.about = desc.all_text().strip()
    for seg in root.iter("trkseg") + root.iter("rte"):
        points = []
        for p in seg.children:
            if p.name not in ("trkpt", "rtept"):
                continue
            lat, lon = _float(p.get("lat")), _float(p.get("lon"))
            if lat is None or lon is None:
                continue
            ele = p.find("ele")
            when = p.find("time")
            points.append((lat, lon, _float(ele.text) if ele is not None else None,
                           seconds_of(when.text) if when is not None else None))
        tr.add_line(points)
    for w in root.findall("wpt"):
        n = w.find("name")
        tr.places.append((n.all_text().strip() if n is not None else "Waypoint", _float(w.get("lat")), _float(w.get("lon"))))
    return tr


def _coords(text):
    """KML's "lon,lat[,alt] lon,lat …"."""
    out = []
    for chunk in text.split():
        bits = chunk.split(",")
        if len(bits) >= 2:
            lon, lat = _float(bits[0]), _float(bits[1])
            if lat is not None and lon is not None:
                out.append((lat, lon, _float(bits[2]) if len(bits) > 2 else None, None))
    return out


def kml(file):
    tr = Track()
    root = file.xml()
    doc = root.first("Document") or root
    n = doc.find("name") or root.first("name")
    if n is not None:
        tr.name = n.all_text().strip()
    for mark in root.iter("Placemark"):
        name_el = mark.find("name")
        name = name_el.all_text().strip() if name_el is not None else ""
        for ls in mark.iter("LineString") + mark.iter("LinearRing"):
            c = ls.find("coordinates")
            if c is not None:
                tr.add_line(_coords(c.all_text()))
        for track in mark.iter("Track"):
            pts = []
            times = [seconds_of(w.all_text()) for w in track.findall("when")]
            for i, coord in enumerate(track.findall("coord")):
                bits = coord.all_text().split()
                if len(bits) >= 2:
                    pts.append((_float(bits[1]), _float(bits[0]), _float(bits[2]) if len(bits) > 2 else None,
                                times[i] if i < len(times) else None))
            tr.add_line(pts)
        for pt in mark.iter("Point"):
            c = pt.find("coordinates")
            got = _coords(c.all_text()) if c is not None else []
            if got:
                tr.places.append((name or "Place", got[0][0], got[0][1]))
    return tr


def _geo_points(coords):
    return [(c[1], c[0], c[2] if len(c) > 2 else None, None) for c in coords if isinstance(c, list) and len(c) >= 2]


def _geometry(tr, g, name):
    if not isinstance(g, dict):
        return
    kind = g.get("type", "")
    tr.shapes[kind] = tr.shapes.get(kind, 0) + 1
    c = g.get("coordinates")
    if kind == "Point" and isinstance(c, list) and len(c) >= 2:
        tr.places.append((name or "Point", c[1], c[0]))
    elif kind == "MultiPoint":
        for p in c or []:
            tr.places.append((name or "Point", p[1], p[0]))
    elif kind == "LineString":
        tr.add_line(_geo_points(c or []))
    elif kind in ("MultiLineString", "Polygon"):
        for line in c or []:
            tr.add_line(_geo_points(line))
    elif kind == "MultiPolygon":
        for poly in c or []:
            for line in poly:
                tr.add_line(_geo_points(line))
    elif kind == "GeometryCollection":
        for sub in g.get("geometries", []):
            _geometry(tr, sub, name)


def geojson(file):
    tr = Track()
    data = file.json()
    tr.name = str(data.get("name", "")) if isinstance(data, dict) else ""
    features = []
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        features = data.get("features", [])
    elif isinstance(data, dict) and data.get("type") == "Feature":
        features = [data]
    elif isinstance(data, dict):
        _geometry(tr, data, "")
    for f in features[:5000]:
        props = f.get("properties") or {}
        label = ""
        for key in ("name", "title", "Name", "NAME", "label", "id"):
            if key in props and props[key] is not None:
                label = str(props[key])
                break
        _geometry(tr, f.get("geometry"), label)
    tr.features = features
    return tr


def tcx(file):
    tr = Track()
    root = file.xml()
    act = root.first("Activity")
    if act is not None:
        tr.name = act.get("Sport", "")
    for track in root.iter("Track"):
        pts = []
        for p in track.findall("Trackpoint"):
            pos = p.find("Position")
            if pos is None:
                continue
            lat, lon = pos.find("LatitudeDegrees"), pos.find("LongitudeDegrees")
            if lat is None or lon is None:
                continue
            alt = p.find("AltitudeMeters")
            when = p.find("Time")
            pts.append((_float(lat.text), _float(lon.text), _float(alt.text) if alt is not None else None,
                        seconds_of(when.text) if when is not None else None))
        tr.add_line(pts)
    return tr


def _thin(points, keep):
    if len(points) <= keep:
        return points
    step = len(points) / keep
    out = [points[int(i * step)] for i in range(keep)]
    out.append(points[-1])
    return out


def _length(m):
    return f"{m / 1000:.2f} km" if m >= 1000 else f"{int(m)} m"


def _duration(s):
    s = int(s)
    h = s // 3600
    m = (s % 3600) // 60
    return f"{h} h {m:02d} min" if h else f"{m} min {s % 60:02d} s"


def draw(tr):
    """The route and places on a canvas, north up, scaled to fit."""
    pts = [p for line in tr.lines for p in line] + [(p[1], p[2]) for p in tr.places if p[1] is not None and p[2] is not None]
    if not pts:
        return
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    mid = (min(lats) + max(lats)) / 2
    squash = math.cos(mid * math.pi / 180)
    w, h = 320, 200
    span_x = max((max(lons) - min(lons)) * squash, 1e-9)
    span_y = max(max(lats) - min(lats), 1e-9)
    scale = min((w - 20) / span_x, (h - 20) / span_y)
    ox = (w - span_x * scale) / 2
    oy = (h - span_y * scale) / 2

    def xy(lat, lon):
        return ox + (lon - min(lons)) * squash * scale, h - (oy + (lat - min(lats)) * scale)

    shapes = [ui.rect(0, 0, w, h, color="muted", radius=12, fill=False)]
    budget = 900
    for line in tr.lines:
        thin = _thin(line, max(2, budget // max(1, len(tr.lines))))
        for a, b in zip(thin, thin[1:]):
            x1, y1 = xy(a[0], a[1])
            x2, y2 = xy(b[0], b[1])
            shapes.append(ui.line(x1, y1, x2, y2, color="primary", width=2))
    for i, line in enumerate(tr.lines[:1]):
        if len(line) > 1:
            x, y = xy(line[0][0], line[0][1])
            shapes.append(ui.circle(x, y, 4, color="success"))
            x, y = xy(line[-1][0], line[-1][1])
            shapes.append(ui.circle(x, y, 4, color="danger"))
    for name, lat, lon in tr.places[:100]:
        if lat is not None and lon is not None:
            x, y = xy(lat, lon)
            shapes.append(ui.circle(x, y, 3, color="accent"))
    ui.canvas(w, h, shapes)


@plugin.preview("track")
def show_track(file):
    reader = {"gpx": gpx, "kml": kml, "geojson": geojson, "tcx": tcx}.get(file.extension)
    if reader is None:
        head = file.data[:400]
        reader = gpx if head.find(b"<gpx") >= 0 else (kml if head.find(b"<kml") >= 0 else geojson)
    try:
        tr = reader(file)
    except ValueError as error:
        ui.empty(f"This file could not be read: {error}")
        return
    if tr.name:
        ui.label(tr.name, style="title")
    if tr.about:
        ui.caption(tr.about[:400])
    if not tr.lines and not tr.places:
        ui.empty("No route or places were found in this file.")
        return
    draw(tr)
    distance = 0.0
    climb = 0.0
    fall = 0.0
    heights = []
    times = []
    for line in tr.lines:
        for a, b in zip(line, line[1:]):
            distance = distance + metres(a, b)
            if a[2] is not None and b[2] is not None:
                if b[2] > a[2]:
                    climb = climb + b[2] - a[2]
                else:
                    fall = fall + a[2] - b[2]
        heights.extend([p[2] for p in line if p[2] is not None])
        times.extend([p[3] for p in line if p[3] is not None])
    stats = []
    points = sum(len(line) for line in tr.lines)
    if points > 1:
        stats.append(("Distance", _length(distance)))
    if len(times) > 1 and max(times) > min(times):
        span = max(times) - min(times)
        stats.append(("Time", _duration(span)))
        if distance > 0:
            stats.append(("Average", f"{distance / span * 3.6:.1f} km/h"))
    if heights:
        stats.append(("Climb", f"{int(climb)} m"))
        stats.append(("Descent", f"{int(fall)} m"))
        stats.append(("Highest", f"{int(max(heights))} m"))
        stats.append(("Lowest", f"{int(min(heights))} m"))
    if stats:
        ui.table([[k, v] for k, v in stats])
    kinds = ", ".join(f"{n} {k}" for k, n in tr.shapes.items())
    ui.caption(f"{points:,} points" + (f" · {len(tr.places)} places" if tr.places else "") + (f" · {kinds}" if kinds else ""))
    if len(heights) > 2:
        with ui.section("Elevation", collapsible=True):
            ui.chart([int(h) for h in _thin(heights, 120)], kind="line", height=120)
    if tr.places:
        with ui.section("Places", collapsible=True, open=not tr.lines):
            ui.table([[n, f"{lat:.5f}, {lon:.5f}" if lat is not None and lon is not None else ""] for n, lat, lon in tr.places[:300]],
                     header=["Name", "Where"])
    features = tr.features
    if features:
        keys = []
        for f in features[:50]:
            for k in (f.get("properties") or {}).keys():
                if k not in keys and len(keys) < 12:
                    keys.append(k)
        if keys:
            with ui.section(f"{len(features):,} features", collapsible=True, open=False):
                rows = []
                for f in features[:200]:
                    props = f.get("properties") or {}
                    rows.append([_cell(props.get(k)) for k in keys])
                ui.table(rows, header=keys)


def _cell(v):
    if v is None:
        return ""
    text = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return text if len(text) <= 120 else text[:119] + "…"
