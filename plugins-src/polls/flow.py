# Runs a backend's requests one after another without holding up the panel.
#
# A backend describes a job (create a poll, read its results, close it) as a
# list of steps. Each step is a function that gets the job's context dict and
# gives back the request to send, or None to skip it. A request is a dict of
# http.request's arguments plus two of its own:
#
#   "take":  fn(ctx, response), which reads what the step needs from the reply
#            into ctx (ids, links, counts). It may raise to stop the job.
#   "ok":    statuses that count as success besides 2xx, such as (404,) for a
#            delete that finds nothing left to delete.
#
# Every request goes out with then=, so the panel keeps drawing between them,
# and the next step is built only once the one before has answered: a step can
# use the id the previous reply carried.

from wm import http


class ServerError(Exception):
    """A reply the job can't go on from, with the response kept for wording."""

    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response
        self.status = response.status_code if response is not None else 0


def reply_message(r):
    """The server's own words for a failed reply, if it sent any."""
    try:
        data = r.json()
    except ValueError:
        return ""
    if isinstance(data, dict):
        meta = data.get("ocs", {}).get("meta", {}) if isinstance(data.get("ocs"), dict) else {}
        for value in (data.get("message"), data.get("error"), meta.get("message")):
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict) and isinstance(value.get("message"), str):
                return value["message"].strip()
    return ""


def run(steps, ctx, done, failed):
    """Send [steps] in order; done(ctx) after the last, failed(error) on the
    first that fails."""
    at = {"i": 0}

    def answered(take, ok):
        def got(r):
            if not (200 <= r.status_code < 300 or r.status_code in ok):
                failed(ServerError(reply_message(r) or (str(r.status_code) + " " + r.reason).strip(), r))
                return
            if take is not None:
                try:
                    take(ctx, r)
                except Exception as e:
                    failed(e)
                    return
            step()
        return got

    def step():
        while at["i"] < len(steps):
            build = steps[at["i"]]
            at["i"] += 1
            try:
                request = build(ctx)
            except Exception as e:
                failed(e)
                return
            if request is None:
                continue
            request = dict(request)
            take = request.pop("take", None)
            ok = tuple(request.pop("ok", ()))
            method = request.pop("method", "GET")
            url = request.pop("url")
            try:
                http.request(method, url, then=answered(take, ok), on_error=failed, **request)
            except Exception as e:
                failed(e)
            return
        done(ctx)

    step()
