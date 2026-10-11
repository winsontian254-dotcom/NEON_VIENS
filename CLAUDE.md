# Neon Veins — notes for Claude

## Project shape
- The whole game is the single file `index.html` (Babylon.js from the CDN; never inline Babylon or add npm/build tooling to the web game).
- `android/` wraps it in an Android app (WebView). The APK is committed at `android/NeonVeins.apk`.

## Rule: every change to index.html also updates the Android app
Whenever you edit `index.html`, in the same commit:
1. Rebuild the APK: `python3 android/tools/build-apk.py` (needs `pip install pyaxml cryptography` and a JDK; no Android SDK required).
2. Commit `android/NeonVeins.apk` together with `index.html`.

If you changed native code (`android/app/src/**`, the manifest, or the build script), also bump `versionCode` (and `versionName`) in `android/version.json` before rebuilding: installed apps offer a one-tap update only when versionCode goes up.
Game-only changes do not need a version bump: installed apps download the new `index.html` from GitHub by themselves, and the rebuilt APK keeps the offline bundle current.

## Rule: announce player-visible changes (new-version prompt)
- Players get a "New version available" prompt (with change log) when `version.json` on GitHub Pages has a higher `build` than the `NV_BUILD` inside their loaded `index.html`.
- When you change the game in a way players should be told about, run `python3 tools/release.py "short change line" "another line"` (bumps `NV_BUILD` in index.html and adds an entry to `version.json`), then commit both with the rebuilt APK. Purely internal fixes don't need it.

## Android app facts
- The updater in `Updater.java` reads the branch `claude/festive-faraday-4v0m9s` of `winsontian254-dotcom/NEON_VIENS` (public GitHub API, no token). If the working branch changes, update `Updater.BRANCH` and bump versionCode.
- The APK is signed with the debug key in `android/keystore/`; keep using it so updates install over older versions.
- `window.NVAndroid` (JS bridge) exists only inside the app: `getMode()/setMode()` for Normal vs Cardboard, `share(name, text)` (share sheet, used by the Dossier), and the Back button calls `window.NVAndroidBack()`.

## Chinese translation (简体 / 繁體)
- Language is a setting (`lang`: 0 English, 1 Simplified, 2 Traditional; auto-detected from the browser on first run). `NV.I18n` translates dialogue in `UI.say` and the rest of the interface in the DOM (MutationObserver), by exact English text.
- Sources: `i18n/zh/bNN.tsv` (story lines by index into `NV.I18n.storyKeys()`), `i18n/zh/uiN.tsv` (English UI text → Simplified). Traditional is generated with OpenCC.
- After editing any translation, or the story data (NV_DATA), run `python3 tools/build_zh.py` (needs `pip install opencc-python-reimplemented`); it rewrites the `NV_ZH` block in index.html. New UI strings: add them to a `uiN.tsv`.

## 3D models (embedded)
- Models live in `assets/src/` with licences in `assets/manifest.json` (CC0 only). `python3 tools/embed_assets.py --slim` (with `GLTF_TRANSFORM_DIR` pointing at a folder with `@gltf-transform/core` + `functions` installed) writes them as base64 into the `NV_ASSETS` block of index.html; then rebuild the APK.
- `NV.Assets.inst(scene, name)` returns a copy with its own animation groups; every use keeps a code-built fallback.
- First-person weapons are built in Blender by `tools/blender/build_weapons.py` (`pip install bpy`; run `python3 tools/blender/build_weapons.py [-- pistol knife hands ...]`): `w_pistol, w_knife, w_smg, w_rifle, w_shotgun, w_sniper` plus two gloved fists `w_hand_grip` (closed round a vertical grip) and `w_hand_hold` (round a horizontal handle: knife, handguards; mirrored with a negative x scale for the left hand). Models are written in game axes (z = barrel direction) and each mesh is named by ROLE (`body metal grip dark acc heat glass glove sleeve`); `weaponModel` in index.html gives each role a material tinted with the weapon's faction colours, so one model serves every weapon of that archetype. `WGLB` / `WMUZ` / `WPOSE` / `HANDS` there list the models, muzzle positions, the knife's carry pose and where the fists sit; archetypes without a Blender model (rotary, launcher, hammer, baton, grenade, wrist, remote, designator, laser) still use the code-built ones. The receiver top is y = .082 so the code-built optics (`OPTICS`) bolt on; the sniper's scope is modelled (lenses at z .302 and `OPTICS.sniper.z`). `NV.Assets.pre(scene, names)` loads them when a level starts and `NV.Assets.sync` copies them instantly; until they arrive the code-built models stand in. Preview them without the game: the HTML viewer used while modelling is not committed; rendering a GLB in Babylon with `body/metal/...` materials by mesh name is enough.

