#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
manifest = json.loads((ROOT / "wmkeyboard-repo.json").read_text(encoding="utf-8"))
addons = manifest.get("addons", [])

rows = []
for a in addons:
    aid = a["id"]
    name = a["name"]
    atype = a["type"]
    desc = a["description"]
    path = a["path"]
    previews = a.get("previews", [])

    if previews:
        prev_md = f'<img src="{previews[0]}" width="120" alt="{name} Preview" />'
    else:
        prev_md = "—"

    file_link = f"[`{path}`]({path})"

    rows.append(f"| **{name}** | `{atype}` | {desc} | {prev_md} | {file_link} |")

table_md = "\n".join(rows)

readme_content = f"""<div align="center">
  <img src="icon.png" width="128" height="128" alt="WM Keyboard Icon" />
  <h1>WM Keyboard Official Addons</h1>
  <p>Official addon repository for WM Keyboard: themes, layouts, dictionaries, snippet packs, stickers, icon packs, fonts, emoji fonts, and key sounds.</p>
</div>

---

## Addons Catalog

To add this repository in **WM Keyboard**, open **Settings → Addons → Add repository** and paste the repository URL:
`https://github.com/wasi-master/wmkeyboard-addon-repository`

| Addon | Type | Description | Preview | Payload File |
|---|---|---|---|---|
{table_md}

Everything is indexed by [`wmkeyboard-repo.json`](wmkeyboard-repo.json) at the repository root.

---

## Addon Details

**Icon packs.** Each of the four packs replaces all 90 icon slots (all 58 tools plus key glyphs, toolbar chrome and emoji category tabs) — drawn in [Lucide](https://lucide.dev)'s 24px outline set, [Boxicons](https://boxicons.com)' 24px vector set, [Bootstrap Icons](https://icons.getbootstrap.com)' vector set, and [Font Awesome Free](https://fontawesome.com)'s iconic solid set. The glyphs are uncoloured and adaptive, so they follow the keyboard theme and per-tool accent colours. Licences: Lucide ISC ([`icons/LUCIDE-LICENSE.txt`](icons/LUCIDE-LICENSE.txt)), Boxicons MIT ([`icons/BOXICONS-LICENSE.txt`](icons/BOXICONS-LICENSE.txt)), Bootstrap Icons MIT ([`icons/BOOTSTRAP-LICENSE.txt`](icons/BOOTSTRAP-LICENSE.txt)), Font Awesome CC BY 4.0 ([`icons/FONTAWESOME-LICENSE.txt`](icons/FONTAWESOME-LICENSE.txt)).

**Fonts.** **Inter** (clean UI sans-serif), **JetBrains Mono** (developer monospace), **Caveat** (handwriting script) and **Press Start 2P** (retro 8-bit arcade). All are licensed under the SIL Open Font License ([`fonts/OFL-LICENSE.txt`](fonts/OFL-LICENSE.txt)). Inter and JetBrains Mono declare `langIds: ["en", "ru", "el"]` — carrying Cyrillic and Greek as well as Latin; Caveat and Press Start 2P declare `["en"]`.

**Emoji fonts.** **Twemoji** (Twitter's colour set via Mozilla's COLRv0 build, CC BY 4.0 — [`fonts/TWEMOJI-LICENSE.txt`](fonts/TWEMOJI-LICENSE.txt)), **OpenMoji Color** (full-colour vector build with COLRv0 and SVG tables, CC BY-SA 4.0 — [`fonts/OPENMOJI-LICENSE.txt`](fonts/OPENMOJI-LICENSE.txt)), and **Emojitwo** (the open-source Emojitwo/EmojiOne 2.2 colour set via Emoji-COLRv0, CC BY 4.0 — [`fonts/EMOJITWO-LICENSE.txt`](fonts/EMOJITWO-LICENSE.txt)).

**Braille.** A layout that types Unicode braille cells (⠁⠃⠉⠙) from QWERTY key positions, with the Latin letter on long-press and shown as the corner hint.

**Sounds.** Four key-press sounds synthesised by [`tools/make_sounds.py`](tools/make_sounds.py) and released CC0 ([`sounds/SOUNDS-LICENSE.txt`](sounds/SOUNDS-LICENSE.txt)).

---

## Make Your Own Repository

1. Fork this repo (or copy the files).
2. Replace the payloads. The easiest way to get valid payloads: **export them from the WM Keyboard app** (a theme, a layout, a snippet pack, a sticker pack, an icon pack) and drop the exported files in.
3. Edit `wmkeyboard-repo.json` — one entry per addon. Include `"$schema"` pointing at the schema URL for IDE autocompletion and validation, and set each `path`.
4. Bump an addon's `version` (semver) whenever you update its file — that's how the app offers updates. Bump `repo.updatedAt` too.
5. Push to any public `https` host and share the URL.

### Checksums & Validation

`sha256` and `sizeBytes` are optional. Run tooling to keep them current and validate:

```bash
python3 tools/build_index.py
python3 tools/validate.py
```

Full spec, field tables and the JSON Schema live in [`docs/addons/`](docs/addons/):
[`REPO_FORMAT.md`](docs/addons/REPO_FORMAT.md), [`wmkeyboard-repo.schema.json`](docs/addons/wmkeyboard-repo.schema.json), [`CLIENT_DESIGN.md`](docs/addons/CLIENT_DESIGN.md).
"""

(ROOT / "README.md").write_text(readme_content, encoding="utf-8")
print("Successfully generated clean GFM-compliant README.md")
