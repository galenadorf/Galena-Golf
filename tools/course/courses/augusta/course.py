"""Augusta National Golf Club, 2604 Washington Road, Augusta GA (Richmond County): everything the pipeline needs to know about this one course
(built from OpenStreetMap, the USGS 1 m terrain model and the GA Statewide 2018 lidar; Masters week, with the tournament dressing).

Each course is a folder under courses/ holding this file, its git-ignored downloads (.cache/) and its generated files (out/).
common.py loads the course picked by --course <key> (or GALENA_COURSE; woodbine when neither is given).
"""
NAME = 'Augusta National Golf Club'
ORIGIN = (33.4995, -82.0240)    # lat, lon: the middle of the 18 holes
OSM_WAY = 871993734             # the leisure=golf_course way. It also holds the Par 3 course (9 unnamed par-3 holes, NE) and the practice grounds,
                                # so only the 18 named holes are kept (HOLE_WAYS)
HOLE_WAYS = [854913181, 854915607, 854940639, 854940645, 854940652, 854940657, 854949697, 855188617, 854913182,
             855188624, 855657864, 855657869, 855657881, 855658985, 856563246, 856563253, 856563261, 856563268]

# areas, in local metres [e0, n0, e1, n1]. The 18 holes run about -420..470 east, -650..600 north; the clubhouse and Magnolia Lane reach
# Washington Road about 800 m north.
DETAIL = (-850, -900, 950, 1100)         # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2600, -2600, 2700, 2800)        # the horizon: coarse terrain only
DEM_AREA = (-1050, -1100, 1150, 1300)    # the coarse terrain grid in the game's data
ROAD_AREA = (-850, -900, 950, 1100)      # the side roads are clipped to this (the game's 2 m class grid: engine gr in courses.json)

# elevation sources (USGS): the 1 m DEM project in the TNM download URLs and the lidar point cloud on s3://usgs-lidar-public (GA Statewide 2018, block 8)
DEM_PROJECT = 'GA_Statewide_2018_B18_DRRA'
LIDAR_EPT = 'GA_Statewide_B8_2018'

# Washington Road (GA 28) runs along the north-east side (Magnolia Lane leaves it), Berckmans Road along the west. No highway in view.
HIGHWAY = None
SIDE_ROADS = []
ROUND_ROADS = True
ALL_ROADS = True
OSM_CARTPATHS = True

# the Masters card (2025; the 13th lengthened to 545 in 2023), yards. Par 72, 7,555 yd. Stroke index from OSM (the club's own).
PAR = [4, 5, 4, 3, 4, 3, 4, 5, 4, 4, 4, 3, 5, 4, 5, 3, 4, 4]
HCP = [9, 1, 13, 15, 5, 17, 11, 3, 7, 6, 8, 16, 4, 12, 2, 18, 14, 10]
NAMES = ['Tea Olive', 'Pink Dogwood', 'Flowering Peach', 'Flowering Crab Apple', 'Magnolia', 'Juniper', 'Pampas', 'Yellow Jasmine', 'Carolina Cherry',
         'Camellia', 'White Dogwood', 'Golden Bell', 'Azalea', 'Chinese Fir', 'Firethorn', 'Redbud', 'Nandina', 'Holly']
_M = [445, 585, 350, 240, 495, 180, 450, 570, 460, 495, 520, 155, 545, 440, 550, 170, 440, 465]
TEES = {  # name: (rating, slope, yards per hole). Only the Masters card is published per hole; the member sets are estimates (the club's
          # card is private): the Masters lengths scaled to about 6,900, 6,350 and 5,600 yd, rounded to 5 yd. Ratings are guesses for the handicap tool.
    'masters': (78.1, 148, _M),
    'member': (74.0, 140, [round(y * .913 / 5) * 5 for y in _M]),
    'forward': (71.5, 133, [round(y * .84 / 5) * 5 for y in _M]),
    'short': (68.0, 122, [round(y * .74 / 5) * 5 for y in _M]),
}
ALT = {}  # no alternate tee lengths
RELIEF_OFF_WATER = True
PAINT = ('fairway', 'green', 'tee', 'bunker', 'tee_dot')
TREES_OFF_TEES_GREENS = True
TREES_OFF_FAIRWAYS = True
TREES_OFF_TEE_FRONT = {11: (100, 9)}   # hole 11's tee faced a wall of pines from the lidar and aerial trees (and its small trees and white dogwoods stood in the line): a 100 m x 18 m corridor out of the tee is clear (the real tee looks down an open chute between pines)
SMOOTH_MORE = True
FINAL_ROUND = dict(fair=(3, 3), water=(2.5, 0), fescue=(3, 1.5), bound=(3, 3))
SMOOTH_PAINTED = True
TEE_FACE = True
OSM_GOLF_RELATIONS = True   # most fairways are multipolygon relations

