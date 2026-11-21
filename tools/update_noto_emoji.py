#!/usr/bin/env python3
"""Publish the newest Noto Color Emoji release, if it is newer than ours.

Reads the latest release of googlefonts/noto-emoji, downloads the 2D
``NotoColorEmoji.ttf`` at that tag, and compares the font's own revision (the
``head`` table) with the version in ``fonts/noto-color-emoji.json``. When the
release is newer it replaces ``fonts/noto-color-emoji.ttf`` and writes the new
version into ``fonts/noto-color-emoji.json`` and ``wmkeyboard-repo.json``;
``tools/build_index.py`` then refreshes the checksums and sizes.

The app's "Get the newest emoji" row reads the version out of
``noto-color-emoji.json`` and offers an update whenever it differs from the
installed copy, so a bump here is what reaches phones.

    python3 tools/update_noto_emoji.py            # update in place if newer
    python3 tools/update_noto_emoji.py --check    # exit 1 if an update exists

Prints ``updated=<version>`` (or ``updated=``) for the workflow to read.
Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "fonts" / "noto-color-emoji.ttf"
SIDECAR = ROOT / "fonts" / "noto-color-emoji.json"
MANIFEST = ROOT / "wmkeyboard-repo.json"
ADDON_ID = "noto-color-emoji"

UPSTREAM = "googlefonts/noto-emoji"
# The 2D font moved under 2D/ when Google started shipping 3D fonts beside it
# (v2026-09-24-unicode18_0); older tags keep it at fonts/.
FONT_PATHS = ("2D/fonts/NotoColorEmoji.ttf", "fonts/NotoColorEmoji.ttf")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "wmkeyboard-addon-repository"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def font_revision(data: bytes) -> str:
    """The ``head`` table's fontRevision as ``major.minor.0`` (2.057 → 2.57.0).

    The repository has always written Noto's revision this way, so the app's
    plain string comparison keeps working.
    """
    if data[:4] not in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
        raise ValueError("not a TrueType/OpenType font")
    num_tables = struct.unpack(">H", data[4:6])[0]
    for i in range(num_tables):
        rec = 12 + 16 * i
        tag, _checksum, offset, _length = struct.unpack(">4sIII", data[rec:rec + 16])
        if tag == b"head":
            fixed = struct.unpack(">i", data[offset + 4:offset + 8])[0]
            thousandths = round(fixed / 65536 * 1000)
            return f"{thousandths // 1000}.{thousandths % 1000}.0"
    raise ValueError("font has no head table")


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.split(".") if p.isdigit())


def latest_font() -> tuple[str, bytes]:
    release = json.loads(_get(f"https://api.github.com/repos/{UPSTREAM}/releases/latest"))
    tag = release["tag_name"]
    for path in FONT_PATHS:
        try:
            data = _get(f"https://raw.githubusercontent.com/{UPSTREAM}/{tag}/{path}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        if data[:4] in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
            return tag, data
    raise SystemExit(f"{tag}: no NotoColorEmoji.ttf at {', '.join(FONT_PATHS)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if an update exists, change nothing")
    args = parser.parse_args()

    sidecar = json.loads(SIDECAR.read_text(encoding="utf-8"))
    current = sidecar["version"]
    tag, data = latest_font()
    latest = font_revision(data)
    print(f"published {current}, upstream {tag} is {latest}", file=sys.stderr)

    if version_key(latest) <= version_key(current):
        print("updated=")
        return 0
    if args.check:
        print(f"updated={latest}")
        return 1

    FONT.write_bytes(data)
    sidecar["version"] = latest
    sidecar["sizeBytes"] = len(data)
    sidecar["sha256"] = hashlib.sha256(data).hexdigest()
    SIDECAR.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = next(a for a in manifest["addons"] if a["id"] == ADDON_ID)
    entry["version"] = latest
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"updated={latest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
