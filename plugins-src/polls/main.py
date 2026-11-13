# Polls: write a question and its answers in the keyboard, make the poll on
# your own server, and put its link into the chat. The polls you made stay in
# a list with their answers so far, and you can close one from there.
#
# The services live in their own files (nextcloud.py, limesurvey.py, ...),
# each giving the same few jobs as lists of requests for flow.run: create a
# poll, read its answers, close it, delete it.

import time
from wm import plugin, ui, storage, share, _, ngettext
import flow
import services

MAX_OPTIONS = 10
MAX_SAVED = 40
REFRESH_SECONDS = 30

draft = plugin.state(persist=True, key="draft", question="", options=["", ""], multi=False, closes=False, deadline=None)
saved = plugin.state(persist=True, key="polls", polls=[], seq=0)
pending = plugin.state(persist=True, key="signin", service="", token="", endpoint="", until=0)
st = plugin.state(busy="", error="", made=None, open_id=None, loading=False, qr=False)


# MARK: - the service and its account

def service():
    """The module for the service chosen in settings."""
    return services.get(plugin.settings.get("service", services.DEFAULT))


def server_url():
    """The address typed into the server setting, as a base URL without a
    trailing slash, or "" when there is none."""
    text = str(plugin.settings.get("server", "") or "").strip().rstrip("/")
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    return text


def account(svc=None):
    """Where and as whom: the server, and the user name and password or key
    from the settings page (the secret rows are kept in the plugin's secrets)."""
    svc = svc or service()
    return {
        "base": server_url() if svc.INFO["server"] else svc.INFO["base"],
        "user": str(plugin.settings.get("user", "") or "").strip() if svc.INFO["user"] else "",
        "password": str(plugin.settings.get(svc.INFO["secret"], "") or "").strip(),
    }


def signed_in(svc=None):
    svc = svc or service()
    acct = account(svc)
    if svc.INFO["server"] and not acct["base"]:
        return False
    return bool(acct["password"]) and (bool(acct["user"]) or not svc.INFO["user"])


def remember_login(svc, user, password):
    """What Login Flow handed over, onto the settings page."""
    if svc.INFO["user"]:
        plugin.settings.set("user", user)
    plugin.settings.set(svc.INFO["secret"], password)


def forget_login(svc):
    plugin.settings.reset(svc.INFO["secret"])


# MARK: - wording errors

def explain(error, svc=None):
    """Something the user can act on, for any failure a job can end in."""
    svc = svc or service()
    if isinstance(error, PermissionError):
        return _("Allow Polls to use the internet on its page in Settings, then try again.")
    if isinstance(error, TimeoutError):
        return _("The server took too long to answer.")
    if isinstance(error, ConnectionError):
        return _("Could not reach the server: {why}", why=str(error))
    if isinstance(error, flow.ServerError):
        said = svc.explain(error.status, str(error))
        if said:
            return said
        if error.status == 401 or error.status == 403:
            return _("The server turned down the sign-in. Sign in again under Account.")
        if error.status == 404:
            return _("The server has no {name} at this address.", name=svc.INFO["name"])
        return _("The server answered: {what}", what=str(error))
    return str(error)


def start(job, ctx, done, svc=None, busy=""):
    svc = svc or service()
    st.busy = busy
    st.error = ""

    def finished(c):
        st.busy = ""
        done(c)

    def failed(e):
        st.busy = ""
        st.error = explain(e, svc)

    flow.run(job, ctx, finished, failed)


# MARK: - writing a poll

def options_given():
    seen = []
    for text in draft.options:
        text = text.strip()
        if text and text.lower() not in [s.lower() for s in seen]:
            seen.append(text)
    return seen


def problem():
    """Why the draft can't be sent yet, or ""."""
    if not draft.question.strip():
        return _("Write the question.")
    if len(options_given()) < 2:
        return _("Give at least two different answers.")
    if draft.closes and draft.deadline and draft.deadline <= time.time():
        return _("The closing time has already passed.")
    return ""


