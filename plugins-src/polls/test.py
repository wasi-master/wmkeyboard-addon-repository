# Tests for Polls, run by tools/test_plugins.py under wm-python-cli. Every
# server is a mock: each test answers the addresses the plugin should call,
# then checks what it sent and what the panel shows.

import json

BASE = "https://cloud.example.com"
FORMS = BASE + "/ocs/v2.php/apps/forms/api/v3/forms"
POLLS = BASE + "/ocs/v2.php/apps/polls/api/v1.0"


def ocs(data, status=200):
    return {"status": status, "text": json.dumps({"ocs": {"meta": {"status": "ok"}, "data": data}}), "headers": {}}


def reply(body, status=200):
    return {"status": status, "text": json.dumps(body), "headers": {}}


# A secret row reads as a marker in the session's settings; its value comes
# from secrets under the setting's key.
SECRET = {"$secret": True}


def secret(name, value):
    return [{"when": {"name": name}, "reply": value}, {"reply": None}]


def signed_in(password="app-pass"):
    return secret("app_password", password)


def walk(node, out):
    if isinstance(node, dict):
        out.append(node)
        for value in node.values():
            walk(value, out)
    elif isinstance(node, list):
        for value in node:
            walk(value, out)
    return out


def widgets(r, kind=None):
    found = walk(r["ui"], [])
    return [w for w in found if "type" in w and (kind is None or w["type"] == kind)]


def texts(r):
    out = []
    for w in widgets(r):
        for k in ("text", "title", "label", "subtitle", "action"):
            if isinstance(w.get(k), str):
                out.append(w[k])
    return " | ".join(out)


def requests(s, method=None):
    out = []
    for c in s["calls"]():
        if c["op"] == "http.request" and (method is None or c["args"]["method"] == method):
            out.append(c["args"])
    return out


def ok(r, what):
    assert r["ok"], what + ": " + json.dumps(r.get("error"))


def fill(s, question, options, multi=False):
    s["event"]({"type": "change", "id": "question", "value": question})
    while len(options) > 2 and len([w for w in widgets(s["render"](), "input") if str(w.get("id", "")).startswith("option")]) < len(options):
        s["event"]({"type": "click", "id": "add_option"})
    for i, text in enumerate(options):
        s["event"]({"type": "change", "id": "option" + str(i), "value": text})
    if multi:
        s["event"]({"type": "change", "id": "multi", "value": "many"})


# MARK: - setup

# No server yet: the panel says where to type it, and the button opens the
# plugin's settings page.
s = plugin_test.session(mock={"secrets.get": None, "plugin.open_settings": None}, settings={"service": "nextcloud_forms", "server": ""})
r = s["load"]()
ok(r, "load without a server")
assert "Type the address of your Nextcloud Forms server" in texts(r), texts(r)
r = s["event"]({"type": "click", "id": widgets(r, "empty")[0]["id"]})
ok(r, "open settings")
assert "plugin.open_settings" in [c["op"] for c in s["calls"]()], s["calls"]()

# A server, no sign-in: the browser sign-in comes first.
mock = {
    "secrets.get": None,
    "secrets.set": None,
    "ui.toast": None,
    "share.open": None,
    "http.request": [
        {"when": {"method": "POST", "url": BASE + "/index.php/login/v2"},
         "reply": reply({"poll": {"token": "tok", "endpoint": BASE + "/index.php/login/v2/poll"}, "login": BASE + "/index.php/login/v2/flow/abc"})},
        {"when": {"method": "POST", "url": BASE + "/index.php/login/v2/poll"},
         "reply": reply({"server": BASE, "loginName": "alice", "appPassword": "app-pass"})},
    ],
}
s = plugin_test.session(mock=mock, settings={"service": "nextcloud_forms", "server": "cloud.example.com", "user": "", "app_password": SECRET})
r = s["load"]()
ok(r, "load signed out")
assert "Sign in to Nextcloud Forms" in texts(r), texts(r)
s["event"]({"type": "click", "id": "browser"})
r = s["settle"]()
ok(r, "login flow start")
opened = [c["args"]["url"] for c in s["calls"]() if c["op"] == "share.open"]
assert opened == [BASE + "/index.php/login/v2/flow/abc"], opened
assert "Finish signing in in the browser" in texts(r), texts(r)
s["event"]({"type": "click", "id": "signed_in"})
r = s["settle"]()
ok(r, "login flow poll")
polled = requests(s)[-1]
assert polled["url"] == BASE + "/index.php/login/v2/poll", polled
assert "tok" in json.dumps(polled), polled
saved = [c["args"] for c in s["calls"]() if c["op"] == "settings.set"]
assert saved == [{"key": "user", "value": "alice"}, {"key": "app_password", "value": "app-pass"}], saved

