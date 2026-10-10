# 3D models for Neon Veins

The game stays one file: `tools/embed_assets.py` turns the models listed in `manifest.json` into a base64 block inside `index.html`. This folder holds the source files and their licences.

## What to upload (all free, CC0)

Download these on your PC. Each one is a zip from the creator's site.

1. **Quaternius: Ultimate Modular Men Pack** and **Ultimate Modular Women Pack** (quaternius.com → Packs). These are the rigged humans.
2. **Quaternius: Universal Animation Library** (quaternius.com). These are the idle, walk, run, talk, hit and death animations for those characters.
3. **Kenney: City Kit (Commercial)**, **Furniture Kit** and **Car Kit** (kenney.nl → Assets). These are the props and vehicles.

From each zip, keep only the **glTF / GLB** files: the `.glb` files, or a `.gltf` with its `.bin` and textures. You can skip FBX, OBJ, Blend and preview images.

## How to upload (GitHub website, no tools needed)

1. Open the repo on github.com and switch to the branch `claude/festive-faraday-4v0m9s`.
2. Go into the folder `assets/src/`.
3. Click **Add file → Upload files**.
4. Drag in one pack's GLB files at a time, into a subfolder named after the pack, for example `assets/src/quaternius-men/`. The GitHub uploader keeps folders if you drag the folder itself.
5. Commit directly to the branch.

GitHub allows up to 100 files per upload and 25 MB per file. If a pack has more files than that, upload it in a few goes.

Then tell Claude which packs you uploaded. Claude will:
- check each licence;
- slim the models;
- add the models to `manifest.json`;
- run `python3 tools/embed_assets.py --slim`.

## Already included

| name | file | licence | source |
|---|---|---|---|
| robot | `src/robot.glb` | CC0 1.0 | RobotExpressive by Tomás Laulhé (Quaternius), via the three.js examples |
