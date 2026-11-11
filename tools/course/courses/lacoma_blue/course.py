"""Lacoma Golf Course (Blue), 8080 Timmerman Drive, East Dubuque IL (Jo Daviess County): everything the pipeline needs to know about this one course (an alpha build from OpenStreetMap).

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its generated files (out/).
common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Lacoma Golf Course (Blue)'
ORIGIN = (42.4854, -90.62454)  # lat, lon: the middle of the course
OSM_WAY = 295902636

DETAIL = (-950, -900, 950, 900)          # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2400, -2400, 2400, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-1150, -1100, 1150, 1100)      # the coarse terrain grid in the game's data
ROAD_AREA = (-950, -900, 950, 900)       # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

DEM_PROJECT = 'IL_8County_PlusChampaign_2019_B19'
LIDAR_EPT = 'IL_8County_PlusChampaign_B2_2019'

HIGHWAY = None
SIDE_ROADS = []
ROUND_ROADS = True
ALL_ROADS = True
OSM_CARTPATHS = True

# the scorecard (golfpass.com, 2026), yards. Men's stroke index. Par 71. The Blue course is the club's 18 untagged holes in OSM (the Gold, Red and Par 3 nines share the land).
# Ratings: blue 72.9/125, white 70.7/120 (the set the crew played in 2021), gold 68.3/115 (women 73.3/122), red (women) 70.0/115.
PAR = [5, 4, 4, 4, 4, 4, 3, 5, 3, 4, 4, 3, 4, 4, 5, 4, 3, 4]
HCP = [3, 13, 5, 11, 9, 7, 15, 1, 17, 6, 8, 18, 12, 14, 2, 10, 16, 4]
TEES = {  # name: (rating, slope, yards per hole)
    'blue': (72.9, 125, [518, 365, 440, 375, 418, 415, 217, 524, 190, 420, 414, 200, 373, 377, 517, 404, 209, 438]),
    'white': (70.7, 120, [495, 356, 398, 341, 399, 400, 175, 475, 170, 382, 370, 185, 342, 340, 495, 370, 185, 417]),
    'gold': (68.3, 115, [477, 332, 344, 295, 370, 350, 151, 433, 149, 365, 355, 165, 314, 280, 472, 358, 167, 386]),
    'red': (70.0, 115, [448, 286, 328, 276, 325, 311, 120, 390, 134, 319, 337, 142, 286, 265, 442, 291, 154, 312]),
}
HOLE_BOX = (-950, -900, 950, 900)   # osm.py: the course is the holes named in HOLE_WAYS
HOLE_WAYS = [492845359, 492845363, 492845367, 492845372, 492845377, 492845386, 492845393, 492845399, 492846577, 492846580, 492846585, 492846590, 496376816, 496376829, 496376830, 496376832, 496376833, 496376838]
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

# the card's yardages put these holes' tees 30-40 m from the box at the start of OSM's hole line (the other nines' tees are close by): all four sets go in that box
TEE_BOXES = {
    7: {'blue': (130.5, -145), 'white': (133.5, -145), 'gold': (136.5, -145), 'red': (139.5, -145)},
    11: {'blue': (178.5, -150), 'white': (181.5, -150), 'gold': (184.5, -150), 'red': (187.5, -150)},
    16: {'blue': (311.5, -392), 'white': (314.5, -392), 'gold': (317.5, -392), 'red': (320.5, -392)},
}