# Not finished in the browser yet: 404, and the panel says so.
mock["http.request"][1] = {"when": {"method": "POST", "url": BASE + "/index.php/login/v2/poll"}, "reply": reply({}, 404)}
s = plugin_test.session(mock=mock, settings={"service": "nextcloud_forms", "server": "cloud.example.com", "user": "", "app_password": SECRET})
s["load"]()
s["event"]({"type": "click", "id": "browser"})
s["settle"]()
s["event"]({"type": "click", "id": "signed_in"})
r = s["settle"]()
assert "Not signed in yet" in texts(r), texts(r)

# A password typed on the settings page is tried at once, so a wrong one is
# said in the panel before the first poll.
mock = {
    "secrets.get": secret("app_password", "xxxx-yyyy"),
    "ui.toast": None,
    "http.request": [
        {"when": {"method": "GET", "url": BASE + "/ocs/v2.php/cloud/user"}, "reply": ocs({"id": "bob"})},
    ],
}
nc = {"service": "nextcloud_forms", "server": "https://cloud.example.com/", "user": "bob", "app_password": SECRET}
s = plugin_test.session(mock=mock, settings=nc)
r = s["load"]()
assert "Make the poll" in texts(r), texts(r)
s["event"]({"type": "setting", "key": "app_password", "value": SECRET})
r = s["settle"]()
ok(r, "password typed in settings")
sent = requests(s)[-1]
assert sent["url"] == BASE + "/ocs/v2.php/cloud/user", sent
assert sent["headers"]["Authorization"] == "Basic Ym9iOnh4eHgteXl5eQ==", sent["headers"]
assert sent["headers"]["OCS-APIRequest"] == "true", sent["headers"]
assert [c["args"]["text"] for c in s["calls"]() if c["op"] == "ui.toast"] == ["Signed in to Nextcloud Forms"]

mock["http.request"] = [{"when": {"url": BASE + "/ocs/v2.php/cloud/user"}, "reply": ocs(None, 401)}]
s = plugin_test.session(mock=mock, settings=nc)
s["load"]()
s["event"]({"type": "setting", "key": "app_password", "value": SECRET})
r = s["settle"]()
assert "turned down the sign-in" in texts(r), texts(r)

# No password yet: the panel has no password box of its own, it sends the
# user to the settings page.
s = plugin_test.session(mock={"secrets.get": None, "plugin.open_settings": None},
                        settings={"service": "nextcloud_forms", "server": "cloud.example.com", "user": "bob", "app_password": SECRET})
r = s["load"]()
assert not widgets(r, "input"), widgets(r, "input")
s["event"]({"type": "click", "id": "settings"})
assert "plugin.open_settings" in [c["op"] for c in s["calls"]()]

# Sign out revokes the app password on the server and forgets it.
mock = {"secrets.get": signed_in(), "http.request": [
    {"when": {"method": "DELETE", "url": BASE + "/ocs/v2.php/core/apppassword"}, "reply": ocs([])}]}
s = plugin_test.session(mock=mock, settings=nc)
s["load"]()
s["event"]({"type": "command", "id": "show_account"})
s["event"]({"type": "click", "id": "sign_out"})
s["settle"]()
assert requests(s, "DELETE")[-1]["url"] == BASE + "/ocs/v2.php/core/apppassword"
assert {"key": "app_password", "value": None} in [c["args"] for c in s["calls"]() if c["op"] == "settings.set"]


