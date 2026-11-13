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
  <p>Official addon repository for WM Keyboard: themes, layouts, dictionaries, snippet packs, stickers, icon packs, fonts, emoji fonts, key sounds and Python plugins.</p>
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

**Icon packs.** Each of the four packs replaces all 94 icon slots (all 62 tools plus key glyphs, toolbar chrome and emoji category tabs) — drawn in [Lucide](https://lucide.dev)'s 24px outline set, [Boxicons](https://boxicons.com)' 24px vector set, [Bootstrap Icons](https://icons.getbootstrap.com)' vector set, and [Font Awesome Free](https://fontawesome.com)'s iconic solid set. The glyphs are uncoloured and adaptive, so they follow the keyboard theme and per-tool accent colours. Licences: Lucide ISC ([`icons/LUCIDE-LICENSE.txt`](icons/LUCIDE-LICENSE.txt)), Boxicons MIT ([`icons/BOXICONS-LICENSE.txt`](icons/BOXICONS-LICENSE.txt)), Bootstrap Icons MIT ([`icons/BOOTSTRAP-LICENSE.txt`](icons/BOOTSTRAP-LICENSE.txt)), Font Awesome CC BY 4.0 ([`icons/FONTAWESOME-LICENSE.txt`](icons/FONTAWESOME-LICENSE.txt)).

**Fonts.** **Inter** (clean UI sans-serif), **JetBrains Mono** (developer monospace), **Caveat** (handwriting script), **Press Start 2P** (retro 8-bit arcade), and **WM Font** (custom handwriting script with Latin, Greek, math symbols, fractions, and blackboard bold characters). All are licensed under the SIL Open Font License. Inter and JetBrains Mono declare `langIds: ["en", "ru", "el"]`; WM Font declares `["en", "el"]`; Caveat and Press Start 2P declare `["en"]`.

**Emoji fonts.** **Twemoji** (Twitter's colour set via Mozilla's COLRv0 build, CC BY 4.0 — [`fonts/TWEMOJI-LICENSE.txt`](fonts/TWEMOJI-LICENSE.txt)), **OpenMoji Color** (full-colour vector build with COLRv0 and SVG tables, CC BY-SA 4.0 — [`fonts/OPENMOJI-LICENSE.txt`](fonts/OPENMOJI-LICENSE.txt)), **Emojitwo** (the open-source Emojitwo/EmojiOne 2.2 colour set via Emoji-COLRv0, CC BY 4.0 — [`fonts/EMOJITWO-LICENSE.txt`](fonts/EMOJITWO-LICENSE.txt)), **Blobmoji** (Google's classic blob emojis updated for modern Unicode standard, Apache 2.0 — [`fonts/BLOBMOJI-LICENSE.txt`](fonts/BLOBMOJI-LICENSE.txt)), and **Fluent Emoji** (Microsoft's modern, friendly 3D emoji collection as a colour font, MIT — [`fonts/FLUENT-EMOJI-LICENSE.txt`](fonts/FLUENT-EMOJI-LICENSE.txt)).

**Snippets.** **Texting Shortcuts** expands 40 plain abbreviations (`omw` → "On my way!"). The other two use *pattern* triggers, where the trigger is a regular expression over the words before the cursor and `$1`…`$9` carry what it matched into the text. **Pattern Replies** turns "hello John" into a full greeting and "thanks Sarah" into a whole thank-you letter — one snippet covers every name. Its snippets are marked "ask first", so they offer themselves on the suggestion bar and write nothing until you tap. **Pattern Formatters** is a set of slash commands that reshape what you just typed: `/up` shouts, `/bold` wraps for Markdown, `/link a b` makes a link, `/gh name` becomes a GitHub URL. Every one of its triggers starts with a slash, so none of them fire inside ordinary writing. One backspace takes any expansion back.

**Braille.** A layout that types Unicode braille cells (⠁⠃⠉⠙) from QWERTY key positions, with the Latin letter on long-press and shown as the corner hint.

**Glide layouts.** Three English layouts arranged for glide typing, each contributed by [cinnabar777](https://github.com/cinnabar777). **ClearFlow** is the public-domain layout by the [ClearFlow authors](https://clearflowkeyboard.github.io/) (Xiaojun Bi et al.) — [`layouts/CLEARFLOW-LICENSE.txt`](layouts/CLEARFLOW-LICENSE.txt). **KASROZ** is [FUTO Keyboard](https://keyboard.futo.org/)'s layout from [futo-keyboard-layouts](https://github.com/futo-org/futo-keyboard-layouts), Apache 2.0 — [`layouts/KASROZ-LICENSE.txt`](layouts/KASROZ-LICENSE.txt). **Vowel Vortex Clarity** is cinnabar777's own design from [Vowel Vortex Keyboard Layouts](https://github.com/cinnabar777/Vowel-Vortex-Keyboard-Layouts), free for personal, non-commercial use under its author's licence.

**Full PC.** A five-row desktop keyboard after [Hacker's Keyboard](https://github.com/klausw/hackerskeyboard): digits with their shifted symbols, Tab, Ctrl, Alt, Meta, Esc and arrows on the board, and an Fn layer with F1 to F12 and the navigation block. For terminals, SSH clients and remote desktops.

**QWERTY with flick edit row.** English QWERTY under five flick keys: 1 and 6 carry the other digits on their arms, and Copy, Select and Cut carry paste, select all, the caret moves and both deletes.

**English QWERTY Gboard+.** Contributed by [AsafMah](https://github.com/AsafMah) and bundled with WM Keyboard until it moved here. Each letter's long-press popup ends in a tool (QR scan on q, translate on t, the clipboard on v), and a flick down from a bottom-row letter types punctuation. The swipe-safe version leaves those flicks off so a glide can't set one off. MIT, like the app.

**Plugins.** Small Python tools that draw a panel on the keyboard: **Cipher Tool** (the one the getting-started guide builds), **Text Tools**, **Lorem Ipsum** (placeholder text by the word, sentence or paragraph), **Todo List** (storage, due dates and reminders), **UI Kitchen Sink** (every widget and event), **Math Mode**, **Transit Planner** (trips, departures, pinned trips with reminders and alarms; Transitous timetables, Singapore bus arrivals and Dhaka Metro), **Day Planner** (time blocks you drag on a day timeline, tasks with steps, a board for today, tomorrow and later, and the week's hours per tag), **Open Food Facts** (scan a barcode for a product's Nutri-Score, ingredients, allergens and labels, and add what is missing), **Polls** (write a poll, make it on your Nextcloud, your LimeSurvey or StrawPoll, put its link into the chat and follow the answers), **Boycott Check** (checks a scanned, photographed or typed brand against Tech for Palestine's boycott dataset and the BDS movement's targets, with the reasons and sources), **Firefly III** (receipts and spending into your own Firefly III server), **Grocy** (your own Grocy server's shopping list, stock and chores; scan a barcode to buy, use or open something, or a receipt to stock a whole shop) and **Language Trainer** (alphabet charts with each letter's sound, and letter, word and sentence drills in 22 languages paired any way, with the keyboard switched to the language you type answers in; words from Wiktionary under CC BY-SA 4.0 and sentences from Tatoeba under CC BY 2.0 FR, see [`plugins/LANGUAGE-TRAINER-LICENSE.txt`](plugins/LANGUAGE-TRAINER-LICENSE.txt)). They run on WM Keyboard's own Python and need app version 43 or later; plugins on API 5, such as Day Planner, Open Food Facts and Boycott Check, need the next release after 0.6.6. A plugin reaches the internet, the camera, your files, your calendar or your To-do list only through permissions shown before install, and the risky ones stay off until you turn them on. Their sources are in [`plugins-src/`](plugins-src/); [`tools/build_plugins.py`](tools/build_plugins.py) packs them and [`tools/test_plugins.py`](tools/test_plugins.py) tests them. MIT ([`plugins/LICENSE.txt`](plugins/LICENSE.txt)).

**Sounds.** Four key-press sounds synthesised by [`tools/make_sounds.py`](tools/make_sounds.py) and released CC0 ([`sounds/SOUNDS-LICENSE.txt`](sounds/SOUNDS-LICENSE.txt)).

**LeanType sound packs.** 22 synthesised packs from [LeanType-SoundPacks](https://github.com/LeanBitLab/LeanType-SoundPacks), CC0 ([`sound_packs/LEANTYPE-SOUNDS-LICENSE.txt`](sound_packs/LEANTYPE-SOUNDS-LICENSE.txt)). The audio is unchanged; [`tools/import_leantype_sounds.py`](tools/import_leantype_sounds.py) only rewrites the manifest.

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
