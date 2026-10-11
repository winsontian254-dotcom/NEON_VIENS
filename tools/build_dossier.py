#!/usr/bin/env python3
"""Build the in-game Dossier (the long Reconstruction Handbook) from the text files in i18n/dossier/.

    python3 tools/build_dossier.py      # then run tools/build_zh.py so the Chinese pairs are picked up

i18n/dossier/NN-name.en.txt is the English source and NN-name.zh.txt its Simplified Chinese twin: the same headings and paragraphs in the same
order (the tool refuses to build if the two differ in shape). Format: '# ' starts a section, '## ' a sub-heading, a blank line ends a paragraph.
It writes the English text into index.html as /*NV_DOSSIER_BEGIN*/ window.NV_DOSSIER = [...] /*NV_DOSSIER_END*/ (a script block placed after the
NV_ASSETS block) and the English -> Chinese pairs into i18n/zh/ui9.tsv, which build_zh.py turns into the translation table
(Traditional Chinese is generated from the Simplified text there)."""
import glob, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'i18n', 'dossier')

def parse(path):
    items = []
    for blk in open(path, encoding='utf-8').read().split('\n\n'):
        t = ' '.join(x.strip() for x in blk.strip().split('\n') if x.strip())
        if not t: continue
        items.append(('H', t[2:]) if t.startswith('# ') else ('h', t[3:]) if t.startswith('## ') else ('p', t))
    return items

def main():
    secs, pairs, words, chars = [], [], 0, 0
    for en in sorted(glob.glob(os.path.join(D, '*.en.txt'))):
        zh = en.replace('.en.txt', '.zh.txt')
        if not os.path.exists(zh): sys.exit('missing Chinese twin: ' + os.path.basename(zh))
        a, b = parse(en), parse(zh)
        if [k for k, _ in a] != [k for k, _ in b]: sys.exit('%s and its Chinese twin differ in shape (%d vs %d items)' % (os.path.basename(en), len(a), len(b)))
        for (k, t), (_, z) in zip(a, b):
            words += len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.,%+−×-]*", t)); chars += len(z)
            if k == 'H': secs.append({'t': t, 'i': []})
            else: secs[-1]['i'].append([k, t])
            pairs.append((t, z))
    seen, rows = set(), []
    for t, z in pairs:
        if t in seen: continue
        seen.add(t); rows.append(t + '\t' + z)
    open(os.path.join(ROOT, 'i18n', 'zh', 'ui9.tsv'), 'w', encoding='utf-8').write('\n'.join(rows) + '\n')
    html_p = os.path.join(ROOT, 'index.html'); html = open(html_p, encoding='utf-8').read()
    block = '<script>/*NV_DOSSIER_BEGIN*/window.NV_DOSSIER=' + json.dumps(secs, ensure_ascii=False, separators=(',', ':')) + ';/*NV_DOSSIER_END*/</script>'
    if '/*NV_DOSSIER_BEGIN*/' in html:
        a0 = html.index('<script>/*NV_DOSSIER_BEGIN*/'); b0 = html.index('/*NV_DOSSIER_END*/</script>') + len('/*NV_DOSSIER_END*/</script>'); html = html[:a0] + block + html[b0:]
    else:
        anchor = '/*NV_ASSETS_END*/</script>' if '/*NV_ASSETS_END*/' in html else '/*NV_ZH_END*/</script>'
        i = html.index(anchor) + len(anchor); html = html[:i] + '\n' + block + html[i:]
    open(html_p, 'w', encoding='utf-8').write(html)
    print('[build_dossier] %d sections · %d items · %d words · %d Chinese characters · %d KB' % (len(secs), sum(len(s['i']) for s in secs), words, chars, len(block) // 1024))

if __name__ == '__main__': main()
