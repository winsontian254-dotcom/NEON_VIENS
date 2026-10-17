"""Geometry from the MakeHuman base mesh (CC0, assets/src/makehuman) for the Neon Veins human kit.

Pure numpy (no bpy), so it can be tested on its own:  python3 tools/blender/mh_import.py   (prints sizes)

MakeHuman works in decimetres, y up, the character faces +z and its LEFT side is +x. The game works in metres with the character's
RIGHT side at +x, so every point goes through  (x, y, z) -> (-x, y, z) * 0.1  (and every face is wound the other way round).

head_geometry()  the head and neck down to just under the jacket collar, in the head frame of build_humans.py (origin = skull centre,
                 eye line at y = EYE_Y); also returns per-vertex masks (lips, brows, ears, nose) taken from the vertices MakeHuman's own
                 morph targets move
hand_geometry()  the right hand with a little forearm, posed hanging relaxed (fingers down and curled a little, thumb forward, palm toward
                 the thigh), in the frame of the rig's hand node (wrist at y = +0.045)
eyes_geometry()  the two eyeballs of MakeHuman's high-poly eyes fitted to the head (UVs are the eye texture's)
"""
import json
import math
import os
import re
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MHDIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'assets', 'src', 'makehuman')
S = 0.1                      # decimetres -> metres
EYE_Y = 0.012                # height of the eye line in the head frame
NECK_CUT = 5.8               # MakeHuman y (dm) where the head part ends (just under the jacket collar)


def parse_obj(path):
    V, VT, F, cur = [], [], [], None
    for line in open(path):
        p = line.split()
        if not p:
            continue
        if p[0] == 'v':
            V.append([float(x) for x in p[1:4]])
        elif p[0] == 'vt':
            VT.append([float(x) for x in p[1:3]])
        elif p[0] in ('g', 'o'):
            cur = p[1]
        elif p[0] == 'f':
            F.append((cur, [tuple((int(i) - 1) if i else -1 for i in t.split('/')[:2]) for t in p[1:]]))
    return np.array(V), np.array(VT), F


class MH:
    def __init__(self):
        self.V, self.VT, self.F = parse_obj(os.path.join(MHDIR, 'base.obj'))
        self.body = [f for g, f in self.F if g == 'body']
        self.skel = json.load(open(os.path.join(MHDIR, 'rigs', 'default.mhskel')))
        self.weights = json.load(open(os.path.join(MHDIR, 'rigs', 'default_weights.mhw')))['weights']

    def joint(self, name):
        return self.V[self.skel['joints'][name]].mean(0)

    def w(self, bone, n=None):
        """dense weight array of one bone"""
        a = np.zeros(len(self.V) if n is None else n)
        for i, x in self.weights.get(bone, []):
            a[i] = x
        return a


def split_faces(faces, vmap_pos, vt, flip=True):
    """faces: [[(v, vt), ...]] -> (positions index per new vertex, uv per new vertex, new faces); a vertex is split per (v, vt) pair"""
    key, src, uv, out = {}, [], [], []
    for f in faces:
        nf = []
        for v, t in f:
            k = (v, t)
            if k not in key:
                key[k] = len(src)
                src.append(v)
                uv.append(vt[t] if t >= 0 else (0.0, 0.0))
            nf.append(key[k])
        out.append(tuple(reversed(nf)) if flip else tuple(nf))
    return np.array(src), np.array(uv), out


def _region(mh, patterns):
    """{base-mesh vertex: strength 0..1} of the vertices moved by the given MakeHuman morph targets (files copied under assets/src/makehuman/targets);
    the strength is the size of the displacement relative to the largest one, so the soft edges of a target fade out"""
    idx = {}
    tdir = os.path.join(MHDIR, 'targets')
    for pat in patterns:
        for fn in sorted(os.listdir(tdir)) if os.path.isdir(tdir) else []:
            if re.fullmatch(pat, fn):
                rows = []
                for line in open(os.path.join(tdir, fn)):
                    if line and line[0] not in '#\n ':
                        q = line.split()
                        rows.append((int(q[0]), math.sqrt(sum(float(x) ** 2 for x in q[1:4]))))
                mx = max((m for _, m in rows), default=1.0) or 1.0
                for v, m in rows:
                    idx[v] = max(idx.get(v, 0.0), m / mx)
    return idx


