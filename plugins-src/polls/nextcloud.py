# Nextcloud: Forms (API v3, Forms 4.3 and later) and Polls (its OCS API,
# Polls 8 and later), signed in with an app password, which Login Flow v2 can
# hand over from the browser.
#
# Both apps answer under /ocs/v2.php with the OCS envelope, {"ocs": {"meta",
# "data"}}, and need the OCS-APIRequest header or they refuse the request as a
# cross-site one.

import base64
from wm import _

HEADERS = {"OCS-APIRequest": "true", "Accept": "application/json"}


def headers(acct):
    pair = (acct["user"] + ":" + acct["password"]).encode("utf-8")
    out = dict(HEADERS)
    out["Authorization"] = "Basic " + base64.b64encode(pair).decode("utf-8")
    return out


def data(r):
    body = r.json()
    if isinstance(body, dict) and isinstance(body.get("ocs"), dict):
        return body["ocs"].get("data")
    return body


def request(acct, method, path, json=None, take=None, ok=()):
    out = {"method": method, "url": acct["base"] + path, "headers": headers(acct), "take": take, "ok": ok}
    if json is not None:
        out["json"] = json
    return out


HELP = _("In Nextcloud, open **Personal settings › Security**, make a new app password under **Devices & sessions**, and type your login name and that password here.")


# MARK: - signing in (shared by both apps)

def login_start(base):
    """Login Flow v2: ask for a sign-in page and a token to poll with."""
    def take(ctx, r):
        body = r.json()
        ctx["login"] = body["login"]
        ctx["token"] = body["poll"]["token"]
        ctx["endpoint"] = body["poll"]["endpoint"]
    return [lambda ctx: {"method": "POST", "url": base + "/index.php/login/v2", "take": take}]


def login_poll(endpoint, token):
    """Not finished yet answers 404; finished hands over the app password once."""
    def take(ctx, r):
        if r.status_code == 200:
            body = r.json()
            ctx["user"] = body.get("loginName", "")
            ctx["password"] = body.get("appPassword", "")
    return [lambda ctx: {"method": "POST", "url": endpoint, "data": {"token": token}, "take": take, "ok": (404,)}]


def check(acct):
    """Who the app password belongs to: fails with 401 when it is wrong."""
    def take(ctx, r):
        info = data(r) or {}
        ctx["user"] = info.get("id", acct["user"])
    return [lambda ctx: request(acct, "GET", "/ocs/v2.php/cloud/user", take=take)]


def logout(acct):
    """Revoke the app password on the server, so it stops working there too."""
    return [lambda ctx: request(acct, "DELETE", "/ocs/v2.php/core/apppassword", ok=(401, 403, 404))]


def explain(status, said):
    if status == 412:
        return _("The server refused the request as cross-site. Is this really a Nextcloud address?")
    return ""


# MARK: - Forms

class Forms:
    INFO = {
        "id": "nextcloud_forms",
        "name": "Nextcloud Forms",
        "account": "nextcloud",
        "server": True,
        "user": True,
        "browser": True,
        "deadline": True,
        "close": True,
        "help": HELP,
    }

    API = "/ocs/v2.php/apps/forms/api/v3/forms"

    @staticmethod
    def explain(status, said):
        if status == 404:
            return _("Nextcloud Forms 4.3 or later isn't installed on this server.")
        if status == 403 and said:
            return _("Nextcloud said no: {what}", what=said)
        return explain(status, said)

    login_start = staticmethod(login_start)
    login_poll = staticmethod(login_poll)
    check = staticmethod(check)
    logout = staticmethod(logout)

    @staticmethod
    def create(acct, poll):
        api = Forms.API
        settings = {
            "title": poll["question"],
            "isAnonymous": True,
            "submitMultiple": False,
        }
        if poll["deadline"]:
            settings["expires"] = poll["deadline"]
            settings["showExpiration"] = True

        def made(ctx, r):
            ctx["form"] = data(r)["id"]

        def asked(ctx, r):
            ctx["question"] = data(r)["id"]

        def options(ctx, r):
            ctx["options"] = [o["id"] for o in data(r)]

        def shared(ctx, r):
            token = data(r)["shareWith"]
            ctx["url"] = acct["base"] + "/index.php/apps/forms/s/" + token
            ctx["remote"] = {"form": ctx["form"], "question": ctx["question"]}

        return [
            lambda ctx: request(acct, "POST", api, take=made),
            lambda ctx: request(acct, "PATCH", api + "/" + str(ctx["form"]), json={"keyValuePairs": settings}),
            lambda ctx: request(acct, "POST", api + "/" + str(ctx["form"]) + "/questions",
                                json={"type": "multiple" if poll["multi"] else "multiple_unique", "text": poll["question"]},
                                take=asked),
            lambda ctx: request(acct, "PATCH", api + "/" + str(ctx["form"]) + "/questions/" + str(ctx["question"]),
                                json={"keyValuePairs": {"isRequired": True}}),
            lambda ctx: request(acct, "POST", api + "/" + str(ctx["form"]) + "/questions/" + str(ctx["question"]) + "/options",
                                json={"optionTexts": poll["options"]}, take=options),
            lambda ctx: request(acct, "POST", api + "/" + str(ctx["form"]) + "/shares",
                                json={"shareType": 3, "permissions": ["submit"]}, take=shared),
        ]

    @staticmethod
    def results(acct, record):
        import time
        form = str(record["remote"]["form"])
        question = record["remote"]["question"]

        def state(ctx, r):
            info = data(r) or {}
            expires = info.get("expires") or 0
            ctx["closed"] = info.get("state", 0) != 0 or (expires > 0 and expires <= time.time())

        def answers(ctx, r):
            body = data(r) or {}
            submissions = body.get("submissions", [])
            counts = [0 for _o in record["options"]]
            for submission in submissions:
                for answer in submission.get("answers", []):
                    if answer.get("questionId") != question:
                        continue
                    text = answer.get("text", "")
                    if text in record["options"]:
                        counts[record["options"].index(text)] += 1
            ctx["counts"] = counts
            ctx["responses"] = len(submissions)

        return [
            lambda ctx: request(acct, "GET", Forms.API + "/" + form, take=state),
            lambda ctx: request(acct, "GET", Forms.API + "/" + form + "/submissions", take=answers),
        ]

    @staticmethod
    def close(acct, record):
        form = str(record["remote"]["form"])
        return [lambda ctx: request(acct, "PATCH", Forms.API + "/" + form, json={"keyValuePairs": {"state": 1}})]

    @staticmethod
    def delete(acct, record):
        form = str(record["remote"]["form"])
        return [lambda ctx: request(acct, "DELETE", Forms.API + "/" + form, ok=(404,))]


