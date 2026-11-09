"""Legends Course, Memphis National Golf Club, 10135 National Club Drive, Collierville TN (Shelby County): everything the pipeline needs to know about this one course.

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its painted masks and generated
files (out/). common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
The club's two courses share this frame (origin, areas), so their downloads in .cache/ are interchangeable (see courses/champions/course.py).
"""
NAME = 'Legends at Memphis National Golf Club'
ORIGIN = (35.0745, -89.7205)  # lat, lon: the middle of the club, the same for both of its courses
OSM_WAY = None   # OSM's "Memphis National Golf Course" outline (way 384260125) covers only the southern holes: the course is made from the holes
HOLE_BOX = (-900, -560, 480, 1460)   # the Legends' 18 holes are OSM's (the Champions are not mapped); Ridgeway Country Club's holes lie west of this
OUTLINE_BUFFER = 70    # osm.py: the outline (the out-of-bounds line) is the holes' lines buffered by this
KEEP_NEAR_HOLES = 110  # osm.py: OSM's golf features count only within this of the Legends' holes (the Champions' bunkers and paths are its own)

# areas, in local metres [e0, n0, e1, n1]. The Legends run about -800..400 east, -520..1400 north (a long loop north of the clubhouse); the Champions
# lie east of it (100..800 east, -520..800 north); both fit this detail area.
DETAIL = (-1050, -700, 950, 1500)        # the club and its edges: 1 m terrain, aerial, lidar
WIDE = (-3000, -2800, 3000, 3000)        # the horizon: coarse terrain only
DEM_AREA = (-1250, -900, 1150, 1700)     # the coarse terrain grid in the game's data
ROAD_AREA = (-1050, -700, 950, 1500)     # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

# elevation sources (USGS): the 1 m DEM project name in TNM download URLs, and the lidar point cloud on s3://usgs-lidar-public
DEM_PROJECT = 'TN_ShelbyCo_2017'
LIDAR_EPT = 'TN_ShelbyCo_2012'          # the Shelby County survey on the public AWS copy (the 2019 West Tennessee ones do not cover the club)

# roads drawn beside the course. Houston Levee Road (north-south, west of the club) has no west-to-east stretch, so no highway with traffic.
HIGHWAY = None
SIDE_ROADS = [('Houston Levee Road',)]
ROUND_ROADS = True   # build.py rounds the side roads' corners
ALL_ROADS = True     # build.py draws every OSM road near a hole, not just the SIDE_ROADS names (the game draws only what is in view)
OSM_CARTPATHS = True  # (only if no cartpaths.json: the paths are painted now, see PAINT)

# the scorecard (golfpass.com Legends card, the club's black/white/gold/green sets), yards. Men's stroke index. Ed Seay and Arnold Palmer, opened 1971
# (renovated by Roy Case 1999 and 2016). Ratings (golfpass tee table, golfify for white): black 72.1/131, white 70.5/126, gold 67.6/121, green (women) 69.1/122.
PAR = [5, 4, 4, 4, 3, 4, 3, 5, 4, 4, 3, 5, 4, 4, 3, 5, 4, 4]
HCP = [8, 2, 16, 4, 10, 12, 18, 14, 6, 9, 1, 5, 3, 15, 11, 13, 7, 17]
TEES = {  # name: (rating, slope, yards per hole)
    'black': (72.1, 131, [543, 398, 329, 402, 195, 346, 148, 523, 365, 344, 242, 580, 436, 340, 195, 570, 380, 375]),
    'white': (70.5, 126, [502, 344, 315, 383, 178, 328, 140, 507, 339, 326, 215, 534, 414, 329, 180, 540, 360, 340]),
    'gold': (67.6, 121, [462, 317, 284, 354, 155, 312, 130, 448, 300, 302, 183, 470, 384, 311, 135, 520, 300, 310]),
    'green': (69.1, 122, [442, 296, 264, 289, 115, 259, 109, 413, 270, 281, 148, 447, 351, 250, 115, 460, 260, 280]),
}
ALT = {}  # no alternate tee lengths
TREES_GONE = True   # trees_aerial.py: the lidar is from 2012, the aerial 2023; a lidar tree with no canopy on the aerial was felled since
RELIEF_OFF_WATER = True   # build.py leaves the lidar relief off the ponds, creeks and their banks
FAIRWAYS_FROM_AERIAL = True   # OSM maps only a few core stripes of fairway: trace.py's aerial fairways fill every par 4 and 5
PAINT = ('fairway', 'green', 'tee', 'bunker', 'fescue', 'path', 'lot', 'wash', 'fence', 'clump', 'drain', 'tee_dot')   # trees and cart paths stay as the data has them
# the game's four tee-marker slots: w is the set played, y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('white', 0xeeeeee), 'y': ('black', 0x26282b), 'b': ('gold', 0xd9b23a), 'r': ('green', 0x2f8f4f)}

