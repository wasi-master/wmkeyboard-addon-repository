"""Firefly III's REST API (v1), as plain functions: addresses, request bodies
and readers for the replies. No network calls here, so tests can feed it
replies directly."""

import json


def base_url(server):
    """The address the user typed, as a base to append /api/v1 to:
    'money.example.com' -> 'https://money.example.com',
    'http://192.168.1.20:8080/firefly/' -> 'http://192.168.1.20:8080/firefly'.
    None when nothing is typed."""
    text = str(server or "").strip()
    if not text:
        return None
    if "://" not in text:
        text = "https://" + text
    while text.endswith("/"):
        text = text[:-1]
    if text.endswith("/api/v1"):
        text = text[:-7]
    return text


def host_of(server):
    base = base_url(server) or ""
    rest = base.split("://", 1)[-1]
    return rest.split("/", 1)[0]


def api(server, path):
    return base_url(server) + "/api/v1" + path


def headers(token):
    return {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.api+json",
    }


def money(value):
    """A number as Firefly wants amounts: a string with a dot, no sign."""
    return f"{abs(float(value)):.2f}"


def _attrs(item):
    return item.get("attributes") or {}


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def read_accounts(data):
    """GET /accounts?type=asset -> active asset accounts:
    [{"id", "name", "balance", "currency", "symbol", "places"}]."""
    out = []
    for item in (data or {}).get("data") or []:
        a = _attrs(item)
        if a.get("active") is False:
            continue
        out.append({
            "id": str(item.get("id")),
            "name": a.get("name") or "?",
            "balance": _number(a.get("current_balance")),
            "currency": a.get("currency_code") or "",
            "symbol": a.get("currency_symbol") or a.get("currency_code") or "",
            "places": a.get("currency_decimal_places") if isinstance(a.get("currency_decimal_places"), int) else 2,
        })
    return out


def read_named(data):
    """GET /categories or /budgets -> [{"id", "name"}], sorted by name."""
    out = []
    for item in (data or {}).get("data") or []:
        a = _attrs(item)
        if a.get("active") is False:
            continue
        out.append({"id": str(item.get("id")), "name": a.get("name") or "?"})
    out.sort(key=lambda x: x["name"].lower())
    return out


def read_summary(data):
    """GET /summary/basic -> {"spent": [...], "earned": [...], "balance": [...],
    "left": [...], "net": [...]}, each a list of
    {"currency", "value", "text"} per currency."""
    kinds = [("spent-in-", "spent"), ("earned-in-", "earned"), ("balance-in-", "balance"),
             ("left-to-spend-in-", "left"), ("net-worth-in-", "net"), ("bills-unpaid-in-", "unpaid")]
    out = {}
    for _, name in kinds:
        out[name] = []
    for key, entry in ((data or {}).get("data") or {}).items():
        if not isinstance(entry, dict):
            continue
        for prefix, name in kinds:
            if str(key).startswith(prefix):
                out[name].append({
                    "currency": entry.get("currency_code") or str(key)[len(prefix):],
                    "value": _number(entry.get("monetary_value")),
                    "text": entry.get("value_parsed") or str(entry.get("monetary_value")),
                })
    return out


def pick(entries, currency):
    """The entry in [currency], else the first, else None."""
    for e in entries:
        if e["currency"] == currency:
            return e
    return entries[0] if entries else None


def read_insight(data):
    """GET /insight/expense/category -> [(name, amount spent)], largest first."""
    rows = data.get("data") if isinstance(data, dict) else data
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or "No category"
        amount = abs(_number(row.get("difference_float", row.get("difference"))))
        if amount > 0:
            out.append((name, amount))
    out.sort(key=lambda r: -r[1])
    return out


def read_groups(data):
    """GET /transactions -> [{"id", "title", "splits": [split]}], where a split
    is {"journal", "type", "date", "amount", "description", "category_id",
    "category", "budget_id", "budget", "source", "destination", "symbol",
    "currency"}."""
    out = []
    for item in (data or {}).get("data") or []:
        a = _attrs(item)
        splits = []
        for t in a.get("transactions") or []:
            splits.append({
                "journal": str(t.get("transaction_journal_id")),
                "type": t.get("type") or "withdrawal",
                "date": str(t.get("date") or "")[:10],
                "amount": _number(t.get("amount")),
                "description": t.get("description") or "",
                "category_id": str(t.get("category_id")) if t.get("category_id") else None,
                "category": t.get("category_name"),
                "budget_id": str(t.get("budget_id")) if t.get("budget_id") else None,
                "budget": t.get("budget_name"),
                "source": t.get("source_name") or "",
                "destination": t.get("destination_name") or "",
                "symbol": t.get("currency_symbol") or t.get("currency_code") or "",
                "currency": t.get("currency_code") or "",
            })
        if splits:
            out.append({"id": str(item.get("id")), "title": a.get("group_title") or splits[0]["description"], "splits": splits})
    return out


