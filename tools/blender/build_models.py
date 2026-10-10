#!/usr/bin/env python3
"""Build Neon Veins' 3D models from scratch and export them as GLB.

Every model here is made in code (primitives, a skinned armature and
keyframed poses). Nothing is downloaded, so every model is original work.

    python3 tools/blender/build_models.py            # needs the bpy module (pip install bpy)
    blender -b -P tools/blender/build_models.py      # or run it inside Blender

Output goes to assets/src/<name>.glb. Then add each file to assets/manifest.json
and run tools/embed_assets.py.
"""
import math, os
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'assets', 'src')
os.makedirs(OUT, exist_ok=True)

_mats = {}


def mat(name, rgb, rough=0.6, metal=0.0, emit=None, strength=0.0):
    """One Principled material per name. Base colour and emission survive glTF export."""
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1.0)
        b.inputs['Emission Strength'].default_value = strength
    _mats[name] = m
    return m


SKIN = mat('skin', (0.78, 0.55, 0.42))
JACKET = mat('jacket', (0.10, 0.11, 0.14), rough=0.5)
PANTS = mat('pants', (0.07, 0.08, 0.10), rough=0.8)
HAIR = mat('hair', (0.04, 0.03, 0.03), rough=0.4)
SHOE = mat('shoe', (0.02, 0.02, 0.02), rough=0.7)
METAL = mat('metal', (0.25, 0.27, 0.30), rough=0.35, metal=0.9)
DARK = mat('dark', (0.05, 0.05, 0.06), rough=0.5, metal=0.4)
WHITE = mat('white', (0.85, 0.86, 0.88), rough=0.4)
RED = mat('red', (0.9, 0.08, 0.06), rough=0.4, emit=(1.0, 0.1, 0.08), strength=2.0)
CYAN = mat('cyan', (0.2, 0.9, 1.0), rough=0.3, emit=(0.3, 0.95, 1.0), strength=4.0)
PAPER = mat('paper', (0.9, 0.12, 0.08), rough=0.9, emit=(1.0, 0.25, 0.1), strength=1.5)
WOOD = mat('crate', (0.32, 0.22, 0.12), rough=0.85)


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


def shape(kind, loc, size, m, rot=(0, 0, 0)):
    """Box (size = full extents), sphere (size = (r, r, r)) or cylinder (size = (r, depth))."""
    if kind == 'box':
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        o = bpy.context.object
        o.scale = size
    elif kind == 'sphere':
        bpy.ops.mesh.primitive_uv_sphere_add(radius=size[0], segments=12, ring_count=8, location=loc)
        o = bpy.context.object
        o.scale = (1, 1, size[2] / size[0]) if len(size) > 2 else (1, 1, 1)
    else:
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=size[0], depth=size[1], location=loc)
        o = bpy.context.object
    o.rotation_euler = rot
    o.data.materials.append(m)
    return o


def limb(a, b, r, m):
    """Cylinder from point a to point b."""
    a, b = Vector(a), Vector(b)
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=r, depth=d.length, location=(a + b) / 2)
    o = bpy.context.object
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    o.data.materials.append(m)
    return o


def join(parts, name):
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name
    return o


