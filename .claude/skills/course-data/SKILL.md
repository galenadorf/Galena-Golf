---
name: course-data
description: Course data pipeline in tools/course/ (geodata, painted mask layers, build.py, install.py) and how to add another course to Galena Golf. Use when repainting a mask, regenerating RD_WOODBINE, or adding a course.
---

# Course data pipeline (`tools/course/`)

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
| site props | `site_edit.py` | `site_mask.png` + `signs.txt` | `site_paint.py` → `site_props.json` | cyan washroom, blue door strip, orange porta-potty, yellow sign, violet `#8000FF` parking lot (the OSM outline is drawn as a guide; `lot_rows` lays out the stalls along the nearest building and parks `CARS` = 8 cars, seeded, in `CAR_LOOKS` models and colours) |
| tee boxes + entrance sign + shed | `paint_edit.py` (whole course and US 20, 4 px per metre) | `paint_mask.png` | `paint_read.py` → `tees_painted.json` (every box must be painted; `--keep` keeps unpainted ones), `tee_starts.json`, `paint_props.json` (site_paint.py adds it to `site_props.json`) | magenta tee boxes, yellow played-tee dots, purple rectangle (entrance sign + flower bed), optional blue strip on its lettering side (default: facing the course), orange rectangle = a shed (pump house) |
| practice green | `practice_edit.py` (8 px per metre, around it) | `practice_mask.png` | `practice_read.py` → `practice.json` (green, bunkers, fescue, cups, trees; `build.py` adds them: the green joins `feat.green`, the painted fescue is merged into the course's by `merge_fescue`, the scene is `RD.prac` and its 1 m lattice `GREEN_ALTI.prac`) | green `#00FF00`, fringe cyan (guide only, the game cuts a 1.5 m collar), fescue magenta (edges that run off the map continue into the course's fescue), orange bunkers, red dots = the four cups, yellow dot = one broadleaf tree as wide as the dot |
| cart paths | `cartpaths_edit.py` (finds them on the aerial: pale grey, thin; yellow guide on a 3 px per metre map) | `cartpaths_mask.png` (optional) | `cartpaths_read.py` → `cartpaths.json` (the network traced into lines, each smoothed along its length with junctions held, then drawn 2.4 m wide; `build.py` encodes them as `feat.path`, the game's asphalt `S.PATH`) | red `#FF0000` = a missing path (any brush width), blue `#0000FF` = remove what was found there |
| tee boxes, whole course (shelved) | `tee_boxes_edit.py` | `tee_boxes_mask.png` | `tee_boxes_paint.py` → `tees_painted.json`, `tee_starts.json` | magenta boxes, yellow start dots |

   `bunkers_auto.py` found six bunkers OSM lacks (`bunkers_auto.json`); `bunkers_painted.json` replaces OSM and auto bunkers when present. Signs: `signs.txt` lines like `7: LINE ONE | LINE TWO`; a yellow dot whose nearest hole has no line is not built.
3. `build.py` encodes everything into `out/rd_woodbine.js`; it prefers painted files over generated ones, clips fescue to the boundary, links each hole's fairway to its green by convex hull (`link_fairways`, so no gap of rough), and snaps the four tee sets (gold, black, silver, bronze) to the tee boxes at their card yardages.
4. `install.py` writes the data into `index.html`. Then `node --check` and a headless run.

The outlines are smoothed so painted pixel staircases do not show: `bunkers_paint.py`, `fairways.py` and `fescue.py` trace the sub-pixel contour of the blurred mask (`smooth_polys` in `common.py`; blur `SMOOTH` px, `TOL` m simplification, area kept within about 1%), and `paint_read.py` does the same for the painted tee boxes, and `build.py` rounds the OSM green outlines (`round_green`, Chaikin corner cutting), the OSM pond outlines (`round_pond`: the same, scaled back to the original area) and the creek's centre line (`round_line`, ends fixed) before it is cut into ribbons; `creek_paint.py` traces a painted creek mask with `smooth_polys` too. The raw pre-smoothing JSON is kept beside each (`*_raw_backup.json`).

To change a layer: repaint the mask, run its reader, then `build.py` and `install.py`.

The highway (US 20, `highway` and `hwSlow` in the data) is not painted: `build.py highway()` reads it from `.cache/osm.json` (clipped to the 2 m class grid, west to east; `hwSlow` is the distance along it where the limit drops to 35 mph). It reads the raw file because `osm.load` loses ways that Overpass lists twice (the second copy has no tags), which includes both US 20 ways.

# Adding another course

A course is an `RD_<NAME>` object (hole lines, par, hcp, tee sets, feature polygons, trees, coarse DEM plus relief; encoding in `tools/course/build.py`). Adapt `common.py` (origin, areas) and `card.py`, then add: an `RDS` entry (data, alti, z0, grid, tweaks, optional `lush`/`dry`/`fescue`), a `<NAME>_DEFS` hole list, a `COURSES` entry (`key`, `name`, `short`, `defs`, `best`, `board`, `coll`, optional `music`), its key and par in the leaderboard workflow plus `leaderboard/<key>.json`. Show the hidden course pickers again (`#segCourse` on the title screen, `#segCourseM` in Settings: remove `hidden`) and update the credits text.
