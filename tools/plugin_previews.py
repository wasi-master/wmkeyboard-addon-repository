"""The rules for a plugin's `previews` and `syntax`, shared by build_plugins.py
and validate.py. Mirrors PluginPreviewRules and PluginSyntax in the app.

A preview names the file types it reads and needs the `previews` permission
(and the permission needs a preview). A grammar is inline or an
`assets/<name>.json` file; its rule expressions are compiled with ICU, the
engine Android runs them on, when the platform has it (libicucore on macOS,
libicui18n on Linux), else with Python's `re` plus the one difference that
bites: ICU refuses a lone `}`.
"""

from __future__ import annotations

import ctypes
import glob
import json
import re
import sys
from typing import Callable

ID = re.compile(r"[a-z0-9_-]{1,32}")
EXTENSION = re.compile(r"[a-z0-9][a-z0-9._+-]{0,15}")
FILE_NAME = re.compile(r"[A-Za-z0-9._+-]{1,40}")
MIME = re.compile(r"[a-z0-9][a-z0-9.+-]*/([a-z0-9][a-z0-9.+_-]*\*?|\*)")
GRAMMAR_ASSET = re.compile(r"assets/[a-z0-9][a-z0-9_.-]{0,59}\.json")
KINDS = {
    "comment", "string", "number", "keyword", "type", "function", "operator", "tag", "attribute",
    "heading", "link", "emphasis", "constant", "punctuation",
}
MAX_PREVIEWS = 16
MAX_SYNTAX = 16
MAX_RULES = 200
MAX_PATTERN = 512
MAX_WORDS = 2000
MAX_BYTES = 16 * 1024 * 1024

_icu = None


def _load_icu():
    """uregex_open from the platform's ICU, or None."""
    global _icu
    if _icu is not None:
        return _icu or None
    try:
        if sys.platform == "darwin":
            lib = ctypes.CDLL("/usr/lib/libicucore.dylib")
            _icu = (lib.uregex_open, lib.uregex_close)
        else:
            found = sorted(glob.glob("/usr/lib/*/libicui18n.so.*") + glob.glob("/usr/lib*/libicui18n.so.*"))
            if not found:
                _icu = False
                return None
            lib = ctypes.CDLL(found[-1])
            version = found[-1].rsplit(".so.", 1)[1].split(".")[0]
            _icu = (getattr(lib, f"uregex_open_{version}"), getattr(lib, f"uregex_close_{version}"))
    except (OSError, AttributeError):
        _icu = False
        return None
    return _icu


def regex_problem(pattern: str, flags: str = "") -> str | None:
    """Why Android would refuse [pattern], or None."""
    icu = _load_icu()
    if icu:
        open_, close = icu
        open_.restype = ctypes.c_void_p
        utf16 = pattern.encode("utf-16-le")
        status = ctypes.c_int(0)
        bits = (2 if "i" in flags else 0) | (8 if "m" in flags else 0) | (32 if "s" in flags else 0)
        handle = open_(ctypes.c_char_p(utf16), ctypes.c_int32(len(utf16) // 2), ctypes.c_uint32(bits), None, ctypes.byref(status))
        if handle:
            close(ctypes.c_void_p(handle))
        return f"ICU error {status.value}" if status.value > 0 else None
    try:
        re.compile(pattern)
    except re.error as error:
        return str(error)
    if re.search(r"(^|[^\\])\}", re.sub(r"\{[^{}]*\}", "", pattern)):
        return 'a lone "}" (Android needs "\\}")'
    return None


def grammar_problem(grammar) -> str | None:
    """What the app's PluginSyntax.compile refuses about [grammar], or None."""
    if not isinstance(grammar, dict):
        return "is not an object"
    rules = grammar.get("rules", [])
    if not isinstance(rules, list) or len(rules) > MAX_RULES:
        return f"has more than {MAX_RULES} rules"
    for i, rule in enumerate(rules, 1):
        if not isinstance(rule, dict):
            return f"rule {i} is not an object"
        match = rule.get("match")
        if not isinstance(match, str) or not 1 <= len(match) <= MAX_PATTERN:
            return f"rule {i}: a match is 1 to {MAX_PATTERN} characters"
        if rule.get("kind") not in KINDS:
            return f"rule {i}: no kind {rule.get('kind')!r}"
        flags = str(rule.get("flags", "")) + ("i" if grammar.get("caseInsensitive") else "")
        why = regex_problem(match, flags)
        if why:
            return f"rule {i} ({match!r}): {why}"
    for key in ("keywords", "types", "constants"):
        words = grammar.get(key, [])
        if not isinstance(words, list) or len(words) > MAX_WORDS:
            return f'"{key}" is a list of up to {MAX_WORDS} words'
    for key in ("lineComment", "strings"):
        value = grammar.get(key)
        if value is not None and not isinstance(value, (str, list)):
            return f'"{key}" is a marker or a list of them'
    block = grammar.get("blockComment")
    if block is not None:
        pairs = block if block and isinstance(block[0], list) else [block]
        if not all(isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) and x for x in p) for p in pairs):
            return '"blockComment" is ["open", "close"] or a list of pairs'
    return None


