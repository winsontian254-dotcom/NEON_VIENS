#!/usr/bin/env python3
"""Bump the game build: python3 tools/release.py "note one" "note two" ...
Updates NV_BUILD in index.html and adds an entry to version.json (shown to players
in the 'new version' prompt). Run it with every index.html change you want players to be told about."""
import json, re, sys, datetime, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
notes = [n for n in sys.argv[1:] if n.strip()]
if not notes: sys.exit('give at least one change-log line')
vp = root / 'version.json'; v = json.loads(vp.read_text(encoding='utf-8'))
b = v['build'] + 1
v['build'] = b
v['history'].insert(0, {'build': b, 'version': '1.' + str(b), 'date': datetime.date.today().isoformat(), 'notes': notes})
v['history'] = v['history'][:25]
vp.write_text(json.dumps(v, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
ip = root / 'index.html'; s = ip.read_text(encoding='utf-8')
s, n = re.subn(r"const NV_BUILD = \d+;", 'const NV_BUILD = %d;' % b, s, count=1)
assert n == 1, 'NV_BUILD not found'
ip.write_text(s, encoding='utf-8'); print('build', b)
