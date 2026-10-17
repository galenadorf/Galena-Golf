# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Galena!!! Golf**: a mobile, browser-based 3D golf game (installable PWA), forked from SweetSpot (https://github.com/nephlonor/SweetSpot). It has exactly one course, **Woodbine Bend Golf Course** (Stockton IL), built from public geodata. Repo: https://github.com/galenadorf/Galena-Golf, branch `main`, live at https://galenadorf.github.io/Galena-Golf/.

## Ground rules

- **Offline rule.** Solo play must work fully offline with no CDN or third-party dependency. Everything the game needs lives in the repo and `sw.js` caches it. Only live multiplayer (public MQTT brokers) and the world leaderboard (GitHub API, `raw.githubusercontent.com`) may use the network, and they must fail quietly offline. Never add an external script, font or asset: download it into `vendor/` or `fonts/` with its licence and add it to `CORE` in `sw.js`. Sounds are synthesised or embedded as base64.
- **Units.** The UI shows yards (feet on and around the green, mph for wind and ball speed). The engine works in metres. `CLUBS[].carry` is in metres.
- **Git.** Commit and push only when the user asks. `git add -A` skips `tools/course/out/` (ignored), so add paths explicitly and check `git status` after a commit. One commit usually covers `index.html` plus the tools, because they can't be split.
- **The painted masks are not in git.** `tools/course/out/` and `.cache/` are git-ignored, so the user's hand-painted masks (`*_mask.png`, `signs.txt`) and every generated JSON live only on this machine. The game does not need them to run (their results are embedded in `index.html`), but they are the source of truth for the course data. Never delete `out/`; tell the user if you change how they are used.

## Working with index.html

`index.html` is the whole game: HTML, CSS and JS in one file (about 5,900 lines, 0.9 MB), no build step. Three lines are huge embedded data; never print them whole, use `cut -c1-200`: `RD_WOODBINE` (course data, ~295 KB) and `GREEN_ALTI_WOODBINE` are **written by `tools/course/install.py`, never edit by hand**; `SND_B64` (base64 MP3) and `CLUB_SPR` (base64 WebP) are static.

- Edit with small Python scripts that assert each `old` string matches exactly once. Line numbers drift constantly: find things with `grep -n` on the function or constant name. Code is organised under `/* ===== NAME ===== */` banners: UTIL, PHYSICS, REAL COURSE, WORLD (three.js), GAME, UI, STATS + RECORDS, PLAYER + LEADERBOARD, INPUT + LOOP.
- Python offsets are code points but JS/node offsets are UTF-16, and the file contains non-BMP characters. Never apply node-computed offsets from Python; do the splice in node or work by string match.
- **Check JS** after every edit: write the text between the last `<script>` and its `</script>` to a scratch file (`s[s.rfind('<script>')+8 : s.find('</script>', s.rfind('<script>'))]` in Python) and run `node --check` on it. For unused or undefined names, run ESLint (`no-undef`, `no-unused-vars`) on that same file from a scratch folder.
- **Browser testing (WSL, no system browser).** In a scratch folder: `npm i playwright@1.48.2 && npx playwright install chromium`; Chromium lacks `libnss3`, `libnspr4`, `libasound2t64` and there is no sudo, so `apt-get download` them, `dpkg-deb -x <deb> <dir>`, and run node with `LD_LIBRARY_PATH=<dir>/usr/lib/x86_64-linux-gnu`. Serve the repo with `python3 -m http.server` and launch with `--use-gl=swiftshader --enable-unsafe-swiftshader --no-sandbox`. Fill `#nameIn`, click `#btnPlay`, then drive the game through globals (`startHole(i)`, `G`, `W`, `impact()`, `simulateShot()`; overriding `updateCamera = () => {...}` gives a fixed camera for screenshots). Swiftshader is slow, so game time runs well under real time. There is no test suite; "tested" means all 18 holes load with every tee and cup in bounds, a shot plays, and the page logs no errors (MQTT WebSocket errors are expected offline).
- `.github/workflows/pages.yml` deploys on push to `main`: copies `index.html manifest.webmanifest sw.js *.png icon.svg vendor fonts`, replaces `__BUILD__` with the commit SHA in `index.html` and `sw.js`, writes `version.txt` (the running game reloads itself when it changes). `sw.js` is network-first for the page (cache after 4 s), cache-first otherwise, cache name `galena-<BUILD>`; it needs https or localhost.
- `.github/workflows/leaderboard.yml`: players post scores as issues titled `[score] ...` with a JSON body; the workflow validates, appends to `leaderboard/<course>.json` and closes the issue. Its `COURSES` map is course key to par (`woodbine: 72`). Score posting points at `GH_REPO`; `GH_POST_KEY` is empty, so players get a pre-filled issue page. `_original/` (git-ignored) is an untouched copy of the fork, for reference.

