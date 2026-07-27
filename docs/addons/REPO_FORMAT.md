# WM Keyboard Addon Repository Format

Version 1 · status: **spec** (client not yet implemented)

WM Keyboard can install extra **themes, layouts, dictionaries, and snippet packs** from the web. Anyone can publish these by putting a small **manifest** and the addon files in a public Git repository (GitHub, GitLab, a raw host — anything that serves files over `https`). Users add a repository by pasting its URL into the app.

A repository is nothing more than an **index over files the app already knows how to import** — the addon files are the same formats the app produces when you export a theme/layout/etc. from the app itself. There is no packaging, signing or build step.

> The full, forkable sample lives at
> **https://github.com/wasi-master/wmkeyboard-addon-repository** — clone it as a starting point.

---

## 1. Repository layout

```
wmkeyboard-repo.json      ← required: the manifest (repo root)
icon.png                  ← optional: repo icon
README.md                 ← optional but recommended
themes/       *.wmtheme.json
layouts/      *.wmlayout.json
dictionaries/ <langId>.txt
snippets/     *.wmsnippets.json
stickers/     *.wmstickers
icons/        *.wmicons
fonts/        *.ttf, *.otf
sounds/       *.mp3
previews/     *.png            ← optional screenshots
```

Folder names are a convention, not a rule — the manifest's `path` fields are what actually locate files.

## 2. The manifest — `wmkeyboard-repo.json`

Must sit at the repository root and validate against
[`wmkeyboard-repo.schema.json`](wmkeyboard-repo.schema.json) (JSON Schema draft 2020-12).

```json
{
  "$schema": "https://raw.githubusercontent.com/wasi-master/wmkeyboard-addon-repository/main/docs/addons/wmkeyboard-repo.schema.json",
  "format": "wmkeyboard-repo",
  "version": 1,
  "repo": {
    "id": "com.example.coolpack",
    "name": "Cool Addon Pack",
    "description": "Dark themes and extra layouts.",
    "author": "Some Creator",
    "homepage": "https://github.com/user/wmkeyboard-addons",
    "icon": "icon.png",
    "updatedAt": "2026-07-22"
  },
  "addons": [ /* AddonEntry[] */ ]
}
```

| Field | Req | Notes |
|---|---|---|
| `$schema` | | Optional URL to `wmkeyboard-repo.schema.json` (e.g. `raw.githubusercontent.com` link) for IDE autocompletion & validation. |
| `format` | ✔ | Magic tag, exactly `"wmkeyboard-repo"`. The client rejects anything else. |
| `version` | ✔ | Manifest schema version. Currently `1`. |
| `repo.id` | ✔ | Stable id, reverse-DNS recommended. Namespaces installed addons. |
| `repo.name` | ✔ | Shown in the repo list. |
| `repo.{description,author,homepage,icon,updatedAt}` | | Optional metadata. `icon` is relative or absolute (see §4). |
| `addons` | ✔ | Array of addon entries (§3). May be empty. |

Unknown fields are ignored, so future versions can add fields without breaking old clients.

## 3. Addon entry

```json
{
  "id": "midnight",
  "type": "theme",
  "name": "Midnight",
  "version": "1.2.0",
  "author": "Some Creator",
  "description": "Deep blue dark theme.",
  "tags": ["dark", "blue"],
  "path": "themes/midnight.wmtheme.json",
  "sha256": "…64 hex chars…",
  "sizeBytes": 24680,
  "previews": ["previews/midnight.png"],
  "minAppVersion": 40,
  "langId": "fr"
}
```

| Field | Req | Notes |
|---|---|---|
| `id` | ✔ | Unique within the repo. |
| `type` | ✔ | `theme` \| `layout` \| `dictionary` \| `snippets` \| `stickers` \| `icon_pack` \| `font` \| `sound`. |
| `name` | ✔ | Display name. |
| `version` | ✔ | **Semver** string. Bump it to offer an update. |
| `path` | ✔ | Payload location — relative to the manifest, or an absolute `https` URL (§4). |
| `author`, `description`, `tags` | | Display / search metadata. |
| `sha256` | | Lowercase hex SHA-256 of the payload; verified before install when present. **Optional** — an addon without one installs normally and is shown as unverified. |
| `sizeBytes` | | Payload size, for the UI and a pre-download guard. Optional; the client caps every download regardless. |
| `previews` | | Screenshot images (relative or absolute). |
| `minAppVersion` | | App `versionCode` floor; older apps hide/disable the addon. |
| `langId` | *dict* | **Required for `dictionary`**, optional hint for `layout`. Must be a registered language id (§5). |