def head_geometry(mh=None):
    mh = mh or MH()
    ey = mh.joint('eye.L____head')
    zc = 0.645                                                       # the skull centre in z (dm): the head bounding box is -0.39 .. 1.68
    def to_head(p):
        p = np.atleast_2d(p)
        return np.stack([-p[:, 0] * S, (p[:, 1] - ey[1]) * S + EYE_Y, (p[:, 2] - zc) * S], axis=1)
    keep = [f for f in mh.body if all(mh.V[v][1] > NECK_CUT for v, _ in f)]
    # the cut follows the vertex rows, which makes a ragged edge: put every boundary vertex on the cut plane
    ec = {}
    for f in keep:
        for (a_, _), (b_, _) in zip(f, f[1:] + f[:1]):
            k = (min(a_, b_), max(a_, b_))
            ec[k] = ec.get(k, 0) + 1
    bnd = {v for (a_, b_), c in ec.items() if c == 1 for v in (a_, b_)}
    Vh = mh.V.copy()
    for v in bnd:
        Vh[v][1] = NECK_CUT
    # UVs: a cylindrical projection round the skull (the face texture of the game is only skin tone and fine pores, so a smooth mapping is
    # better than MakeHuman's own layout, which crams the scalp into a tiny island); the seam is at the back of the head
    allpos = to_head(Vh)
    def u_of(v):
        x, y, z = allpos[v]
        return (math.atan2(x, z) + math.pi) / (2 * math.pi)
    key, src_l, uv_l, faces = {}, [], [], []
    for f in keep:
        us = [u_of(v) for v, _ in f]
        wrap = max(us) - min(us) > 0.5
        nf = []
        for (v, _), u in zip(f, us):
            if wrap and u < 0.5:
                u += 1.0
            vv = 0.5 + allpos[v][1] / 0.34
            k = (v, round(u, 5))
            if k not in key:
                key[k] = len(src_l)
                src_l.append(v)
                uv_l.append((u, vv))
            nf.append(key[k])
        faces.append(tuple(reversed(nf)))
    src, uv = np.array(src_l), np.array(uv_l)
    pos = allpos[src]
    # masks from the morph targets' vertex sets
    sets = {
        'lips': _region(mh, [r'mouth-(lower|upper)lip-(volume|height|width)-incr\.target', r'mouth-cupidsbow-incr\.target']),
        'brows': _region(mh, [r'eyebrows-(trans-up|angle-up|trans-down)\.target']),
        'ears': _region(mh, [r'[lr]-ear-(scale|flap)-incr\.target']),
        'nose': _region(mh, [r'nose-(scale-vert|flaring|width1)-incr\.target', r'nose-base-up\.target']),
    }
    masks = {k: np.array([v.get(int(s), 0.0) for s in src]) for k, v in sets.items()}
    # each mask is also limited to where its feature really is (the morph targets reach out over a wide area)
    ym = np.median(pos[masks['lips'] > 0.5][:, 1])
    # the lips themselves: about 1 cm above and below the mouth line, 2.5 cm to each side (the targets also move the philtrum and the chin crease)
    fade = lambda a, lo, hi: np.clip((hi - a) / (hi - lo), 0.0, 1.0)
    masks['lips'] = np.clip(masks['lips'] * 3.0, 0.0, 1.0) * fade(np.abs(pos[:, 1] - ym), 0.0075, 0.0115) * fade(np.abs(pos[:, 0]), 0.021, 0.029) * (pos[:, 2] > 0.06)
    masks['ears'] = masks['ears'] * ((np.abs(pos[:, 0]) > 0.055) & (pos[:, 2] < 0.03) & (pos[:, 1] > -0.04) & (pos[:, 1] < 0.05))
    masks['nose'] = masks['nose'] * ((np.abs(pos[:, 0]) < 0.026) & (pos[:, 1] > -0.05) & (pos[:, 1] < 0.0) & (pos[:, 2] > 0.075))
    masks['brows'] = masks['brows'] * 0
    return {'pos': pos, 'uv': uv, 'faces': faces, 'src': src, 'masks': masks, 'to_head': to_head, 'eye_mh': ey}


