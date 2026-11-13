# Dhaka Metro Line 6 (MRT-6), from its published timetable: no network.
#
# Sources:
# - Timetable: DMTCL, https://dmtcl.gov.bd/pages/static-pages/6922df5f933eb65569e218ed
#   (last updated 1 September 2026). Holiday timetables are not covered.
# - Fares: DTCA fare chart of 8 September 2022 (memo 35.02.0000.016.47.001.19-371),
#   linked from https://dmtcl.gov.bd/pages/static-pages/6922df5a933eb65569e2169f.
#   MRT Pass and Rapid Pass pay 10% less.
# - Ride times: 17 minutes Uttara North to Agargaon and 14 minutes Agargaon to
#   Motijheel (The Business Standard, November 2023), shared out between the
#   stations by distance. Times at stations between the ends are estimates.
# - Station positions: OpenStreetMap.

import clock_text

# Bangladesh keeps UTC+6 all year, so the timetable needs no zone database:
# times are shown at this fixed offset wherever the phone is.
OFFSET = 6 * 3600
ZONE = OFFSET

NOTE = ("Times from DMTCL's timetable (1 September 2026); times between the ends of the line are estimates. "
        "Holidays run to their own timetable. Fares from DTCA; MRT Pass and Rapid Pass pay 10% less.")

STATIONS = [
    {"name": "Uttara North", "bn": "উত্তরা উত্তর", "lat": 23.8691, "lon": 90.3675},
    {"name": "Uttara Center", "bn": "উত্তরা সেন্টার", "lat": 23.8597, "lon": 90.3652},
    {"name": "Uttara South", "bn": "উত্তরা দক্ষিণ", "lat": 23.8459, "lon": 90.3632},
    {"name": "Pallabi", "bn": "পল্লবী", "lat": 23.8262, "lon": 90.3642},
    {"name": "Mirpur 11", "bn": "মিরপুর ১১", "lat": 23.8191, "lon": 90.3653},
    {"name": "Mirpur 10", "bn": "মিরপুর ১০", "lat": 23.8084, "lon": 90.3683},
    {"name": "Kazipara", "bn": "কাজীপাড়া", "lat": 23.7992, "lon": 90.3720},
    {"name": "Shewrapara", "bn": "শেওড়াপাড়া", "lat": 23.7910, "lon": 90.3755},
    {"name": "Agargaon", "bn": "আগারগাঁও", "lat": 23.7784, "lon": 90.3801},
    {"name": "Bijoy Sarani", "bn": "বিজয় সরণি", "lat": 23.7664, "lon": 90.3831},
    {"name": "Farmgate", "bn": "ফার্মগেট", "lat": 23.7590, "lon": 90.3871},
    {"name": "Karwan Bazar", "bn": "কারওয়ান বাজার", "lat": 23.7513, "lon": 90.3928},
    {"name": "Shahbag", "bn": "শাহবাগ", "lat": 23.7395, "lon": 90.3960},
    {"name": "Dhaka University", "bn": "ঢাকা বিশ্ববিদ্যালয়", "lat": 23.7317, "lon": 90.3968},
    {"name": "Bangladesh Secretariat", "bn": "বাংলাদেশ সচিবালয়", "lat": 23.7300, "lon": 90.4075},
    {"name": "Motijheel", "bn": "মতিঝিল", "lat": 23.7281, "lon": 90.4191},
]

NORTH_END = 0
SOUTH_END = len(STATIONS) - 1
AGARGAON = 8

