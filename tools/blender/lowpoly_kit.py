#!/usr/bin/env python3
"""Low-poly version of the human kit (the art direction of Build 62: faceted figures on purpose).

    python3 tools/blender/lowpoly_kit.py [-- debug]     # needs the bpy module (pip install bpy)

build_humans.py writes the full-detail kit to assets/src/human_kit_hires.glb (not shipped). This script reads it, collapses every part to a
target triangle count with Blender's Decimate modifier (vertex colours, UVs and part names are kept, so NV.Human needs no change) and writes
assets/src/human_kit.glb, the kit that is embedded. The game lights every face on its own (NV.Style), so what is left reads as clean facets.
There are no coarse `_lo` copies any more: a part is a few hundred triangles, so NV.Human draws it whole at every distance (and Babylon does not draw
disabled LOD meshes anyway).
"""
import os, sys
import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'assets', 'src', 'human_kit_hires.glb')
OUT = os.path.join(ROOT, 'assets', 'src', 'human_kit.glb')

# triangles of the full-detail part (the hires parts have 800 to 27000)
TRIS = {
    'head': 640, 'torso': 380, 'pelvis': 130, 'leg_u': 120, 'leg_l': 100, 'foot': 110, 'arm_u': 110, 'arm_l': 90, 'hand': 170,
    'hair_buzz': 240, 'hair_undercut': 300, 'hair_mohawk': 280, 'hair_bob': 440, 'hair_long': 540, 'hair_bun': 340, 'hair_braids': 440,
    'hood': 360, 'cap': 260,
}


def tris(ob):
    me = ob.data
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def decimate(ob, want):
    n = tris(ob)
    if n <= want:
        return n
    md = ob.modifiers.new('lp', 'DECIMATE')
    md.decimate_type = 'COLLAPSE'
    md.ratio = max(0.001, want / n)
    md.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=md.name)
    return tris(ob)


def main():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.import_scene.gltf(filepath=SRC)
    objs = {o.name: o for o in bpy.context.scene.objects if o.type == 'MESH'}
    for name in [n for n in objs if n.endswith('_lo') or n.endswith('_lo2')]:      # the full-detail kit's coarse copies are not shipped
        bpy.data.objects.remove(objs.pop(name), do_unlink=True)
    report = []
    for name, want in TRIS.items():
        ob = objs.get(name)
        if ob:
            report.append((name, tris(ob), decimate(ob, want)))
    for key, a, b in report:
        print(f'  {key:18s} {a:6d} -> {b:5d}')
    print('total', sum(r[2] for r in report))
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs.values():
        o.select_set(True)
    bpy.context.view_layer.objects.active = next(iter(objs.values()))
    kw = dict(filepath=OUT, export_format='GLB', use_selection=True, export_apply=True, export_animations=False, export_yup=True)
    for extra in ({'export_vertex_color': 'ACTIVE'}, {'export_active_vertex_color_when_no_material': True}, {}):
        try:
            bpy.ops.export_scene.gltf(**kw, **extra)
            break
        except TypeError:
            continue
    print('wrote', os.path.basename(OUT), os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    main()
