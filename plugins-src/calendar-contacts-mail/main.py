# Calendar, Contacts and Mail: .ics events, .vcf contacts, .eml messages and
# .mbox mailboxes, drawn in the file manager.

from wm import plugin, ui

import text as t

MAX_EVENTS = 200
MAX_CONTACTS = 300
MAX_MESSAGES = 300
BODY_CHARS = 20000


# MARK: - calendars

FREQ = {"DAILY": ("day", "days"), "WEEKLY": ("week", "weeks"), "MONTHLY": ("month", "months"), "YEARLY": ("year", "years")}
WEEKDAYS = {"MO": "Monday", "TU": "Tuesday", "WE": "Wednesday", "TH": "Thursday", "FR": "Friday", "SA": "Saturday", "SU": "Sunday"}


def repeats(rule):
    """An RRULE in words: "Every 2 weeks on Monday, Friday, 10 times"."""
    parts = {}
    for piece in rule.split(";"):
        if "=" in piece:
            k, v = piece.split("=", 1)
            parts[k.upper()] = v
    one, many = FREQ.get(parts.get("FREQ", ""), ("time", "times"))
    every = int(parts.get("INTERVAL", "1") or "1")
    out = f"Every {one}" if every == 1 else f"Every {every} {many}"
    if "BYDAY" in parts:
        days = [WEEKDAYS.get(d[-2:], d) for d in parts["BYDAY"].split(",")]
        out = out + " on " + ", ".join(days)
    if "COUNT" in parts:
        out = out + f", {parts['COUNT']} times"
    if "UNTIL" in parts:
        out = out + ", until " + t.when(parts["UNTIL"])
    return out


def components(lines, kinds):
    """The BEGIN:kind … END:kind blocks as [(kind, {NAME: [(params, value)]})]."""
    out = []
    stack = []
    for line in lines:
        p = t.prop(line)
        if p is None:
            continue
        name, params, value = p
        if name == "BEGIN":
            stack.append((value.upper(), {}))
            continue
        if name == "END":
            if stack:
                kind, props = stack.pop()
                if kind in kinds:
                    out.append((kind, props))
            continue
        if stack:
            stack[-1][1].setdefault(name, []).append((params, value))
    return out


def first(props, name, default=""):
    found = props.get(name)
    return t.unescape(found[0][1]) if found else default


def _person(value, params):
    name = params.get("CN", "")
    mail = value[7:] if value.lower().startswith("mailto:") else value
    return f"{name} <{mail}>" if name and mail else (name or mail)


def show_event(kind, props):
    summary = first(props, "SUMMARY", "(No title)")
    start = props.get("DTSTART")
    end = props.get("DTEND") or props.get("DUE")
    with ui.card(title=("✓ " if kind == "VTODO" else "") + summary):
        if start:
            line = t.when(start[0][1], start[0][0])
            if end:
                finish = t.when(end[0][1], end[0][0])
                same_day = finish[:15] == line[:15] and "," in finish
                line = line + " – " + (finish.split(", ", 1)[1] if same_day else finish)
            ui.label(line)
        elif end:
            ui.label("Due " + t.when(end[0][1], end[0][0]))
        place = first(props, "LOCATION")
        if place:
            ui.label("📍 " + place)
        rule = first(props, "RRULE")
        if rule:
            ui.caption(repeats(rule))
        status = first(props, "STATUS")
        if status and status.upper() != "CONFIRMED":
            ui.caption(status.capitalize())
        org = props.get("ORGANIZER")
        if org:
            ui.caption("Organiser: " + _person(org[0][1], org[0][0]))
        people = props.get("ATTENDEE", [])
        if people:
            names = [_person(v, p) for p, v in people[:8]]
            ui.caption(f"{len(people)} invited: " + ", ".join(names) + ("…" if len(people) > 8 else ""))
        note = first(props, "DESCRIPTION")
        if note:
            ui.label(note[:2000])
        link = first(props, "URL")
        if link:
            ui.caption(link)


@plugin.preview("calendar")
def show_calendar(file):
    lines = t.unfold(file.text())
    name = ""
    for line in lines[:40]:
        p = t.prop(line)
        if p is not None and p[0] in ("X-WR-CALNAME", "NAME"):
            name = t.unescape(p[2])
            break
    items = components(lines, ("VEVENT", "VTODO", "VJOURNAL"))
    if not items:
        ui.empty("This calendar has no events.")
        return
    items = sorted(items, key=lambda kp: t.sort_key(kp[1].get("DTSTART", kp[1].get("DUE", [({}, "")]))[0][1]))
    events = len([1 for k, p in items if k == "VEVENT"])
    tasks = len(items) - events
    counts = [f"{events} event" + ("" if events == 1 else "s")] if events else []
    if tasks:
        counts.append(f"{tasks} task" + ("" if tasks == 1 else "s"))
    if name:
        ui.label(name, style="headline")
    ui.caption(" · ".join(counts))
    for kind, props in items[:MAX_EVENTS]:
        show_event(kind, props)
    if len(items) > MAX_EVENTS:
        ui.caption(f"{len(items) - MAX_EVENTS} more")


