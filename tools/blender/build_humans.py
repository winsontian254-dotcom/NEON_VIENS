#!/usr/bin/env python3
"""Realistic human kit for Neon Veins, built from scratch in Blender (bpy) and exported as one GLB.

    python3 tools/blender/build_humans.py [-- body head hair ware]   # needs the bpy module (pip install bpy numpy)

Everything is authored in GAME axes (x right, y up, z forward) at the scale of the game's rig (`rigBuild` in index.html), one
mesh per rig segment, each in the local frame of the node it is mounted on:

    head       the skull and face (sculpted from an ellipsoid with anatomical bumps), eyelids and ears' roots   origin = head centre
    eyes, iris eyeballs and irises (separate meshes, so the game can colour the irises and make them glow)
    ear        both ears
    neck       origin = neck pivot
    torso      jacket and chest                                                                               origin = (0, 1.26, 0)
    pelvis     trousers hips and belt                                                                         origin = (0, .96, 0)
    leg_u      thigh   (origin: hip pivot + (0, -.22, 0))        leg_l   shin (knee pivot + (0, -.22, 0))
    foot       boot    (knee pivot + (0, -.43, .06))
    arm_u      upper arm (shoulder pivot + (0, -.16, 0))         arm_l   forearm (elbow pivot + (0, -.16, 0))
    hand       a relaxed hand, fingers curled (elbow pivot + (0, -.34, 0); the left hand is the same mesh mirrored)
    hair_*     hair styles (head origin)       ware_*  cyberware that follows the face       visor / shades

Every vertex carries COLOR_0 = baked ambient occlusion x small painted details (seams, lips, brows), which the game multiplies
with the skin / cloth colour, and every skin part has UVs so the game can lay a procedural skin texture over it.
"""
import math, os, sys
import numpy as np
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'assets', 'src')
TAU = math.tau


def P(x, y, z):
    """game axes (x right, y up, z forward) -> Blender axes (same convention as build_weapons.py)"""
    return (-x, -z, y)


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def gauss(x, c, s):
    return np.exp(-((x - c) ** 2) / (2 * s * s))


def angdiff(a, b):
    d = (a - b + math.pi) % TAU - math.pi
    return d


# ---------------------------------------------------------------------------------------------------------------------------
#  mesh container (game axes, part-local frame)
# ---------------------------------------------------------------------------------------------------------------------------
class Part:
    def __init__(self, name):
        self.name = name
        self.v = np.zeros((0, 3))
        self.f = []          # faces: tuples of vertex indices
        self.uv = np.zeros((0, 2))
        self.col = np.zeros((0, 3))   # painted detail multiplier (rgb), AO is multiplied in later

    def add(self, pts, uvs=None, cols=None):
        pts = np.asarray(pts, dtype=float).reshape(-1, 3)
        n0 = len(self.v)
        self.v = np.vstack([self.v, pts])
        self.uv = np.vstack([self.uv, np.zeros((len(pts), 2)) if uvs is None else np.asarray(uvs, dtype=float).reshape(-1, 2)])
        self.col = np.vstack([self.col, np.ones((len(pts), 3)) if cols is None else np.asarray(cols, dtype=float).reshape(-1, 3)])
        return n0

    def grid(self, i0, rows, cols, rev=False):
        """quads between consecutive rows of a (rows x cols) vertex grid that starts at index i0 (rev flips the winding)"""
        for r in range(rows - 1):
            for c in range(cols - 1):
                a = i0 + r * cols + c
                q = (a, a + 1, a + cols + 1, a + cols)
                self.f.append(q[::-1] if rev else q)

    def merge(self, other):
        n0 = self.add(other.v, other.uv, other.col)
        for f in other.f:
            self.f.append(tuple(i + n0 for i in f))

    def mirror_x(self):
        m = Part(self.name)
        m.v = self.v * np.array([-1, 1, 1])
        m.f = [tuple(reversed(f)) for f in self.f]
        m.uv, m.col = self.uv.copy(), self.col.copy()
        return m

    def normals(self):
        n = np.zeros_like(self.v)
        for f in self.f:
            p = self.v[list(f)]
            fn = np.cross(p[1] - p[0], p[2] - p[0]) if len(f) >= 3 else np.zeros(3)
            if len(f) == 4:
                fn = np.cross(p[2] - p[0], p[3] - p[1])
            for i in f:
                n[i] += fn
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        return n / np.maximum(ln, 1e-12)


def catmull(pts, n):
    """Catmull-Rom spline through the rows of pts, sampled at n evenly spaced parameter values"""
    pts = np.asarray(pts, dtype=float)
    m = len(pts)
    out = []
    for k in range(n):
        t = k / (n - 1) * (m - 1)
        i = min(int(t), m - 2)
        u = t - i
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, m - 1)]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    return np.array(out)


# ---------------------------------------------------------------------------------------------------------------------------
#  lofts: a stack of superelliptic rings along y (or z)
# ---------------------------------------------------------------------------------------------------------------------------
def loft(part, prof, n=32, axis='y', p=2.2, mod=None, cap0=0.0, cap1=0.0, rows=24, uvscale=(1.0, 1.0), pole=True):
    """prof rows: (t, a, b, c1, c2)  t = position along the axis, a/b = radii (x / depth for y-lofts, x / height for z-lofts),
    c1/c2 = ring centre in the two other axes.  `mod(theta, t, u, v)` -> (radial multiplier, rgb) lets a part add anatomy.
    cap0/cap1: depth of a rounded end (metres) at the start / end of the profile."""
    prof = np.asarray(prof, dtype=float)
    ring_rows = catmull(prof, rows) if rows else prof
    extra0 = []
    extra1 = []
    for cap, lst, sgn, base in ((cap0, extra0, -1, ring_rows[0]), (cap1, extra1, 1, ring_rows[-1])):
        if cap > 0:
            for k in range(1, 6):
                s = k / 6.0
                r = math.sqrt(max(1 - s * s, 0.0))
                row = base.copy()
                row[0] = base[0] + (cap * s if sgn > 0 else -cap * s)
                row[1] = base[1] * r
                row[2] = base[2] * r
                lst.append(row)
    rows_all = np.vstack([np.array(extra0[::-1]).reshape(-1, 5), ring_rows, np.array(extra1).reshape(-1, 5)])
    nr = len(rows_all)
    verts, uvs, cols = [], [], []
    for ri, (t, a, b, c1, c2) in enumerate(rows_all):
        for j in range(n + 1):
            th = j / n * TAU
            cs, sn = math.cos(th), math.sin(th)
            u = a * np.sign(cs) * abs(cs) ** (2.0 / p)
            v = b * np.sign(sn) * abs(sn) ** (2.0 / p)
            k, col = 1.0, (1.0, 1.0, 1.0)
            if mod is not None:
                k, col = mod(th, t, u, v)
                u, v = u * k, v * k
            if axis == 'y':
                verts.append((c1 + u, t, c2 + v))
            else:
                verts.append((c1 + u, c2 + v, t))
            uvs.append((j / n * uvscale[0], ri / (nr - 1) * uvscale[1]))
            cols.append(col)
    i0 = part.add(verts, uvs, cols)
    part.grid(i0, nr, n + 1)
    # end caps (fans around a centre vertex)
    for ri, rev in ((0, True), (nr - 1, False)):
        t, a, b, c1, c2 = rows_all[ri]
        cen = (c1, t, c2) if axis == 'y' else (c1, c2, t)
        ci = part.add([cen], [(0.5, 0.0 if ri == 0 else 1.0)], [(1, 1, 1)])
        for j in range(n):
            a_i = i0 + ri * (n + 1) + j
            part.f.append((ci, a_i + 1, a_i) if rev else (ci, a_i, a_i + 1))
    return part


