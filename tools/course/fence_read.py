"""The hand-painted fence lines (all_edit.PALETTE 'fence', brown #804000) as smooth lines in local metres, and the out-of-bounds boundary they make.

A fence is the property line where houses line a hole: out of bounds is on the house side. `lines_from_mask` thins the painted lines (skeleton), traces them,
joins touching ones and smooths them (the cart-path tracer's own); `apply` cuts the boundary back to them: each line gets the strip behind it (the side with
more building area within SIDE_PROBE m; FENCE_REACH m deep, flat ends) cut from the course outline, but never anything mown, teed or green (a fence painted across
play is a mistake, reported) and never past the course outline's own edge. Writes out/fence_lines.json; build.py reads it (and `HOUSE_LOTS` is then not used)."""
import numpy as np
from scipy import ndimage as ndi
from shapely.geometry import LineString
from shapely.ops import linemerge, unary_union
from skimage.morphology import skeletonize

from cartpaths_read import smooth_line, trace

SIDE_PROBE, FENCE_REACH, MIN_LEN = 35.0, 90.0, 6.0


def lines_from_mask(m, fr):
    sk = skeletonize(ndi.binary_closing(m, iterations=2))
    lab, n = ndi.label(sk, structure=np.ones((3, 3)))
    size = ndi.sum(sk, lab, range(1, n + 1))
    sk = np.isin(lab, [i + 1 for i, s in enumerate(size) if s * fr['res'] >= MIN_LEN])
    lines, npos, _ = trace(sk, fr)
    out = []
    for pts, a0, a1 in lines:
        a = np.array(pts, float)
        if a0 is not None:
            a = np.vstack([npos[a0], a])
        if a1 is not None:
            a = np.vstack([a, npos[a1]])
        if len(a) >= 2:
            out.append(LineString(smooth_line(a, sigma=2.0)))
    merged = linemerge(out)
    res = [g for g in getattr(merged, 'geoms', [merged]) if g.length >= MIN_LEN]
    return res


def side_cut(line, houses):
    """The strip of ground behind `line` (the house side), FENCE_REACH deep."""
    best = None
    for sgn in (1, -1):
        probe = line.buffer(sgn * SIDE_PROBE, single_sided=True, cap_style=2)
        a = probe.intersection(houses).area if houses is not None else 0
        if best is None or a > best[0]:
            best = (a, sgn)
    return line.buffer(best[1] * FENCE_REACH, single_sided=True, cap_style=2)


def apply(bound, lines, houses, play):
    cuts = [side_cut(L, houses) for L in lines]
    cut = unary_union(cuts).difference(play)
    nb = bound.difference(cut)
    nb = max(getattr(nb, 'geoms', [nb]), key=lambda g: g.area)
    nb = nb.buffer(-1.0, quad_segs=6).buffer(1.0, quad_segs=6)
    return max(getattr(nb, 'geoms', [nb]), key=lambda g: g.area)

