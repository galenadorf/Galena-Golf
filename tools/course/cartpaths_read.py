"""Cart paths: the found paths (cartpaths_edit.py) corrected by the hand-painted out/cartpaths_mask.png (RED = a missing path, BLUE = remove what was found
there; same pixels as out/cartpaths_edit.png). Each path is reduced to its middle line and drawn again 2.4 m wide, then its outline is smoothed. Writes
out/cartpaths.json (polygons in local metres); build.py encodes them as feat.path (the game's 'Cart path' surface: asphalt, a hard bouncy lie). Without a
mask the found paths are used as they are. `--full` with a mask whose red is the whole network (cartpaths_export.py writes one) starts from nothing. The thin network is traced into lines (a line per stretch between junctions and ends), each line is
smoothed along its length (every corner and curve rounded, junctions held), and only then given its width, so edges come out clean and light."""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.ndimage import gaussian_filter1d
from shapely.geometry import LineString, mapping
from shapely.geometry import Point
from shapely.ops import nearest_points, unary_union
from skimage.morphology import skeletonize

from common import OUT
from cartpaths_edit import PATH_W, band

BRIDGE, MIN_PIECE = 12.0, 40.0   # gaps up to this many m between pieces are closed; a piece shorter than this that is still on its own is dropped
LINE_SIGMA, SPUR, TOL = 3.5, 5.0, .06   # m of smoothing along a line, shortest dead-end stub kept, simplification of the outline
RED, BLUE = (255, 0, 0), (0, 0, 255)


def coarse(mask, ed, fr):
    """A boolean mask on the edit map's pixels, as the found paths' 0.5 m grid."""
    k = ed['ppm'] * fr['res']
    h, w = round(mask.shape[0] / k), round(mask.shape[1] / k)
    small = np.array(Image.fromarray((mask * 255).astype(np.uint8)).resize((w, h), Image.BOX)) > 70
    out = np.zeros((fr['h'], fr['w']), bool)
    c0, r0 = round((ed['e0'] - fr['e0']) / fr['res']), round((fr['n1'] - ed['n1']) / fr['res'])
    hh, ww = min(h, fr['h'] - r0), min(w, fr['w'] - c0)
    out[r0:r0 + hh, c0:c0 + ww] = small[:hh, :ww]
    return out


NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def trace(sk, fr):
    """The skeleton as lines in metres: [(points, startNode, endNode)] and the node positions. A node is an end or a junction (nearby ones merged)."""
    res = fr['res']
    cnt = ndi.convolve(sk.astype(int), np.ones((3, 3), int), mode='constant') - 1
    nodes = sk & ((cnt == 1) | (cnt >= 3))
    nlab, nn = ndi.label(ndi.binary_dilation(nodes, structure=np.ones((3, 3)), iterations=2) & sk, structure=np.ones((3, 3)))
    cen = ndi.center_of_mass(sk, nlab, range(1, nn + 1))
    xy = lambda r, c: (fr['e0'] + (c + .5) * res, fr['n1'] - (r + .5) * res)
    npos = [xy(r, c) for r, c in cen]
    rest = sk & (nlab == 0)
    lab, n = ndi.label(rest, structure=np.ones((3, 3)))
    near = ndi.binary_dilation(nlab > 0, structure=np.ones((3, 3)), iterations=1)
    lines = []
    for i in range(1, n + 1):
        pix = set(zip(*np.nonzero(lab == i)))
        def nb(p):
            return [(p[0] + a, p[1] + b) for a, b in NB if (p[0] + a, p[1] + b) in pix]
        ends = [p for p in pix if len(nb(p)) <= 1]
        cur = ends[0] if ends else next(iter(pix))
        order, seen = [cur], {cur}
        while True:
            nxt = [q for q in nb(cur) if q not in seen]
            if not nxt:
                break
            cur = min(nxt, key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))   # straight steps before diagonal ones
            order.append(cur); seen.add(cur)
        pts = [xy(r, c) for r, c in order]
        def node_at(p):   # the node cluster touching this end of the line
            r, c = p; best = None
            for a in range(-2, 3):
                for b in range(-2, 3):
                    rr, cc = r + a, c + b
                    if 0 <= rr < nlab.shape[0] and 0 <= cc < nlab.shape[1] and nlab[rr, cc] and (best is None or a * a + b * b < best[0]):
                        best = (a * a + b * b, nlab[rr, cc] - 1)
            return best[1] if best else None
        lines.append((pts, node_at(order[0]), node_at(order[-1]) if len(order) > 1 else None))
    return lines, npos, near


