# The rules for what counts as a link, kept apart from the panel so test.py
# can check them on their own.

import re

MOST_LINKS = 500
MOST_TITLE = 80
MOST_URL = 4000

_SCHEME = r"^[a-zA-Z][a-zA-Z0-9+.-]*:"
# A name with a dot and no spaces: "example.com", "docs.example.org/a?b".
_BARE = r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)+(:[0-9]+)?([/?#].*)?$"
# An address on the home network, which is plain http more often than not.
_LOCAL = r"^(localhost|[0-9]{1,3}(\.[0-9]{1,3}){3})(:[0-9]+)?([/?#].*)?$"
_SPACE = r"\s"


def host_of(url):
    """The site part of [url] without "www.", for a button nobody named."""
    rest = url.split("://", 1)[1] if "://" in url else url
    for cut in ("/", "?", "#"):
        rest = rest.split(cut, 1)[0]
    rest = rest.split("@")[-1].lower()
    if rest.startswith("www."):
        rest = rest[4:]
    return rest or url


def normalise(text):
    """[text] as a web address the phone can open, or None.

    Trimmed; a bare name like example.com gets https:// in front (http:// for
    localhost and a numbered address); http and https links are kept as they
    are. Anything else, mailto: or javascript: alike, is not a link here: the
    keyboard opens only web links from a plugin."""
    t = str(text if text is not None else "").strip()
    if not t or len(t) > MOST_URL or re.search(_SPACE, t):
        return None
    if re.match(_SCHEME, t):
        scheme = t.split(":", 1)[0].lower()
        rest = t[len(scheme) + 1:]
        if scheme in ("http", "https"):
            if not rest.startswith("//"):
                return None
            authority = rest[2:]
            for cut in ("/", "?", "#"):
                authority = authority.split(cut, 1)[0]
            # No site, or a user name in front of it (a link dressed up as another site's).
            if not authority or "@" in authority:
                return None
            return scheme + ":" + rest
        # "localhost:8080" and "nas.local:5000" read as a scheme; they are hosts.
        if rest[:1].isdigit():
            return normalise("http://" + t)
        return None
    if re.match(_LOCAL, t):
        return "http://" + t
    if re.match(_BARE, t):
        return "https://" + t
    return None


def first_link_in(text):
    """The first link in [text]: all of it when it is one, else the first
    word that looks like one, for an Add that starts from a copied message."""
    whole = normalise(text)
    if whole:
        return whole
    for word in re.split(_SPACE, str(text or "")):
        word = word.strip("()<>\"',.;!")
        if "://" in word or re.match(_BARE, word) or re.match(_LOCAL, word):
            found = normalise(word)
            if found:
                return found
    return None


def clean_title(title, url):
    """A button's name: its own words on one line, cut to MOST_TITLE, or the site's name."""
    words = " ".join(str(title or "").split())
    if len(words) > MOST_TITLE:
        words = words[:MOST_TITLE].rstrip()
    return words or host_of(url)