## Character data
- A character is one of three lifepaths (`street`, `corp`, `nomad`) plus five attributes (`body ref int tech cool`, 3-8, lifepath minimums, four free points): `NV.BG` (`LIST`, `ATTR`, `floor`, `attrNorm`, `migrate`, `mods`) in index.html. Gameplay reads the numbers from `L.bg = NV.BG.mods(profile.tags, profile.attr)` (set in `NV.Level.start`; `mods([])` is neutral, used by multiplayer); never check tag ids directly. The numbers are explained only in the Dossier, so after changing any of them update `i18n/dossier/*` too.
- Appearance is `profile.look` (`jacket, visor, skin, hair, hairCol, eyes, ware`), normalised by `NV.LOOK.norm`. Profiles carry `v: 3` (`tags: [lifepath]`, `attr`); `NV.State.newGame` / `setProfile` fold any older profile through `NV.BG.migrate`. `ensureProfile` in the main loop converts v2 saves silently (with a toast) and asks about older ones through `UI.convertProfile`.
- The creator is `UI.create` (four screens; headings and microtext are `.notr` and translated with `tr()` by hand; art from `NV.Art`), `NV.Art.mount(canvas, 'street'|'corp'|'nomad'|'overlook')` paints the animated card scenes from code.

## The Dossier (long handbook + database tools)
- Source: `i18n/dossier/NN-name.en.txt` and its Simplified twin `.zh.txt` (`# ` section, `## ` sub-heading, blank line = paragraph; the two must have the same shape). `python3 tools/build_dossier.py` writes the English into the `NV_DOSSIER` script block of index.html and the English -> Chinese pairs into `i18n/zh/ui9.tsv`; then run `tools/build_zh.py`.
- `UI.dossier` is the reader: contents, query line (matches English and the current language), EXTRACT PASSAGE notes (`localStorage.nv_extract_v1`, `[section, item, hash]`), copy / download, and EXPORT MY RECORD (builds a text report from `nv_save_v1`). Inside the Android app downloads go through `window.NVAndroid.share(name, text)` (share sheet; older app builds fall back to the clipboard).

## Accounts server
- `server/` is the account API (Cloudflare Worker + D1 `neon-veins-accounts`, id in `server/wrangler.toml`; schema in `server/schema.sql`). It is deployed at https://neon-veins-api.winsontian254.workers.dev (`cd server && wrangler deploy` from a PC; this cloud session cannot reach Cloudflare).
- The game reads the API base from `DEFAULT_API` in `NV.Account` (index.html); `NV.Account.DEMO` is the number of chapters playable without an account.

## The city (hand-drawn)
- `NV.CITY_MAP` (above `NV.CityPlan` in index.html) is the authored map: a 32 x 32 grid of district letters, a block pattern per district (`a-o` templates, `.` plaza, `@` landmark site, `S` safe plaza), hand-placed `over` blocks, and the template library `T` (rects with height and facade `grid` / `ribbon` / `shed`).
- Landmark names from `NV.LANDMARKS` fill the `@` sites of their own district in reading order; if a district has too few, ordinary blocks make up the rest. Changing the map changes where everything is, so check that every district still has enough `@` sites and that the start plaza stays reachable.

## Authored interiors (missions, arenas, story spaces)
- `NV.LAYOUTS` (above the Helix Tower code in index.html) holds the hand-drawn plans, one character per 4 m cell: `#` wall, `.` floor, `S` start, `X` exit (scenes: where the cast gathers), `1-9` room centres, `T` terminal, `P` pickup, `e` enemy post, `m` medkit, `v` civilian, `c` crate, furniture `R B D C M K L Y N U` (cover, with their own collision size), `r` rails (walkable). `kind` is `mission`, `arena` (17 x 17, keep the anchor cells free: the centre, the four spawn alcoves and the terminal/node/medkit spots `populate` uses) or `scene`; `pal` overrides the scene colours.
- `NV.layoutFor(op, ctx, wantCity)` and `NV.sceneInterior(heading)` choose the plan from the scene heading and objective text (never at random); `NV.Level.start` then sets `L.layout` and `L.city = false`. `parseLayout` / `buildDeco` in `NV.Level` read a plan and build its furniture. Outdoor operations still run in the city and get the arena plans as hand-placed cover.
- Test one in the browser with `#dev&allowgl&op=infiltrate&scene=THE%20HIVE&layout=factory` (`op=arena`, `op=scene` work too). Every plan must keep S and X connected to all its markers.

## Hardcore and performance
- `NV.DIFF.hardcore` has `perma:true`, `ammo:.5` (reserve cap via `capOf`/`Arms.cap`) and `marks:false` (minimap/waypoints draw no markers). Use `NV.State.hardcore()` rather than reading `profile.difficulty` (old saves lack it). A failed solo operation calls `NV.State.markDead(why)` in `finish()`; `Story.runOp` then shows `UI.hardcoreOver` and `NV.State.endRun()` erases the save. The cloud copy is a tombstone (`dead` flag) in `NV.Account.upload`. Test with `#dev&allowgl&diff=hardcore&op=hack` and `NV.Level.devApi().hurtPlayer(99999)`.
- Big repeated sets use `NV.thinChunks` (per-chunk thin-instance buffers with LOD-null culling); far entities are `setEnabled(false)` in `updateEnemies` / `updateFree` / `updateTraffic`. Profile with `SceneInstrumentation` (JS is not the bottleneck; draw calls and triangles are).
