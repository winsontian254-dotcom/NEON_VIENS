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

## Android app facts
- The updater in `Updater.java` reads the branch `claude/festive-faraday-4v0m9s` of `winsontian254-dotcom/NEON_VIENS` (public GitHub API, no token). If the working branch changes, update `Updater.BRANCH` and bump versionCode.
- The APK is signed with the debug key in `android/keystore/`; keep using it so updates install over older versions.
- `window.NVAndroid` (JS bridge) exists only inside the app: `getMode()/setMode()` for Normal vs Cardboard, and the Back button calls `window.NVAndroidBack()`.

## Chinese translation (简体 / 繁體)
- Language is a setting (`lang`: 0 English, 1 Simplified, 2 Traditional; auto-detected from the browser on first run). `NV.I18n` translates dialogue in `UI.say` and the rest of the interface in the DOM (MutationObserver), by exact English text.
- Sources: `i18n/zh/bNN.tsv` (story lines by index into `NV.I18n.storyKeys()`), `i18n/zh/uiN.tsv` (English UI text → Simplified). Traditional is generated with OpenCC.
- After editing any translation, or the story data (NV_DATA), run `python3 tools/build_zh.py` (needs `pip install opencc-python-reimplemented`); it rewrites the `NV_ZH` block in index.html. New UI strings: add them to a `uiN.tsv`.
