# LimeSurvey, through RemoteControl 2 (JSON-RPC at /index.php/admin/remotecontrol),
# which the server's admin turns on in Global settings › Interfaces.
#
# RemoteControl has no call that adds a question with its answers, so the
# question goes in as a question file (.lsq), the same thing LimeSurvey's own
# "Import question" takes. The file uses the layout without separate
# translation tables, which LimeSurvey 3 to 6 all import.
#
# Every job signs in for a session key first and gives it back at the end.

import base64
import html
import json
import random
import re
import time
from wm import _
import wm

PATH = "/index.php/admin/remotecontrol"
LANGUAGE = "en"


class RpcError(Exception):
    """LimeSurvey's own refusal, from a {"status": ...} result."""


def rpc(acct, method, params, take=None):
    def read(ctx, r):
        try:
            body = r.json()
        except ValueError:
            raise RpcError(_("LimeSurvey's JSON-RPC interface is off. Turn it on under Configuration › Global settings › Interfaces."))
        if not isinstance(body, dict):
            raise RpcError(_("LimeSurvey's JSON-RPC interface is off. Turn it on under Configuration › Global settings › Interfaces."))
        if body.get("error"):
            raise RpcError(str(body["error"]))
        result = body.get("result")
        if isinstance(result, dict) and isinstance(result.get("status"), str) and result["status"] != "OK":
            raise RpcError(wording(result["status"]))
        if take is not None:
            take(ctx, result)
    return {
        "method": "POST",
        "url": acct["base"] + PATH,
        "json": {"method": method, "params": params, "id": 1},
        "take": read,
    }


def wording(status):
    if status.startswith("Invalid user name or password"):
        return _("LimeSurvey turned down the user name or password. Sign in again under Account.")
    if status == "No permission":
        return _("Your LimeSurvey account isn't allowed to do that.")
    if status.startswith("Invalid session key"):
        return _("LimeSurvey ended the session. Try again.")
    return _("LimeSurvey said: {what}", what=status)


def signed(acct, steps):
    """[steps] between taking a session key and giving it back."""
    def keep(ctx, result):
        if not isinstance(result, str):
            raise RpcError(_("LimeSurvey's JSON-RPC interface is off. Turn it on under Configuration › Global settings › Interfaces."))
        ctx["key"] = result
    out = [lambda ctx: rpc(acct, "get_session_key", [acct["user"], acct["password"]], take=keep)]
    out.extend(steps)
    out.append(lambda ctx: rpc(acct, "release_session_key", [ctx["key"]]))
    return out


def cdata(text):
    return "<![CDATA[" + str(text).replace("]]>", "]]]]><![CDATA[>") + "]]>"


def row(fields):
    return "   <row>\n" + "".join(["    <" + k + ">" + cdata(v) + "</" + k + ">\n" for k, v in fields]) + "   </row>\n"


def table(name, rows):
    if not rows:
        return ""
    names = [k for k, _v in rows[0]]
    head = "  <fields>\n" + "".join(["   <fieldname>" + n + "</fieldname>\n" for n in names]) + "  </fields>\n"
    return " <" + name + ">\n" + head + "  <rows>\n" + "".join([row(r) for r in rows]) + "  </rows>\n </" + name + ">\n"


def question_file(poll):
    """The poll as a .lsq question file: type L (one answer, radio buttons)
    with answer options, or type M (several answers, checkboxes) with
    subquestions."""
    kind = "M" if poll["multi"] else "L"

    def question(qid, parent, title, text, order):
        return [
            ("qid", qid), ("parent_qid", parent), ("sid", 1), ("gid", 1), ("type", kind),
            ("title", title), ("question", html.escape(text)), ("preg", ""), ("help", ""),
            ("other", "N"), ("mandatory", "Y" if parent == 0 else "N"), ("question_order", order),
            ("language", LANGUAGE), ("scale_id", 0), ("same_default", 0), ("relevance", "1"),
        ]

    questions = [question(1, 0, "Q1", poll["question"], 0)]
    subquestions = []
    answers = []
    for i, option in enumerate(poll["options"]):
        if poll["multi"]:
            subquestions.append(question(10 + i, 1, code(i), option, i + 1))
        else:
            answers.append([
                ("qid", 1), ("code", code(i)), ("answer", html.escape(option)), ("sortorder", i + 1),
                ("assessment_value", 0), ("language", LANGUAGE), ("scale_id", 0),
            ])
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<document>\n'
        " <LimeSurveyDocType>Question</LimeSurveyDocType>\n <DBVersion>366</DBVersion>\n"
        " <languages>\n  <language>" + LANGUAGE + "</language>\n </languages>\n"
        + table("questions", questions) + table("subquestions", subquestions) + table("answers", answers)
        + "</document>\n"
    )


def code(i):
    """A1, A2...: answer codes for one answer, subquestion titles for several."""
    return "A" + str(i + 1)


