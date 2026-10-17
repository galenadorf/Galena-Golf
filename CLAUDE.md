# Galena!!! Golf

A mobile, browser-based 3D golf game (installable PWA), forked from **SweetSpot** (https://github.com/nephlonor/SweetSpot) and being customised into **Galena!!! Golf**.

**Offline rule:** all solo play must work fully offline, with no CDN or other third-party dependency. Every file the game needs lives in this repo, and `sw.js` caches it. Only **live multiplayer** (public MQTT brokers) and the **world leaderboard** (GitHub API and `raw.githubusercontent.com`) need a connection; they must fail quietly when offline. Don't add new external scripts, fonts or assets: download them into `vendor/` or `fonts/` (with their licence) and add them to `CORE` in `sw.js`.

**Goal:** a rebrand plus gameplay changes, with **exactly one course: Woodbine Bend Golf Course** (`woodbine`, Stockton IL). It replaced the placeholder Golf & Country Club Basel (`gccb`), which is now removed. The UI shows **yards** (feet on and around the green, mph for wind and ball speed); the engine works in metres.

## Project layout

- `index.html` — **the entire game**: HTML, CSS and JS in one file (~7,320 lines, ~1 MB). There's no build step for the game.
- `vendor/` — three.js r128 (`three.r128.min.js`, the global build) and mqtt.js 5.10.1 (loaded only when multiplayer starts), byte-identical to the npm builds, with their MIT licences.
- `fonts/` — Oswald (variable) and Barlow 500/600/700 as `.woff2`, all subsets Google Fonts serves, plus `fonts.css` and the OFL licences.
- `sw.js` — service worker for offline play: precaches `CORE` (page, icons, vendor, fonts), network-first for the page (falls back to the cache after 4 s), cache-first for everything else; it doesn't touch other origins or `version.txt`. Its cache is `galena-<BUILD>`, so each deploy replaces it. Registered at the end of `index.html`; needs https or localhost.
- `manifest.webmanifest`, `icon*.png`, `icon.svg`, `apple-touch-icon.png` — PWA metadata and icons (the icons are still SweetSpot's artwork).
- `leaderboard/woodbine.json` — the world leaderboard (empty).
- `tools/course/` — the Python pipeline that builds the course data (see *Rebuilding the course data* below). Its `.cache/` (downloads) and `out/` (results, preview images) are git-ignored.
- `.github/workflows/pages.yml` — deploys to GitHub Pages: copies the files (including `sw.js`, `vendor/` and `fonts/`), replaces `__BUILD__` with the commit SHA in `index.html` and `sw.js` and writes `version.txt` (the game reloads itself when that file changes).
- `.github/workflows/leaderboard.yml` — players post scores as GitHub issues titled `[score] ...` with a JSON body. The workflow validates them, appends them to `leaderboard/<course>.json` and closes the issue. Its `COURSES` map holds course key → par.
- `_original/` — an untouched copy of the files as forked (index.html, manifest, leaderboard, .github). It's for reference only and isn't deployed.
- Git repo: https://github.com/galenadorf/Galena-Golf (branch `main`). `_original/` is git-ignored.

### Working with index.html

Several lines are huge embedded data. Don't print them whole; cut them with `cut -c1-200`.
- line ~1804 `RD_WOODBINE` (~290 KB of course data; written by `tools/course/install.py`, never edit by hand)
- line ~2000 `GREEN_ALTI_WOODBINE` (green elevation grids; also written by `install.py`)
- line ~4886 `SND_B64` (sound effects as base64 MP3)
- line ~6294 `CLUB_SPR` (club-head sprites as base64 WebP)

Do edits with small Python scripts that assert each `old` string matches exactly once. Check the JS afterwards by extracting the last inline `<script>` and running `node --check`.

**Browser testing on this machine (WSL):** there's no system browser, and Playwright's Chromium is missing `libnss3`, `libnspr4` and `libasound2t64` (installing them needs sudo). Workaround without sudo: `npm i playwright@1.48.2 && npx playwright install chromium` in a scratch folder, then `apt-get download libnss3 libnspr4 libasound2t64`, extract each with `dpkg-deb -x <deb> <dir>`, and run node with `LD_LIBRARY_PATH=<dir>/usr/lib/x86_64-linux-gnu`. Serve the folder with `python3 -m http.server` on localhost; launch Chromium with `--use-gl=swiftshader --enable-unsafe-swiftshader`. A player name must be filled in (`#nameIn`) before `#btnPlay` starts a round.

### Code map (line numbers approximate; each section starts with a `/* ===== NAME ===== */` banner)

| Lines | Section |
|---|---|
| 14–353 | CSS. Theme variables on `:root` (line 17): greens `--g1..g3`, `--yel`, fonts Oswald and Barlow |
| 354–433 | HTML: HUD, title screen (h1 at 383), menus and sheets; help/credits text at ~427 |
| 434 | UTIL (noise, maths); unit helpers `toYd`, `toFt`, `toMph`, `fmtM`, `fmtDistShort`, `holeYd` (~473) |
| 481 | PHYSICS: ball flight fitted to TrackMan data; `SURF` surfaces (493), `WEATHERS` (510), **`CLUBS` table (537)** |
| 1012 | COURSE: the procedural "Legacy" course (switched off via `LEGACY_ON = false`) and the terrain builder |
| 1807 | REAL COURSE: decoders, `realPrep()` (course-wide data), `makeRealCourse` (one hole), `buildRealHole`, trees, decor. `RD_CUR` is the data set in use |
| ~2983 | `WOODBINE_DEFS`, `RDS` (data set per course, ~2985), `COURSES` (~2995), `setCourse()` (~3004) |
| 3020 | WORLD (three.js): terrain shaders, tilt-shift, rain, particles |
| 4012 | PROPS & DETAIL: walls, buildings, shrubs, wildlife, plane, paraglider |
| 4872 | GAME: settings, `LB_EPOCH` (4877), audio, live multiplayer over MQTT (~4945), synthesised music |
| ~5410 | state `G`, swing `SW`, saving the round in progress (`ssg-round-<course>`), swing input, flight playback, camera |
| 6120 | UI: tempo panel, strike dial, HUD, sheets, hole map |
| 6783 | STATS + RECORDS |
| 6880 | PLAYER + LEADERBOARD (local board and GitHub board; `GH_REPO` at 6887) |
| 7052 | INPUT + LOOP |

## Done so far (session of 2026-10-16)

1. **Removed the Augusta National and Alsace courses**, the two largest: their data blobs (`RD_AUGUSTA`, `RD_ALSACE`), hole definitions, `RDS`/`COURSES` entries, picker buttons, credits text, leaderboard files, and their entries in the workflow's `COURSES`. The file went from 2.4 MB to 0.9 MB.
2. **Course pickers hidden**: both rows (`#segCourse` on the title screen, `#segCourseM` in Settings) have the `hidden` attribute while there's only one course. Each holds a `woodbine` button.
3. **Music is now a per-course flag**: `musicWanted()` checks `COURSE.music`. No course has it set, so the Music menu row (`#musRow`) stays hidden; `setCourse()` toggles it. Augusta's synthesised guitar-and-piano engine is still in the code.
4. **Engine features kept but switched off** (they were driven by the removed courses and could be reused): swirling wind (`def.swirl`, `swirlWind`, `buildSwirlFx`), the `RDC.lush` / `RDC.dry` palettes, pine straw, stone bridges and loblolly pines. Comments still mention Augusta and Alsace to explain where these came from, and so do some hole descriptions in the disabled Legacy course.
5. **Renamed to "Galena!!! Golf"**: `<title>`, the apple web-app title (`Galena!!!`), the title-screen `<h1>Galena<span>!!!</span><br>Golf</h1>`, the logo's alt text, the share-link title, the score-post issue text, and the manifest's `name`/`short_name`.
6. Verified with `node --check` and a search for leftover references only. Since then: headless-Chromium tested on 2026-10-16 (title screen, fonts, three.js, starting a round, online and with the server stopped), and the live site works on the user's phone. A full round with score posting hasn't been tested yet.

## Ball flight visibility (2026-10-17)

"Dramatic bounce" (Settings, `settings.drama`, on by default; `drama()` and `HOP_K` near `saveSettings`): the ball sits on the ground at any drawn scale (centre lifted by `VIS_R * scale`), hops after the first landing are drawn 2.2x as high (`hopY`; physics untouched), a flat roll-out trail (`W.trail`) and a landing ring (`W.landRing`), a puff on every bounce, a lower chase camera after landing (`camFollowTargets`, `R.pk`), a short slow-motion over the first landing of hard-hit shots (`updateFlight`, `rate`), and the drawn ball shrinks from 7x to 4x while it rolls (`BALL_CAP`). Tune `HOP_K`, the 7/4 caps and the 7 m / 1.7 m camera numbers by feel on a phone.

## Club carries (2026-10-17)

`CLUBS` (~line 538) `carry` is in metres (a full swing, flat, calm). Set 2026-10-17 from yards: Dr 250, 3W 230, 5W 220, 4H 205, 5i 185, 6i 175, 7i 165, 8i 155, 9i 145, PW 135, GW 125, SW 115, LW 100 yd (carry = yd / 1.09361). The game solves each club's ball speed from it at startup. `smash` only sets the clubhead speed shown (clubhead = ball speed / smash; the ball speed itself is solved from the carry), so it was divided by 1.0405 for every club to put the driver at 110 mph and the 7 iron at 89 mph without changing any carry.
Launch and spin (2026-10-17): launch raised 1.2 deg for Dr-4H, 1.1 for 5i, 0.6 for 6i, 0.3 for 7i (Dr 13.2, 3W 12.6, 5W 13.6, 4H 14.4, 5i 15.0, 6i 15.9, 7i 17.3); spin cut 12 % on GW/SW/LW and 11 % on PW (PW 8300, GW 8600, SW 9000, LW 9300), a little less on 8i/9i. `smash` was then re-solved per club (ball speed / the previous clubhead speed) so every clubhead speed stayed the same; a lower wedge spin needs less ball speed, so wedge smash is now 1.09-1.17 (display only).

## Wildlife (2026-10-17)

The deer are gone: `makeTurkey(L, tom)` / `turkeyParts` (near `makeRabbit`, ~line 4477) put a tom and two hens across the fairways, three rabbits as before. Same behaviour as the deer did (cross the line of play, stop to peck, run when the ball comes near, can be hit: "Clipped a turkey!" with a synthesised gobble, `SFX.gobble`, played from `lifeHitNote`). Low-poly box-and-sphere models, bob and peck animation by head pivot; tune sizes in `turkeyParts`, speeds in `e.update`, count in `buildLife`.

## Strike sound (2026-10-17)

`HIT_PITCH` (.88), `HIT_VOL` (.76) and `HIT_LP` (2400 Hz) above `SFX` soften the recorded club-on-ball sample (pitched down, high end rolled off, quieter), full shots, mishits and putts alike. Tune them there.

Putts do not use that sample: `SFX.tap(speed)` (synthesised: a short low thud, a faint click and a noise tick, level .55-1 by stroke speed) is played from `SFX.hit` when `putt` is true.

## To do before publishing

- [x] **Score posting** now points at `GH_REPO = 'galenadorf/Galena-Golf'` (line ~6887). `GH_POST_KEY` is now emptied (it was the original author's token), so players get a pre-filled issue page; to post silently, add your own fine-grained token (Issues read/write on that repo only).
- [x] **Video removed**: the intro layer (`#vidIntro`) and the help-sheet video are gone from the HTML, and `pages.yml` now copies `*.png icon.svg` only. Dead CSS and the null-guarded `initIntroVideo()` remain. To bring a video back, add `swing-explainer.mp4` and `swing-poster.jpg` and restore the copy step.
- [x] **Multiplayer prefix** changed to `galena/v1/` in `mpT` and the subscribe string.
- [x] the leaderboard reset (now `leaderboard/woodbine.json`) and `LB_EPOCH` bumped to `2026-10-16-galena`. Syntax-checked with `node --check` (node v22) on 2026-10-16: OK.
- [ ] New icons (`icon.svg`, PNGs, `apple-touch-icon.png`) and a theme colour if wanted (`manifest.webmanifest` and `<meta name="theme-color">`).
- [ ] Optional: the `ssg-` localStorage keys are harmless and can stay.
- [x] Git repo set up and Pages enabled; live at https://galenadorf.github.io/Galena-Golf/ (first deploy 2026-10-16).

## The course: Woodbine Bend Golf Course

Decided with the user on 2026-10-16:
- **Course:** Woodbine Bend Golf Course, 3500 E Center Rd, Stockton, IL 61085 (near Elizabeth, IL; Jo Daviess County). Display name **"Woodbine Bend Golf Course"**. Lohmann/Benkusky design, ~2002, public, links-style: open, rolling farmland with native tall grass, mounds ("moguls"), a creek, 2 ponds and 31 bunkers. Par 72 (36/36).
- **Default tees: Gold** (6,223 yd). The other three tee sets (Black, Silver, Bronze) are only shown as markers.
- **Units: yards** everywhere in the UI. Internal maths stays in metres.
- **Fairways: traced from the USDA NAIP aerial** (2023, 30 cm), because OSM has none; show the user an overlay to check.
- **Scorecard (official card, woodbinebend.com/scorecard, 2024):**

| Hole | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Par | 4 | 3 | 4 | 5 | 4 | 4 | 3 | 4 | 5 | 4 | 3 | 4 | 4 | 4 | 3 | 5 | 4 | 5 |
| Hcp | 8 | 16 | 18 | 6 | 12 | 2 | 14 | 4 | 10 | 13 | 17 | 5 | 1 | 15 | 7 | 3 | 11 | 9 |
| Black 71.8/124 | 394 | 151/159 | 325 | 524 | 359 | 422 | 200 | 405 | 486 | 343 | 172 | 389 | 406 | 321 | 201 | 535 | 420 | 478 |
| Gold 70.3/121 | 370 | 133/143 | 306 | 514 | 343 | 412 | 157/154 | 384 | 467 | 329 | 148 | 372 | 392 | 319 | 182 | 513 | 398 | 474 |
| Silver 69.3/118 | 347 | 124/133 | 295 | 488 | 330 | 402 | 147/142 | 370 | 454 | 319 | 131 | 359 | 386 | 304 | 168 | 498 | 326 | 451 |
| Bronze 70.4/116 | 303 | 105/115 | 272 | 410 | 314 | 340 | 113 | 331 | 396 | 299 | 104 | 302 | 340 | 294 | 134 | 420 | 292 | 413 |

Totals: Black 6,539 · Gold 6,223 · Silver 5,908 · Bronze 5,192. Holes 2 and 7 have two alternate tee lengths.

**Data sources (all public domain or ODbL):**
- OpenStreetMap (way 295902659 is the course): all 18 hole lines with par/handicap (matching the card), 18 greens, 54 tees, 31 bunkers, 18 pins, ponds, the creek, buildings. **No fairways, no cart paths.** Overpass needs a `User-Agent` header or it answers 406.
- USGS 3DEP 1 m DEM, project `IL_8County_PlusChampaign_2019_B19` (tiles x73y469, x73y470, 16 x24y470).
- USGS lidar point cloud `IL_22County_D25` (2025), for trees and mounds.
- USDA NAIP via Microsoft Planetary Computer STAC: `il_m_4209047_ne_15_030_20230710_20230929` (30 cm, July 2023).

### Status (2026-10-16)

**Playable and installed**, GCCB removed. Headless-tested: all 18 holes build without errors, each starts on a tee with the cup on the green, hole cards show the Gold yardages, the HUD shows yd/ft/mph. Not yet played on a phone.
- In `index.html`: `RD_WOODBINE`, `GREEN_ALTI_WOODBINE`, `WOODBINE_DEFS`, `RDS.woodbine` (z0 200, class map `gr` 2 km square around the origin), `COURSES.woodbine`; default course `woodbine` everywhere `gccb` used to be. Tee markers use per-course colours (`RD_WOODBINE.mkc`: gold, black, silver, bronze). Hole names "Hole N"; hole notes generated (elevation in ft, water side, bunkers, mounds).
- GCCB-only code removed: its data, hole list, hand-tuned trees, benches, weather station, the hole-14 lost-ball rule. Generic engine features stay (tiered greens via `RDS[key].tiers`, tree tweaks, benches list).
- Leaderboard: `leaderboard/woodbine.json`, workflow `COURSES = { woodbine: 72 }`.

### Rebuilding the course data

Python venv at `~/.venvs/galena` (numpy, scipy, rasterio, pyproj, shapely, pillow, laspy[lazrs], scikit-image, scikit-learn, requests). Run in `tools/course/`, in order; each step caches its downloads in `.cache/`:
1. `fetch.py` — OSM (Overpass), NAIP aerial (Planetary Computer, signed URLs), USGS 1 m DEM (TNM, read as COGs).
2. `lidar.py` — canopy height `.cache/chm.tif` from the 2019 lidar on the public AWS bucket (Entwine, only the octree nodes over the course, ~66 MB). The 2025 lidar exists but `rockyweb.usgs.gov` doesn't answer from this machine.
3. `trace.py` — fairways (per-hole random walker on the aerial, seeded along OSM hole lines; par 3s get none) and rough cart paths → `out/fairways.json`, `out/paths.json`.
4. `trees.py` — single trees from the canopy model → `out/trees.json`.
5. `build.py` — everything encoded as `out/rd_woodbine.js` (dem 15 m, relief 2 m, polygons, trees, holes with tee sets snapped to the OSM tee boxes at the card yardages).
6. `install.py` — replaces the two data lines in `index.html`. Then `node --check` and a headless run.
- `preview.py [fair]` draws the aerial and a hillshade with everything on top (`out/aerial_*.jpg`, `out/relief_*.jpg`). `card.py` holds the scorecard, `common.py` the frame (local transverse Mercator around `ORIGIN`) and areas.

### Open items for the course
- [ ] **User to review the fairway overlay** (`tools/course/out/aerial_fair.jpg`). Known: hole 5 takes in some mown ground by the back tees; par 3s have no fairway (mown rough plus the automatic first cut).
- [x] **Cart paths** removed from the whole course (2026-10-17): `build.py` sets `paths = []`, so `RD_WOODBINE` has none. `trace.py` still writes `out/paths.json` but nothing reads it.
- [x] **The creek** (2026-10-17): `tools/course/creek.py` traces the DEM channel (past the clubhouse and behind 16's green) to `out/creek.json`; `build.py` cuts it into 14 m ribbons (`feat.creek`, 4 m wide) that the engine digs as creek pieces and treats as water (penalty). Run `creek.py` before `build.py`. The four OSM ponds were already in. Headless-checked: holes 9, 10, 12, 13, 16, 17, 18 get creek pieces.
- [x] **Course boundary / out of bounds** (2026-10-17): hand-painted, not OSM. `out/course_boundary.png` (solid cyan over `fescue_base.png`, same pixels) → `boundary.py` → `out/boundary.json` (48.8 ha; OSM's outline was 54.0) → `build.py` (`boundary`, and the fescue is clipped to it) → `install.py`. Anything outside it is OB. Headless-checked: every tee and cup is inside it. Per-hole build time did not change measurably (about 1.6 s for all 18 holes either way), so the boundary was not the performance problem.
- [ ] Tree species is a guess (crown shape plus NIR): 505 broadleaf, 281 conifer, 38 shrubs.
- [x] **Fescue** (2026-10-17): the deep rough (clumpy tall grass, `S.DEEP`) is now exactly the areas painted on `tools/course/out/fescue_base.png` → `out/fescue_mask.png` (pure magenta). Pipeline: `fescue_base.py` (makes the base map; only needed once), `fescue.py` (mask → `out/fescue.json`, 14.2 ha, 88 areas), then `build.py` (`feat.fescue`) and `install.py`. Engine: `hasFescue` in `makeRealCourse` sets `deepF` from the polygons (plus 0.9 m of edge noise); a course without `feat.fescue` keeps the old distance rule. Fairway, first cut, greens, tees, bunkers and water still take precedence, so a 2.8 m first cut remains along fairway edges. Outside the course boundary stays deep as before.
- [x] Fescue colour (2026-10-17): tan/amber. `RDS.woodbine.fescue = true` switches the deep rough to `FESCUE_HSL` (ground; terrain shader `cDeep` and the hole-map colour) and `FESCUE_COLS` (blades and tufts), near `GRASS_COLS`. Tune those two by eye; the shader darkens colours a lot, so `FESCUE_HSL` has to be light (`[.155, .36, .64]` renders as a greenish tan; `.125, .44, .68` was too brown). On a fescue course the tall grass blades (`groundJob`) are drawn only in the fescue, and land outside the course boundary that is not painted is normal rough, not deep (it used to be deep, which put fescue clumps in unpainted ground). Pond-edge reeds (`decor`, ~line 2810) still stand in regular rough by design. The far class map (beyond the hole window) follows the same rule: outside-boundary and wooded cells are `cOut` (= `cRough` on a fescue course) in `farColor` and `farSurf`; only the painted fescue class draws and plays as deep. Try `dry: true` in `RDS.woodbine` (the links palette) or a tan tint.
- [ ] Playtest a full round on a phone, and post a score.

## Adding another course (general)

A real course is a `RD_<NAME>` data object (holes with par, hcp, len, yd, lens, tee, green, line, mk, desc; feature polygons, trees, a coarse DEM plus optional relief; see `tools/course/build.py` for the encoding). The pipeline in `tools/course/` is written for Woodbine Bend but adapts by changing `common.py` (origin, areas) and `card.py`. It also needs:
1. an entry in `RDS` (data, alti, z0, grid, tweaks, optional `lush`/`dry`),
2. a `<NAME>_DEFS` hole list,
3. an entry in `COURSES` (`key`, `name`, `short`, `defs`, `best`, `board`, `coll`, and optionally `music: true`),
4. its key and par in the leaderboard workflow, and a `leaderboard/<key>.json`.

Then show the course pickers again (remove `hidden` from `.courseRow` and the Settings row) and update the credits text at ~427.