def smooth_line(pts, step=.5, sigma=LINE_SIGMA):
    """Resample at `step` m and smooth along the line; the two ends stay where they are."""
    a = np.array(pts, float)
    if len(a) < 3:
        return a
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(a, axis=0).T))]
    if d[-1] < 2 * step:
        return a
    t = np.arange(0, d[-1], step); t = np.r_[t, d[-1]]
    r = np.c_[np.interp(t, d, a[:, 0]), np.interp(t, d, a[:, 1])]
    if len(r) < 4:
        return r
    k = min(int(3 * sigma / step) + 1, len(r) - 2)
    pad = lambda x: np.r_[2 * x[0] - x[1:k + 1][::-1], x, 2 * x[-1] - x[-k - 1:-1][::-1]]   # point-reflected, so the ends hold
    out = np.c_[gaussian_filter1d(pad(r[:, 0]), sigma / step)[k:-k], gaussian_filter1d(pad(r[:, 1]), sigma / step)[k:-k]]
    out[0], out[-1] = r[0], r[-1]
    return out


def pieces(lines):
    """The lines grouped into pieces that touch each other (as lists of indices)."""
    n = len(lines); par = list(range(n))
    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            if lines[i].distance(lines[j]) < .5:
                par[find(i)] = find(j)
    g = {}
    for i in range(n):
        g.setdefault(find(i), []).append(i)
    return list(g.values())


def bridge(a, b, pa, pb):
    """A smooth link from pa on line a to pb on line b: a curve leaving each line along its own direction if the point is its end, else straight."""
    def leave(line, p):
        c = list(line.coords)
        for end, nxt in ((c[0], c[min(3, len(c) - 1)]), (c[-1], c[max(-4, -len(c))])):
            if Point(end).distance(p) < 1.0:
                v = np.array(end) - np.array(nxt); n = np.hypot(*v)
                return v / n if n > 1e-6 else None
        return None
    d = np.hypot(pb.x - pa.x, pb.y - pa.y); A, B = np.array([pa.x, pa.y]), np.array([pb.x, pb.y])
    ta, tb = leave(a, pa), leave(b, pb)
    c1 = A + ta * d / 3 if ta is not None and ta @ (B - A) > 0 else A + (B - A) / 3
    c2 = B + tb * d / 3 if tb is not None and tb @ (A - B) > 0 else B + (A - B) / 3
    t = np.linspace(0, 1, 12)[:, None]
    pts = (1 - t) ** 3 * A + 3 * (1 - t) ** 2 * t * c1 + 3 * (1 - t) * t ** 2 * c2 + t ** 3 * B
    return LineString(pts)


def main():
    fr = json.load(open(os.path.join(OUT, 'cartpaths_found.json')))
    cen = np.array(Image.open(os.path.join(OUT, 'cartpaths_found.png'))) > 0
    # python cartpaths_read.py [mask.png] [--full]: another mask file (a copy of out/cartpaths_mask_2.png, say); --full means its RED is the whole network, not additions to the found paths
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    full = '--full' in sys.argv
    mp = os.path.join(OUT, args[0]) if args else os.path.join(OUT, 'cartpaths_mask.png')
    if full:
        cen = np.zeros_like(cen)
    if os.path.exists(mp):
        ed = json.load(open(os.path.join(OUT, 'cartpaths_edit.json')))
        a = np.array(Image.open(mp).convert('RGB')).astype(int)
        assert a.shape[1] == ed['w'] and a.shape[0] == ed['h'], 'the mask must have the edit map\'s size'
        red = coarse(np.abs(a - np.array(RED)).max(2) <= 40, ed, fr)
        blue = coarse(np.abs(a - np.array(BLUE)).max(2) <= 40, ed, fr)
        cen = cen & ~ndi.binary_dilation(blue, iterations=1)
        cen |= skeletonize(ndi.binary_closing(red, iterations=1))
        print(f'mask read: {int(red.sum() * fr["res"] ** 2)} m2 of red, {int(blue.sum() * fr["res"] ** 2)} m2 of blue')
    write_network(cen, fr)


