#!/usr/bin/env python3
"""Validate wmkeyboard-repo.json before publishing it.

Two passes:

1. The JSON Schema at ``docs/addons/wmkeyboard-repo.schema.json`` (draft 2020-12).
2. The things a schema cannot express — that every ``path``, ``previews[]``,
   ``licenseFile`` and ``repo.icon`` resolves to a file that is actually here,
   that ids are unique, that any checksum present is correct, and that each
   ``localizations[]`` item is one the app will actually keep.

``sha256`` and ``sizeBytes`` are **optional**. A manifest without them is valid
and installs fine; they are only checked when a publisher chose to provide them.

    python3 tools/validate.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
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
    "sound_pack": ".wmsoundpack",
    "plugin": ".wmplugin",
    "vocabulary": (".wmvocab.json", ".wmvocab.json.gz"),
}

# Types whose payload is executable code rather than data. The rules are
# stricter for these: the app refuses to install one without a checksum,
# because "unverified" is not a state code gets to be in.
EXECUTABLE_TYPES = {"plugin"}

# Mirrors PluginPermission.kt. A permission the app does not recognise makes
# it refuse the install outright, so publishing one ships a dead plugin.
KNOWN_PLUGIN_PERMISSIONS = {
    "storage", "reminders", "selection",
    # API 5
    "network", "network.local", "ai", "field.read", "field.write", "clipboard.read", "clipboard.write",
    "location", "files", "sensors", "scan", "device", "share", "notifications", "calendar", "todo", "clock",
}

# The app's PluginManifestCodec.API_VERSION. 4 is Python, which replaced Lua:
# 2 added wm.reminders and ui.date, 3 selection actions, 4 the switch, 5 the
# wm package, the host modules and their permissions.
PLUGIN_API_VERSION = 5

# The permissions API 5 added; a manifest below 5 may not declare them.
API_5_PERMISSIONS = KNOWN_PLUGIN_PERMISSIONS - {"storage", "reminders", "selection"}

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
    # network.local only widens a host setting; without both it grants nothing.
    if "network.local" in permissions and ("network" not in permissions or not host_setting):
        out.append("\"network.local\" needs \"network\" and a \"host\" setting")
    # A secret row is kept in the plugin's secrets, which need storage.
    if any(isinstance(s, dict) and s.get("type") == "secret" for s in manifest.get("settings", [])) and "storage" not in permissions:
        out.append("a \"secret\" setting needs the \"storage\" permission")
    return out

# The types whose payload is in one language, and so can carry `localizations`.
LOCALIZABLE_TYPES = {"dictionary", "emoji_keywords", "vocabulary"}

# Mirrors AddonRepoCodec: a registered language id, optionally a hyphen and a
# region (es, es-419, pt-BR). The app drops anything else.
LOCALE_PATTERN = re.compile(r"[a-z]{2,3}(_[a-z0-9]+)*(-[A-Za-z0-9]{2,8})?")

LANG_IDS_FILE = ROOT / "tools" / "lang_ids.txt"


def known_lang_ids() -> set[str]:
    """The app's registered language ids, from the snapshot in tools/lang_ids.txt."""
    lines = LANG_IDS_FILE.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def check_plugin(ident, payload, errors, warnings):
    """Reads a .wmplugin's manifest and checks what the app will check.

    Catching this here means a broken plugin fails in CI rather than silently
    refusing to install on someone's phone with a message they can't act on.
    """
    try:
        with zipfile.ZipFile(payload) as archive:
            names = set(archive.namelist())
            if "plugin.json" not in names:
                errors.append(f"{ident}: no plugin.json in the archive")
                return
            manifest = json.loads(archive.read("plugin.json"))
            entry_name = manifest.get("entry", "main.py")
            if entry_name not in names:
                errors.append(f"{ident}: entry {entry_name} is missing from the archive")
            elif not entry_name.endswith(".py"):
                errors.append(
                    f"{ident}: entry {entry_name} is not a .py file — plugins are "
                    f"Python, and the app no longer runs Lua"
                )
            else:
                script = archive.read(entry_name)
                try:
                    script.decode("utf-8")
                except UnicodeDecodeError:
                    errors.append(
                        f"{ident}: {entry_name} is not UTF-8 text — plugins must ship "
                        f"source so their code can be read before it runs"
                    )
    except (zipfile.BadZipFile, KeyError, ValueError) as error:
        errors.append(f"{ident}: unreadable plugin archive — {error}")
        return

    if manifest.get("format") != "wmkeyboard-plugin":
        errors.append(f"{ident}: plugin.json format must be 'wmkeyboard-plugin'")
    for field in ("id", "name", "pluginVersion"):
        if not manifest.get(field):
            errors.append(f"{ident}: plugin.json is missing {field}")
    plugin_id = manifest.get("id", "")
    if plugin_id and not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", plugin_id):
        errors.append(
            f"{ident}: plugin id {plugin_id!r} must be lowercase, 3-64 characters, "
            f"and only letters, numbers, dots, dashes and underscores"
        )
    language = manifest.get("language")
    api_version = manifest.get("apiVersion", 1)
    if language == "lua" or (language is None and isinstance(api_version, int) and api_version <= 3):
        errors.append(
            f"{ident}: written in Lua, which WM Keyboard no longer runs — "
            f"port it to Python (apiVersion {PLUGIN_API_VERSION}, entry main.py)"
        )
    elif language not in (None, "python"):
        errors.append(f"{ident}: unknown plugin language {language!r} — only \"python\"")
    if not isinstance(api_version, int) or api_version > PLUGIN_API_VERSION:
        warnings.append(
            f"{ident}: apiVersion {api_version} is newer than this "
            f"validator knows — current app versions will refuse it"
        )
    permissions = manifest.get("permissions", [])
    for permission in permissions:
        if permission not in KNOWN_PLUGIN_PERMISSIONS:
            errors.append(
                f"{ident}: unknown permission {permission!r} — the app refuses to "
                f"install a plugin whose capabilities it cannot explain"
            )
        elif permission in API_5_PERMISSIONS and api_version != 5:
            errors.append(f"{ident}: permission {permission!r} needs apiVersion 5")
    errors.extend(f"{ident}: {problem}" for problem in host_problems(manifest, permissions))


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


