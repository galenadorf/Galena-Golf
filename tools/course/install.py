"""Put out/rd_woodbine.js into index.html: replaces the RD_WOODBINE and GREEN_ALTI_WOODBINE lines."""
import os

from common import HERE, OUT

INDEX = os.path.join(HERE, '..', '..', 'index.html')
rd, alti = open(os.path.join(OUT, 'rd_woodbine.js'), encoding='utf-8').read().splitlines()
lines = open(INDEX, encoding='utf-8').read().split('\n')


def put(prefix, new):
    hit = [i for i, l in enumerate(lines) if l.startswith(prefix)]
    assert len(hit) == 1, prefix
    lines[hit[0]] = new


put('const RD_WOODBINE = ', rd)
put('const GREEN_ALTI_WOODBINE = ', alti)
print('installed')
open(INDEX, 'w', encoding='utf-8').write('\n'.join(lines))
