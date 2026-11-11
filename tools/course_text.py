#!/usr/bin/env python3
"""The play page's course descriptions, as a plain text file to edit by hand: course_descriptions.txt (repo root).

  python3 tools/course_text.py            read course_descriptions.txt and write each description into courses/courses.json ("blurb")
  python3 tools/course_text.py --export   write course_descriptions.txt from courses/courses.json (overwrites your edits: only for a fresh start)
  python3 tools/course_text.py --check    say what would change, change nothing

File format: a line "[key] Course name" starts a course; the lines under it, up to the next blank line, are its description (they are joined into one
paragraph). Lines starting with # are notes and are ignored. The rounds, years and champions line under the description in the game comes from the trip
spreadsheet (the "trip" field in courses.json), not from this file. An empty description hides the whole block for that course.
pages.yml runs this on every deploy, so editing the text file and pushing is enough."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TXT = os.path.join(ROOT, 'course_descriptions.txt')
HEAD = """# COURSE DESCRIPTIONS: the text shown on the play page, between the course tile and the course picker (one description per course).
#
# HOW THE FILE WORKS
#   - Each course starts with a line like  [woodbine] Woodbine Bend Golf Course
#     Do not change the [key] part: the key picks the course. The name after it is only a label for you.
#   - The description is the line(s) right under the [key] line, up to the next blank line. It can wrap over several lines; they are joined into one paragraph.
#   - Lines starting with # are notes and are ignored. That includes the "shown under it" and "trip champs" notes below each description.
#   - Straight quotes, curly quotes and apostrophes are all fine.
#   - An empty description hides the whole text block for that course.
#
# WHAT THE GAME ADDS UNDER EACH DESCRIPTION (not edited here)
#   - The rounds, years and trip champions come from the trip spreadsheet (the "trip" data in courses/courses.json). The # notes below each description show what
#     the game will print there, for reference only; editing those notes changes nothing.
#   - A course the crew has not played shows only "Trip champs: none yet, the Brown Jacket awaits".
#
# APPLYING YOUR EDITS
#   - Push this file: the deploy copies it into the game automatically.
#   - Or run   python3 tools/course_text.py   to update courses/courses.json yourself (add --check to see what would change without changing it).
#   - The text must fit the screen without scrolling; the game shrinks it a little if needed, so keep each description to about 300 characters.
#   - Do not run   python3 tools/course_text.py --export   unless you want to throw your edits away: it rewrites this file from courses.json.
#
"""


def years(ys):
    o, i = [], 0
    while i < len(ys):
        j = i
        while j + 1 < len(ys) and ys[j + 1] == ys[j] + 1:
            j += 1
        o.append(f'{ys[i]}-{ys[j]}' if j - i >= 2 else ', '.join(map(str, ys[i:j + 1])))
        i = j + 1
    return ', '.join(o)


def export(courses):
    out = [HEAD]
    for c in courses:
        if 'blurb' not in c:
            continue
        t = c.get('trip')
        out.append(f'[{c["key"]}] {c["name"]}')
        out.append(c['blurb'])
        if t:
            out.append(f'# shown under it: {t["n"]} round{"" if t["n"] == 1 else "s"} - {years(t["years"])}')
            if t['win']:
                out.append('# trip champs: ' + ' | '.join(n + ' ' + ' '.join("'" + str(y)[2:] for y in v) for n, v in t['win']))
        else:
            out.append('# shown under it: (nothing: the crew has not played it yet; "Trip champs: none yet" is shown)')
        out.append('')
    return '\n'.join(out)


def parse(text):
    d, key = {}, None
    for line in text.splitlines():
        if line.startswith('#'):
            continue
        m = re.match(r'^\[([a-z0-9_]+)\]', line)
        if m:
            key = m.group(1); d[key] = []
        elif not line.strip():
            key = None
        elif key:
            d[key].append(line.strip())
    return {k: ' '.join(v) for k, v in d.items()}


def main():
    args = sys.argv[1:]
    path = os.path.join(ROOT, 'courses', 'courses.json')
    for a in args:
        if a.endswith('.json'):
            path = a
    raw = open(path, encoding='utf8').read()
    courses = json.loads(raw)['courses']
    if '--export' in args:
        open(TXT, 'w', encoding='utf8').write(export(courses)); print('wrote', TXT); return
    desc = parse(open(TXT, encoding='utf8').read())
    keys = {c['key'] for c in courses}
    for k in desc:
        if k not in keys:
            sys.exit(f'course_descriptions.txt: unknown course key [{k}]')
    changed = 0
    for k, txt in desc.items():
        i = raw.index(f'"key": "{k}"'); nxt = raw.find('"key": ', i + 10)
        a = raw.find('      "blurb": ', i)
        line = f'      "blurb": {json.dumps(txt, ensure_ascii=False)},'
        if a == -1 or (nxt != -1 and a > nxt):   # no description yet: add one above the course's "engine" line
            j = raw.index('      "engine"', i); raw = raw[:j] + line + '\n' + raw[j:]; changed += 1; print('added   ', k)
        else:
            b = raw.index('\n', a)
            if raw[a:b] != line:
                raw = raw[:a] + line + raw[b:]; changed += 1; print('changed ', k)
    json.loads(raw)
    if '--check' in args:
        print(changed, 'course(s) would change'); return
    if changed:
        open(path, 'w', encoding='utf8').write(raw)
    print(changed, 'course(s) updated' if changed else 'courses.json already matches course_descriptions.txt')


if __name__ == '__main__':
    main()
