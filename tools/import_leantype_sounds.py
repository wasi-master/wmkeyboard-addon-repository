#!/usr/bin/env python3
"""Convert LeanType's CC0 sound packs into .wmsoundpack addons.

Takes a checkout of https://github.com/LeanBitLab/LeanType-SoundPacks and writes
sound_packs/leantype-<slug>.wmsoundpack, a preview card per pack, the licence
notice, and the matching wmkeyboard-repo.json entries. Run tools/build_index.py
afterwards for the checksums, then tools/gen_readme.py.

The audio is copied byte for byte. The manifest translation is the one the app's
LeanTypeSoundPack.kt applies when a user imports one of these zips directly:

    keypress.default                    top-level press
    keypress.space / delete / return    the space, delete and enter roles
    keypress.shift / symbol             both into the modifier role
    defaultMasterVolume x event volume  gain
    mode "single"                       the first file only
    mode "random" / "cycle"             every file

Needs ffmpeg (previews decode the recordings) and Pillow.
"""

import argparse
import colorsys
import json
import subprocess
import zipfile
from array import array
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "sound_packs"
PREVIEWS = ROOT / "previews"
LICENSE_NAME = "LEANTYPE-SOUNDS-LICENSE.txt"
SOURCE_URL = "https://github.com/LeanBitLab/LeanType-SoundPacks"
ZIP_TIME = (2026, 1, 1, 0, 0, 0)
# The first app version that knows sound_pack, as the Monkeytype repository declares.
MIN_APP_VERSION = 4

ROLE_EVENTS = {
    "space": ["keypress.space"],
    "enter": ["keypress.return"],
    "delete": ["keypress.delete"],
    "modifier": ["keypress.shift", "keypress.symbol"],
}


def samples(event: dict) -> list[str]:
    files = event.get("files", [])
    return files if event.get("mode", "single") != "single" else files[:1]


def translate(source: dict, addon_id: str) -> dict:
    master = source.get("defaultMasterVolume", 1.0)

    def gain(event: dict) -> float:
        return round(master * event.get("volume", 1.0), 4)

    sounds = source["sounds"]
    roles = {}
    for role, names in ROLE_EVENTS.items():
        events = [sounds[n] for n in names if n in sounds and samples(sounds[n])]
        if events:
            press = list(dict.fromkeys(f for e in events for f in samples(e)))
            roles[role] = {"press": press, "gain": gain(events[0])}

    default = sounds["keypress.default"]
    return {
        "format": "wmkeyboard-sound-pack",
        "version": 1,
        "id": addon_id,
        "name": source["name"],
        "author": source["author"],
        "packVersion": source["versionName"],
        "description": source["summary"],
        "gain": gain(default),
        "press": samples(default),
        "roles": roles,
    }


def write_pack(manifest: dict, pack_dir: Path, out: Path) -> None:
    """A stable archive: same input, same bytes, so a re-run changes no checksum."""
    paths = list(manifest["press"])
    for spec in manifest["roles"].values():
        paths += spec["press"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        def add(name: str, data: bytes) -> None:
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)

        add("pack.json", json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))
        for path in sorted(set(paths)):
            add(path, (pack_dir / path).read_bytes())


