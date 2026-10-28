"""Put the course's out/rd_<key>.js (build.py) into index.html: replaces its RD_<KEY> and GREEN_ALTI_<KEY> lines."""
import os

from common import ALTI_VAR, HERE, RD_JS, RD_VAR

INDEX = os.path.join(HERE, '..', '..', 'index.html')
rd, alti = open(RD_JS, encoding='utf-8').read().splitlines()
lines = open(INDEX, encoding='utf-8').read().split('\n')


def put(prefix, new):
    hit = [i for i, l in enumerate(lines) if l.startswith(prefix)]
    assert len(hit) == 1, prefix
    lines[hit[0]] = new


put(f'const {RD_VAR} = ', rd)
put(f'const {ALTI_VAR} = ', alti)
print('installed')
open(INDEX, 'w', encoding='utf-8').write('\n'.join(lines))