## 4. Path & URL resolution (hybrid model)

`path`, `previews[]` and `repo.icon` are each **either**:

- a path **relative to the manifest URL's directory** — e.g. `themes/midnight.wmtheme.json`; or
- an absolute `https://` URL — point anywhere (a GitHub Release asset, a CDN, another repo).

The app derives the raw manifest URL from what the user pastes:

| User pastes | Manifest fetched from |
|---|---|
| `https://github.com/USER/REPO` | `https://raw.githubusercontent.com/USER/REPO/HEAD/wmkeyboard-repo.json` |
| `https://github.com/USER/REPO/tree/BRANCH` | …/`BRANCH`/wmkeyboard-repo.json |
| a direct `raw.githubusercontent.com/.../wmkeyboard-repo.json` | used as-is |
| any other `https` URL to a manifest | used as-is |

Relative paths resolve against that manifest URL's directory. **`https` only** — plain `http` and non-URL schemes are rejected.

## 5. Payload formats (these ARE the app's native import/export formats)

| `type` | File | Format |
|---|---|---|
| `theme` | `*.wmtheme.json` | One `ThemeSpec` object (the app's theme export). **The only payload with no `format`/`version` envelope** — it is the bare object, so a theme file is identified by its extension rather than a magic tag. Background images travel base64-embedded inside the JSON, so the file is self-contained. Colors are decimal ARGB longs (`0xAARRGGBB`). |
| `layout` | `*.wmlayout.json` | Envelope `{ "format":"wmkeyboard-layout", "version":1, "layout": { …LayoutSpec… } }` — the app's layout export. |
| `dictionary` | `<langId>.txt` | Plain UTF-8, one entry per line: `word<space>frequency` (frequency optional, default 1). `#` starts a comment. May be gzipped (`.txt.gz`) for transport. |
| `snippets` | `*.wmsnippets.json` | `{ "format":"wmkeyboard-snippets", "version":1, "snippets":[ { "id":1, "label":"…", "text":"…", "trigger":"…"? }, … ] }`. Ids are reassigned on import. |
| `stickers` | `*.wmstickers` | ZIP archive containing a `pack.json` envelope (`"format":"wmkeyboard-stickers"`, `"version":1`, `pack` metadata, `stickers[]`) and the image files under `stickers/`. See [Sticker packs](#sticker-packs). |
| `icon_pack` | `*.wmicons` | ZIP archive containing a `pack.json` envelope (`"format":"wmkeyboard-icons"`, `"version":1`, `pack` metadata) and one SVG per replaced icon under `icons/`, named for its slot. See [Icon packs](#icon-packs). |
| `font` | `*.ttf`, `*.otf` | Standard TrueType or OpenType font file used for keyboard key labels and text typography. |
| `sound` | `*.mp3` | A single short key-press sound. Keep it under ~300 ms and a few tens of KB: it is loaded into a `SoundPool` and replayed on every keystroke. |

To make a theme/layout/snippet/sticker/icon payload, just **export it from the app** and drop the file into your repo — the exported files already match these formats.

### Sticker packs

```
mypack.wmstickers
├── pack.json
└── stickers/<stickerId>.<ext>
```

```json
{
  "format": "wmkeyboard-stickers",
  "version": 1,
  "appVersion": 41,
  "appVersionName": "1.4.0",
  "pack": {
    "id": "undraw-illustrations",
    "name": "unDraw Everyday Moments",
    "author": "…",
    "description": "…"
  },
  "stickers": [
    { "id": "airplane", "name": "Airplane", "file": "stickers/airplane.png" }
  ]
}
```

Unlike icon packs, sticker entry names **are** listed explicitly in `stickers[]` — `id` keys
the sticker, `name` is what the user searches, and `file` locates the image inside the archive.
Images are re-encoded into the app's own sticker storage on import, so any common raster format
works. Limits: at most 500 entries and 64 MB per archive, 200 stickers per pack and 50 packs
installed.

`appVersion` / `appVersionName` record the app build that wrote the file. They are informational
— import ignores them — and both are optional in a hand-built pack.

### Icon packs

```
mypack.wmicons
├── pack.json
└── icons/<slotId>.svg
```

```json
{
  "format": "wmkeyboard-icons",
  "version": 1,
  "appVersion": 41,
  "appVersionName": "1.4.0",
  "pack": {
    "id": "rounded",
    "name": "Rounded",
    "author": "…",
    "description": "…",
    "version": "1.0.0",
    "slots": ["tool.clipboard", "key.enter_send", "…"]
  }
}
```

`appVersion` / `appVersionName` record the app build that exported the pack. They are
informational — import ignores them — and can be left out of a hand-built pack.

**Slot ids are the file names.** An icon for `tool.clipboard` is
`icons/tool.clipboard.svg`. The four slot groups are:

| Group | Ids | Count |
|---|---|---|
| Tools | `tool.<toolbar tool>` — `tool.clipboard`, `tool.gif`, `tool.sticker`, `tool.voice`, … | 58 |
| Keys | `key.shift`, `key.shift_on`, `key.shift_lock`, `key.backspace`, `key.globe`, `key.emoji`, and `key.enter` plus `key.enter_{search,send,go,next,previous,done}` | 13 |
| Toolbar chrome | `chrome.toolbox`, `chrome.panel_back`, `chrome.suggestions_expand`, `chrome.emoji_shortcut`, `chrome.search_close`, `chrome.incognito` | 6 |
| Emoji tabs | `emoji_tab.search`, `emoji_tab.recent`, `emoji_tab.most_used`, and one per category (`smileys`, `people`, `animals`, `nature`, `food`, `travel`, `activities`, `objects`, `symbols`, `flags`) | 13 |

A pack does **not** have to be complete: any slot it leaves out keeps the app's
built-in icon. The `slots` list is advisory — the app walks the archive's
entries and keeps every one whose name matches a slot it knows, so a pack
assembled by hand still works if the manifest is out of date. Files naming a
slot the installed version has no idea about are dropped and reported, never
stored.

**Colour.** An SVG that declares no colours — `fill="none"`, `currentColor`, or
nothing at all — is drawn in the theme's colour and picks up the per-tool accent
colours, exactly like a built-in icon. An SVG that sets real colours keeps them
and stops following the theme. Prefer the first unless the pack is deliberately
a colour set.

**Supported SVG.** `<path>`, `<rect>`, `<circle>`, `<ellipse>`, `<line>`,
`<polyline>`, `<polygon>`, `<g transform>` (translate/scale/rotate/matrix),
presentation attributes and inline `style`, and `#rgb`/`#rrggbb`/`#rrggbbaa`/
`rgb()`/named colours. Text, embedded images, `<use>`, gradients, filters, masks
and CSS `<style>` blocks are skipped — an icon that leans on them renders as
whatever is left rather than failing to import. Each SVG must be under 256 KB,
and the archive under 8 MB with at most 400 entries.

A DOCTYPE declaration causes the file to be **rejected outright**: packs are
untrusted input, and an external entity there would be a file-disclosure hole.
Do not ship SVGs with one — most exporters can be told to omit it.

### The registered-language constraint

Dictionaries and layouts attach to a language by `langId` (e.g. `en`, `fr`, `bn`). The app can only accept a `langId` that is **already built into it**. A dictionary for a brand-new language the app has never heard of cannot be added as data alone today — that needs an app update that registers the language. So: pick a `langId` the current app supports.

## 6. Versioning & updates

- Bump an addon's `version` (semver) to publish an update; the app compares it against the installed version and offers **Update**.
- Bump `repo.updatedAt` when you change the manifest.
- Never recycle an `id` for a different addon — ids are how installs are tracked.

## 7. Publishing checklist

1. Put `wmkeyboard-repo.json` at the repo root; list every addon.
2. Add the payload files; set each `path`.
3. Optionally fill `sha256` and `sizeBytes`. **Neither is required** — a manifest without them
   is valid and its addons install normally, just marked unverified. If you do want them, don't
   compute them by hand; run `python3 tools/build_index.py` (in the
   [sample repo](https://github.com/wasi-master/wmkeyboard-addon-repository/blob/main/tools/build_index.py))
   after every payload change and it keeps them current.
4. Validate: `python3 tools/validate.py` runs the JSON Schema plus the file-existence and
   checksum checks a schema can't express.
5. Push to a public `https` host and share the repo URL.

See also: [CLIENT_DESIGN.md](CLIENT_DESIGN.md) for how the app fetches, resolves and installs these.
