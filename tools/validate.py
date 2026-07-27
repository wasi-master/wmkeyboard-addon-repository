#!/usr/bin/env python3
"""Validate wmkeyboard-repo.json before publishing it.

Two passes:

1. The JSON Schema at ``docs/addons/wmkeyboard-repo.schema.json`` (draft 2020-12).
2. The things a schema cannot express — that every ``path``, ``previews[]``,
   ``licenseFile`` and ``repo.icon`` resolves to a file that is actually here,
   that ids are unique, and that any checksum present is correct.

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
    "emoji_font": (".ttf", ".otf"),
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


def check_icon_pack(ident: str, payload: Path, errors: list[str], warnings: list[str]) -> None:
    """Validate .wmicons ZIP structure, SVG XML, width/height, and arc path data formatting."""
    import re
    import xml.etree.ElementTree as ET
    import zipfile

    arc_pattern = re.compile(r"[Aa]\s*[\d\.]+\s+[\d\.]+\s+[\d\.]+\s+([01]{2}(?=[-\d]))")

    try:
        with zipfile.ZipFile(payload, "r") as z:
            names = z.namelist()
            if "pack.json" not in names:
                errors.append(f"{ident}: missing pack.json in .wmicons archive")
            for name in names:
                if name.startswith("icons/") and name.endswith(".svg"):
                    svg_bytes = z.read(name)
                    try:
                        root = ET.fromstring(svg_bytes)
                        w = root.attrib.get("width")
                        h = root.attrib.get("height")
                        if not w or not h:
                            warnings.append(
                                f"{ident}: {name}: SVG omits explicit width/height attributes"
                            )
                    except Exception as e:
                        errors.append(f"{ident}: {name}: invalid SVG XML — {e}")

                    content = svg_bytes.decode("utf-8", errors="replace")
                    matches = arc_pattern.findall(content)
                    if matches:
                        errors.append(
                            f"{ident}: {name}: compressed arc flags without spaces ({matches[0]}) may break Android path parsing"
                        )
    except Exception as e:
        errors.append(f"{ident}: corrupt .wmicons ZIP file — {e}")


def check_sticker_pack(ident: str, payload: Path, errors: list[str], warnings: list[str]) -> None:
    """Check that pack.json declares stickers and that each one names a real archive entry.

    The app writes `stickers[]` inside `pack`; it also reads a top-level
    `stickers[]`, `file` for `fileName`, and a path where a bare name belongs,
    because that is what hand-written packs do. What it cannot do is invent
    images — a manifest whose entries name nothing in the archive installs as an
    empty pack, which is how this check came to exist.
    """
    import json as _json
    import posixpath
    import zipfile

    try:
        with zipfile.ZipFile(payload, "r") as z:
            names = set(z.namelist())
            if "pack.json" not in names:
                errors.append(f"{ident}: missing pack.json in .wmstickers archive")
                return
            manifest = _json.loads(z.read("pack.json"))
    except Exception as e:
        errors.append(f"{ident}: corrupt .wmstickers ZIP file — {e}")
        return

    if manifest.get("format") != "wmkeyboard-stickers":
        errors.append(f"{ident}: pack.json format is not wmkeyboard-stickers")
        return

    pack = manifest.get("pack") or {}
    declared = pack.get("stickers") or manifest.get("stickers") or []
    if not declared:
        errors.append(f"{ident}: pack.json lists no stickers — the app refuses an empty pack")
        return
    if "stickers" not in pack:
        warnings.append(
            f"{ident}: stickers[] sits beside pack rather than inside it — accepted, "
            f"but the app's own export nests it"
        )

    tails = {posixpath.basename(n): n for n in names if n != "pack.json"}
    missing = []
    for sticker in declared:
        source = (sticker.get("fileName") or sticker.get("file") or "").strip()
        if not source:
            missing.append(sticker.get("id", "?"))
            continue
        if source in names or f"stickers/{source}" in names:
            continue
        if posixpath.basename(source) in tails:
            continue
        missing.append(sticker.get("id") or source)

    if missing:
        shown = ", ".join(missing[:5]) + (f" …and {len(missing) - 5} more" if len(missing) > 5 else "")
        errors.append(
            f"{ident}: {len(missing)} of {len(declared)} stickers name no image in the "
            f"archive ({shown})"
        )


def check_emoji_font(ident: str, payload: Path, errors: list[str], warnings: list[str]) -> None:
    """Check GSUB ZWJ ligature coverage in emoji fonts if fontTools is installed."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return

    try:
        font = TTFont(payload)
        if "GSUB" not in font:
            warnings.append(f"{ident}: GSUB table missing in emoji font")
            return

        gsub = font["GSUB"].table
        seqs_with_fe0f = set()
        seqs_without_fe0f = set()

        for lookup in gsub.LookupList.Lookup:
            for subtable in lookup.SubTable:
                if hasattr(subtable, "ligatures"):
                    for first, lig_list in subtable.ligatures.items():
                        for lig in lig_list:
                            comps = [first] + lig.Component
                            if "ufe0f" in comps and len(comps) > 2:
                                key = tuple(c for c in comps if c != "ufe0f")
                                seqs_with_fe0f.add(key)
                            elif len(comps) > 1:
                                seqs_without_fe0f.add(tuple(comps))

        missing_variants = seqs_with_fe0f - seqs_without_fe0f
        if missing_variants:
            warnings.append(
                f"{ident}: {len(missing_variants)} multi-character ZWJ ligatures require ufe0f but lack non-ufe0f fallback rules"
            )
    except Exception as e:
        errors.append(f"{ident}: font parsing error — {e}")


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

            if kind == "icon_pack":
                check_icon_pack(ident, payload, errors, warnings)
            elif kind == "stickers":
                check_sticker_pack(ident, payload, errors, warnings)
            elif kind == "emoji_font":
                check_emoji_font(ident, payload, errors, warnings)

        for preview in entry.get("previews", []):
            check_asset(f"{ident}.previews", preview, errors, warnings)

        licence_file = entry.get("licenseFile")
        if licence_file:
            check_asset(f"{ident}.licenseFile", licence_file, errors, warnings)

        if kind == "dictionary" and not entry.get("langId"):
            errors.append(f"{ident}: dictionaries must declare a langId")

        # Not required, but an addon whose licence nobody can find is one
        # nobody can safely reuse — and for a font or an icon set that is the
        # first thing a publisher is asked.
        if not any(entry.get(k) for k in ("license", "licenseText", "licenseFile")):
            warnings.append(f"{ident}: no licence stated")

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