def eyes_geometry(mh=None):
    """MakeHuman proxies place their vertices as barycentric weights of three base vertices plus scaled offsets (the .mhclo file)"""
    mh = mh or MH()
    lines = open(os.path.join(MHDIR, 'eyes', 'high-poly.mhclo')).read().splitlines()
    sc = {}
    for ln in lines:
        m = re.match(r'([xyz])_scale (\d+) (\d+) ([\d.]+)', ln)
        if m:
            sc[m.group(1)] = (int(m.group(2)), int(m.group(3)), float(m.group(4)))
    i0 = next(i for i, ln in enumerate(lines) if ln.startswith('verts')) + 1
    refs = []
    for ln in lines[i0:]:
        p = ln.split()
        if len(p) >= 9:
            refs.append(p)
    scale = [abs(mh.V[sc[a][0]][k] - mh.V[sc[a][1]][k]) / sc[a][2] for k, a in enumerate('xyz')]
    pts = []
    for p in refs:
        a, b, c = int(p[0]), int(p[1]), int(p[2])
        w = [float(x) for x in p[3:6]]
        d = [float(x) * s for x, s in zip(p[6:9], scale)]
        pts.append(mh.V[a] * w[0] + mh.V[b] * w[1] + mh.V[c] * w[2] + np.array(d))
    pts = np.array(pts)
    EV, EVT, EF = parse_obj(os.path.join(MHDIR, 'eyes', 'high-poly.obj'))
    # half of the faces are the glassy cornea shell: its UVs sit on the pale blue disc in the corner of the texture, and it would hide the iris, so drop it
    keep = []
    for _, f in EF:
        c = np.mean([EVT[t] for _, t in f], axis=0)
        if math.hypot(c[0] - 0.934, c[1] - 0.066) > 0.06:
            keep.append(f)
    src, uv, faces = split_faces(keep, None, EVT)
    return pts, src, uv, faces