def export_static(obj, name):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(OUT, name + '.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True,
                              export_apply=True, export_animations=False)
    print('  wrote', path, os.path.getsize(path) // 1024, 'KB')


# ---------- Human: skinned body with five animation clips ----------

BONES = {  # name: (head, tail, parent)
    'Hips': ((0, 0, 0.95), (0, 0, 1.10), None),
    'Spine': ((0, 0, 1.10), (0, 0, 1.40), 'Hips'),
    'Neck': ((0, 0, 1.40), (0, 0, 1.55), 'Spine'),
    'Head': ((0, 0, 1.55), (0, 0, 1.80), 'Neck'),
}
for s, side in ((1, 'L'), (-1, 'R')):
    BONES[f'UpperArm.{side}'] = ((s * 0.20, 0, 1.36), (s * 0.23, 0, 1.08), 'Spine')
    BONES[f'Forearm.{side}'] = ((s * 0.23, 0, 1.08), (s * 0.25, 0.03, 0.82), f'UpperArm.{side}')
    BONES[f'Thigh.{side}'] = ((s * 0.10, 0, 0.95), (s * 0.10, 0, 0.50), 'Hips')
    BONES[f'Shin.{side}'] = ((s * 0.10, 0, 0.50), (s * 0.10, 0, 0.08), f'Thigh.{side}')
    BONES[f'Foot.{side}'] = ((s * 0.10, 0, 0.08), (s * 0.10, 0.18, 0.02), f'Shin.{side}')


def build_human_armature():
    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm = bpy.context.object
    arm.name = 'HumanRig'
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    eb.remove(eb[0])
    for name, (h, t, parent) in BONES.items():
        b = eb.new(name)
        b.head, b.tail = Vector(h), Vector(t)
        if parent:
            b.parent = eb[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm


def build_human_body():
    p = []
    p.append(shape('box', (0, 0, 1.0), (0.34, 0.22, 0.20), PANTS))          # hips
    p.append(shape('box', (0, 0, 1.25), (0.38, 0.24, 0.32), JACKET))        # chest
    p.append(shape('box', (0, 0.01, 1.16), (0.30, 0.20, 0.10), JACKET))     # waist
    p.append(shape('sphere', (0, 0, 1.68), (0.115, 0.115, 0.13), SKIN))     # head
    p.append(shape('sphere', (0, 0.01, 1.73), (0.12, 0.12, 0.08), HAIR))    # hair cap
    p.append(shape('box', (0, 0.07, 1.60), (0.14, 0.12, 0.06), HAIR))       # hair back
    p.append(limb((0, 0, 1.42), (0, 0, 1.56), 0.05, SKIN))                  # neck
    for s in (1, -1):
        p.append(limb((s * 0.20, 0, 1.36), (s * 0.23, 0, 1.08), 0.06, JACKET))
        p.append(limb((s * 0.23, 0, 1.08), (s * 0.25, 0.03, 0.82), 0.055, JACKET))
        p.append(shape('sphere', (s * 0.25, 0.03, 0.80), (0.05, 0.05, 0.05), SKIN))
        p.append(limb((s * 0.10, 0, 0.95), (s * 0.10, 0, 0.50), 0.09, PANTS))
        p.append(limb((s * 0.10, 0, 0.50), (s * 0.10, 0, 0.08), 0.075, PANTS))
        p.append(shape('box', (s * 0.10, 0.07, 0.05), (0.11, 0.22, 0.08), SHOE))
    return join(p, 'Human')


def pose(arm, frame, bones, hips_loc=None):
    for name in BONES:
        pb = arm.pose.bones[name]
        pb.rotation_mode = 'XYZ'
        x, y, z = bones.get(name, (0, 0, 0))
        pb.rotation_euler = (x, y, z)
        pb.keyframe_insert('rotation_euler', frame=frame)
    if hips_loc is not None:
        arm.pose.bones['Hips'].location = hips_loc
        arm.pose.bones['Hips'].keyframe_insert('location', frame=frame)


def clip(arm, name, count, fn):
    """Build one action from count frames. fn(i) returns (bones, hips_loc)."""
    act = bpy.data.actions.new(name)
    arm.animation_data_create()
    arm.animation_data.action = act
    for i in range(count):
        bones, loc = fn(i)
        pose(arm, i + 1, bones, loc)
    return act


def walk_pose(t, amp):
    s, c = math.sin(t), math.cos(t)
    return {
        'Thigh.L': (s * 0.6 * amp, 0, 0), 'Thigh.R': (-s * 0.6 * amp, 0, 0),
        'Shin.L': (-max(0, -s) * 0.9 * amp, 0, 0), 'Shin.R': (-max(0, s) * 0.9 * amp, 0, 0),
        'UpperArm.L': (-s * 0.5 * amp, 0, 0), 'UpperArm.R': (s * 0.5 * amp, 0, 0),
        'Forearm.L': (-0.35, 0, 0), 'Forearm.R': (-0.35, 0, 0),
        'Hips': (0, 0, s * 0.05 * amp),
    }, (0, 0, 0.02 * amp * abs(c))


def build_clips(arm):
    clip(arm, 'Idle', 48, lambda i: ({
        'Spine': (math.sin(i / 48 * 2 * math.pi) * 0.02, 0, 0),
        'UpperArm.L': (0.05, 0, 0), 'UpperArm.R': (0.05, 0, 0),
        'Forearm.L': (-0.3, 0, 0), 'Forearm.R': (-0.3, 0, 0),
    }, None))
    clip(arm, 'Walk', 25, lambda i: walk_pose(i / 24 * 2 * math.pi, 1.0))
    clip(arm, 'Run', 17, lambda i: (lambda b: (
        {**b[0], 'Spine': (0.15, 0, 0), 'UpperArm.L': (-b[0]['UpperArm.L'][0] * 1.4, 0, 0),
         'UpperArm.R': (-b[0]['UpperArm.R'][0] * 1.4, 0, 0)}, b[1]))(
        walk_pose(i / 16 * 2 * math.pi, 1.5)))

    def hit(i):
        e = math.sin(math.pi * min(1.0, i / 10))
        return {'Spine': (0.35 * e, 0, 0.2 * e), 'Head': (0.3 * e, 0.2 * e, 0)}, None
    clip(arm, 'Hit', 11, hit)

    def death(i):
        p = min(1.0, i / 30)
        return {
            'Spine': (-1.0 * p, 0, 0), 'Head': (-0.3 * p, 0, 0),
            'Hips': (-0.7 * p, 0, 0),
            'Thigh.L': (0.5 * p, 0, 0), 'Thigh.R': (0.3 * p, 0, 0),
            'Shin.L': (-1.1 * p, 0, 0), 'Shin.R': (-0.8 * p, 0, 0),
            'UpperArm.L': (-1.2 * p, 0, 0), 'UpperArm.R': (-1.0 * p, 0, 0),
        }, None
    clip(arm, 'Death', 40, death)


def make_human():
    body = build_human_body()
    arm = build_human_armature()
    body.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    build_clips(arm)
    arm.animation_data.action = bpy.data.actions['Idle']
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    path = os.path.join(OUT, 'human.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True,
                              export_skins=True, export_animations=True,
                              export_animation_mode='ACTIONS', export_apply=False)
    print('  wrote', path, os.path.getsize(path) // 1024, 'KB')


# ---------- Static props ----------

def make_drone():
    p = [shape('sphere', (0, 0, 0), (0.16, 0.16, 0.10), DARK),
         shape('sphere', (0, 0.15, -0.02), (0.05, 0.05, 0.05), RED)]          # lens
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        p.append(limb((0, 0, 0), (sx * 0.22, sy * 0.22, 0.05), 0.012, METAL))
        p.append(shape('cylinder', (sx * 0.22, sy * 0.22, 0.07), (0.11, 0.01), CYAN))
    return join(p, 'Drone')


def make_medkit():
    p = [shape('box', (0, 0, 0), (0.26, 0.16, 0.14), WHITE),
         shape('box', (0, 0.082, 0), (0.07, 0.01, 0.20), RED),
         shape('box', (0, 0.082, 0), (0.20, 0.01, 0.07), RED)]
    return join(p, 'Medkit')


def make_crate():
    p = [shape('box', (0, 0, 0), (0.6, 0.6, 0.6), WOOD)]
    for z in (-0.25, 0.25):
        p.append(shape('box', (0, 0, z), (0.62, 0.62, 0.05), METAL))
    return join(p, 'Crate')


def make_lantern():
    p = [shape('cylinder', (0, 0, 0), (0.18, 0.40), PAPER),
         shape('cylinder', (0, 0, 0.22), (0.12, 0.03), DARK),
         shape('cylinder', (0, 0, -0.22), (0.12, 0.03), DARK),
         limb((0, 0, 0.24), (0, 0, 0.45), 0.012, METAL)]
    return join(p, 'Lantern')


def main():
    clear_scene()
    make_human()
    clear_scene()
    export_static(make_drone(), 'drone')
    clear_scene()
    export_static(make_medkit(), 'medkit')
    clear_scene()
    export_static(make_crate(), 'crate')
    clear_scene()
    export_static(make_lantern(), 'lantern')


if __name__ == '__main__':
    main()