def decode(path: Path, rate: int = 16000) -> array:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(rate), "-"],
        check=True,
        capture_output=True,
    ).stdout
    pcm = array("h")
    pcm.frombytes(raw[: len(raw) // 2 * 2])
    return pcm


def draw_wave(draw, box, pcm, color) -> None:
    left, top, right, bottom = box
    middle = (top + bottom) / 2
    columns = int((right - left) / 6)
    peak = max((abs(s) for s in pcm), default=1) or 1
    step = max(1, len(pcm) // columns)
    for index in range(columns):
        chunk = pcm[index * step : (index + 1) * step]
        level = max((abs(s) for s in chunk), default=0) / peak
        height = max(2.0, level * (bottom - top) / 2)
        x = left + index * 6
        draw.rounded_rectangle([x, middle - height, x + 3, middle + height], radius=1.5, fill=color)


def write_preview(manifest: dict, pack_dir: Path, slug: str, out: Path) -> None:
    hue = sum(map(ord, slug)) * 47 % 360 / 360
    def tone(light, sat):
        return tuple(int(c * 255) for c in colorsys.hls_to_rgb(hue, light, sat))

    width, height = 720, 633
    image = Image.new("RGB", (width, height), tone(0.11, 0.35))
    draw = ImageDraw.Draw(image)
    title = ImageFont.truetype(str(ROOT / "fonts/inter.ttf"), 42)
    body = ImageFont.truetype(str(ROOT / "fonts/inter.ttf"), 22)
    small = ImageFont.truetype(str(ROOT / "fonts/inter.ttf"), 18)

    draw.text((44, 40), manifest["name"], fill=(248, 250, 252), font=title)
    draw.text((44, 98), manifest["description"], fill=tone(0.78, 0.35), font=body)

    rows = [("Letters", manifest["press"][0])]
    labels = {"space": "Space", "enter": "Enter", "delete": "Delete", "modifier": "Shift"}
    rows += [(labels[r], s["press"][0]) for r, s in manifest["roles"].items()]
    top = 160
    row_height = (height - top - 60) // len(rows)
    for index, (label, path) in enumerate(rows):
        y = top + index * row_height
        draw.text((44, y + row_height / 2 - 11), label, fill=tone(0.72, 0.3), font=small)
        box = (140, y + 8, width - 44, y + row_height - 8)
        draw_wave(draw, box, decode(pack_dir / path), tone(0.62, 0.7))

    draw.text((44, height - 42), "CC0 · LeanType Sound Lab", fill=tone(0.6, 0.25), font=small)
    image.save(out, "PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="checkout of LeanType-SoundPacks")
    parser.add_argument("--commit", required=True, help="the commit that checkout is at")
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / LICENSE_NAME).write_text(
        "The recordings in the leantype-*.wmsoundpack files in this directory come from\n"
        f"LeanType-SoundPacks by LeanType Sound Lab ({SOURCE_URL}),\n"
        f"at commit {args.commit}. They are synthesised and dedicated to the public\n"
        "domain under CC0 1.0 Universal. The audio is unchanged; only the manifest was\n"
        "rewritten, by tools/import_leantype_sounds.py.\n\n"
        + (args.source / "LICENSE").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    entries = []
    for pack_dir in sorted(p for p in (args.source / "packs").iterdir() if (p / "pack.json").is_file()):
        slug = pack_dir.name
        source = json.loads((pack_dir / "pack.json").read_text(encoding="utf-8"))
        if source.get("license") != "CC0-1.0":
            raise SystemExit(f"{slug}: expected CC0-1.0, found {source.get('license')}")
        addon_id = f"leantype-{slug}"
        manifest = translate(source, addon_id)
        write_pack(manifest, pack_dir, OUT_DIR / f"{addon_id}.wmsoundpack")
        keys = "space, enter, delete and shift" if "modifier" in manifest["roles"] else "space, enter and delete"
        write_preview(manifest, pack_dir, slug, PREVIEWS / f"{addon_id}.png")
        entries.append(
            {
                "id": addon_id,
                "type": "sound_pack",
                "name": source["name"],
                "version": source["versionName"],
                "author": source["author"],
                "description": f"{source['summary']} Synthesised, with its own sounds for {keys}. From LeanType's sound pack collection.",
                "tags": source.get("tags", []),
                "path": f"sound_packs/{addon_id}.wmsoundpack",
                "previews": [f"previews/{addon_id}.png"],
                "minAppVersion": MIN_APP_VERSION,
                "license": "CC0-1.0",
                "licenseFile": f"sound_packs/{LICENSE_NAME}",
            }
        )

    manifest_path = ROOT / "wmkeyboard-repo.json"
    repo = json.loads(manifest_path.read_text(encoding="utf-8"))
    kept = [a for a in repo["addons"] if not a["id"].startswith("leantype-")]
    # Directly after the other key sounds, where a reader of the catalog looks.
    last_sound = max(i for i, a in enumerate(kept) if a["type"] == "sound")
    repo["addons"] = kept[: last_sound + 1] + entries + kept[last_sound + 1 :]
    manifest_path.write_text(json.dumps(repo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(entries)} packs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
