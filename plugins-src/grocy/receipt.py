# Reading a shop receipt: which lines are things bought, how many of each,
# what they cost, and which Grocy product each one most likely is.
#
# Receipts differ by shop and country, so this is a set of rules that hold
# often, not a parser for one layout. The user checks every line before
# anything is added to stock.

import json
import re

# Lines with any of these words are about the payment, not a thing bought.
NOT_ITEMS = (
    "total", "subtotal", "sub total", "sum", "summe", "gesamt", "zu zahlen",
    "tax", "vat", "mwst", "ust", "tva", "iva", "gst", "hst",
    "change", "cash", "card", "visa", "mastercard", "maestro", "amex", "debit",
    "credit", "eftpos", "contactless", "balance", "payment", "paid", "tender",
    "rueckgeld", "rückgeld", "bar", "ec-karte", "kartenzahlung", "girocard",
    "especes", "espèces", "carte", "efectivo", "tarjeta", "cambio", "contanti",
    "resto", "receipt", "thank", "danke", "merci", "gracias", "grazie",
    "cashier", "kasse", "kassierer", "operator", "terminal", "auth", "trace",
    "approved", "invoice", "rechnung", "bon", "beleg", "www", "http", "tel",
    "phone", "vat no", "ust-id", "st.nr", "steuer", "rounding", "rundung",
    "points", "punkte", "member", "loyalty", "savings", "you saved", "coupon",
    "pfand", "deposit", "bottle return", "leergut", "items", "artikel",
    "qty", "quantity", "netto", "brutto", "net", "gross",
)

# Short words a receipt prints as units or flags, never part of a name.
NOISE = {
    "x", "kg", "g", "gr", "l", "ml", "cl", "pc", "pcs", "st", "stk", "ea",
    "each", "pk", "pkg", "eur", "usd", "gbp", "a", "b", "c", "d", "e", "f",
}

FOLD = {
    "á": "a", "à": "a", "â": "a", "ä": "a", "ã": "a", "å": "a", "ā": "a",
    "é": "e", "è": "e", "ê": "e", "ë": "e", "ē": "e", "í": "i", "ì": "i",
    "î": "i", "ï": "i", "ó": "o", "ò": "o", "ô": "o", "ö": "o", "õ": "o",
    "ø": "o", "ú": "u", "ù": "u", "û": "u", "ü": "u", "ñ": "n", "ç": "c",
    "ß": "ss", "œ": "oe", "æ": "ae", "ł": "l", "ś": "s", "ź": "z", "ż": "z",
    "č": "c", "š": "s", "ž": "z", "ř": "r", "ě": "e", "ů": "u", "ý": "y",
}

PRICE = r"(-?\d{1,6}[.,]\d{2})\s*[A-Za-z*€$£]{0,3}\s*$"
# "2 x 1.29", "2x1,29", "2 @ 1.29", "2 st x 0,99"
QTY_AT = r"(\d{1,3})\s*(?:st|stk|pcs|pc)?\s*[x×@*]\s*(\d{1,6}[.,]\d{2})"
# "x2" or "2x" next to the name
QTY_SHORT = r"(?:^|\s)(?:[xX]\s?(\d{1,3})|(\d{1,3})\s?[xX])(?:\s|$)"
# A weighed item: "0.512 kg x 2.99 EUR/kg"
WEIGHT = r"(\d{1,3}[.,]\d{1,3})\s*[kK][gG]"
# "2 MILK": a count, then the name.
LEADING_QTY = r"^(\d{1,2})\s+(\D.*)$"
ARTICLE_CODE = r"\b\d{4,}\b"
# A price left inside the name, such as the unit price before the total.
UNIT_PRICE = r"\b\d{1,6}[.,]\d{2}\b"


def fold(text):
    """Lowercase, accents gone, only letters, digits and single spaces."""
    out = []
    for ch in str(text).lower():
        ch = FOLD.get(ch, ch)
        if ch.isalnum():
            out.append(ch)
        else:
            out.append(" ")
    return " ".join("".join(out).split())


def words(text):
    """The words of [text] that can name a thing: no units, flags or numbers."""
    kept = []
    for w in fold(text).split():
        if w in NOISE or len(w) < 2 or any(c.isdigit() for c in w):
            continue
        kept.append(w)
    return kept


def number(text):
    return float(str(text).replace(",", "."))


def is_payment_line(line):
    low = " " + fold(line) + " "
    for word in NOT_ITEMS:
        if " " + fold(word) + " " in low:
            return True
    return False


