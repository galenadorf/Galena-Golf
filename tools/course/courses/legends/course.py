"""Legends Course, Memphis National Golf Club, 10135 National Club Drive, Collierville TN (Shelby County): everything the pipeline needs to know about this one course.

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its painted masks and generated
files (out/). common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
The club's two courses share this frame (origin, areas), so their downloads in .cache/ are interchangeable (see courses/champions/course.py).
"""
NAME = 'Legends at Memphis National Golf Club'
ORIGIN = (35.0745, -89.7205)  # lat, lon: the middle of the club, the same for both of its courses
OSM_WAY = None   # OSM's "Memphis National Golf Course" outline (way 384260125) covers only the southern holes: the course is made from the holes
HOLE_BOX = (-900, -560, 480, 1460)   # the Legends' 18 holes are OSM's (the Champions are not mapped); Ridgeway Country Club's holes lie west of this
OUTLINE_BUFFER = 70    # osm.py: the outline (the out-of-bounds line) is the holes' lines buffered by this
KEEP_NEAR_HOLES = 110  # osm.py: OSM's golf features count only within this of the Legends' holes (the Champions' bunkers and paths are its own)

# areas, in local metres [e0, n0, e1, n1]. The Legends run about -800..400 east, -520..1400 north (a long loop north of the clubhouse); the Champions
# lie east of it (100..800 east, -520..800 north); both fit this detail area.
DETAIL = (-1050, -700, 950, 1500)        # the club and its edges: 1 m terrain, aerial, lidar
WIDE = (-3000, -2800, 3000, 3000)        # the horizon: coarse terrain only
DEM_AREA = (-1250, -900, 1150, 1700)     # the coarse terrain grid in the game's data
ROAD_AREA = (-1050, -700, 950, 1500)     # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

# elevation sources (USGS): the 1 m DEM project name in TNM download URLs, and the lidar point cloud on s3://usgs-lidar-public
DEM_PROJECT = 'TN_ShelbyCo_2017'
LIDAR_EPT = 'TN_ShelbyCo_2012'          # the Shelby County survey on the public AWS copy (the 2019 West Tennessee ones do not cover the club)

# roads drawn beside the course. Houston Levee Road (north-south, west of the club) has no west-to-east stretch, so no highway with traffic.
HIGHWAY = None
SIDE_ROADS = [('Houston Levee Road',)]
ROUND_ROADS = True   # build.py rounds the side roads' corners
ALL_ROADS = True     # build.py draws every OSM road near a hole, not just the SIDE_ROADS names (the game draws only what is in view)
OSM_CARTPATHS = True  # no painted cart paths: build.py takes OSM's golf=cartpath lines, joined across the roads

# the scorecard (golfpass.com Legends card, the club's black/white/gold/green sets), yards. Men's stroke index. Ed Seay and Arnold Palmer, opened 1971
# (renovated by Roy Case 1999 and 2016). Ratings (golfpass tee table, golfify for white): black 72.1/131, white 70.5/126, gold 67.6/121, green (women) 69.1/122.
PAR = [5, 4, 4, 4, 3, 4, 3, 5, 4, 4, 3, 5, 4, 4, 3, 5, 4, 4]
HCP = [8, 2, 16, 4, 10, 12, 18, 14, 6, 9, 1, 5, 3, 15, 11, 13, 7, 17]
TEES = {  # name: (rating, slope, yards per hole)
    'black': (72.1, 131, [543, 398, 329, 402, 195, 346, 148, 523, 365, 344, 242, 580, 436, 340, 195, 570, 380, 375]),
    'white': (70.5, 126, [502, 344, 315, 383, 178, 328, 140, 507, 339, 326, 215, 534, 414, 329, 180, 540, 360, 340]),
    'gold': (67.6, 121, [462, 317, 284, 354, 155, 312, 130, 448, 300, 302, 183, 470, 384, 311, 135, 520, 300, 310]),
    'green': (69.1, 122, [442, 296, 264, 289, 115, 259, 109, 413, 270, 281, 148, 447, 351, 250, 115, 460, 260, 280]),
}
ALT = {}  # no alternate tee lengths
TREES_GONE = True   # trees_aerial.py: the lidar is from 2012, the aerial 2023; a lidar tree with no canopy on the aerial was felled since
RELIEF_OFF_WATER = True   # build.py leaves the lidar relief off the ponds, creeks and their banks
FAIRWAYS_FROM_AERIAL = True   # OSM maps only a few core stripes of fairway: trace.py's aerial fairways fill every par 4 and 5
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
# the game's four tee-marker slots: w is the set played, y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('white', 0xeeeeee), 'y': ('black', 0x26282b), 'b': ('gold', 0xd9b23a), 'r': ('green', 0x2f8f4f)}

SMOOTH_MORE = True
