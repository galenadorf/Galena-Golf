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
RELIEF_OFF_WATER = True   # build.py leaves the lidar relief off the ponds, creeks and their banks (shores drawn as curves, not 2 m steps)
# the layers painted on all_edit.py's map (all_read.py reads only these): fairways, greens, tee boxes, bunkers and played-tee dots.
# The rough, deep rough (no fescue: the game makes it from the distance to play), trees, water, cart paths, boundary and props are
# left as OSM and the lidar give them.
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
# the game's four tee-marker slots: w is the set played, y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('gold', 0xd9b23a), 'y': ('black', 0x26282b), 'b': ('white', 0xeeeeee), 'r': ('jade', 0x2f8f6f)}