def tube(part, path, radii, n=10, ratio=1.0, col=(1, 1, 1), cap=True):
    """a tube along a polyline (fingers, braids, hair clumps); radii per path point"""
    path = np.asarray(path, dtype=float)
    m = len(path)
    tang = np.gradient(path, axis=0)
    tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-9)
    ref = np.array([0.0, 0.0, 1.0])
    verts, uvs, cols = [], [], []
    prev = None
    for i in range(m):
        t = tang[i]
        r0 = ref - t * np.dot(ref, t) if prev is None else prev - t * np.dot(prev, t)
        if np.linalg.norm(r0) < 1e-6:
            r0 = np.cross(t, np.array([1.0, 0, 0]))
        r0 /= np.linalg.norm(r0)
        prev = r0
        r1 = np.cross(t, r0)
        for j in range(n + 1):
            th = j / n * TAU
            verts.append(path[i] + (r0 * math.cos(th) * ratio + r1 * math.sin(th)) * radii[i])
            uvs.append((j / n, i / max(m - 1, 1)))
            cols.append(col)
    i0 = part.add(verts, uvs, cols)
    part.grid(i0, m, n + 1)
    if cap:
        for idx, rev in ((0, True), (m - 1, False)):
            ci = part.add([path[idx]], [(0.5, 0.0)], [col])
            for j in range(n):
                a_i = i0 + idx * (n + 1) + j
                part.f.append((ci, a_i + 1, a_i) if rev else (ci, a_i, a_i + 1))
    return part


def ellipsoid(part, c, r, nlon=16, nlat=10, col=(1, 1, 1), rot=None):
    verts, uvs, cols = [], [], []
    for i in range(nlat + 1):
        th = math.pi * i / nlat
        for j in range(nlon + 1):
            ph = TAU * j / nlon
            p = np.array([r[0] * math.sin(th) * math.sin(ph), r[1] * math.cos(th), r[2] * math.sin(th) * math.cos(ph)])
            if rot is not None:
                p = rot @ p
            verts.append(np.array(c) + p)
            uvs.append((j / nlon, i / nlat))
            cols.append(col)
    i0 = part.add(verts, uvs, cols)
    part.grid(i0, nlat + 1, nlon + 1)
    return part


# ---------------------------------------------------------------------------------------------------------------------------
#  body parts
# ---------------------------------------------------------------------------------------------------------------------------
def band(y, y0, y1, soft=0.004):
    """1 inside [y0, y1], smooth edges"""
    return float(smooth((y - y0) / soft) * smooth((y1 - y) / soft))


def front_lobe(th, centre_deg, width_deg):
    return math.exp(-(angdiff(th, math.radians(centre_deg)) ** 2) / (2 * math.radians(width_deg) ** 2))


def torso():
    pt = Part('torso')
    # a loose hip-length jacket: flat chest, boxy waist, sloping shoulders and a high stand collar (y is local to the mount at 1.26).
    # All the cloth detail (zip, pockets, seams, collar, rib hem) is painted into the jacket texture by NV.Human; only soft folds and the baked occlusion live here.
    prof = [
        (-0.250, .180, .121, 0, 0.002), (-0.170, .181, .122, 0, 0.005), (-0.050, .176, .118, 0, 0.009), (0.060, .190, .126, 0, 0.013),
        (0.160, .204, .131, 0, 0.016), (0.240, .214, .128, 0, 0.012), (0.292, .210, .118, 0, 0.004), (0.330, .168, .101, 0, -0.004),
        (0.364, .106, .088, 0, -0.009), (0.394, .076, .076, 0, -0.011), (0.414, .074, .074, 0, -0.011)]
    prof = [(t, a * (0.86 if t < 0.35 else 0.92), b, c1, c2) for (t, a, b, c1, c2) in prof]      # narrower shoulders: the head reads at the right size

    def mod(th, y, u, v):
        k = 1.0
        front = front_lobe(th, 90, 38)
        back = front_lobe(th, 270, 34)
        side = max(front_lobe(th, 0, 25), front_lobe(th, 180, 25))
        k += .008 * front * math.exp(-((y - 0.14) ** 2) / (2 * .07 ** 2))                                # chest
        k += .007 * front_lobe(th, 90, 7) * band(y, -0.25, 0.33, .03)                                    # the zip placket stands a little proud
        k += .006 * back * math.exp(-((y - 0.17) ** 2) / (2 * .08 ** 2))                                  # back
        k += .008 * side * math.exp(-((y - 0.08) ** 2) / (2 * .09 ** 2))                                  # sides
        k += .014 * band(y, -0.250, -0.215, .012)                                                          # the rib hem blouses out a little
        k += .012 * band(y, 0.330, 0.414, .02)                                                             # collar
        k += .005 * math.sin(th * 5 + y * 9) * band(y, -0.2, 0.05, .06)                                    # soft cloth folds at the waist
        return k, (1.0, 1.0, 1.0)

    loft(pt, prof, n=48, p=2.4, mod=mod, cap0=0.0, cap1=0.0, rows=44)
    return pt


def pelvis():
    pt = Part('pelvis')
    prof = [(-0.165, .148, .106, 0, -0.004), (-0.100, .178, .118, 0, -0.006), (-0.020, .190, .122, 0, -0.008), (0.050, .180, .115, 0, 0.0),
            (0.092, .172, .110, 0, 0.0)]
    prof = [(t, a * 0.88, b * 0.96, c1, c2) for (t, a, b, c1, c2) in prof]        # hips no wider than the jacket

    def mod(th, y, u, v):
        k = 1.0
        col = [1.0, 1.0, 1.0]
        k += .030 * front_lobe(th, 270, 40) * math.exp(-((y + 0.08) ** 2) / (2 * .06 ** 2))          # seat
        belt = band(y, 0.028, 0.062, .004)
        k += .009 * belt
        col = [c * (1 - .55 * belt) for c in col]
        buckle = front_lobe(th, 90, 5) * band(y, 0.02, 0.07, .004)
        k += .006 * buckle
        col = [min(1.0, c + .5 * buckle) for c in col] if buckle > .2 else col
        fly = front_lobe(th, 90, 2.2) * band(y, -0.12, 0.028, .01)
        col = [c * (1 - .35 * fly) for c in col]
        return k, tuple(col)

    return loft(pt, prof, n=36, p=2.2, mod=mod, rows=16)


def neck():
    pt = Part('neck')
    prof = [(-0.075, .064, .068, 0, 0.000), (-0.020, .056, .060, 0, 0.004), (0.035, .052, .056, 0, 0.008), (0.095, .054, .058, 0, 0.012)]

    def mod(th, y, u, v):
        k = 1.0
        for sx in (-1, 1):
            k += .007 * front_lobe(th, 90 - sx * 52, 14) * band(y, -0.05, 0.07, .02)               # sternocleidomastoid
        k += .006 * front_lobe(th, 90, 8) * math.exp(-((y - 0.0) ** 2) / (2 * .014 ** 2))            # larynx
        k += .008 * front_lobe(th, 270, 40) * band(y, -0.06, 0.02, .02)
        return k, (1, 1, 1)

    return loft(pt, prof, n=28, p=2.1, mod=mod, rows=10, uvscale=(2.0, 1.0))


