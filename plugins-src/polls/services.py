# The services a poll can be made on, by the id the `service` setting holds.
#
# Each one is a class with an INFO dict and the same jobs, every job a list
# of steps for flow.run:
#
#   create(acct, poll)        ctx gets "url" (the link to share) and "remote"
#                             (whatever the other jobs need to find it again)
#   results(acct, record)     ctx gets "counts" (one per answer, in order),
#                             "responses" (people who answered), "closed"
#   close(acct, record), delete(acct, record)
#   check(acct)               fails when the sign-in is wrong
#   logout(acct)              revokes the sign-in on the server, if it can
#   explain(status, said)     wording for a failed reply, or "" for the usual
#
# INFO: id, name, account (which saved sign-in it uses), server (needs the
# server setting), base (the fixed address when it doesn't), user (asks for a
# user name), browser (can sign in through the browser), deadline, close,
# help (Markdown shown over the sign-in boxes), secret (that box's label).

import limesurvey
import nextcloud
import strawpoll

ALL = [nextcloud.Forms, nextcloud.Polls, limesurvey.LimeSurvey, strawpoll.StrawPoll]
DEFAULT = "nextcloud_forms"


def get(service_id):
    for svc in ALL:
        if svc.INFO["id"] == service_id:
            return svc
    return ALL[0]
