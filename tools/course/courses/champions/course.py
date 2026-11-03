"""Champions Course, Memphis National Golf Club, 10135 National Club Drive, Collierville TN (Shelby County): everything the pipeline needs to know about this one course.

Same club and same frame as courses/legends/course.py (origin, areas), so .cache/ is a copy of the Legends'. OSM maps none of the Champions: its greens, tees,
fairways and bunkers are painted on all_edit.py's map (out/all_mask.png), then its holes are worked out from them (see the course-data skill).
"""
NAME = 'Champions at Memphis National Golf Club'
ORIGIN = (35.0745, -89.7205)  # lat, lon: the middle of the club, the same for both of its courses
OSM_WAY = None
EXTRA_FILE = 'extra.json'     # osm.py: the hand-drawn outline of the Champions' land (and, later, its holes); OSM's bunkers and cart paths inside it are kept
OSM_HOLES = False             # none of OSM's holes (they are the Legends')

DETAIL = (-1050, -700, 950, 1500)
WIDE = (-3000, -2800, 3000, 3000)
DEM_AREA = (-1250, -900, 1150, 1700)
ROAD_AREA = (-1050, -700, 950, 1500)

DEM_PROJECT = 'TN_ShelbyCo_2017'
LIDAR_EPT = 'TN_ShelbyCo_2012'

HIGHWAY = None
SIDE_ROADS = [('Houston Levee Road',)]
ROUND_ROADS = True
ALL_ROADS = True
OSM_CARTPATHS = True

# the scorecard (golfpass.com Champions card), yards. Men's stroke index. Arnold Palmer and Ed Seay, opened 1971 (Roy Case 1999; renovated 2016).
# Ratings (golfpass tee table): black 6,500 yd 71.9/123, white 69.5/117, gold 67.5/113, green (women, par 73 there) 70.3/120.
PAR = [3, 5, 5, 4, 4, 4, 4, 4, 3, 4, 3, 5, 4, 4, 4, 3, 4, 5]
HCP = [6, 10, 8, 4, 18, 16, 14, 12, 2, 3, 15, 17, 13, 1, 5, 11, 7, 9]
TEES = {  # name: (rating, slope, yards per hole)
    'black': (71.9, 123, [150, 520, 480, 406, 297, 340, 310, 360, 222, 375, 153, 497, 406, 450, 424, 159, 421, 530]),
    'white': (69.5, 117, [142, 490, 410, 362, 282, 329, 292, 275, 194, 365, 135, 459, 380, 409, 411, 144, 387, 490]),
    'gold': (67.5, 113, [118, 470, 350, 348, 260, 305, 264, 262, 170, 354, 113, 430, 346, 372, 380, 127, 353, 452]),
    'green': (70.3, 120, [107, 426, 330, 305, 258, 296, 236, 251, 147, 346, 99, 410, 324, 348, 348, 113, 326, 408]),
}
ALT = {}
TREES_GONE = True
RELIEF_OFF_WATER = True
FAIRWAYS_FROM_AERIAL = True
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
MARKERS = {'w': ('white', 0xeeeeee), 'y': ('black', 0x26282b), 'b': ('gold', 0xd9b23a), 'r': ('green', 0x2f8f4f)}

SMOOTH_MORE = True