def leg_u():
    pt = Part('leg_u')
    prof = [(-0.285, .056, .060, 0, 0.000), (-0.225, .060, .066, 0, 0.002), (-0.140, .073, .080, 0, 0.004), (-0.020, .089, .099, 0, 0.006),
            (0.100, .098, .108, 0, 0.004), (0.200, .100, .105, 0, 0.002), (0.255, .084, .088, 0, 0.0), (0.285, .050, .052, 0, 0.0)]
    prof = [(t, a * 0.86, b * 0.88, c1, c2) for (t, a, b, c1, c2) in prof]

    def mod(th, y, u, v):
        k = 1.0
        col = [1.0, 1.0, 1.0]
        k += .016 * front_lobe(th, 90, 36) * band(y, -0.12, 0.12, .08)                              # quadriceps
        k += .010 * front_lobe(th, 270, 40) * band(y, -0.12, 0.12, .08)                             # hamstrings
        seam = max(front_lobe(th, 0, 3), front_lobe(th, 180, 3))
        col = [c * (1 - .35 * seam) for c in col]
        k -= .002 * seam
        return k, tuple(col)

    return loft(pt, prof, n=32, p=2.1, mod=mod, rows=20)


def leg_l():
    pt = Part('leg_l')
    prof = [(-0.265, .044, .048, 0, 0.002), (-0.235, .043, .047, 0, 0.0), (-0.160, .040, .045, 0, -0.004), (-0.060, .050, .057, 0, -0.008),
            (0.040, .057, .066, 0, -0.010), (0.120, .060, .068, 0, -0.004), (0.215, .062, .066, 0, 0.002), (0.275, .058, .062, 0, 0.0)]
    prof = [(t, a * 0.9, b * 0.9, c1, c2) for (t, a, b, c1, c2) in prof]

    def mod(th, y, u, v):
        k = 1.0
        col = [1.0, 1.0, 1.0]
        k += .014 * front_lobe(th, 270, 40) * band(y, -0.04, 0.14, .05)                              # calf
        k += .008 * front_lobe(th, 90, 14) * band(y, -0.2, 0.12, .05)                                # shin
        k += .007 * front_lobe(th, 90, 20) * math.exp(-((y - 0.20) ** 2) / (2 * .02 ** 2))           # kneecap
        cuff = band(y, -0.265, -0.205, .006)
        k += .005 * cuff
        col = [c * (1 - .45 * cuff) for c in col]
        seam = max(front_lobe(th, 0, 3), front_lobe(th, 180, 3))
        col = [c * (1 - .35 * seam) for c in col]
        return k, tuple(col)

    return loft(pt, prof, n=30, p=2.1, mod=mod, rows=18)


def foot():
    pt = Part('foot')
    # ring rows are (z, half width, half height, x centre, y centre); the boot is lofted along z
    prof = [(-0.088, .030, .038, 0, -0.006), (-0.070, .039, .050, 0, 0.004), (-0.036, .044, .062, 0, 0.016), (0.012, .045, .055, 0, 0.005),
            (0.066, .047, .041, 0, -0.005), (0.120, .046, .031, 0, -0.015), (0.165, .041, .022, 0, -0.023), (0.196, .027, .013, 0, -0.031)]

    def mod(th, z, u, v):
        k = 1.0
        col = [1.0, 1.0, 1.0]
        # sole: darker band along the bottom edge, slightly wider
        low = smooth((-math.sin(th) - 0.55) / 0.35)
        col = [c * (1 - .72 * low) for c in col]
        k += .004 * low
        # laces: ridges across the instep
        top = front_lobe(th, 90, 20)
        lace = 0.5 + 0.5 * math.cos((z - -0.02) * 2 * math.pi / 0.016)
        lz = band(z, -0.024, 0.074, .006)
        k += .0035 * top * lace * lz
        col = [c * (1 - .30 * top * (1 - lace) * lz) for c in col]
        return k, tuple(col)

    return loft(pt, prof, n=30, axis='z', p=3.0, mod=mod, rows=22, cap0=0.012, cap1=0.012)


def arm_u():
    pt = Part('arm_u')
    prof = [(-0.235, .042, .045, 0, 0.0), (-0.190, .044, .047, 0, 0.0), (-0.120, .048, .052, 0, 0.002), (-0.040, .054, .058, 0, 0.002),
            (0.060, .060, .064, 0, 0.0), (0.150, .070, .072, 0, -0.002), (0.205, .068, .072, 0, 0.0), (0.228, .056, .060, 0, 0.0)]
    prof = [(t, a * 0.9, b * 0.9, c1, c2) for (t, a, b, c1, c2) in prof]

    def mod(th, y, u, v):
        k = 1.0
        col = [1.0, 1.0, 1.0]
        k += .008 * front_lobe(th, 90, 38) * band(y, -0.12, 0.10, .05)
        k += .008 * front_lobe(th, 270, 38) * band(y, -0.12, 0.10, .05)
        seam = band(y, 0.135, 0.150, .004)
        k += .004 * seam
        col = [c * (1 - .4 * seam) for c in col]
        k += .003 * math.sin((y + 0.19) * 140) * band(y, -0.23, -0.12, .02) * front_lobe(th, 90, 70)   # sleeve creases at the elbow
        return k, tuple(col)

    return loft(pt, prof, n=28, p=2.1, mod=mod, rows=20, cap1=0.045)


def arm_l():
    pt = Part('arm_l')
    prof = [(-0.215, .037, .039, 0, 0.0), (-0.150, .031, .032, 0, 0.0), (-0.100, .034, .036, 0, 0.0), (-0.020, .042, .044, 0, 0.002),
            (0.080, .049, .052, 0, 0.002), (0.160, .046, .049, 0, -0.002), (0.215, .044, .047, 0, 0.0)]

    def mod(th, y, u, v):
        k = 1.0
        col = [1.0, 1.0, 1.0]
        cuff = band(y, -0.205, -0.135, .006)
        k += .0075 * cuff
        col = [c * (1 - .40 * cuff) for c in col]
        k += .004 * front_lobe(th, 270, 40) * math.exp(-((y - 0.15) ** 2) / (2 * .02 ** 2))          # elbow point
        k += .003 * math.sin((y - 0.1) * 150) * band(y, 0.1, 0.2, .02) * front_lobe(th, 90, 70)
        return k, tuple(col)

    return loft(pt, prof, n=26, p=2.1, mod=mod, rows=18, cap0=0.0, cap1=0.0)


def hand():
    """a relaxed right hand hanging from the wrist: the palm faces the thigh (-x), the thumb is forward (+z), the fingers lie side by side
    and curl a little toward the palm, more toward the little finger. Origin: the wrist centre is at y = +.05; the knuckle line is at -.062."""
    pt = Part('hand')
    # the palm: thin along x, wide along z, a little thicker on the thumb side
    prof = [(0.050, .0150, .0290, 0.0, 0.000), (0.020, .0155, .0305, -.001, 0.002), (-0.010, .0160, .0365, -.002, 0.004), (-0.040, .0143, .0412, -.001, 0.001), (-0.062, .0118, .0428, 0.0, 0.000)]
    loft(pt, prof, n=26, axis='y', p=2.3, rows=12, cap0=0.0, cap1=0.012)
    zs = (0.0295, 0.0105, -0.0085, -0.0255)
    lens = ((.043, .026, .021), (.047, .029, .023), (.044, .027, .022), (.035, .021, .019))
    curl = ((16, 28, 12), (22, 36, 14), (28, 42, 18), (34, 48, 22))
    rad = ((.0090, .0082, .0074, .0067), (.0092, .0084, .0076, .0069), (.0088, .0080, .0072, .0065), (.0078, .0071, .0064, .0057))
    for z, L, cv, rr in zip(zs, lens, curl, rad):
        base = np.array([-0.001, -0.060, z])
        ellipsoid(pt, base + np.array([0.0, -0.004, 0.0]), (rr[0] * 1.02, 0.010, rr[0] * 1.02), 10, 6)
        path = [base]
        cur = base.copy()
        th = 0.0
        for seg, a in zip(L, cv):
            th += math.radians(a)
            cur = cur + np.array([-math.sin(th), -math.cos(th), 0.0]) * seg
            path.append(cur.copy())
            # a joint bulge
            ellipsoid(pt, cur, (rr[min(len(path) - 1, 3)] * 1.0,) * 3, 8, 5)
        tube(pt, path, list(rr), n=12, ratio=1.0)
        ellipsoid(pt, path[-1], (rr[3] * 1.02,) * 3, 8, 5)
        ellipsoid(pt, (0.008, -0.063, z), (0.0060, 0.0065, 0.0085), 8, 5)           # the knuckle on the back of the hand
    # the thumb: from the thenar pad, forward and down, lying against the index finger
    tp = [np.array([-0.004, -0.012, 0.036]), np.array([-0.006, -0.036, 0.048]), np.array([-0.010, -0.058, 0.050]), np.array([-0.015, -0.080, 0.047]), np.array([-0.019, -0.094, 0.043])]
    tube(pt, tp, [0.0118, 0.0106, 0.0096, 0.0086, 0.0078], n=12, ratio=1.0)
    ellipsoid(pt, tp[-1], (.0080, .0080, .0078), 8, 5)
    ellipsoid(pt, (-0.007, -0.022, 0.036), (.010, .028, .016), 12, 8)                 # thenar pad
    ellipsoid(pt, (-0.005, -0.028, -0.032), (.008, .026, .010), 10, 6)                # the heel of the little-finger side
    ellipsoid(pt, (0.010, -0.030, 0.002), (.006, .036, .026), 10, 8)                  # the back of the hand
    return pt


