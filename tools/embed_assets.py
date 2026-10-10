#!/usr/bin/env python3
"""Embed 3D models into index.html (the game stays a single file).

    python3 tools/embed_assets.py            # embed every model listed in assets/manifest.json
    python3 tools/embed_assets.py --slim     # first slim each model with gltf-transform (node, offline)

assets/manifest.json maps a short name to a source file plus its licence:
    { "robot": { "file": "src/robot.glb", "anims": ["Idle", "Walking"], "license": "CC0 1.0", "source": "..." } }
"anims" (optional) keeps only the listed animation clips.

The models go into one script block, /*NV_ASSETS_BEGIN*/ window.NV_ASSETS = { name: 'base64' } /*NV_ASSETS_END*/,
placed after the NV_ZH block. NV.Assets in index.html decodes and loads them.

--slim needs a folder where `npm i @gltf-transform/core @gltf-transform/functions` was run, given as GLTF_TRANSFORM_DIR=/that/folder;
it drops unlisted animations, removes unused data, merges duplicates and quantises vertex data."""
import base64, json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')
ADIR = os.path.join(ROOT, 'assets')
BUDGET = 8 * 1024 * 1024

SLIM = r"""
import { NodeIO } from '@gltf-transform/core';
import { prune, dedup, quantize, weld } from '@gltf-transform/functions';
const [src, dst, keep] = process.argv.slice(2);
const io = new NodeIO(); const doc = await io.read(src);
const want = keep ? keep.split('|') : null;
if (want) doc.getRoot().listAnimations().forEach(a => { if (!want.includes(a.getName())) a.dispose(); });
await doc.transform(dedup(), weld(), prune(), quantize());
await io.write(dst, doc);
"""


def slim(src, keep):
    with tempfile.TemporaryDirectory() as td:
        js = os.path.join(os.environ.get('GLTF_TRANSFORM_DIR', td), '_nv_slim.mjs'); out = os.path.join(td, 'out.glb')
        open(js, 'w').write(SLIM)
        r = subprocess.run(['node', js, src, out, '|'.join(keep or [])], capture_output=True, text=True)
        try: os.remove(js)
        except OSError: pass
        if r.returncode:
            print('  slim failed, embedding as is:', (r.stderr or '').strip()[-300:])
            return open(src, 'rb').read()
        return open(out, 'rb').read()


def main():
    man = json.load(open(os.path.join(ADIR, 'manifest.json'), encoding='utf-8'))
    blob, total = {}, 0
    for name, a in man.items():
        path = os.path.join(ADIR, a['file'])
        if not os.path.exists(path):
            print(f'  {name}: missing {a["file"]}, skipped'); continue
        if not a.get('license'):
            sys.exit(f'{name}: no licence recorded in manifest.json')
        data = slim(path, a.get('anims')) if '--slim' in sys.argv else open(path, 'rb').read()
        blob[name] = base64.b64encode(data).decode('ascii'); total += len(blob[name])
        print(f'  {name}: {os.path.getsize(path) // 1024} KB -> {len(data) // 1024} KB ({a["license"]})')
    html = open(HTML, encoding='utf-8').read()
    block = '<script>/*NV_ASSETS_BEGIN*/window.NV_ASSETS=' + json.dumps(blob, separators=(',', ':')) + ';/*NV_ASSETS_END*/</script>'
    if '/*NV_ASSETS_BEGIN*/' in html:
        a = html.index('<script>/*NV_ASSETS_BEGIN*/'); b = html.index('/*NV_ASSETS_END*/</script>') + len('/*NV_ASSETS_END*/</script>')
        html = html[:a] + block + html[b:]
    else:
        a = html.index('</script>', html.index('/*NV_ZH_END*/')) + len('</script>')
        html = html[:a] + '\n' + block + html[a:]
    open(HTML, 'w', encoding='utf-8').write(html)
    print(f'[embed_assets] {len(blob)} models · {total // 1024} KB embedded')
    if total > BUDGET:
        print(f'WARNING: the asset block is over {BUDGET // 1048576} MB; slim or drop models.')


if __name__ == '__main__':
    main()
