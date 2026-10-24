#!/usr/bin/env python3
"""Rebuild the per-player files the leaderboard workflow keeps up to date, from the rounds themselves.

  stats.py [P001 P002 ...]   (no IDs: every player with rounds)

Reads rounds/<id>/<year>.json (a player's rounds, one file per UTC year, each {course, at, strokes, toPar, hs}) and writes stats/<id>.json, the
lifetime summary the game's Stats screen reads: per course the rounds played, the best round, and for each hole
[rounds, strokes, putts, fairways hit, fairway chances, greens hit, green chances, penalties, best score].
A flat rounds/<id>.json from before the year split is moved into the year files first. The workflow adds each new round to the same files
(one line of arithmetic per hole), so this is only for repairing or checking them."""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
ROUNDS, STATS = os.path.join(ROOT, 'rounds'), os.path.join(ROOT, 'stats')


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
        f.write('\n')


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
        co = st['courses'].setdefault(r['course'], {'rounds': 0, 'best': None, 'holes': [[0, 0, 0, 0, 0, 0, 0, 0, 99] for _ in r['hs']]})
        for a, h in zip(co['holes'], r['hs']):
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
        co['rounds'] += 1
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


def main(argv):
    ids = argv or sorted({os.path.splitext(f)[0] for f in os.listdir(ROUNDS)}) if os.path.isdir(ROUNDS) else []
    for pid in ids:
        rebuild(pid)


if __name__ == '__main__':
    main(sys.argv[1:])
