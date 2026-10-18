"""Read out/hole7_zoom_mask.png (painted on out/hole7_zoom.png; see hole_zoom_edit.py):
  RED line     the two tee markers of the played (gold) tee: its middle is the tee, half its length is the marker offset
  YELLOW dot   where the sign post stands
Writes out/tee_marks.json ({hole: {"mid": [e, n], "half": m, "angle": deg}}) and out/sign_pos.json ({hole: [e, n]}).
build.py plays the hole from the middle and spaces the gold markers by the line's length; site_paint.py puts the sign on the dot.
Rerun this, site_paint.py, build.py, install.py after repainting."""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from common import OUT


def blob(a, rgb):
    m = ndi.binary_closing(np.abs(a - np.array(rgb)).max(2) <= 40, iterations=2)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    assert n and max(sizes) >= 40, f'no {rgb} paint found'
    ys, xs = np.nonzero(lab == 1 + int(np.argmax(sizes)))
    return xs, ys


def main(ref=7):
    f = json.load(open(os.path.join(OUT, f'hole{ref}_zoom.json')))
    a = np.array(Image.open(os.path.join(OUT, f'hole{ref}_zoom_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == f['w'] and a.shape[0] == f['h'], 'the mask must have the map\'s size'
    a[f['h'] - 250:f['h'] - 20, 20:1020] = 0   # the key printed on the map
    ll = lambda x, y: (f['e0'] + x / f['ppm'], f['n1'] - y / f['ppm'])
    xs, ys = blob(a, (255, 0, 0))
    P = np.c_[xs, ys].astype(float); c = P.mean(0)
    u = np.linalg.svd(P - c, full_matrices=False)[2][0]   # the line's axis
    t = (P - c) @ u
    ends = [ll(*(c + u * t.min())), ll(*(c + u * t.max()))]
    mid = [(ends[0][0] + ends[1][0]) / 2, (ends[0][1] + ends[1][1]) / 2]
    half = math.hypot(ends[0][0] - ends[1][0], ends[0][1] - ends[1][1]) / 2
    ang = math.degrees(math.atan2(ends[1][1] - ends[0][1], ends[1][0] - ends[0][0])) % 180
    sx, sy = blob(a, (255, 255, 0))
    sign = ll(sx.mean(), sy.mean())
    json.dump({str(ref): {'mid': [round(mid[0], 2), round(mid[1], 2)], 'half': round(half, 2), 'angle': round(ang)}}, open(os.path.join(OUT, 'tee_marks.json'), 'w'))
    json.dump({str(ref): [round(sign[0], 2), round(sign[1], 2)]}, open(os.path.join(OUT, 'sign_pos.json'), 'w'))
    print(f'hole {ref}: tee middle {mid[0]:.1f}, {mid[1]:.1f}; markers {2 * half / .9144:.1f} yd apart (line angle {ang:.0f} deg); sign {sign[0]:.1f}, {sign[1]:.1f}')


if __name__ == '__main__':
    main(*(int(x) for x in sys.argv[1:2]))
