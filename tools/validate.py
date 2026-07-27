#!/usr/bin/env python3
"""Validate wmkeyboard-repo.json before publishing it.

Two passes:

1. The JSON Schema at ``docs/addons/wmkeyboard-repo.schema.json`` (draft 2020-12).
2. The things a schema cannot express — that every ``path``, ``previews[]`` and
   ``repo.icon`` resolves to a file that is actually here, that ids are unique,
   and that any checksum present is correct.

``sha256`` and ``sizeBytes`` are **optional**. A manifest without them is valid
and installs fine; they are only checked when a publisher chose to provide them.

    python3 tools/validate.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "wmkeyboard-repo.json"
SCHEMA = ROOT / "docs" / "addons" / "wmkeyboard-repo.schema.json"

# Payload extensions the format defines, by type. A mismatch is a warning
# rather than an error: `path` is free-form on purpose, and a publisher may
# serve a theme from a URL with no extension at all.
EXPECTED_SUFFIX = {
    "theme": ".wmtheme.json",
    "layout": ".wmlayout.json",
    "dictionary": (".txt", ".txt.gz"),
    "snippets": ".wmsnippets.json",
    "stickers": ".wmstickers",
    "icon_pack": ".wmicons",
    "font": (".ttf", ".otf"),
    "sound": ".mp3",
}


def is_remote(path: str) -> bool:
    return path.startswith("https://") or path.startswith("http://")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_asset(field: str, value: str, errors: list[str], warnings: list[str]) -> Path | None:
    """Resolve one path/preview/icon reference, or record why it can't be."""
    if is_remote(value):
        if value.startswith("http://"):
            errors.append(f"{field}: plain http is rejected by the app — use https ({value})")
        return None
    target = (ROOT / value).resolve()
    try:
        target.relative_to(ROOT)
    except ValueError:
        errors.append(f"{field}: escapes the repository root ({value})")
        return None
    if not target.is_file():
        errors.append(f"{field}: no such file ({value})")
        return None
    return target


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    try:
        import jsonschema
    except ImportError:
        print("jsonschema not installed — skipping schema pass (pip install jsonschema)")
    else:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        for failure in sorted(validator.iter_errors(manifest), key=lambda e: list(e.path)):
            where = "/".join(str(p) for p in failure.path) or "<root>"
            errors.append(f"schema: {where}: {failure.message}")

    seen: dict[str, int] = {}
    for index, entry in enumerate(manifest.get("addons", [])):
        ident = entry.get("id", f"<entry {index}>")

        if ident in seen:
            errors.append(f"{ident}: duplicate id (also entry {seen[ident]})")
        seen[ident] = index

        kind = entry.get("type", "")
        path = entry.get("path", "")

        payload = check_asset(f"{ident}.path", path, errors, warnings) if path else None

        suffix = EXPECTED_SUFFIX.get(kind)
        if suffix and path and not is_remote(path) and not path.endswith(suffix):
            expected = suffix if isinstance(suffix, str) else " or ".join(suffix)
            warnings.append(f"{ident}: type {kind} usually ends in {expected} — got {path}")

        if payload is not None:
            declared_size = entry.get("sizeBytes")
            actual_size = payload.stat().st_size
            if declared_size is not None and declared_size != actual_size:
                errors.append(
                    f"{ident}: sizeBytes says {declared_size}, file is {actual_size}"
                )

            declared_hash = entry.get("sha256")
            if declared_hash is not None:
                actual_hash = sha256_of(payload)
                if declared_hash != actual_hash:
                    errors.append(
                        f"{ident}: sha256 mismatch\n"
                        f"    declared {declared_hash}\n"
                        f"    actual   {actual_hash}"
                    )

            if declared_hash is None and declared_size is None:
                warnings.append(
                    f"{ident}: no sha256/sizeBytes — valid, but the app will show it "
                    f"as unverified (run tools/build_index.py to fill them in)"
                )

        for preview in entry.get("previews", []):
            check_asset(f"{ident}.previews", preview, errors, warnings)

        if kind == "dictionary" and not entry.get("langId"):
            errors.append(f"{ident}: dictionaries must declare a langId")

    icon = manifest.get("repo", {}).get("icon")
    if icon:
        check_asset("repo.icon", icon, errors, warnings)

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}", file=sys.stderr)

    count = len(manifest.get("addons", []))
    if errors:
        print(f"\n{len(errors)} error(s) in {count} addons", file=sys.stderr)
        return 1

    print(f"\nok — {count} addons, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
