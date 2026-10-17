# Galena!!! Golf

A mobile, browser-based 3D golf game (installable PWA), forked from **SweetSpot** (https://github.com/nephlonor/SweetSpot) and being customised into **Galena!!! Golf**.

**Offline rule:** all solo play must work fully offline, with no CDN or other third-party dependency. Every file the game needs lives in this repo, and `sw.js` caches it. Only **live multiplayer** (public MQTT brokers) and the **world leaderboard** (GitHub API and `raw.githubusercontent.com`) need a connection; they must fail quietly when offline. Don't add new external scripts, fonts or assets: download them into `vendor/` or `fonts/` (with their licence) and add them to `CORE` in `sw.js`.

**Goal:** a rebrand plus gameplay changes, ending with **exactly one course, which hasn't been created yet**. Golf & Country Club Basel (`gccb`) is a temporary placeholder until it's replaced.

## Project layout

- `index.html` — **the entire game**: HTML, CSS and JS in one file (~7,340 lines, ~0.9 MB). There's no build step.
- `vendor/` — three.js r128 (`three.r128.min.js`, the global build) and mqtt.js 5.10.1 (loaded only when multiplayer starts), byte-identical to the npm builds, with their MIT licences.
- `fonts/` — Oswald (variable) and Barlow 500/600/700 as `.woff2`, all subsets Google Fonts serves, plus `fonts.css` and the OFL licences.
- `sw.js` — service worker for offline play: precaches `CORE` (page, icons, vendor, fonts), network-first for the page (falls back to the cache after 4 s), cache-first for everything else; it doesn't touch other origins or `version.txt`. Its cache is `galena-<BUILD>`, so each deploy replaces it. Registered at the end of `index.html`; needs https or localhost.
- `manifest.webmanifest`, `icon*.png`, `icon.svg`, `apple-touch-icon.png` — PWA metadata and icons (the icons are still SweetSpot's artwork).
- `leaderboard/gccb.json` — the world leaderboard (reset to `[]`).
- `.github/workflows/pages.yml` — deploys to GitHub Pages: copies the files (including `sw.js`, `vendor/` and `fonts/`), replaces `__BUILD__` with the commit SHA in `index.html` and `sw.js` and writes `version.txt` (the game reloads itself when that file changes).
- `.github/workflows/leaderboard.yml` — players post scores as GitHub issues titled `[score] ...` with a JSON body. The workflow validates them, appends them to `leaderboard/<course>.json` and closes the issue. Its `COURSES` map holds course key → par.
- `_original/` — an untouched copy of the files as forked (index.html, manifest, leaderboard, .github). It's for reference only and isn't deployed.
- Git repo: https://github.com/galenadorf/Galena-Golf (branch `main`). `_original/` is git-ignored.

### Working with index.html

Several lines are huge embedded data. Don't print them whole; cut them with `cut -c1-200`.
- line ~1802 `RD_GCCB` (120 KB of course data)
- line ~1998 `GREEN_ALTI_GCCB` (green elevation grids)
- line ~4908 `SND_B64` (sound effects as base64 MP3)
- line ~6316 `CLUB_SPR` (club-head sprites as base64 WebP)

Do edits with small Python scripts that assert each `old` string matches exactly once. Check the JS afterwards by extracting the last inline `<script>` and running `node --check`.

**Browser testing on this machine (WSL):** there's no system browser, and Playwright's Chromium is missing `libnss3`, `libnspr4` and `libasound2t64` (installing them needs sudo). Workaround without sudo: `npm i playwright@1.48.2 && npx playwright install chromium` in a scratch folder, then `apt-get download libnss3 libnspr4 libasound2t64`, extract each with `dpkg-deb -x <deb> <dir>`, and run node with `LD_LIBRARY_PATH=<dir>/usr/lib/x86_64-linux-gnu`. Serve the folder with `python3 -m http.server` on localhost; launch Chromium with `--use-gl=swiftshader --enable-unsafe-swiftshader`. A player name must be filled in (`#nameIn`) before `#btnPlay` starts a round.

### Code map (line numbers approximate; each section starts with a `/* ===== NAME ===== */` banner)

| Lines | Section |
|---|---|
| 14–353 | CSS. Theme variables on `:root` (line 17): greens `--g1..g3`, `--yel`, fonts Oswald and Barlow |
| 354–433 | HTML: HUD, title screen (h1 at 384), menus and sheets; help/credits text at ~430 |
| 437 | UTIL (noise, maths) |
| 479 | PHYSICS: ball flight fitted to TrackMan data; `SURF` surfaces (491), `WEATHERS` (508), **`CLUBS` table (535)** |
| 1010 | COURSE: the procedural "Legacy" course (switched off via `LEGACY_ON = false`, line ~3021) and the terrain builder |
| 1805 | REAL COURSE: builds holes from real-course data (`makeRealCourse`) |
| ~3007 | `RDS` (data set per course), `COURSES` (~3017), `setCourse()` (~3026) |
| 3042 | WORLD (three.js): terrain shaders, tilt-shift, rain, particles |
| 4034 | PROPS & DETAIL: walls, buildings, shrubs, wildlife, plane, paraglider |
| 4894 | GAME: settings, `LB_EPOCH` (4899), audio, live multiplayer over MQTT (~4963), synthesised music (~5282) |
| ~5430 | state `G`, swing `SW`, saving the round in progress (`ssg-round-<course>`), swing input, flight playback, camera |
| 6142 | UI: tempo panel, strike dial, HUD, sheets, hole map |
| 6805 | STATS + RECORDS |
| 6902 | PLAYER + LEADERBOARD (local board and GitHub board) |
| 7074 | INPUT + LOOP |

## Done so far (session of 2026-10-16)

1. **Removed the Augusta National and Alsace courses**, the two largest: their data blobs (`RD_AUGUSTA`, `RD_ALSACE`), hole definitions, `RDS`/`COURSES` entries, picker buttons, credits text, leaderboard files, and their entries in the workflow's `COURSES`. The file went from 2.4 MB to 0.9 MB.
2. **Course pickers hidden**: both rows (`#segCourse` on the title screen, `#segCourseM` in Settings) have the `hidden` attribute while there's only one course. Each still holds its `gccb` button.
3. **Music is now a per-course flag**: `musicWanted()` checks `COURSE.music`. No course has it set, so the Music menu row (`#musRow`) stays hidden; `setCourse()` toggles it. Augusta's synthesised guitar-and-piano engine is still in the code.
4. **Engine features kept but switched off** (they were driven by the removed courses and could be reused): swirling wind (`def.swirl`, `swirlWind`, `buildSwirlFx`), the `RDC.lush` / `RDC.dry` palettes, pine straw, stone bridges and loblolly pines. Comments still mention Augusta and Alsace to explain where these came from, and so do some hole descriptions in the disabled Legacy course.
5. **Renamed to "Galena!!! Golf"**: `<title>`, the apple web-app title (`Galena!!!`), the title-screen `<h1>Galena<span>!!!</span><br>Golf</h1>`, the logo's alt text, the share-link title, the score-post issue text, and the manifest's `name`/`short_name`.
6. Verified with `node --check` and a search for leftover references only. Since then: headless-Chromium tested on 2026-10-16 (title screen, fonts, three.js, starting a round, online and with the server stopped), and the live site works on the user's phone. A full round with score posting hasn't been tested yet.

## To do before publishing

- [x] **Score posting** now points at `GH_REPO = 'galenadorf/Galena-Golf'` (line ~6907). `GH_POST_KEY` is now emptied (it was the original author's token), so players get a pre-filled issue page; to post silently, add your own fine-grained token (Issues read/write on that repo only).
- [x] **Video removed**: the intro layer (`#vidIntro`) and the help-sheet video are gone from the HTML, and `pages.yml` now copies `*.png icon.svg` only. Dead CSS and the null-guarded `initIntroVideo()` remain. To bring a video back, add `swing-explainer.mp4` and `swing-poster.jpg` and restore the copy step.
- [x] **Multiplayer prefix** changed to `galena/v1/` in `mpT` and the subscribe string.
- [x] `leaderboard/gccb.json` reset to `[]` and `LB_EPOCH` bumped to `2026-10-16-galena`. Syntax-checked with `node --check` (node v22) on 2026-10-16: OK.
- [ ] New icons (`icon.svg`, PNGs, `apple-touch-icon.png`) and a theme colour if wanted (`manifest.webmanifest` and `<meta name="theme-color">`).
- [ ] Optional: the `ssg-` localStorage keys are harmless and can stay.
- [x] Git repo set up and Pages enabled; live at https://galenadorf.github.io/Galena-Golf/ (first deploy 2026-10-16).

## Adding the new course (later)

A real course is a `RD_<NAME>` data object (holes with par, hcp, len, tees, fairways, greens, bunkers, water, trees, a DEM, etc.; see the shape of `RD_GCCB`). It also needs:
1. an entry in `RDS` (data, alti, z0, grid, tweaks, optional `lush`/`dry`),
2. a `<NAME>_DEFS` hole list,
3. an entry in `COURSES` (`key`, `name`, `short`, `defs`, `best`, `board`, `coll`, and optionally `music: true`),
4. its key and par in the leaderboard workflow, and a `leaderboard/<key>.json`.

When it's working, remove `gccb` the same way Augusta and Alsace were removed, and update the credits text at ~430.
