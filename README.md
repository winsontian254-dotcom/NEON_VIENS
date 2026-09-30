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
| Enter / exit vehicle (free roam) | `F` | X |
| Drive: throttle / reverse, steer | `W`/`S`, `A`/`D` | RT / LT, left stick |
| Drive: handbrake, boost, horn | `Space`, `Shift`, `H` | A, LB, R3 |
| Pause · Black Market | `Esc` | Start |
| Hotbar slot / cycle | `1`–`9` / wheel | RB |
| Zoom (precision rifles) | RMB | — |
| Chat (multiplayer) | `Enter` | — |
| Volume down / up, mute | `-` / `=`, `M` | — |
| Jump (the void after the ending) | `Space` | A |
| Advance dialogue | `Space` / click | A |
| Choose option | `1-4` / click | dpad + A |
| Auto-advance dialogue | `A` | — |
| Hold to skip | `Ctrl` | RB |
| Backlog | `L` | — |
| Journal | `J` | — |

---

## Climbing & skydiving

In the city, keep pushing forward into a building to climb its wall; release forward to hang, dash to let go. At the top you mount the roof and can climb taller neighbours. Walk off an edge and you fall; drops longer than ~12 m become a steerable third-person skydive, and hard landings (street or roof) knock Ghost into a ragdoll. Guards lose sight of you on high rooftops.

## Parkour

City-only moves, built on the climbing system:
- **Running jump**: `Space` while sprinting (pad A, or DASH while running on touch). It carries extra momentum for roof-to-roof gaps. `Space` without sprint is still a dash.
- **Wall-run**: jump beside a tall wall while running forward to run along it. Jump again to kick off it.
- **Vault / mantle**: run into anything up to ~2.4 m above your feet (crates, low roofs, ledges mid-air) to vault straight on top.
- **Slide**: press crouch while sprinting.
- **Roll**: land a 12–27 m/s drop while sprinting or crouching to roll out instead of ragdolling.

## Arsenal & Black Market

Pause (**Esc**) → **Black Market** to buy from the arsenal: 267 weapons, tools, drones, cyberattacks, environmental triggers, boss gear, strategic strikes and legendaries from the script. Pick a hotbar slot and equip; right-click a slot to clear it.

- Hotbar: **1–9** or mouse wheel (RB on gamepad). **LMB** uses the selected item, **RMB** zooms precision rifles.
- Each item's behaviour comes from what it is: smart/predictive guns home in, rail/phase guns pierce, Echo guns repeat their shot, Null/EMP gear stuns and fries drones, nonlethal gear takes enemies down alive, melee is silent and one-shots unaware guards.
- Grenades, rockets and mines have area effects: frag, EMP, sleep gas, coolant freeze, decoys and gravity. Hacks can stun, turn guards against their squad, overload them, blind a squad, mark every hostile, or cloak you. Drones attack, heal, jam sensors or shield you. Environmental and strategic weapons call in crane drops, floods, coolant, kinetic rods, solar beams and barrages at the point you aim at.
- Every item has its own procedural 3D viewmodel (pistol, SMG, rifle, shotgun, sniper, rotary, laser, launcher, grenade, blade, hammer, baton, wrist rig, drone remote, strike designator), coloured by faction.
- Credits: 9 ¢ per kill, 14 ¢ per nonlethal takedown, 150 ¢ or more per completed operation, plus gigs and data shards. Multiplayer sessions start with 3000 ¢.

## VR (WebXR)

Settings → **VR headset mode** (the page reloads). WebXR can't run on WebGPU, so VR mode uses Babylon's WebGL2 renderer. Then press the headset button in the bottom-right corner to enter VR. Works in the Quest Browser, or desktop Chrome/Edge with a PC VR headset. The page must be served over https or from localhost.

| Action | Controller |
|---|---|
| Move / drive | Left stick |
| Snap turn (30°) | Right stick |
| Fire / use hotbar item | Right trigger (the weapon sits in your right hand and aims where it points) |
| Interact (E) | Grip |
| Advance dialogue / confirm | A |
| Next hotbar item | B |
| Vehicle (F) | X |
| Sprint | Y |

A floating panel in front of you mirrors health, energy, the objective, prompts, dialogue and toasts, because HTML overlays can't be shown inside a headset. Menus (pause, Black Market, settings) still need you to take the headset off.

## Controllers & touch

**Gamepad** (standard layout): left stick move, right stick look, RT fire, LT zoom (precision rifles) or brake, A dash-stop / confirm / jump, B dash / back, X interact (hold near a car to enter), Y EMP, LB sprint / boost, RB or d-pad left/right switch hotbar item, L3 sneak, R3 horn, Select fast travel, Start pause. The left stick and d-pad navigate every menu, including the Black Market and Multiplayer screens. Gentle aim assist and rumble come on while you're using a controller.

**Touch** (phones/tablets, appears on first touch): left thumb joystick (push fully forward to sprint), drag anywhere on the right to look, buttons for fire, interact, dash, EMP, car, sneak, zoom and pause, and tap a hotbar slot to select it. Touch gets the same gentle aim assist. Menus, dialogue and choices are simply tapped.

**Mobile**: on phones and tablets the game detects the device, drops to lighter graphics, goes fullscreen and locks to landscape on the first tap, asks you to rotate the phone in portrait, pauses when the app goes to the background, and can be added to the home screen as a full-screen app. It needs a browser with WebGPU (recent Chrome on Android, Safari 26+ on iOS).

## Multiplayer

Title → **Multiplayer**. One player hosts and gets a 6-character join code; friends type it in to join (drop-in, any time).

- Peer-to-peer over WebRTC. [PeerJS](https://peerjs.com) is loaded from the jsDelivr CDN only when you open multiplayer, and its free public server is used just to connect players. After that, game traffic goes directly between players, relayed by the host.
- No story in multiplayer: the open world plus co-op missions. The host starts missions from the pause menu (**Co-op Missions**), and everyone drops in next to the host.
- Role-play: every player picks a character from the script, is seen by others as that character (name tag shows character · player name), and chat (**Enter**) appears in a bubble over their head and is spoken in that character's voice.
- Shared: enemy takedowns, hacked terminals, pickups, freed civilians, boss damage, mission success/failure. Traffic and pedestrians are local to each player.
- Friendly fire is a host option (off by default). Going down in a co-op mission respawns you at the start point.
- Multiplayer never touches your story save.
- Limitations: some strict networks (symmetric NAT, corporate/school firewalls) block direct peer-to-peer connections, and there is no TURN relay fallback.

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