# MARK: - Nextcloud Forms

forms_mock = {
    "secrets.get": signed_in(),
    "ui.toast": None,
    "ui.dialog": [
        {"when": {"title": "Close this poll?"}, "reply": "Close poll"},
        {"when": {"title": "Remove this poll?"}, "reply": "Delete on the server"},
    ],
    "http.request": [
        {"when": {"method": "POST", "url": FORMS}, "reply": ocs({"id": 7, "hash": "h", "title": ""})},
        {"when": {"method": "PATCH", "url": FORMS + "/7"}, "reply": ocs(7)},
        {"when": {"method": "POST", "url": FORMS + "/7/questions"}, "reply": ocs({"id": 70, "type": "multiple_unique"})},
        {"when": {"method": "PATCH", "url": FORMS + "/7/questions/70"}, "reply": ocs(70)},
        {"when": {"method": "POST", "url": FORMS + "/7/questions/70/options"},
         "reply": ocs([{"id": 1, "text": "Pizza"}, {"id": 2, "text": "Sushi"}, {"id": 3, "text": "Tacos"}])},
        {"when": {"method": "POST", "url": FORMS + "/7/shares"}, "reply": ocs({"id": 9, "shareType": 3, "shareWith": "AbCdEf"})},
        {"when": {"method": "GET", "url": FORMS + "/7"}, "reply": ocs({"id": 7, "state": 0, "expires": 0})},
        {"when": {"method": "GET", "url": FORMS + "/7/submissions"}, "reply": ocs({"submissions": [
            {"id": 1, "answers": [{"questionId": 70, "text": "Pizza"}]},
            {"id": 2, "answers": [{"questionId": 70, "text": "Sushi"}]},
            {"id": 3, "answers": [{"questionId": 70, "text": "Pizza"}, {"questionId": 99, "text": "other"}]},
        ]})},
        {"when": {"method": "DELETE", "url": FORMS + "/7"}, "reply": ocs(7)},
    ],
}
settings = {"service": "nextcloud_forms", "server": "cloud.example.com", "user": "alice", "app_password": SECRET}
s = plugin_test.session(mock=forms_mock, settings=settings)
r = s["load"]()
ok(r, "forms load")
assert "Question" in texts(r) and "Make the poll" in texts(r), texts(r)
make = [w for w in widgets(r, "button") if w.get("text") == "Make the poll"][0]
assert make["enabled"] is False, make

fill(s, "Lunch?", ["Pizza", "Sushi", "Tacos"])
r = s["event"]({"type": "click", "id": "make"})
ok(r, "forms create click")
r = s["settle"]()
ok(r, "forms create")
sent = requests(s)
assert [(q["method"], q["url"]) for q in sent] == [
    ("POST", FORMS), ("PATCH", FORMS + "/7"), ("POST", FORMS + "/7/questions"),
    ("PATCH", FORMS + "/7/questions/70"), ("POST", FORMS + "/7/questions/70/options"), ("POST", FORMS + "/7/shares"),
], sent
assert json.loads(sent[1]["body"]) == {"keyValuePairs": {"title": "Lunch?", "isAnonymous": True, "submitMultiple": False}}, sent[1]
assert json.loads(sent[2]["body"]) == {"type": "multiple_unique", "text": "Lunch?"}, sent[2]
assert json.loads(sent[4]["body"]) == {"optionTexts": ["Pizza", "Sushi", "Tacos"]}, sent[4]
assert json.loads(sent[5]["body"]) == {"shareType": 3, "permissions": ["submit"]}, sent[5]
link = BASE + "/index.php/apps/forms/s/AbCdEf"
outputs = widgets(r, "output")
assert outputs and outputs[0]["text"] == "Lunch?\n" + link, outputs
saved_polls = json.loads(s["storage"]()["__state__:polls"])["polls"]
assert saved_polls[0]["remote"] == {"form": 7, "question": 70}, saved_polls
assert saved_polls[0]["url"] == link

