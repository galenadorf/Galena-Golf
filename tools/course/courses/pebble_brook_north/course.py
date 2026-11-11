"""Pebble Brook Golf Club, North Course, Noblesville IN (Hamilton County): everything the pipeline needs to know about this one course (an alpha build from OpenStreetMap).

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its generated files (out/).
common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Pebble Brook Golf Club, North Course'
ORIGIN = (40.05596, -86.08024)  # lat, lon: the middle of the course
OSM_WAY = 21436573

DETAIL = (-900, -1150, 900, 1150)          # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2400, -2400, 2400, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-1100, -1350, 1100, 1350)      # the coarse terrain grid in the game's data
ROAD_AREA = (-900, -1150, 900, 1150)       # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

DEM_PROJECT = 'IN_Central_Hamilton_2017'
LIDAR_EPT = 'USGS_LPC_IN_Central_Hamilton_2017_LAS_2019'

HIGHWAY = None
SIDE_ROADS = []
ROUND_ROADS = True
ALL_ROADS = True
OSM_CARTPATHS = True

# the scorecard (golfpass.com, 2026), yards. Men's stroke index. The card's hole pars add to 70 (the listing says 72); OSM's own hole 18 is a par 4, the card's a par 5.
# Ratings: blue 70.7/124, white 69.7/122, gold 67.9/118, red 71.5/124 (women's). The North course is OSM's holes 908562347-908562364 (the South course shares the land).
PAR = [4, 3, 4, 4, 5, 3, 4, 5, 4, 3, 4, 4, 4, 3, 4, 3, 4, 5]
HCP = [7, 13, 5, 9, 15, 17, 11, 3, 1, 16, 4, 10, 2, 12, 14, 18, 6, 8]
TEES = {  # name: (rating, slope, yards per hole)
    'blue': (70.7, 124, [420, 204, 420, 392, 510, 170, 375, 552, 454, 168, 398, 382, 432, 167, 365, 141, 396, 502]),
    'white': (69.7, 122, [380, 157, 405, 352, 485, 156, 356, 527, 417, 145, 378, 360, 392, 151, 343, 128, 370, 473]),
    'gold': (67.9, 118, [304, 145, 342, 297, 436, 147, 315, 475, 371, 135, 328, 311, 335, 142, 298, 117, 329, 407]),
    'red': (71.5, 124, [286, 135, 295, 258, 394, 136, 267, 432, 338, 123, 295, 281, 303, 131, 269, 108, 265, 349]),
}
HOLE_BOX = (-900, -1150, 900, 1150)   # osm.py: the course is the holes named in HOLE_WAYS
HOLE_WAYS = list(range(908562347, 908562365))
KEEP_NEAR_HOLES = 45
OUTLINE_BUFFER = 70
ALT = {}
RELIEF_OFF_WATER = True
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
TREES_OFF_TEES_GREENS = True
SMOOTH_MORE = True
FINAL_ROUND = dict(fair=(3, 3), water=(2.5, 0), fescue=(3, 1.5), bound=(3, 3))
SMOOTH_PAINTED = True
MARKERS = {'w': ('white', 0xeeeeee), 'y': ('blue', 0x2f6fd0), 'b': ('gold', 0xd9b23a), 'r': ('red', 0xc0392b)}
FAIRWAYS_FROM_AERIAL = True   # OSM maps only 2 of the North course's fairways: trace.py + fairways_fill.py add the aerial-traced ones (as at Bear Slide)
