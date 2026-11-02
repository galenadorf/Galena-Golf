"""Eagle Ridge The General Course, Eagle Ridge Resort & Spa, 444 Eagle Ridge Drive, Galena IL: everything the pipeline needs to know about this one course.

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its painted masks and generated
files (out/). common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Eagle Ridge The General Course'
ORIGIN = (42.3764, -90.3277)  # lat, lon: the middle of the course
OSM_WAY = 295902654           # the leisure=golf_course way "The General": its outline is the course (the resort's North, South and East share the area)

# areas, in local metres [e0, n0, e1, n1]. The outline runs about -1040..1040 east, -520..520 north (wider than it is tall).
DETAIL = (-1150, -700, 1150, 700)        # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2800, -2400, 2800, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-1350, -900, 1350, 900)      # the coarse terrain grid in the game's data
ROAD_AREA = (-1150, -700, 1150, 700)     # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

# elevation sources (USGS): the 1 m DEM project name in TNM download URLs, and the lidar point cloud on s3://usgs-lidar-public
DEM_PROJECT = 'IL_8County_PlusChampaign_2019_B19'
LIDAR_EPT = 'IL_8County_PlusChampaign_B2_2019'

# no highway with traffic; the side roads are every OSM road near a hole (ALL_ROADS)
HIGHWAY = None
SIDE_ROADS = []
ROUND_ROADS = True   # build.py rounds the side roads' corners
ALL_ROADS = True      # build.py draws every OSM road near a hole (the game draws only what is in view)
OSM_CARTPATHS = True  # no painted cart paths: build.py takes OSM's golf=cartpath lines, joined across the roads

# the official scorecard (eagleridge.com, pdf/doc-2020-general-score-card), yards. Men's stroke index. Andy North and Roger B. Packard, opened 1997.
# The card names its tees 4-Star, 3-Star, 2-Star, 1-Star (and a Forward set, not used). 2-Star is also rated for women (74.3/132), 1-Star 70.4/124.
# Women's stroke index 8 18 10 2 14 16 12 6 4 / 9 1 17 11 3 5 13 15 7.
PAR = [4, 3, 5, 4, 4, 3, 4, 4, 5, 4, 5, 3, 4, 4, 5, 3, 4, 4]
HCP = [6, 18, 14, 2, 16, 10, 12, 4, 8, 9, 7, 17, 13, 1, 5, 11, 15, 3]
TEES = {  # name: (rating, slope, yards per hole)
    '4-star': (72.4, 136, [396, 163, 499, 442, 357, 189, 398, 370, 520, 407, 549, 170, 376, 418, 505, 130, 350, 410]),
    '3-star': (70.6, 132, [361, 152, 466, 423, 341, 168, 380, 360, 500, 378, 528, 143, 354, 396, 479, 120, 306, 390]),
    '2-star': (68.8, 127, [354, 141, 444, 383, 339, 150, 354, 340, 471, 346, 501, 133, 325, 340, 459, 110, 280, 376]),
    '1-star': (65.6, 119, [326, 100, 410, 346, 313, 147, 305, 270, 417, 285, 452, 106, 298, 313, 436, 86, 225, 315]),
}
ALT = {}  # no alternate tee lengths
RELIEF_OFF_WATER = True
# the layers painted on all_edit.py's map (all_read.py reads only these)
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
TREES_OFF_TEES_GREENS = True   # build.py takes any tree out of a tee box or off a green

# the game's four tee-marker slots: w is the set played (3-Star, 6,245 yd), y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('3-star', 0xd9b23a), 'y': ('4-star', 0x26282b), 'b': ('2-star', 0xeeeeee), 'r': ('1-star', 0x2f8f6f)}