def check_payload_checksums(
    ident: str, payload: Path, holder: dict, errors: list[str], warnings: list[str]
) -> None:
    """Compare a declared sizeBytes/sha256 (on an entry or a localization) with the file."""
    declared_size = holder.get("sizeBytes")
    actual_size = payload.stat().st_size
    if declared_size is not None and declared_size != actual_size:
        errors.append(f"{ident}: sizeBytes says {declared_size}, file is {actual_size}")

    declared_hash = holder.get("sha256")
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


def check_localizations(
    ident: str, entry: dict, lang_ids: set[str], errors: list[str], warnings: list[str]
) -> None:
    """Check what the app's codec would silently drop, so it fails here instead."""
    localizations = entry.get("localizations")
    if not localizations:
        return
    kind = entry.get("type", "")
    if kind not in LOCALIZABLE_TYPES:
        warnings.append(f"{ident}: localizations are ignored for type {kind}")
        return

    base = entry.get("langId", "")
    seen: set[str] = set()
    for index, item in enumerate(localizations):
        locale = item.get("locale", "")
        where = f"{ident}@{locale or index}"
        if not LOCALE_PATTERN.fullmatch(locale):
            errors.append(f"{where}: malformed locale {locale!r} — the app drops it")
            continue
        language = locale.split("-", 1)[0]
        if language not in lang_ids:
            errors.append(
                f"{where}: {language!r} is not a language the app registers "
                f"(tools/lang_ids.txt)"
            )
        if locale == base:
            errors.append(f"{where}: repeats the entry's own langId — the app drops it")
        if locale in seen:
            errors.append(f"{where}: duplicate locale — the app keeps only the first")
        seen.add(locale)

        path = item.get("path", "")
        if not path:
            errors.append(f"{where}: no path — the app drops it")
            continue
        payload = check_asset(f"{where}.path", path, errors, warnings)
        suffix = EXPECTED_SUFFIX.get(kind)
        if suffix and not is_remote(path) and not path.endswith(suffix):
            expected = suffix if isinstance(suffix, str) else " or ".join(suffix)
            warnings.append(f"{where}: type {kind} usually ends in {expected} — got {path}")
        if payload is not None:
            check_payload_checksums(where, payload, item, errors, warnings)


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


