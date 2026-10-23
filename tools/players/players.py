#!/usr/bin/env python3
"""Player roster admin: edits players.json at the repo root (the only place player IDs and device keys live).

  players.py add "Kalle" GG1-...          new player, next free ID (P001, P002, ...), first device from an ID request
  players.py device P007 GG1-... [label]  another device for that player (label defaults to the one in the request)
  players.py drop P007 <label|key prefix> remove one device (a lost phone); that device becomes a guest
  players.py rename P007 "New Name"
  players.py list

A player makes an ID request in the game (Settings > Player ID > Copy ID request) and sends you the code (GG1-...). Commit and push
players.json afterwards; the game picks it up from GitHub within a few minutes (Settings > Player ID > Check now)."""
import base64
import json
import os
import re
import sys

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'players.json')
SPKI = bytes.fromhex('3059301306072a8648ce3d020106082a8648ce3d030107034200')  # DER header of a P-256 public key; 65 key bytes follow


def load():
    try:
        return json.load(open(PATH))
    except FileNotFoundError:
        return []


def save(a):
    with open(PATH, 'w') as f:
        json.dump(a, f, indent=1, ensure_ascii=False)
        f.write('\n')


def clean_name(n):
    n = re.sub(r'\s+', ' ', n).strip()
    if not re.fullmatch(r"[\w .'\-]{1,14}", n):
        sys.exit('The name must be 1-14 letters, digits, spaces or . _ \' -')
    return n


def parse(code):
    assert code.startswith('GG1-'), 'not an ID request (it starts with GG1-)'
    raw = code[4:].strip()
    d = json.loads(base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)))
    k = base64.b64decode(d['k'])
    assert len(k) == len(SPKI) + 65 and k.startswith(SPKI) and k[len(SPKI)] == 4, 'that is not a P-256 public key'
    return d['k'], re.sub(r'[^\w .\-]', '', str(d.get('l') or 'Device'))[:24] or 'Device'


def find(a, pid):
    p = next((q for q in a if q['id'] == pid), None)
    if not p:
        sys.exit('No player ' + pid)
    return p


def add_key(a, p, code, label=None):
    k, l = parse(code)
    for q in a:
        if any(x['k'] == k for x in q['keys']):
            sys.exit('That device is already registered to ' + q['id'])
    p['keys'].append({'k': k, 'label': label or l})


def main(argv):
    a = load()
    cmd = argv[0] if argv else 'list'
    if cmd == 'add' and len(argv) == 3:
        name = clean_name(argv[1])
        if any(q['name'].lower() == name.lower() for q in a):
            sys.exit('That name is taken')
        n = 1 + max([int(q['id'][1:]) for q in a] + [0])
        p = {'id': f'P{n:03d}', 'name': name, 'keys': []}
        add_key(a, p, argv[2]); a.append(p)
        print('added', p['id'], name)
    elif cmd == 'device' and len(argv) in (3, 4):
        p = find(a, argv[1]); add_key(a, p, argv[2], argv[3] if len(argv) == 4 else None)
        print('device added to', p['id'], p['name'], '->', [x['label'] for x in p['keys']])
    elif cmd == 'drop' and len(argv) == 3:
        p = find(a, argv[1]); gone = [x for x in p['keys'] if x['label'] == argv[2] or x['k'].startswith(argv[2])]
        if len(gone) != 1:
            sys.exit(f'{len(gone)} devices match; use the label or a longer key prefix')
        p['keys'].remove(gone[0]); print('removed', gone[0]['label'], 'from', p['id'])
    elif cmd == 'rename' and len(argv) == 3:
        p = find(a, argv[1]); name = clean_name(argv[2])
        if any(q is not p and q['name'].lower() == name.lower() for q in a):
            sys.exit('That name is taken')
        p['name'] = name; print('renamed', p['id'], 'to', name)
    elif cmd == 'list':
        for q in a:
            print(q['id'], q['name'], '·', ', '.join(f"{x['label']} ({x['k'][-8:]})" for x in q['keys']) or 'no devices')
        return
    else:
        sys.exit(__doc__)
    save(a)


if __name__ == '__main__':
    main(sys.argv[1:])