def write_network(cen, fr):
    """The thin centre-line mask `cen` on the grid `fr` as smoothed path lines, gaps closed, drawn PATH_W wide; writes out/cartpaths.json
    and out/cartpaths_links.json (also used by all_read.py)."""
    # join what the painting touched into one thin network, drop bits shorter than 6 m, then widen to the path width
    cen = skeletonize(ndi.binary_closing(band(cen, fr['res'], 1.2), iterations=1))
    lab, n = ndi.label(cen, structure=np.ones((3, 3)))
    size = ndi.sum(cen, lab, range(1, n + 1))
    cen = np.isin(lab, [i + 1 for i, s in enumerate(size) if s * fr['res'] >= 6])
    lines, npos, _ = trace(cen, fr)
    deg = {}
    for pts, a0, a1 in lines:
        for q in (a0, a1):
            if q is not None:
                deg[q] = deg.get(q, 0) + 1
    out = []
    for pts, a0, a1 in lines:
        a = np.array(pts, float)
        ln = float(np.hypot(*np.diff(a, axis=0).T).sum()) if len(a) > 1 else 0
        stub = (a0 is None or a1 is None or deg.get(a0, 0) == 1 or deg.get(a1, 0) == 1) and ln < SPUR   # a short dead end: a spur of the skeleton
        if stub:
            continue
        if a0 is not None:
            a = np.vstack([npos[a0], a])   # the line starts and ends exactly on its junction
        if a1 is not None:
            a = np.vstack([a, npos[a1]])
        out.append(LineString(smooth_line(a)))
    # close the small gaps between pieces (shortest first), then drop what is still a short piece on its own
    links = []   # where a gap was closed: x, y, centre-line length
    while True:
        pcs = pieces(out)
        if len(pcs) < 2:
            break
        best = None
        for x in range(len(pcs)):
            ux = unary_union([out[i] for i in pcs[x]])
            for y in range(x + 1, len(pcs)):
                uy = unary_union([out[i] for i in pcs[y]]); d = ux.distance(uy)
                if best is None or d < best[0]:
                    best = (d, pcs[x], pcs[y], ux, uy)
        if best[0] > BRIDGE:
            break
        d, ia, ib, ux, uy = best
        pa, pb = nearest_points(ux, uy)
        la = min((out[i] for i in ia), key=lambda l: l.distance(pa)); lb = min((out[i] for i in ib), key=lambda l: l.distance(pb))
        out.append(bridge(la, lb, pa, pb)); links.append([round((pa.x + pb.x) / 2, 1), round((pa.y + pb.y) / 2, 1), round(d + PATH_W, 1)])
    pcs = pieces(out)
    keep = [i for pc in pcs for i in pc if len(pcs) == 1 or sum(out[k].length for k in pc) >= MIN_PIECE]
    print(f'{len(out) - len(keep)} lines dropped as short pieces on their own')
    out = [out[i] for i in keep]
    pcs = pieces(out)
    print(len(pcs), 'pieces left:')
    for pc in sorted(pcs, key=lambda pc: -sum(out[k].length for k in pc)):
        u = unary_union([out[k] for k in pc]); others = [unary_union([out[k] for k in o]) for o in pcs if o is not pc]
        c = u.centroid
        print(f'  {sum(out[k].length for k in pc):6.0f} m at E{c.x:.0f} N{c.y:.0f}, nearest other piece {min(u.distance(o) for o in others):.0f} m' if others else f'  {sum(out[k].length for k in pc):6.0f} m (all of it)')
    w = PATH_W / 2
    polys = []
    for g in getattr(unary_union([l.buffer(w, resolution=6) for l in out]).simplify(TOL), 'geoms', None) or [unary_union([l.buffer(w, resolution=6) for l in out]).simplify(TOL)]:
        polys.append(g)
    json.dump(links, open(os.path.join(OUT, 'cartpaths_links.json'), 'w'))
    json.dump([mapping(p) for p in polys], open(os.path.join(OUT, 'cartpaths.json'), 'w'))
    print(len(out), 'lines,', len(polys), 'path areas,', int(sum(p.area for p in polys)), 'm2 (about', int(sum(l.length for l in out)), 'm of path),', sum(len(p.exterior.coords) + sum(len(r.coords) for r in p.interiors) for p in polys), 'vertices')


if __name__ == '__main__':
    main()