def check_snippet_pack(ident: str, payload: Path, errors: list[str], warnings: list[str]) -> None:
    """Check that a snippet pack parses and that every trigger pattern compiles.

    A snippet whose ``triggerPattern`` will not compile is not refused by the
    app — the pattern is dropped and the snippet stays, which is the right
    behaviour on a phone and the wrong one for a publisher, who then ships a
    pack whose triggers silently do nothing. Catch it here instead.

    Python's ``re`` is not Java's, but the two agree on everything a snippet
    pattern uses, so a failure here is a real failure. The nesting and
    backreference screens mirror the app's own; see ``SnippetMatcher.validate``.
    """
    import re as _re

    MAX_PATTERN_LENGTH = 200
    MAX_WORDS = 8

    try:
        manifest = json.loads(payload.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"{ident}: cannot read the snippet pack — {e}")
        return

    if manifest.get("format") != "wmkeyboard-snippets":
        errors.append(f"{ident}: format is not wmkeyboard-snippets")
        return

    snippets = manifest.get("snippets") or []
    if not snippets:
        errors.append(f"{ident}: the pack lists no snippets — the app refuses an empty one")
        return

    for snippet in snippets:
        name = snippet.get("label") or snippet.get("id") or "?"
        if not (snippet.get("text") or "").strip():
            errors.append(f"{ident}: snippet {name!r} has no text, so the app drops it")
        pattern = (snippet.get("triggerPattern") or "").strip()
        words = snippet.get("triggerWords", 0)
        if not isinstance(words, int) or not 0 <= words <= MAX_WORDS:
            warnings.append(
                f"{ident}: snippet {name!r} asks for triggerWords={words}; "
                f"the app clamps it to 0..{MAX_WORDS}"
            )
        if not pattern:
            continue
        if snippet.get("trigger"):
            warnings.append(
                f"{ident}: snippet {name!r} has both trigger and triggerPattern; "
                f"the app keeps the word and ignores the pattern"
            )
        if len(pattern) > MAX_PATTERN_LENGTH:
            errors.append(
                f"{ident}: snippet {name!r} has a {len(pattern)}-character pattern; "
                f"the app drops anything over {MAX_PATTERN_LENGTH}"
            )
            continue
        try:
            # Java spells a named group (?<name>…), Python (?P<name>…). A group
            # called "name" only takes words that read as a name in the app.
            _re.compile(_re.sub(r"\(\?<(?=[A-Za-z])", "(?P<", pattern))
        except _re.error as e:
            errors.append(f"{ident}: snippet {name!r} has a pattern that will not compile — {e}")
            continue
        if _re.search(r"\\[1-9]|\\k<", pattern):
            errors.append(
                f"{ident}: snippet {name!r} uses a backreference; the app refuses those"
            )
        if _re.search(r"\([^()]*[*+?][^()]*\)[*+?{]", pattern):
            errors.append(
                f"{ident}: snippet {name!r} quantifies a group that is already quantified "
                f"(the (a+)+ shape); the app refuses those"
            )
        if not _re.match(r"\^?(?:\(\?[idmsuxU-]+\)\^?)?[\w/@#.-]{2,}", pattern):
            warnings.append(
                f"{ident}: snippet {name!r} has no plain word at the start of its pattern, "
                f"so the keyboard tries it after every word the user types"
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

    lang_ids = known_lang_ids()
    seen: dict[str, int] = {}
    for index, entry in enumerate(manifest.get("addons", [])):
        ident = entry.get("id", f"<entry {index}>")

        if "@" in ident:
            errors.append(f"{ident}: '@' is reserved for localized install keys — the app refuses the entry")
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
            check_payload_checksums(ident, payload, entry, errors, warnings)

            if kind == "icon_pack":
                check_icon_pack(ident, payload, errors, warnings)
            elif kind == "stickers":
                check_sticker_pack(ident, payload, errors, warnings)
            elif kind == "snippets":
                check_snippet_pack(ident, payload, errors, warnings)
            elif kind == "emoji_font":
                check_emoji_font(ident, payload, errors, warnings)
            elif kind == "plugin":
                check_plugin(ident, payload, errors, warnings)

            # For code, the checksum is the install gate rather than a badge:
            # the app refuses a plugin that has none, so publishing one without
            # is publishing something nobody can install.
            if kind in EXECUTABLE_TYPES and not entry.get("sha256"):
                errors.append(
                    f"{ident}: a {kind} must declare a sha256 — the app refuses to "
                    f"install code it cannot verify (run tools/build_index.py)"
                )

        for preview in entry.get("previews", []):
            check_asset(f"{ident}.previews", preview, errors, warnings)

        licence_file = entry.get("licenseFile")
        if licence_file:
            check_asset(f"{ident}.licenseFile", licence_file, errors, warnings)

        if kind in ("dictionary", "vocabulary") and not entry.get("langId"):
            errors.append(f"{ident}: dictionaries must declare a langId")

        check_localizations(ident, entry, lang_ids, errors, warnings)

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
