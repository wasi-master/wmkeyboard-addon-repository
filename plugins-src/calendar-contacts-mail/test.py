# Tests for Calendar, Contacts and Mail, run by tools/test_plugins.py under
# wm-python-cli. tests/ holds hand-written files in the shapes phones and mail
# programs export: CRLF lines, folding, quoted-printable, encoded words.

import json

import text as t


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


# MARK: - decoding

assert t.words("=?UTF-8?Q?Caf=C3=A9_plans?= =?UTF-8?Q?_for_Friday?=") == "Café plans for Friday"
assert t.words("Re: =?ISO-8859-1?Q?caf=E9?= time") == "Re: café time"
assert t.unescape("a\\, b\\nc") == "a, b\nc"
assert t.when("20260304T100000Z") == "Wed 4 Mar 2026, 10:00 UTC"
assert t.when("2026-03-01") == "Sun 1 Mar 2026"

# MARK: - calendars

root = shown("calendar", "team.ics")
text = words(root)
has(text, "Team", "2 events · 1 task",
    "Holiday", "Sun 1 Mar 2026 – Mon 2 Mar 2026",
    "Stand-up", "Wed 4 Mar 2026, 10:00 (Asia/Dhaka) – 10:15 (Asia/Dhaka)",
    "📍 Room 4, second floor", "Every 2 weeks on Monday, Friday, 10 times",
    "Organiser: Ann <ann@example.com>", "2 invited: Bo, B <bo@example.com>, cy@example.com",
    "Line one\nLine two that is long enough to be folded across two lines",
    "✓ Send report", "Due Thu 5 Mar 2026, 17:00 UTC", "Needs-action")
titles = [c["title"] for c in find(root, "card")]
assert titles == ["Holiday", "Stand-up", "✓ Send report"], titles

# MARK: - contacts

root = shown("contacts", "people.vcf")
text = words(root)
has(text, "2 contacts", "Ayséa Karim", "Phone (cell): +8801700000000", "Email (home): a@example.com",
    "Bo Lee", "Phone (work): 555-0101", "Organisation: Acme, Sales", "Address (work): 1 Main St, Springfield, 12345, USA")
titles = [c["title"] for c in find(root, "card")]
assert titles == ["Ayséa Karim", "Bo Lee"], titles

root = shown("contacts", "one.vcf")
has(words(root), "Cy Diaz", "Email (work)", "cy@example.com", "Birthday", "Thu 15 Feb 1990", "Met at the fair, 2024")
assert find(root, "image")[0]["src"].startswith("data:iVBORw0KGgo")

assert plugin_test.thumbnail("contacts", "tests/people.vcf")["value"].startswith("iVBORw0KGgo"), "the first contact's photo"
assert plugin_test.thumbnail("contacts", "tests/one.vcf")["value"].startswith("iVBORw0KGgo")

# MARK: - mail

root = shown("mail", "hello.eml")
text = words(root)
has(text, "Café plans for Friday", "Ayéa <a@example.com>", "Bo <bo@example.com>, Cy <cy@example.com>",
    "Wed, 4 Mar 2026 10:00:00 +0600", "Let's meet at the café at 5. See you.", "1 attachment", "menu.pdf", "application/pdf · 13 B")
assert "<p>" not in text, "the plain part wins over HTML"

has(words(shown("mail", "news.eml")), "Weekly news", "News\nPrices fell & rose.\nCafé open")

root = shown("mail", "box.mbox")
has(words(root), "2 messages", "First", "a@example.com", "Second", "b@example.com")