# MARK: - Polls

class Polls:
    INFO = {
        "id": "nextcloud_polls",
        "name": "Nextcloud Polls",
        "account": "nextcloud",
        "server": True,
        "user": True,
        "browser": True,
        "deadline": True,
        "close": True,
        "help": HELP,
    }

    API = "/ocs/v2.php/apps/polls/api/v1.0"

    @staticmethod
    def explain(status, said):
        if status == 404:
            return _("Nextcloud Polls 8 or later isn't installed on this server.")
        if status == 403 and said:
            return _("Nextcloud said no: {what}", what=said)
        return explain(status, said)

    login_start = staticmethod(login_start)
    login_poll = staticmethod(login_poll)
    check = staticmethod(check)
    logout = staticmethod(logout)

    @staticmethod
    def create(acct, poll):
        api = Polls.API
        config = {
            "title": poll["question"],
            "access": "private",
            "allowMaybe": False,
            "useNo": False,
            "anonymous": True,
            "showResults": "always",
            "maxVotesPerUser": 0 if poll["multi"] else 1,
            "expire": poll["deadline"] or 0,
        }

        def made(ctx, r):
            body = data(r) or {}
            ctx["poll"] = (body.get("poll") or body)["id"]

        def shared(ctx, r):
            body = data(r) or {}
            share = body.get("share") or body
            ctx["url"] = share.get("URL") or (acct["base"] + "/index.php/apps/polls/s/" + share["token"])
            ctx["remote"] = {"poll": ctx["poll"]}

        return [
            lambda ctx: request(acct, "POST", api + "/poll", json={"type": "textPoll", "title": poll["question"]}, take=made),
            lambda ctx: request(acct, "PUT", api + "/poll/" + str(ctx["poll"]), json={"pollConfiguration": config}),
            lambda ctx: request(acct, "POST", api + "/poll/" + str(ctx["poll"]) + "/options",
                                json={"text": "\n".join(poll["options"])}),
            lambda ctx: request(acct, "POST", api + "/poll/" + str(ctx["poll"]) + "/share/public", json={}, take=shared),
        ]

    @staticmethod
    def results(acct, record):
        import time
        poll_id = str(record["remote"]["poll"])

        def state(ctx, r):
            body = data(r) or {}
            info = body.get("poll") or body
            config = info.get("configuration") or info
            status = info.get("status") or {}
            expire = config.get("expire") or 0
            ctx["closed"] = bool(status.get("isExpired")) or (expire > 0 and expire <= time.time())

        def votes(ctx, r):
            body = data(r) or {}
            counts = [0 for _o in record["options"]]
            voters = []
            for vote in body.get("votes", []):
                if vote.get("answer") != "yes":
                    continue
                text = vote.get("optionText", "")
                if text in record["options"]:
                    counts[record["options"].index(text)] += 1
                who = vote.get("user")
                who = who.get("id") if isinstance(who, dict) else who
                if who not in voters:
                    voters.append(who)
            ctx["counts"] = counts
            ctx["responses"] = len(voters)

        return [
            lambda ctx: request(acct, "GET", Polls.API + "/poll/" + poll_id, take=state),
            lambda ctx: request(acct, "GET", Polls.API + "/poll/" + poll_id + "/votes", take=votes),
        ]

    @staticmethod
    def close(acct, record):
        return [lambda ctx: request(acct, "PUT", Polls.API + "/poll/" + str(record["remote"]["poll"]) + "/close")]

    @staticmethod
    def delete(acct, record):
        return [lambda ctx: request(acct, "DELETE", Polls.API + "/poll/" + str(record["remote"]["poll"]), ok=(404,))]