# MARK: - contacts

def _value(params, value):
    """A vCard value, decoded as its parameters say."""
    enc = params.get("ENCODING", "").upper()
    if enc == "QUOTED-PRINTABLE":
        return t.charset(t.quoted_printable(value), params.get("CHARSET"))
    return t.unescape(value)


def _kind(params):
    kinds = [k.lower() for k in params.get("TYPE", "").replace(";", ",").split(",") if k]
    kinds = [k for k in kinds if k not in ("pref", "voice", "internet", "x400")]
    return ", ".join(kinds)


def contacts(text):
    cards = []
    lines = t.unfold_qp(t.unfold(text))
    for kind, props in components(lines, ("VCARD",)):
        cards.append(props)
    return cards


def card_name(props):
    for p, v in props.get("FN", []):
        name = _value(p, v).strip()
        if name:
            return name
    for p, v in props.get("N", []):
        parts = [x.strip() for x in _value(p, v).split(";")]
        while len(parts) < 5:
            parts.append("")
        name = " ".join(x for x in (parts[3], parts[1], parts[2], parts[0], parts[4]) if x)
        if name:
            return name
    for p, v in props.get("ORG", []):
        return _value(p, v).replace(";", ", ")
    return "(No name)"


def photo(props):
    """A contact's photo as bytes, or None."""
    for p, v in props.get("PHOTO", []):
        if v.startswith("data:"):
            comma = v.find(",")
            return t.b64(v[comma + 1:]) if comma > 0 else None
        enc = p.get("ENCODING", "").upper()
        if enc in ("B", "BASE64"):
            return t.b64(v)
    return None


def show_contact(props, full):
    name = card_name(props)
    rows = []
    for p, v in props.get("TEL", []):
        rows.append(["Phone" + (" (" + _kind(p) + ")" if _kind(p) else ""), _value(p, v)])
    for p, v in props.get("EMAIL", []):
        rows.append(["Email" + (" (" + _kind(p) + ")" if _kind(p) else ""), _value(p, v)])
    for p, v in props.get("ADR", []):
        parts = [x.strip() for x in _value(p, v).split(";") if x.strip()]
        if parts:
            rows.append(["Address" + (" (" + _kind(p) + ")" if _kind(p) else ""), ", ".join(parts)])
    for key, label in (("ORG", "Organisation"), ("TITLE", "Job title"), ("BDAY", "Birthday"), ("URL", "Website"),
                       ("NICKNAME", "Nickname"), ("NOTE", "Note")):
        for p, v in props.get(key, []):
            value = _value(p, v)
            if key == "ORG":
                value = ", ".join(x for x in value.split(";") if x)
            elif key == "BDAY":
                value = t.when(value)
            if value.strip():
                rows.append([label, value.strip()])
    if full:
        picture = photo(props)
        if picture:
            ui.image(picture, alt=name, height=140)
        ui.label(name, style="headline")
        if rows:
            ui.table(rows)
        return
    with ui.card(title=name):
        for label, value in rows[:6]:
            ui.label(label + ": " + value)


@plugin.preview("contacts")
def show_contacts(file):
    cards = contacts(file.text())
    if not cards:
        ui.empty("This file has no contacts.")
        return
    if len(cards) == 1:
        show_contact(cards[0], True)
        return
    ui.caption(f"{len(cards)} contacts")
    for props in sorted(cards[:MAX_CONTACTS], key=lambda c: card_name(c).lower()):
        show_contact(props, False)
    if len(cards) > MAX_CONTACTS:
        ui.caption(f"{len(cards) - MAX_CONTACTS} more")


@plugin.thumbnail("contacts")
def contact_photo(file):
    cards = contacts(file.text())
    picture = photo(cards[0]) if cards else None
    return picture if picture and len(picture) <= 524288 else None


# MARK: - mail

def headers(block):
    """[(name, value)] from a header block, folded lines joined."""
    out = []
    for line in t.unfold(block, keep=True):
        colon = line.find(":")
        if colon > 0 and " " not in line[:colon]:
            out.append((line[:colon].lower(), line[colon + 1:].strip()))
    return out


def header(hs, name, default=""):
    for k, v in hs:
        if k == name:
            return v
    return default


def _param(value, name):
    """A parameter such as boundary= or charset= from a header value."""
    low = value.lower()
    at = low.find(name + "=")
    if at < 0:
        return ""
    rest = value[at + len(name) + 1:]
    if rest.startswith("\""):
        end = rest.find("\"", 1)
        return rest[1:end] if end > 0 else rest[1:]
    end = len(rest)
    for stop in (";", " ", "\t"):
        i = rest.find(stop)
        if 0 <= i < end:
            end = i
    return rest[:end]


def split_message(raw):
    """(headers, body bytes): the blank line between them."""
    for sep in (b"\r\n\r\n", b"\n\n"):
        at = raw.find(sep)
        if at >= 0:
            return headers(raw[:at].decode("utf-8", "replace")), raw[at + len(sep):]
    return headers(raw.decode("utf-8", "replace")), b""