def set_question(text):
    draft.question = text


def set_option(i, text):
    if i < len(draft.options):
        draft.options[i] = text


def add_option():
    if len(draft.options) < MAX_OPTIONS:
        draft.options.append("")


def drop_option(i):
    if len(draft.options) > 2 and i < len(draft.options):
        draft.options.pop(i)


def set_multi(value):
    draft.multi = value == "many"


def set_closes(on):
    draft.closes = on
    if on and not draft.deadline:
        draft.deadline = round_up(time.time() + 24 * 3600)


def set_deadline(value):
    draft.deadline = value


def round_up(seconds):
    return int(seconds // 900 + 1) * 900


def clear_draft():
    draft.update(question="", options=["", ""], multi=False, closes=False, deadline=None)
    st.made = None
    st.error = ""


def create():
    svc = service()
    if problem() or st.busy:
        return
    poll = {
        "question": draft.question.strip(),
        "options": options_given(),
        "multi": draft.multi,
        "deadline": int(draft.deadline) if draft.closes and draft.deadline else None,
    }
    ctx = {"poll": poll}

    def made(c):
        saved.seq += 1
        record = {
            "id": saved.seq,
            "service": svc.INFO["id"],
            "question": poll["question"],
            "options": poll["options"],
            "multi": poll["multi"],
            "deadline": poll["deadline"],
            "url": c["url"],
            "base": account(svc)["base"],
            "remote": c.get("remote", {}),
            "made": int(time.time()),
            "closed": False,
            "counts": [0 for _o in poll["options"]],
            "responses": 0,
            "checked": 0,
        }
        saved.polls = ([record] + saved.polls)[:MAX_SAVED]
        st.made = record["id"]
        st.qr = False
        draft.update(question="", options=["", ""], multi=False, closes=False, deadline=None)

    start(svc.create(account(svc), poll), ctx, made, svc, busy=_("Making the poll…"))


def share_text(record):
    return record["question"] + "\n" + record["url"]


# MARK: - keyword

@plugin.keyword("poll")
def from_keyword(text):
    """`@poll Lunch? Pizza, Sushi, Tacos` fills in the question and answers."""
    text = (text or "").strip()
    if not text:
        return
    question, rest = text, ""
    if "?" in text:
        cut = text.index("?") + 1
        question, rest = text[:cut], text[cut:]
    elif ":" in text:
        cut = text.index(":")
        question, rest = text[:cut], text[cut + 1:]
    answers = []
    for sep in (",", " / ", "|", ";"):
        if sep in rest:
            answers = [a.strip() for a in rest.split(sep) if a.strip()]
            break
    if not answers and rest.strip():
        answers = [a.strip() for a in rest.replace(" or ", ",").split(",") if a.strip()]
    draft.question = question.strip()
    draft.options = (answers + ["", ""])[:max(2, min(len(answers), MAX_OPTIONS))]
    st.made = None


# MARK: - saved polls

def find(poll_id):
    for record in saved.polls:
        if record["id"] == poll_id:
            return record
    return None


def store(record):
    saved.polls = [record if p["id"] == record["id"] else p for p in saved.polls]


def open_poll(poll_id):
    st.open_id = poll_id
    st.qr = False
    record = find(poll_id)
    if record is None:
        return
    plugin.push(poll_page, title=_("Poll"))
    load_results(record)


def moved(record):
    """Why a saved poll can't be reached any more, or "": the server setting
    now names another server than the one it was made on."""
    svc = services.get(record["service"])
    base = record.get("base") or ""
    if svc.INFO["server"] and base and base != server_url():
        return _("This poll is on {where}. Type that server in settings again to follow it.", where=base.split("://")[-1])
    return ""


def open_link(url):
    try:
        share.open(url)
    except PermissionError:
        st.error = _("Allow Polls to open links on its page in Settings.")
    except (ValueError, OSError) as e:
        st.error = str(e)


def load_results(record, quiet=False):
    svc = services.get(record["service"])
    if st.loading or not signed_in(svc):
        return
    if moved(record):
        if not quiet:
            st.error = moved(record)
        return
    st.loading = True
    if not quiet:
        st.error = ""

    def got(c):
        st.loading = False
        fresh = find(record["id"])
        if fresh is None:
            return
        fresh["counts"] = c.get("counts", fresh["counts"])
        fresh["responses"] = c.get("responses", fresh["responses"])
        if c.get("closed") is not None:
            fresh["closed"] = c["closed"]
        fresh["checked"] = int(time.time())
        store(fresh)

    def failed(e):
        st.loading = False
        if not quiet:
            st.error = explain(e, svc)

    ctx = {"poll": record, "remote": record["remote"]}
    flow.run(svc.results(account(svc), record), ctx, got, failed)


@plugin.every(seconds=REFRESH_SECONDS)
def keep_fresh():
    record = find(st.open_id) if st.open_id else None
    if record is not None and not record["closed"] and not st.busy:
        load_results(record, quiet=True)


def close_poll(record):
    svc = services.get(record["service"])
    if moved(record):
        st.error = moved(record)
        return

    def closed(c):
        fresh = find(record["id"])
        if fresh is not None:
            fresh["closed"] = True
            store(fresh)
        ui.toast(_("Poll closed"))

    start(svc.close(account(svc), record), {"poll": record, "remote": record["remote"]}, closed, svc, busy=_("Closing…"))


def ask_close(record):
    def answer(label):
        if label == _("Close poll"):
            close_poll(record)
    ui.dialog(_("Close this poll?"), _("Nobody can answer it after this. The answers so far stay."),
              buttons=(_("Cancel"), _("Close poll")), on_result=answer)


def forget(record):
    saved.polls = [p for p in saved.polls if p["id"] != record["id"]]
    if st.open_id == record["id"]:
        st.open_id = None
        plugin.back()


def delete_poll(record):
    svc = services.get(record["service"])
    if moved(record):
        st.error = moved(record)
        return

    def gone(c):
        forget(record)
        ui.toast(_("Poll deleted"))

    start(svc.delete(account(svc), record), {"poll": record, "remote": record["remote"]}, gone, svc, busy=_("Deleting…"))


def ask_remove(record):
    keep, drop, cancel = _("Only from this list"), _("Delete on the server"), _("Cancel")

    def answer(label):
        if label == keep:
            forget(record)
        elif label == drop:
            delete_poll(record)
    ui.dialog(_("Remove this poll?"), _("Deleting it on the server also deletes every answer."),
              buttons=(cancel, keep, drop), on_result=answer)


# MARK: - signing in

def sign_in_browser():
    svc = service()
    if not server_url():
        return

    def started(c):
        pending.update(service=svc.INFO["id"], token=c["token"], endpoint=c["endpoint"], until=int(time.time()) + 20 * 60)
        open_link(c["login"])

    start(svc.login_start(server_url()), {}, started, svc, busy=_("Opening the sign-in page…"))


def check_sign_in(quiet=False):
    if not pending.token:
        return
    if time.time() > pending.until:
        pending.update(service="", token="", endpoint="", until=0)
        if not quiet:
            st.error = _("The sign-in took too long. Start it again.")
        return
    svc = services.get(pending.service)

    def finished(c):
        if not c.get("password"):
            if not quiet:
                st.error = _("Not signed in yet. Finish in the browser, then come back.")
            return
        remember_login(svc, c["user"], c["password"])
        pending.update(service="", token="", endpoint="", until=0)
        ui.toast(_("Signed in as {user}", user=c["user"]))

    start(svc.login_poll(pending.endpoint, pending.token), {}, finished, svc, busy="" if quiet else _("Checking…"))


@plugin.setting_changed("app_password")
@plugin.setting_changed("api_key")
def credentials_changed(value):
    """A password or key typed on the settings page: try it at once, so a
    wrong one is said here rather than at the first poll."""
    svc = service()
    if not value or not signed_in(svc):
        return

    def ok(c):
        st.error = ""
        ui.toast(_("Signed in to {name}", name=svc.INFO["name"]))

    start(svc.check(account(svc)), {}, ok, svc, busy=_("Checking…"))


def sign_out():
    svc = service()
    acct = account(svc)

    # Revoke the app password on the server when the service can, and
    # forget it here either way.
    flow.run(svc.logout(acct), {}, lambda c: None, lambda e: None)
    forget_login(svc)


@plugin.on_open
def opened():
    if pending.token:
        check_sign_in(quiet=True)


@plugin.command(_("Account"), icon="account_circle")
def show_account():
    plugin.push(account_page, title=_("Account"))


# MARK: - drawing

def when(seconds):
    return time.format("EEE d MMM, HH:mm", seconds)


def status_line(record):
    svc = services.get(record["service"])
    parts = [svc.INFO["name"]]
    parts.append(ngettext("{n} answer", "{n} answers", record["responses"]))
    if record["closed"]:
        parts.append(_("closed"))
    elif record["deadline"]:
        if record["deadline"] <= time.time():
            parts.append(_("closed"))
        else:
            parts.append(_("closes {when}", when=when(record["deadline"])))
    return " · ".join(parts)


def account_card():
    """Setup, when the chosen service isn't ready. True when it drew one."""
    svc = service()
    if svc.INFO["server"] and not server_url():
        ui.empty(_("Type the address of your {name} server on the plugin's page in Settings.", name=svc.INFO["name"]),
                 icon="dns", action=_("Open settings"), on_click=plugin.open_settings)
        return True
    if signed_in(svc):
        return False
    account_form(svc)
    return True


def account_form(svc):
    """How to sign in. Passwords and keys are typed on the settings page,
    never in the panel; Nextcloud can also hand one over from the browser."""
    with ui.card(title=_("Sign in to {name}", name=svc.INFO["name"])):
        if svc.INFO["server"]:
            ui.caption(server_url())
        if svc.INFO.get("browser"):
            if pending.token:
                ui.label(_("Finish signing in in the browser, then come back here."))
                with ui.row():
                    ui.button(_("I've signed in"), on_click=check_sign_in, primary=True, key="signed_in")
                    ui.button(_("Start again"), on_click=sign_in_browser, key="restart")
            else:
                ui.button(_("Sign in with the browser"), on_click=sign_in_browser, primary=True, icon="open_in_new", key="browser")
        ui.markdown(svc.INFO["help"])
        ui.button(_("Open settings"), on_click=plugin.open_settings, icon="settings", primary=not svc.INFO.get("browser"), key="settings")


def compose():
    if st.made:
        record = find(st.made)
        if record is not None:
            made_card(record)
            return
    if account_card():
        return
    svc = service()
    ui.input(label=_("Question"), value=draft.question, on_change=set_question, key="question",
             placeholder=_("Where shall we eat?"))
    for i, text in enumerate(draft.options):
        with ui.row(weights=[6, 1]):
            ui.input(label=_("Answer {n}", n=i + 1), value=text, on_change=lambda t, i=i: set_option(i, t), key="option" + str(i))
            ui.icon_button("close", on_click=lambda i=i: drop_option(i), label=_("Remove"), enabled=len(draft.options) > 2)
    if len(draft.options) < MAX_OPTIONS:
        ui.button(_("Add an answer"), on_click=add_option, icon="add", key="add_option")
    ui.select([("one", _("One answer")), ("many", _("Several answers"))], value="many" if draft.multi else "one",
              on_change=set_multi, style="segmented", key="multi")
    if svc.INFO["deadline"]:
        ui.toggle(_("Closes at a set time"), value=draft.closes, on_change=set_closes, key="closes")
        if draft.closes:
            ui.date(label=_("Closes"), value=draft.deadline, time=True, on_change=set_deadline, key="deadline")
    why = problem()
    if st.busy:
        ui.progress()
        ui.caption(st.busy)
    else:
        ui.button(_("Make the poll"), on_click=create, primary=True, enabled=not why, icon="how_to_vote", key="make")
        ui.caption(why or _("On {name} · {where}", name=svc.INFO["name"], where=account(svc)["base"].split("://")[-1]))


def made_card(record):
    with ui.card(title=_("Your poll is ready")):
        ui.output(share_text(record))
        if st.qr:
            ui.qr(record["url"])
        with ui.row():
            ui.button(_("Answers"), on_click=lambda: open_poll(record["id"]), icon="bar_chart", key="answers")
            ui.button(_("Hide QR") if st.qr else _("QR code"), on_click=lambda: st.update(qr=not st.qr), icon="qr_code", key="qr")
            ui.button(_("New poll"), on_click=clear_draft, icon="add", key="new")


def my_polls():
    rows = []
    for record in saved.polls:
        rows.append(ui.item(record["question"], subtitle=status_line(record),
                            icon="lock" if record["closed"] else "how_to_vote",
                            on_click=lambda r=record: open_poll(r["id"]),
                            actions={_("Remove"): lambda r=record: ask_remove(r)}))
    ui.list(rows)


def results(record):
    counts = record["counts"]
    votes = sum(counts)
    ui.stat(_("Answers"), record["responses"], caption=_("checked {when}", when=when(record["checked"])) if record["checked"] else None)
    if votes:
        ui.chart(counts, kind="bar", labels=[short(o) for o in record["options"]])
    for option, n in zip(record["options"], counts):
        share_of = n / votes if votes else 0
        ui.label(option + "  —  " + ngettext("{n} vote", "{n} votes", n) + " (" + str(round(share_of * 100)) + "%)")
        ui.progress(share_of)


def short(text):
    return text if len(text) <= 12 else text[:11] + "…"


def poll_page():
    record = find(st.open_id)
    if record is None:
        ui.empty(_("This poll is gone."), icon="delete")
        return
    with ui.column():
        ui.title(record["question"])
        ui.caption(status_line(record))
        if st.loading or st.busy:
            ui.progress()
        if st.error:
            ui.label(st.error, color="danger")
        results(record)
        ui.output(share_text(record))
        if st.qr:
            ui.qr(record["url"])
        with ui.row():
            ui.button(_("Refresh"), on_click=lambda: load_results(record), icon="refresh", enabled=not st.loading, key="refresh")
            ui.button(_("Open"), on_click=lambda: open_link(record["url"]), icon="open_in_new", key="open")
            ui.button(_("Hide QR") if st.qr else _("QR code"), on_click=lambda: st.update(qr=not st.qr), icon="qr_code", key="qr")
        with ui.row():
            if not record["closed"] and services.get(record["service"]).INFO["close"]:
                ui.button(_("Close poll"), on_click=lambda: ask_close(record), icon="lock", key="close")
            ui.button(_("Remove"), on_click=lambda: ask_remove(record), icon="delete", color="danger", key="remove")


def account_page():
    svc = service()
    with ui.column():
        if svc.INFO["server"] and not server_url():
            account_card()
            return
        if st.busy:
            ui.progress()
        if st.error:
            ui.label(st.error, color="danger")
        if signed_in(svc):
            acct = account(svc)
            ui.item(acct["user"] or svc.INFO["name"], subtitle=svc.INFO["name"] + " · " + acct["base"].split("://")[-1], icon="account_circle")
            ui.button(_("Sign out"), on_click=sign_out, icon="logout", key="sign_out")
            ui.button(_("Server and service settings"), on_click=plugin.open_settings, icon="settings", key="settings")
        else:
            account_form(svc)


def render():
    # The main page is on top again: no poll's page is open to keep fresh.
    st.open_id = None
    with ui.column():
        if st.error:
            ui.label(st.error, color="danger")
        compose()
        if saved.polls:
            with ui.section(_("Your polls"), collapsible=True):
                my_polls()
