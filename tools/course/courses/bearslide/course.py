"""Bear Slide Golf Club, 6770 E 231st St, Cicero IN (Hamilton County): everything the pipeline needs to know about this one course.

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its painted masks and generated
files (out/). common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Bear Slide Golf Club'
ORIGIN = (40.1199, -86.0497)  # lat, lon: the middle of the course
OSM_WAY = 1081529942          # the leisure=golf_course way: its outline is the course

# areas, in local metres [e0, n0, e1, n1].
# The outline is about 1.96 km east-west by 0.78 km north-south: 231st Street runs along the north edge, East 226th Street the south, Tollgate Road the east, East Millcreek Road the west.
DETAIL = (-1250, -650, 1250, 650)        # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2800, -2400, 2800, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-1500, -1100, 1500, 1100)    # the coarse terrain grid in the game's data
ROAD_AREA = (-1250, -650, 1250, 650)     # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

# elevation sources (USGS): the 1 m DEM project name in TNM download URLs, and the lidar point cloud on s3://usgs-lidar-public
DEM_PROJECT = 'IN_Central_Hamilton_2017'
LIDAR_EPT = 'USGS_LPC_IN_Central_Hamilton_2017_LAS_2019'

# roads drawn beside the course (None / [] for none)
HIGHWAY = None
SIDE_ROADS = [('231st Street',), ('East 226th Street',), ('Tollgate Road',), ('East Millcreek Road',), ('Sonoma Lane',), ('Morse Landing Drive',)]
ROUND_ROADS = True   # build.py rounds the side roads' corners

# the official scorecard (bearslide.com/course/scorecard, 2023), yards. Men's stroke index (the black tees' row).
# Ratings: black 74.1/136, blue 72/131, white 69.4/122, red (women) 68.2/117, gold 65.3/111.
PAR = [4, 4, 5, 3, 4, 3, 4, 5, 4, 4, 4, 5, 4, 3, 4, 3, 4, 4]
HCP = [3, 13, 17, 7, 5, 11, 9, 15, 1, 4, 16, 10, 6, 12, 14, 18, 8, 2]
TEES = {  # name: (rating, slope, yards per hole)
    'black': (74.1, 136, [395, 426, 517, 166, 494, 186, 469, 533, 429, 446, 344, 583, 448, 212, 337, 188, 376, 449]),
    'blue': (72.0, 131, [379, 420, 504, 159, 453, 166, 409, 514, 378, 440, 331, 528, 437, 166, 325, 172, 368, 422]),
    'white': (69.4, 122, [360, 391, 442, 133, 422, 137, 375, 468, 378, 369, 306, 517, 402, 148, 252, 120, 350, 396]),
    'red': (68.2, 117, [337, 319, 396, 96, 358, 104, 319, 393, 310, 328, 269, 423, 274, 130, 189, 91, 236, 262]),
    'gold': (65.3, 111, [347, 359, 398, 96, 360, 104, 339, 400, 345, 329, 285, 451, 290, 138, 246, 97, 265, 271]),
}
ALT = {}  # no alternate tee lengths
TREES_GONE = True   # trees_aerial.py: a lidar tree with no canopy on the 2022 aerial was felled since the 2017 survey
RELIEF_OFF_WATER = True   # build.py leaves the lidar relief off the ponds, creeks and their banks
# the layers painted on all_edit.py's map, if the course is ever painted (all_read.py reads only these)
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
# the game's four tee-marker slots: w is the set played, y/b/r the others (tee set, marker colour); gold is left off
MARKERS = {'w': ('white', 0xe8e8e8), 'y': ('black', 0x26282b), 'b': ('blue', 0x2f4fa8), 'r': ('red', 0xa8323c)}