def _strings(value) -> list[str] | None:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return None
    return value


def preview_problems(manifest: dict, read: Callable[[str], bytes | None]) -> list[str]:
    """What the app refuses about [manifest]'s previews and syntax. [read]
    returns an archived file's bytes, or None when it is not there."""
    out: list[str] = []
    previews = manifest.get("previews", [])
    syntax = manifest.get("syntax", [])
    permissions = manifest.get("permissions", [])
    if not isinstance(previews, list) or not isinstance(syntax, list):
        return ['"previews" and "syntax" are lists']
    if (previews or syntax) and manifest.get("apiVersion") != 5:
        out.append('"previews" and "syntax" need apiVersion 5')
    if previews and "previews" not in permissions:
        out.append('"previews" needs the "previews" permission')
    if not previews and "previews" in permissions:
        out.append('the "previews" permission without any "previews"')
    if len(previews) > MAX_PREVIEWS:
        out.append(f"{len(previews)} previews; the app caps at {MAX_PREVIEWS}")
    seen = set()
    for p in previews:
        if not isinstance(p, dict):
            out.append("a preview is not an object")
            continue
        pid = p.get("id")
        if not isinstance(pid, str) or not ID.fullmatch(pid) or pid in seen:
            out.append(f"preview id {pid!r} must be unique, a-z 0-9 _ -, up to 32")
        seen.add(pid)
        if isinstance(p.get("name"), str) and len(p["name"]) > 24:
            out.append(f"preview {pid!r}: name is over 24 characters")
        ext, names, mimes = _strings(p.get("extensions")), _strings(p.get("names")), _strings(p.get("mimes"))
        if ext is None or len(ext) > 64 or not all(EXTENSION.fullmatch(e) for e in ext):
            out.append(f"preview {pid!r}: extensions are up to 64, lower case, without the dot")
        if names is None or len(names) > 16 or not all(FILE_NAME.fullmatch(n) for n in names):
            out.append(f"preview {pid!r}: names are up to 16 plain file names")
        if mimes is None or len(mimes) > 16 or not all(MIME.fullmatch(m) for m in mimes):
            out.append(f"preview {pid!r}: mimes are up to 16 types such as \"text/csv\" or \"application/vnd.ms-*\"")
        if not (ext or names or mimes):
            out.append(f"preview {pid!r} lists no extensions, names or mimes")
        size = p.get("maxBytes")
        if size is not None and (not isinstance(size, int) or not 1 <= size <= MAX_BYTES):
            out.append(f"preview {pid!r}: maxBytes is 1 to {MAX_BYTES}")
        if "thumbnails" in p and not isinstance(p["thumbnails"], bool):
            out.append(f"preview {pid!r}: thumbnails is true or false")
    if len(syntax) > MAX_SYNTAX:
        out.append(f"{len(syntax)} grammars; the app caps at {MAX_SYNTAX}")
    seen = set()
    for s in syntax:
        if not isinstance(s, dict):
            out.append("a grammar is not an object")
            continue
        sid = s.get("id")
        if not isinstance(sid, str) or not ID.fullmatch(sid) or sid in seen:
            out.append(f"grammar id {sid!r} must be unique, a-z 0-9 _ -, up to 32")
        seen.add(sid)
        ext, names = _strings(s.get("extensions")), _strings(s.get("names"))
        if ext is None or len(ext) > 32 or not all(EXTENSION.fullmatch(e) for e in ext):
            out.append(f"grammar {sid!r}: extensions are up to 32, lower case, without the dot")
        if names is None or len(names) > 16 or not all(FILE_NAME.fullmatch(n) for n in names):
            out.append(f"grammar {sid!r}: names are up to 16 plain file names")
        if not (ext or names):
            out.append(f"grammar {sid!r} lists no extensions or names")
        grammar = s.get("grammar")
        if isinstance(grammar, str):
            if not GRAMMAR_ASSET.fullmatch(grammar):
                out.append(f'grammar {sid!r}: "grammar" is an object, or "assets/<name>.json"')
                continue
            data = read(grammar)
            if data is None:
                out.append(f"grammar {sid!r} names {grammar}, which is not in the archive")
                continue
            try:
                grammar = json.loads(data)
            except ValueError as error:
                out.append(f"grammar {sid!r}: {s['grammar']} is not JSON: {error}")
                continue
        why = grammar_problem(grammar)
        if why:
            out.append(f"grammar {sid!r} {why}")
    return out
