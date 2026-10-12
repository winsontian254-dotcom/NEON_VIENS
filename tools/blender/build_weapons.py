#!/usr/bin/env python3
"""First-person weapon models for Neon Veins, built from scratch in Blender (bpy) and exported as GLB.

    python3 tools/blender/build_weapons.py            # needs the bpy module (pip install bpy)
    blender -b -P tools/blender/build_weapons.py      # or run it inside Blender

Everything is modelled in GAME axes (x right, y up, z forward = the way the barrel points),
at the scale the game's viewmodels use, then written to assets/src/w_<name>.glb.

Each model is a handful of meshes named by ROLE; the game gives every role its own material
(tinted with the weapon's faction colours, so one model serves hundreds of weapons):
    body   the painted shell (slide, receiver, blade flats)   -> weapon colour
    metal  barrels, bolts, fasteners, edges                    -> bright steel
    grip   polymer: grips, frames, handguards                  -> near-black
    dark   cuts, serrations, vents, bores                      -> black
    acc    thin light lines, status lights                     -> weapon accent colour, emissive
    heat   the energy coil strip                               -> palette colour that dims as the gun heats
    glass  sight windows                                       -> translucent
Edges are bevelled so the light catches them.
"""
import math, os
import bpy, bmesh
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'assets', 'src')
os.makedirs(OUT, exist_ok=True)

ROLES = {  # name: (base colour, roughness, metallic, emission colour, strength)
    'body': ((0.35, 0.36, 0.42), 0.45, 0.6, None, 0),
    'metal': ((0.62, 0.65, 0.72), 0.3, 1.0, None, 0),
    'grip': ((0.07, 0.07, 0.09), 0.7, 0.1, None, 0),
    'dark': ((0.01, 0.01, 0.015), 0.8, 0.0, None, 0),
    'acc': ((0.1, 0.9, 1.0), 0.3, 0.0, (0.1, 0.9, 1.0), 6.0),
    'heat': ((1.0, 0.2, 0.7), 0.3, 0.0, (1.0, 0.2, 0.7), 4.0),
    'glass': ((0.1, 0.25, 0.3), 0.1, 0.0, (0.05, 0.3, 0.35), 1.0),
    'glove': ((0.16, 0.15, 0.2), 0.8, 0.0, None, 0),
    'sleeve': ((0.3, 0.2, 0.5), 0.8, 0.0, None, 0),
}
_mats = {}


def mat(role):
    if role in _mats:
        return _mats[role]
    c, r, m, e, s = ROLES[role]
    mt = bpy.data.materials.new(role)
    mt.use_nodes = True
    b = mt.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*c, 1.0)
    b.inputs['Roughness'].default_value = r
    b.inputs['Metallic'].default_value = m
    if e:
        b.inputs['Emission Color'].default_value = (*e, 1.0)
        b.inputs['Emission Strength'].default_value = s
    _mats[role] = mt
    return mt


def P(x, y, z):
    """game axes (x right, y up, z forward) -> Blender axes. Babylon's glTF loader turns a model that faces
    glTF +Z (= Blender -Y) into one facing +Z, with Blender -X as its right-hand side."""
    return (-x, -z, y)


def clear():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for blk in (bpy.data.meshes, bpy.data.materials):
        for b in list(blk):
            blk.remove(b)
    _mats.clear()


