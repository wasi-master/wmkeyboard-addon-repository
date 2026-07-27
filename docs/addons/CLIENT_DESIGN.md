# Addon Repositories — Client Handling Design

How the app should fetch, resolve, validate and install addons from a repository.
Companion to [REPO_FORMAT.md](REPO_FORMAT.md). Status: **design** (not yet implemented).

Guiding principle: **reuse everything.** Every addon payload is already a native import
format, so install = *download the file, hand it to the existing importer*. The only new
code is the manifest layer + a fetch/browse/install shell.

## 1. Data model (new)

New file `core/addons/AddonRepo.kt`, kotlinx-serialization, decoded with the same tolerant
codec settings the rest of the app uses (`Json { ignoreUnknownKeys = true; coerceInputValues = true }`):

```kotlin
@Serializable data class AddonRepoManifest(
    val format: String,           // must equal "wmkeyboard-repo"
    val version: Int = 1,
    val repo: AddonRepoInfo,
    val addons: List<AddonEntry> = emptyList(),
)
@Serializable data class AddonRepoInfo(
    val id: String, val name: String,
    val description: String = "", val author: String = "",
    val homepage: String = "", val icon: String? = null,
    val updatedAt: String = "",
)
@Serializable data class AddonEntry(
    val id: String,
    val type: AddonType,          // enum with an `Unknown` fallback for forward-compat
    val name: String,
    val version: String,          // semver
    val author: String = "",
    val description: String = "",
    val tags: List<String> = emptyList(),
    val path: String,
    val sha256: String? = null,
    val sizeBytes: Long? = null,
    val previews: List<String> = emptyList(),
    val minAppVersion: Int? = null,
    val langId: String? = null,
)
```

`AddonRepoCodec.decode(json)` validates the `format` tag (reject on mismatch, like
`LayoutFile.decode` does at `LayoutFile.kt:77`) and returns `null` on failure rather than
throwing.

## 2. Add-a-repo → manifest URL resolution

Accept a pasted string and normalise to the raw manifest URL (§4 of the format doc):

- `github.com/USER/REPO` → `raw.githubusercontent.com/USER/REPO/HEAD/wmkeyboard-repo.json`
- `github.com/USER/REPO/tree/BRANCH` → same on `BRANCH`
- a direct `raw.githubusercontent.com/.../wmkeyboard-repo.json` or any `https` manifest URL → as-is

Keep the resolved **manifest URL's directory** as the base for resolving relative
`path` / `previews` / `icon`. Enforce **`https` only**.

## 3. Persistence — a file-backed store, not DataStore

`filesDir/addons/`, following the same contract as `IconPackStore` / `StickerPackStore`:

- `repos.json` — `[{ url, manifestUrl, addedAt, cachedManifest, fetchedAt, seeded }]`.
- `installed.json` — `{ "<repoId>/<addonId>": { version, type, localRef, installedAt } }` where
  `localRef` is the created custom-theme/layout id, dictionary file path, pack id, font id or
  sound id. Drives the Installed / Update-available / Uninstall states.

The store's directory getter returns **null** when `!DirectBoot.isUserUnlocked`, so it reads as
empty before first unlock; `attach(context)` re-points it afterwards. A `reconcile()` sweep drops
entries whose local target the user has since deleted by hand.

> This is a deliberate change from the original design, which put `addon_repos` /
> `installed_addons` in DataStore next to `custom_themes` / `custom_layouts`. Cached manifests
> run to several KB each, and `KeyboardSettings` is re-emitted to the IME on every settings
> change — parking manifests there would push that payload through the keyboard's hot path for
> no benefit, and `KeyboardSettings` is already near the JVM's 255-argument `copy$default`
> ceiling. Net new `KeyboardSettings` fields for the addon layer: zero.

## 4. Fetch

- Manifest and small text payloads (theme/layout/snippets JSON): existing blocking
  `ToolHttp.get(url)` on `Dispatchers.IO` (`core/tools/ToolHttp.kt`).
- Dictionaries can be large: stream to a temp file with a **32 MiB cap** (matches
  `CustomDictionaries.MAX_BYTES`), following the resumable pattern in
  `core/localllm/LocalLlmDownloadManager.kt`. Accept optional `.txt.gz`.
- `sha256` is **optional**. When present, hash the bytes as they stream in and verify **before**
  install, aborting on mismatch. When absent, install proceeds and the UI marks the addon
  unverified — a beginner hand-writing a manifest must not be blocked on computing hashes.
  `sizeBytes` is likewise a pre-download guard only; the mid-stream cap does the real work.
- If `minAppVersion > BuildConfig.VERSION_CODE`, disable install with an "update the app" note.