def decode_body(hs, body):
    enc = header(hs, "content-transfer-encoding").lower().strip()
    if enc == "base64":
        return t.b64(body.decode("utf-8", "replace"))
    if enc == "quoted-printable":
        return t.quoted_printable(body.decode("utf-8", "replace").replace("\r\n", "\n"))
    return body


def parts(hs, body, out, depth=0):
    """Walks a MIME tree: out gets {"type", "text", "name", "size"} for each leaf."""
    kind = header(hs, "content-type", "text/plain").split(";")[0].strip().lower()
    if kind.startswith("multipart/") and depth < 6:
        boundary = _param(header(hs, "content-type"), "boundary")
        if boundary:
            marker = b"--" + boundary.encode("utf-8")
            pieces = body.split(marker)
            for piece in pieces[1:]:
                if piece.startswith(b"--"):
                    break
                if piece.startswith(b"\r\n"):
                    piece = piece[2:]
                elif piece.startswith(b"\n"):
                    piece = piece[1:]
                sub_h, sub_b = split_message(piece)
                parts(sub_h, sub_b, out, depth + 1)
            return
    disposition = header(hs, "content-disposition")
    name = t.words(_param(disposition, "filename") or _param(header(hs, "content-type"), "name"))
    data = decode_body(hs, body)
    if name or disposition.lower().startswith("attachment"):
        out.append({"type": kind, "name": name or "attachment", "size": len(data), "text": None})
    elif kind in ("text/plain", "text/html"):
        out.append({"type": kind, "name": None, "size": len(data),
                    "text": t.charset(data, _param(header(hs, "content-type"), "charset"))})
    elif kind == "message/rfc822":
        sub_h, sub_b = split_message(data)
        parts(sub_h, sub_b, out, depth + 1)
    else:
        out.append({"type": kind, "name": kind, "size": len(data), "text": None})


def html_text(html):
    from wm.preview import xml
    tree = xml(html, max_nodes=40000)
    lines = []
    for e in tree.iter():
        if e.name in ("p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "blockquote"):
            words = " ".join(e.text.split())
            if words:
                lines.append(words)
    if not lines:
        return " ".join(tree.all_text().split())
    return "\n".join(lines)


def _size(n):
    if n < 1024:
        return f"{n} B"
    if n < 1048576:
        return f"{n // 1024} KB"
    return f"{n // 1048576} MB"


def show_message(raw):
    hs, body = split_message(raw)
    subject = t.words(header(hs, "subject", "(No subject)"))
    ui.label(subject, style="headline")
    rows = []
    for key, label in (("from", "From"), ("to", "To"), ("cc", "Cc"), ("reply-to", "Reply to")):
        value = header(hs, key)
        if value:
            rows.append([label, t.words(value)])
    date = header(hs, "date")
    if date:
        rows.append(["Date", date])
    if rows:
        ui.table(rows)
    found = []
    parts(hs, body, found)
    plain = [p for p in found if p["type"] == "text/plain" and p["text"] is not None]
    html = [p for p in found if p["type"] == "text/html" and p["text"] is not None]
    if plain:
        ui.label("\n\n".join(p["text"].strip() for p in plain)[:BODY_CHARS])
    elif html:
        ui.label(html_text(html[0]["text"])[:BODY_CHARS])
    attached = [p for p in found if p["text"] is None]
    if attached:
        with ui.section(f"{len(attached)} attachment" + ("" if len(attached) == 1 else "s"), collapsible=True):
            for a in attached[:50]:
                ui.item(a["name"], subtitle=a["type"] + " · " + _size(a["size"]), icon="attach_file")


def mailbox(raw):
    """An mbox's messages: the "From " line that starts each one."""
    starts = []
    at = 0 if raw.startswith(b"From ") else -1
    if at == 0:
        starts.append(0)
    while len(starts) <= MAX_MESSAGES:
        nxt = raw.find(b"\nFrom ", at + 1)
        if nxt < 0:
            break
        starts.append(nxt + 1)
        at = nxt + 1
    out = []
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(raw)
        msg = raw[s:end]
        line = msg.find(b"\n")
        out.append(msg[line + 1:] if line >= 0 else b"")
    return out


@plugin.preview("mail")
def show_mail(file):
    raw = file.data
    if file.extension in ("mbox", "mbx") or raw.startswith(b"From "):
        messages = mailbox(raw)
        if not messages:
            ui.empty("This mailbox has no messages.")
            return
        if len(messages) == 1:
            show_message(messages[0])
            return
        ui.caption(f"{len(messages)} messages" + (" or more" if file.truncated or len(messages) > MAX_MESSAGES else ""))
        for m in messages[:MAX_MESSAGES]:
            hs, body = split_message(m)
            ui.item(t.words(header(hs, "subject", "(No subject)")),
                    subtitle=t.words(header(hs, "from")) + " · " + header(hs, "date"), icon="mail")
        return
    show_message(raw)