class Model:
    """Collects bmesh parts per role; build() turns each role into one bevelled mesh."""

    def __init__(self, name):
        self.name = name
        self.bm = {}
        self.bevel = {}
        self.M = None            # optional 3x3 matrix applied to every point of ball()/limb() (game axes)
        self.part = None         # while set, new geometry goes to separate '<role>.<part>' nodes (see part_on)

    def part_on(self, name):
        """Geometry from here to part_off() becomes its own node(s) named '<role>.<name>': the game animates them
        (mag = magazine, slide = pistol slide, bolt = charging handle / bolt handle, pump = shotgun forend)."""
        self.part = name

    def part_off(self):
        self.part = None

    def pt(self, x, y, z):
        v = Vector((x, y, z))
        if self.M is not None:
            v = self.M @ v
        return P(v.x, v.y, v.z)

    def ball(self, role, c, r, seg=8, rings=4, sy=1.0):
        """A (squashed) sphere: knuckles, fingertips and joints."""
        bm = self._b(role)
        rows = []
        for j in range(rings + 1):
            a = math.pi * j / rings
            ring = []
            for i in range(seg):
                t = i / seg * math.tau
                ring.append(bm.verts.new(self.pt(c[0] + r * math.sin(a) * math.cos(t), c[1] + r * sy * math.cos(a), c[2] + r * math.sin(a) * math.sin(t))))
            rows.append(ring)
        for j in range(rings):
            for i in range(seg):
                k = (i + 1) % seg
                try:
                    bm.faces.new([rows[j][i], rows[j][k], rows[j + 1][k], rows[j + 1][i]])
                except ValueError:
                    pass

    def limb(self, role, a, b, r0, r1, seg=8, ends=True):
        """A tapered tube from a to b with round ends (finger segments, thumbs, forearms)."""
        bm = self._b(role)
        a, b = Vector(a), Vector(b)
        d = (b - a)
        L = d.length
        d.normalize()
        t = Vector((0, 1, 0)) if abs(d.y) < 0.9 else Vector((1, 0, 0))
        u = d.cross(t).normalized()
        v = d.cross(u).normalized()
        ra, rb = [], []
        for i in range(seg):
            ang = i / seg * math.tau
            c, s_ = math.cos(ang), math.sin(ang)
            ra.append(bm.verts.new(self.pt(*(a + (u * c + v * s_) * r0))))
            rb.append(bm.verts.new(self.pt(*(b + (u * c + v * s_) * r1))))
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new([ra[i], ra[j], rb[j], rb[i]])
        bm.faces.new(ra[::-1])      # end caps keep each tube a closed shell, so its normals face outwards
        bm.faces.new(rb)
        if ends:
            self.ball(role, tuple(a), r0, seg, 4)
            self.ball(role, tuple(b), r1, seg, 4)

    def _b(self, role):
        key = role if not self.part else role + '.' + self.part
        if key not in self.bm:
            self.bm[key] = bmesh.new()
        return self.bm[key]

    # ---- primitives (all dimensions in game axes) ----
    def box(self, role, size, at, rot=(0, 0, 0), taper=None):
        """Box centred at `at`; rot = euler radians in game axes; taper=('z', .6) narrows the +end of that axis."""
        bm = self._b(role)
        sx, sy, sz = size
        vs = []
        for dx in (-.5, .5):
            for dy in (-.5, .5):
                for dz in (-.5, .5):
                    kx = ky = kz = 1.0
                    if taper:
                        ax, f = taper
                        k = 1 + (f - 1) * ({'x': dx, 'y': dy, 'z': dz}[ax] + .5)
                        if ax == 'x':
                            ky = kz = k
                        elif ax == 'y':
                            kx = kz = k
                        else:
                            kx = ky = k
                    vs.append(Vector((dx * sx * kx, dy * sy * ky, dz * sz * kz)))
        self._emit(bm, vs, rot, at, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])

    def _emit(self, bm, vs, rot, at, faces):
        from mathutils import Euler
        e = Euler(rot, 'XYZ')
        vv = []
        for p in vs:
            q = e.to_matrix() @ p
            vv.append(bm.verts.new(P(q.x + at[0], q.y + at[1], q.z + at[2])))
        for f in faces:
            try:
                bm.faces.new([vv[i] for i in f])
            except ValueError:
                pass

    def prism(self, role, pts, width, x=0.0, rot=(0, 0, 0), at=(0, 0, 0)):
        """Extrude a side profile [(z, y), ...] sideways to `width`, centred on x."""
        bm = self._b(role)
        n = len(pts)
        l = [bm.verts.new(P(x - width / 2, y, z)) for z, y in pts]
        r = [bm.verts.new(P(x + width / 2, y, z)) for z, y in pts]
        try:
            bm.faces.new(l[::-1])
            bm.faces.new(r)
        except ValueError:
            pass
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new([l[i], l[j], r[j], r[i]])
            except ValueError:
                pass

    def cyl(self, role, r, length, at, axis='z', r2=None, seg=16, cap=True):
        """Cylinder (or cone when r2 is given) along game axis x/y/z, centred at `at`."""
        bm = self._b(role)
        r2 = r if r2 is None else r2
        a = []
        b = []
        for i in range(seg):
            t = i / seg * math.tau
            c, s = math.cos(t), math.sin(t)
            if axis == 'z':
                a.append(bm.verts.new(P(at[0] + c * r, at[1] + s * r, at[2] - length / 2)))
                b.append(bm.verts.new(P(at[0] + c * r2, at[1] + s * r2, at[2] + length / 2)))
            elif axis == 'y':
                a.append(bm.verts.new(P(at[0] + c * r, at[1] - length / 2, at[2] + s * r)))
                b.append(bm.verts.new(P(at[0] + c * r2, at[1] + length / 2, at[2] + s * r2)))
            else:
                a.append(bm.verts.new(P(at[0] - length / 2, at[1] + c * r, at[2] + s * r)))
                b.append(bm.verts.new(P(at[0] + length / 2, at[1] + c * r2, at[2] + s * r2)))
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new([a[i], a[j], b[j], b[i]])
        if cap:
            bm.faces.new(a[::-1])
            bm.faces.new(b)

    def ribbon(self, role, path, thick, width, x=0.0, closed=False):
        """A thick polyline in the (z, y) plane extruded sideways (trigger guards, curved rails)."""
        pts = []
        n = len(path)
        left, right = [], []
        for i, (z, y) in enumerate(path):
            if i == 0:
                dz, dy = path[1][0] - z, path[1][1] - y
            elif i == n - 1:
                dz, dy = z - path[i - 1][0], y - path[i - 1][1]
            else:
                dz, dy = path[i + 1][0] - path[i - 1][0], path[i + 1][1] - path[i - 1][1]
            ln = math.hypot(dz, dy) or 1
            nz, ny = -dy / ln, dz / ln
            left.append((z + nz * thick / 2, y + ny * thick / 2))
            right.append((z - nz * thick / 2, y - ny * thick / 2))
        self.prism(role, left + right[::-1], width, x)

    def lines(self, role, zs, y0, y1, xs, depth=0.0012, w=0.0016):
        """Thin vertical grooves (serrations) at each z, on the faces at x in xs (side +/-)."""
        for z in zs:
            for sx in xs:
                self.box(role, (depth * 2, y1 - y0, w), (sx, (y0 + y1) / 2, z))

    # ---- finish ----
    def build(self, bevel=0.0016, seg=1):
        objs = []
        self.bevel.setdefault('dark', 0)
        self.bevel.setdefault('acc', 0)
        self.bevel.setdefault('heat', 0)
        self.bevel.setdefault('glass', 0)
        for key, bm in self.bm.items():
            role = key.split('.')[0]
            if not bm.faces:
                continue
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            me = bpy.data.meshes.new(self.name + '_' + key)
            bm.to_mesh(me)
            bm.free()
            ob = bpy.data.objects.new(key, me)  # mesh node named by role (and part)
            bpy.context.collection.objects.link(ob)
            ob.data.materials.append(mat(role))
            bv = self.bevel.get(role, bevel)
            sg = seg
            if isinstance(bv, tuple):
                bv, sg = bv
            if bv:
                bpy.context.view_layer.objects.active = ob
                md = ob.modifiers.new('bev', 'BEVEL')
                md.width = bv
                md.segments = sg
                md.limit_method = 'ANGLE'
                md.angle_limit = math.radians(32)
                bpy.ops.object.modifier_apply(modifier='bev')
            bpy.ops.object.select_all(action='DESELECT')
            ob.select_set(True)
            bpy.context.view_layer.objects.active = ob
            try:
                bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
            except Exception:
                bpy.ops.object.shade_smooth()
            objs.append(ob)
            print('   ', key, len(ob.data.polygons), 'faces')
        self.bm = {}
        return objs

    def export(self, objs=None):
        objs = objs or [o for o in bpy.context.scene.objects if o.type == 'MESH']
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        path = os.path.join(OUT, 'w_' + self.name + '.glb')
        bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                                  export_animations=False, export_yup=True)
        tris = sum(len(o.data.polygons) for o in objs)
        print('  wrote', os.path.basename(path), os.path.getsize(path) // 1024, 'KB', len(objs), 'meshes')


# =====================================================================================================
#  PISTOL: tall slide with serrations, ejection port and sights, a polymer frame with an accessory rail,
#  a guard, a raked textured grip and a base plate; light lines on the slide, a coil strip on the frame.
# =====================================================================================================
def pistol():
    m = Model('pistol')
    W = 0.040  # slide width
    # slide: chamfered top, angled muzzle end, open underside
    m.part_on('slide')
    m.prism('body', [(-0.118, 0.034), (-0.118, 0.086), (-0.112, 0.094), (0.190, 0.094), (0.222, 0.086), (0.232, 0.070), (0.232, 0.040), (0.222, 0.034)], W)
    # ejection port on the right face: a dark opening with a steel chamber lip
    m.box('dark', (0.0016, 0.022, 0.056), (W / 2 - 0.0002, 0.066, 0.046))
    m.box('metal', (0.0018, 0.003, 0.050), (W / 2 - 0.0001, 0.0555, 0.046))
    # top: slim accent rib between the sights, plus a flat plate for an optic
    m.box('acc', (0.0032, 0.0012, 0.205), (0, 0.0948, 0.060))
    m.box('metal', (0.024, 0.0028, 0.052), (0, 0.0948, 0.040))
    # rear face: firing-pin hole and a chamber indicator
    m.cyl('dark', 0.0045, 0.0024, (0, 0.062, -0.118), 'z', seg=12)
    m.box('acc', (0.012, 0.003, 0.0016), (0, 0.082, -0.1182))
    # serrations: rear set and front set, both faces
    m.lines('dark', [-0.106 + 0.0085 * i for i in range(7)], 0.046, 0.088, (-W / 2, W / 2))
    m.lines('dark', [0.168 + 0.0085 * i for i in range(4)], 0.044, 0.084, (-W / 2, W / 2))
    # light lines low on the slide, both sides
    for sx in (-1, 1):
        m.box('acc', (0.0014, 0.0035, 0.140), (sx * (W / 2 + 0.0001), 0.0485, 0.034))
    # sights: post with a lit dot, notched rear
    m.box('metal', (0.006, 0.014, 0.008), (0, 0.101, 0.216))
    m.box('acc', (0.0026, 0.0026, 0.0016), (0, 0.1065, 0.2203))
    for sx in (-1, 1):
        m.box('metal', (0.014, 0.012, 0.010), (sx * 0.0105, 0.1, -0.104))
    # barrel crown, bore and a light ring
    m.cyl('metal', 0.0125, 0.034, (0, 0.063, 0.236), 'z', seg=20)
    m.cyl('dark', 0.0072, 0.036, (0, 0.063, 0.2365), 'z', seg=14)
    m.cyl('acc', 0.0138, 0.003, (0, 0.063, 0.2265), 'z', seg=20)
    m.part_off()
    # frame / dust cover with rail slots and the coil strip
    m.prism('grip', [(-0.108, 0.034), (-0.108, 0.004), (0.050, -0.002), (0.056, 0.018), (0.176, 0.018), (0.196, 0.026), (0.196, 0.034)], 0.034)
    for i in range(3):
        m.box('dark', (0.036, 0.0035, 0.004), (0, 0.022, 0.092 + i * 0.026))
    for sx in (-1, 1):
        m.box('heat', (0.0014, 0.0045, 0.110), (sx * 0.0176, 0.0225, 0.0))
    # guard: a rounded loop in front of the grip, then trigger and slide-lock
    m.ribbon('grip', [(0.058, 0.020), (0.094, 0.004), (0.100, -0.020), (0.078, -0.046), (0.036, -0.054), (-0.030, -0.046)], 0.0105, 0.030)
    m.prism('metal', [(0.030, 0.002), (0.048, 0.002), (0.040, -0.030), (0.029, -0.030)], 0.0085)
    m.box('metal', (0.006, 0.010, 0.026), (0.0212, 0.042, -0.040))
    # grip: raked, beavertail, base plate, coloured panels, texture bands and lit gauges
    GF = [(-0.126, 0.026), (-0.128, 0.010), (-0.163, -0.178), (-0.082, -0.178), (-0.040, -0.012), (0.040, 0.0), (0.040, 0.034), (-0.100, 0.034)]
    m.prism('grip', GF, 0.034)
    PN = [(-0.120, -0.014), (-0.156, -0.168), (-0.088, -0.168), (-0.047, -0.026)]   # side panel outline (rear-top, rear-bottom, front-bottom, front-top)
    for sx in (-1, 1):
        m.prism('body', PN, 0.0016, sx * 0.0178)
    for i in range(6):
        y = -0.038 - i * 0.024
        t = (-0.014 - y) / 0.154
        rear, front = PN[0][0] + (PN[1][0] - PN[0][0]) * t, PN[3][0] + (PN[2][0] - PN[3][0]) * t
        for sx in (-1, 1):
            m.box('dark', (0.0017, 0.0016, (front - rear) * 0.78), (sx * 0.0188, y, (rear + front) / 2))
    m.part_on('mag')      # the magazine: a black body hidden in the grip, and the base plate under it
    m.prism('dark', [(-0.121, -0.020), (-0.158, -0.176), (-0.086, -0.176), (-0.049, -0.030)], 0.028)
    m.prism('metal', [(-0.169, -0.178), (-0.166, -0.194), (-0.078, -0.194), (-0.080, -0.178)], 0.038)
    m.part_off()
    for sx in (-1, 1):
        m.box('acc', (0.0012, 0.060, 0.006), (sx * 0.0190, -0.098, -0.056))
    m.build()
    return m


# =====================================================================================================
#  KNIFE: a combat blade. Steel flats, a dark spine with a saw-back, a cutting edge that glows along its grind,
#  a cross guard, a wrapped handle with a lit strip, a pommel with a lanyard loop.
#  Handle runs along z (blade points +z); the broad faces look sideways (x).
# =====================================================================================================
def knife():
    m = Model('knife')
    T = 0.0042                    # half thickness at the spine
    z0, z1 = 0.030, 0.318         # ricasso -> tip
    N = 22
    def spine(z):
        return 0.0215 if z < 0.205 else 0.0215 * (1 - ((z - 0.205) / (z1 - 0.205)) ** 1.5)
    def edge(z):
        if z < 0.10:
            return -0.0215 - 0.0012 * (z - z0) / 0.07
        return -0.0227 * (1 - ((z - 0.10) / (z1 - 0.10)) ** 1.9)
    rows = []
    for i in range(N + 1):
        z = z0 + (z1 - z0) * i / N
        sp, ed = spine(z), edge(z)
        if i == N:
            sp = ed = 0.0
        gr = ed + (sp - ed) * 0.26          # where the glowing edge facet ends
        rows.append((z, sp, gr, ed))
    bm_f, bm_e, bm_s = m._b('metal'), m._b('acc'), m._b('dark')
    def V(x, y, z):
        return P(x, y, z)
    vl = []
    for z, sp, gr, ed in rows:
        vl.append([bm_f.verts.new(V(-T, sp, z)), bm_f.verts.new(V(-T, gr, z)), bm_f.verts.new(V(T, gr, z)), bm_f.verts.new(V(T, sp, z))])
    # separate vertices for the glowing facets and the spine so each role has its own mesh
    ve = [[bm_e.verts.new(V(-T, gr, z)), bm_e.verts.new(V(0, ed, z)), bm_e.verts.new(V(T, gr, z))] for z, sp, gr, ed in rows]
    vs = [[bm_s.verts.new(V(-T, sp, z)), bm_s.verts.new(V(T, sp, z))] for z, sp, gr, ed in rows]
    for i in range(N):
        a, b = vl[i], vl[i + 1]
        bm_f.faces.new([a[0], b[0], b[1], a[1]])          # left flat
        bm_f.faces.new([a[2], b[2], b[3], a[3]])          # right flat
        c, d = ve[i], ve[i + 1]
        bm_e.faces.new([c[0], d[0], d[1], c[1]])          # left edge facet
        bm_e.faces.new([c[1], d[1], d[2], c[2]])          # right edge facet
        e, f = vs[i], vs[i + 1]
        bm_s.faces.new([e[0], f[0], f[1], e[1]])          # spine top
    bm_f.faces.new([vl[0][0], vl[0][1], vl[0][2], vl[0][3]][::-1])
    # a raised dark spine rib and the saw-back teeth
    m.box('dark', (T * 2 + 0.0006, 0.0026, 0.168), (0, 0.0195, 0.126))
    for i in range(7):
        z = 0.050 + i * 0.0105
        m.prism('dark', [(z, 0.0214), (z + 0.0050, 0.0214), (z + 0.0105, 0.0244), (z + 0.0105, 0.0214)], T * 2 + 0.0008)
    # fuller: a dark groove on each flat
    for sx in (-1, 1):
        m.box('dark', (0.0012, 0.0034, 0.17), (sx * T, 0.0105, 0.124))
        m.box('acc', (0.0010, 0.0013, 0.045), (sx * (T + 0.0001), 0.0105, 0.062))   # a short lit slot at the base
    # guard with a finger choil, handle swells, wraps, lit strip, pommel and lanyard loop
    m.box('body', (0.0120, 0.056, 0.0125), (0, 0.0, 0.0245))
    m.box('metal', (0.0070, 0.0125, 0.012), (0, -0.0335, 0.0245))
    m.cyl('grip', 0.0150, 0.050, (0, 0, -0.0050), 'z', r2=0.0160, seg=10)
    m.cyl('grip', 0.0160, 0.050, (0, 0, -0.0550), 'z', r2=0.0150, seg=10)
    m.cyl('body', 0.0140, 0.018, (0, 0, -0.0990), 'z', r2=0.0165, seg=10)
    m.cyl('metal', 0.0160, 0.006, (0, 0, -0.1105), 'z', r2=0.0150, seg=10)
    for i in range(9):
        m.cyl('dark', 0.0166 if i % 2 == 0 else 0.0158, 0.0022, (0, 0, 0.012 - i * 0.0108), 'z', seg=10)
    m.box('heat', (0.0034, 0.0016, 0.085), (0, 0.0176, -0.040))
    m.ribbon('metal', [(-0.1105, 0.010), (-0.128, 0.012), (-0.134, 0.0), (-0.128, -0.012), (-0.1105, -0.010)], 0.0040, 0.0070)
    m.bevel['metal'] = (0.0008, 1)
    m.build()
    return m


# =====================================================================================================
#  LONG GUNS share one vocabulary: a painted receiver (body), polymer furniture (grip), steel barrels and bolts
#  (metal), dark cuts, thin light lines (acc) and the coil strip (heat). The receiver top sits at y = .082 so the
#  game's optics (red dot, holo, scope) bolt onto the rail at the heights its OPTICS table expects.
# =====================================================================================================
def rail(m, z0, z1, y=0.082, w=0.022):
    """A picatinny-style top rail: a strip with cross slots."""
    m.box('metal', (w, 0.0075, z1 - z0), (0, y - 0.0037, (z0 + z1) / 2))
    n = int((z1 - z0) / 0.0215)
    for i in range(n):
        m.box('dark', (w + 0.0004, 0.0012, 0.0075), (0, y + 0.0003, z0 + 0.0125 + i * 0.0215))


def vents(m, z0, z1, n, y0, y1, xs, role='dark'):
    for i in range(n):
        z = z0 + (z1 - z0) * (i + 0.5) / n
        for sx in xs:
            m.box(role, (0.0016, y1 - y0, (z1 - z0) / n * 0.5), (sx, (y0 + y1) / 2, z))


def grip_raked(m, zt, zb, y0, y1, w, role='grip', front=0.075):
    """A raked pistol grip below the receiver: top edge at zt (rear), bottom edge at zb (rear)."""
    m.prism(role, [(zt, y0), (zb, y1), (zb + front * 0.92, y1), (zt + front, y0)], w)
    for i in range(5):
        y = y0 - 0.026 - i * 0.026
        t = (y0 - y) / (y0 - y1)
        zr = zt + (zb - zt) * t
        for sx in (-1, 1):
            m.box('dark', (0.0017, 0.0016, front * 0.78), (sx * (w / 2 + 0.0003), y, zr + front * 0.5))


def guard(m, z0, z1, y0=-0.040, dy=0.052):
    m.ribbon('grip', [(z1, y0 + 0.002), (z1 + 0.012, y0 - 0.020), (z1 - 0.012, y0 - dy), (z0 + 0.03, y0 - dy), (z0, y0 - 0.012)], 0.0095, 0.030)
    m.prism('metal', [(z1 - 0.040, y0 + 0.002), (z1 - 0.024, y0 + 0.002), (z1 - 0.032, y0 - 0.030), (z1 - 0.044, y0 - 0.030)], 0.0085)


def smg():
    m = Model('smg')
    W = 0.060
    # receiver: boxy with a sloped nose
    m.prism('body', [(-0.205, -0.046), (-0.205, 0.070), (-0.195, 0.078), (0.200, 0.078), (0.236, 0.062), (0.262, 0.040), (0.262, -0.046)], W)
    rail(m, -0.180, 0.195)
    m.box('dark', (W + 0.0016, 0.026, 0.060), (0, 0.030, 0.020))           # ejection port, right face
    m.box('metal', (0.0016, 0.004, 0.062), (W / 2 + 0.0004, 0.020, 0.020))
    m.box('acc', (0.0016, 0.004, 0.230), (W / 2 + 0.0002, 0.050, -0.030))
    m.box('acc', (0.0016, 0.004, 0.230), (-W / 2 - 0.0002, 0.050, -0.030))
    # shroud with vents and a coil strip
    m.prism('grip', [(0.200, -0.040), (0.200, 0.066), (0.345, 0.056), (0.345, -0.040)], 0.056)
    vents(m, 0.215, 0.335, 5, 0.004, 0.046, (-0.0285, 0.0285))
    for sx in (-1, 1):
        m.box('heat', (0.0015, 0.0050, 0.110), (sx * 0.0286, -0.020, 0.268))
    # barrel / suppressor
    m.cyl('metal', 0.0150, 0.200, (0, 0.012, 0.445), 'z', seg=18)
    m.cyl('metal', 0.0172, 0.030, (0, 0.012, 0.556), 'z', seg=18)
    m.cyl('dark', 0.0078, 0.032, (0, 0.012, 0.558), 'z', seg=12)
    m.cyl('acc', 0.0178, 0.004, (0, 0.012, 0.346), 'z', seg=18)
    m.cyl('acc', 0.0178, 0.004, (0, 0.012, 0.540), 'z', seg=18)
    # stock: two arms and a butt pad
    for sx in (-1, 1):
        m.prism('grip', [(-0.205, 0.058), (-0.372, 0.040), (-0.372, 0.016), (-0.205, 0.030)], 0.010, sx * 0.026)
    m.prism('grip', [(-0.372, 0.052), (-0.396, 0.056), (-0.396, -0.056), (-0.372, -0.052)], 0.050)
    m.box('acc', (0.030, 0.0016, 0.0016), (0, 0.0, -0.3972))
    # grip, trigger guard and a curved magazine with a lit window
    grip_raked(m, -0.142, -0.178, -0.044, -0.200, 0.036, front=0.074)
    guard(m, -0.040, 0.050)
    m.part_on('mag')
    m.prism('grip', [(0.030, -0.046), (0.092, -0.046), (0.108, -0.214), (0.050, -0.230)], 0.036)
    m.prism('metal', [(0.049, -0.230), (0.109, -0.214), (0.110, -0.226), (0.050, -0.242)], 0.040)
    for sx in (-1, 1):
        m.box('acc', (0.0012, 0.100, 0.007), (sx * 0.0186, -0.130, 0.083), rot=(-0.13, 0, 0))
    m.part_off()
    # charging handle and selector
    m.part_on('bolt')
    m.box('metal', (0.022, 0.010, 0.016), (0, 0.083, -0.150))
    m.part_off()
    m.box('metal', (0.006, 0.014, 0.014), (-W / 2 - 0.002, 0.004, -0.120))
    m.box('acc', (0.0016, 0.004, 0.004), (-W / 2 - 0.0046, 0.010, -0.120))
    m.build()
    return m


def rifle():
    m = Model('rifle')
    W = 0.068
    # receiver, upper and lower
    m.prism('body', [(-0.285, -0.005), (-0.285, 0.074), (-0.275, 0.082), (0.300, 0.082), (0.322, 0.070), (0.322, -0.005)], W)
    m.prism('grip', [(-0.230, -0.050), (-0.230, -0.004), (0.200, -0.004), (0.200, -0.050)], 0.062)
    rail(m, -0.255, 0.325)
    m.box('dark', (W + 0.0016, 0.028, 0.072), (0, 0.040, 0.040))           # ejection port
    m.box('metal', (0.0016, 0.004, 0.074), (W / 2 + 0.0004, 0.028, 0.040))
    for sx in (-1, 1):
        m.box('acc', (0.0016, 0.004, 0.300), (sx * (W / 2 + 0.0002), 0.056, 0.010))
    # handguard with rail slots and a coil strip
    m.prism('grip', [(0.322, -0.058), (0.322, 0.066), (0.660, 0.060), (0.660, -0.058)], 0.062)
    vents(m, 0.345, 0.650, 9, -0.040, 0.044, (-0.0312, 0.0312))
    vents(m, 0.345, 0.650, 9, -0.058, -0.048, (-0.0312, 0.0312), 'dark')
    for sx in (-1, 1):
        m.box('heat', (0.0015, 0.0055, 0.250), (sx * 0.0313, 0.050, 0.490))
    rail(m, 0.330, 0.655, y=0.0715 + 0.0105, w=0.020)
    # barrel, gas block, front post and a slotted flash hider
    m.cyl('metal', 0.0112, 0.150, (0, 0.016, 0.735), 'z', seg=14)
    m.cyl('metal', 0.0200, 0.100, (0, 0.016, 0.860), 'z', seg=16)
    m.cyl('dark', 0.0072, 0.104, (0, 0.016, 0.862), 'z', seg=12)
    for i in range(3):
        m.box('dark', (0.046, 0.0035, 0.052), (0, 0.016, 0.845 + i * 0.0), rot=(0, 0, i * math.pi / 3))
    m.cyl('acc', 0.0207, 0.004, (0, 0.016, 0.800), 'z', seg=16)
    m.box('metal', (0.008, 0.022, 0.010), (0, 0.098, 0.640))
    # stock: buffer tube, cheek riser and a butt pad
    m.cyl('grip', 0.0210, 0.215, (0, 0.012, -0.385), 'z', seg=12)
    m.prism('grip', [(-0.285, 0.070), (-0.560, 0.066), (-0.600, 0.040), (-0.600, -0.106), (-0.560, -0.090), (-0.285, -0.004)], 0.050)
    m.prism('metal', [(-0.600, 0.040), (-0.612, 0.036), (-0.612, -0.100), (-0.600, -0.106)], 0.054)
    m.box('acc', (0.0016, 0.060, 0.0030), (0.0265, -0.030, -0.455))
    m.box('acc', (0.0016, 0.060, 0.0030), (-0.0265, -0.030, -0.455))
    # grip, guard, magazine
    grip_raked(m, -0.215, -0.255, -0.050, -0.215, 0.038, front=0.082)
    guard(m, -0.100, 0.060, y0=-0.050, dy=0.050)
    m.part_on('mag')
    m.prism('grip', [(0.020, -0.050), (0.110, -0.050), (0.150, -0.240), (0.074, -0.256)], 0.040)
    m.prism('metal', [(0.073, -0.256), (0.151, -0.240), (0.152, -0.252), (0.076, -0.268)], 0.044)
    for sx in (-1, 1):
        m.box('acc', (0.0012, 0.110, 0.007), (sx * 0.0206, -0.150, 0.110), rot=(-0.19, 0, 0))
    m.part_off()
    m.part_on('bolt')
    m.box('metal', (0.024, 0.012, 0.020), (0, 0.090, -0.230))               # charging handle
    m.part_off()
    m.box('metal', (0.006, 0.016, 0.016), (-W / 2 - 0.002, -0.020, -0.130))
    m.box('acc', (0.0016, 0.004, 0.004), (-W / 2 - 0.0046, -0.014, -0.130))
    m.build()
    return m


def shotgun():
    m = Model('shotgun')
    W = 0.080
    # receiver
    m.prism('body', [(-0.250, -0.052), (-0.250, 0.070), (-0.240, 0.082), (0.170, 0.082), (0.210, 0.062), (0.210, -0.052)], W)
    rail(m, -0.200, 0.160)
    m.box('dark', (W + 0.0016, 0.030, 0.082), (0, 0.030, -0.010))
    m.box('metal', (0.0016, 0.004, 0.084), (W / 2 + 0.0004, 0.014, -0.010))
    for sx in (-1, 1):
        m.box('acc', (0.0016, 0.004, 0.260), (sx * (W / 2 + 0.0002), 0.056, -0.040))
    # barrel over a magazine tube, a heat shield with vents, end cap, bead sight
    m.cyl('metal', 0.0240, 0.640, (0, 0.050, 0.520), 'z', seg=18)
    m.prism('grip', [(0.230, 0.026), (0.230, 0.074), (0.560, 0.072), (0.560, 0.026)], 0.044)
    vents(m, 0.250, 0.545, 9, 0.034, 0.066, (-0.0222, 0.0222))
    m.cyl('metal', 0.0215, 0.640, (0, -0.014, 0.500), 'z', seg=16)
    m.cyl('metal', 0.0262, 0.030, (0, -0.014, 0.832), 'z', seg=16)
    m.cyl('dark', 0.0190, 0.034, (0, 0.050, 0.838), 'z', seg=16)
    m.cyl('acc', 0.0268, 0.004, (0, 0.050, 0.800), 'z', seg=16)
    m.box('metal', (0.006, 0.014, 0.010), (0, 0.104, 0.800))
    # pump forend
    m.part_on('pump')
    m.prism('grip', [(0.250, -0.082), (0.250, 0.012), (0.470, 0.012), (0.470, -0.082)], 0.080)
    for i in range(8):
        for sx in (-1, 1):
            m.box('dark', (0.0018, 0.070, 0.0045), (sx * 0.0405, -0.035, 0.272 + i * 0.026))
    for sx in (-1, 1):
        m.box('heat', (0.0015, 0.0055, 0.190), (sx * 0.0407, -0.010, 0.360))
    m.part_off()
    # stock with a cheek rest, a pad and a pistol grip
    m.prism('grip', [(-0.250, 0.060), (-0.560, 0.050), (-0.640, 0.016), (-0.650, -0.100), (-0.560, -0.082), (-0.250, -0.030)], 0.050)
    m.prism('metal', [(-0.650, 0.016), (-0.664, 0.010), (-0.664, -0.104), (-0.650, -0.100)], 0.056)
    m.box('acc', (0.0016, 0.060, 0.0030), (0.0255, -0.020, -0.470))
    m.box('acc', (0.0016, 0.060, 0.0030), (-0.0255, -0.020, -0.470))
    grip_raked(m, -0.200, -0.238, -0.052, -0.215, 0.040, front=0.078)
    guard(m, -0.120, 0.045, y0=-0.052, dy=0.050)
    # a side-saddle of shells on the left of the receiver: brass-coloured caps
    for i in range(4):
        m.cyl('dark', 0.0100, 0.048, (-W / 2 - 0.008, 0.030 - i * 0.0, -0.170 + i * 0.045), 'y', seg=10)
        m.cyl('acc', 0.0102, 0.010, (-W / 2 - 0.008, 0.056, -0.170 + i * 0.045), 'y', seg=10)
    # ghost-ring rear sight
    m.ribbon('metal', [(-0.200, 0.084), (-0.200, 0.104), (-0.190, 0.112), (-0.180, 0.104), (-0.180, 0.084)], 0.0035, 0.020)
    m.build()
    return m


def sniper():
    m = Model('sniper')
    W = 0.062
    # receiver and a long free-floated barrel with a brake
    m.prism('body', [(-0.255, -0.050), (-0.255, 0.056), (-0.245, 0.066), (0.440, 0.066), (0.470, 0.050), (0.470, -0.050)], W)
    m.cyl('metal', 0.0170, 0.140, (0, 0.010, 0.540), 'z', seg=16, r2=0.0150)
    m.cyl('metal', 0.0150, 0.640, (0, 0.010, 0.890), 'z', seg=14)
    m.cyl('metal', 0.0230, 0.100, (0, 0.010, 1.230), 'z', seg=16)
    m.cyl('dark', 0.0072, 0.104, (0, 0.010, 1.232), 'z', seg=12)
    for i in range(4):
        for sx in (-1, 1):
            m.box('dark', (0.0016, 0.020, 0.012), (sx * 0.0232, 0.010, 1.190 + i * 0.022))
    m.cyl('acc', 0.0238, 0.004, (0, 0.010, 1.160), 'z', seg=16)
    for i in range(6):
        m.box('dark', (0.0008, 0.0016, 0.060), (0.0150, 0.010 + 0.0, 0.62 + i * 0.1), rot=(0, 0, 0))
    # handguard / chassis rail
    m.prism('grip', [(0.300, -0.050), (0.300, 0.054), (0.560, 0.050), (0.560, -0.050)], 0.056)
    vents(m, 0.316, 0.550, 7, -0.030, 0.034, (-0.0282, 0.0282))
    for sx in (-1, 1):
        m.box('heat', (0.0015, 0.0055, 0.200), (sx * 0.0283, 0.040, 0.430))
        m.box('acc', (0.0016, 0.004, 0.260), (sx * (W / 2 + 0.0002), 0.040, 0.050))
    # scope (the game's lenses sit at its two ends): tube, bells, turrets, rings and a mount
    m.cyl('metal', 0.0360, 0.360, (0, 0.140, 0.080), 'z', seg=20)
    m.cyl('metal', 0.0450, 0.060, (0, 0.140, 0.270), 'z', seg=20, r2=0.0380)
    m.cyl('metal', 0.0420, 0.050, (0, 0.140, -0.110), 'z', seg=20, r2=0.0360)
    m.cyl('acc', 0.0452, 0.004, (0, 0.140, 0.243), 'z', seg=20)
    m.cyl('acc', 0.0424, 0.004, (0, 0.140, -0.086), 'z', seg=20)
    m.cyl('metal', 0.0120, 0.030, (0, 0.182, 0.080), 'y', seg=12)
    m.cyl('metal', 0.0120, 0.030, (0.0420, 0.140, 0.080), 'x', seg=12)
    for z in (0.000, 0.160):
        m.prism('metal', [(z - 0.020, 0.066), (z - 0.016, 0.102), (z + 0.016, 0.102), (z + 0.020, 0.066)], 0.034)
        m.cyl('metal', 0.0400, 0.020, (0, 0.140, z), 'z', seg=20)
    # bolt handle, magazine, bipod legs folded under the chassis
    m.part_on('bolt')
    m.prism('metal', [(-0.100, 0.026), (-0.080, 0.026), (-0.080, 0.014), (-0.100, 0.014)], 0.050, 0.056)
    m.cyl('body', 0.0130, 0.026, (0.082, 0.020, -0.090), 'x', seg=10)
    m.part_off()
    m.part_on('mag')
    m.prism('grip', [(0.040, -0.050), (0.120, -0.050), (0.126, -0.150), (0.054, -0.150)], 0.034)
    m.prism('metal', [(0.053, -0.150), (0.127, -0.150), (0.128, -0.160), (0.055, -0.160)], 0.038)
    m.part_off()
    for sx in (-1, 1):
        m.box('metal', (0.008, 0.012, 0.200), (sx * 0.020, -0.056, 0.440))
    # stock: cheek riser, adjustable butt pad, grip
    m.prism('grip', [(-0.255, 0.050), (-0.520, 0.062), (-0.640, 0.044), (-0.650, -0.110), (-0.540, -0.100), (-0.255, -0.020)], 0.050)
    m.prism('metal', [(-0.650, 0.044), (-0.664, 0.038), (-0.664, -0.114), (-0.650, -0.110)], 0.054)
    m.box('acc', (0.0016, 0.070, 0.0030), (0.0255, -0.025, -0.560))
    m.box('acc', (0.0016, 0.070, 0.0030), (-0.0255, -0.025, -0.560))
    grip_raked(m, -0.205, -0.240, -0.050, -0.210, 0.038, front=0.078)
    guard(m, -0.110, 0.050, y0=-0.050, dy=0.048)
    m.build()
    return m


# =====================================================================================================
#  FIST: a gloved right hand closed round a grip. Built around a vertical grip (axis y, front +z, hand on the
#  right); `hold` turns it to close round a horizontal handle (a knife, a handguard) instead.
#  Fingers are chains of rounded segments with knuckles; the thumb crosses behind the grip; a knuckle plate
#  and a lit seam sit on the back of the hand; a wide cuff leaves room for the sleeve.
# =====================================================================================================
def fist(name, a, b, hold=False):
    """a = grip half width (x), b = grip half depth (z). Origin = middle of the grip."""
    m = Model(name)
    if hold:
        m.M = __import__('mathutils').Matrix.Rotation(math.radians(90), 3, 'X')   # (x, y, z) -> (x, -z, y)
    gl = 'glove'
    r = 0.0112
    tops = [0.0325, 0.0108, -0.0108, -0.0325]
    for k, y in enumerate(tops):
        sc = 1.0 - 0.07 * (k == 3)
        A = (a + 0.016, y, -b + 0.012)
        B = (a + 0.0095, y, b * 0.52)
        C = (a * 0.30, y - 0.001 * k, b + 0.0085)
        D = (-a * 0.80, y - 0.002 * k, b * 0.50 + 0.001)
        m.limb(gl, A, B, r * sc, r * 0.95 * sc)
        m.limb(gl, B, C, r * 0.95 * sc, r * 0.90 * sc)
        m.limb(gl, C, D, r * 0.90 * sc, r * 0.80 * sc)
        m.ball(gl, D, r * 0.80 * sc)
        m.ball('body', (A[0] + 0.004, A[1], A[2] - 0.001), r * 0.92 * sc, 8, 4)           # knuckle guards in the weapon's colour
    # back of the hand and wrist
    m.limb(gl, (a + 0.026, 0.045, -b - 0.030), (a + 0.026, -0.045, -b - 0.030), 0.024, 0.021)
    m.limb(gl, (a + 0.027, 0.042, -b - 0.006), (a + 0.027, -0.044, -b - 0.006), 0.0165, 0.0155)
    m.box(gl, (0.030, 0.092, 0.050), (a + 0.022, 0.0, -b - 0.026), rot=(0, 0.12, 0))
    m.box('body', (0.004, 0.070, 0.044), (a + 0.040, 0.0, -b - 0.024), rot=(0, 0.12, 0))     # plate on the back of the hand
    m.box('acc', (0.0016, 0.074, 0.0030), (a + 0.0425, 0.0, -b - 0.006), rot=(0, 0.12, 0))   # lit seam along it
    m.box('acc', (0.0016, 0.074, 0.0030), (a + 0.0420, 0.0, -b - 0.044), rot=(0, 0.12, 0))
    # thumb: over the back of the grip and along its left side
    T = [(a + 0.022, 0.050, -b - 0.020), (a - 0.002, 0.054, -b - 0.020), (-a - 0.012, 0.050, -b + 0.004), (-a - 0.0155, 0.046, b * 0.28)]
    for i in range(len(T) - 1):
        m.limb(gl, T[i], T[i + 1], 0.0118 - 0.0012 * i, 0.0118 - 0.0012 * (i + 1))
    m.ball(gl, T[-1], 0.0098)
    m.ball('body', (T[-1][0], T[-1][1] + 0.001, T[-1][2] - 0.003), 0.0088, 8, 4)
    # cuff, set back from the palm
    m.limb('sleeve', (a + 0.027, 0.0, -b - 0.060), (a + 0.040, -0.004, -b - 0.092), 0.031, 0.033, ends=False)
    m.limb('acc', (a + 0.027, 0.0, -b - 0.057), (a + 0.0285, 0.0, -b - 0.0605), 0.0322, 0.0322, ends=False)
    m.bevel['glove'] = 0
    m.bevel['body'] = 0
    m.build()
    return m


def hands():
    clear()
    print('hand_grip')
    fist('hand_grip', 0.017, 0.040).export()
    clear()
    print('hand_hold')
    fist('hand_hold', 0.0185, 0.0185, hold=True).export()


if __name__ == '__main__':
    import sys
    only = set(sys.argv[sys.argv.index('--') + 1:]) if '--' in sys.argv else None
    for fn in (pistol, knife, smg, rifle, shotgun, sniper):
        if only and fn.__name__ not in only:
            continue
        clear()
        print(fn.__name__)
        mdl = fn()
        mdl.export()
    if not only or 'hands' in only:
        hands()