## Architecture

**Data to game.** `tools/course/` (Python) turns public geodata into one data object, `RD_WOODBINE`, that `install.py` splices into `index.html`. At run time: `setCourse` (`COURSES`, `RDS`, `WOODBINE_DEFS`) selects it; `realPrep` decodes the course-wide data once (`GC`); `makeRealCourse(idx, pin)` builds one hole as a lattice of fields (fairway, green, tee, sand, water, creek, fescue distance fields) plus the ground height, dug greens, ponds, bunkers and creek pieces, and returns the `C` object the whole game uses (`C.surf`, `C.h`, `C.wl`, `C.cup`, `C.treeHit`); `buildRealHole` makes the three.js scene (terrain shader, trees, buildings, props, wildlife). Surface class is decided in `surfInfo` in a fixed precedence (water, sand, green, fringe, tee, path, fairway, first cut, deep, rough); the tall fescue is the only `DEEP`. Everything outside the hand-painted boundary is out of bounds.

**Ball flight.** `simulateShot(C, o)` is a fixed-step simulation (drag, lift and spin fitted to TrackMan data; surface bounce, roll, trees, buildings, cup). `calibrateClubs()` solves each club's ball speed at start-up so a full swing on flat ground carries exactly `CLUBS[].carry`; `launch` and `spin` shape the flight and roll, `smash` only sets the displayed clubhead speed. `impact()` turns the swing (`SW`: tempo, strike dot) into a launch, runs the simulation, and `updateFlight(dt)` plays the recorded frames back with the camera (`camFollowTargets`), trail, particles and slow-motion. The "Dramatic bounce" setting (`drama()`, `HOP_K`, `BALL_CAP`) only changes how the flight is drawn, never the physics.

**Round state.** `G` holds the round (scores, putts, `G.pins`, weather); `saveRound` persists it per course; each round draws a random pin (front, back, left, right) per hole.

**Tunables worth knowing:** `CLUBS` (carry in metres, launch, spin, smash), `WOBBLE` (strike-dot wobble), `HIT_PITCH`/`HIT_VOL`/`HIT_LP` (strike sound), `HOP_K`, `FESCUE_HSL`/`FESCUE_COLS`, `SFX.gobble`/`SFX.tap` (synthesised), turkey count in `buildLife`.

**Switched off but kept.** Engine features from the removed Augusta and Alsace courses stay for reuse: swirling wind, pine straw, azaleas, stone bridges, loblolly pines, the `lush`/`dry` palettes, tiered greens, and the synthesised music engine (`musicWanted` needs `COURSE.music`, which nothing sets). The Legacy course (original 18 made-up holes) was removed; it is in git history before 2026-10-17.

## Course data pipeline (`tools/course/`)

Python venv `~/.venvs/galena` (numpy, scipy, rasterio, pyproj, shapely, pillow, laspy[lazrs], scikit-image, requests, pyflakes). Run from `tools/course/`; `pyflakes *.py` must stay clean. Frame: local transverse Mercator in metres around `ORIGIN` (`common.py`); the scorecard is in `card.py`.

1. Geodata (re-run only if needed): `fetch.py` (OSM via Overpass with a `User-Agent`, NAIP aerial 0.5 m, USGS 1 m DEM), `lidar.py` (canopy model from the 2019 lidar), `trace.py` (first-pass fairways; still the base map for fairway painting), `trees.py` (lidar trees), `creek.py` (creek centre line from the DEM channel).
2. Painted layers: the user paints a copy of a generated map and saves a PNG (solid colours, hard edges, never resized or cropped); a reader script turns it into polygons. All maps share the pixel grid of `fescue_base.json` except trees and creek, which have their own frame JSON.