def _rot_z(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _frame_from(a, b):
    """right-handed orthonormal frame with its first axis along a and the second as close as possible to b"""
    a = a / np.linalg.norm(a)
    b = b - a * np.dot(a, b)
    b /= np.linalg.norm(b)
    return np.stack([a, b, np.cross(a, b)], axis=1)


def hand_geometry(mh=None, curl=(1.0, 1.0, 1.0, 1.0, 1.0), side='R'):
    mh = mh or MH()
    V = mh.V
    hand_bones = ['wrist.' + side] + ['metacarpal%d.%s' % (i, side) for i in range(1, 5)] + ['finger%d-%d.%s' % (f, k, side) for f in range(1, 6) for k in range(1, 4)]
    wh = np.zeros(len(V))
    for b in hand_bones:
        wh += mh.w(b)
    wrist = mh.joint('wrist.%s____head' % side)
    # a short piece of forearm so the sleeve can overlap the skin: body vertices near the wrist on the arm side
    fore = mh.w('lowerarm02.' + side) + mh.w('lowerarm01.' + side)
    d_wrist = np.linalg.norm(V - wrist, axis=1)
    arm_ok = (fore > 0.5) & (d_wrist < 0.55)
    sel = (wh > 0.12) | arm_ok
    # frame: the hand axis (wrist -> middle fingertip) and the thumb side (index base -> pinky base)
    tip = mh.joint('finger3-3.%s____tail' % side)
    idx = mh.joint('finger2-1.%s____head' % side)
    pnk = mh.joint('finger5-1.%s____head' % side)
    thumb = mh.joint('finger1-1.%s____head' % side)
    axis = tip - wrist
    side_vec = (idx - pnk)
    # source frame (mesh): e0 = hand axis, e1 = towards the index finger side, e2 = e0 x e1 (the palm normal or its opposite)
    Fsrc = _frame_from(axis, side_vec)
    # target frame (game, right hand at +x): axis -> -y (down), index side -> +z (forward); then the palm normal e2 lands on one of +-x
    # which is decided by the chirality of the mesh; the mesh is mirrored to game space first, so use game coordinates for the frame
    def g(p):
        p = np.atleast_2d(p)
        return np.stack([-p[:, 0], p[:, 1], p[:, 2]], axis=1)
    gw, gt, gi, gp, gth = g(wrist)[0], g(tip)[0], g(idx)[0], g(pnk)[0], g(thumb)[0]
    Fg = _frame_from(gt - gw, gi - gp)
    Ft = _frame_from(np.array([0.0, -1.0, 0.0]), np.array([0.0, 0.0, 1.0]))
    R = Ft @ Fg.T                                                    # game-space rotation taking the hand into the hanging pose
    pts_g = g(V)
    pose = lambda P: (np.atleast_2d(P) - gw) @ R.T
    # joints (in the hanging frame, before the curl)
    def J(name):
        return pose(g(mh.joint(name)))[0]
    # finger curl: forward kinematics down each finger chain, flexion about the z axis towards -x (the palm side)
    base_deg = {1: (6, 12, 8), 2: (16, 28, 12), 3: (22, 36, 14), 4: (28, 42, 18), 5: (34, 48, 22)}
    Vp = pose(pts_g)
    out = Vp.copy()
    acc = {}
    for f in range(1, 6):
        joints = [J('finger%d-%d.%s____head' % (f, k, side)) for k in (1, 2, 3)] + [J('finger%d-3.%s____tail' % (f, side))]
        wts = [mh.w('finger%d-%d.%s' % (f, k, side)) for k in (1, 2, 3)]
        M = np.eye(4)
        for k in range(3):
            jk = joints[k]
            ang = -base_deg[f][k] * curl[f - 1]
            if f == 1:
                ang = -ang * 0.8                                       # the thumb folds the other way round (towards the palm along z)
            Rk = np.eye(4)
            Rk[:3, :3] = _rot_z(ang)
            T1, T2 = np.eye(4), np.eye(4)
            T1[:3, 3] = jk
            T2[:3, 3] = -jk
            M = M @ (T1 @ Rk @ T2)
            acc[(f, k)] = (M.copy(), wts[k])
    tips, knuck = [], []
    for f in range(1, 6):                                            # fingertip and knuckle positions (hand node space), for the nails and the knuckle tint
        tail = np.append(J('finger%d-3.%s____tail' % (f, side)), 1.0)
        tp = (acc[(f, 2)][0] @ tail)[:3]
        kp = J('finger%d-1.%s____head' % (f, side))
        tips.append(tp * S + np.array([0.0, 0.045, 0.0]))
        knuck.append(kp * S + np.array([0.0, 0.045, 0.0]))
    wsum = np.zeros(len(V))
    for (f, k), (M, w) in acc.items():
        wsum += w
    wsum = np.minimum(wsum, 1.0)
    res = Vp * (1 - wsum)[:, None]
    for (f, k), (M, w) in acc.items():
        h = np.concatenate([Vp, np.ones((len(Vp), 1))], axis=1)
        res += (h @ M.T)[:, :3] * w[:, None]
    # faces of the selection
    sel_idx = set(np.nonzero(sel)[0])
    keep = [f for f in mh.body if all(v in sel_idx for v, _ in f)]
    keep = [f for f in keep if all(res[v][1] * S + 0.045 < 0.052 for v, _ in f)]       # the forearm stub ends a few millimetres above the wrist: it lives inside the sleeve
    src, uv, faces = split_faces(keep, None, mh.VT)
    pos = res[src] * S                                              # decimetres -> metres, relative to the wrist
    pos[:, 1] += 0.045                                              # the wrist sits at y = +0.045 of the hand node
    return {'pos': pos, 'uv': uv, 'faces': faces, 'src': src, 'tips': np.array(tips), 'knuck': np.array(knuck)}


if __name__ == '__main__':
    mh = MH()
    h = head_geometry(mh)
    print('head uv', h['uv'].min(0).round(3), h['uv'].max(0).round(3))
    print('head', len(h['pos']), 'verts', len(h['faces']), 'faces', h['pos'].min(0).round(3), h['pos'].max(0).round(3), {k: int(v.sum()) for k, v in h['masks'].items()})
    hd = hand_geometry(mh)
    print('hand', len(hd['pos']), 'verts', len(hd['faces']), 'faces', hd['pos'].min(0).round(3), hd['pos'].max(0).round(3))
    e, *_ = eyes_geometry(mh)
    print('eyes', len(e), (e.min(0) * 0.1).round(3), (e.max(0) * 0.1).round(3))
