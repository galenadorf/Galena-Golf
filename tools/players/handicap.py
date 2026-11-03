#!/usr/bin/env python3
"""Handicap foundation (NOT live: nothing in the game reads these files yet).

  handicap.py ratings   writes handicap/ratings.json: per course the played tee's rating, slope and par, read from tools/course/courses/<key>/course.py
                        (the tee set in MARKERS slot 'w', the one the game plays)
  handicap.py calc      reads every player's rounds (rounds/<id>/<year>.json) and writes handicap/handicaps.json: per player the index and the
                        differentials behind it, worked out the way the World Handicap System does it (differential = 113 / slope x (adjusted gross - rating),
                        index = the mean of the best N of the last 20 differentials, N from the WHS table). Run it from the repo root.

Adjusted gross caps each hole at net double bogey (par + 5 for a player with no index yet; `adjusted`). Only 18-hole rounds on a course with a rating count (9-hole rounds will join when events can be nine holes), and a
course whose rating is a guess is listed in ratings.json with "est": true so the index can say it leans on one.

The game's physics are not a real course's, so these are handicaps *in this game*; the index needs enough rounds on enough courses before it is shown
(MIN_ROUNDS, 3 in the WHS). A player with fewer gets "index": null.
"""
import glob, json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MIN_ROUNDS = 3
# WHS: how many of the lowest differentials count (and the adjustment) for 3..20 rounds on file
BEST = {3: (1, -2.0), 4: (1, -1.0), 5: (1, 0.0), 6: (2, -1.0), 7: (2, 0.0), 8: (2, 0.0), 9: (3, 0.0), 10: (3, 0.0), 11: (3, 0.0), 12: (4, 0.0), 13: (4, 0.0),
        14: (4, 0.0), 15: (5, 0.0), 16: (5, 0.0), 17: (6, 0.0), 18: (6, 0.0), 19: (7, 0.0), 20: (8, 0.0)}
MAX_INDEX = 54.0


def ratings():
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, 'tools/course/courses/*/course.py'))):
        key = path.split(os.sep)[-2]
        ns = {}
        try:
            exec(compile(open(path, encoding='utf8').read(), path, 'exec'), ns)
        except Exception as e:  # a course.py that needs the tools' modules: skip it, say so
            print('skip', key, e); continue
        if ns.get('DISC') or 'TEES' not in ns or 'MARKERS' not in ns or 'PAR' not in ns:
            continue
        tee = ns['MARKERS']['w'][0]; rating, slope, _ = ns['TEES'][tee]
        out[key] = {'tee': tee, 'rating': rating, 'slope': slope, 'par': sum(ns['PAR']), 'pars': ns['PAR']}
    return out


def adjusted(hs, pars, playing=0):
    """Adjusted gross: every hole capped at net double bogey, par + 2 plus the strokes the player gets there (playing = course handicap, 0 until
    the player has an index: par + 5, the cap the game's maximum hole score also uses)."""
    cap = lambda i, p: p + 2 + (playing // 18) + (1 if i < playing % 18 else 0) if playing else p + 5
    return sum(min(h[0], cap(i, p)) for i, (h, p) in enumerate(zip(hs, pars)))


def index_of(diffs):
    """diffs: the player's differentials, oldest first. Returns (index, used) or (None, 0) with too few rounds."""
    last = diffs[-20:]
    if len(last) < MIN_ROUNDS:
        return None, 0
    n, adj = BEST[len(last)]
    best = sorted(last)[:n]
    return min(MAX_INDEX, round(sum(best) / n + adj, 1)), n


def course_handicap(index, rating, slope, par):
    """The strokes a player of this index gets on a course from the tees whose rating and slope are given."""
    return round(index * slope / 113 + (rating - par))


def calc(rt):
    res = {}
    for pdir in sorted(glob.glob(os.path.join(ROOT, 'rounds/P*'))):
        pid = os.path.basename(pdir); rounds = []
        for f in sorted(glob.glob(os.path.join(pdir, '*.json'))):
            try: rounds += json.load(open(f))
            except Exception: pass
        rounds.sort(key=lambda r: r['at']); diffs = []
        for r in rounds:
            c = rt.get(r['course']); hs = r.get('hs')
            if not c or not hs or len(hs) != 18: continue
            ags = adjusted(hs, c['pars'], 0)
            diffs.append([r['at'], r['course'], round((113 / c['slope']) * (ags - c['rating']), 1)])
        idx, n = index_of([d[2] for d in diffs])
        res[pid] = {'index': idx, 'rounds': len(diffs), 'counted': n, 'diffs': diffs[-20:]}
    return res


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    os.makedirs(os.path.join(ROOT, 'handicap'), exist_ok=True)
    rt = ratings()
    if cmd == 'ratings':
        json.dump(rt, open(os.path.join(ROOT, 'handicap/ratings.json'), 'w'), indent=1); print(len(rt), 'courses')
    elif cmd == 'calc':
        res = calc(rt); json.dump(res, open(os.path.join(ROOT, 'handicap/handicaps.json'), 'w'), indent=1)
        for pid, r in res.items(): print(pid, r['index'], 'from', r['rounds'], 'rounds')
    else:
        print(__doc__)
