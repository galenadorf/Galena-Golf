"""Elbel Park Golf Course, South Bend IN (St. Joseph County): everything the pipeline needs to know about this one course (an alpha build from OpenStreetMap).

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its generated files (out/).
common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Elbel Park Golf Course'
ORIGIN = (41.74798, -86.38099)  # lat, lon: the middle of the course
OSM_WAY = 16239928

DETAIL = (-950, -550, 950, 550)          # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2400, -2400, 2400, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-1150, -750, 1150, 750)      # the coarse terrain grid in the game's data
ROAD_AREA = (-950, -550, 950, 550)       # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

DEM_PROJECT = 'IN_Indiana_Statewide_LiDAR_2017_B17'
LIDAR_EPT = 'IN_Statewide_Opt1_B1_2017'

HIGHWAY = None
SIDE_ROADS = []
ROUND_ROADS = True
ALL_ROADS = True
OSM_CARTPATHS = True

# the scorecard (golfpass.com, 2026), yards. Men's stroke index. The page names the tees Cardinal, Sand Hill, Heron and Egret and its hole table Black, Blue, White and Gold:
# taken in that order. Ratings: cardinal 72.1/125, sand hill 70.5/121, heron 68.9/118, egret 66.1/111.
PAR = [4, 5, 4, 3, 4, 5, 4, 3, 4, 4, 5, 4, 3, 4, 5, 4, 3, 4]
HCP = [1, 13, 7, 17, 3, 11, 15, 9, 5, 2, 10, 18, 6, 16, 8, 12, 14, 4]
TEES = {  # name: (rating, slope, yards per hole)
    'cardinal': (72.1, 125, [446, 501, 383, 184, 404, 528, 426, 205, 378, 416, 501, 365, 231, 386, 527, 382, 192, 435]),
    'sand hill': (70.5, 121, [411, 480, 360, 166, 370, 512, 365, 177, 345, 398, 481, 350, 215, 371, 500, 360, 185, 395]),
    'heron': (68.9, 118, [390, 458, 349, 150, 356, 494, 341, 162, 330, 376, 459, 337, 193, 351, 481, 333, 173, 376]),
    'egret': (66.1, 111, [339, 386, 251, 138, 300, 409, 294, 141, 280, 304, 399, 323, 138, 310, 413, 285, 165, 284]),
}
ALT = {}
RELIEF_OFF_WATER = True
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
TREES_OFF_TEES_GREENS = True
SMOOTH_MORE = True
FINAL_ROUND = dict(fair=(3, 3), water=(2.5, 0), fescue=(3, 1.5), bound=(3, 3))
SMOOTH_PAINTED = True
MARKERS = {'w': ('sand hill', 0xeeeeee), 'y': ('cardinal', 0x26282b), 'b': ('heron', 0x2f6fd0), 'r': ('egret', 0xc0392b)}

# the card's hole 3 is longer than OSM's hole line, which put its tees in a box 100 m away: all four sets go in the box at the start of the line
TEE_BOXES = {3: {'cardinal': (356, -77.5), 'sand hill': (357.3, -75.3), 'heron': (358.7, -72.7), 'egret': (360, -70.5)}}