# the game's four tee-marker slots: w is the set played (the Masters tees), y/b/r the others (tee set, marker colour)
MARKERS = {'w': ('masters', 0x1f5f3a), 'y': ('member', 0xd9b23a), 'b': ('forward', 0xf2f2f2), 'r': ('short', 0xc0392b)}

# OSM golf features that are not part of the 18 (osm.py): the patrons' walkway mown as fairway, and the practice grounds
OSM_SKIP_NAMES = ['Gallery Fairway Area', 'Members Short Game Area', 'Composite Course', 'Redbud Replica', 'Pampas Replica', 'Chinese Fir Replica']
# Hurricane Helene (2024-09-27) felled many of the club's trees after the 2018 lidar: the newest aerial (NAIP 2025-09-25) is the truth, so a lidar
# tree with no canopy on it is dropped (trees_aerial.py)
TREES_GONE = True

# the southern floor (pines.py, called by build.py): pine straw under every stand, the stone bridges from OSM (Hogan at 12, Nelson at 13, Sarazen
# at 15 and the unnamed spans), and the azaleas in bloom for Masters week along the straw's edge. Placement follows the club's own record of its
# plantings: the 13th (Azalea) holds the most, some 1,600 plants down the left along the tributary of Rae's Creek and behind the green; the hill
# behind 12; the bank left of 10's green; behind 16 and 15; around 2, 9, 11 and 18's greens. Colours are the cultivars reported as the club's common ones (Southern Indicas):
# 0 'Judge Solomon' rose-salmon pink, 1 'Formosa' magenta-violet, 2 'George L. Tabor' pale orchid pink, 3 'Mrs. G. G. Gerbing' white; by default Formosa,
# the South's most planted azalea, is two in five.
STRAW = True
STONE_BRIDGES = True
PLANTINGS = [
    dict(hole=13, at='green', reach=70, side='all', gap=1.6, r=1.3),
    dict(hole=13, at='line', reach=28, side='left', gap=1.8, r=1.2),
    dict(hole=12, at='green', reach=55, side='behind', gap=1.8, r=1.2),
    dict(hole=10, at='green', reach=60, side='left', gap=2.0, r=1.2),
    dict(hole=16, at='green', reach=75, side='behind', gap=2.2),
    dict(hole=15, at='green', reach=75, side='behind', gap=2.6),
    dict(hole=2, at='green', reach=75, side='all', gap=3.0, cols=[2, 0, 3]),
    dict(hole=9, at='green', reach=65, side='behind', gap=3.2),
    dict(hole=11, at='green', reach=40, side='behind', gap=2.8, cols=[3, 2, 0]),
    dict(hole=18, at='green', reach=70, side='left', gap=3.2),
]