def parse(text):
    """The things bought on a receipt: a list of dicts with `text` (the
    line as printed), `name` (the cleaned name), `amount` and `price` (the
    line's total, or None)."""
    items = []
    for raw in str(text).splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        letters = len([c for c in line if c.isalpha()])
        qty = re.search(QTY_AT, line)
        if letters < 3 or (qty is not None and len(words(line[:qty.start()] + line[qty.end():])) == 0):
            # A line of its own like "2 x 1,29": it counts the line above.
            if qty is not None and items and items[-1]["amount"] == 1:
                items[-1]["amount"] = int(qty.group(1))
                if items[-1]["price"] is None:
                    items[-1]["price"] = round(int(qty.group(1)) * number(qty.group(2)), 2)
            continue
        if is_payment_line(line):
            continue
        price = None
        name = line
        m = re.search(PRICE, name)
        if m is not None:
            price = number(m.group(1))
            name = name[:m.start()]
        if price is not None and price < 0:
            continue  # a discount line
        amount = 1
        m = re.search(QTY_AT, name)
        if m is not None:
            amount = int(m.group(1))
            name = name[:m.start()] + " " + name[m.end():]
        else:
            m = re.search(QTY_SHORT, name)
            if m is not None:
                amount = int(m.group(1) or m.group(2))
                name = name[:m.start()] + " " + name[m.end():]
            else:
                m = re.search(LEADING_QTY, name)
                if m is not None and int(m.group(1)) > 0:
                    amount = int(m.group(1))
                    name = m.group(2)
        if re.search(WEIGHT, name) is not None:
            name = re.sub(WEIGHT, " ", name)
        name = re.sub(ARTICLE_CODE, " ", name)
        name = re.sub(UNIT_PRICE, " ", name)
        name = " ".join(name.replace("*", " ").split()).strip(" -.:")
        # Tax and food flags printed after the name: "MILK F", "EGGS N".
        name = re.sub(r"(\s[A-Za-z])+$", "", name)
        if len(words(name)) == 0:
            continue
        items.append({"text": line, "name": name, "amount": max(1, amount), "price": price})
    # Where most lines carry a price, a line without one is the shop's name,
    # its address or a heading.
    priced = [i for i in items if i["price"] is not None]
    if len(priced) * 2 >= len(items):
        return priced
    return items


def _word_score(a, b):
    """How well receipt word [a] stands for product word [b]: 1 when equal,
    0.8 when one starts the other (receipts cut names short), else 0."""
    if a == b:
        return 1.0
    if len(a) >= 3 and len(b) >= 3 and (b.startswith(a) or a.startswith(b)):
        return 0.8
    # The same stem with another ending: "tomaten" and "tomatoes".
    same = 0
    while same < len(a) and same < len(b) and a[same] == b[same]:
        same += 1
    if same >= 4 and same >= 0.6 * min(len(a), len(b)):
        return 0.6
    return 0.0


def score(line_name, product_name):
    """0 to 1: how likely the receipt's [line_name] is [product_name]."""
    lw = words(line_name)
    pw = words(product_name)
    if not lw or not pw:
        return 0.0
    total = 0.0
    for p in pw:
        best = 0.0
        for w in lw:
            s = _word_score(w, p)
            if s > best:
                best = s
        total += best
    # Dice-like: the product's words found, against both lengths.
    return 2.0 * total / (len(pw) + len(lw))


def best_match(line_name, products, aliases=None, least=0.45):
    """The id of the product [line_name] most likely is, or None.
    [products] is a list of (id, name); [aliases] maps a folded line name the
    user matched before to the product id they picked."""
    key = fold(line_name)
    if aliases and key in aliases:
        known = aliases[key]
        for pid, _ in products:
            if pid == known:
                return pid
    best_id = None
    best = least
    for pid, name in products:
        s = score(line_name, name)
        if s > best:
            best = s
            best_id = pid
    return best_id


def ai_prompt(items, products, most=300):
    """A prompt asking a model to match receipt lines to products, and the
    system text to go with it."""
    shown = products[:most]
    lines = ["Products (id: name):"]
    for pid, name in shown:
        lines.append(f"{pid}: {name}")
    lines.append("")
    lines.append("Receipt lines (number: text):")
    for i, item in enumerate(items):
        lines.append(f"{i}: {item['text']}")
    system = (
        "You match lines from a shop receipt to products in a household stock list. "
        "Receipt names are often shortened or in capitals. Answer only with a JSON array, "
        "one object per receipt line: {\"line\": number, \"product\": id or null, \"amount\": number}. "
        "Use null when no product fits. amount is how many were bought, 1 unless the line says more."
    )
    return "\n".join(lines), system


def read_ai_reply(text, items, product_ids):
    """{line index: (product id or None, amount)} from a model's reply, keeping
    only lines and products that exist. Anything unreadable gives {}."""
    text = str(text or "")
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        return {}
    try:
        rows = json.loads(text[start:end + 1])
    except ValueError:
        return {}
    known = set(product_ids)
    out = {}
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        line = row.get("line")
        if not isinstance(line, int) or line < 0 or line >= len(items):
            continue
        pid = row.get("product")
        if isinstance(pid, str) and pid.isdigit():
            pid = int(pid)
        if pid not in known:
            pid = None
        amount = row.get("amount")
        if not isinstance(amount, (int, float)) or amount <= 0:
            amount = items[line]["amount"]
        out[line] = (pid, amount)
    return out
