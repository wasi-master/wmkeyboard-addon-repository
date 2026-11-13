"""Reads a scanned receipt's text: merchant, total, date, currency and items.

Regular expressions first, so it works with no AI set up. parse(text) gives a
dict; merge_ai(found, reply) lays a model's JSON answer over it where the
model's values make sense.
"""

import json
import re

# A money amount with two decimals: 1,234.56  1.234,56  1 234,56.
AMOUNT = r"(?:-?\d{1,3}(?:[,. ]\d{3})*[.,]\d{2}|-?\d+[.,]\d{2})"
# On a total line a whole number counts too (yen, won, taka).
WHOLE = r"(?:-?\d{1,3}(?:[,.]\d{3})+|-?\d+)"
# A run of digits and separators, taken whole so 1,250 is never read as 1,25.
NUMBER = r"-?\d(?:[\d,.]*\d)?"

# Words that mark the amount to pay, strongest first.
TOTAL_WORDS = [
    ("grand total", 5), ("total due", 5), ("amount due", 5), ("balance due", 5),
    ("amount payable", 5), ("net payable", 5), ("total to pay", 5), ("to pay", 4),
    ("total amount", 4), ("zu zahlen", 5), ("gesamtsumme", 5), ("total ttc", 5),
    ("te betalen", 5), ("importe total", 5), ("к оплате", 5),
    ("total", 3), ("summe", 3), ("gesamt", 3), ("montant", 3), ("totale", 3),
    ("importe", 2), ("totaal", 3), ("razem", 3), ("suma", 3), ("итого", 3),
    ("合計", 3), ("合计", 3), ("총액", 3), ("মোট", 3), ("कुल", 3),
]

# Lines that look like a total but are not the amount paid.
NOT_TOTAL = [
    "subtotal", "sub total", "sub-total", "zwischensumme", "sous-total", "total tax", "tax total",
    "total items", "total qty", "total quantity", "item count", "items sold", "total savings",
    "you saved", "savings", "discount", "change", "tendered", "rounding", "total vat", "vat total",
    "total points", "points",
]

# Lines that are payment, tax or bookkeeping, never an item bought.
NOT_ITEM = NOT_TOTAL + [
    "total", "tax", "vat", "gst", "hst", "mwst", "tva", "iva", "cash", "card", "visa", "mastercard",
    "amex", "debit", "credit", "paid", "payment", "balance", "tip", "gratuity", "service charge",
    "amount", "summe", "gesamt", "change", "auth", "approval", "terminal", "receipt", "invoice",
    "tel", "phone", "date", "time", "table", "order", "cashier", "server", "guest", "net",
]

# Header lines that are not the merchant's name.
NOT_MERCHANT = [
    "receipt", "invoice", "tax invoice", "welcome", "tel", "phone", "fax", "www", "http", "@",
    "vat", "gst", "order", "table", "date", "time", "cashier", "store #", "store no", "thank",
    "customer copy", "merchant copy", "duplicate", "bill", "check",
]

# Symbols and words that name a currency without ambiguity.
SYMBOLS = [
    ("R$", "BRL"), ("A$", "AUD"), ("C$", "CAD"), ("NZ$", "NZD"), ("HK$", "HKD"), ("S$", "SGD"),
    ("US$", "USD"), ("€", "EUR"), ("£", "GBP"), ("₹", "INR"), ("৳", "BDT"), ("₽", "RUB"),
    ("₩", "KRW"), ("₺", "TRY"), ("₫", "VND"), ("₱", "PHP"), ("₪", "ILS"), ("₴", "UAH"),
    ("₦", "NGN"), ("฿", "THB"), ("zł", "PLN"), ("Kč", "CZK"), ("Tk", "BDT"), ("Rp", "IDR"),
    ("RM", "MYR"), ("CHF", "CHF"), ("¥", "JPY"), ("$", "USD"),
]

