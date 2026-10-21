#!/usr/bin/env python3
"""Build promo/banner.js (the embeddable Neon Veins banner) and promo/banner.html (the same banner as a page, for <iframe> embeds).

  python3 promo/src/build.py

Inputs, all in promo/src: style.css, body.html, app.js (the script template), logo_wide.svg / logo_stack.svg (copies of NV.Logo in index.html,
ids renamed nvl* / nvs*; regenerate them if the lettering changes) and ../../version.json (the last 12 updates become the offline fallback).
The skyline is generated here from a fixed seed. Run it after a release if you want the fallback list to be current (the live list is always read
from version.json on GitHub Pages).
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.dirname(HERE)
GAME = 'https://winsontian254-dotcom.github.io/NEON_VIENS/'
APK = 'https://github.com/winsontian254-dotcom/NEON_VIENS/raw/claude/festive-faraday-4v0m9s/android/NeonVeins.apk'


def read(name):
    return open(os.path.join(HERE, name), encoding='utf-8').read()


def skyline():
    random.seed(2098)
    W, H = 1600, 460
    layers = [('#12072a', 70, 260, 34, 80, .07), ('#0b0418', 90, 360, 46, 110, .07), ('#05020b', 110, 430, 60, 150, .09)]
    parts = []
    for col, h0, h1, w0, w1, lit in layers:
        x = -random.randint(0, 40)
        pts, extra = [f'{x},{H}'], []
        while x < W + 40:
            w, h = random.randint(w0, w1), random.randint(h0, h1)
            top = H - h
            if random.random() < .25:
                pts += [f'{x},{top + 14}', f'{x + 10},{top}', f'{x + w - 10},{top}', f'{x + w},{top + 14}']
            else:
                pts += [f'{x},{top}', f'{x + w},{top}']
            if random.random() < .12:
                extra.append(f'<rect x="{x + w // 2 - 1.5}" y="{top - 34}" width="3" height="34" fill="{col}"/>')
            for wy in range(top + 18, H - 8, 16):
                for wx in range(x + 8, x + w - 8, 12):
                    if random.random() < lit:
                        c = random.choice(['#fcee09', '#02d7f2', '#ff2bd6', '#fcee09'])
                        extra.append(f'<rect x="{wx}" y="{wy}" width="4" height="6" fill="{c}" opacity="{0.35 + 0.5 * random.random():.2f}"/>')
            x += w + random.randint(0, 6)
        pts.append(f'{x},{H}')
        parts.append(f'<polygon points="{" ".join(pts)}" fill="{col}"/>' + ''.join(extra))
    parts.append('<g><polygon points="760,460 776,40 800,0 824,40 840,460" fill="#030108"/><path d="M776 40L800 0L824 40" fill="none" stroke="#02d7f2" stroke-width="2" opacity=".9"/>'
                 '<path d="M776 40V460M824 40V460" stroke="#02d7f2" stroke-width="1.5" opacity=".55"/><rect x="796" y="-30" width="8" height="40" fill="#ff2bd6" opacity=".9"/></g>')
    return f'<svg class="nvb-city" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice" aria-hidden="true">{"".join(parts)}</svg>'


def main():
    ver = json.load(open(os.path.join(ROOT, 'version.json'), encoding='utf-8'))
    snap = {'build': ver['build'], 'history': ver['history'][:12]}
    html = read('body.html')
    for k, v in (('@@CITY@@', skyline()), ('@@LOGO_WIDE@@', read('logo_wide.svg').strip()), ('@@LOGO_STACK@@', read('logo_stack.svg').strip()),
                 ('@@GAME@@', GAME), ('@@APK@@', APK), ('@@BUILD@@', str(ver['build']))):
        html = html.replace(k, v)
    js = read('app.js')
    for k, v in (('@@CSS@@', json.dumps(read('style.css'))), ('@@HTML@@', json.dumps(html)),
                 ('@@DATA@@', json.dumps(snap, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')), ('@@GAME@@', GAME)):
        js = js.replace(k, v)
    open(os.path.join(OUT, 'banner.js'), 'w', encoding='utf-8').write(js)
    open(os.path.join(OUT, 'banner.html'), 'w', encoding='utf-8').write(
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Neon Veins</title>'
        '<style>html,body{margin:0;background:#07030f}</style></head>\n<body>\n<script src="banner.js" data-mode="frame"></script>\n</body></html>\n')
    print(f'[promo] banner.js {os.path.getsize(os.path.join(OUT, "banner.js")) // 1024} KB, build {ver["build"]}')


if __name__ == '__main__':
    main()
