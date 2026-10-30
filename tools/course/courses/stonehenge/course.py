"""Stonehenge Golf Club, 27250 W. Highway 22, Barrington IL (Lake County): everything the pipeline needs to know about this one course.

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its painted masks and generated
files (out/). common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Stonehenge Golf Club'
ORIGIN = (42.19456, -88.16486)  # lat, lon: the middle of the course
OSM_WAY = 238828753             # the leisure=golf_course way: its outline is the course (all 18 holes, greens, tees, bunkers mapped)

# areas, in local metres [e0, n0, e1, n1]. The outline runs about -430..430 east, -410..410 north.
DETAIL = (-700, -700, 700, 700)          # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2400, -2400, 2400, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-1200, -1200, 1200, 1200)    # the coarse terrain grid in the game's data
ROAD_AREA = (-700, -700, 700, 700)       # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

# elevation sources (USGS): the 1 m DEM project name in TNM download URLs, and the lidar point cloud on s3://usgs-lidar-public
DEM_PROJECT = 'IL_4_County_QL1_LiDAR_2016_B16'
LIDAR_EPT = 'ARRA-IL_LakeCo_2007'        # the only Lake County survey on the public AWS copy (as at Adler Park)

# roads drawn beside the course (None / [] for none)
# IL 22 runs past the south edge (the clubhouse drive comes off it), 50 mph, with traffic; Old Barrington Road is past the northeast corner.
HIGHWAY = dict(ref='IL 22', ways=9)   # no 'fast': the limit does not drop on this stretch
SIDE_ROADS = [('West Old Barrington Road', 'North Old Barrington Road')]
ROUND_ROADS = True   # build.py rounds the side roads' corners

# the official scorecard (stonehengegolfclubil.com, 41621-StonehengeScorecard.pdf, 2019), yards. Men's stroke index.
# CDGA ratings: black 72.8/135, blue 70.5/130, white 68.7/126 (women 73.7/133), red 66.1/120 (women 70.6/126).
# Out of bounds stakes on 3, 4, 10, 11 and 18.
PAR = [4, 4, 4, 5, 3, 4, 4, 3, 5, 4, 4, 3, 5, 4, 4, 4, 3, 5]
HCP = [7, 9, 1, 3, 11, 5, 13, 15, 17, 8, 12, 16, 6, 10, 4, 14, 18, 2]
TEES = {  # name: (rating, slope, yards per hole)
    'black': (72.8, 135, [436, 391, 444, 561, 200, 410, 383, 205, 561, 389, 395, 187, 496, 352, 399, 355, 158, 526]),
    'blue': (70.5, 130, [418, 363, 410, 516, 184, 395, 371, 189, 501, 354, 361, 163, 478, 330, 370, 305, 140, 502]),
    'white': (68.7, 126, [400, 339, 369, 473, 188, 368, 359, 176, 468, 319, 344, 148, 428, 322, 349, 290, 127, 484]),
    'red': (66.1, 120, [382, 315, 286, 449, 133, 357, 307, 150, 450, 291, 327, 115, 365, 297, 328, 275, 110, 443]),
}
ALT = {}  # no alternate tee lengths
TREES_GONE = True   # trees_aerial.py: the lidar is from 2007, the aerial 2023; a lidar tree with no canopy on the aerial was felled since
RELIEF_OFF_WATER = True   # build.py leaves the lidar relief off the ponds, creeks and their banks
# the layers painted on all_edit.py's map, if the course is ever painted (all_read.py reads only these)
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
# the game's four tee-marker slots: w is the set played, y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('blue', 0x2f6fd0), 'y': ('black', 0x26282b), 'b': ('white', 0xeeeeee), 'r': ('red', 0xc0392b)}
