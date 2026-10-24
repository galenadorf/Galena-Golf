"""Builds the Galena crest logo, brand/galena-crest.svg, from the scan of the embroidered 1826-1976 Galena patch (the years on the logo are 2007-2026) (brand/source/Galena_crest.png).
The shield, border, stars, Greek letters (Pi Kappa Phi) in the middle of the star cluster, two blue shields, red diamond, golf ball on its tee, putter, bat, hot dog and bacon are drawn here as clean shapes (positions measured on the
scan, mirrored about x = 197); the lettering and the years are set in DejaVu Serif Bold (free licence) converted to outlines, so the SVG needs no font: GALENA!!! letter by letter
along the shield's V, tilted to follow it. Everything is flat colour on a transparent background.
Usage: python crest_vector.py   Needs fontTools (pip install --target <dir> fonttools; put <dir> in PYTHONPATH) and the DejaVu Serif Bold file."""
import math
import os
import warnings

warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, 'brand', 'galena-crest.svg')
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'
GOLD, RED, BLUE, WHITE, EDGE = '#f2a50c', '#c8102e', '#1c3fae', '#ffffff', '#d98900'
CX = 197.0                    # the crest's centre line


def mirror(pts):
    return [(2 * CX - x, y) for x, y in pts]


def poly(pts, r=0):
    """a closed polygon path with its corners rounded by r"""
    n = len(pts); d = []
    for i, p in enumerate(pts):
        a, b, c = pts[i - 1], p, pts[(i + 1) % n]
        if r <= 0:
            d.append(('M' if i == 0 else 'L') + f'{b[0]:.1f} {b[1]:.1f}'); continue
        va = (a[0] - b[0], a[1] - b[1]); vc = (c[0] - b[0], c[1] - b[1]); la = math.hypot(*va); lc = math.hypot(*vc)
        t = min(r, la / 2.2, lc / 2.2); p1 = (b[0] + va[0] / la * t, b[1] + va[1] / la * t); p2 = (b[0] + vc[0] / lc * t, b[1] + vc[1] / lc * t)
        d.append(('M' if i == 0 else 'L') + f'{p1[0]:.1f} {p1[1]:.1f}Q{b[0]:.1f} {b[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}')
    return ''.join(d) + 'Z'


def star(cx, cy, R, rot=0):
    pts = []
    for i in range(10):
        a = math.radians(-90 + rot + i * 36); r = R if i % 2 == 0 else R * .5
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return poly(pts, .6)


_F = []


def font():
    from fontTools.ttLib import TTFont
    if not _F:
        f = TTFont(FONT); _F.append((f, f.getGlyphSet(), f.getBestCmap(), f['glyf']['H'].yMax))   # the cap height is the height of an H
    return _F[0]


def glyphs(letters):
    """outlines of text in DejaVu Serif Bold. letters: list of (char, cx, baseline_y, tilt_deg, cap, sx); each letter is drawn upright, then tilted about
    the middle of its baseline."""
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    f, gs, cm, cap0 = font(); out = []
    for ch, cx, by, tilt, cap, sx in letters:
        g = cm[ord(ch)]; adv = f['hmtx'][g][0]; sc = cap / cap0
        th = math.radians(tilt); c, s_ = math.cos(th), math.sin(th)
        # glyph -> upright (x*sc*sx - adv/2*sc*sx, -y*sc) -> rotate about the origin -> move to (cx, by)
        a_, d_ = sc * sx, -sc
        e = cx - (adv / 2 * a_) * c; f_ = by - (adv / 2 * a_) * s_
        pen = SVGPathPen(gs, ntos=lambda v: f'{v:.1f}'); gs[g].draw(TransformPen(pen, (c * a_, s_ * a_, -s_ * d_, c * d_, e, f_))); out.append(pen.getCommands())
    return ''.join(out)


def adv_of(ch, cap, sx=1):
    f, gs, cm, cap0 = font(); return f['hmtx'][cm[ord(ch)]][0] * cap / cap0 * sx


def wordmark():
    """GALENA!!! along the V: left-to-right in order, centres spaced by their advances, each tilted by how steeply the V falls there"""
    word, cap, gap = 'GALENA!!!', 36, 4
    adv = [adv_of(c, cap) for c in word]; total = sum(adv) + gap * (len(word) - 1); x = 197 - total / 2 - 2; L = []
    for ch, a in zip(word, adv):
        cx = x + a / 2; k = max(-1, min(1, (197 - cx) / 75)); tilt = 21 * k
        by = 338 - .40 * max(0, abs(cx - 197) - 24)
        L.append((ch, cx, by, tilt, cap + (4 if ch in 'LE' else 0), 1)); x += a + gap
    return glyphs(L)