# Single-journey fares in taka, rows and columns in station order.
FARES = [
    [0, 20, 20, 30, 30, 40, 40, 50, 60, 60, 70, 80, 80, 90, 90, 100],
    [20, 0, 20, 20, 30, 30, 40, 40, 50, 60, 60, 70, 80, 80, 90, 90],
    [20, 20, 0, 20, 20, 30, 30, 40, 40, 50, 60, 60, 70, 70, 80, 90],
    [30, 20, 20, 0, 20, 20, 20, 30, 30, 40, 50, 50, 60, 60, 70, 80],
    [30, 30, 20, 20, 0, 20, 20, 20, 30, 40, 40, 50, 50, 60, 70, 70],
    [40, 30, 30, 20, 20, 0, 20, 20, 20, 30, 30, 40, 50, 50, 60, 60],
    [40, 40, 30, 20, 20, 20, 0, 20, 20, 20, 30, 40, 40, 50, 50, 60],
    [50, 40, 40, 30, 20, 20, 20, 0, 20, 20, 20, 30, 40, 40, 50, 50],
    [60, 50, 40, 30, 30, 20, 20, 20, 0, 20, 20, 20, 30, 30, 40, 50],
    [60, 60, 50, 40, 40, 30, 20, 20, 20, 0, 20, 20, 20, 30, 40, 40],
    [70, 60, 60, 50, 40, 30, 30, 20, 20, 20, 0, 20, 20, 20, 30, 30],
    [80, 70, 60, 50, 50, 40, 40, 30, 20, 20, 20, 0, 20, 20, 20, 30],
    [80, 80, 70, 60, 50, 50, 40, 40, 30, 20, 20, 20, 0, 20, 20, 20],
    [90, 80, 70, 60, 60, 50, 50, 40, 30, 30, 20, 20, 20, 0, 20, 20],
    [90, 90, 80, 70, 70, 60, 50, 50, 40, 40, 30, 20, 20, 20, 0, 20],
    [100, 90, 90, 80, 70, 60, 60, 50, 50, 40, 30, 30, 20, 20, 20, 0],
]

# Straight-line kilometres between neighbouring stations (OpenStreetMap),
# only to share the two published ride times out between the stations.
GAPS_KM = [1.07, 1.55, 2.20, 0.79, 1.23, 1.08, 0.99, 1.47, 1.37, 0.91, 1.04, 1.35, 0.87, 1.10, 1.20]
NORTH_HALF_MIN = 17
SOUTH_HALF_MIN = 14

# The timetable: (first, last, every N minutes) bands of departures from
# the end of the line. "south" leaves Uttara North, "north" leaves Motijheel.
TIMETABLE = {
    "sun_thu": {
        "south": [("06:30", "07:10", 20), ("07:11", "07:30", 10), ("07:31", "08:10", 8), ("08:11", "10:00", 5),
                  ("10:01", "15:20", 8), ("15:21", "16:44", 6), ("16:44", "20:04", 5), ("20:05", "21:00", 10),
                  ("21:01", "21:30", 15), ("21:31", "21:50", 20)],
        "north": [("07:15", "07:55", 10), ("07:56", "08:45", 8), ("08:46", "10:35", 5), ("10:36", "15:55", 8),
                  ("15:56", "17:19", 6), ("17:20", "20:39", 8), ("20:39", "21:40", 10), ("21:41", "22:10", 15),
                  ("22:11", "22:30", 20)],
    },
    "sat": {
        "south": [("06:30", "07:25", 20), ("07:26", "07:49", 12), ("07:50", "08:39", 10), ("08:40", "10:39", 8),
                  ("10:40", "15:29", 10), ("15:30", "16:25", 8), ("16:26", "18:55", 6), ("18:56", "19:51", 8),
                  ("19:52", "21:30", 15), ("21:31", "21:50", 20)],
        "north": [("07:15", "08:24", 12), ("08:25", "09:14", 10), ("09:15", "11:14", 8), ("11:15", "16:04", 10),
                  ("16:05", "17:00", 8), ("17:01", "19:30", 6), ("19:31", "20:26", 8), ("20:27", "21:40", 10),
                  ("21:41", "22:10", 15), ("22:11", "22:30", 20)],
    },
    "fri": {
        "south": [("15:00", "16:36", 8), ("16:37", "18:42", 6), ("18:43", "20:18", 8), ("20:19", "21:00", 10),
                  ("21:01", "21:30", 15), ("21:31", "21:50", 20)],
        "north": [("15:20", "17:11", 8), ("17:12", "19:17", 6), ("19:18", "20:53", 8), ("20:54", "21:40", 10),
                  ("21:41", "22:10", 15), ("22:11", "22:30", 20)],
    },
}


