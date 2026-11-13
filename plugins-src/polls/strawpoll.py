# StrawPoll, for people without a server of their own: polls on strawpoll.com,
# made with the user's free API key (strawpoll.com › Settings › API keys).
# API v4, live on strawpoll.com from 1 December 2026.

import time
from wm import _

BASE = "https://api.strawpoll.com/v4"


def request(acct, method, path, json=None, take=None, ok=()):
    out = {"method": method, "url": BASE + path, "take": take, "ok": ok,
           "headers": {"X-API-Key": acct["password"], "Accept": "application/json"}}
    if json is not None:
        out["json"] = json
    return out


def iso(seconds):
    """A time as ISO 8601 in UTC, which StrawPoll's closesAt takes."""
    days, rest = divmod(int(seconds), 86400)
    # Days since 1970-01-01 to a civil date (Howard Hinnant's algorithm).
    z = days + 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    if m <= 2:
        y += 1
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, m, d, rest // 3600, rest % 3600 // 60, rest % 60)


class StrawPoll:
    INFO = {
        "id": "strawpoll",
        "name": "StrawPoll",
        "account": "strawpoll",
        "server": False,
        "base": BASE,
        "user": False,
        "browser": False,
        "deadline": True,
        "close": True,
        "secret": _("API key"),
        "help": _("No server needed. Sign in at **strawpoll.com**, make a key under **Settings › API keys**, and paste it here."),
    }

    @staticmethod
    def explain(status, said):
        if status == 401 or status == 403:
            return _("StrawPoll turned down the API key. Paste it again under Account.")
        if status == 429:
            return _("Too many requests to StrawPoll. Wait a minute and try again.")
        return ""

    @staticmethod
    def check(acct):
        return [lambda ctx: request(acct, "GET", "/me")]

    @staticmethod
    def logout(acct):
        return []

    @staticmethod
    def create(acct, poll):
        field = {
            "type": "multiple_choice",
            "label": poll["question"],
            "properties": {"isMultipleChoice": poll["multi"]},
            "choices": [{"label": o} for o in poll["options"]],
        }
        body = {
            "title": poll["question"],
            "status": "published",
            "sections": [{"type": "multiple_choice", "title": poll["question"], "fields": [field]}],
        }
        if poll["deadline"]:
            body["properties"] = {"closesAt": iso(poll["deadline"])}

        def made(ctx, r):
            form = r.json()
            form = form.get("data", form) if isinstance(form, dict) else {}
            urls = form.get("urls") or {}
            ctx["url"] = urls.get("formUrl") or ("https://strawpoll.com/r/" + form["slug"])
            ctx["remote"] = {"slug": form["slug"]}

        return [lambda ctx: request(acct, "POST", "/forms", json=body, take=made)]

    @staticmethod
    def results(acct, record):
        slug = record["remote"]["slug"]

        def read(ctx, r):
            form = r.json()
            form = form.get("data", form) if isinstance(form, dict) else {}
            counts = [0 for _o in record["options"]]
            for section in form.get("sections") or []:
                for field in section.get("fields") or []:
                    for choice in field.get("choices") or []:
                        label = choice.get("label")
                        if label in record["options"]:
                            counts[record["options"].index(label)] = int(choice.get("responseCount") or 0)
            ctx["counts"] = counts
            ctx["responses"] = int(form.get("responseCount") or 0)
            closes = (form.get("properties") or {}).get("closesAt")
            ctx["closed"] = form.get("isOpen") is False or bool(closes and record.get("deadline") and record["deadline"] <= time.time())

        return [lambda ctx: request(acct, "GET", "/forms/" + slug, take=read)]

    @staticmethod
    def close(acct, record):
        return [lambda ctx: request(acct, "PATCH", "/forms/" + record["remote"]["slug"], json={"isOpen": False})]

    @staticmethod
    def delete(acct, record):
        return [lambda ctx: request(acct, "DELETE", "/forms/" + record["remote"]["slug"], ok=(404,))]
