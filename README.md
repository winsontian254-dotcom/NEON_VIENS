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

## Weapon stats

Guns and melee weapons are rated on the script's 1–100 sheet: **Damage, Rate of Fire, Accuracy, Stability, Range, Magazine, Armour Penetration and Network Safety**. The Black Market shows each rating as a bar.
- The 25 weapons listed in the script use its exact numbers.
- Every other weapon is rated from its family baseline plus maker traits. Iron Angel gear is heavy and analogue, Helix, Aurex and predictive gear is smart but low on Network Safety, and Rust Harbor, Quiet Mile and Sector 9 gear is hardened.

How each rating plays:
- **Damage** sets hit damage.
- **Rate of Fire** sets the shot interval.
- **Accuracy** sets spread.
- **Stability** sets recoil kick.
- **Range** sets hit distance.
- **Magazine** sets how many shots fill the coil-heat bar before a reload. Reload time depends on the weapon family.
- **Penetration** adds damage against plated drones and bosses, and 75+ pierces a target.
- **Network Safety** matters near live hostile drones: below 50 a weapon's spread widens, and below 25 its smart lock is also lost.

### Upgrade trees

Every owned weapon has the script's five-level tree. Open it from the **LV** button in the Black Market.
- Levels II and IV improve core stats.
- Levels III and V are permanent A/B branch choices, for example:
  - Pistols: Gunslinger or Ghostwork, then Dead Certainty or Clean Exit.
  - Shotguns: Breacher or Crowd Control, then Final Door or Mercy Pattern.
- All ten families have their branches in the game, and each branch works in combat.
- Costs: Levels II–III use Weapon Parts, Level IV uses Military Components, and Level V also needs a Quantum Fragment or Living Cipher Thread for prediction, smart or ASCENSION-linked weapons.

### Ammunition & materials

- **Ammo families:** the script's ammunition families are shared by weapon type:
  - light, rifle, shells, precision, coil, heavy belts, micro-missiles, improvised rockets, power cells, restraint canisters, harpoon bolts and drone tokens;
  - plus the exotic Quantum Charges and Null Capsules.
- **Magazines and reserves:** the coil-heat bar is the magazine. Every shot draws from the family reserve, and the HUD shows `magazine | reserve`.
- **Getting ammo:**
  - You're resupplied to half of your carry limit at every deployment.
  - Fallen enemies drop ammo for the gun in hand, plus Weapon Parts. Lethal kills yield more.
  - Refills are sold in *Ammo & Workbench*.
- **Workbench:** converts a weapon's ammunition. Shotguns take slug, foam, shock or breaching loads for 4 Parts. Any ballistic gun can load Null Capsules or Quantum Charges.
- **Materials:**
  - Drones sometimes drop Military Components.
  - Bosses drop a module: Military Components, a Quantum Fragment and a Living Cipher Thread.
  - Completed operations pay Parts and Military Components.
  - Materials can also be bought.

### Tactical consumables

All 20 of the script's tactical, medical, hacking and crafting consumables are in, with its carry limits.
- **Quick slots:** Ghost carries four. Use **G** or d-pad ↓ to use the selected one, **X** or d-pad ↑ to pick the next slot, or tap a slot on touch screens.
- **Getting them:** buy them and bind them to Q1–Q4 in the Black Market's *Consumables* tab. Enemies sometimes drop common ones, and you start with 2 frags, 1 EMP and 2 Trauma Patches.
- **What they do:**
  - **Throwables:** Frag, EMP (10 s shutdown), Identity-Jamming Gas (breaks locks), Memory-Static, Coolant (also clears your weapon heat), Quantum Decoy (three echoes) and Solar Charge (anti-armour).
  - **Healing:** Trauma Patch heals 35% over 6 s, but heavy damage tears it. Noah's Kit heals 60% and blocks weapon hijacking for 20 s. Repair Foam restores armour, HP and drone life.
  - **Stimulant:** +20% move and reload speed, then 8 s of shaky aim.
  - **Protection:** Oxygen halves blast and fire damage for 90 s. Somatic Firewall stops forced launches for 20 s. The Pallbearer Shell survives one lethal hit.
  - **Hacking and stealth:** Neural Inhibitor pacifies one target. Neural Coolant resets hack cooldowns and cuts them 25%. Exploit Shard halves the next upload. Consent Key adds a stun to hacks and extra lock to smart guns. Signal Scrubber drops every hunter's track. False Telemetry sends hunters to a fake position.

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

## VR Mode (Google Cardboard)

Turn it on from **Settings → Gameplay Mode**, from **Switch to VR Mode** in the pause menu, or from the **VR** button on the story top bar. It switches instantly, with no reload and no lost progress.
- **Display:** a stereo split-screen camera (Babylon's `VRDeviceOrientationFreeCamera`). Lens distortion correction runs on WebGL; on WebGPU the view is split without it. The game asks for fullscreen and landscape.
- **Head tracking:** uses the gyroscope, and on iPhone asks for motion permission the first time. You look to aim, and movement follows your gaze.
- **Controls:**
  - Tap the screen or press the Cardboard trigger to use, take down or hack whatever is in front of you. Otherwise the tap fires. In dialogue, a tap advances the story.
  - Hold the screen to walk.
  - A Bluetooth gamepad works as normal.
- **HUD, dialogue and toasts:** shrunk into the left eye and mirrored into the right, so both eyes can read them.
- **Code:** the whole feature lives in one block in `index.html`, marked `/* ================= Google Cardboard & VR Mode Manager ================= */`.

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

Ten presets run from **Ultra** to **Potato** (plus *How the hell is your PC running WebGPU*). The default is **Auto**:

1. **GPU score.** The GPU's renderer string is matched against a performance table covering:
   - NVIDIA RTX 50–20 and GTX 10/16/9;
   - AMD RX 9000–400;
   - Radeon 8060S/890M/780M and other iGPUs;
   - Intel Arc, Iris Xe and UHD;
   - Apple M-series;
   - Adreno and Mali.

   This gives a rough score (≈ 3DMark Time Spy graphics). Some examples:

   | GPU | Score | Auto tier |
   |---|---|---|
   | Radeon 8060S | ≈ 11.5k | Very High |
   | RTX 3060 | ≈ 8.8k | High |
   | GTX 1660 | ≈ 5.4k | Medium High |
   | Intel UHD 620 | ≈ 0.45k | Very Low |

   Laptop dGPUs are scored lower, phones are capped for heat, and very high-resolution screens drop one tier. Unknown or masked GPUs fall back to CPU cores and memory.
2. **Frame-rate governor.** Dynamic resolution adjusts `hardwareScalingLevel` every ~1.2 s. If that alone can't hold the target frame rate, Auto steps the whole preset down a tier (after ~5 s below 70% of the target), or back up (after ~15 s of headroom), staying within two tiers of the detected one.
3. **Re-detection.** Auto re-detects when the GPU changes. The Graphics menu shows the detected GPU and its score. Picking any preset, or changing any option, turns Auto off.

The renderer prefers WebGPU and falls back to WebGL2 automatically.

---|---|---|---|---|---|---|
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
| **F** | █████ | ... |

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
- **Story & script:** copilot in word
- **Music & sound:** real-time WebAudio synthesis
- **All code:** claude opus 5.5, deepseek v4.1 flash

> *"Who is outside the model?"*
