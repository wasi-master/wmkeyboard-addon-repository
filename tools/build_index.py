#!/usr/bin/env python3
"""Recompute the checksums and sizes in wmkeyboard-repo.json.

Every addon's metadata — name, description, tags, version — is written by hand.
The two fields that are mechanical, ``sha256`` and ``sizeBytes``, drift the
moment a payload changes, so this script recomputes them from the files on disk
and leaves everything else exactly as it was.

Both fields are **optional** in the format: a manifest without them installs
fine, and the app just marks the addon unverified. This script is a convenience
for publishers who want them, not a step anyone is required to run.

    python3 tools/build_index.py              # rewrite in place
    python3 tools/build_index.py --check      # exit 1 if anything is stale
    python3 tools/build_index.py --date 2026-07-27
    python3 tools/build_index.py --drop-checksums

By default ``repo.updatedAt`` is bumped only when something else changed.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "wmkeyboard-repo.json"

# The order entries are written back in. Anything not listed keeps its relative
# position at the end, so a field added to the format later is not dropped.
FIELD_ORDER = [
    "id",
    "type",
    "name",
    "version",
    "author",
    "description",
    "tags",
    "path",
    "sha256",
    "sizeBytes",
    "previews",
    "minAppVersion",
    "langId",
]

# Where each type's payloads conventionally live, used only to spot files that
# exist but were never indexed. The manifest's `path` is what actually locates a
# payload — these folders are a convention, not a rule.
PAYLOAD_DIRS = {
    "themes": "*.wmtheme.json",
    "layouts": "*.wmlayout.json",
    "dictionaries": "*.txt*",
    "snippets": "*.wmsnippets.json",
    "stickers": "*.wmstickers",
    "icons": "*.wmicons",
    "fonts": "*.[to]tf",
    "sounds": "*.mp3",
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ordered(entry: dict) -> dict:
    """Reorder an entry's keys, keeping unknown ones at the end."""
    known = [k for k in FIELD_ORDER if k in entry]
    extra = [k for k in entry if k not in FIELD_ORDER]
    return {k: entry[k] for k in known + extra}


def is_remote(path: str) -> bool:
    return path.startswith("https://") or path.startswith("http://")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report staleness and exit 1 instead of rewriting",
    )
    parser.add_argument(
        "--date",
        help="value for repo.updatedAt (default: today, only written if something changed)",
    )
    parser.add_argument(
        "--drop-checksums",
        action="store_true",
        help="remove sha256/sizeBytes entirely — both are optional in the format",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    addons = manifest.get("addons", [])

    changes: list[str] = []
    problems: list[str] = []
    indexed: set[Path] = set()

    for entry in addons:
        ident = entry.get("id", "<no id>")
        path = entry.get("path", "")

        if not path:
            problems.append(f"{ident}: no path")
            continue

        if is_remote(path):
            # Absolute URLs point off-repo; we can't hash what we don't have.
            if not args.drop_checksums and "sha256" not in entry:
                print(f"note: {ident}: absolute URL, checksum left to the publisher")
            continue

        payload = ROOT / path
        if not payload.is_file():
            problems.append(f"{ident}: path does not exist — {path}")
            continue
        indexed.add(payload.resolve())

        if args.drop_checksums:
            for field in ("sha256", "sizeBytes"):
                if entry.pop(field, None) is not None:
                    changes.append(f"{ident}: dropped {field}")
            continue

        size = payload.stat().st_size
        digest = sha256_of(payload)

        if entry.get("sizeBytes") != size:
            changes.append(f"{ident}: sizeBytes {entry.get('sizeBytes')} -> {size}")
            entry["sizeBytes"] = size
        if entry.get("sha256") != digest:
            changes.append(f"{ident}: sha256 {str(entry.get('sha256'))[:12]}… -> {digest[:12]}…")
            entry["sha256"] = digest

        for preview in entry.get("previews", []):
            if not is_remote(preview) and not (ROOT / preview).is_file():
                problems.append(f"{ident}: preview does not exist — {preview}")

    icon = manifest.get("repo", {}).get("icon")
    if icon and not is_remote(icon) and not (ROOT / icon).is_file():
        problems.append(f"repo.icon does not exist — {icon}")

    # Payload files sitting in the tree that nothing indexes. Not an error — a
    # repo may keep licence texts or work-in-progress files around — but it is
    # almost always a forgotten manifest entry.
    for folder, pattern in PAYLOAD_DIRS.items():
        directory = ROOT / folder
        if not directory.is_dir():
            continue
        for payload in sorted(directory.glob(pattern)):
            if payload.resolve() not in indexed:
                print(f"note: not in the manifest — {payload.relative_to(ROOT)}")

    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    manifest["addons"] = [ordered(entry) for entry in addons]

    if changes:
        today = args.date or _dt.date.today().isoformat()
        if manifest.get("repo", {}).get("updatedAt") != today:
            changes.append(f"repo.updatedAt -> {today}")
            manifest.setdefault("repo", {})["updatedAt"] = today
    elif args.date:
        manifest.setdefault("repo", {})["updatedAt"] = args.date
        changes.append(f"repo.updatedAt -> {args.date}")

    if not changes:
        print(f"{len(addons)} addons, manifest up to date")
        return 0

    for change in changes:
        print(change)

    if args.check:
        print("\nmanifest is stale — run tools/build_index.py", file=sys.stderr)
        return 1

    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
