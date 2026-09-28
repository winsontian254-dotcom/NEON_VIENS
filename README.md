# NEON VEINS

A single-file browser-based cyberpunk narrative RPG built with Babylon.js.

**New Avalon, 2098.** The city is a vertical nation built around Helix Tower, a four-kilometre arcology whose upper gardens receive engineered sunlight while the districts below survive on rented oxygen, recycled water, and subscription medicine. You are Ghost, a courier whose identity was erased from every civic database. A message from a missing scientist sends you into a conflict over ASCENSION — a self-rewriting intelligence imprisoned beneath the city.

---

## Quick start

1. Open `index.html` in a modern browser (Chrome 113+, Edge 113+, Firefox 121+, Safari 18+).
2. Click to initialize → press any key → pick a profile → begin.
3. Everything runs locally. No server, no build step, no install. Babylon.js loads from CDN on first boot.

**Dev shortcuts** (append to the URL hash):

- `#dev&op=boss&scene=NEON HEIGHTS — ROOFTOP` — boot straight into an operation
- `#dev&op=hack&k=4` — hack operation with 4 terminals
- `#chapter=3` — jump straight to a chapter
- `#diff=hard` — override difficulty

---

## What's in the box

**Story**
- 70 chapters across 5 acts, ~3,100 dialogue lines, ~390 branching choices
- 6 endings (A–F), stat-gated and flag-gated
- 50 main missions, 60 side quests
- Walkable story scenes — speakers from the script stand in the level; walk up and talk to them
- Compiled script data (`NV_DATA`) is baked into the HTML

**Gameplay**
- **Open world free roam** — procedural New Avalon with buildings, pedestrians, patrols, gigs, vendors, and 24 hidden data shards
- **First-person operations** — stealth, silent takedowns, hacking minigame, shock-pistol combat, EMP pulse, dash
- **Boss fights** — multi-phase encounters with shields, rings, spirals, charges, and summoned adds
- **Arena waves**, **defend-the-uplink**, **hack-the-terminals**, **retrieve-the-shards**, **escort/rescue** modes
- **Overwatch of your choices** — every decision nudges 5 faction stats: Raven Trust, Voss Integrity, Civilian Hope, Corporate Leverage, AI Sympathy
- **Ending eligibility** is computed live from stats, flags, and side-quest completion
- **Save system** — checkpoint per chapter, snapshot-based chapter select, `localStorage` persistence

**Presentation**
- Cinematic title screen with animated skyline, flying traffic, holo signs, rain, searchlight beams
- Procedural character portraits (2D canvas)
- Procedural WebAudio score — 8 moods (title, story, stealth, combat, boss, explore, tense, ending) with adaptive layering
- Volumetric-looking light shafts, glow layer, chromatic aberration + film grain on high tier
- Quality auto-detection for weak hardware (Chromebooks, iGPUs, phones)
- Dynamic resolution scaling — trades pixels for frame time to hold ~50-60 FPS

---

## Controls

| Action | Keyboard | Gamepad |
|---|---|---|
| Move | `WASD` / arrows | Left stick |
| Look | Mouse | Right stick |
| Sprint | `Shift` | LT |
| Sneak | `C` / `Ctrl` | LB |
| Fire | Left click | RT |
| Dash | `Space` | A |
| Interact / Takedown / Hack | `E` | X |
| EMP pulse | `Q` | Y |
| Fast travel (free roam) | `T` | Select |
| Pause | `Esc` | Start |
| Advance dialogue | `Space` / click | A |
| Choose option | `1-4` / click | dpad + A |
| Auto-advance dialogue | `A` | — |
| Hold to skip | `Ctrl` | RB |
| Backlog | `L` | — |
| Journal | `J` | — |

---

## Architecture

The entire game lives in `index.html`. Internally it's split into modules under a single `NV` namespace:

```
NV.U          — utilities (math, RNG, colour, string)
NV.Audio      — procedural synthwave score + SFX (WebAudio)
NV.In         — keyboard/mouse/gamepad input with edge detection
NV.Settings   — user preferences (persisted)
NV.State      — save data, faction stats, facts, journal, snapshots
NV.Cond       — condition evaluator for the compiled script
NV.Quality    — hardware detection + per-scene graphics setup
NV.Backdrop   — cinematic 3D scenes (city, tunnel, cyber, space)
NV.Level      — first-person operations (stealth/combat/hack/boss/free-roam)
NV.UI         — DOM overlay (menus, dialogue, journal, doors, credits)
NV.Story      — interpreter for the compiled chapter tree
NV_DATA       — the compiled script (chapters, missions, endings)
```

