"""Put the course's out/rd_<key>.js (build.py) into the game as courses/<key>.js (repo root), the file the game loads when the
course is picked. The course must also be listed in courses/courses.json (name, pars, scenery), which is written by hand."""
import json
import os

from common import ALTI_VAR, HERE, KEY, NAME, ORIGIN, RD_JS, RD_VAR

ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
DEST = os.path.join(ROOT, 'courses', KEY + '.js')
rd, alti = open(RD_JS, encoding='utf-8').read().splitlines()


def body(line, var):
    head = f'const {var} = '
    assert line.startswith(head) and line.endswith(';'), var
    return line[len(head):]


reg = json.load(open(os.path.join(ROOT, 'courses', 'courses.json'), encoding='utf-8'))
if not any(c['key'] == KEY for c in reg['courses']):
    print(f'note: "{KEY}" is not in courses/courses.json yet, so the game will not offer it')
lines = [
    f'/* {NAME}: course data (ENU metres around {abs(ORIGIN[0])} {"NS"[ORIGIN[0] < 0]} {abs(ORIGIN[1])} {"EW"[ORIGIN[1] < 0]}), built by tools/course (build.py, install.py --course {KEY}); never edit by hand */',
    'window.COURSE_DATA = window.COURSE_DATA || {};',
    f'COURSE_DATA.{KEY} = {{}};',
    f'COURSE_DATA.{KEY}.rd = {body(rd, RD_VAR)}',
    f'COURSE_DATA.{KEY}.alti = {body(alti, ALTI_VAR)}',
]
os.makedirs(os.path.dirname(DEST), exist_ok=True)
open(DEST, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('installed', os.path.relpath(DEST, ROOT), f'{os.path.getsize(DEST) / 1024:.0f} KB')
