# Galena!!! Pocket Edition



Fork and customization of @nephlonor's excellent SweetSpot (https://github.com/nephlonor/SweetSpot) - Thank you so much for sharing!



This pals golf game was inspired by and is dedicated Andy in honor of his first ever hole-in-one on #7, which happened around 10:30 AM on Sept. 10th, 2026. Congrats, Andy!



## Milestones

**v1.4.** Build `638b566`, 2026-11-21.

- **A new look.** The game now looks like a paper scorecard. The title screen shows your name on a pen line and your last card, with birdies circled and bogeys boxed. Each course gets its own scorecard page with yards, par, handicap and your best on every hole. Settings, Practice, Leaderboard, Stats, Hole by hole and How to play are full pages with a back arrow, and the hole-done card and confirmation cards are paper too. New type throughout: bold serif titles, handwriting for your name and scores, typewriter course descriptions and engraved buttons. The fonts are stored in the game, so it still works offline.
- **More on the cards.** Your handicap index next to your name, how many rounds have been recorded on each course, and every hole in one on the Global leaderboard and in Stats. Stats, Hole by hole and How to play each have their own course picker.
- **Courses.** Smoother fairways, deep rough and bunkers on Woodbine and ER South, with ER South's deep rough repainted by hand. The first cut now curves into the green's collar. Tee boxes face their holes. Augusta gets solid stone bridges, a gallery that parts around your ball, bright white sand, Rae's Creek filled to its banks and a recorded song on hole 1.
- **Battery.** No sound engine while sound is off, a slower frame rate when the game sits idle, and the multiplayer connection runs only while it's needed.
- **Fixes.** Every score post had been failing because of a bug in the leaderboard workflow; that's fixed. Players online shows the connection state again, sand shots no longer run out past their carry, and tee boxes no longer face the wrong way.
- **Leaner code.** Repeated code is now shared helpers: saving data on the phone, signing and posting rounds, starting practice, clearing the scorecard. The whole game was checked for type errors.

**v1.3.** Build `cb99828`, 2026-11-14.

- **Every Galena!!! trip course.** All the courses the trip has played over the years are now in the game, built from public map and terrain data.
- **The Pals Masters is live.** Augusta National in Masters week, open to registered players, with the 2026 Masters hole locations (a new sheet each day, rounds 1 to 4).
- **Faster.** Holes build up to a third faster (most on the courses with houses and Augusta's dressing), the clouds and first frame of each hole cost less, and the tempo bar's distances now come from the real ground, so they match the aim ring.
- **Tidier menus.** Settings shows only what applies: no round buttons on the title screen, Restart and Abandon in red, and Players online beside Live room.
- **Under the hood.** mqtt 5.16.1 (kept in the game for offline play), newer GitHub Actions, and a leaderboard that no longer drops a round when several are posted at once.

**v1.2.** Build `39e00cf`, 2026-11-03.

- **Putting read.** Every putt now shows a grid on the green with small dots flowing downhill (steeper is faster and pinker) and a short read such as "Downhill · Breaks right". It replaces the old arrows, which are gone.
- **Flag shadows.** They no longer flicker, and shadows no longer shimmer as you aim.

**v1.0: a major milestone.** Build `ce4c23d`, 2026-10-27 16:30 CDT (21:30 UTC). PALS Rules (mulligan, gimme, maximum hole score) on by default. This is the first version of Galena!!! Pocket Edition to be considered complete: all 18 holes of Woodbine Bend, the practice green and driving range, live multiplayer, and the Player ID leaderboard and records.

Added to v1.0 the same evening (through build `6613975`):

- **Fresh start.** The world leaderboard, records and every player's stored rounds and stats were cleared (build `1c422ca`); v1.0 scores start from zero.
- **Leaderboard.** Shows the top 40 plus ties, equal scores share a rank (T4, T4, then 6), and after a round posts the game says where it stands ("You're #4 on the leaderboard").
- **Always current.** Every new round first checks for a newer build and reloads into it.
- **Battery.** 30 fps when nothing is moving (including the hole-done card and final scorecard), at most 60 fps when active, a lighter tilt-shift blur and 2x anti-aliasing.
- **Gimme.** Measured from the edge of the drawn hole: inside 24 in of the edge, and always anything the readout shows as 2 ft or less.
- **Truer putting.** The ball and cup are drawn and played at half their old size (an 11 in hole, about 2.6x real), chosen from a make-rate study calibrated to PGA Tour putting: from 8 ft, 78% of putts drop instead of 92%; from 30 ft, 19% instead of 36%.