### Story node types

The script compiler emits a tree of typed nodes. `NV.Story.runNode` handles them:

| Node | Meaning |
|---|---|
| `scene` | Location change — swaps backdrop, may trigger a walkable level |
| `n` | Narration text |
| `l` | Dialogue line (speaker + text) |
| `sys` | System event — journal, side quest, evidence, star, ending tag, etc. |
| `choice` | Player choice with optional effects, flags, and sub-blocks |
| `cond` | Conditional branch (stat-based, fact-based, or branch-pointer) |
| `play` | Playable operation (infiltrate / hack / defend / arena / boss / retrieve / explore / free) |
| `final` | The ending door selection |

### Stat & fact memory

The game doesn't track a single "karma" number. It tracks:

- **5 faction stats** (0–100) that drift up and down based on dialogue effects
- **`flags`** — explicit named events (e.g. `autonomy`, `control`)
- **`facts`** — keyword stem sets recorded for every narrative beat the player experiences
- **`sides`** — side quest state (`open` / `done`)
- **`shards`** — collected data shard IDs
- **`memories`** — recovered memory fragments
- **`mysteries`** — outstanding plot threads

`NV.Cond` reads all of these to decide which conditional branches fire, which endings are eligible, and which dialogue variations play.

---

## Graphics tiers

| Tier | Trigger | Resolution | Glow | Post | Rain | Notes |
|---|---|---|---|---|---|---|
| **Low** | Chromebook, mobile, iGPU, ≤4 cores, ≤4GB | 160% scale | off | FXAA only | 450 | no beams, no cones |
| **Medium** | default | 115% scale | ¼ ratio | FXAA | 1500 | beams + cones |
| **High** | discrete GPU | native DPR | ½ ratio | FXAA + chroma + grain | 3600 | ACES tonemap |

The renderer prefers WebGPU, falls back to WebGL2 automatically.

Dynamic resolution adjusts `hardwareScalingLevel` every ~1.2 seconds based on measured FPS.

---

## Endings

Each ending has a stat/flag gate. The game tells you what you're missing.

| Ending | Title | Requirement |
|---|---|---|
| **A** | The Long Blackout | Always available |
| **B** | One Mind, One World | AI Sympathy ≥ 60 |
| **C** | Open Sky | AI Sympathy ≥ 55 + 3 autonomy choices |
| **D** | The Crown of Glass | Corporate Leverage ≥ 58 or Elena alliance |
| **E** | Concord | SQ45 + SQ50 + Hope ≥ 60 + no Dominion alliance |
| **F** | Beyond the Veins | SQ60 + Raven ≥ 55 + Voss ≥ 55 + no absolute control |

---

## Save data

Everything lives in `localStorage`:

- `nv_settings_v1` — user preferences
- `nv_save_v1` — current game state
- `nv_meta_v1` — endings unlocked, chapter snapshots

Chapter snapshots are taken at the start of every chapter, so **Chapter Select** can jump you to any point you've reached.

---

## Known limitations & risks

- **`NV.Cond.pick()` uses fuzzy keyword stems** to match conditions against recent facts. It's clever but can fire on unrelated facts that happen to share stems. Verify branch behavior manually for critical scenes.
- **`runOp` retry loop is unbounded.** A stuck operation can theoretically loop forever. Add a max-retry guard if it becomes an issue.
- **`NV.Quality.detect()` uses GPU name matching.** New GPU models (Adreno 6xx/7xx, M4, etc.) may fall through to the wrong tier. Update the regex as needed.
- **Mid-operation saves don't exist.** Dying restarts from the chapter checkpoint, not from the last objective.
- ~~The `#op=` dev hash is live in production.~~ Fixed: dev hashes now need `#dev&...`.
- **Walkable story scenes are decided by heuristic** (`settings.walk && !chapter70 && has-ghost && theme !== space`). Some scenes become levels, some don't, and the player can't predict which without trying.

---

## File size

Single HTML file, currently around 1MB (grows with script rebuilds). It has been tested up to 100MB+ in similar single-file projects, so size is not a concern for this game.

---

## Credits

- **Engine:** Babylon.js
- **Story & script:** the NEON VEINS script
- **Music & sound:** real-time WebAudio synthesis
- **Everything else:** procedural

> *"Who is outside the model?"*
