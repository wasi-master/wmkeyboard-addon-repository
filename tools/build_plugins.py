#!/usr/bin/env python3
"""Zips plugins-src/<name>/ into plugins/<name>.wmplugin.

A .wmplugin is just a ZIP holding plugin.json and main.py, so this could be a
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
import re
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
KNOWN_PERMISSIONS = {
    "storage", "reminders", "selection",
    # API 5
    "network", "ai", "field.read", "field.write", "clipboard.read", "clipboard.write",
    "location", "files", "sensors", "scan", "device", "share", "notifications",
}

# Plugins are Python: API 4 (the wm and ui globals) or API 5 (the wm
# package, several modules and assets/). The app refuses Lua outright.
MAX_API_VERSION = 5

# The permissions API 5 added; a manifest below 5 may not declare them.
API_5_PERMISSIONS = KNOWN_PERMISSIONS - {"storage", "reminders", "selection"}

# Mirrors PluginManifestCodec.isValidHost: a host name, optionally "*." first;
# no scheme, port, path, IP address or localhost.
HOST_PATTERN = re.compile(r"(\*\.)?([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")


def host_problems(manifest: dict, permissions: list) -> list[str]:
    """What the app refuses about `hosts`, in its own terms."""
    hosts = manifest.get("hosts", [])
    out = []
    if not isinstance(hosts, list):
        return ["hosts must be a list"]
    if len(hosts) > 16:
        out.append(f"{len(hosts)} hosts; the app caps at 16")
    for host in hosts:
        if not isinstance(host, str) or not HOST_PATTERN.fullmatch(host.lower()) or host == "localhost":
            out.append(f"host {host!r} is not a host name (no scheme, port, path or IP address)")
    host_setting = any(isinstance(s, dict) and s.get("type") == "host" for s in manifest.get("settings", []))
    if "network" in permissions and not hosts and not host_setting:
        out.append("\"network\" needs \"hosts\" (or a \"host\" setting)")
    return out

# PluginFile: what an API 5 archive may hold.
MAX_ENTRIES = 64
MAX_ARCHIVE = 4 * 1024 * 1024
MAX_ASSET = 512 * 1024
ASSET_TYPES = {".png", ".webp", ".jpg", ".jpeg", ".svg", ".json", ".txt"}


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
    permissions = manifest.get("permissions", [])
    api = manifest.get("apiVersion", 1)
    for permission in permissions:
        if permission not in KNOWN_PERMISSIONS:
            problems.append(f"{source.name}: unknown permission {permission!r}")
        elif permission in API_5_PERMISSIONS and api != 5:
            problems.append(f"{source.name}: permission {permission!r} needs apiVersion 5")
    problems.extend(f"{source.name}: {p}" for p in host_problems(manifest, permissions))

    if manifest.get("language", "python") != "python":
        problems.append(f"{source.name}: language must be \"python\"")
    if not isinstance(api, int) or not 4 <= api <= MAX_API_VERSION:
        problems.append(f"{source.name}: apiVersion must be 4 or {MAX_API_VERSION} (Python plugins)")
    entry = manifest.get("entry", "main.py")
    if not entry.endswith(".py"):
        problems.append(f"{source.name}: entry {entry} is not a .py file")
    script = source / entry
    if not script.is_file():
        problems.append(f"{source.name}: entry {entry} is missing")
        return b"", problems

    import io

    buffer = io.BytesIO()
    # API 4 is one script. API 5 may add other .py modules beside it and an
    # assets/ folder; anything else in the folder (tests, notes) stays out.
    names = [MANIFEST, entry]
    if api == 5:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(source).as_posix()
            if rel in names or rel == "test.py" or rel.startswith("tests/"):
                continue
            if rel.endswith(".py") or (rel.startswith("assets/") and path.suffix.lower() in ASSET_TYPES):
                if rel.startswith("assets/") and path.stat().st_size > MAX_ASSET:
                    problems.append(f"{source.name}: {rel} is over 512 KB")
                names.append(rel)
    if len(names) > MAX_ENTRIES:
        problems.append(f"{source.name}: {len(names)} entries; the app caps at {MAX_ENTRIES}")
    if sum((source / n).stat().st_size for n in names) > MAX_ARCHIVE:
        problems.append(f"{source.name}: over 4 MB unpacked")
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
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
