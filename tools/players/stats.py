#!/usr/bin/env python3
"""Rebuild the per-player files the leaderboard workflow keeps up to date, from the rounds themselves.

  stats.py [P001 P002 ...]            rebuild the summaries (no IDs: every player with rounds)
  stats.py --backfill [P001 ...]      first file the rounds on the leaderboard (leaderboard/<course>.json) that a player's year files lack,
                                      with hs null (they were played before holes were recorded), then rebuild

Records: each course's summary also carries `rec` (key -> [value, hole, at]), the player's best marks from their full rounds, and records/<course>.json holds the
best 5 players of each (rebuilt from every stats file at the end). Keys: drive, holed, putt (decimetres, from the round's `x`), roundPutts, bestNine (lowest is best),
mostPutts, lips (lipped-out putts, from x.l), birdies, birdStreak, gir, girStreak, fairways, fwStreak (highest is best). Same rules as the workflow.

Reads rounds/<id>/<year>.json (a player's rounds, one file per UTC year, each {course, at, strokes, toPar, hs}) and writes stats/<id>.json, the
lifetime summary the game's Stats screen reads: per course the rounds played, the best round, and for each hole
[rounds, strokes, putts, fairways hit, fairway chances, greens hit, green chances, penalties, best score, histogram of strokes 1..9 and 10+].
A round with hs null counts as a round (and for the best round) but adds nothing to the per-hole totals. A flat rounds/<id>.json from before the year split is moved into the year files first. The workflow adds each new round to the same files
(one line of arithmetic per hole), so this is only for repairing or checking them."""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
ROUNDS, STATS = os.path.join(ROOT, 'rounds'), os.path.join(ROOT, 'stats')
HOLES = 18
PARS = {'woodbine': [4, 3, 4, 5, 4, 4, 3, 4, 5, 4, 3, 4, 4, 4, 3, 5, 4, 5]}   # keep in step with the workflow and the course
LOW = {'roundPutts', 'bestNine'}
REC_FROM = 1793059200000   # records count from 2026-10-27 on (the day they started); earlier rounds are not scanned for them


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
        f.write('\n')


def run(hs, f):
    best = c = 0
    for i, h in enumerate(hs):
        q = f(h, i)
        if q is None:
            continue
        c = c + 1 if q else 0
        best = max(best, c)
    return best


def marks(r):
    """The round's record candidates: key -> (value, hole); only values above 0 count. Rounds without per-hole data have none."""
    hs, par = r.get('hs'), PARS.get(r['course'])
    if not hs or not par or len(hs) != HOLES or r['at'] < REC_FROM:
        return {}
    front, back = sum(h[0] for h in hs[:9]), sum(h[0] for h in hs[9:])
    c = {'roundPutts': (sum(h[1] for h in hs), 0), 'mostPutts': (sum(h[1] for h in hs), 0), 'lips': ((r.get('x') or {}).get('l', 0), 0), 'bestNine': (min(front, back), 1 if front <= back else 10),
         'birdies': (sum(1 for i, h in enumerate(hs) if h[0] < par[i]), 0), 'birdStreak': (run(hs, lambda h, i: h[0] < par[i]), 0),
         'gir': (sum(1 for h in hs if h[3] == 1), 0), 'girStreak': (run(hs, lambda h, i: h[3] == 1), 0),
         'fairways': (sum(1 for h in hs if h[2] == 1), 0), 'fwStreak': (run(hs, lambda h, i: (h[2] == 1) if par[i] >= 4 else None), 0)}
    for k, key in (('d', 'drive'), ('h', 'holed'), ('p', 'putt')):
        if (r.get('x') or {}).get(k):
            c[key] = tuple(r['x'][k])
    return {k: v for k, v in c.items() if v[0] > 0}


def migrate(pid):
    flat = os.path.join(ROUNDS, pid + '.json')
    if not os.path.isfile(flat):
        return
    by = defaultdict(list)
    for r in json.load(open(flat)):
        by[datetime.fromtimestamp(r['at'] / 1000, timezone.utc).year].append(r)
    for y, rs in by.items():
        dump(os.path.join(ROUNDS, pid, f'{y}.json'), sorted(rs, key=lambda r: r['at']))
    os.remove(flat)
    print('split', flat, 'into', sorted(by))