# tee sets put in the tee box named by a point in it (build.py TEE_BOXES), by the user's reading of the boxes on the aerial: the card yardage puts them one box too far back
# on these holes. Hole 18's most forward box (-452, 211) is the water drop zone, not a tee.
TEE_BOXES = {
    8: {'black': (-669.4, -485.1), 'white': (-673.5, -464.0)},   # white in the back-middle of the second box
    9: {'white': (-717.1, 3.3), 'gold': (-677.4, 20.1), 'green': (-653.5, 24.5)},
    18: {'black': (-269.8, 220.0), 'white': (-298.5, 214.8), 'gold': (-324.5, 211.1), 'green': (-355.8, 220.7)},
}

# cart-path bridges (e, n, bearing counter-clockwise from east, length m, hole): OSM's four bridge=yes ways, each checked on the aerial (a short concrete deck over the creek)
CART_BRIDGES = [
    (243.3, -310.0, -157.4, 17, 2),
    (211.4, -302.7, 111.2, 15, 2),
    (-419.8, -482.0, -61.8, 11, 5),
    (-187.0, -397.7, 107.9, 14, 1),
]

# houses along the holes: Overture Maps footprints plus roofs found on the aerial (buildings_overture.py, buildings_detect.py), within this of a hole line (or 20 m less of a fairway, green, tee)
OVERTURE_REACH = 130
ROOF_TRAIN = (-300, -300, 250, 0)   # the part of the course whose buildings are all mapped: what the roof finder learns from
# steady car traffic on a road (build.py roadBusy; the game's side-road cars, cars only): Frank Road runs along the south edge, tertiary, 40 mph
TRAFFIC = {'Frank Road': dict(cars=10, mph=40, colors=[0xf2f2f0, 0xb9bec4, 0x1b1c1f, 0xb3262e, 0x1f3f7a, 0x7b92ac, 0x2f5a3c, 0xc8b48a, 0x6b1f2a, 0x4a4f55])}   # a mix of body colours: white, silver, black, red, blue, light blue, green, tan, maroon, charcoal
NO_FAIRWAY_HULL = True    # build.py: the painted fairways already touch the greens; the convex-hull link would fill notches and reach over water
FAIRWAY_OFF_WATER = True  # build.py: fairway polygons are cut back from the ponds
FAIRWAY_SETBACK = {3: 16.8}   # build.py: hole 3's fairway stays 10 yd (9.1 m) from the water the player sees (the game's water line lies about 5.5 m past the creek ribbon: dug banks) after the tee
# out of bounds at the property lines where houses line a hole: a lot reaches HOUSE_LOTS m past a house's walls (rows of lots are joined), the clubhouse area is exempt;
# the stretches of boundary along lots are drawn as a 2-rail split-rail cedar fence
HOUSE_LOTS = 12
HOUSE_LOTS_JOIN = 10
HOUSE_LOTS_EXEMPT = [(-400, -70, 115)]   # the clubhouse, cart barns and lot
# trees_fill.py: boxes (e0, n0, e1, n1) where pines the lidar and the canopy classifier missed are found on the aerial: the Frank Road border, and the trees south of the 18th tee
TREES_FILL = [(-880, -548, 480, -478), (-470, 150, -140, 232)]
ROAD_ROW_DEEP = 1.5   # build.py: deep rough under every row of trees lining a road, 5 ft beyond the crowns
TREE_HEIGHT = [((-420, 108, -360, 130), 2, 2.0)]   # the four pines on the far shore of the lake from the 18th tee: twice as tall
TREES_OFF_TEES_GREENS = True   # build.py: no tree stands in a tee box or on a green
SMOOTH_MORE = True
SMOOTH_PAINTED = True   # build.py: the painted bunkers and tee boxes are low-passed too, so no outline keeps a pixel staircase or a hull corner

# hole 4: the trees crowding the tee boxes (south of them) moved 20 ft (6.1 m) south, toward Frank Road
# Frank Road's trees on the course side are tall, skinny deciduous 'spears' about 60 ft tall (kind 6: bare trunk to 30 ft, then a narrow crown); h and d are the range in m
CREEK_CUT = [(-310, -530, -240, -454.5)]   # build.py: no creek branch across hole 4's fairway: it stops just north of the cart path (the water 2.7 m off its edge, the dug bank reaching it) (the path's north edge is at n -460.4 there)
CREEK_DEEP = 1.524   # build.py: deep rough on both banks of the creek, 5 ft past the top of the dug bank
TREE_SPEARS = dict(road='Frank Road', reach=60.0, convert=12.0, into=4.57, gap=3.0, h=(16.5, 20.0), d=(3.0, 5.0))   # build.py: along the stretch of Frank Road beside the course, every tree on the course (north) side within 12 m of the road becomes a spear, and the strip from the shoulder to 15 ft (4.57 m) further north is packed with them 3 m apart; trees south of the road stay as they are
TREE_SHIFT = [((-10, -535, 90, -518), 0, -6.1)]