## 5. Install dispatch

Six of the eight types route straight to an importer that already exists. Two do not, and are
built as part of this work — the rows are marked.

| type | Install path |
|---|---|
| `theme` | `ThemeCodec.decode` → `copy(id = "custom_" + now)` → `ThemeSpec.withExtractedImages(themeImagesDir(ctx))` → `SettingsRepository.upsertCustomTheme` |
| `layout` | `LayoutFile.decode` → `LayoutCodec.migrateLayout` → `LayoutSpec.repair` → fresh id → `SettingsRepository.upsertCustomLayout` |
| `dictionary` | `CustomDictionaries.import(filesDir, langId, name, stream)` — validates ≥1 word, 32 MiB cap. Guard: `langId` must exist in `LanguageRegistry` (else surface a clear "unsupported language" error). |
| `snippets` | **new** `SnippetFile.decode` (the `.wmsnippets.json` codec was specified but never written) → for each entry `SnippetStore.add(label, text, trigger)`, ids reassigned. The same codec gives the app snippet export/import, so anything a repo can ship the app can also produce. |
| `stickers` | `StickerPackFile.import(input, store)` — extracts `*.wmstickers` ZIP archive, validates `wmkeyboard-stickers` envelope in `pack.json`, normalizes images to app-private sticker storage, and registers pack in `StickerPackStore`. |
| `icon_pack` | `IconPackFile.import(input, store)` — extracts `*.wmicons`, validates the `wmkeyboard-icons` envelope in `pack.json`, keeps every entry naming a slot `IconSlots` knows (parsing each SVG to prove it renders), and registers the pack in `IconPackStore`. Then `SettingsRepository.setIconPack(id)` to switch to it. |
| `font` | **new subsystem.** The app had three fixed custom-font slots, each overwritten on import, so a *library* of installed fonts had to be built first: `FontStore` (`filesDir/fonts/installed/`, `fonts.json` index, 50-font cap) + `FontFile.import(stream, store, name)` validating the sfnt magic and proving the face actually loads. `KeyboardFonts` resolves an `installed:<id>` font id through the store, so installed faces appear in the font picker beside the Google Fonts. |
| `sound` | **new subsystem.** Key sounds were five synthesised waveforms behind a `KeySoundStyle` enum with no import path at all. Adds a `CUSTOM` style, `SoundStore` (`filesDir/keysounds/`, `sounds.json`, 30-sound cap) and `SoundFile.import(stream, store, name)` validating the MPEG frame header; `KeySoundPlayer` loads the chosen file into its `SoundPool` instead of a synthesised buffer. |

Record the result in `installed_addons`. Uninstall reverses the local action
(`deleteCustomTheme` / `deleteCustomLayout` / delete the dict file / remove snippets / delete sticker pack / etc.).

## 6. Update detection

On the Addons screen (or manual refresh): re-fetch each repo's manifest, and for every entry
whose `"<repoId>/<addonId>"` is in `installed_addons`, semver-compare `entry.version` to the
stored version → show **Update**. Re-running install overwrites in place.

## 7. Security & privacy

All addons are **pure data — no code runs**. Residual surface + mitigations:

- **Transport:** `https` only. Size caps on manifest and every payload type (theme image cap,
  32 MiB dict cap). Optional but recommended `sha256` verification.
- **Images & Stickers:** theme backgrounds and sticker images decode through `BitmapFactory` — the parser exposed to
  untrusted bytes. Cap dimensions/bytes; decode off the main thread. Import already nulls any
  local absolute `backgroundImage` path and re-extracts to app-private storage — keep that.
- **Layouts:** the `send_key` / `mod` key actions are a capability, but they only inject into the
  field the user is typing in (no exfiltration, no off-device effect). Already part of the trusted
  layout format; note in review, no extra gate needed for v1.
- **Privacy:** manifests are fetched only from user-added URLs. No telemetry, no phone-home.
- **Deep links:** a `wmkeyboard://` link is untrusted input from a web page, so it may never
  install on arrival. It navigates to the addon's detail screen showing the repo URL, name and
  author, and the user taps Install. Adding a repository from a link needs the same explicit
  confirm, with the resolved host shown so a lookalike URL is visible before it is trusted.

## 8. Future work

- **Data-driven languages** — a downloadable dictionary/layout for a *new* language currently
  needs a compiled `LanguageDef` in `LanguageRegistry.all` (`core/script/Language.kt:54`). Making
  that registry data-driven would let repos ship whole new languages; larger effort, tracked
  separately.
- **Curated index** — an optional list of known repos the app suggests when the user has none added.