BODY = [torso, pelvis, neck, leg_u, leg_l, foot, arm_u, arm_l, hand]

# ---------------------------------------------------------------------------------------------------------------------------
#  the head: an ellipsoid skull, sculpted with anatomical bumps (brow ridge, cheekbones, nose, lips, chin, jaw)
# ---------------------------------------------------------------------------------------------------------------------------
HA, HB, HC = 0.084, 0.113, 0.099          # skull half width, half height, half depth (head centre = origin, face toward +z)
EYE_X, EYE_Y, EYE_R, EYE_Z = 0.0325, 0.010, 0.0108, 0.0735     # eyeball centre (x is mirrored), radius and depth

# (cx, cy, cz, sx, sy, sz, amplitude): a gaussian blob pushed along the surface normal; + out, - in
FEATURES = [
    ('forehead', 0.0, 0.066, 0.095, .060, .036, .05, +.0040), ('brow_r', 0.031, 0.033, 0.100, .027, .0095, .03, +.0085), ('brow_l', -0.031, 0.033, 0.100, .027, .0095, .03, +.0085),
    ('glabella', 0.0, 0.032, 0.102, .013, .014, .03, +.0045),
    ('socket_r', 0.0325, 0.010, 0.098, .017, .012, .03, -.0040), ('socket_l', -0.0325, 0.010, 0.098, .017, .012, .03, -.0040),
    ('lid_r', 0.0325, 0.021, 0.098, .015, .0055, .03, +.0030), ('lid_l', -0.0325, 0.021, 0.098, .015, .0055, .03, +.0030),
    ('cheek_r', 0.052, -0.016, 0.080, .026, .021, .04, +.0095), ('cheek_l', -0.052, -0.016, 0.080, .026, .021, .04, +.0095),
    ('bridge', 0.0, -0.002, 0.108, .0058, .032, .03, +.0090), ('tip', 0.0, -0.038, 0.118, .0110, .0105, .026, +.0190),
    ('wing_r', 0.0160, -0.042, 0.108, .0082, .0100, .02, +.0085), ('wing_l', -0.0160, -0.042, 0.108, .0082, .0100, .02, +.0085),
    ('nostril_r', 0.0085, -0.0495, 0.110, .0055, .0045, .015, -.0065), ('nostril_l', -0.0085, -0.0495, 0.110, .0055, .0045, .015, -.0065),
    ('philtrum', 0.0, -0.056, 0.108, .0035, .0075, .02, -.0025),
    ('lip_up', 0.0, -0.0645, 0.1055, .0190, .0068, .02, +.0085), ('lip_lo', 0.0, -0.0795, 0.1045, .0185, .0078, .02, +.0085),
    ('mouth', 0.0, -0.0715, 0.1035, .0260, .0022, .02, -.0075), ('corner_r', 0.0255, -0.0715, 0.098, .0055, .0065, .02, -.0045), ('corner_l', -0.0255, -0.0715, 0.098, .0055, .0065, .02, -.0045),
    ('nasolab_r', 0.0275, -0.052, 0.098, .0050, .024, .02, -.0035), ('nasolab_l', -0.0275, -0.052, 0.098, .0050, .024, .02, -.0035),
    ('chin', 0.0, -0.1115, 0.088, .0220, .0160, .03, +.0100), ('chinlip', 0.0, -0.0915, 0.100, .0140, .0035, .02, -.0035),
    ('jaw_r', 0.062, -0.075, 0.010, .020, .030, .05, +.0085), ('jaw_l', -0.062, -0.075, 0.010, .020, .030, .05, +.0085),
    ('temple_r', 0.066, 0.042, 0.050, .020, .030, .03, -.0040), ('temple_l', -0.066, 0.042, 0.050, .020, .030, .03, -.0040),
    ('undereye_r', 0.0325, -0.008, 0.100, .016, .005, .02, -.0015), ('undereye_l', -0.0325, -0.008, 0.100, .016, .005, .02, -.0015),
]
BLANK_FACE = 0.22          # the face is left a smooth blank surface: facial detail (brows, eyes, nose, lips) keeps only this share of its relief
STRUCT = ('forehead', 'cheek_r', 'cheek_l', 'chin', 'jaw_r', 'jaw_l', 'temple_r', 'temple_l')
FEATURES = [f if f[0] in STRUCT else f[:7] + (f[7] * BLANK_FACE,) for f in FEATURES]
FEAT = {f[0]: f for f in FEATURES}


def head_pos(phi, theta, features=True):
    """surface points (n,3) of the head for polar coordinates (phi around, theta from the top); phi = pi looks at the face"""
    phi = np.asarray(phi, float)
    theta = np.asarray(theta, float)
    d = np.stack([np.sin(theta) * np.sin(phi), np.cos(theta), -np.sin(theta) * np.cos(phi)], axis=-1)
    p = d * np.array([HA, HB, HC])
    y = p[..., 1]
    front = smooth((p[..., 2] + 0.01) / 0.05)
    # jaw: narrower below the cheekbones, chin forward
    kx = 1.0 - 0.034 * smooth((-0.010 - y) / 0.105)
    p[..., 0] *= kx
    p[..., 2] += 0.0215 * smooth((-0.022 - y) / 0.085) * front
    p[..., 2] += -0.004 * smooth((y - 0.04) / 0.07) * front                                         # the forehead leans back a little
    # the face is flatter than an ellipsoid across the cheeks
    p[..., 2] -= 0.007 * front * np.exp(-(p[..., 0] / 0.05) ** 2) * smooth((y + 0.09) / 0.08) * smooth((0.08 - y) / 0.05)
    if features:
        nrm = d / np.array([HA, HB, HC]) ** 2
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        off = np.zeros(p.shape[:-1])
        for (_, cx, cy, cz, sx, sy, sz, amp) in FEATURES:
            off += amp * np.exp(-(((p[..., 0] - cx) / sx) ** 2 + ((p[..., 1] - cy) / sy) ** 2 + ((p[..., 2] - cz) / sz) ** 2) / 2)
        p = p + nrm * off[..., None]
    return p


