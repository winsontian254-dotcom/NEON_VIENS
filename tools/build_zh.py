#!/usr/bin/env python3
"""Compile the Chinese translations in i18n/zh/ into index.html (window.NV_ZH).

  python3 tools/build_zh.py            # rebuild the NV_ZH block
  python3 tools/build_zh.py --src DIR  # also write DIR/src.json + batches.json (untranslated story keys)

Sources (UTF-8, one entry per line, TAB-separated, Simplified Chinese):
  i18n/zh/bNN.tsv   story lines:  <index>\t<translation>   (index into storyKeys(), see NV.I18n in index.html)
  i18n/zh/uiN.tsv   interface:    <English text>\t<translation>
Traditional Chinese is generated from Simplified with OpenCC (s2twp): pip install opencc-python-reimplemented
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')
DIR = os.path.join(ROOT, 'i18n', 'zh')

# regex patterns for composed labels (English regex, flags, Simplified replacement)
PATTERNS = [
    (r'^CHAPTER (\w+) COMPLETE$', 'i', r'第$1章完成'),
    (r'^CHAPTER (\w+)$', 'i', r'第$1章'),
    (r'^ACT I$', '', '第一幕'), (r'^ACT II$', '', '第二幕'), (r'^ACT III$', '', '第三幕'), (r'^ACT IV$', '', '第四幕'), (r'^ACT V$', '', '第五幕'),
    (r'^ENDING (\w+) ACHIEVED$', 'i', r'达成结局 $1'),
    (r'^ENDING (\w+)$', 'i', r'结局 $1'),
    (r'^MISSION (\d+)$', 'i', r'任务 $1'),
    (r'^(\d+) CHAPTERS$', 'i', r'$1 章'),
    (r'^Implant level (\d+)$', '', r'植入体等级 $1'),
    (r'^Paper stars (\S+)$', '', r'纸星星 $1'),
    (r'^Operations (\d+)$', '', r'行动 $1'),
    (r'^Next: Chapter (\w+)$', '', r'下一章：第$1章'),
    (r'^(\d+) objective\(s\) left$', '', r'剩余 $1 个目标'),
    (r'^Find (.+) and talk to them \[E\]\. Follow the yellow beam\.$', '', r'找到$1并与其交谈 [E]。跟随黄色光柱。'),
    (r'^Head to the red beam to start: (.+)\.$', '', r'前往红色光柱开始：$1。'),
]


def load_data():
    s = open(HTML, encoding='utf-8').read()
    a = s.index('window.NV_DATA=') + len('window.NV_DATA=')
    b = s.index('/*NV_DATA_END')
    return s, json.loads(s[a:b].strip().rstrip(';'))


def story_keys(d):  # must mirror NV.I18n.storyKeys() in index.html
    out, seen = [], set()

    def add(x):
        if isinstance(x, str) and x.strip() and x not in seen:
            seen.add(x); out.append(x)

    def walk(ns):
        for n in ns:
            t = n['t']
            if t in ('scene', 'n', 'l', 'sys'): add(n.get('v'))
            if t == 'l': add(n.get('s'))
            if t == 'choice':
                add(n.get('p'))
                for o in n['o']:
                    add(o.get('label')); add(o.get('text')); walk(o.get('b') or [])
            if t == 'cond':
                for b in n['b']: walk(b.get('n') or [])
            if t == 'play':
                add(n.get('d')); add(n.get('boss'))
    for c in d['chapters']:
        add(c['title']); walk(c['n'])
    for k in sorted(d['acts']): add(d['acts'][k])
    for p in d['premise']: add(p)
    for k in sorted(d['endings']):
        e = d['endings'][k]; add(e['title']); add(e['desc'])
        if e['desc'].startswith('Choice: '): add(e['desc'][8:])
    for k in sorted(d['missions']):
        m = d['missions'][k]; add(m['title']); add(m['syn']); add('. '.join(m['syn'].split('. ')[:2]) + '.')
    return out


def read_tsv(path):
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if '\t' in line:
            k, v = line.split('\t', 1)
            if k and v.strip(): yield k, v.strip()


def main():
    import opencc
    cc = opencc.OpenCC('s2twp')
    html, d = load_data()
    keys = story_keys(d)
    hans = [''] * len(keys)
    for f in sorted(glob.glob(os.path.join(DIR, 'b*.tsv'))):
        for k, v in read_tsv(f):
            i = int(k)
            if 0 <= i < len(keys): hans[i] = v
    ui = {}
    for f in sorted(glob.glob(os.path.join(DIR, 'ui*.tsv'))):
        for k, v in read_tsv(f):
            ui[k] = [v, cc.convert(v)]
    hant = [cc.convert(x) if x else '' for x in hans]
    pat = [[p, f, r.replace('$1', '$1'), cc.convert(r)] for p, f, r in PATTERNS]
    blob = json.dumps({'story': [hans, hant], 'ui': ui, 'pat': pat}, ensure_ascii=False, separators=(',', ':'))
    block = '<script>/*NV_ZH_BEGIN*/window.NV_ZH=' + blob + ';/*NV_ZH_END*/</script>'
    if '/*NV_ZH_BEGIN*/' in html:
        a = html.index('<script>/*NV_ZH_BEGIN*/'); b = html.index('/*NV_ZH_END*/</script>') + len('/*NV_ZH_END*/</script>')
        html = html[:a] + block + html[b:]
    else:
        a = html.index('</script>', html.index('/*NV_DATA_END')) + len('</script>')
        html = html[:a] + '\n' + block + html[a:]
    open(HTML, 'w', encoding='utf-8').write(html)
    done = sum(1 for x in hans if x)
    print(f'[build_zh] story {done}/{len(keys)} lines · ui {len(ui)} strings · {len(blob) // 1024} KB')
    if '--src' in sys.argv:
        out = sys.argv[sys.argv.index('--src') + 1]
        json.dump(keys, open(os.path.join(out, 'src.json'), 'w', encoding='utf-8'), ensure_ascii=False)


if __name__ == '__main__':
    main()