# Answers: two for Pizza, one for Sushi; the other question's answer is not counted.
r = s["event"]({"type": "click", "id": "answers"})
r = s["settle"]()
ok(r, "forms results")
assert r["host"]["canBack"], r["host"]
chart = widgets(r, "chart")[0]
assert chart["series"][0]["values"] == [2.0, 1.0, 0.0], chart
assert "3 answers" in texts(r), texts(r)
assert "Pizza  —  2 votes (67%)" in texts(r), texts(r)

# Closing sets the form's state to closed.
s["event"]({"type": "click", "id": "close"})
r = s["settle"]()
ok(r, "forms close")
patch = requests(s, "PATCH")[-1]
assert patch["url"] == FORMS + "/7" and json.loads(patch["body"]) == {"keyValuePairs": {"state": 1}}, patch
assert "closed" in texts(r), texts(r)
assert not [w for w in widgets(r, "button") if w.get("text") == "Close poll"]

# Deleting on the server removes it from the list too.
s["event"]({"type": "click", "id": "remove"})
r = s["settle"]()
ok(r, "forms delete")
assert requests(s, "DELETE")[-1]["url"] == FORMS + "/7"
assert json.loads(s["storage"]()["__state__:polls"])["polls"] == []

# Several answers and a closing time.
s = plugin_test.session(mock=forms_mock, settings=settings)
s["load"]()
fill(s, "Which days work?", ["Mon", "Tue"], multi=True)
s["event"]({"type": "change", "id": "closes", "value": True})
s["event"]({"type": "change", "id": "deadline", "value": 4102444800})
s["event"]({"type": "click", "id": "make"})
s["settle"]()
sent = requests(s)
assert json.loads(sent[1]["body"])["keyValuePairs"]["expires"] == 4102444800, sent[1]
assert json.loads(sent[1]["body"])["keyValuePairs"]["showExpiration"] is True, sent[1]
assert json.loads(sent[2]["body"])["type"] == "multiple", sent[2]

# A closing time in the past is caught before anything is sent.
s = plugin_test.session(mock=forms_mock, settings=settings)
s["load"]()
fill(s, "Late?", ["Yes", "No"])
s["event"]({"type": "change", "id": "closes", "value": True})
r = s["event"]({"type": "change", "id": "deadline", "value": 1000})
assert "already passed" in texts(r), texts(r)
s["event"]({"type": "click", "id": "make"})
assert requests(s) == []

# Duplicate and empty answers don't count towards the two needed.
s = plugin_test.session(mock=forms_mock, settings=settings)
s["load"]()
r = s["event"]({"type": "change", "id": "question", "value": "Same?"})
s["event"]({"type": "change", "id": "option0", "value": "Yes"})
r = s["event"]({"type": "change", "id": "option1", "value": " yes "})
assert "at least two different answers" in texts(r), texts(r)

# Forms not installed: a 404 says so.
missing = dict(forms_mock)
missing["http.request"] = [{"when": {"method": "POST", "url": FORMS}, "reply": ocs(None, 404)}]
s = plugin_test.session(mock=missing, settings=settings)
s["load"]()
fill(s, "Lunch?", ["Pizza", "Sushi"])
s["event"]({"type": "click", "id": "make"})
r = s["settle"]()
assert "Nextcloud Forms 4.3 or later isn't installed" in texts(r), texts(r)
assert json.loads(s["storage"]().get("__state__:polls", '{"polls": []}'))["polls"] == []

# Offline: the error is shown and the draft is kept.
offline = dict(forms_mock)
offline["http.request"] = {"error": {"kind": "ConnectionError", "message": "no network"}}
s = plugin_test.session(mock=offline, settings=settings)
s["load"]()
fill(s, "Lunch?", ["Pizza", "Sushi"])
s["event"]({"type": "click", "id": "make"})
r = s["settle"]()
assert "Could not reach the server" in texts(r), texts(r)
assert json.loads(s["storage"]()["__state__:draft"])["question"] == "Lunch?"


# MARK: - Nextcloud Polls

