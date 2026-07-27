# WM Keyboard — Sample Addon Repository

A minimal, forkable example of a **WM Keyboard addon repository**. It ships at least one of
every addon type so you can see the exact file shapes, then copy this repo as a starting point
for your own.

Add it in WM Keyboard: **Settings → Addons → Add repository**, then paste this repo's URL.

## What's inside

| Addon | Type | File |
|---|---|---|
| Midnight | theme | [`themes/midnight.wmtheme.json`](themes/midnight.wmtheme.json) |
| Français BÉPO | layout | [`layouts/fr-bepo.wmlayout.json`](layouts/fr-bepo.wmlayout.json) |
| Developer Dictionary | dictionary | [`dictionaries/en-developer.txt`](dictionaries/en-developer.txt) |
| Internet Slang & Urban Dictionary | dictionary | [`dictionaries/en-slang.txt`](dictionaries/en-slang.txt) |
| Handy snippets | snippets | [`snippets/dev-shortcuts.wmsnippets.json`](snippets/dev-shortcuts.wmsnippets.json) |
| unDraw Everyday Moments | stickers | [`stickers/undraw-illustrations.wmstickers`](stickers/undraw-illustrations.wmstickers) |
| Lucide | icon_pack | [`icons/lucide.wmicons`](icons/lucide.wmicons) |
| Boxicons | icon_pack | [`icons/boxicons.wmicons`](icons/boxicons.wmicons) |
| Bootstrap Icons | icon_pack | [`icons/bootstrap-icons.wmicons`](icons/bootstrap-icons.wmicons) |
| Font Awesome | icon_pack | [`icons/fontawesome.wmicons`](icons/fontawesome.wmicons) |
| Inter | font | [`fonts/inter.ttf`](fonts/inter.ttf) |
| JetBrains Mono | font | [`fonts/jetbrains-mono.ttf`](fonts/jetbrains-mono.ttf) |
| Caveat | font | [`fonts/caveat.ttf`](fonts/caveat.ttf) |
| Press Start 2P | font | [`fonts/press-start-2p.ttf`](fonts/press-start-2p.ttf) |
| Typewriter | sound | [`sounds/typewriter.mp3`](sounds/typewriter.mp3) |
| Marimba | sound | [`sounds/marimba.mp3`](sounds/marimba.mp3) |
| Droplet | sound | [`sounds/droplet.mp3`](sounds/droplet.mp3) |
| Blip | sound | [`sounds/blip.mp3`](sounds/blip.mp3) |

Everything is indexed by [`wmkeyboard-repo.json`](wmkeyboard-repo.json) at the repo root.

**Icon packs.** Each of the four packs is complete — it replaces all 90 icon slots, which is
every one of the 58 tools plus the key glyphs, toolbar chrome and emoji category tabs — with
[Lucide](https://lucide.dev)'s 24px outline set, [Boxicons](https://boxicons.com)' 24px vector
set, [Bootstrap Icons](https://icons.getbootstrap.com)' vector set, and
[Font Awesome Free](https://fontawesome.com)'s iconic solid set. The glyphs are uncoloured and
adaptive, so they follow the keyboard theme and the per-tool accent colours. Lucide is ISC
licensed ([`icons/LUCIDE-LICENSE.txt`](icons/LUCIDE-LICENSE.txt)), Boxicons MIT
([`icons/BOXICONS-LICENSE.txt`](icons/BOXICONS-LICENSE.txt)), Bootstrap Icons MIT
([`icons/BOOTSTRAP-LICENSE.txt`](icons/BOOTSTRAP-LICENSE.txt)), and Font Awesome CC BY 4.0
([`icons/FONTAWESOME-LICENSE.txt`](icons/FONTAWESOME-LICENSE.txt)).

**Fonts.** **Inter** (clean UI sans-serif), **JetBrains Mono** (developer monospace),
**Caveat** (handwriting script) and **Press Start 2P** (retro 8-bit arcade). All are licensed
under the SIL Open Font License.

**Sounds.** Four key-press sounds, synthesised from scratch by
[`tools/make_sounds.py`](tools/make_sounds.py) and released CC0
([`sounds/SOUNDS-LICENSE.txt`](sounds/SOUNDS-LICENSE.txt)) — no sample library involved.

## Make your own

1. Fork this repo (or copy the files).
2. Replace the payloads. The easiest way to get valid payloads: **export them from the WM
   Keyboard app** (a theme, a layout, a snippet pack, a sticker pack, an icon pack) and drop
   the exported files in.
3. Edit `wmkeyboard-repo.json` — one entry per addon. Include `"$schema"` pointing at the
   schema URL for IDE autocompletion and validation, and set each `path`.
4. Bump an addon's `version` (semver) whenever you update its file — that's how the app offers
   updates. Bump `repo.updatedAt` too.
5. Push to any public `https` host and share the URL.

### Checksums are optional

`sha256` and `sizeBytes` are **not required**. A manifest without them is perfectly valid and
its addons install normally; the app just shows them as unverified. Add them if you want the
integrity check, and let the tooling keep them current rather than doing it by hand:

```bash
python3 tools/build_index.py
```

That recomputes `sha256`/`sizeBytes` for every local payload, leaves all your hand-written
metadata alone, and bumps `repo.updatedAt` when something actually changed. Use
`--check` to fail without writing (that's what CI runs), or `--drop-checksums` to strip both
fields back out.

### Validate before you publish

```bash
pip install jsonschema
python3 tools/validate.py
```

Runs the JSON Schema, then the checks a schema can't express: every `path`, `previews[]` and
`repo.icon` resolves to a real file, ids are unique, dictionaries declare a `langId`, and any
checksum you did provide is correct. [`.github/workflows/validate.yml`](.github/workflows/validate.yml)
runs the same thing on every push and pull request.

## Format reference

Full spec, field tables and the JSON Schema live in [`docs/addons/`](docs/addons/):
[`REPO_FORMAT.md`](docs/addons/REPO_FORMAT.md),
[`wmkeyboard-repo.schema.json`](docs/addons/wmkeyboard-repo.schema.json),
[`CLIENT_DESIGN.md`](docs/addons/CLIENT_DESIGN.md).

Notes:
- Supported addon types: `theme`, `layout`, `dictionary`, `snippets`, `stickers`, `icon_pack`,
  `font`, and `sound`.
- `dictionary` and `layout` attach to a language by `langId` (e.g. `fr`) — it must be a
  language the app already supports.
- Everything here is **pure data**. Installing an addon never runs code.