def eye_skin(p):
    """the skin around each eye follows the eyeball (so lids cover it) and drops below its surface inside the almond-shaped eye gap"""
    p = p.copy()
    R1 = EYE_R + 0.0017
    for sx in (-1, 1):
        lx = p[..., 0] - sx * EYE_X
        ly = p[..., 1] - EYE_Y
        u = lx * sx                                   # lateral coordinate: + toward the outer corner
        rho = np.hypot(lx, ly)
        yt = ly - math.tan(0.14) * u                  # the outer corner sits higher than the inner one
        up = 0.0046 * np.clip(1 - ((u - 0.0005) / 0.0128) ** 2, 0, 1) ** 0.8
        lo = -0.0038 * np.clip(1 - ((u + 0.0018) / 0.0128) ** 2, 0, 1) ** 0.8
        sd = np.minimum(np.minimum(up - yt, yt - lo), (0.0128 - np.abs(u)) * 0.5)
        fw = smooth(sd / 0.0007 + 0.5)
        rc = np.minimum(rho, 0.92 * R1)
        z_out = EYE_Z + np.sqrt(np.maximum(R1 ** 2 - rc ** 2, 0))
        rr = np.minimum(rho, 0.97 * EYE_R)
        z_in = EYE_Z + np.sqrt(np.maximum(EYE_R ** 2 - rr ** 2, 0)) - 0.0028
        zt = z_out * (1 - fw) + z_in * fw
        w = smooth((0.0240 - np.hypot(lx / 1.25, ly)) / 0.0110) * smooth((p[..., 2] - 0.03) / 0.03)
        p[..., 2] = p[..., 2] * (1 - w) + zt * w
    return p


FACE_PSI = 1.22      # the face grid covers +-1.22 rad around the front; the rest of the head is a coarser grid with its own UVs


def head_grid(pt, psi0, psi1, nlon, nlat, uvfn):
    """a (nlat+1) x (nlon+1) block of the head between two longitudes (psi measured from the front)"""
    psi = np.linspace(psi0, psi1, nlon + 1)
    th = np.linspace(0.0, math.pi, nlat + 1)
    PSI, TH = np.meshgrid(psi, th)
    pos = head_pos((math.pi + PSI).ravel(), TH.ravel())
    uv = uvfn(pos, PSI.ravel(), TH.ravel())
    i0 = pt.add(pos, uv, np.ones((len(pos), 3)))
    pt.grid(i0, nlat + 1, nlon + 1)
    return pos


def face_uv(pos, psi, th):
    # planar projection from the front: the painted face texture lives in the left half of the atlas
    return np.stack([(pos[:, 0] / 0.24 + 0.5) * 0.5, pos[:, 1] / 0.25 + 0.5], axis=1)


def back_uv(pos, psi, th):
    # the rest of the head: plain skin in the right half of the atlas
    return np.stack([0.5 + 0.5 * ((psi + math.pi) / TAU) * 1.0, th / math.pi], axis=1)


EYE_C = {}


def eye_centres(head_only):
    for sx in (-1, 1):
        z = surf_z(head_only, sx * EYE_X, EYE_Y)
        EYE_C[sx] = np.array([sx * EYE_X, EYE_Y, z - EYE_R + 0.0030])


def head_part(nfront=96, nback=34, nlat=84, name='head'):
    pt = Part(name)
    head_grid(pt, -FACE_PSI, FACE_PSI, nfront, nlat, face_uv)
    head_grid(pt, FACE_PSI, TAU - FACE_PSI, nback, nlat, back_uv)
    return pt


def surf_z(part, x, y, z0=0.4):
    """z of the part's surface at (x, y), found by casting a ray along -z"""
    v = [tuple(p) for p in part.v]
    tris = []
    for f in part.f:
        for k in range(1, len(f) - 1):
            tris.append((f[0], f[k], f[k + 1]))
    bvh = BVHTree.FromPolygons(v, tris)
    hit = bvh.ray_cast(Vector((x, y, z0)), Vector((0, 0, -1)), 1.0)
    return hit[0].z if hit[0] is not None else 0.1


def eyes_parts(head):
    sc, ir = Part('eyes'), Part('iris')
    for sx in (-1, 1):
        c = np.array([sx * EYE_X, EYE_Y, EYE_Z])
        ellipsoid(sc, c, (EYE_R, EYE_R, EYE_R), 26, 18)
        # iris and pupil: a slightly domed cap on the front of the eyeball
        rows, cols_n = 8, 28
        verts, uvs, cc = [], [], []
        for i in range(rows):
            rho = 0.0055 * i / (rows - 1)                       # distance from the eye's axis
            for j in range(cols_n + 1):
                a = j / cols_n * TAU
                x, y = rho * math.cos(a), rho * math.sin(a)
                z = math.sqrt(max(EYE_R ** 2 - rho ** 2, 1e-9)) + 0.0004 + 0.0012 * (1 - (rho / 0.0055) ** 2)
                verts.append(c + np.array([x, y, z]))
                uvs.append((j / cols_n, i / (rows - 1)))
                t = rho / 0.0055
                if t < .30:
                    v = .05                                         # pupil
                elif t > .88:
                    v = .38                                         # limbal ring
                else:
                    streak = .78 + .22 * math.sin(a * 17 + 3 * math.sin(a * 5))
                    v = streak * (.80 + .20 * (t - .3) / .58)
                cc.append((v, v, v))
        i1 = ir.add(verts, uvs, cc)
        ir.grid(i1, rows, cols_n + 1, rev=True)
    return sc, ir


def ear_part(head):
    pt = Part('ear')
    for sx in (-1, 1):
        nlon, nlat = 26, 20
        verts, uvs, cols = [], [], []
        for i in range(nlat + 1):
            t = math.pi * i / nlat
            for j in range(nlon + 1):
                a = TAU * j / nlon
                # ellipsoid: thin in x, tall in y, deep in z; the outer face (x > 0) is dished
                px, py, pz = 0.0062 * math.cos(t), 0.0330 * math.sin(t) * math.sin(a), 0.0220 * math.sin(t) * math.cos(a)
                rr = math.hypot(py / 0.033, pz / 0.022)
                bowl = -0.0050 * math.exp(-(rr / 0.50) ** 2) if px > 0 else 0.0
                rim = 0.0022 * math.exp(-((rr - 0.88) / 0.10) ** 2) if px > 0 else 0.0
                px += bowl + rim
                # the lobe hangs lower and narrower
                pz *= 1.0 - 0.22 * smooth(-py / 0.033)
                col = 1.0 - 0.38 * math.exp(-(rr / 0.55) ** 2) * (1 if px > 0.0 else 0.4)
                verts.append((sx * (0.0785 + px), -0.002 + py, -0.012 + pz))
                uvs.append((j / nlon, i / nlat))
                cols.append((col, col * .93, col * .92))
        i0 = pt.add(verts, uvs, cols)
        pt.grid(i0, nlat + 1, nlon + 1)
    return pt



# ---------------------------------------------------------------------------------------------------------------------------
#  hair (double-sided sheets that drape over the scalp), hood and cap
# ---------------------------------------------------------------------------------------------------------------------------
def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def hairline_y(psi):
    """height of the hairline for a longitude psi measured from the front: forehead, temples, above the ear, nape"""
    a = np.abs(((psi + math.pi) % TAU) - math.pi)
    return np.interp(a, [0.0, 0.5, 1.0, 1.45, 1.9, 2.5, math.pi], [0.074, 0.062, 0.040, 0.022, 0.0, -0.045, -0.078])


