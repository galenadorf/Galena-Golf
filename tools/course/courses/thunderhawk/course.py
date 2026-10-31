"""Thunderhawk Golf Club, 39700 N Lewis Ave, Beach Park IL (Lake County): everything the pipeline needs to know about this one course.

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its painted masks and generated
files (out/). common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Thunderhawk Golf Club'
ORIGIN = (42.4391, -87.8654)  # lat, lon: the middle of the course
OSM_WAY = 40333078            # the leisure=golf_course way: its outline is the course

# areas, in local metres [e0, n0, e1, n1].
# The outline runs about -870..865 east, -385..390 north: a long rectangle between Green Bay Road (west), Lewis Avenue (east) and 33rd Street (south).
DETAIL = (-1150, -650, 1150, 650)        # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2800, -2400, 2800, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-1400, -1100, 1400, 1100)    # the coarse terrain grid in the game's data
ROAD_AREA = (-1150, -650, 1150, 650)     # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

# elevation sources (USGS): the 1 m DEM project name in TNM download URLs, and the lidar point cloud on s3://usgs-lidar-public
DEM_PROJECT = 'IL_4_County_QL1_LiDAR_2016_B16'
LIDAR_EPT = 'ARRA-IL_LakeCo_2007'        # the only Lake County survey on the public AWS copy (as at Adler Park and Stonehenge)

# roads drawn beside the course (None / [] for none)
# No highway with traffic (build.py's highway runs west to east; the busy roads here run north-south).
HIGHWAY = None
SIDE_ROADS = [('North Lewis Avenue', 'Lewis Avenue'), ('North Green Bay Road',), ('West 33rd Street', '33rd Street')]
ROUND_ROADS = True   # build.py rounds the side roads' corners

# the official scorecard (thunderhawkgolfclub.org, Thunderhawk-scorecard-1/2.jpg, Fore Better Golf 2014), yards. Men's stroke index.
# Robert Trent Jones Jr., opened 1999, Lake County Forest Preserves.
# Ratings: black 74.2/141, brass 72.4/137, bronze 71.2/134, silver 70.1/131 (women 75.6/138), auburn (women) 69.6/125.
PAR = [4, 5, 3, 4, 4, 3, 5, 4, 4, 4, 5, 4, 3, 4, 3, 5, 3, 5]
HCP = [17, 5, 9, 3, 7, 11, 15, 13, 1, 14, 16, 4, 8, 12, 18, 2, 10, 6]
TEES = {  # name: (rating, slope, yards per hole)
    'black': (74.2, 141, [414, 573, 212, 446, 416, 178, 522, 338, 481, 429, 517, 385, 225, 363, 172, 578, 182, 600]),
    'brass': (72.4, 137, [394, 554, 187, 424, 391, 168, 501, 333, 452, 409, 512, 363, 200, 317, 145, 568, 154, 559]),
    'bronze': (71.2, 134, [369, 534, 187, 394, 391, 168, 470, 333, 417, 362, 512, 363, 160, 317, 172, 568, 130, 514]),
    'silver': (70.1, 131, [369, 534, 153, 394, 379, 138, 470, 302, 417, 362, 503, 331, 160, 276, 134, 558, 130, 514]),
    'auburn': (69.6, 125, [298, 453, 95, 309, 326, 90, 422, 254, 378, 299, 444, 241, 120, 246, 66, 401, 106, 498]),
}
ALT = {}  # no alternate tee lengths
TREES_GONE = True   # trees_aerial.py: the lidar is from 2007, the aerial 2023; a lidar tree with no canopy on the aerial was felled since
RELIEF_OFF_WATER = True   # build.py leaves the lidar relief off the ponds, creeks and their banks
# the layers painted on all_edit.py's map, if the course is ever painted (all_read.py reads only these)
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
# the game's four tee-marker slots: w is the set played, y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('bronze', 0xc0682a), 'y': ('black', 0x26282b), 'b': ('silver', 0xc8ccd2), 'r': ('auburn', 0xa8323c)}
