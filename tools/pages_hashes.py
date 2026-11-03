#!/usr/bin/env python3
"""Run by pages.yml on the deploy folder: stamps sw.js with the hash of every file, so a new build copies unchanged files from its old cache instead of downloading them."""
import hashlib, json, pathlib, sys

site = pathlib.Path(sys.argv[1])
SKIP = {'index.html', 'sw.js', 'version.txt'}   # the page and the worker carry the build number, so they change on every deploy
hashes = {p.relative_to(site).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in sorted(site.rglob('*')) if p.is_file() and p.name not in SKIP}
sw = site / 'sw.js'
text = sw.read_text(encoding='utf8')
assert text.count("'__HASHES__'") == 1
sw.write_text(text.replace("'__HASHES__'", json.dumps(hashes, separators=(',', ':'))), encoding='utf8')
print(len(hashes), 'files hashed')
