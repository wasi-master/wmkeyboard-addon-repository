# Talking to a Grocy server: where it is, the key, and turning its answers
# and errors into something the panel can show.
#
# Every call is made with then=, so the panel never freezes while the server
# answers. A call gives its result to `ok`, or a sentence for the user to
# `fail`.

from wm import http, plugin, secrets

KEY_NAME = "api_key"
# The key, read from secrets once a session.
_key = [None]
# Grocy's own answer header; a server that sends HTML instead is not Grocy.
JSON_TYPES = ("application/json", "text/json")


def base_url():
    """The server's address as the user typed it, made into the start of an
    https:// (or http:// for a local server) URL with no trailing slash and
    no /api. Empty when the user has not set one."""
    raw = str(plugin.settings.get("server", "") or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    if not (low.startswith("https://") or low.startswith("http://")):
        raw = "https://" + raw
    raw = raw.rstrip("/")
    if raw.lower().endswith("/api"):
        raw = raw[:-4]
    return raw


def api_key():
    if _key[0] is None:
        _key[0] = secrets.get(KEY_NAME, "") or ""
    return _key[0]


def forget_key():
    """Read the key from secrets again: the user changed it on the settings page."""
    _key[0] = None


def save_key(text):
    text = str(text or "").strip()
    if text:
        secrets.set(KEY_NAME, text)
    else:
        secrets.remove(KEY_NAME)
    _key[0] = text


def ready():
    return bool(base_url()) and bool(api_key())


def message_of(r):
    """What a failed answer says, in one line."""
    detail = ""
    try:
        body = r.json()
        if isinstance(body, dict):
            detail = str(body.get("error_message") or body.get("message") or "")
    except Exception:
        detail = ""
    if r.status_code == 401:
        return "Grocy refused the API key. Check it under Manage API keys."
    if r.status_code == 404 and not detail:
        return "Grocy has no " + (r.url or "such address") + ". Is the server address right?"
    if detail:
        # Grocy puts the whole PHP exception text in; the first line is enough.
        return detail.splitlines()[0][:200]
    return f"Grocy answered {r.status_code} {r.reason}".strip()


def failure_text(e):
    if isinstance(e, PermissionError):
        text = str(e)
        if "network.local" in text:
            return "Allow local network access for this plugin to reach a server at home."
        return "Allow internet access for this plugin on its page, then try again."
    if isinstance(e, TimeoutError):
        return "Grocy did not answer in time."
    if isinstance(e, ConnectionError):
        return "Could not reach Grocy: " + str(e)
    return str(e)


def call(method, path, ok, fail, json=None, params=None, on_status=None):
    """[method] /api[path] on the user's server. [ok] gets the answer's JSON
    (None for an empty answer), [fail] a sentence. [on_status] maps a status
    such as 400 to a function that hears Grocy's message instead of [fail]."""
    base = base_url()
    if not base:
        fail("Set your Grocy server's address on this plugin's page first.")
        return
    key = api_key()
    if not key:
        fail("Paste a Grocy API key first.")
        return

    def answered(r):
        if r.status_code >= 400:
            special = (on_status or {}).get(r.status_code)
            (special or fail)(message_of(r))
            return
        if not r.text.strip():
            ok(None)
            return
        kind = str(r.headers.get("content-type", ""))
        if kind and not any(t in kind for t in JSON_TYPES):
            fail("That address answered with a web page, not Grocy's API. Check the server address.")
            return
        try:
            body = r.json()
        except ValueError:
            fail("Grocy sent an answer that is not JSON.")
            return
        ok(body)

    http.request(
        method,
        base + "/api" + path,
        params=params,
        json=json,
        headers={"GROCY-API-KEY": key, "Accept": "application/json"},
        then=answered,
        on_error=lambda e: fail(failure_text(e)),
    )


def get(path, ok, fail, params=None, on_status=None):
    call("GET", path, ok, fail, params=params, on_status=on_status)


def post(path, body, ok, fail):
    call("POST", path, ok, fail, json=body if body is not None else {})


def put(path, body, ok, fail):
    call("PUT", path, ok, fail, json=body)


def delete(path, ok, fail):
    call("DELETE", path, ok, fail)