def _minutes(hhmm):
    return int(hhmm[:2]) * 60 + int(hhmm[3:5])


def _offsets():
    """Minutes from Uttara North to each station."""
    north = sum(GAPS_KM[:AGARGAON])
    south = sum(GAPS_KM[AGARGAON:])
    out = [0.0]
    for i, km in enumerate(GAPS_KM):
        share = NORTH_HALF_MIN * km / north if i < AGARGAON else SOUTH_HALF_MIN * km / south
        out.append(out[-1] + share)
    return out


OFFSETS = _offsets()


def fare(a, b):
    return FARES[a][b]


def card_fare(a, b):
    """With MRT Pass or Rapid Pass: 10% off, to the taka."""
    return int(FARES[a][b] * 9 // 10)


def ride_minutes(a, b):
    return int(round(abs(OFFSETS[b] - OFFSETS[a])))


def direction(a, b):
    return "south" if b > a else "north"


def terminus(a, b):
    """The station the train is heading for."""
    return SOUTH_END if b > a else NORTH_END


def _from_end(a, way):
    """Minutes from the end the train left to station [a]."""
    if way == "south":
        return OFFSETS[a]
    return OFFSETS[SOUTH_END] - OFFSETS[a]


def day_kind(local_days):
    """"fri", "sat" or "sun_thu" for a day count since 1970 (a Thursday)."""
    weekday = (local_days + 3) % 7  # 0 Monday ... 6 Sunday
    if weekday == 4:
        return "fri"
    if weekday == 5:
        return "sat"
    return "sun_thu"


def departures_from_end(kind, way):
    """Minutes after midnight of every train leaving the end of the line."""
    out = []
    for first, last, every in TIMETABLE[kind][way]:
        m = _minutes(first)
        stop = _minutes(last)
        while m <= stop:
            if not out or m > out[-1]:
                out.append(m)
            m += every
    # The last band ends on the day's last train (22:11 then 22:30, not 22:31).
    end = _minutes(TIMETABLE[kind][way][-1][1])
    if out and out[-1] < end:
        out.append(end)
    return out


def _day(local_days, a, b):
    """[(departs a, arrives b)] for one service day, seconds since 1970."""
    way = direction(a, b)
    base = local_days * clock_text.DAY - OFFSET
    lead = _from_end(a, way)
    ride = abs(OFFSETS[b] - OFFSETS[a])
    out = []
    for m in departures_from_end(day_kind(local_days), way):
        dep = base + int(round((m + lead) * 60))
        out.append((dep, dep + int(round(ride * 60))))
    return out


def next_trains(a, b, now, count=4):
    """The next [count] trains from [a] towards [b] after [now], today's
    first, then tomorrow's."""
    if a == b:
        return []
    today = (now + OFFSET) // clock_text.DAY
    out = [t for t in _day(today, a, b) if t[0] >= now - 30]
    if len(out) < count:
        out = out + _day(today + 1, a, b)
    return out[:count]


def first_last(a, b, now):
    """Departure times from [a] of today's first and last trains towards [b]."""
    if a == b:
        return None, None
    today = (now + OFFSET) // clock_text.DAY
    day = _day(today, a, b)
    if not day:
        return None, None
    return day[0][0], day[-1][0]


def headway_now(a, b, now):
    """Minutes between trains at [now], or None outside service hours."""
    if a == b:
        return None
    local = (now + OFFSET) % clock_text.DAY // 60
    today = (now + OFFSET) // clock_text.DAY
    way = direction(a, b)
    lead = _from_end(a, way)
    for first, last, every in TIMETABLE[day_kind(today)][way]:
        if _minutes(first) + lead <= local <= _minutes(last) + lead:
            return every
    return None
