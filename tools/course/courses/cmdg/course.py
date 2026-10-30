"""Chestnut Mountain Resort disc golf course, 8700 W. Chestnut Mountain Rd, Galena IL: everything the pipeline needs to know about this one course.

A disc golf course (DISC = True): 9 holes, all par 3, played twice for the game's 18 (the long tees first, then the short ones). Its tees
and baskets are read off the course's hole map (disc_holes.json in out/, from disc_read.py); there is no OSM golf course, so the
boundary is the holes' corridors (build.py disc_course). Each course is a folder under courses/ holding this file, its git-ignored
downloads (.cache/) and its generated files (out/). common.py loads the course picked by --course <key>.
"""
NAME = 'Chestnut Mountain Disc Golf'
ORIGIN = (42.3175, -90.3950)  # lat, lon: UDisc's course point, by the lodge on the bluff top
OSM_WAY = None
DISC = True

# areas, in local metres [e0, n0, e1, n1]. The course is on the ski hill: the lodge on the bluff and the runs falling west to the river.
DETAIL = (-600, -600, 600, 600)          # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-3000, -3000, 3000, 3000)        # the horizon: coarse terrain only (the Mississippi valley to the west)
DEM_AREA = (-1500, -1500, 1500, 1500)    # the coarse terrain grid in the game's data
ROAD_AREA = (-600, -600, 600, 600)       # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

DEM_PROJECT = 'IL_8County_PlusChampaign_2019_B19'
LIDAR_EPT = 'IL_8County_PlusChampaign_B2_2019'

HIGHWAY = None
SIDE_ROADS = [('West Chestnut Mountain Road', 'West Chestnut Mt Road')]   # the resort road up to the lodge
ROUND_ROADS = True
# trees.py: oak-hickory woods; tall trees in a closed forest get narrow crowns, so only a dark crown on the aerial makes a conifer
CONIFER_NIR, CONIFER_SHAPE = 100, False

# the card (UDisc, layout "Main - 9 holes", 2,972 ft; PDGA lists dual tees). The short tees' lengths are not published: PDGA gives
# 1,880 ft for the short layout, so each short tee is taken at the same share of its hole (63 %) until the map says otherwise.
PAR9 = [3] * 9
FEET_LONG = [433, 319, 417, 384, 233, 291, 177, 258, 460]
FEET_SHORT = [round(f * 1880 / 2972) for f in FEET_LONG]
