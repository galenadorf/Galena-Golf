"""Adler Park disc golf course, Adler Memorial Park, 1700 N. Milwaukee Ave, Libertyville IL: everything the pipeline needs to know about this one course.

A disc golf course (DISC = True): 9 holes, all par 3 (1981), played twice for the game's 18. The course has one tee per hole, so the
second nine is the first again. Its tees and baskets are read off the course sign's map (hole_map.jpg beside this file, from UDisc;
disc_holes.json in out/, from disc_read.py). OSM maps only the course's outline (way 745015368, leisure=pitch, sport=disc_golf), so
the boundary is the holes' corridors (disc_build.py). Each course is a folder under courses/ holding this file, its git-ignored
downloads (.cache/) and its generated files (out/). common.py loads the course picked by --course <key>.
"""
NAME = 'Adler Park Disc Golf'
ORIGIN = (42.30305, -87.95543)  # lat, lon: UDisc's course point, by the rec centre parking
OSM_WAY = None
DISC = True

# areas, in local metres [e0, n0, e1, n1]. A town park: the arts centre, pool and school round it, the Des Plaines River to the east.
DETAIL = (-450, -450, 450, 450)          # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2000, -2000, 2000, 2000)        # the horizon: coarse terrain only
DEM_AREA = (-1000, -1000, 1000, 1000)    # the coarse terrain grid in the game's data
ROAD_AREA = (-450, -450, 450, 450)       # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

DEM_PROJECT = 'IL_4_County_QL1_LiDAR_2016_B16'
LIDAR_EPT = 'ARRA-IL_LakeCo_2007'        # the only Lake County survey on the public AWS copy

HIGHWAY = None
SIDE_ROADS = [('North Milwaukee Avenue',), ('West Adler Drive',)]   # IL 21 past the arts centre (two carriageways north of it), the school's street
ROUND_ROADS = True
# trees.py: park trees and a wooded ravine; as at Chestnut Mountain, only a dark crown on the aerial makes a conifer
CONIFER_NIR, CONIFER_SHAPE = 100, False

# the card (the course sign: "Dist (ft.)", 2,740 ft, par 27). One tee per hole, so the short nine is the same as the long one.
PAR9 = [3] * 9
FEET_LONG = [304, 366, 275, 270, 325, 300, 380, 240, 280]
FEET_SHORT = FEET_LONG
FIT_CARD = True   # disc_read.py: the sign draws its tees and baskets loosely; each hole is scaled about its middle to the card
WATER_CLIP = True   # disc_build.py: OSM's Des Plaines River is one 16 km2 area (and a long centre line); the stretch past holes 8 and 9 is cut out

# disc_build.py props (local metres, read off the NAIP 2023 aerial at 0.5 m; disc_build adds the OSM outlines named here)
# Adler Park Pool: the fenced pool complex (OSM way 61511555, the fence), the leisure pool (OSM way 369025489) and, measured here, the lap pool
# joined to it (lanes along its first edge), the side pool and the kiddie pool; the blue water slide (its tower, then the tube's path down:
# east, north, height above the tower's foot); the shade canopies over the deck.
POOL = dict(
    fence_way=61511555, water_way=369025489,
    pools=[dict(ring=[(-60.3, -236.7), (-37.5, -234.2), (-35.0, -257.5), (-58.0, -260.0)], lanes=8),
           dict(ring=[(-100.3, -223.3), (-87.0, -227.5), (-90.3, -240.8), (-103.7, -236.7)]),
           dict(ring=[(-84.2, -237.5), (-74.2, -240.0), (-76.3, -249.7), (-86.3, -247.0)])],
    slide=[(-79.0, -254.0, 6.5), (-83.0, -252.0, 5.6), (-88.0, -253.5, 4.6), (-91.0, -250.5, 3.6), (-88.0, -247.5, 2.6), (-84.0, -249.5, 1.6),
           (-82.0, -246.5, .9), (-81.0, -244.5, .4)],
    shades=[(-95.8, -201.7), (-71.7, -196.7), (-54.2, -209.2), (-73.3, -220.0), (-53.3, -266.7), (-40.0, -264.2)],
)
# the park playground by basket 3 (OSM has only a point, node 762932305): its mulch bed, and the way the play structure faces (degrees, east = 0)
PLAYGROUND = dict(mulch=[(-15.0, -141.7), (-4.2, -133.3), (10.0, -133.3), (15.0, -141.7), (11.7, -150.0), (5.0, -157.5), (-10.8, -155.0), (-17.5, -148.3)],
                  face=-90)
