"""The rules for a plugin's tool icon, shared by build_plugins.py and validate.py.

A plugin's `tool.icon` is what the keyboard draws for it on the toolbar, in the
toolbox, on the floating button and on its rows in Settings. It is either a
Material Symbols name the app carries (`kitchen`, `directions_transit`) or
`assets/<file>.svg`, a one-colour 24x24 drawing the app tints like its own
icons. Mirrors PluginManifestCodec.packageProblems and PluginToolIcons.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Callable

# PluginManifestCodec.ICON.
ICON_PATTERN = re.compile(r"([a-z0-9_]{0,48}|assets/[a-z0-9][a-z0-9_.-]{0,59}\.svg)")

# SvgParser.MAX_SOURCE_BYTES: a bigger file is the jigsaw.
MAX_SVG_BYTES = 256 * 1024

# Paints that keep the drawing one colour. The app tints the icon, so any
# other colour is lost; flagging it catches a drawing exported from a tool
# that hard-coded black or a brand colour.
PLAIN_PAINTS = {"none", "currentcolor", "#000", "#000000", "black"}

# The names the app resolves, from WMKeyboard's generated SymbolNames.kt, when
# a checkout sits beside this repository. Without it the name is not checked.
SYMBOL_NAMES_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "WMKeyboard/core/icons/src/main/java/com/wasimaster/wmkeyboard/core/icons/SymbolNames.kt"
)


def known_symbol_names() -> set[str] | None:
    """The symbol names the app carries, or None when no app checkout is beside this one."""
    if not SYMBOL_NAMES_FILE.is_file():
        return None
    text = SYMBOL_NAMES_FILE.read_text(encoding="utf-8")
    return set(re.findall(r'^\s*"([a-z0-9_]+)" ->', text, re.MULTILINE))


def svg_problems(name: str, data: bytes) -> list[str]:
    """What keeps an SVG from being a tool icon: size, shape, colours."""
    if len(data) > MAX_SVG_BYTES:
        return [f"{name} is over 256 KB; the app draws the jigsaw instead"]
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        return [f"{name} is not well-formed SVG ({error})"]
    out = []
    if not root.tag.endswith("svg"):
        out.append(f"{name} is not an <svg> document")
    view_box = (root.get("viewBox") or "").split()
    if view_box != ["0", "0", "24", "24"]:
        out.append(f"{name} needs viewBox=\"0 0 24 24\", like the Material Symbols it sits beside")
    colours = set()
    for element in root.iter():
        for attribute in ("fill", "stroke"):
            value = element.get(attribute)
            if value is not None and value.strip().lower() not in PLAIN_PAINTS:
                colours.add(value.strip())
        if element.get("style") and re.search(r"(fill|stroke)\s*:\s*(?!none|currentColor)", element.get("style"), re.IGNORECASE):
            colours.add(element.get("style"))
        if element.tag.endswith(("image", "text", "linearGradient", "radialGradient")):
            out.append(f"{name} holds <{element.tag.split('}')[-1]}>; a tool icon is plain shapes")
    if colours:
        out.append(f"{name} paints in {', '.join(sorted(colours))}; use currentColor, the app tints the icon")
    return out


def tool_problems(manifest: dict, read: Callable[[str], bytes | None]) -> tuple[list[str], list[str]]:
    """Errors and warnings about the `tool` block. [read] returns a file of the archive or source, or None."""
    errors: list[str] = []
    warnings: list[str] = []
    tool = manifest.get("tool", {})
    if not isinstance(tool, dict):
        return ["\"tool\" must be an object"], warnings
    api = manifest.get("apiVersion", 1)
    # An icon name is the one tool field an API 4 plugin may carry.
    if api != 5 and any(key != "icon" for key in tool):
        errors.append("a \"tool\" block beyond \"icon\" needs apiVersion 5")
    icon = str(tool.get("icon", "")).strip()
    if not ICON_PATTERN.fullmatch(icon):
        errors.append(f"tool.icon {icon!r} is neither a Material Symbols name nor \"assets/<file>.svg\"")
    elif icon.startswith("assets/"):
        if api != 5:
            errors.append(f"tool.icon {icon} is a file, and only apiVersion 5 archives ship assets/")
        else:
            data = read(icon)
            if data is None:
                errors.append(f"tool.icon names {icon}, which is not in the plugin")
            else:
                errors.extend(svg_problems(icon, data))
    elif icon:
        names = known_symbol_names()
        if names is not None and icon not in names:
            warnings.append(f"tool.icon {icon!r} is not a symbol the app carries; it draws the jigsaw")
    else:
        warnings.append("no tool.icon; the plugin draws as the jigsaw")
    return errors, warnings
