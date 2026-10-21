#!/usr/bin/env python3
"""Manage the promo codes in index.html (the NV_PROMO script block).

Codes are stored as salted SHA-256 hashes, so the plain code is written nowhere in the repo: keep your own list of the codes you hand out.
The hash is sha256('nv-promo:' + CODE) with CODE upper-cased and cut down to A-Z and 0-9 (what NV.Rewards.hashOf does in the game).

  python3 tools/promo.py add CODE "Name shown to the player" cr=500 parts=10 cons.trauma=2 [expires=YYYY-MM-DD]
  python3 tools/promo.py list
  python3 tools/promo.py remove CODE | HASH-PREFIX

Reward keys: cr (credits), parts, mil, quantum, cipher (materials), picks (lockpicks), xp, cons.<id> (a consumable id from NV.Arms.CONS, e.g. cons.trauma).
Every code works once per device. An expired code (expires=...) is refused after that local date. Run tools/build_zh.py afterwards if the name is a new
English string that needs a translation (add it to a uiN.tsv first).
"""
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')
BEGIN, END = '<script>/*NV_PROMO_BEGIN*/window.NV_PROMO=', ';/*NV_PROMO_END*/</script>'
PLAIN = ('cr', 'parts', 'mil', 'quantum', 'cipher', 'picks', 'xp')


def norm(code):
    return re.sub(r'[^A-Z0-9]', '', code.upper())[:32]


def hash_of(code):
    return hashlib.sha256(('nv-promo:' + norm(code)).encode()).hexdigest()


def load():
    html = open(HTML, encoding='utf-8').read()
    a = html.index(BEGIN) + len(BEGIN)
    b = html.index(END, a)
    return html, a, b, json.loads(html[a:b])


def save(html, a, b, promos):
    blob = json.dumps(promos, ensure_ascii=False, separators=(',', ':'))
    open(HTML, 'w', encoding='utf-8').write(html[:a] + blob + html[b:])


def consumables(html):
    a = html.index('const CONS = {')
    b = html.index('};', a)
    return set(re.findall(r'(?:^|[\s,{])(\w+): \[[\'"]', html[a:b]))


def describe(p):
    r = p['r']
    bits = [f'{r[k]} {k}' for k in PLAIN if k in r] + [f'{n} {k}' for k, n in sorted(r.get('cons', {}).items())]
    return ', '.join(bits) + (f'  (expires {p["x"]})' if p.get('x') else '')


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ('add', 'list', 'remove'):
        print(__doc__)
        return 1
    html, a, b, promos = load()
    if args[0] == 'list':
        for p in promos:
            print(f'{p["h"][:10]}  {p["n"]:<28} {describe(p)}')
        print(f'[promo] {len(promos)} codes')
        return 0
    if args[0] == 'remove':
        key = args[1] if len(args) > 1 else ''
        h = hash_of(key)
        keep = [p for p in promos if p['h'] != h and not (len(key) >= 6 and p['h'].startswith(key.lower()))]
        if len(keep) == len(promos):
            print('[promo] no such code')
            return 1
        save(html, a, b, keep)
        print(f'[promo] removed, {len(keep)} codes left')
        return 0
    if len(args) < 4:
        print(__doc__)
        return 1
    code, name = args[1], args[2]
    if not norm(code):
        print('[promo] the code needs letters or digits')
        return 1
    reward, exp = {}, None
    known = consumables(html)
    for kv in args[3:]:
        k, _, v = kv.partition('=')
        if k == 'expires':
            if not re.fullmatch(r'\d{4}-\d\d-\d\d', v):
                print('[promo] expires=YYYY-MM-DD')
                return 1
            exp = v
        elif k in PLAIN and v.isdigit() and int(v) > 0:
            reward[k] = int(v)
        elif k.startswith('cons.') and v.isdigit() and int(v) > 0:
            cid = k[5:]
            if cid not in known:
                print(f'[promo] unknown consumable "{cid}". Known: {", ".join(sorted(known))}')
                return 1
            reward.setdefault('cons', {})[cid] = int(v)
        else:
            print(f'[promo] cannot read "{kv}"')
            return 1
    if not reward:
        print('[promo] the code gives nothing')
        return 1
    entry = {'h': hash_of(code), 'n': name, 'r': reward}
    if exp:
        entry['x'] = exp
    promos = [p for p in promos if p['h'] != entry['h']] + [entry]
    save(html, a, b, promos)
    print(f'[promo] {norm(code)} -> {describe(entry)}  ({len(promos)} codes)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