def hair_sheet(part, psis, theta0, y_end, drop, thick0=0.004, thick1=0.012, flare=0.0, stripe=0.10, ns=16, nd=8, rnd=0.0, wave=0.0, seed=1, dark_root=0.55, tuck=0.0, vspan=None, ucols=0.14, lat=0.0):
    """one column per longitude: from near the crown down over the scalp to y_end, then hanging `drop` metres straight down"""
    rng = np.random.default_rng(seed)
    psis = np.asarray(psis, float)
    nc = len(psis)
    rows = ns + nd
    pos = np.zeros((rows, nc, 3))
    col = np.zeros((rows, nc, 3))
    for c, psi in enumerate(psis):
        ye = float(y_end(psi) if callable(y_end) else y_end)
        th0 = float(theta0(psi) if callable(theta0) else theta0)
        th1 = math.acos(np.clip(ye / HB, -0.99, 0.99))
        dr = float(drop(psi) if callable(drop) else drop) + rng.normal() * rnd
        t0 = float(thick0(psi) if callable(thick0) else thick0)
        t1 = float(thick1(psi) if callable(thick1) else thick1)
        lt = float(lat(psi) if callable(lat) else lat)
        jitter = 1.0 + stripe * math.sin(psi * 83.0 + 1.7) + 0.5 * stripe * math.sin(psi * 37.0)
        for k in range(ns):
            s = k / (ns - 1)
            th = th0 + (th1 - th0) * s
            p = head_pos(np.array([math.pi + psi]), np.array([th]))[0]
            nrm = unit(p / np.array([HA, HB, HC]) ** 2)
            t = (t0 + (t1 - t0) * smooth(s)) * jitter
            pos[k, c] = p + nrm * t
            col[k, c] = dark_root + (1 - dark_root) * 0.5 * s
        pb = head_pos(np.array([math.pi + psi]), np.array([th1]))[0]
        nb = unit(pb / np.array([HA, HB, HC]) ** 2)
        nh = unit(np.array([nb[0], 0.0, nb[2]]))
        for i in range(1, nd + 1):
            s = i / nd
            q = pb + np.array([0.0, -dr * s, 0.0]) + nh * (t1 * jitter + flare * s) - nh * tuck * s * s
            q[0] += wave * math.sin(s * 5.5 + psi * 3.0) * s
            q[0] += math.copysign(1.0, pb[0] + 1e-9) * lt * s                 # hair that falls beside the face is swept outward and back, clear of the cheek
            q[2] -= 0.8 * lt * s
            pos[ns - 1 + i, c] = q
            col[ns - 1 + i, c] = 0.82 + 0.18 * s + 0.06 * math.sin(psi * 60 + s * 9)
    flat = pos.reshape(-1, 3)
    vs = 0.95 if vspan is None else vspan
    uv = np.stack([np.tile(np.arange(nc) * ucols, rows), np.repeat(np.linspace(0, 1, rows), nc) * vs], axis=1)
    i0 = part.add(flat, uv, col.reshape(-1, 3))
    part.grid(i0, rows, nc)
    return part


def mask_top(part, y_min):
    """drop quads that lie entirely below y_min (used to trim a shell to a hairline)"""
    keep = []
    for f in part.f:
        if max(part.v[i][1] for i in f) > y_min:
            keep.append(f)
    part.f = keep


def hair_cap(name, thick=0.004, stripe=0.10, seed=2, higher=0.0, nc=72, cover=None):
    pt = Part(name)
    psis = np.linspace(-math.pi, math.pi, nc)
    hair_sheet(pt, psis, 0.0, lambda ps: hairline_y(ps) + higher, 0.0, thick, thick, stripe=stripe, ns=16, nd=0 + 1, seed=seed, vspan=0.9)
    return pt


def hair_buzz():
    return hair_cap('hair_buzz', 0.0045, 0.10, 3)


def hair_undercut():
    pt = Part('hair_undercut')
    # sides and back: a short shell that stops higher up
    psis = np.linspace(-math.pi, math.pi, 72)
    hair_sheet(pt, psis, 0.0, lambda ps: hairline_y(ps) + 0.022 * smooth((np.abs(ps) - 0.4) / 0.9), 0.0, 0.0045, 0.0045, stripe=0.10, ns=14, nd=1, seed=4, vspan=0.9)
    # the long top: a swept block from the forehead to the crown
    top = np.linspace(-1.0, 1.0, 21)
    hair_sheet(pt, top, 0.0, lambda ps: 0.068 + 0.02 * abs(ps), 0.012, 0.014, 0.022, stripe=0.18, ns=14, nd=3, seed=5, flare=0.004, wave=0.002)
    return pt


def hair_mohawk():
    pt = Part('hair_mohawk')
    psis = np.linspace(-math.pi, math.pi, 72)
    hair_sheet(pt, psis, 0.0, lambda ps: hairline_y(ps) + 0.045, 0.0, 0.003, 0.003, stripe=0.0, ns=12, nd=1, seed=6)
    # the crest: blades along the sagittal curve from the forehead over the crown to the nape
    n = 22
    for i in range(n):
        t = i / (n - 1)
        th = 0.55 + t * 2.15                       # polar angle along the front to back arc (0 = crown)
        side = 0 if t < 0.5 else 1
        psi = 0.0 if t < 0.5 else math.pi
        th_eff = 0.55 + (0.5 - abs(t - 0.5)) * 0  # placeholder keeps the arc readable
        ang = (0.62 - 1.55 * t)                    # from the front (+) over the top to the back (-)
        c = np.array([0.0, HB * math.sin(0.5 + 2.3 * t - 0.0) * 0.0, 0.0])
        # a point on the sagittal outline of the skull
        phi = math.pi * (0.78 - 1.56 * t) / 0.78 * 0.5 + 0.0
        theta = 0.40 + 2.0 * t if t < 0.5 else 0.40 + 2.0 * t
        ps = 0.0 if t < 0.5 else math.pi
        thv = 0.9 - 1.8 * t if t < 0.5 else 1.8 * t - 0.9
        thv = abs(thv) * 0.9 + 0.12
        base = head_pos(np.array([math.pi + (0.0 if t < 0.5 else math.pi)]), np.array([thv]))[0]
        nrm = unit(base / np.array([HA, HB, HC]) ** 2)
        h = 0.070 * math.sin(math.pi * min(1, 0.12 + t * 0.98)) ** 0.8 + 0.012
        tilt = (0.5 - t) * 0.7
        lean = np.array([0.0, math.cos(tilt), math.sin(tilt) * 1.0]) * 1.0
        for k in range(3):
            off = (k - 1) * 0.0075
            path = [base + np.array([off, 0, 0]) + nrm * 0.004, base + np.array([off * 0.8, 0, 0]) + nrm * 0.004 + unit(nrm + np.array([0, 0.3, 0]) * 0) * h * 0.55,
                    base + np.array([off * 0.4, 0, 0]) + nrm * 0.004 + lean * h]
            tube(pt, path, [0.0060, 0.0048, 0.0014], n=7, ratio=0.9, col=(0.85, 0.85, 0.85))
    return pt


def hair_bob():
    pt = Part('hair_bob')
    nc = 84
    psis = np.concatenate([np.linspace(-math.pi, -0.82, 44), np.linspace(0.82, math.pi, 44)])
    hair_sheet(pt, psis, 0.10, lambda ps: (-0.092 + 0.015 * math.sin(ps * 9)) * smooth((abs(ps) - 0.82) / 0.55) + 0.030 * (1 - smooth((abs(ps) - 0.82) / 0.55)), 0.0, 0.012, 0.024, flare=0.006, stripe=0.14, ns=22, nd=2, seed=7, rnd=0.004, tuck=0.012)
    # the fringe over the forehead
    fr = np.linspace(-1.1, 1.1, 36)
    hair_sheet(pt, fr, 0.10, lambda ps: 0.056 + 0.03 * abs(ps) ** 2, 0.0, 0.012, 0.016, stripe=0.18, ns=12, nd=2, seed=8)
    top = np.linspace(-math.pi, math.pi, 72)
    hair_sheet(pt, top, 0.0, lambda ps: 0.045 + 0.02 * smooth((np.abs(ps) - 0.5) / 1.5), 0.0, 0.008, 0.010, stripe=0.10, ns=8, nd=1, seed=9)
    return pt


