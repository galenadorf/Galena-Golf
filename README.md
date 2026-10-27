# Galena!!! Golf



Fork and customization of @nephlonor's excellent SweetSpot (https://github.com/nephlonor/SweetSpot) - Thank you so much for sharing!



This pals golf game was inspired by and is dedicated Andy in honor of his first ever hole-in-one on #7, which happened around 10:30 AM on Sept. 10th, 2026. Congrats, Andy!



## Milestones

**v1.0: a major milestone.** Build `ce4c23d`, 2026-10-27 16:30 CDT (21:30 UTC). PALS Rules (mulligan, gimme, maximum hole score) on by default. This is the first version of Galena!!! Golf to be considered complete: all 18 holes of Woodbine Bend, the practice green and driving range, live multiplayer, and the Player ID leaderboard and records.

Added to v1.0 the same evening (through build `6613975`):

- **Fresh start.** The world leaderboard, records and every player's stored rounds and stats were cleared (build `1c422ca`); v1.0 scores start from zero.
- **Leaderboard.** Shows the top 40 plus ties, equal scores share a rank (T4, T4, then 6), and after a round posts the game says where it stands ("You're #4 on the leaderboard").
- **Always current.** Every new round first checks for a newer build and reloads into it.
- **Battery.** 30 fps when nothing is moving (including the hole-done card and final scorecard), at most 60 fps when active, a lighter tilt-shift blur and 2x anti-aliasing.
- **Gimme.** Measured from the edge of the drawn hole: inside 24 in of the edge, and always anything the readout shows as 2 ft or less.
- **Truer putting.** The ball and cup are drawn and played at half their old size (an 11 in hole, about 2.6x real), chosen from a make-rate study calibrated to PGA Tour putting: from 8 ft, 78% of putts drop instead of 92%; from 30 ft, 19% instead of 36%.
