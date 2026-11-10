"""Galena Golf Club, 11557 US 20, Galena IL (Jo Daviess County): everything the pipeline needs to know about this one course.

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its painted masks and generated
files (out/). common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Galena Golf Club'
ORIGIN = (42.44827, -90.44628)  # lat, lon: the middle of the course
OSM_WAY = 477049513             # the leisure=golf_course way: its outline is the course (17 hole lines, 19 greens, 21 tees, 19 fairways, 38 bunkers; hole 8's line is missing)

# areas, in local metres [e0, n0, e1, n1]. The outline runs about -750..750 east, -490..490 north.
DETAIL = (-900, -700, 900, 700)          # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2400, -2400, 2400, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-1100, -900, 1100, 900)      # the coarse terrain grid in the game's data
ROAD_AREA = (-900, -700, 900, 700)       # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

# elevation sources (USGS): the 1 m DEM project name in TNM download URLs, and the lidar point cloud on s3://usgs-lidar-public
DEM_PROJECT = 'IL_8County_PlusChampaign_2019_B19'
LIDAR_EPT = 'IL_8County_PlusChampaign_B2_2019'

# US 20 (U.S. Grant Memorial Highway, also IL 84) runs along the course, 50 mph, with traffic. The side streets are every OSM road near a hole (ALL_ROADS).
HIGHWAY = dict(ref='US 20;IL 84', ways=2)
SIDE_ROADS = []
ROUND_ROADS = True   # build.py rounds the side roads' corners
ALL_ROADS = True     # build.py draws every OSM road near a hole (the game draws only what is in view)
OSM_CARTPATHS = True # no painted cart paths: build.py takes OSM's golf=cartpath lines, joined across the roads

# the scorecard (golfpass.com / stymie.golf, 2026), yards. Men's stroke index (OSM's handicap tags agree). Par 72: OSM tags hole 18 as a par 4, the card has a par 5 (492 yd).
# Ratings: blue 72.4/125, white 71.4/122, gold 68.7/119 (men), red 65.4/112 (women 70.8/121).
PAR = [4, 4, 3, 5, 4, 4, 4, 3, 4, 5, 3, 4, 4, 3, 5, 4, 4, 5]
HCP = [9, 1, 15, 17, 3, 5, 13, 7, 11, 8, 16, 6, 2, 14, 18, 10, 4, 12]
TEES = {  # name: (rating, slope, yards per hole)
    'blue': (72.4, 125, [326, 422, 165, 494, 363, 404, 326, 193, 342, 543, 215, 435, 431, 169, 495, 360, 440, 492]),
    'white': (71.4, 122, [316, 418, 152, 475, 363, 390, 315, 176, 334, 524, 171, 420, 418, 157, 477, 351, 431, 480]),
    'gold': (68.7, 119, [307, 364, 142, 441, 353, 315, 256, 159, 325, 456, 154, 374, 408, 136, 450, 342, 340, 462]),
    'red': (65.4, 112, [301, 348, 129, 335, 211, 308, 246, 151, 318, 447, 110, 371, 355, 127, 344, 280, 332, 362]),
}
ALT = {}  # no alternate tee lengths
RELIEF_OFF_WATER = True
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
TREES_OFF_TEES_GREENS = True
SMOOTH_MORE = True

# the game's four tee-marker slots: w is the set played (white, 6,368 yd), y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('white', 0xeeeeee), 'y': ('blue', 0x2f6fd0), 'b': ('gold', 0xd9b23a), 'r': ('red', 0xc0392b)}

# tee boxes OSM does not map (read off the aerial): hole -> (east, north) of the box's middle
EXTRA_TEES = {3: (121, -313), 4: (125, -478), 9: (-274, -291)}

# tee sets put in the box named by a point in it (build.py TEE_BOXES): the card yardage is longer than OSM's straight hole line on 2 and 7, which put them in the next box back
TEE_BOXES = {
    2: {'blue': (-211, -255), 'white': (-208, -255), 'gold': (-205, -255), 'red': (-202, -255)},
    7: {'blue': (-178, -385), 'white': (-175, -385), 'gold': (-172, -385), 'red': (-169, -385)},
}