| Layer | Make the map | User saves | Reader (output in `out/`) | Colour |
|---|---|---|---|---|
| fescue (deep rough) | `fescue_base.py` | `fescue_mask.png` | `fescue.py` → `fescue.json` | magenta `#FF00FF` |
| course boundary (OB) | `fescue_base.png` | `course_boundary.png` | `boundary.py` → `boundary.json` | cyan `#00FFFF` |
| fairways | `fairway_edit.py` | `fairway_mask.png` | `fairways.py` → `fairways_painted.json` | green `#00FF00` |
| bunkers | `bunkers_edit.py` | `bunkers_mask.png` | `bunkers_paint.py` → `bunkers_painted.json` | orange `#FF8000` |
| trees | `trees_edit.py` | `trees_mask.png` | `trees_paint.py` → `trees_painted.json` | orange broadleaf, blue `#0080FF` conifer, magenta shrub |
| creek | `creek_edit.py` | `creek_mask.png` | `creek_paint.py` → `creek_painted.json` | blue `#0000FF` |
| site props | `site_edit.py` | `site_mask.png` + `signs.txt` | `site_paint.py` → `site_props.json` | cyan washroom, blue door strip, orange porta-potty, yellow sign |
| tee boxes (shelved) | `tee_boxes_edit.py` | `tee_boxes_mask.png` | `tee_boxes_paint.py` → `tees_painted.json`, `tee_starts.json` | magenta boxes, yellow start dots |

   `bunkers_auto.py` found six bunkers OSM lacks (`bunkers_auto.json`); `bunkers_painted.json` replaces OSM and auto bunkers when present. Signs: `signs.txt` lines like `7: LINE ONE | LINE TWO`; a yellow dot whose nearest hole has no line is not built.
3. `build.py` encodes everything into `out/rd_woodbine.js`; it prefers painted files over generated ones, clips fescue to the boundary, links each hole's fairway to its green by convex hull (`link_fairways`, so no gap of rough), and snaps the four tee sets (gold, black, silver, bronze) to the tee boxes at their card yardages. Cart paths are deliberately dropped.
4. `install.py` writes the data into `index.html`. Then `node --check` and a headless run.

To change a layer: repaint the mask, run its reader, then `build.py` and `install.py`.

## Woodbine Bend reference

Woodbine Bend Golf Course, 3500 E Center Rd, Stockton IL (Jo Daviess County): Lohmann/Benkusky links-style course (~2002), par 72, open rolling farmland with native fescue, mounds, a creek, two ponds, 31 OSM bunkers. Default tees: **Gold** (6,223 yd); Black, Silver and Bronze are only markers. Holes 2 and 7 have alternate tee lengths.

| Hole | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Par | 4 | 3 | 4 | 5 | 4 | 4 | 3 | 4 | 5 | 4 | 3 | 4 | 4 | 4 | 3 | 5 | 4 | 5 |
| Hcp | 8 | 16 | 18 | 6 | 12 | 2 | 14 | 4 | 10 | 13 | 17 | 5 | 1 | 15 | 7 | 3 | 11 | 9 |
| Gold 70.3/121 | 370 | 133/143 | 306 | 514 | 343 | 412 | 157/154 | 384 | 467 | 329 | 148 | 372 | 392 | 319 | 182 | 513 | 398 | 474 |

Gold total 6,223; Black 6,539; Silver 5,908; Bronze 5,192 (full card in `tools/course/card.py`, from woodbinebend.com/scorecard, 2024). Sources: OpenStreetMap (ODbL; way 295902659 is the course), USGS 3DEP 1 m DEM (`IL_8County_PlusChampaign_2019_B19`), USGS lidar `IL_8County_PlusChampaign_B2_2019` (the 2025 `IL_22County_D25` set is not reachable from this machine), USDA NAIP via Microsoft Planetary Computer (`il_m_4209047_ne_15_030_20230710_20230929`, July 2023).

## Open items

- New icons (`icon.svg`, PNGs, `apple-touch-icon.png`; still SweetSpot artwork) and a theme colour in `manifest.webmanifest` and `<meta name="theme-color">`.
- Play a full round on a phone and post a score (score posting is untested end to end).
- Tree species (broadleaf, conifer, shrub) is a guess from crown shape and near-infrared.

## Adding another course

A course is an `RD_<NAME>` object (hole lines, par, hcp, tee sets, feature polygons, trees, coarse DEM plus relief; encoding in `tools/course/build.py`). Adapt `common.py` (origin, areas) and `card.py`, then add: an `RDS` entry (data, alti, z0, grid, tweaks, optional `lush`/`dry`/`fescue`), a `<NAME>_DEFS` hole list, a `COURSES` entry (`key`, `name`, `short`, `defs`, `best`, `board`, `coll`, optional `music`), its key and par in the leaderboard workflow plus `leaderboard/<key>.json`. Show the hidden course pickers again (`#segCourse` on the title screen, `#segCourseM` in Settings: remove `hidden`) and update the credits text.
