"""Writes out/cartpaths_mask_2.png: the cart paths as they stand (out/cartpaths.json) drawn as solid RED #FF0000 lines, 2.4 m wide, on the aerial map (same
pixels as cartpaths_edit.png), to edit or just look at. Orange rings (a guide, not read) mark the gaps that were closed with a link: check that each is a real path.
Edit a copy: paint more RED where a path is missing, BLUE #0000FF over red (or anything) to remove it. Read it back with
    python cartpaths_read.py cartpaths_mask_2.png --full
(red is then the whole network), then build.py and install.py."""
import json
import os

from PIL import ImageDraw
from shapely.geometry import shape

import osm
from cartpaths_edit import legend, render
from common import OUT
from preview import load_rgb


def main():
    rgb, res = load_rgb()
    img, fr, px = render(rgb, res, osm.load())
    d = ImageDraw.Draw(img)
    polys = [shape(g) for g in json.load(open(os.path.join(OUT, 'cartpaths.json')))]
    for p in polys:
        d.polygon([px(*q) for q in p.exterior.coords], fill=(255, 0, 0))
        for r in p.interiors:
            d.polygon([px(*q) for q in r.coords], fill=None)
    links = json.load(open(os.path.join(OUT, 'cartpaths_links.json')))   # the gaps cartpaths_read.py closed with a link
    for x, y, g in links:
        px_, py_ = px(x, y)
        d.ellipse([px_ - 45, py_ - 45, px_ + 45, py_ + 45], outline=(255, 140, 0), width=5)
    legend(img, [((255, 0, 0), 'RED: cart path as it stands (edit me)'), ((0, 0, 255), 'BLUE: erase'), ((255, 140, 0), 'ORANGE ring (guide): a gap I closed')])
    img.convert('RGB').save(os.path.join(OUT, 'cartpaths_mask_2.png'))
    print(img.size, len(polys), 'pieces,', len(links), 'links ringed')


if __name__ == '__main__':
    main()