def years(text, x, by, cap, width):
    a = [adv_of(c, cap) for c in text]; sx = min(1, width / sum(a)); L = []; cx = x
    for ch, w in zip(text, a):
        L.append((ch, cx + w * sx / 2, by, 0, cap, sx)); cx += w * sx
    return glyphs(L)


def golf_ball():
    """the red diamond's emblem: a white golf ball with dimples, on a gold tee"""
    bx, by, r = 197, 229, 25
    d = []
    for row in range(-5, 6):
        for col in range(-6, 7):
            x = bx + col * 7.2 + (3.6 if row % 2 else 0); y = by + row * 6.3
            if math.hypot(x - bx, y - by) < r - 3:
                d.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.9"/>')
    tee = poly([(189.5, by + r - 1), (204.5, by + r - 1), (199.5, by + r + 6), (198.5, by + r + 17), (197, by + r + 21), (195.5, by + r + 17), (194.5, by + r + 6)], .8)
    return (f'<path d="{tee}" fill="{GOLD}"/><circle cx="{bx}" cy="{by}" r="{r}" fill="{WHITE}"/>'
            f'<g fill="#d5dae8">' + ''.join(d) + '</g>'
            f'<circle cx="{bx}" cy="{by}" r="{r}" fill="none" stroke="#ffffff" stroke-width="1.2"/>')


def bat(bs, be):
    """a white baseball bat from its knob at bs to the end of its barrel at be"""
    dx, dy = be[0] - bs[0], be[1] - bs[1]; bl = math.hypot(dx, dy); ba = math.degrees(math.atan2(dy, dx))
    shape = poly([(0, -1.6), (bl * .55, -1.9), (bl * .86, -4.4), (bl, -4.6), (bl, 4.6), (bl * .86, 4.4), (bl * .55, 1.9), (0, 1.6)], 2.2)
    return f'<g transform="translate({bs[0]} {bs[1]}) rotate({ba:.1f})"><path d="{shape}" fill="{WHITE}"/><circle cx="-1" cy="0" r="3.6" fill="{WHITE}"/></g>'


def putter_and_bat():
    """left shield: a golf putter (grip upper left, head lower right) crossed with a baseball bat (knob lower left, barrel upper right)"""
    g, e = (104, 150), (150, 190)                                   # the club: grip end and the foot of the shaft
    ux, uy = e[0] - g[0], e[1] - g[1]; n = math.hypot(ux, uy); ux, uy = ux / n, uy / n; px, py = uy, -ux   # along the shaft; towards the toe (up and right)
    def at(a, b):
        return f'{e[0] + a * ux + b * px:.1f} {e[1] + a * uy + b * py:.1f}'
    head = poly([tuple(map(float, at(a, b).split())) for a, b in ((-2.5, -4), (5.5, -4), (5.5, 20), (-2.5, 20))], 1.6)   # a putter: a long, thin blade, the shaft joining near the heel
    grip = (g[0] + ux * 13, g[1] + uy * 13)
    o = [bat((98, 208), (144, 156)),
         f'<g stroke="{WHITE}" stroke-linecap="round" stroke-linejoin="round" fill="none">',
         f'<path d="M{g[0]} {g[1]}L{e[0] - ux * 2:.1f} {e[1] - uy * 2:.1f}" stroke-width="2.8"/>',
         f'<path d="M{g[0] - ux * 2:.1f} {g[1] - uy * 2:.1f}L{grip[0]:.1f} {grip[1]:.1f}" stroke-width="5.6"/>',
         f'<path d="{head}" fill="{WHITE}" stroke-width="1.2"/>',
         f'<path d="M{at(-1, 9)}L{at(4.2, 9)}" stroke="{BLUE}" stroke-width="1.3"/>',   # the sight line
         '</g>']
    return ''.join(o)


def bacon(bs, be):
    """a slice of cooked bacon: a wavy red strip with two pale streaks of fat, edged in white"""
    dx, dy = be[0] - bs[0], be[1] - bs[1]; L = math.hypot(dx, dy); ang = math.degrees(math.atan2(dy, dx))
    lam, amp, hw = 17.0, 2.1, 6.4
    xs = [i * 2.0 for i in range(int(L / 2) + 1)] + [L]
    top = [(x, -hw + amp * math.sin(2 * math.pi * x / lam)) for x in xs]
    bot = [(x, hw + amp * math.sin(2 * math.pi * x / lam + .9)) for x in reversed(xs)]
    d = 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in top + bot) + 'Z'
    streak = lambda off: 'M' + 'L'.join(f'{x:.1f} {off + amp * math.sin(2 * math.pi * x / lam + .45):.1f}' for x in xs[2:-2])
    return (f'<g transform="translate({bs[0]} {bs[1]}) rotate({ang:.1f})"><path d="{d}" fill="{RED}" stroke="{WHITE}" stroke-width="1.5" stroke-linejoin="round"/>'
            f'<path d="{streak(-2.3)}" fill="none" stroke="#f7d9cf" stroke-width="2" stroke-linecap="round"/>'
            f'<path d="{streak(2.3)}" fill="none" stroke="#f7d9cf" stroke-width="2" stroke-linecap="round"/></g>')


