"""Woodbine Bend Golf Course, 3500 E Center Rd, Stockton IL: everything the pipeline needs to know about this one course.

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its painted masks and generated
files (out/). common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Woodbine Bend Golf Course'
ORIGIN = (42.3373, -90.1503)  # lat, lon: the middle of the course
OSM_WAY = 295902659           # the leisure=golf_course way: its outline is the course (None: the only one in the download)

# areas, in local metres [e0, n0, e1, n1]
DETAIL = (-700, -700, 700, 700)          # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2400, -2000, 2400, 2000)        # the horizon: coarse terrain only
DEM_AREA = (-1200, -1200, 1200, 1200)    # the coarse terrain grid in the game's data
ROAD_AREA = (-1250, -720, 1250, 720)     # the highway and side roads are clipped to this (the game's 2 m class grid)

# elevation sources (USGS): the 1 m DEM project name in TNM download URLs, and the lidar point cloud on s3://usgs-lidar-public
DEM_PROJECT = 'IL_8County_PlusChampaign_2019_B19'
LIDAR_EPT = 'IL_8County_PlusChampaign_B2_2019'

# roads drawn beside the course (None / [] for none). The highway has traffic in the game: its OSM ref, how many ways make it, and the
# maxspeed of the stretch whose far end is where the limit drops (hwSlow in the data). Side roads are for looks: OSM names, one tuple per road.
HIGHWAY = dict(ref='US 20', ways=2, fast='55 mph')
SIDE_ROADS = [('East Center Road',), ('South Brown Road', 'Chicago Street')]

# the official scorecard (woodbinebend.com, 2024), yards. Holes 2 and 7 have two tee lengths per set; the first is used.
PAR = [4, 3, 4, 5, 4, 4, 3, 4, 5, 4, 3, 4, 4, 4, 3, 5, 4, 5]
HCP = [8, 16, 18, 6, 12, 2, 14, 4, 10, 13, 17, 5, 1, 15, 7, 3, 11, 9]
TEES = {  # name: (rating, slope, yards per hole)
    'black': (71.8, 124, [394, 159, 325, 524, 359, 422, 200, 405, 486, 343, 172, 389, 406, 321, 201, 535, 420, 478]),
    'gold': (70.3, 121, [370, 143, 306, 514, 343, 412, 154, 384, 467, 329, 148, 372, 392, 319, 182, 513, 398, 474]),
    'silver': (69.3, 118, [347, 133, 295, 488, 330, 402, 142, 370, 454, 319, 131, 359, 386, 304, 168, 498, 326, 451]),
    'bronze': (70.4, 116, [303, 115, 272, 410, 314, 340, 113, 331, 396, 299, 104, 302, 340, 294, 134, 420, 292, 413]),
}
ALT = {1: {'black': 151, 'gold': 133, 'silver': 124, 'bronze': 105}, 6: {'gold': 157, 'silver': 147}}  # the other tee on 2 and 7
# the game's four tee-marker slots: w is the set played, y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('gold', 0xd9b23a), 'y': ('black', 0x26282b), 'b': ('silver', 0xc9ced3), 'r': ('bronze', 0xb07045)}
