"""Briar Leaf Golf Club (closed in 2026; its hole lines are a best guess, see the end of this file), 3233 E State Road 39, La Porte IN (LaPorte County): everything the pipeline needs to know about this one course (an alpha build from OpenStreetMap).

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its generated files (out/).
common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Briar Leaf Golf Club'
ORIGIN = (41.65292, -86.73122)  # lat, lon: the middle of the course
OSM_WAY = 2726759

DETAIL = (-750, -500, 750, 500)          # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2400, -2400, 2400, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-950, -700, 950, 700)      # the coarse terrain grid in the game's data
ROAD_AREA = (-750, -500, 750, 500)       # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

DEM_PROJECT = 'IN_Indiana_Statewide_LiDAR_2017_B17'
LIDAR_EPT = 'IN_Statewide_Opt2_B1_2017'

HIGHWAY = None
SIDE_ROADS = []
ROUND_ROADS = True
ALL_ROADS = True
OSM_CARTPATHS = True

# the scorecard (golfpass.com, 2026), yards. Men's stroke index. The card's tees are Black ("Medal": 73.0/133), Silver, Gold and Green. The crew's 2022 card says 70.4/128 (Silver); the
# listings give no rating for Gold or Green, so none is claimed here. OSM maps no hole lines or tee boxes at Briar Leaf: its holes are rebuilt by briar_holes.py (extra.json).
PAR = [4, 4, 3, 5, 4, 5, 4, 3, 4, 4, 3, 4, 3, 5, 5, 4, 4, 4]
HCP = [13, 9, 11, 3, 5, 7, 15, 17, 1, 4, 14, 10, 18, 12, 6, 2, 16, 8]
TEES = {  # name: (rating, slope, yards per hole)
    'black': (73.0, 133, [378, 383, 138, 547, 352, 546, 336, 182, 431, 362, 162, 418, 214, 523, 462, 402, 366, 377]),
    'silver': (70.4, 128, [350, 372, 124, 529, 333, 519, 323, 166, 419, 353, 135, 399, 150, 495, 447, 390, 353, 360]),
    'gold': (None, None, [337, 358, 115, 472, 321, 496, 295, 157, 406, 346, 124, 373, 137, 480, 380, 380, 345, 339]),
    'green': (None, None, [306, 313, 75, 388, 281, 324, 240, 115, 345, 339, 106, 276, 110, 372, 307, 321, 292, 294]),
}
ALT = {}
RELIEF_OFF_WATER = True
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
TREES_OFF_TEES_GREENS = True
SMOOTH_MORE = True
FINAL_ROUND = dict(fair=(3, 3), water=(2.5, 0), fescue=(3, 1.5), bound=(3, 3))
SMOOTH_PAINTED = True
MARKERS = {'w': ('silver', 0xeeeeee), 'y': ('black', 0x26282b), 'b': ('gold', 0xd9b23a), 'r': ('green', 0x2f8f4f)}

# HOLE LINES ARE A BEST GUESS (OSM has none): briar_holes.py writes extra.json from order.json (see its docstring); osm.py takes the holes and tee boxes from it.
EXTRA_FILE = 'extra.json'
OSM_HOLES = False
KEEP_NEAR_HOLES = 60
OUTLINE_BUFFER = 90
# (no aerial fairway tracing: it found almost nothing along the guessed lines; briar_holes.py adds a mown corridor to each hole OSM has no fairway for)