def dog_and_bacon():
    """right shield: a slice of bacon (lower left to upper right) crossed with a hot dog (bun, sausage and mustard) from upper left to lower right"""
    hs, he = (240, 161), (299, 206); dx, dy = he[0] - hs[0], he[1] - hs[1]; hl = math.hypot(dx, dy); ha = math.degrees(math.atan2(dy, dx))
    zig = 'M' + 'L'.join(f'{hl * .16 + i * (hl * .68 / 10):.1f} {(-1.6 if i % 2 else 1.6):.1f}' for i in range(11))
    return (bacon((248, 205), (288, 147)) +
            f'<g transform="translate({hs[0]} {hs[1]}) rotate({ha:.1f})">'
            f'<rect x="0" y="-7.5" width="{hl:.1f}" height="15" rx="7.5" fill="{WHITE}"/>'
            f'<rect x="-3.5" y="-3.6" width="{hl + 7:.1f}" height="7.2" rx="3.6" fill="{RED}" stroke="{WHITE}" stroke-width="1.1"/>'
            f'<path d="{zig}" fill="none" stroke="{GOLD}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></g>')


def main():
    outer = [(10, 8), (384, 8), (384, 288), (197, 394), (10, 288)]
    inset = 14
    inner = [(10 + inset, 8 + inset), (384 - inset, 8 + inset), (384 - inset, 288 - inset * .1), (197, 394 - inset * 1.75), (10 + inset, 288 - inset * .1)]
    L = [(103, 118), (195, 174), (118, 240), (79, 213)]            # the left blue shield; the right one is its mirror
    R = mirror(L)
    diamond = [(197, 176), (116, 241), (197, 281), (278, 241)]
    left = [(112, 101), (146, 88), (133, 123), (163, 113)]   # four on each side of the letters: an upper arc and a lower row, mirrored
    stars = [(x, y, 14.5) for x, y in left + mirror(left)]
    o = []
    A = o.append
    A(f'<path d="{poly(outer, 14)}" fill="{GOLD}"/>')
    A(f'<path d="{poly(inner, 9)}" fill="{WHITE}" stroke="{EDGE}" stroke-width="1.2"/>')
    A(f'<path d="{poly(diamond, 3)}" fill="{RED}"/>')
    A(f'<path d="{poly(L, 9)}" fill="{BLUE}"/><path d="{poly(R, 9)}" fill="{BLUE}"/>')
    # stars: a white halo cuts them clear of the shields, like the white stitching of the patch
    A(f'<g fill="{BLUE}" stroke="{WHITE}" stroke-width="3" stroke-linejoin="round" paint-order="stroke">' + ''.join(f'<path d="{star(*s)}"/>' for s in stars) + '</g>')
    # the middle column of the star cluster: Pi, Kappa, Phi, top to bottom, in the stars' blue with the same white halo
    A(f'<path d="{glyphs([(c, 198, y + 14.5, 0, 29, 1) for c, y in zip("\u03a0\u039a\u03a6", (72, 109, 146))])}" fill="{BLUE}" stroke="{WHITE}" stroke-width="3" stroke-linejoin="round" paint-order="stroke"/>')
    A(golf_ball())
    # a golf putter and a baseball bat crossed on the left shield; a hot dog and a slice of bacon on the right
    A(putter_and_bat())
    A(dog_and_bacon())
    # lettering and years
    A(f'<path d="{wordmark()}" fill="{RED}"/>')
    wr = sum(adv_of(c, 32) for c in '2026')   # the years sit level, mirrored about the centre line
    A(f'<path d="{years("2007", 50, 77, 32, 90)}" fill="{RED}"/><path d="{years("2026", 2 * CX - 50 - min(wr, 90), 77, 32, 90)}" fill="{RED}"/>')
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 394 402" role="img" aria-label="Galena 2007-2026 crest">\n' + '\n'.join(o) + '\n</svg>\n'
    open(OUT, 'w').write(svg)
    print(OUT, f'{len(svg) / 1024:.0f} KB')


if __name__ == '__main__':
    main()