def group_total(group):
    return sum(s["amount"] for s in group["splits"])


def withdrawal(draft, apply_rules=True, tag=None):
    """The body of POST /transactions for one receipt [draft]:
    {"description", "amount", "date", "source_id", "destination", "category_id"
    or "category", "budget_id", "notes", "items", "split", "currency",
    "foreign_amount"}. With "split" and items, one split per item, plus one for
    whatever the items leave of the total (tax, rounding)."""
    description = (draft.get("description") or "").strip() or "Receipt"
    destination = (draft.get("destination") or "").strip() or description
    base = {
        "type": "withdrawal",
        "date": draft.get("date"),
        "source_id": str(draft.get("source_id")),
        "destination_name": destination,
    }
    if draft.get("category"):
        base["category_name"] = draft["category"]
    elif draft.get("category_id"):
        base["category_id"] = str(draft["category_id"])
    if draft.get("budget_id"):
        base["budget_id"] = str(draft["budget_id"])
    if tag:
        base["tags"] = [tag]
    foreign = draft.get("foreign_currency")
    total = float(draft.get("amount") or 0)
    rows = []
    items = draft.get("items") or []
    if draft.get("split") and items and can_split(items, total):
        for item in items:
            rows.append((item["name"], item["amount"]))
        rest = round(total - sum(i["amount"] for i in items), 2)
        if rest >= 0.01:
            rows.append(("Tax and other", rest))
    else:
        rows.append((description, total))
    splits = []
    for name, amount in rows:
        split = dict(base)
        split["description"] = name
        if foreign:
            # The receipt's own currency; the account's amount is what Firefly books.
            share = amount / total if total else 1
            split["foreign_currency_code"] = foreign
            split["foreign_amount"] = money(amount)
            split["amount"] = money(float(draft.get("account_amount") or 0) * share)
        else:
            split["amount"] = money(amount)
        splits.append(split)
    if draft.get("notes"):
        splits[0]["notes"] = draft["notes"]
    body = {
        "error_if_duplicate_hash": True,
        "apply_rules": bool(apply_rules),
        "fire_webhooks": True,
        "transactions": splits,
    }
    if len(splits) > 1:
        body["group_title"] = description
    return body


def can_split(items, total):
    """Whether [items] fit inside [total]: each at least a cent, together not over it."""
    if not items:
        return False
    if any(i["amount"] < 0.01 for i in items):
        return False
    return sum(i["amount"] for i in items) <= float(total or 0) + 0.005


def recategorise(group, journal, category_id=None, budget_id=None):
    """The body of PUT /transactions/{group} giving one split a category or a
    budget. Every split's journal id goes along: Firefly deletes the splits
    an update leaves out."""
    rows = []
    for s in group["splits"]:
        row = {"transaction_journal_id": s["journal"]}
        if s["journal"] == journal:
            if category_id:
                row["category_id"] = str(category_id)
            if budget_id:
                row["budget_id"] = str(budget_id)
        rows.append(row)
    return {"apply_rules": False, "fire_webhooks": True, "transactions": rows}


def problem(response):
    """What went wrong, in words, from an error reply."""
    code = response.status_code
    message = ""
    try:
        data = json.loads(response.text)
    except ValueError:
        data = None
    if isinstance(data, dict):
        message = str(data.get("message") or "")
        errors = data.get("errors")
        if isinstance(errors, dict):
            first = []
            for field, texts in errors.items():
                if isinstance(texts, list) and texts:
                    first.append(str(texts[0]))
            if first:
                message = "; ".join(first[:3])
    if code == 401:
        return "Firefly III did not accept the token. Make a new Personal Access Token and paste it again."
    if code == 404:
        return "Not found on the server. Check the address on the plugin's settings page."
    if code >= 500:
        return f"The server had a problem ({code}). " + message
    return message or f"The server answered {code}."


def is_duplicate(response):
    """A 422 saying Firefly already has this exact transaction."""
    return response.status_code == 422 and "duplicate" in str(response.text).lower()
