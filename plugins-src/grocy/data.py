# Grocy's numbers, units, dates and products, made small and readable.
#
# Grocy 3 sends numbers as text and Grocy 4 as numbers, so everything goes
# through num(). Dates are "YYYY-MM-DD"; 2999-12-31 means "never".

import time
import wm

NEVER = "2999-12-31"

# What the panel keeps of a product row (a whole row with userfields can be
# a few KB; the stored cache keeps only these).
PRODUCT_FIELDS = (
    "id", "name", "location_id", "qu_id_stock", "qu_id_purchase", "qu_id_consume",
    "min_stock_amount", "quick_consume_amount", "quick_open_amount",
    "default_best_before_days", "default_best_before_days_after_open",
    "disable_open", "active", "parent_product_id",
)


def num(v, default=0.0):
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return default


def ident(v):
    """A row id as an int (Grocy 3 sends "7"), or None."""
    if v is None or v == "":
        return None
    try:
        return int(num(v))
    except (ValueError, TypeError):
        return None


def amount_text(n):
    """1, 1.5, 0.25: no trailing zeros."""
    n = round(num(n), 2)
    if n == int(n):
        return str(int(n))
    text = f"{n:.2f}".rstrip("0").rstrip(".")
    return text


def unit_name(units, qu_id, n=1):
    unit = units.get(str(ident(qu_id))) if units else None
    if unit is None:
        return ""
    if num(n) == 1:
        return unit.get("name") or ""
    return unit.get("name_plural") or unit.get("name") or ""


def amount_with_unit(n, units, qu_id):
    name = unit_name(units, qu_id, n)
    return (amount_text(n) + " " + name).strip()


def slim_product(row):
    return {k: row.get(k) for k in PRODUCT_FIELDS if k in row}


def slim_unit(row):
    return {"id": ident(row.get("id")), "name": row.get("name") or "", "name_plural": row.get("name_plural") or ""}


def version_of(info):
    """(major, minor, patch) from /system/info, or None when the answer is
    not Grocy's."""
    if not isinstance(info, dict):
        return None
    v = info.get("grocy_version")
    if not isinstance(v, dict):
        return None
    parts = []
    for piece in str(v.get("Version", "")).split(".")[:3]:
        digits = "".join([c for c in piece if c.isdigit()])
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return (parts[0], parts[1], parts[2])


# ---------------------------------------------------------------- dates ----

def today(now=None):
    return time.format("yyyy-MM-dd", time.time() if now is None else now)


def stamp(date_text):
    """Noon of a "YYYY-MM-DD" day in seconds, or None."""
    parts = str(date_text or "")[:10].split("-")
    if len(parts) != 3:
        return None
    try:
        return wm.timestamp(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, TypeError):
        return None


def days_until(date_text, now=None):
    """Whole days from today to [date_text]: 0 today, -2 two days ago. None
    for no date or never."""
    if not date_text or str(date_text).startswith(NEVER):
        return None
    then = stamp(date_text)
    if then is None:
        return None
    start = stamp(today(now))
    return int(round((then - start) / 86400.0))


def plus_days(days, now=None):
    """The date [days] after today, as "YYYY-MM-DD"."""
    return time.format("yyyy-MM-dd", stamp(today(now)) + days * 86400)


def due_text(date_text, now=None):
    d = days_until(date_text, now)
    if d is None:
        return ""
    if d == 0:
        return "due today"
    if d == 1:
        return "due tomorrow"
    if d == -1:
        return "1 day overdue"
    if d < 0:
        return f"{-d} days overdue"
    if d < 14:
        return f"due in {d} days"
    return "due " + time.format("d MMM", stamp(date_text))


def default_due(product, now=None):
    """The best-before date Grocy would give a purchase: never for -1, none
    for 0 (the user picks), today + N otherwise."""
    days = int(num((product or {}).get("default_best_before_days"), 0))
    if days < 0:
        return NEVER
    if days == 0:
        return None
    return plus_days(days, now)


def when_text(datetime_text, now=None):
    """A chore's next time as words: "today", "3 days overdue", "in 2 days",
    or "whenever" for none."""
    if not datetime_text or str(datetime_text).startswith(NEVER):
        return "whenever"
    d = days_until(str(datetime_text)[:10], now)
    if d is None:
        return "whenever"
    if d == 0:
        return "today"
    if d == 1:
        return "tomorrow"
    if d == -1:
        return "1 day overdue"
    if d < 0:
        return f"{-d} days overdue"
    return f"in {d} days"


def now_text(now=None):
    """Grocy's datetime format for a tracked time."""
    return time.format("yyyy-MM-dd HH:mm:ss", time.time() if now is None else now)