CODES = [
    "USD", "EUR", "GBP", "JPY", "CNY", "INR", "BDT", "PKR", "LKR", "NPR", "RUB", "KRW", "TRY",
    "VND", "PHP", "ILS", "UAH", "NGN", "THB", "PLN", "CZK", "IDR", "MYR", "SGD", "HKD", "AUD",
    "NZD", "CAD", "CHF", "SEK", "NOK", "DKK", "HUF", "RON", "BGN", "BRL", "MXN", "ARS", "CLP",
    "COP", "PEN", "ZAR", "EGP", "MAD", "KES", "AED", "SAR", "QAR", "KWD", "TWD",
]

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    # German, French, Spanish and Dutch spellings that differ in the first letters.
    "mär": 3, "mai": 5, "okt": 10, "dez": 12, "janv": 1, "févr": 2, "fév": 2, "avr": 4,
    "juin": 6, "juil": 7, "aoû": 8, "déc": 12, "ene": 1, "abr": 4, "ago": 8, "dic": 12,
    "mrt": 3, "mei": 5,
}


def amount_value(text):
    """'1.234,56' -> 1234.56, '1,234.56' -> 1234.56, '12' -> 12.0, or None."""
    t = str(text).strip().replace(" ", "")
    if not t:
        return None
    negative = t.startswith("-")
    t = t.lstrip("-")
    last_dot = t.rfind(".")
    last_comma = t.rfind(",")
    cut = max(last_dot, last_comma)
    if cut >= 0 and len(t) - cut - 1 == 2:
        whole = t[:cut].replace(".", "").replace(",", "")
        t = whole + "." + t[cut + 1:]
    else:
        t = t.replace(".", "").replace(",", "")
    try:
        value = float(t)
    except ValueError:
        return None
    return -value if negative else value


def amounts_in(line, whole=False):
    """Every amount on [line], left to right, as numbers: those with cents,
    and with [whole] also whole ones (1,250 or 280, never a date)."""
    out = []
    for m in re.finditer(NUMBER, line):
        token = m.group(0)
        cut = max(token.rfind("."), token.rfind(","))
        cents = cut >= 0 and len(token) - cut - 1 == 2
        if not cents and not (whole and re.fullmatch(WHOLE, token)):
            continue
        v = amount_value(token)
        if v is not None:
            out.append(v)
    return out


def _has(line_lower, words):
    for w in words:
        if w in line_lower:
            return True
    return False


def _total(lines):
    """(amount, line index) of the amount paid, or (None, -1)."""
    best = None
    best_rank = 0
    best_at = -1
    for i, line in enumerate(lines):
        low = line.lower()
        if _has(low, NOT_TOTAL):
            continue
        rank = 0
        for word, weight in TOTAL_WORDS:
            if word in low:
                rank = weight
                break
        if rank == 0:
            continue
        found = amounts_in(line, whole=True)
        if not found and i + 1 < len(lines):
            found = amounts_in(lines[i + 1], whole=True)
        found = [a for a in found if a > 0]
        if not found:
            continue
        value = found[-1]
        # A stronger word wins; between equals, the later line (totals come last).
        if rank > best_rank or (rank == best_rank and best is not None):
            best = value
            best_rank = rank
            best_at = i
    if best is not None:
        return best, best_at
    # No total line: the largest amount that is not cash handed over or change.
    largest = None
    at = -1
    for i, line in enumerate(lines):
        low = line.lower()
        if _has(low, ["cash", "tendered", "change", "card no", "auth"]):
            continue
        for a in amounts_in(line):
            if a > 0 and (largest is None or a > largest):
                largest = a
                at = i
    return largest, at


def _merchant(lines):
    for line in lines[:6]:
        text = line.strip(" *-=#:.")
        low = text.lower()
        letters = len(re.findall(r"[^\W\d_]", text))
        if len(text) < 3 or letters < 3 or letters * 2 < len(text.replace(" ", "")):
            continue
        if _has(low, NOT_MERCHANT):
            continue
        if text.upper() == text:
            text = text.title()
        return text[:60]
    return None


def _valid(y, m, d):
    if y < 100:
        y += 2000
    if not (2000 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31):
        return None
    if m in (4, 6, 9, 11) and d > 30:
        return None
    if m == 2 and d > (29 if y % 4 == 0 else 28):
        return None
    return f"{y:04d}-{m:02d}-{d:02d}"


