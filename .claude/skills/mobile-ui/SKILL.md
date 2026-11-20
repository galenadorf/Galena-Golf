---
name: mobile-ui
description: Mobile app interface design rules for Galena!!! Pocket Edition (the game's HUD, sheets, cards, layers, buttons, safe areas, touch, portrait and landscape, battery). Use when adding or changing any screen, sheet, card, button, HUD element or other UI in index.html.
---

# Mobile interface design (Galena!!! Pocket Edition)

The game is a phone-first installable PWA played one-handed in portrait, often outdoors, but also in landscape and on a desktop browser. `index.html` holds the UI; this is how it is built and how new UI should be. Look at the nearest existing element before inventing anything: copy its classes and tokens.

## Principles
1. **The scene is the product.** A golf hole is drawn full screen (`#gl`); UI floats over it as small glass pieces and stays out of the ball, the target and the player's thumb. Never cover the centre of the screen during aim or flight. Sheets pause the scene (`sceneStill`).
2. **Thumb first.** Primary actions live in the bottom half and are reachable one-handed; the top edge holds read-only status and the menu. Touch targets are at least 44 x 44 px (buttons here: 50 px `.mbtn`, 44 px round buttons, 38 px close/back); keep 8 px or more between targets.
3. **One idea per screen.** A sheet has one job, a short title (`.sht`), at most one scrolling list, and one way out (the `.shX` close, `.shBack` for a second level). No nested modals.
4. **Say little, show numbers.** Labels are uppercase condensed (Oswald) and short; values are big. Prefer a number, an icon or a bar to a sentence. Distances show in yards (feet on and around the green), speed in mph; the engine's metres never reach the screen.
5. **Quiet failure.** Network features (boards, records, roster, multiplayer) must fail without a message or a broken screen, and solo play never depends on them (see the offline rule in CLAUDE.md).
6. **Battery.** Nothing animates when nothing changes: no `setInterval` loops for UI, no backdrop blur over the moving scene, no per-frame DOM work; a still scene drops the frame rate (`frameGap`, `sceneStill`). New per-frame work must fit those limits.

## Layout
- **Safe areas.** Every fixed element offsets by the tokens `--st --sb --sl --sr` (`env(safe-area-inset-*)`): `top:calc(var(--st) + 8px)`, side padding `calc(var(--sl) + 16px)`. The viewport meta has `viewport-fit=cover`. Gutter 8 px for floating pieces, 16 px for sheet content.
- **Layers.** Full screens are `.layer` (fixed, `z-index:6`, fade with `.on`, `opacity` + `pointer-events`); the HUD is `z-index:2`, sheets `z-index:8`. Reuse these instead of new z-index values.
- **Sheets.** Bottom sheets: `.sheet` (28 px top radius, `.grab` handle, spring-slide in, `max-height:88vh`, content scrolls inside). Use `.sht` for the title and `.sht small` for its count or hint. Add the close and back buttons the same way the others do.
- **Orientation.** Design portrait first, then check `@media (orientation:landscape)` (side-by-side layouts: see `#play`, `#glb`, `#pgBar`) and short screens (`max-height:780px` and `670px`: an iPhone in Safari has only about 680 px). Nothing may need a horizontal scroll; lists scroll vertically in their own container.
- **Scroll and touch.** The page itself never scrolls (`overflow:hidden`, `overscroll-behavior:none`, `touch-action:none`). A scrolling element must be allowed explicitly: it goes in the `touchmove` guard's `closest('.sheet, input, #glbList, #playBlurb')` list, or the scroll is blocked. Buttons use `touch-action:manipulation` (no 300 ms delay, no double-tap zoom); inputs set `user-select:text`.

## Look
- **Tokens (`:root`).** Ink `--ink/--ink2/--ink3/--hair/--soft`; greens `--g1 #2f6b35 --g2 --g3`; accents `--yel --red`; status `--good --ok --bad` (on glass: `--gGood --gOk --gBad`); white scale `--w1..w3`; glass `--gl-bg --gl-tint --gl-line --gl-sh`; text shadow `--tsh`. Use tokens, not new hex values; a new colour needs a reason.
- **Glass over the scene.** `.card`/`.glass`: translucent white gradient on a dark green tint, 1 px light border, 22 px radius, white text with `--tsh`. No backdrop blur over the moving scene (a stronger tint instead); sheets, which sit over a paused scene, keep their blur. Sheets are light (frosted white, dark ink); the settings sheet is dark glass.
- **Type.** Headings and buttons: `var(--cond)` (Oswald 600, uppercase, letter-spacing .04-.1em); body and numbers: `var(--body)` (Barlow 500-700). Sizes: sheet title 24, button 16, label 12-13 with wide tracking, body 14-16. Inputs are at least 16 px so iOS does not zoom. Fonts are self-hosted in `fonts/` (never a CDN).
- **Shape.** Radii 12 (small buttons), 16 (buttons, rows), 20-22 (cards), 28 (sheets), 50 % (round icon buttons). Buttons: `.mbtn` (50 px, soft fill), `.mpb` (38 px green, 13-15 px text), danger red (`.mbtn.danger`, `.mpLr.on`), dark (`.mbtn.dark`). Icons are inline SVG with `stroke="currentColor"`, 2-2.8 px round strokes, 18-22 px; emoji are used sparingly for stats and records.
- **Colour meaning.** Green is good and primary; amber is caution; red is destructive or penalty. Never rely on colour alone: pair it with a word or icon (the game is played in sun and by colour-blind players too). Contrast: white text on glass needs the text shadow, ink on frosted white is at least `--ink2`.
- **Motion.** Springy for things that arrive (`--spring`, .42 s sheet slide), eased for fades (`--ease`, .25-.35 s). Animate `transform` and `opacity` only. Respect reduced motion where an effect is decorative.
- **Feedback.** Every tap answers within a frame: `:active` state on buttons, a `SFX` blip on taps that change screen (`SFX.blip()`), a short readout pill (`readout`, `readoutNote`) for results, never a blocking dialog for information. Destructive actions (abandon round, new round over a saved one) ask once, with the safe choice first.

## Building a screen: checklist
1. Find the closest existing screen and copy its markup and classes; add CSS next to its rules, using tokens.
2. Safe-area offsets on every fixed edge; a 44 px minimum target; text no smaller than 12 px.
3. Portrait, landscape and a 670 px-high portrait all look right; no horizontal scroll.
4. Opens and closes through the existing helpers (`closeSheets`, `titleOff`, a `.layer.on` toggle), and the back button or swipe leaves no state behind.
5. Works with the network off and with no data yet (empty state in one line: "No rounds posted yet.").
6. Any new thing a player can see or hear is added to `on_course_objects_and_sounds.txt` if it is on the course, and new files go into `sw.js` `CORE` and `pages.yml`.
7. After editing: `node --check` on the extracted script, then a headless run (see CLAUDE.md, Browser testing) with a screenshot at 390 x 844 portrait and 844 x 390 landscape; look at it.
