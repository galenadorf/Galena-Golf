"""Eagle Ridge North Course, Eagle Ridge Resort & Spa, 444 Eagle Ridge Drive, Galena IL: everything the pipeline needs to know about this one course.

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its painted masks and generated
files (out/). common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Eagle Ridge North Course'
ORIGIN = (42.3980, -90.3340)  # lat, lon: the middle of the course
OSM_WAY = 295902642           # the leisure=golf_course way: its outline is the course (the resort's South, East and General share the area)

# areas, in local metres [e0, n0, e1, n1]. The outline runs about -1010..1010 east, -700..700 north (wider than it is tall).
DETAIL = (-1150, -850, 1150, 850)        # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2800, -2400, 2800, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-1350, -1200, 1350, 1200)    # the coarse terrain grid in the game's data
ROAD_AREA = (-1150, -850, 1150, 850)     # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

# elevation sources (USGS): the 1 m DEM project name in TNM download URLs, and the lidar point cloud on s3://usgs-lidar-public
DEM_PROJECT = 'IL_8County_PlusChampaign_2019_B19'
LIDAR_EPT = 'IL_8County_PlusChampaign_B2_2019'

# roads drawn beside the course (None / [] for none). US 20 is south of the resort, off the map, so there is no highway with traffic.
# Side roads are for looks: OSM names, one tuple per road (the card: roadways left of #1, #2 and #18 are out of bounds). Eagle Ridge
# Drive runs beside 1, 2, 9, 10 and 18, Walnut Hill Road beside 1, 9, 10, 12, 14 and 15, Thunder Bay Road beside 2, 3, 6 and 7.
HIGHWAY = None
SIDE_ROADS = [('Eagle Ridge Drive',), ('Walnut Hill Road',), ('Thunder Bay Road',)]
ROUND_ROADS = True   # build.py rounds the side roads' corners

# the official scorecard (eagleridge.com, pdf/doc-2016-north-scorecard), yards. Men's stroke index. Roger B. Packard, opened 1977.
# White is also rated for women (75.2/137), Jade 71.9/130 for women; Forward tees (64.8/116) not used.
# Women's stroke index 9 3 1 17 5 13 7 11 15 / 18 8 10 16 6 2 12 4 14.
PAR = [4, 5, 4, 3, 5, 4, 4, 3, 4, 4, 5, 4, 3, 4, 5, 3, 4, 4]
HCP = [15, 5, 1, 9, 11, 13, 7, 17, 3, 18, 8, 10, 16, 6, 4, 12, 2, 14]
TEES = {  # name: (rating, slope, yards per hole)
    'black': (73.6, 136, [369, 533, 446, 204, 508, 362, 402, 165, 397, 329, 533, 413, 185, 433, 566, 180, 439, 420]),
    'gold': (71.4, 131, [362, 501, 416, 182, 482, 349, 357, 147, 377, 325, 527, 390, 146, 383, 529, 159, 411, 385]),
    'white': (69.7, 127, [334, 486, 394, 151, 464, 336, 334, 135, 360, 275, 515, 376, 132, 344, 511, 140, 396, 369]),
    'jade': (67.0, 121, [313, 429, 383, 145, 457, 287, 318, 129, 247, 272, 418, 326, 114, 294, 483, 133, 372, 348]),
}
ALT = {}  # no alternate tee lengths
# the game's four tee-marker slots: w is the set played, y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('gold', 0xd9b23a), 'y': ('black', 0x26282b), 'b': ('white', 0xeeeeee), 'r': ('jade', 0x2f8f6f)}
