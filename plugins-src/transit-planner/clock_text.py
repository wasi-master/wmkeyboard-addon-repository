# Times for the transit planner: ISO 8601 in, "08:12" out, in the time zone
# of the stop rather than the phone's.
#
# Timetables answer in UTC ("2026-11-14T21:00:00Z") and name each stop's zone
# ("Asia/Tokyo"). A trip planned in Dhaka for Tokyo must still read 06:00,
# so a time is shown in its stop's zone, through wm.zone_offset when the
# keyboard has it, else in the phone's own zone (older keyboards).

import time

import wm

MINUTE = 60
HOUR = 3600
DAY = 86400

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# "24h" or "12h", from the plugin's settings.
style = ["24h"]

# zone name -> True once the keyboard said it knows it, False when it does not.
_known = {}


def days_from_civil(y, m, d):
    """Days since 1970-01-01 of a date in the proleptic Gregorian calendar."""
    y = y - 1 if m <= 2 else y
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    mp = m + 9 if m <= 2 else m - 3
    doy = (153 * mp + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    """(year, month, day) of a day count since 1970-01-01."""
    z = z + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return (y + 1 if m <= 2 else y, m, d)


def parse_iso(text):
    """Seconds since 1970 of "2026-11-14T21:00:00Z" or "...+08:00", or None."""
    if not text or len(text) < 19:
        return None
    try:
        y = int(text[0:4])
        mo = int(text[5:7])
        d = int(text[8:10])
        h = int(text[11:13])
        mi = int(text[14:16])
        s = int(text[17:19])
    except ValueError:
        return None
    t = days_from_civil(y, mo, d) * DAY + h * HOUR + mi * MINUTE + s
    rest = text[19:]
    if "." in rest[:1]:
        i = 1
        while i < len(rest) and rest[i].isdigit():
            i += 1
        rest = rest[i:]
    if rest[:1] in ("+", "-") and len(rest) >= 6:
        sign = 1 if rest[0] == "+" else -1
        t -= sign * (int(rest[1:3]) * HOUR + int(rest[4:6]) * MINUTE)
    return t


def iso(t):
    """"2026-11-14T21:00:00Z" for seconds since 1970."""
    t = int(t)
    y, m, d = civil_from_days(t // DAY)
    r = t % DAY
    return f"{y:04d}-{m:02d}-{d:02d}T{r // HOUR:02d}:{r % HOUR // MINUTE:02d}:{r % MINUTE:02d}Z"


def phone_offset(t):
    """The phone's own UTC offset at t, in seconds."""
    p = time.parts(int(t))
    wall = days_from_civil(p["year"], p["month"], p["day"]) * DAY + p["hour"] * HOUR + p["minute"] * MINUTE + p["second"]
    return wall - int(t)


def offset(t, zone=None):
    """UTC offset in seconds at t in [zone], or the phone's when the zone is
    unknown or the keyboard cannot look zones up."""
    if isinstance(zone, int):
        return zone
    if zone and _known.get(zone) is not False:
        fn = getattr(wm, "zone_offset", None)
        if fn is not None:
            try:
                off = fn(zone, t)
                _known[zone] = True
                return off
            except (ValueError, NotImplementedError, PermissionError):
                _known[zone] = False
    return phone_offset(t)


def wall(t, zone=None):
    """Seconds since 1970 of the wall-clock reading at t, as if it were UTC."""
    return int(t) + offset(t, zone)


def hm(t, zone=None):
    """"08:12" (or "8:12 am" with the 12-hour setting) at t in [zone]."""
    if t is None:
        return "--:--"
    w = wall(t, zone) % DAY
    h = w // HOUR
    m = w % HOUR // MINUTE
    if style[0] == "12h":
        suffix = "am" if h < 12 else "pm"
        h12 = h % 12
        return f"{12 if h12 == 0 else h12}:{m:02d} {suffix}"
    return f"{h:02d}:{m:02d}"


def day_label(t, zone=None):
    """"Sat 15 Nov" at t in [zone]."""
    w = wall(t, zone)
    days = w // DAY
    y, m, d = civil_from_days(days)
    # 1970-01-01 was a Thursday.
    return f"{WEEKDAYS[(days + 3) % 7]} {d} {MONTHS[m - 1]}"


def same_day(a, b, zone=None):
    return wall(a, zone) // DAY == wall(b, zone) // DAY


def when(t, now, zone=None):
    """The time, with the day in front when it is not today's."""
    if same_day(t, now, zone):
        return hm(t, zone)
    return day_label(t, zone) + " " + hm(t, zone)


def day_start(t, zone=None, hour=0):
    """Seconds since 1970 of [hour]:00 on t's day in [zone]."""
    w = wall(t, zone)
    local = w - w % DAY + hour * HOUR
    return local - offset(local - offset(t, zone), zone)


def duration(seconds):
    """"1 h 05 min", "14 min", "under a minute"."""
    m = int(round(seconds / 60.0))
    if m < 1:
        return "under a minute"
    if m < 60:
        return f"{m} min"
    return f"{m // 60} h {m % 60:02d} min"


def until(t, now):
    """"in 4 min", "now", "5 min ago"."""
    m = int((t - now) // 60)
    if m == 0:
        return "now"
    if m > 0:
        return "in " + duration(m * 60)
    return duration(-m * 60) + " ago"
