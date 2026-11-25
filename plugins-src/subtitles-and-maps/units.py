"""Times and distances: subtitle clocks, ISO 8601 stamps, great-circle metres."""

import math

EARTH = 6371008.8     # metres


def clock(text):
    """Seconds from "01:02:03,456", "02:03.45", "0:01:02.00" or "1:02"."""
    text = text.strip().replace(",", ".")
    parts = text.split(":")
    total = 0.0
    for p in parts:
        try:
            total = total * 60 + float(p)
        except ValueError:
            return None
    return total


def stamp(seconds):
    if seconds is None:
        return ""
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return (f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}")


def seconds_of(stamp_text):
    """Seconds since 1970 for "2026-03-04T10:00:00Z" (or with an offset), or None."""
    s = stamp_text.strip()
    if len(s) < 19 or s[4] != "-" or s[10] not in "T ":
        return None
    try:
        y, mo, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
        h, mi, sec = int(s[11:13]), int(s[14:16]), float(s[17:19])
    except ValueError:
        return None
    # Days from 1970-01-01, the civil-from-days inverse (Howard Hinnant's).
    yy = y - 1 if mo <= 2 else y
    era = yy // 400
    yoe = yy - era * 400
    doy = (153 * (mo + (-3 if mo > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    days = era * 146097 + doe - 719468
    total = days * 86400 + h * 3600 + mi * 60 + sec
    tail = s[19:]
    dot = 0
    while dot < len(tail) and (tail[dot] == "." or tail[dot].isdigit()):
        dot = dot + 1
    zone = tail[dot:]
    if len(zone) >= 6 and zone[0] in "+-":
        shift = int(zone[1:3]) * 3600 + int(zone[4:6]) * 60
        total = total - shift if zone[0] == "+" else total + shift
    return total


def metres(a, b):
    """Great-circle distance between (lat, lon) pairs."""
    r = math.pi / 180
    la1 = a[0] * r
    la2 = b[0] * r
    dla = la2 - la1
    dlo = (b[1] - a[1]) * r
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * EARTH * math.asin(min(1.0, math.sqrt(h)))