def _date(text, month_first):
    m = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", text)
    if m:
        found = _valid(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if found:
            return found
    for m in re.finditer(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b", text):
        a = int(m.group(1))
        b = int(m.group(2))
        y = int(m.group(3))
        if a > 12:
            found = _valid(y, b, a)
        elif b > 12:
            found = _valid(y, a, b)
        elif month_first:
            found = _valid(y, a, b)
        else:
            found = _valid(y, b, a)
        if found:
            return found
    for m in re.finditer(r"\b(\d{1,2})\.?\s+([^\W\d_]{3,9})\.?,?\s+(\d{2,4})\b", text):
        month = _month(m.group(2))
        if month:
            found = _valid(int(m.group(3)), month, int(m.group(1)))
            if found:
                return found
    for m in re.finditer(r"\b([^\W\d_]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b", text):
        month = _month(m.group(1))
        if month:
            found = _valid(int(m.group(3)), month, int(m.group(2)))
            if found:
                return found
    return None


def _month(word):
    w = word.lower()
    for name in (w[:4], w[:3]):
        if name in MONTHS:
            return MONTHS[name]
    return None


def _currency(text):
    for code in CODES:
        if re.search(r"\b" + code + r"\b", text):
            return code
    for symbol, code in SYMBOLS:
        if symbol in text:
            return code
    return None


def _items(lines, stop):
    out = []
    end = stop if stop >= 0 else len(lines)
    for line in lines[:end]:
        low = line.lower()
        if _has(low, NOT_ITEM):
            continue
        m = re.search(r"^(.*?[^\W\d_].*?)\s+[^\d\s-]{0,3}\s?(" + AMOUNT + r")\s*[A-Za-z*]{0,2}\s*$", line.strip())
        if not m:
            continue
        name = m.group(1).strip(" .:*-")
        # "2 x 3.50" or "2 @ 3.50" around the name: keep only the name.
        name = re.sub(r"\s+\d+\s*[x@×]\s*" + AMOUNT + r"\s*$", "", name)
        name = re.sub(r"\s+" + AMOUNT + r"\s*$", "", name)
        name = re.sub(r"^\d+\s*[x@×]\s*" + AMOUNT + r"\s+", "", name)
        amount = amount_value(m.group(2))
        if not name or amount is None or len(name) < 2:
            continue
        out.append({"name": name[:60], "amount": amount})
        if len(out) >= 40:
            break
    return out


def parse(text, month_first=False):
    """What the receipt says, as far as the text shows it:
    {"merchant", "total", "date" ("YYYY-MM-DD"), "currency", "items": [{"name", "amount"}]}.
    Anything not found is None (items: an empty list)."""
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    total, at = _total(lines)
    return {
        "merchant": _merchant(lines),
        "total": total,
        "date": _date("\n".join(lines), month_first),
        "currency": _currency("\n".join(lines)),
        "items": _items(lines, at),
    }


AI_SYSTEM = (
    "You read shop receipts. Answer with one JSON object and nothing else: "
    '{"merchant": str, "total": number, "date": "YYYY-MM-DD", "currency": "ISO 4217 code", '
    '"items": [{"name": str, "amount": number}]}. '
    "total is the amount paid. Use null for anything the receipt does not show."
)


def ai_prompt(text):
    return "Receipt text from a phone scanner:\n\n" + str(text)[:4000]


def merge_ai(found, reply):
    """[found] with the model's values laid over it where they are usable.
    A reply that is not JSON leaves [found] as it was."""
    out = dict(found)
    text = str(reply or "")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return out
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return out
    if not isinstance(data, dict):
        return out
    merchant = data.get("merchant")
    if isinstance(merchant, str) and merchant.strip():
        out["merchant"] = merchant.strip()[:60]
    total = data.get("total")
    if isinstance(total, str):
        total = amount_value(total)
    if isinstance(total, (int, float)) and total > 0:
        out["total"] = float(total)
    date = data.get("date")
    if isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date.strip()):
        parts = date.strip().split("-")
        valid = _valid(int(parts[0]), int(parts[1]), int(parts[2]))
        if valid:
            out["date"] = valid
    currency = data.get("currency")
    if isinstance(currency, str) and re.fullmatch(r"[A-Za-z]{3}", currency.strip()):
        out["currency"] = currency.strip().upper()
    items = data.get("items")
    if isinstance(items, list):
        clean = []
        for item in items[:40]:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            amount = item.get("amount")
            if isinstance(amount, str):
                amount = amount_value(amount)
            if isinstance(name, str) and name.strip() and isinstance(amount, (int, float)):
                clean.append({"name": name.strip()[:60], "amount": float(amount)})
        if clean:
            out["items"] = clean
    return out
