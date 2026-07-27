#!/usr/bin/env python3
"""Zips plugins-src/<name>/ into plugins/<name>.wmplugin.

A .wmplugin is just a ZIP holding plugin.json and main.lua, so this could be a
`zip` one-liner — but the sources are what people read and the archives are what
they install, and the two drifting apart is the failure worth preventing. Run
this before tools/build_index.py, which computes the checksums.

Deterministic on purpose: fixed timestamps and sorted entries, so rebuilding an
unchanged plugin produces a byte-identical file and the index does not churn.

Usage:
    tools/build_plugins.py            rebuild every plugin
    tools/build_plugins.py --check    fail if anything is out of date
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "plugins-src"
OUTPUT_DIR = ROOT / "plugins"

MANIFEST = "plugin.json"

# Fixed ZIP timestamp (1980-01-01), the earliest the format can represent.
FIXED_DATE = (1980, 1, 1, 0, 0, 0)

FORMAT = "wmkeyboard-plugin"

# Mirrors PluginPermission.kt. A permission the app does not know refuses the
# install outright, so publishing one would ship a plugin nobody can use.
KNOWN_PERMISSIONS = {"storage"}


def build(source: Path) -> tuple[bytes, list[str]]:
    """Returns the archive bytes for one plugin source directory, plus problems."""
    problems: list[str] = []
    manifest_path = source / MANIFEST
    if not manifest_path.is_file():
        return b"", [f"{source.name}: no {MANIFEST}"]

    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as error:
        return b"", [f"{source.name}: {MANIFEST} is not valid JSON — {error}"]

    if manifest.get("format") != FORMAT:
        problems.append(f"{source.name}: format must be {FORMAT!r}")
    for field in ("id", "name", "pluginVersion"):
        if not manifest.get(field):
            problems.append(f"{source.name}: {field} is required")
    for permission in manifest.get("permissions", []):
        if permission not in KNOWN_PERMISSIONS:
            problems.append(f"{source.name}: unknown permission {permission!r}")

    entry = manifest.get("entry", "main.lua")
    script = source / entry
    if not script.is_file():
        problems.append(f"{source.name}: entry {entry} is missing")
        return b"", problems

    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted([MANIFEST, entry]):
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (source / name).read_bytes())
    return buffer.getvalue(), problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="don't write anything; fail if an archive is missing or stale",
    )
    args = parser.parse_args()

    if not SOURCE_DIR.is_dir():
        print(f"no {SOURCE_DIR.relative_to(ROOT)} directory — nothing to build")
        return 0

    OUTPUT_DIR.mkdir(exist_ok=True)
    problems: list[str] = []
    stale: list[str] = []

    for source in sorted(p for p in SOURCE_DIR.iterdir() if p.is_dir()):
        data, issues = build(source)
        problems.extend(issues)
        if not data:
            continue
        target = OUTPUT_DIR / f"{source.name}.wmplugin"
        if args.check:
            if not target.is_file() or target.read_bytes() != data:
                stale.append(str(target.relative_to(ROOT)))
        else:
            target.write_bytes(data)
            print(f"built {target.relative_to(ROOT)} ({len(data)} bytes)")

    for line in problems:
        print(f"error: {line}", file=sys.stderr)
    for line in stale:
        print(f"error: out of date — {line}", file=sys.stderr)
    if problems or stale:
        if stale:
            print("run tools/build_plugins.py to rebuild", file=sys.stderr)
        return 1
    if args.check:
        print("every plugin archive is up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