# hand-placed plants (pines.specimens; the game draws each kind as that plant, as it stands in Masters week). Where each stands and when it flowers is
# taken from published guides to the course's plants: GOLF.com's field guide, NBC (2026), AP photographs of the 2026 practice rounds, and the two
# hole-by-hole plant guides at outdoordreamsva.com ("The Plants of Augusta National") and harborclub.com ("Augusta National's Trees and Flowers").
#   Magnolia Lane: 61 Southern magnolias planted from seed by the Berckmans in the late 1850s, 330 yd from Washington Road to Founders Circle; one
#   was lost to Hurricane Helene in 2024, so 60 stand. OSM ways 951829126 (the gate stretch) and 871993723 (the lane), 274 m together.
#   The Big Oak behind the clubhouse (planted in the late 1850s, the club's own history): OSM node 11927490812, "The Tree".
#   The club's one palm, "just to the right of the green on the par-3 fourth" (NBC; the 4th was called Palm before it became Flowering Crab Apple).
# hole by hole (where; in flower or not in the second week of April):
#    1 tea olive: right of the fairway and behind the green (both guides); flowers December to March: in leaf
#    2 pink dogwood: both sides of the fairway, "masses" of them (both guides; AP: right of the fairway, in bloom); in bloom
#    3 flowering peach: right of the fairway (Harbor Club); blooms mid to late March (Outdoor Dreams) or to early April (Harbor Club): the last of it
#    4 flowering crab apple: either side of the fairway approaching the green (both guides); late March and early April: in bloom (GOLF.com, NBC)
#    5 magnolia: along the fairway and around the green (Outdoor Dreams); flowers May and June: in leaf
#    6 juniper (eastern red cedar): round the tee and the right side of the green (Harbor Club); evergreen
#    7 pampas grass: left of the fairway (Outdoor Dreams); plumes in August, the seed tassels lasting into spring: green clumps, a few faded plumes
#    8 Carolina yellow jasmine: ESTIMATE, no guide says where (a vine: low mounds on the tree line by the green); February to late March (Outdoor
#      Dreams) or to late April (Harbor Club): a little yellow left
#    9 Carolina cherry: right of the fairway (Harbor Club); small creamy-white flowers in April: in bloom
#   10 camellia: behind the green and left of the fairway (both guides); blooms well before the Masters (NBC): in leaf
#   11 white dogwood: framing the hole (GOLF.com); late March to May: in bloom
#   12 golden bell (weeping forsythia): behind the green (both guides); March and early April: the end of it, half yellow
#   14 Chinese fir: left of the fairway (Outdoor Dreams); evergreen, keeping its old dry foliage for years
#   15 firethorn: ESTIMATE, no guide says where (round the green); covered in creamy-white flowers in April (both guides); the red berries are autumn's
#   16 redbud: ESTIMATE on the tree line nearest the green (NBC puts it on 16; Outdoor Dreams: "along the fairways throughout the course"); orchid pink
#   17 nandina: along the left side of the fairway (Outdoor Dreams); flowers in May: in leaf, bronze-red new growth
#   18 holly: both sides of the tee (NBC) and along the fairway, "several varieties" (Outdoor Dreams); a few red berries left
SPECIMENS = [
    dict(kind='magnolia', way=[951829126, 871993723], count=60, offset=6.5, d=12, h=16, trim=(10, 8)),
    dict(kind='bigoak', node=11927490812, d=30, h=20),
    dict(kind='tea_olive', hole=1, along=(.45, .9), side='right', n=4, d=4, h=5),
    dict(kind='tea_olive', hole=1, at='green', side='both', n=3, d=4, h=5, reach=50),
    dict(kind='dogwood_pink', hole=2, along=(.2, .9), side='both', n=14, d=6, h=7),
    dict(kind='peach', hole=3, along=(.3, .85), side='right', n=5, d=5, h=5, reach=100),
    dict(kind='crabapple', hole=4, along=(.6, .95), side='both', n=4, d=6, h=6),
    dict(kind='palm', hole=4, beside='green', side='right', gap=6, d=4, h=9),
    dict(kind='magnolia', hole=5, along=(.25, .9), side='both', n=8, d=10, h=14),
    dict(kind='magnolia', hole=5, at='green', side='both', n=4, d=10, h=14, reach=50),
    dict(kind='juniper', hole=6, at='tee', side='both', n=4, d=3.5, h=10, reach=30),
    dict(kind='juniper', hole=6, at='green', side='right', n=3, d=3.5, h=10, reach=90),
    dict(kind='pampas', hole=7, along=(.3, .8), side='left', n=5, d=2.8, h=2.4),
    dict(kind='yellow_jasmine', hole=8, near='green', n=3, d=3, h=1.6, reach=80),
    dict(kind='carolina_cherry', hole=9, along=(.3, .85), side='right', n=5, d=5, h=7),
    dict(kind='camellia', hole=10, along=(.4, .9), side='left', n=5, d=3.5, h=4),
    dict(kind='camellia', hole=10, at='green', side='both', n=4, d=3.5, h=4, reach=50),
    dict(kind='dogwood_white', hole=11, along=(.25, .85), side='both', n=12, d=6, h=7),
    dict(kind='golden_bell', hole=12, at='green', side='both', n=6, d=3, h=2.2, reach=60),
    dict(kind='chinese_fir', hole=14, along=(.2, .8), side='left', n=5, d=5, h=14),
    dict(kind='firethorn', hole=15, near='green', n=3, d=3, h=2.4, reach=80),
    dict(kind='redbud', hole=16, near='green', n=2, d=6, h=6, reach=80),
    dict(kind='nandina', hole=17, along=(.3, .85), side='left', n=8, d=1.6, h=1.8, reach=100),
    dict(kind='holly', hole=18, at='tee', side='both', n=4, d=5, h=9, reach=25),
    dict(kind='holly', hole=18, along=(.3, .85), side='both', n=6, d=5, h=9),
]

# the 12 OSM buildings tagged man_made=tower are the tournament's TV towers: not drawn as buildings (they belong with the Masters dressing)
BUILDINGS_SKIP = {'man_made': 'tower'}