def hair_long():
    pt = Part('hair_long')
    psis = np.concatenate([np.linspace(-math.pi, -0.86, 50), np.linspace(0.86, math.pi, 50)])
    hair_sheet(pt, psis, 0.10, lambda ps: (-0.02 + 0.03 * math.sin(ps * 7)) * smooth((abs(ps) - 0.86) / 0.55) + 0.030 * (1 - smooth((abs(ps) - 0.86) / 0.55)), lambda ps: (0.36 + 0.05 * math.sin(ps * 11) + 0.04 * (1 - abs(abs(ps) - math.pi) / math.pi)) * (0.35 + 0.65 * smooth((abs(ps) - 0.86) / 0.6)), 0.012, 0.024, flare=0.016, stripe=0.14, ns=18, nd=14, seed=10, rnd=0.012, wave=0.006, lat=lambda ps: 0.045 * (1 - smooth((abs(ps) - 0.86) / 0.75)))
    fr = np.linspace(-1.14, 1.14, 40)
    hair_sheet(pt, fr, 0.10, lambda ps: 0.056 + 0.03 * abs(ps) ** 2, 0.0, 0.012, 0.016, stripe=0.18, ns=12, nd=2, seed=11)
    top = np.linspace(-math.pi, math.pi, 72)
    hair_sheet(pt, top, 0.0, lambda ps: 0.04 + 0.02 * smooth((np.abs(ps) - 0.5) / 1.5), 0.0, 0.008, 0.010, stripe=0.10, ns=8, nd=1, seed=12)
    return pt


def hair_bun():
    pt = hair_cap('hair_bun', 0.0055, 0.10, 13, higher=0.012)
    ellipsoid(pt, (0.0, 0.098, -0.082), (0.040, 0.034, 0.038), 22, 14, col=(0.9, 0.9, 0.9))
    ellipsoid(pt, (0.0, 0.098, -0.082), (0.043, 0.0045, 0.041), 22, 8, col=(0.35, 0.35, 0.35))       # the hair tie
    return pt


def hair_braids():
    pt = hair_cap('hair_braids', 0.0050, 0.10, 14, higher=0.010)
    for sx in (-1, 1):
        path = [(0.094, 0.002, -0.030), (0.108, -0.060, -0.020), (0.119, -0.130, 0.022), (0.124, -0.200, 0.092), (0.127, -0.280, 0.140), (0.127, -0.360, 0.158), (0.127, -0.440, 0.164)]
        pts = catmull(np.array(path), 15)
        pts[:, 0] *= sx
        for i, c in enumerate(pts):
            t = i / (len(pts) - 1)
            r = 0.0185 * (1 - 0.35 * t)
            ellipsoid(pt, c, (r, r * 1.15, r * 0.9), 10, 6, col=(0.78 if i % 2 else 1.0,) * 3)
        ellipsoid(pt, pts[-1] + np.array([0, -0.014, 0]), (0.006, 0.020, 0.006), 8, 6, col=(0.7, 0.7, 0.7))
    return pt


def hood():
    pt = Part('hood')
    # a hood pulled up: it hugs the skull, hangs a little over the nape and the sides of the neck, and has a rolled front edge above the eyes; no brim
    side = np.concatenate([np.linspace(-math.pi, -0.88, 48), np.linspace(0.88, math.pi, 48)])
    hair_sheet(pt, side, 0.0, lambda ps: -0.020 - 0.060 * smooth((abs(ps) - 1.2) / 1.6), lambda ps: 0.030 + 0.020 * smooth((abs(ps) - 1.6) / 1.2), 0.016, 0.022, flare=0.006, stripe=0.0, ns=18, nd=8, seed=15, dark_root=0.9, wave=0.002, vspan=0.9, tuck=0.004)
    fr = np.linspace(-0.92, 0.92, 32)
    hair_sheet(pt, fr, 0.0, lambda ps: 0.070 - 0.010 * (1 - np.cos(ps * 2.2)), 0.0, 0.016, 0.030, stripe=0.0, ns=14, nd=2, seed=16, dark_root=0.9, vspan=0.9)
    return pt


def cap():
    pt = Part('cap')
    psis = np.linspace(-math.pi, math.pi, 72)
    hair_sheet(pt, psis, 0.0, lambda ps: 0.052, 0.0, 0.008, 0.010, stripe=0.0, ns=14, nd=1, seed=17, dark_root=0.95)
    # the brim: a curved plate
    rows, cols_n = 6, 28
    verts, uvs, cc = [], [], []
    for i in range(rows):
        for j in range(cols_n):
            a = -1.05 + 2.1 * j / (cols_n - 1)
            reach = 0.002 + 0.078 * (i / (rows - 1)) * (1 - 0.35 * (a / 1.05) ** 2)
            x = math.sin(a) * (0.092 + reach * 0.9)
            z = math.cos(a) * (0.099 + reach)
            y = 0.050 - 0.012 * (i / (rows - 1)) - 0.004 * (a / 1.05) ** 2
            verts.append((x, y, z))
            uvs.append((j / (cols_n - 1), i / (rows - 1)))
            cc.append((0.9, 0.9, 0.9))
    i0 = pt.add(verts, uvs, cc)
    pt.grid(i0, rows, cols_n)
    ellipsoid(pt, (0.0, 0.112, -0.004), (0.008, 0.006, 0.008), 8, 5, col=(0.7, 0.7, 0.7))
    return pt


HAIR_STYLES = [hair_buzz, hair_undercut, hair_mohawk, hair_bob, hair_long, hair_bun, hair_braids, hood, cap]


def HEAD_PARTS(only=None):
    if only and not (only & {'head', 'body'}):
        return {}
    head = head_part()
    sc, ir = eyes_parts(head)
    ear = ear_part(head)
    out = {'head': head, 'ear': ear, 'head_lo': head_part(30, 12, 28, 'head_lo')}
    if not only or 'hair' in only or 'body' in only:
        for fn in HAIR_STYLES:
            h = fn()
            out[h.name] = h
    return out



# ---------------------------------------------------------------------------------------------------------------------------
#  export helpers: ambient occlusion baked per vertex over the assembled rest pose, then written to GLB
# ---------------------------------------------------------------------------------------------------------------------------
# where each part sits in the rig (translation in root space); (translation, mirrored)
MOUNT = {
    **{k: [((0, 1.80, 0), False)] for k in ('hair_buzz', 'hair_undercut', 'hair_mohawk', 'hair_bob', 'hair_long', 'hair_bun', 'hair_braids', 'hood', 'cap')},
    'head_lo': [((0, 1.80, 0), False)],
    'torso': [((0, 1.26, 0), False)], 'pelvis': [((0, .96, 0), False)], 'neck': [((0, 1.67, 0), False)],
    'head': [((0, 1.80, 0), False)], 'eyes': [((0, 1.80, 0), False)], 'iris': [((0, 1.80, 0), False)], 'ear': [((0, 1.80, 0), False)],
    'leg_u': [((-.105, .70, 0), False), ((.105, .70, 0), False)], 'leg_l': [((-.105, .25, 0), False), ((.105, .25, 0), False)],
    'foot': [((-.105, .04, .06), True), ((.105, .04, .06), False)],
    'arm_u': [((-.228, 1.34, 0), True), ((.228, 1.34, 0), False)], 'arm_l': [((-.228, 1.01, 0), True), ((.228, 1.01, 0), False)],
    'hand': [((-.228, .83, 0), True), ((.228, .83, 0), False)],
}