def backfill(pid):
    """File the leaderboard's rounds for this player that the year files lack (rounds played before per-hole data was recorded)."""
    lb = os.path.join(ROOT, 'leaderboard')
    have = set()
    d = os.path.join(ROUNDS, pid)
    for fn in os.listdir(d) if os.path.isdir(d) else []:
        have |= {r['at'] for r in json.load(open(os.path.join(d, fn)))}
    added = defaultdict(list)
    for fn in sorted(os.listdir(lb)) if os.path.isdir(lb) else []:
        for x in json.load(open(os.path.join(lb, fn))):
            if x.get('pid') == pid and x['at'] not in have:
                y = datetime.fromtimestamp(x['at'] / 1000, timezone.utc).year
                added[y].append({'course': os.path.splitext(fn)[0], 'at': x['at'], 'strokes': x['strokes'], 'toPar': x['toPar'], 'hs': None})
                have.add(x['at'])
    for y, rs in added.items():
        path = os.path.join(ROUNDS, pid, f'{y}.json')
        old = json.load(open(path)) if os.path.isfile(path) else []
        dump(path, sorted(old + rs, key=lambda r: r['at']))
    if added:
        print(pid, 'backfilled', sum(len(v) for v in added.values()), 'rounds')


def rebuild(pid):
    migrate(pid)
    rounds = []
    d = os.path.join(ROUNDS, pid)
    for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if fn.endswith('.json'):
            rounds += json.load(open(os.path.join(d, fn)))
    if not rounds:
        return
    rounds.sort(key=lambda r: r['at'])
    st = {'v': 1, 'pid': pid, 'rounds': 0, 'first': rounds[0]['at'], 'last': rounds[0]['at'], 'years': [], 'courses': {}}
    for r in rounds:
        co = st['courses'].setdefault(r['course'], {'rounds': 0, 'best': None, 'holes': [[0, 0, 0, 0, 0, 0, 0, 0, 99, [0] * 10] for _ in range(HOLES)]})
        for a, h in zip(co['holes'], r.get('hs') or []):
            a[0] += 1
            a[1] += h[0]
            a[2] += h[1]
            if h[2] >= 0:
                a[3] += h[2]
                a[4] += 1
            if h[3] >= 0:
                a[5] += h[3]
                a[6] += 1
            a[7] += h[4]
            a[8] = min(a[8], h[0])
            a[9][min(h[0], 10) - 1] += 1
        co['rounds'] += 1
        rec = co.setdefault('rec', {})
        for k, (v, hole) in marks(r).items():
            cur = rec.get(k)
            if cur is None or (v < cur[0] if k in LOW else v > cur[0]):
                rec[k] = [v, hole, r['at']]
        if co['best'] is None or r['strokes'] < co['best']['strokes']:
            co['best'] = {'strokes': r['strokes'], 'at': r['at']}
        st['rounds'] += 1
        st['first'] = min(st['first'], r['at'])
        st['last'] = max(st['last'], r['at'])
        y = datetime.fromtimestamp(r['at'] / 1000, timezone.utc).year
        if y not in st['years']:
            st['years'] = sorted(st['years'] + [y])
    dump(os.path.join(STATS, pid + '.json'), st)
    print(pid, st['rounds'], 'rounds ->', os.path.join('stats', pid + '.json'))


def rebuild_records():
    """records/<course>.json: the best 5 players of each record, from every player's stats file."""
    names = {}
    try:
        names = {p['id']: p['name'] for p in json.load(open(os.path.join(ROOT, 'players.json')))}
    except (OSError, ValueError):
        pass
    per = defaultdict(lambda: defaultdict(list))
    for fn in sorted(os.listdir(STATS)) if os.path.isdir(STATS) else []:
        st = json.load(open(os.path.join(STATS, fn)))
        for course, co in st.get('courses', {}).items():
            for k, (v, hole, at) in (co.get('rec') or {}).items():
                per[course][k].append({'pid': st['pid'], 'name': names.get(st['pid'], st['pid']), 'v': v, 'hole': hole, 'at': at})
    for course, recs in per.items():
        out = {k: sorted(l, key=lambda x: ((x['v'] if k in LOW else -x['v']), x['at']))[:5] for k, l in recs.items()}
        dump(os.path.join(ROOT, 'records', course + '.json'), {'v': 1, 'rec': out})
        print('records/' + course + '.json:', len(out), 'records')


def main(argv):
    bf = '--backfill' in argv
    ids = [a for a in argv if a != '--backfill']
    if not ids:
        names = set(os.listdir(ROUNDS)) if os.path.isdir(ROUNDS) else set()
        if bf:
            lb = os.path.join(ROOT, 'leaderboard')
            names |= {x['pid'] for fn in os.listdir(lb) for x in json.load(open(os.path.join(lb, fn))) if x.get('pid')}
        ids = sorted({os.path.splitext(f)[0] for f in names})
    for pid in ids:
        migrate(pid)
        if bf:
            backfill(pid)
        rebuild(pid)
    rebuild_records()


if __name__ == '__main__':
    main(sys.argv[1:])