polls_mock = {
    "secrets.get": signed_in(),
    "ui.toast": None,
    "ui.dialog": [{"when": {"title": "Close this poll?"}, "reply": "Close poll"}],
    "http.request": [
        {"when": {"method": "POST", "url": POLLS + "/poll"}, "reply": ocs({"poll": {"id": 12}}, 201)},
        {"when": {"method": "PUT", "url": POLLS + "/poll/12"}, "reply": ocs({"poll": {"id": 12}})},
        {"when": {"method": "POST", "url": POLLS + "/poll/12/options"}, "reply": ocs({"options": []})},
        {"when": {"method": "POST", "url": POLLS + "/poll/12/share/public"},
         "reply": ocs({"share": {"token": "tk", "type": "public", "URL": BASE + "/index.php/apps/polls/s/tk"}}, 201)},
        {"when": {"method": "GET", "url": POLLS + "/poll/12"}, "reply": ocs({"poll": {"id": 12, "configuration": {"expire": 0}, "status": {"isExpired": False}}})},
        {"when": {"method": "GET", "url": POLLS + "/poll/12/votes"}, "reply": ocs({"votes": [
            {"optionText": "Mon", "answer": "yes", "user": {"id": "a"}},
            {"optionText": "Tue", "answer": "yes", "user": {"id": "a"}},
            {"optionText": "Tue", "answer": "yes", "user": {"id": "b"}},
            {"optionText": "Mon", "answer": "no", "user": {"id": "b"}},
        ]})},
        {"when": {"method": "PUT", "url": POLLS + "/poll/12/close"}, "reply": ocs({"poll": {"id": 12}})},
    ],
}
s = plugin_test.session(mock=polls_mock, settings={"service": "nextcloud_polls", "server": "cloud.example.com", "user": "alice", "app_password": SECRET})
ok(s["load"](), "polls load")
fill(s, "Which days?", ["Mon", "Tue"], multi=True)
s["event"]({"type": "click", "id": "make"})
r = s["settle"]()
ok(r, "polls create")
sent = requests(s)
assert json.loads(sent[0]["body"]) == {"type": "textPoll", "title": "Which days?"}, sent[0]
config = json.loads(sent[1]["body"])["pollConfiguration"]
assert config["maxVotesPerUser"] == 0 and config["allowMaybe"] is False and config["expire"] == 0, config
assert json.loads(sent[2]["body"]) == {"text": "Mon\nTue"}, sent[2]
assert widgets(r, "output")[0]["text"] == "Which days?\n" + BASE + "/index.php/apps/polls/s/tk"

s["event"]({"type": "click", "id": "answers"})
r = s["settle"]()
ok(r, "polls results")
assert widgets(r, "chart")[0]["series"][0]["values"] == [1.0, 2.0], widgets(r, "chart")
assert "2 answers" in texts(r), texts(r)
s["event"]({"type": "click", "id": "close"})
r = s["settle"]()
assert requests(s, "PUT")[-1]["url"] == POLLS + "/poll/12/close"

# One answer each: maxVotesPerUser is 1.
s = plugin_test.session(mock=polls_mock, settings={"service": "nextcloud_polls", "server": "cloud.example.com", "user": "alice", "app_password": SECRET})
s["load"]()
fill(s, "Pick one", ["Mon", "Tue"])
s["event"]({"type": "click", "id": "make"})
s["settle"]()
assert json.loads(requests(s)[1]["body"])["pollConfiguration"]["maxVotesPerUser"] == 1


# MARK: - LimeSurvey

LS = "https://survey.example.com/ls"
RPC = LS + "/index.php/admin/remotecontrol"


def rpc_route(method, result):
    return {"when": {"method": "POST", "url": RPC, "body": '{"method": "' + method + '"*'},
            "reply": reply({"id": 1, "result": result, "error": None})}


def rpc_calls(s):
    return [json.loads(q["body"]) for q in requests(s, "POST") if q["url"] == RPC]


