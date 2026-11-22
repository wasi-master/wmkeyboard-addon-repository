#!/usr/bin/env python3
"""Publish new upstream releases of the repository's emoji fonts.

Each emoji font here is a build someone else publishes. For each one this
reads the upstream's latest release, and when its tag differs from the one
recorded in ``tools/emoji_upstreams.json`` it fetches the font, writes it over
the payload, and sets the new version in ``wmkeyboard-repo.json`` (and in the
font's ``.json`` sidecar, if it has one). ``tools/build_index.py`` then
refreshes the checksums and sizes.

The app offers an update whenever an addon's version changes, so a bump here
is what reaches phones that installed the font.

    python3 tools/update_emoji_fonts.py --list           # ids, one per line
    python3 tools/update_emoji_fonts.py --only twemoji   # update one font
    python3 tools/update_emoji_fonts.py --check          # exit 1 if any is behind

With ``--only`` it prints ``<name> <version>`` when it updated the font, and
nothing when the font is current. Emojitwo is not listed: its upstream's last
release was 2022.

Needs fontTools and Pillow for Fluent Emoji only (tools/slim_fluent_emoji.py).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import struct
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "wmkeyboard-repo.json"
STATE = Path(__file__).resolve().parent / "emoji_upstreams.json"
FONT_MAGIC = (b"\x00\x01\x00\x00", b"true", b"OTTO")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "wmkeyboard-addon-repository"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def _api(path: str):
    return json.loads(_get(f"https://api.github.com/repos/{path}"))


def _asset(release: dict, name: str) -> bytes:
    for asset in release["assets"]:
        if asset["name"] == name:
            return _get(asset["browser_download_url"])
    raise SystemExit(f"{release['tag_name']}: no asset named {name}")


def _font(data: bytes, where: str) -> bytes:
    if data[:4] not in FONT_MAGIC:
        raise SystemExit(f"{where}: not a TrueType/OpenType font")
    return data


def head_revision(data: bytes) -> str:
    """The ``head`` fontRevision as ``major.minor.0`` (2.057 -> 2.57.0)."""
    num_tables = struct.unpack(">H", data[4:6])[0]
    for i in range(num_tables):
        tag, _c, offset, _l = struct.unpack(">4sIII", data[12 + 16 * i:28 + 16 * i])
        if tag == b"head":
            fixed = struct.unpack(">i", data[offset + 4:offset + 8])[0]
            thousandths = round(fixed / 65536 * 1000)
            return f"{thousandths // 1000}.{thousandths % 1000}.0"
    raise ValueError("font has no head table")


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", version))


def bump_patch(version: str) -> str:
    major, minor, patch = (list(version_key(version)) + [0, 0, 0])[:3]
    return f"{major}.{minor}.{patch + 1}"


def semver(tag: str) -> str | None:
    m = re.fullmatch(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", tag)
    if not m:
        return None
    return ".".join(p or "0" for p in m.groups())


@dataclass
class Upstream:
    """One emoji font and where its builds come from.

    ``fetch(release)`` returns the payload bytes, or writes the payload itself
    and returns None (Fluent, which goes through the slimming script).
    ``version(release, data)`` returns the version to publish, or None to bump
    the patch of the current one.
    """

    id: str
    repo: str
    fetch: Callable[[dict], bytes | None]
    version: Callable[[dict, bytes | None], str | None]


# ---- per-font sources ----

def _noto_fetch(release: dict) -> bytes:
    # The 2D font moved under 2D/ when Google started shipping 3D fonts
    # beside it (v2026-09-24-unicode18_0); older tags keep it at fonts/.
    for path in ("2D/fonts/NotoColorEmoji.ttf", "fonts/NotoColorEmoji.ttf"):
        try:
            data = _get(f"https://raw.githubusercontent.com/googlefonts/noto-emoji/{release['tag_name']}/{path}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        if data[:4] in FONT_MAGIC:
            return data
    raise SystemExit(f"noto {release['tag_name']}: no NotoColorEmoji.ttf")


def _twemoji_version(release: dict, _data: bytes | None) -> str | None:
    # The build's tag says nothing about the artwork; its twemoji submodule
    # does. Match the submodule commit to a jdecked/twemoji tag.
    try:
        sub = _api(f"Nerixyz/twemoji-colr-font/contents/twemoji?ref={release['tag_name']}")
        for tag in _api("jdecked/twemoji/tags?per_page=100"):
            if tag["commit"]["sha"] == sub["sha"]:
                return semver(tag["name"])
    except (urllib.error.HTTPError, KeyError):
        pass
    return None


def _openmoji_fetch(release: dict) -> bytes:
    with zipfile.ZipFile(io.BytesIO(_asset(release, "openmoji-font.zip"))) as z:
        return z.read("OpenMoji-color-colr0_svg/OpenMoji-color-colr0_svg.ttf")


def _blobmoji_version(release: dict, _data: bytes | None) -> str | None:
    # "blobmoji-17r1" is Blobmoji 17, release 1 -> 17.0.0; r2 -> 17.0.1.
    m = re.fullmatch(r"blobmoji-(\d+)r(\d+)", release["tag_name"])
    return f"{m[1]}.0.{int(m[2]) - 1}" if m else None


def _fluent_fetch(release: dict) -> None:
    raw = _get(f"https://raw.githubusercontent.com/tetunori/fluent-emoji-webfont/{release['tag_name']}/dist/FluentEmojiColor.ttf")
    _font(raw, "fluent")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import slim_fluent_emoji  # needs fontTools + Pillow

    with tempfile.NamedTemporaryFile(suffix=".ttf") as tmp:
        tmp.write(raw)
        tmp.flush()
        # Its report goes to stderr: stdout is what the workflow reads.
        with contextlib.redirect_stdout(sys.stderr):
            slim_fluent_emoji.main(tmp.name)
    return None


UPSTREAMS = [
    Upstream("noto-color-emoji", "googlefonts/noto-emoji", _noto_fetch,
             lambda r, d: head_revision(d)),
    Upstream("twemoji", "Nerixyz/twemoji-colr-font",
             lambda r: _font(_asset(r, "Twemoji_GlyfColr0.ttf"), "twemoji"), _twemoji_version),
    Upstream("openmoji-color", "hfg-gmuend/openmoji",
             lambda r: _font(_openmoji_fetch(r), "openmoji"), lambda r, d: semver(r["tag_name"])),
    Upstream("blobmoji", "DavidBerdik/blobmoji2",
             lambda r: _font(_asset(r, "NotoColorEmoji.ttf"), "blobmoji"), _blobmoji_version),
    Upstream("fluent-emoji", "tetunori/fluent-emoji-webfont", _fluent_fetch,
             lambda r, d: None),
]


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update(up: Upstream, check: bool) -> str | None:
    """Returns "<name> <version>" when the font was (or, with check, would be) updated."""
    state = _load(STATE)
    recorded = state.get(up.id, {}).get("tag")
    release = _api(f"{up.repo}/releases/latest")
    tag = release["tag_name"]
    manifest = _load(MANIFEST)
    entry = next(a for a in manifest["addons"] if a["id"] == up.id)
    print(f"{up.id}: published {entry['version']} from {recorded}, upstream latest {tag}", file=sys.stderr)
    if tag == recorded:
        return None
    if check:
        return f"{entry['name']} {tag}"

    state[up.id] = {"repo": up.repo, "tag": tag}
    payload = ROOT / entry["path"]
    before = payload.read_bytes()
    data = up.fetch(release)
    if data is not None:
        if data == before:
            # A new tag with the same font in it: nothing for phones to fetch.
            _dump(STATE, state)
            return None
        payload.write_bytes(data)
    old = entry["version"]
    upstream = up.version(release, data if data is not None else payload.read_bytes())
    new = upstream if upstream and version_key(upstream) > version_key(old) else bump_patch(old)

    entry["version"] = new
    licence = entry.get("licenseFile")
    text = (ROOT / licence).read_text(encoding="utf-8") if licence else None
    if text is not None and recorded:
        text = text.replace(f"release {recorded}", f"release {tag}")
    # Descriptions and licence notes name the artwork version they describe;
    # only an upstream version may change that, not a patch bump.
    if new == upstream:
        if "description" in entry:
            entry["description"] = entry["description"].replace(old, new)
        if text is not None:
            text = text.replace(old, new)
    _dump(MANIFEST, manifest)
    if text is not None:
        (ROOT / licence).write_text(text, encoding="utf-8")
    sidecar = payload.with_suffix(".json")
    if sidecar.exists():
        side = _load(sidecar)
        side["version"] = new
        blob = payload.read_bytes()
        side["sizeBytes"] = len(blob)
        side["sha256"] = hashlib.sha256(blob).hexdigest()
        _dump(sidecar, side)

    _dump(STATE, state)
    return f"{entry['name']} {new}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="print the font ids")
    parser.add_argument("--only", metavar="ID", help="update one font")
    parser.add_argument("--check", action="store_true", help="report fonts behind upstream, change nothing")
    args = parser.parse_args()

    if args.list:
        print("\n".join(up.id for up in UPSTREAMS))
        return 0
    targets = [up for up in UPSTREAMS if args.only in (None, up.id)]
    if not targets:
        raise SystemExit(f"unknown id {args.only}")
    behind = False
    for up in targets:
        result = update(up, args.check)
        if result:
            behind = True
            print(result)
    return 1 if args.check and behind else 0


if __name__ == "__main__":
    sys.exit(main())
