# Singapore bus arrivals from LTA DataMall (Bus Arrival v3).
#
# Every user brings their own free AccountKey from
# https://datamall.lta.gov.sg/content/datamall/en/request-for-api.html
# and the plugin keeps it in `secrets`. The reply lists each service at the
# stop with its next three buses: estimated arrival, how full, what kind of
# bus, and whether the time comes from the bus's own position.

import clock_text

URL = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"
SIGN_UP = "https://datamall.lta.gov.sg/content/datamall/en/request-for-api.html"

LOADS = {
    "SEA": ("Seats", "success"),
    "SDA": ("Standing", "warning"),
    "LSD": ("Full", "danger"),
}
TYPES = {"SD": "single deck", "DD": "double deck", "BD": "bendy"}
OPERATORS = {"SBST": "SBS Transit", "SMRT": "SMRT", "TTS": "Tower Transit", "GAS": "Go-Ahead"}


def stop_code(text):
    """The five-digit stop code in "83139", "sg-LTA_83139" or a stop id."""
    digits = ""
    for ch in str(text or "")[::-1]:
        if ch.isdigit():
            digits = ch + digits
        elif digits:
            break
    return digits if len(digits) == 5 else None


def bus(b, now):
    """One coming bus, or None when the slot is empty."""
    if not b:
        return None
    t = clock_text.parse_iso(b.get("EstimatedArrival") or "")
    if t is None:
        return None
    load = LOADS.get(b.get("Load"), ("", None))
    return {
        "t": t,
        "mins": max(0, int((t - now) // 60)),
        "load": load[0],
        "color": load[1],
        "type": TYPES.get(b.get("Type"), ""),
        "step_free": b.get("Feature") == "WAB",
        "live": str(b.get("Monitored")) == "1",
        "visit": b.get("VisitNumber"),
    }


def services(data, now):
    """[{no, operator, buses: [...]}] sorted by service number."""
    out = []
    for s in (data or {}).get("Services") or []:
        buses = []
        for slot in ("NextBus", "NextBus2", "NextBus3"):
            b = bus(s.get(slot), now)
            if b is not None:
                buses.append(b)
        out.append({
            "no": s.get("ServiceNo") or "?",
            "operator": OPERATORS.get(s.get("Operator"), s.get("Operator") or ""),
            "buses": buses,
        })
    out.sort(key=lambda s: service_order(s["no"]))
    return out


def service_order(no):
    digits = ""
    for ch in no:
        if ch.isdigit():
            digits += ch
        else:
            break
    return (int(digits) if digits else 9999, no)


def arrival_text(b):
    """"Arr", "3 min", "12 min" as Singapore's own signs show them."""
    if b["mins"] <= 1:
        return "Arr"
    return f"{b['mins']} min"