# The test runner has no base64 module, so a small one for what the RPC carries.
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def b64(text):
    data = text.encode("utf-8")
    out = ""
    for i in range(0, len(data), 3):
        chunk = data[i:i + 3]
        n = 0
        for b in chunk:
            n = n * 256 + b
        n = n * 256 ** (3 - len(chunk))
        quad = "".join([ALPHABET[n // (64 ** k) % 64] for k in (3, 2, 1, 0)])
        out += quad[:len(chunk) + 1] + "=" * (3 - len(chunk))
    return out


def unb64(text):
    bits, count, out = 0, 0, []
    for ch in text:
        if ch == "=":
            break
        bits = bits * 64 + ALPHABET.index(ch)
        count += 6
        if count >= 8:
            count -= 8
            out.append(bits // (2 ** count) % 256)
            bits = bits % (2 ** count)
    return bytes(out).decode("utf-8")


answers_one = {"responses": [{"1": {"id": "1", "Q1": "A1"}}, {"2": {"id": "2", "Q1": "A2"}}, {"3": {"id": "3", "Q1": "A1"}}]}
ls_mock = {
    "secrets.get": secret("app_password", "pw"),
    "ui.toast": None,
    "ui.dialog": [{"when": {"title": "Close this poll?"}, "reply": "Close poll"}],
    "http.request": [
        rpc_route("get_session_key", "KEY"),
        rpc_route("add_survey", 123456),
        rpc_route("add_group", 5),
        rpc_route("import_question", 77),
        rpc_route("set_survey_properties", {"showwelcome": True}),
        rpc_route("activate_survey", {"status": "OK"}),
        rpc_route("get_survey_properties", {"active": "Y", "expires": None}),
        rpc_route("export_responses", b64(json.dumps(answers_one))),
        rpc_route("release_session_key", "OK"),
    ],
}
ls_settings = {"service": "limesurvey", "server": "survey.example.com/ls", "user": "admin", "app_password": SECRET}
s = plugin_test.session(mock=ls_mock, settings=ls_settings)
r = s["load"]()
ok(r, "limesurvey load")
fill(s, "Fish & chips?", ["Yes <please>", "No", "Maybe"])
s["event"]({"type": "click", "id": "make"})
r = s["settle"]()
ok(r, "limesurvey create")
calls = rpc_calls(s)
assert [c["method"] for c in calls] == ["get_session_key", "add_survey", "add_group", "import_question",
                                        "set_survey_properties", "activate_survey", "release_session_key"], calls
assert calls[0]["params"] == ["admin", "pw"], calls[0]
assert calls[1]["params"][0] == "KEY" and calls[1]["params"][2:] == ["Fish & chips?", "en", "A"], calls[1]
assert calls[2]["params"][:2] == ["KEY", 123456], calls[2]
assert calls[3]["params"][1:3] == [123456, 5] and calls[3]["params"][4:] == ["lsq", "Y"], calls[3]
lsq = unb64(calls[3]["params"][3])
assert "<type><![CDATA[L]]></type>" in lsq, lsq
assert "<question><![CDATA[Fish &amp; chips?]]></question>" in lsq, lsq
assert "<answer><![CDATA[Yes &lt;please&gt;]]></answer>" in lsq, lsq
assert lsq.count("<code>") == 3 and "<subquestions>" not in lsq, lsq
assert calls[4]["params"][2] == {"showwelcome": "N", "showxquestions": "N", "showprogress": "N", "allowprev": "N"}, calls[4]
assert widgets(r, "output")[0]["text"] == "Fish & chips?\n" + LS + "/index.php/123456?lang=en"
assert json.loads(s["storage"]()["__state__:polls"])["polls"][0]["remote"] == {"sid": 123456}

s["event"]({"type": "click", "id": "answers"})
r = s["settle"]()
ok(r, "limesurvey results")
assert widgets(r, "chart")[0]["series"][0]["values"] == [2.0, 1.0, 0.0], widgets(r, "chart")
calls = rpc_calls(s)
export = [c for c in calls if c["method"] == "export_responses"][-1]
assert export["params"][1:] == [123456, "json", "en", "complete", "code", "short"], export

s["event"]({"type": "click", "id": "close"})
r = s["settle"]()
ok(r, "limesurvey close")
closing = [c for c in rpc_calls(s) if c["method"] == "set_survey_properties"][-1]
assert list(closing["params"][2].keys()) == ["expires"], closing
assert "closed" in texts(r), texts(r)

# Several answers: type M, one subquestion per answer, ticked ones read "Y".
answers_many = {"responses": [{"id": "1", "Q1[A1]": "Y", "Q1[A2]": "Y"}, {"id": "2", "Q1[A1]": "", "Q1[A2]": "Y"}]}
many = dict(ls_mock)
many["http.request"] = [rpc_route("export_responses", b64(json.dumps(answers_many)))] + ls_mock["http.request"]
s = plugin_test.session(mock=many, settings=ls_settings)
s["load"]()
fill(s, "Which days?", ["Mon", "Tue"], multi=True)
s["event"]({"type": "change", "id": "closes", "value": True})
s["event"]({"type": "change", "id": "deadline", "value": 4102444800})
s["event"]({"type": "click", "id": "make"})
s["settle"]()
calls = rpc_calls(s)
lsq = unb64([c for c in calls if c["method"] == "import_question"][0]["params"][3])
assert "<type><![CDATA[M]]></type>" in lsq and "<subquestions>" in lsq and "<answers>" not in lsq, lsq
assert "<title><![CDATA[A2]]></title>" in lsq, lsq
props = [c for c in calls if c["method"] == "set_survey_properties"][0]["params"][2]
assert props["expires"].startswith("2100-01-01") or props["expires"].startswith("2099-12-31"), props
s["event"]({"type": "click", "id": "answers"})
r = s["settle"]()
assert widgets(r, "chart")[0]["series"][0]["values"] == [1.0, 2.0], widgets(r, "chart")
assert "2 answers" in texts(r), texts(r)

# No answers yet: LimeSurvey answers with a status, which counts as none.
empty = dict(ls_mock)
empty["http.request"] = [rpc_route("export_responses", {"status": "No Data, could not get max id.", "error_code": 9})] + ls_mock["http.request"]
s = plugin_test.session(mock=empty, settings=ls_settings)
s["load"]()
fill(s, "Anyone?", ["Yes", "No"])
s["event"]({"type": "click", "id": "make"})
s["settle"]()
s["event"]({"type": "click", "id": "answers"})
r = s["settle"]()
ok(r, "limesurvey no answers")
assert "0 answers" in texts(r) and "LimeSurvey said" not in texts(r), texts(r)

# The JSON-RPC interface switched off: LimeSurvey answers a web page.
off = dict(ls_mock)
off["http.request"] = [{"when": {"url": RPC}, "reply": {"status": 200, "text": "<html>Not found</html>", "headers": {}}}]
s = plugin_test.session(mock=off, settings=ls_settings)
s["load"]()
fill(s, "Lunch?", ["Pizza", "Sushi"])
s["event"]({"type": "click", "id": "make"})
r = s["settle"]()
assert "JSON-RPC interface is off" in texts(r), texts(r)

# A wrong password, typed on the settings page.
wrong = {"secrets.get": secret("app_password", "nope"), "ui.toast": None,
         "http.request": [rpc_route("get_session_key", {"status": "Invalid user name or password", "error_code": 1})]}
s = plugin_test.session(mock=wrong, settings=ls_settings)
s["load"]()
s["event"]({"type": "setting", "key": "app_password", "value": SECRET})
r = s["settle"]()
assert "turned down the user name or password" in texts(r), texts(r)

# Not signed in: no browser sign-in for LimeSurvey, only the settings page.
s = plugin_test.session(mock={"secrets.get": None}, settings={"service": "limesurvey", "server": "survey.example.com/ls"})
r = s["load"]()
ids = [w.get("id") for w in widgets(r, "button")]
assert "Sign in to LimeSurvey" in texts(r) and "browser" not in ids and "settings" in ids, texts(r)


# MARK: - StrawPoll

SP = "https://api.strawpoll.com/v4"
form = {"id": "u-1", "slug": "NPgxkzPqrn2", "urls": {"formUrl": "https://strawpoll.com/r/NPgxkzPqrn2"}}
read_form = {"slug": "NPgxkzPqrn2", "isOpen": True, "responseCount": 5, "sections": [{"fields": [{"choices": [
    {"label": "Tea", "responseCount": 3}, {"label": "Coffee", "responseCount": 2}]}]}]}
sp_mock = {
    "secrets.get": secret("api_key", "sp_key"),
    "secrets.set": None,
    "ui.toast": None,
    "ui.dialog": [{"when": {"title": "Close this poll?"}, "reply": "Close poll"}],
    "http.request": [
        {"when": {"method": "POST", "url": SP + "/forms"}, "reply": reply(form)},
        {"when": {"method": "GET", "url": SP + "/forms/NPgxkzPqrn2"}, "reply": reply(read_form)},
        {"when": {"method": "PATCH", "url": SP + "/forms/NPgxkzPqrn2"}, "reply": reply(read_form)},
        {"when": {"method": "GET", "url": SP + "/me"}, "reply": reply({"id": "me"})},
    ],
}
s = plugin_test.session(mock=sp_mock, settings={"service": "strawpoll", "server": "", "api_key": SECRET})
r = s["load"]()
ok(r, "strawpoll load")
assert "Make the poll" in texts(r), texts(r)
fill(s, "Tea or coffee?", ["Tea", "Coffee"])
s["event"]({"type": "change", "id": "closes", "value": True})
s["event"]({"type": "change", "id": "deadline", "value": 4102444800})
s["event"]({"type": "click", "id": "make"})
r = s["settle"]()
ok(r, "strawpoll create")
sent = requests(s)[0]
assert sent["headers"]["X-API-Key"] == "sp_key", sent["headers"]
body = json.loads(sent["body"])
assert body["status"] == "published" and body["properties"] == {"closesAt": "2100-01-01T00:00:00Z"}, body
field = body["sections"][0]["fields"][0]
assert field["choices"] == [{"label": "Tea"}, {"label": "Coffee"}] and field["properties"] == {"isMultipleChoice": False}, field
assert widgets(r, "output")[0]["text"] == "Tea or coffee?\nhttps://strawpoll.com/r/NPgxkzPqrn2"
s["event"]({"type": "click", "id": "answers"})
r = s["settle"]()
assert widgets(r, "chart")[0]["series"][0]["values"] == [3.0, 2.0], widgets(r, "chart")
assert "5 answers" in texts(r), texts(r)
s["event"]({"type": "click", "id": "close"})
r = s["settle"]()
patch = requests(s, "PATCH")[-1]
assert json.loads(patch["body"]) == {"isOpen": False}, patch

# No key yet: no server needed, the card points at the settings page.
s = plugin_test.session(mock={"secrets.get": None}, settings={"service": "strawpoll", "server": "", "api_key": SECRET})
r = s["load"]()
assert "Sign in to StrawPoll" in texts(r) and "Type the address" not in texts(r), texts(r)

# A refused key says so.
s = plugin_test.session(mock={"secrets.get": secret("api_key", "sp_bad"), "ui.toast": None,
                              "http.request": [{"when": {"url": SP + "/me"}, "reply": reply({"message": "Unauthorized"}, 401)}]},
                        settings={"service": "strawpoll", "server": "", "api_key": SECRET})
s["load"]()
s["event"]({"type": "setting", "key": "api_key", "value": SECRET})
r = s["settle"]()
assert "StrawPoll turned down the API key" in texts(r), texts(r)


# MARK: - keyword

s = plugin_test.session(mock=forms_mock, settings=settings)
s["load"]()
r = s["event"]({"type": "keyword", "id": "poll", "value": "Where shall we eat? Pizza, Sushi, Tacos"})
ok(r, "keyword")
draft = json.loads(s["storage"]()["__state__:draft"])
assert draft["question"] == "Where shall we eat?", draft
assert draft["options"] == ["Pizza", "Sushi", "Tacos"], draft
s["event"]({"type": "keyword", "id": "poll", "value": "Tea or coffee: tea or coffee"})
draft = json.loads(s["storage"]()["__state__:draft"])
assert draft["question"] == "Tea or coffee" and draft["options"] == ["tea", "coffee"], draft

print("polls: all checks passed")