def assembled_bvh(parts, skip=()):
    verts, tris = [], []
    for name, part in parts.items():
        if name in skip or name not in MOUNT:
            continue
        for (tr, mir) in MOUNT[name]:
            pp = part.mirror_x() if mir else part
            off = len(verts)
            for v in pp.v + np.array(tr):
                verts.append(tuple(v))
            for f in pp.f:
                for k in range(1, len(f) - 1):
                    tris.append((f[0] + off, f[k] + off, f[k + 1] + off))
    return BVHTree.FromPolygons(verts, tris, epsilon=0.0)


AO_SETTINGS = {'head': (48, 0.05, 0.55), 'head_lo': (24, 0.05, 0.55), 'ear': (32, 0.04, 0.5), 'neck': (32, 0.08, 0.45), 'hand': (32, 0.03, 0.62)}


def smooth_by_position(part, ao, passes=2):
    """average the baked values over coincident vertices (the UV seams) and over neighbours, so the shading has no noise"""
    key = [tuple(np.round(v, 5)) for v in part.v]
    groups = {}
    for i, k in enumerate(key):
        groups.setdefault(k, []).append(i)
    nb = {}
    for f in part.f:
        for a_, b_ in zip(f, list(f[1:]) + [f[0]]):
            nb.setdefault(key[a_], set()).add(key[b_])
            nb.setdefault(key[b_], set()).add(key[a_])
    val = {k: float(np.mean([ao[i] for i in idx])) for k, idx in groups.items()}
    for _ in range(passes):
        new = {}
        for k, v in val.items():
            ns = nb.get(k)
            new[k] = 0.5 * v + 0.5 * (sum(val[n] for n in ns) / len(ns)) if ns else v
        val = new
    return np.array([val[k] for k in key])


def bake_ao(parts, rays=24, dist=0.11, lo=0.38, skip_names=()):
    bvh = assembled_bvh(parts)
    for name, part in parts.items():
        if name not in MOUNT or not len(part.v):
            continue
        nrays, d_max, lo_p = AO_SETTINGS.get(name, (rays, dist, lo))
        rng = np.random.default_rng(7)
        u1 = (np.arange(nrays) + rng.random(nrays)) / nrays
        u2 = rng.random(nrays)
        r = np.sqrt(u1)
        ph = TAU * u2
        local = np.stack([r * np.cos(ph), r * np.sin(ph), np.sqrt(1 - u1)], axis=1)
        tr = np.array(MOUNT[name][-1][0])
        mir = MOUNT[name][-1][1]
        pp = part.mirror_x() if mir else part
        n = pp.normals()
        ao = np.ones(len(pp.v))
        for i, (p, nn) in enumerate(zip(pp.v + tr, n)):
            t = np.cross(nn, [0, 1, 0]) if abs(nn[1]) < .9 else np.cross(nn, [1, 0, 0])
            t /= np.linalg.norm(t) + 1e-12
            b = np.cross(nn, t)
            occ = 0.0
            o = Vector(p + nn * 0.002)
            for s_ in local:
                d = Vector(t * s_[0] + b * s_[1] + nn * s_[2])
                hit = bvh.ray_cast(o, d, d_max)
                if hit[0] is not None:
                    occ += 1.0 - hit[3] / d_max
            ao[i] = 1.0 - occ / nrays
        ao = smooth_by_position(part, ao)
        part.ao = lo_p + (1 - lo_p) * np.clip(ao, 0, 1) ** 1.25
    return parts


def to_object(part):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    verts = [bm.verts.new(P(*p)) for p in part.v]
    bm.verts.ensure_lookup_table()
    for f in part.f:
        try:
            fc = bm.faces.new([verts[i] for i in f])
        except ValueError:
            continue
        for lp, i in zip(fc.loops, f):
            lp[uvl].uv = tuple(part.uv[i])
    # weld the lofts' seam columns and poles (the UVs live on the loops, so they survive)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bm.faces.ensure_lookup_table()
    seen = set()
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        island, stack = [], [f0]
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            island.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        closed = all(not e.is_boundary for f in island for e in f.edges)
        if closed:
            bmesh.ops.recalc_face_normals(bm, faces=island)
        else:
            bmesh.ops.reverse_faces(bm, faces=island)       # open shells are authored outward in game space; the axis change P() mirrors that
    me = bpy.data.meshes.new(part.name)
    bm.verts.index_update()
    bm.to_mesh(me)
    bm.free()
    # vertex colour: look the colour up by position, since remove_doubles dropped the index mapping
    key = {tuple(np.round(P(*p), 5)): i for i, p in enumerate(part.v)}
    ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    ao = getattr(part, 'ao', np.ones(len(part.v)))
    for vi, v in enumerate(me.vertices):
        k = tuple(np.round(tuple(v.co), 5))
        i = key.get(k)
        if i is None:
            c = (1, 1, 1)
            a = 1.0
        else:
            c = part.col[i]
            a = ao[i]
        ca.data[vi].color = (c[0] * a, c[1] * a, c[2] * a, 1.0)
    for pl in me.polygons:
        pl.use_smooth = True
    ob = bpy.data.objects.new(part.name, me)
    bpy.context.collection.objects.link(ob)
    mt = bpy.data.materials.new(part.name)
    mt.use_nodes = True
    ob.data.materials.append(mt)
    return ob


def clear():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for blk in (bpy.data.meshes, bpy.data.materials):
        for b in list(blk):
            blk.remove(b)


LOD_BODY = ('torso', 'pelvis', 'neck', 'leg_u', 'leg_l', 'foot', 'arm_u', 'arm_l', 'hand', 'ear')
LOD_HAIR = ('hair_buzz', 'hair_undercut', 'hair_mohawk', 'hair_bob', 'hair_long', 'hair_bun', 'hair_braids', 'hood', 'cap')
LOD_RATIO = 0.2


def export(parts, path):
    clear()
    objs = [to_object(p) for p in parts.values() if len(p.v)]
    # coarse copies of the body parts for distant people (crowds, enemies): about a fifth of the triangles
    for o in list(objs):
        if o.name in LOD_BODY or o.name in LOD_HAIR:
            lo = o.copy()
            lo.data = o.data.copy()
            lo.name = o.name + '_lo'
            bpy.context.collection.objects.link(lo)
            md = lo.modifiers.new('lod', 'DECIMATE')
            md.ratio = LOD_RATIO if o.name in LOD_BODY else 0.3
            bpy.context.view_layer.objects.active = lo
            bpy.ops.object.modifier_apply(modifier=md.name)
            objs.append(lo)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    kw = dict(filepath=path, export_format='GLB', use_selection=True, export_apply=True, export_animations=False, export_yup=True)
    for extra in ({'export_vertex_color': 'ACTIVE'}, {'export_active_vertex_color_when_no_material': True}, {}):
        try:
            bpy.ops.export_scene.gltf(**kw, **extra)
            break
        except TypeError:
            continue
    tris = sum(len(o.data.polygons) for o in objs)
    print('wrote', os.path.basename(path), os.path.getsize(path) // 1024, 'KB', len(objs), 'meshes', tris, 'faces')


def build_all(only=None):
    parts = {}
    for fn in BODY:
        if only and fn.__name__ not in only and 'body' not in only:
            continue
        pt = fn()
        parts[pt.name] = pt
        print(' ', pt.name, len(pt.v), 'verts', len(pt.f), 'faces')
    try:
        from_head = HEAD_PARTS(only)
        parts.update(from_head)
    except NameError:
        pass
    bake_ao(parts)
    export(parts, os.path.join(OUT, 'human_kit.glb'))


if __name__ == '__main__':
    only = set(sys.argv[sys.argv.index('--') + 1:]) if '--' in sys.argv else None
    build_all(only)
