# Tests for Subtitles and Maps, run by tools/test_plugins.py under wm-python-cli.

import json

import units as m


def shown(preview, name):
    r = plugin_test.preview(preview, "tests/" + name)
    assert r["ok"], name + ": " + json.dumps(r.get("error"))
    return r["ui"]["root"]


def words(tree):
    """Every string in the widget tree, in order, one per line."""
    out = []
    stack = [tree]
    while stack:
        n = stack.pop()
        if isinstance(n, str):
            out.append(n)
        elif isinstance(n, list):
            stack.extend(reversed(n))
        elif isinstance(n, dict):
            stack.extend(reversed([v for k, v in n.items() if k != "type"]))
    return "\n".join(out)


def find(tree, kind):
    found = []
    stack = [tree]
    while stack:
        n = stack.pop()
        if isinstance(n, list):
            stack.extend(reversed(n))
        elif isinstance(n, dict):
            if n.get("type") == kind:
                found.append(n)
            stack.extend(reversed(list(n.values())))
    return found


def has(text, *needles):
    for needle in needles:
        assert needle in text, "missing " + json.dumps(needle) + " in:\n" + text


# MARK: - helpers

assert m.clock("01:02:03,500") == 3723.5
assert m.clock("02:03.25") == 123.25
assert m.stamp(3723.5) == "1:02:03" and m.stamp(62) == "1:02"
assert m.seconds_of("1970-01-02T00:00:00Z") == 86400
assert m.seconds_of("2026-03-04T12:00:00+06:00") == m.seconds_of("2026-03-04T06:00:00Z")
d = m.metres((0.0, 0.0), (0.0, 1.0))
assert 111000 < d < 111400, d

# MARK: - subtitles

root = shown("subtitles", "film.srt")
has(words(root), "2 lines · 1:05 long · 5 words")
assert find(root, "table")[0]["rows"] == [["0:01", "Hello there"], ["1:02", "Second line\nwraps"]]

root = shown("subtitles", "talk.vtt")
assert find(root, "table")[0]["rows"] == [["0:00", "Welcome all"], ["1:00:00", "Late"]], find(root, "table")[0]["rows"]

root = shown("subtitles", "anime.ass")
has(words(root), "Episode 1")
assert find(root, "table")[0]["rows"] == [["0:01", "First"], ["0:05", "Later, then\nnext"]]

root = shown("subtitles", "song.lrc")
has(words(root), "Rain · Mina")
assert find(root, "table")[0]["rows"] == [["0:05", "Intro"], ["0:12", "Rain falls"], ["1:30", "Rain falls"]]

root = shown("subtitles", "clip.sbv")
assert find(root, "table")[0]["rows"] == [["0:01", "Hi"], ["0:03", "Bye"]]

# MARK: - tracks

root = shown("track", "walk.gpx")
text = words(root)
has(text, "Morning walk", "Round the lake", "Distance", "2.13 km", "Time", "20 min 00 s", "Climb", "15 m", "Descent", "10 m",
    "Highest", "25 m", "3 points · 1 places", "Tea stall", "23.80500, 90.40500")
assert find(root, "canvas"), "the route is drawn"
assert find(root, "chart")[0]["series"][0]["values"] == [10.0, 25.0, 15.0]

root = shown("track", "places.kml")
has(words(root), "Trip", "1.02 km", "Hotel", "2 points · 1 places")

root = shown("track", "parks.geojson")
has(words(root), "1 Polygon, 1 Point", "Gate", "2 features")
t = find(root, "table")
assert t[-1]["header"] == ["name", "area", "open"] and t[-1]["rows"][0] == ["Big park", "12.5", ""], t[-1]

root = shown("track", "ride.tcx")
has(words(root), "Biking", "11.12 km", "30 min 00 s", "22.2 km/h")
