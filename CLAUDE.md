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
- `window.NVAndroid` (JS bridge) exists only inside the app: `getMode()/setMode()` for Normal vs Cardboard, and the Back button calls `window.NVAndroidBack()`.

## Chinese translation (简体 / 繁體)
- Language is a setting (`lang`: 0 English, 1 Simplified, 2 Traditional; auto-detected from the browser on first run). `NV.I18n` translates dialogue in `UI.say` and the rest of the interface in the DOM (MutationObserver), by exact English text.
- Sources: `i18n/zh/bNN.tsv` (story lines by index into `NV.I18n.storyKeys()`), `i18n/zh/uiN.tsv` (English UI text → Simplified). Traditional is generated with OpenCC.
- After editing any translation, or the story data (NV_DATA), run `python3 tools/build_zh.py` (needs `pip install opencc-python-reimplemented`); it rewrites the `NV_ZH` block in index.html. New UI strings: add them to a `uiN.tsv`.

## 3D models (embedded)
- Models live in `assets/src/` with licences in `assets/manifest.json` (CC0 only). `python3 tools/embed_assets.py --slim` (with `GLTF_TRANSFORM_DIR` pointing at a folder with `@gltf-transform/core` + `functions` installed) writes them as base64 into the `NV_ASSETS` block of index.html; then rebuild the APK.
- `NV.Assets.inst(scene, name)` returns a copy with its own animation groups; every use keeps a code-built fallback.

## Character data
- Backgrounds live in `NV.BG` (eight entries: text, `mods`, `start` stats, combos and clashes). Gameplay reads the merged mods from `L.bg` (set in `NV.Level.start`); never check tag ids directly.
- Appearance is `profile.look` (`jacket, visor, skin, hair, hairCol, eyes, ware`), normalised by `NV.LOOK.norm`. Profiles carry `v: 2`; older saves are converted through `UI.convertProfile` / `NV.State.setProfile` in the main loop.

## Accounts server
- `server/` is the account API (Cloudflare Worker + D1 `neon-veins-accounts`, id in `server/wrangler.toml`; schema in `server/schema.sql`). It is deployed at https://neon-veins-api.winsontian254.workers.dev (`cd server && wrangler deploy` from a PC; this cloud session cannot reach Cloudflare).
- The game reads the API base from `DEFAULT_API` in `NV.Account` (index.html); `NV.Account.DEMO` is the number of chapters playable without an account.
