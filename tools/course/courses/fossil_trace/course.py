"""Fossil Trace Golf Club, 3050 Illinois Street, Golden CO (Jefferson County; Jim Engh, 2003): everything the pipeline needs to know about this one course.

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its painted masks and generated
files (out/). common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Fossil Trace Golf Club'
ORIGIN = (39.7413, -105.2113)  # lat, lon: the middle of the course
OSM_WAY = 1665398              # the leisure=golf_course multipolygon RELATION (osm.py takes a relation's id too): its outer ring is the course

# areas, in local metres [e0, n0, e1, n1]. The outline runs about -860..860 east, -600..600 north.
DETAIL = (-1000, -750, 1000, 750)        # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2800, -2400, 2800, 2400)        # the horizon: coarse terrain only
DEM_AREA = (-1200, -950, 1200, 950)      # the coarse terrain grid in the game's data
ROAD_AREA = (-1000, -750, 1000, 750)     # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

# elevation sources (USGS): the 1 m DEM project name in TNM download URLs, and the lidar point cloud on s3://usgs-lidar-public (DRCOG 2020, QL1)
DEM_PROJECT = 'CO_DRCOG_2020_B20'
LIDAR_EPT = 'CO_DRCOG_2_2020'

Z0 = 1990   # metres the stored heights are measured from (int16 centimetres: +-327 m): the wide terrain runs 1,707-2,281 m. courses.json engine.z0 is the same
HIGHWAY = None
SIDE_ROADS = []
ROUND_ROADS = True
ALL_ROADS = True      # every OSM road near a hole (the game draws only what is in view)
OSM_CARTPATHS = True  # OSM's golf=cartpath lines, joined across the roads

# the scorecard (golfpass.com, from the club's card), yards. Men's stroke index. The women's index differs on 11-18 and is not used.
# Tees: Black 72.0/141, T-Rex 70.9/136, Blue 68.9/130, Trike 67.8/121, White 66.2/114 (Palm and Gold are forward sets rated for women only: not used).
PAR = [5, 4, 3, 4, 3, 4, 4, 4, 5, 4, 3, 5, 4, 3, 5, 3, 4, 5]
HCP = [3, 13, 15, 5, 17, 9, 11, 7, 1, 10, 16, 4, 8, 14, 2, 18, 12, 6]
TEES = {  # name: (rating, slope, yards per hole)
    'black': (72.0, 141, [575, 320, 151, 480, 96, 409, 377, 412, 626, 333, 186, 585, 394, 231, 565, 160, 356, 542]),
    'blue': (68.9, 130, [544, 297, 135, 426, 95, 372, 338, 372, 570, 305, 154, 545, 381, 205, 536, 141, 320, 505]),
    'trike': (67.8, 121, [491, 297, 135, 383, 91, 372, 338, 317, 513, 305, 154, 507, 381, 172, 503, 141, 320, 505]),
    'white': (66.2, 114, [491, 271, 119, 383, 91, 339, 279, 317, 513, 270, 126, 507, 331, 172, 480, 128, 276, 458]),
}
ALT = {}
RELIEF_OFF_WATER = True
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
TREES_OFF_TEES_GREENS = True
FAIRWAYS_FROM_AERIAL = True   # OSM's fairways are a core stripe (and miss part of holes 1, 6, 8, 12...): fairways_fill.py adds trace.py's aerial fairways to every par 4 and 5
MOWN_ROUGH = True             # OSM's golf=rough outlines the mown rough: deep rough is only the native grass beyond 8 m of anything mown (build.py)

# greens OSM has in the wrong place: hole -> outline in local metres, traced off the 2023 aerial (osm.py swaps it for the nearest OSM green and ends
# the hole line and pin in it). Hole 15's OSM green is a strip of fairway 14 m west of the real green.
GREEN_FIX = {15: [(-381.2, -214.5), (-386.2, -214.0), (-389.0, -210.8), (-389.5, -199.2), (-395.5, -192.2), (-396.5, -189.8), (-396.5, -185.8),
                  (-394.2, -182.5), (-390.2, -181.5), (-381.2, -181.5), (-375.5, -185.8), (-374.5, -189.2), (-374.5, -191.8), (-376.0, -195.2),
                  (-375.0, -205.8), (-377.0, -211.8)]}

# the game's four tee-marker slots: w is the set played (Blue, 6,241 yd), y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('blue', 0x2a5db0), 'y': ('black', 0x26282b), 'b': ('trike', 0xc0392b), 'r': ('white', 0xeeeeee)}
