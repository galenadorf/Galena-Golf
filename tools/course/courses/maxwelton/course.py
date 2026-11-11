"""Maxwelton Braes Golf Resort, 7670 State Highway 57, Baileys Harbor WI (Door County): everything the pipeline needs to know about this one course (an alpha build from OpenStreetMap).

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its generated files (out/).
common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Maxwelton Braes Golf Resort'
ORIGIN = (45.04393, -87.13623)  # lat, lon: the middle of the course
OSM_WAY = 74452148              # the leisure=golf_course way: its outline is the course (18 hole lines with par and ref, 19 greens, 24 tees, 19 fairways, 57 bunkers). The outline runs about -430..430 east, -405..405 north.

# areas, in local metres [e0, n0, e1, n1]
DETAIL = (-650, -600, 650, 600)          # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2400, -2400, 2400, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-850, -800, 850, 800)        # the coarse terrain grid in the game's data
ROAD_AREA = (-650, -600, 650, 600)       # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

# elevation sources (USGS): the 1 m DEM project in the TNM download URLs and the lidar point cloud on s3://usgs-lidar-public, both the WI FEMAHQ 2018 survey (flown 2018-19).
# (The National Map was down on 2026-11-11, so the first build used Planetary Computer's 2 m copies: DEM_SOURCE / CHM_SOURCE = 'pc' in fetch.py and lidar.py. USGS was back and
# the 1 m DEM and the point cloud both exist, so the course was switched over the same day.)
DEM_PROJECT = 'WI_FEMAHQ_2018'
LIDAR_EPT = 'USGS_LPC_WI_FEMAHQ_2018_LAS_2019'

# WI 57 runs diagonally through the middle of the course (between holes 3/18 and 9/10); County Trunk E runs along the north edge. The side streets are every OSM road near a hole (ALL_ROADS).
HIGHWAY = dict(ref='WI 57', ways=1)
SIDE_ROADS = []
ROUND_ROADS = True
ALL_ROADS = True
OSM_CARTPATHS = True

# the scorecard (18birdies.com, 2026), yards. Men's stroke index. Par 72 (OSM tags holes 4 and 12 as par 4; the card has par 5s, 456 and 453 yd).
# Ratings: green 69.5/119, gold 69.5/119, white 69.5/119, blue 66.5/108, orange 66.5/108. Green is the back tee and is the one played.
PAR = [4, 4, 5, 5, 3, 4, 4, 3, 4, 4, 5, 5, 4, 4, 3, 4, 3, 4]
HCP = [13, 17, 15, 3, 9, 5, 7, 11, 1, 4, 16, 12, 6, 8, 10, 14, 18, 2]
TEES = {  # name: (rating, slope, yards per hole)
    'green': (69.5, 119, [298, 258, 466, 456, 180, 351, 342, 140, 411, 373, 515, 453, 366, 372, 206, 313, 131, 410]),
    'gold': (69.5, 119, [273, 237, 427, 408, 165, 322, 313, 128, 350, 342, 515, 415, 336, 341, 189, 287, 120, 376]),
    'white': (69.5, 119, [248, 215, 388, 380, 150, 293, 285, 117, 327, 311, 429, 378, 305, 310, 172, 261, 100, 342]),
    'blue': (66.5, 108, [225, 195, 350, 340, 135, 265, 255, 105, 310, 280, 385, 340, 275, 280, 155, 235, 100, 310]),
    'orange': (66.5, 108, [199, 172, 311, 304, 120, 234, 228, 93, 274, 249, 344, 302, 244, 248, 137, 209, 87, 273]),
}
ALT = {}  # no alternate tee lengths
RELIEF_OFF_WATER = True
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
TREES_OFF_TEES_GREENS = True
SMOOTH_MORE = True
FINAL_ROUND = dict(fair=(3, 3), water=(2.5, 0), fescue=(3, 1.5), bound=(3, 3))
SMOOTH_PAINTED = True

# the game's four tee-marker slots: w is the set played (green here, 6,041 yd), y/b/r the others (tee set, marker colour). Five sets on the card; the white is left out.
MARKERS = {'w': ('green', 0x2e8b3d), 'y': ('gold', 0xd9b23a), 'b': ('blue', 0x2f6fd0), 'r': ('orange', 0xe67e22)}

# OSM maps 7 of the fairways as ways and the rest as multipolygon relations (golf=fairway): osm.py reads those relations too
OSM_GOLF_RELATIONS = True