def stamp(seconds):
    """A time as LimeSurvey stores it, in the phone's time zone."""
    return time.format("yyyy-MM-dd HH:mm:ss", seconds)


def unstamp(text):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?", str(text or ""))
    if not m:
        return None
    parts = [int(p) if p else 0 for p in m.groups()]
    return wm.timestamp(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])


def tally(rows, record):
    """Counts per answer from export_responses' rows, keyed by question code."""
    counts = [0 for _o in record["options"]]
    for item in rows:
        if isinstance(item, dict) and len(item) == 1:
            only = list(item.values())[0]
            if isinstance(only, dict):
                item = only
        if not isinstance(item, dict):
            continue
        for i in range(len(record["options"])):
            if record["multi"]:
                ticked = item.get("Q1[" + code(i) + "]", item.get("Q1_" + code(i)))
                if ticked in ("Y", "y", "Yes", 1, "1"):
                    counts[i] += 1
            elif item.get("Q1") == code(i):
                counts[i] += 1
    return counts


class LimeSurvey:
    INFO = {
        "id": "limesurvey",
        "name": "LimeSurvey",
        "account": "limesurvey",
        "server": True,
        "user": True,
        "browser": False,
        "deadline": True,
        "close": True,
        "secret": "app_password",
        "help": _("Type your LimeSurvey user name and password on the plugin's settings page. The server's admin must turn on the JSON-RPC interface under **Configuration › Global settings › Interfaces**."),
    }

    @staticmethod
    def explain(status, said):
        if status == 404:
            return _("No LimeSurvey answers at this address. Type the address you open LimeSurvey at, such as https://survey.example.com.")
        return ""

    @staticmethod
    def check(acct):
        return signed(acct, [])

    @staticmethod
    def logout(acct):
        return []

    @staticmethod
    def create(acct, poll):
        lsq = base64.b64encode(question_file(poll).encode("utf-8")).decode("utf-8")
        props = {"showwelcome": "N", "showxquestions": "N", "showprogress": "N", "allowprev": "N"}
        if poll["deadline"]:
            props["expires"] = stamp(poll["deadline"])

        def made(ctx, result):
            ctx["sid"] = int(result)

        def grouped(ctx, result):
            ctx["gid"] = int(result)

        def done(ctx, result):
            ctx["url"] = acct["base"] + "/index.php/" + str(ctx["sid"]) + "?lang=" + LANGUAGE
            ctx["remote"] = {"sid": ctx["sid"]}

        return signed(acct, [
            lambda ctx: rpc(acct, "add_survey", [ctx["key"], random.randint(100000, 999999), poll["question"], LANGUAGE, "A"], take=made),
            lambda ctx: rpc(acct, "add_group", [ctx["key"], ctx["sid"], poll["question"], ""], take=grouped),
            lambda ctx: rpc(acct, "import_question", [ctx["key"], ctx["sid"], ctx["gid"], lsq, "lsq", "Y"]),
            lambda ctx: rpc(acct, "set_survey_properties", [ctx["key"], ctx["sid"], props]),
            lambda ctx: rpc(acct, "activate_survey", [ctx["key"], ctx["sid"], {"anonymized": "Y"}], take=done),
        ])

    @staticmethod
    def results(acct, record):
        sid = record["remote"]["sid"]

        def state(ctx, result):
            result = result or {}
            ends = unstamp(result.get("expires"))
            ctx["closed"] = result.get("active") != "Y" or (ends is not None and ends <= time.time())

        def answers(ctx, result):
            rows = []
            if isinstance(result, str):
                body = json.loads(base64.b64decode(result).decode("utf-8"))
                rows = body.get("responses", []) if isinstance(body, dict) else []
            ctx["counts"] = tally(rows, record)
            ctx["responses"] = len(rows)

        def read(ctx):
            request = rpc(acct, "export_responses", [ctx["key"], sid, "json", LANGUAGE, "complete", "code", "short"], take=answers)
            first = request["take"]

            def lenient(c, r):
                # No answers yet comes back as a status, not an empty list.
                try:
                    body = r.json()
                except ValueError:
                    body = None
                result = body.get("result") if isinstance(body, dict) else None
                if isinstance(result, dict) and str(result.get("status", "")).startswith("No"):
                    c["counts"] = [0 for _o in record["options"]]
                    c["responses"] = 0
                    return
                first(c, r)
            request["take"] = lenient
            return request

        return signed(acct, [
            lambda ctx: rpc(acct, "get_survey_properties", [ctx["key"], sid, ["active", "expires"]], take=state),
            read,
        ])

    @staticmethod
    def close(acct, record):
        # A day back, so it has passed in any time zone the server keeps.
        props = {"expires": stamp(time.time() - 24 * 3600)}
        return signed(acct, [lambda ctx: rpc(acct, "set_survey_properties", [ctx["key"], record["remote"]["sid"], props])])

    @staticmethod
    def delete(acct, record):
        return signed(acct, [lambda ctx: rpc(acct, "delete_survey", [ctx["key"], record["remote"]["sid"]])])
