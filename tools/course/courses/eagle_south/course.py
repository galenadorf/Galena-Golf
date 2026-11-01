"""Eagle Ridge South Course, Eagle Ridge Resort & Spa, 444 Eagle Ridge Drive, Galena IL: everything the pipeline needs to know about this one course.

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its painted masks and generated
files (out/). common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Eagle Ridge South Course'
ORIGIN = (42.3868, -90.3413)  # lat, lon: the middle of the course
OSM_WAY = 295902650           # the leisure=golf_course way: its outline is the course (the resort's North, East and General share the download)

# areas, in local metres [e0, n0, e1, n1]. The outline runs -804..806 east, -737..732 north.
DETAIL = (-900, -850, 900, 850)          # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2600, -2400, 2600, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-1200, -1200, 1200, 1200)    # the coarse terrain grid in the game's data
ROAD_AREA = (-1000, -1000, 1000, 1000)   # the side roads are clipped to this (the game's 2 m class grid)

# elevation sources (USGS): the 1 m DEM project name in TNM download URLs, and the lidar point cloud on s3://usgs-lidar-public
DEM_PROJECT = 'IL_8County_PlusChampaign_2019_B19'
LIDAR_EPT = 'IL_8County_PlusChampaign_B2_2019'

# roads drawn beside the course (None / [] for none). US 20 is about 2 km south, off the map, so there is no highway with traffic.
# Side roads are for looks: OSM names, one tuple per road (Eagle Ridge Drive passes the clubhouse).
HIGHWAY = None
SIDE_ROADS = [('Eagle Ridge Drive',)]
ROUND_ROADS = True   # build.py rounds the side roads' corners (Eagle Ridge Drive winds; Woodbine's are left as OSM has them)
ALL_ROADS = True      # build.py draws every OSM road near a hole, not just the SIDE_ROADS names (the game draws only what is in view)
OSM_CARTPATHS = True  # no painted cart paths: build.py takes OSM's golf=cartpath lines, joined across the roads

# the official scorecard (eagleridge.com, doc-2016-south-scorecard, printed 08/2014), yards. Men's handicap. Jade is rated for women
# (73.1/135; women's handicap 16 4 18 12 8 6 14 10 2 / 1 11 15 9 13 5 3 17 7).
PAR = [4, 5, 3, 4, 4, 5, 3, 4, 4, 4, 5, 4, 3, 4, 4, 5, 3, 4]
HCP = [14, 4, 18, 10, 8, 12, 16, 6, 2, 1, 13, 11, 15, 9, 3, 7, 17, 5]
TEES = {  # name: (rating, slope, yards per hole)
    'black': (73.7, 140, [386, 541, 147, 339, 420, 505, 174, 361, 402, 440, 512, 348, 214, 382, 469, 557, 159, 406]),
    'gold': (71.8, 136, [359, 522, 136, 325, 401, 493, 162, 348, 380, 408, 481, 327, 186, 364, 429, 535, 133, 372]),
    'white': (70.1, 132, [321, 488, 136, 325, 401, 449, 162, 307, 341, 357, 481, 327, 186, 364, 370, 463, 133, 372]),
    'jade': (73.1, 135, [321, 488, 105, 292, 356, 449, 131, 307, 341, 357, 426, 284, 143, 328, 370, 463, 107, 341]),
}
ALT = {}  # no alternate tee lengths

# gaps in OSM's cart paths that are neither a road nor the creek, closed with a straight piece: ((east, north), (east, north)) of the two path ends
PATH_JOINS = [
    ((250.5, 403.4), (240.5, 381.5)),    # hole 18, by the green: the path from the 18th green's junction on to the next path
    ((240.5, 381.5), (227.8, 370.8)),
    ((501.6, -284.6), (500.4, -296.9)),  # between holes 13 and 16, one path through three ends
    ((500.4, -296.9), (500.1, -309.5)),
    ((500.1, -309.5), (546.4, -324.5)),  # and the fork off it
]
# cart-path bridges over the creek, where OSM's cart paths break at it (the gap between the two path ends): (east, north, deck bearing in degrees
# counter-clockwise from east, length m, hole). build.py writes them as `cartBridges`; the game builds a 2.6 m wide deck with rails (buildCartBridges).
CART_BRIDGES = [
    (-685.8, 575.6, 53.5, 21, 3),     # hole 3, the creek on the way to the green
    (-553.5, 512.1, 57.4, 19, 8),     # hole 8, from the tee box towards the fairway
    (-231.8, 464.7, 82.8, 16, 8),     # hole 8, the creek again, by the green
    (-122.4, 394.9, 43.7, 16, 9),     # hole 9, just after the tee box
    (517.6, 267.5, 137.3, 14, 10),    # hole 10, the second path, three-quarters of the way down on the south side
    (701.3, 174.0, 60.9, 9, 10),      # hole 10, the creek crossing by the green
    (509.6, -171.4, 50.4, 19, 13),    # hole 13, towards the green
    (630.2, -367.8, 1.0, 9, 14),      # hole 14, just after the tee box
    (761.6, -676.6, 32.6, 18, 15),    # between the 14th green and the 15th tee boxes
    (180.4, 251.9, 62.6, 14, 18),     # hole 18, where the fairway divides at the bottom of the hill
]
RELIEF_OFF_WATER = True   # build.py leaves the lidar relief off the ponds, creeks and their banks (shores drawn as curves, not 2 m steps)
# the layers painted on all_edit.py's map (all_read.py reads only these): fairways, greens, tee boxes, bunkers and played-tee dots.
# The rough, deep rough (no fescue: the game makes it from the distance to play), trees, water, cart paths, boundary and props are
# left as OSM and the lidar give them.
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
# the game's four tee-marker slots: w is the set played, y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('gold', 0xd9b23a), 'y': ('black', 0x26282b), 'b': ('white', 0xeeeeee), 'r': ('jade', 0x2f8f6f)}
