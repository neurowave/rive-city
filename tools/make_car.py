"""Sculpted hovercar: exterior body + full cabin, built from SDFs.

Car local space: metres, x right, y up, z back (forward is -z). Origin on the
hover plane. Every part is a signed-distance function meshed with marching
cubes, shaded with smooth SDF-gradient normals, and carries baked ambient
occlusion in uv.x. uv.y carries a pattern flag for the shader:
  0 plain, 1 diamond quilting, 2 perforation, 3 vent slats, 4 speaker grille,
  5 knurling
Materials are separate meshes (world.as gives each its shader material id).
"""
import math
import time
import numpy as np
import sdf as S
from sdf import V

# ================================================================ helpers
def emit(meshes, prefix, v, n, f, names, ao, flag, uvx=None):
    """split one MC part into per-material meshes"""
    if len(f) == 0:
        return
    for name in np.unique(names):
        sel = f[names == name]
        used, inv = np.unique(sel.ravel(), return_inverse=True)
        u = ao[used] if uvx is None else uvx[used]
        vv = np.concatenate([v[used], n[used], u[:, None], flag[used][:, None]], 1).astype(np.float32)
        key = prefix + name
        if key not in meshes:
            from meshpack import Mesh
            meshes[key] = Mesh(key)
        meshes[key].add(vv, inv.reshape(-1))


def emit_groups(meshes, prefix, fn, v, f, names, target, step, ao_fn, flag_fn=None):
    """material-first decimation: names per raw MC face"""
    for name, gv, gn, gf in S.split_decimate(fn, v, f, np.asarray(names).astype(str), target, step):
        ao = ao_fn(gv, gn)
        flag = flag_fn(gv) if flag_fn is not None else np.zeros(len(gv))
        emit(meshes, prefix, gv, gn, gf, np.full(len(gf), name), ao, flag)


def tube(meshes, key, pts, r, sides=8, u0=0.0, u1=1.0, nrm_up=(0, 1, 0)):
    """explicit round tube along a polyline, uv.x = 0..1 along (ambient strips)"""
    from meshpack import Mesh
    if key not in meshes:
        meshes[key] = Mesh(key)
    pts = np.asarray(pts, float)
    L = len(pts)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    seg = seg / max(seg[-1], 1e-9)
    verts = []
    for i, p in enumerate(pts):
        t = pts[min(i + 1, L - 1)] - pts[max(i - 1, 0)]
        t /= np.linalg.norm(t)
        a = np.cross(t, np.array(nrm_up, float))
        if np.linalg.norm(a) < 1e-6:
            a = np.cross(t, np.array([1.0, 0, 0]))
        a /= np.linalg.norm(a)
        b = np.cross(a, t)
        for s in range(sides):
            ang = 2 * math.pi * s / sides
            d = a * math.cos(ang) + b * math.sin(ang)
            q = p + d * r
            verts.append((*q, *d, u0 + (u1 - u0) * seg[i], 0.0))
    idx = []
    for i in range(L - 1):
        for s in range(sides):
            s2 = (s + 1) % sides
            a, b, c, d = i * sides + s, i * sides + s2, (i + 1) * sides + s2, (i + 1) * sides + s
            idx += [a, b, c, a, c, d]
    meshes[key].add(verts, idx)


def disc(meshes, key, c, r, y_up=True, k=40, n=(0, -1, 0)):
    from meshpack import Mesh
    if key not in meshes:
        meshes[key] = Mesh(key)
    c = np.asarray(c, float)
    verts = [(*c, *n, 0.0, 0.0)]
    for i in range(k + 1):
        a = 2 * math.pi * i / k
        verts.append((c[0] + r * math.cos(a), c[1], c[2] + r * math.sin(a), *n, 1.0, 0.0))
    idx = []
    for i in range(k):
        idx += [0, i + 2, i + 1]
    meshes[key].add(verts, idx)


def timed(label, fn):
    t = time.time()
    r = fn()
    print(f"  {label}: {time.time() - t:.1f}s")
    return r


# ================================================================ exterior
def body_prof(z):
    zs = [-2.42, -2.36, -2.2, -1.7, -1.1, 0.0, 1.0, 1.9, 2.3, 2.42]
    hw = [0.66, 0.84, 0.94, 1.0, 1.01, 1.0, 1.02, 0.99, 0.92, 0.80]
    yb = [0.44, 0.38, 0.34, 0.31, 0.30, 0.30, 0.30, 0.32, 0.37, 0.44]
    yt = [0.56, 0.62, 0.68, 0.76, 0.86, 0.91, 0.93, 0.95, 0.94, 0.86]
    return np.interp(z, zs, hw), np.interp(z, zs, yb), np.interp(z, zs, yt)


def body_outer(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    hw, yb, yt = body_prof(np.clip(z, -2.42, 2.42))
    cy = (yb + yt) * 0.5
    hh = (yt - yb) * 0.5
    # hull section: tucked under, full at the shoulder, tumblehome to the top
    tt = np.clip((y - yb) / np.maximum(yt - yb, 1e-3), 0, 1)
    tuck = np.clip((0.3 - tt) / 0.3, 0, 1) ** 2
    crown = np.clip((tt - 0.75) / 0.25, 0, 1) ** 2
    hwy = hw * (1.0 - 0.12 * tuck - 0.06 * crown)
    r = 0.11
    qx = np.abs(x) - (hwy - r)
    qy = np.abs(y - cy) - (hh - r)
    d = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - r
    d = S.smax(d, np.abs(z) - 2.42, 0.10)
    m = S.mirror_x(p)
    # haunches over the four thruster pods
    for zc, rz in ((-1.55, 0.62), (1.45, 0.80)):
        d = S.smin(d, S.ellipsoid(m, (0.88, 0.60, zc), (0.20, 0.24, rz)), 0.14)
    # side intake carved behind the door
    d = S.smax(d, -S.ellipsoid(m, (1.10, 0.62, 1.05), (0.13, 0.10, 0.42)), 0.05)
    # front intake + rear diffuser cavities
    d = S.smax(d, -S.round_box(p, (0, 0.43, -2.42), (0.64, 0.065, 0.12), 0.04), 0.03)
    d = S.smax(d, -S.round_box(p, (0, 0.34, 2.42), (0.62, 0.07, 0.22), 0.04), 0.03)
    # hood: twin power ridges + ducktail lip
    d = S.smin(d, S.capsule(m, (0.34, 0.74, -2.05), (0.30, 0.85, -1.3), 0.03), 0.05)
    d = S.smin(d, S.capsule(p, (-0.80, 0.955, 2.30), (0.80, 0.955, 2.30), 0.025), 0.07)
    return d


def body_shell(p):
    d = body_outer(p)
    # open cabin tub (the canopy closes it)
    cav = S.round_box(p, (0, 1.31, 0.06), (0.90, 0.95, 1.19), 0.08)
    return S.smax(d, -cav, 0.03)


CAN_Z = [-1.26, -1.05, -0.6, -0.2, 0.2, 0.8, 1.4, 1.9, 2.3]
CAN_Y = [0.86, 1.00, 1.22, 1.38, 1.43, 1.42, 1.29, 1.11, 0.97]
CAN_W = [0.70, 0.84, 0.92, 0.94, 0.94, 0.93, 0.89, 0.82, 0.70]


def canopy_raw(p):
    """fastback canopy: profile-lofted arch, base buried in the body"""
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    zc = np.clip(z, CAN_Z[0], CAN_Z[-1])
    top = np.interp(zc, CAN_Z, CAN_Y)
    wb = np.interp(zc, CAN_Z, CAN_W)
    base = 0.62
    cy = (top + base) * 0.5
    hh = (top - base) * 0.5
    tt = np.clip((y - base) / np.maximum(top - base, 1e-3), 0, 1)
    w = wb * (1.0 - 0.24 * tt ** 2.2)
    r = np.minimum(0.24, hh * 0.9)
    qx = np.abs(x) - (w - r)
    qy = np.abs(y - cy) - (hh - r)
    d = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - r
    d = S.smax(d, CAN_Z[0] + 0.02 - z, 0.12)
    d = S.smax(d, z - (CAN_Z[-1] - 0.02), 0.12)
    return d * 0.8


def ext_detail(p):
    """carbon aero bits: splitter, skirts, diffuser fins, fastback louvers"""
    m = S.mirror_x(p)
    d = S.round_box(p, (0, 0.335, -2.22), (0.88, 0.022, 0.22), 0.018)                 # splitter
    d = np.minimum(d, S.round_box(m, (1.0, 0.33, 0.0), (0.035, 0.03, 1.55), 0.025))    # skirts
    for fx in (-0.42, -0.21, 0.0, 0.21, 0.42):                                     # diffuser fins
        d = np.minimum(d, S.round_box(p, (fx, 0.355, 2.28), (0.008, 0.065, 0.2), 0.006))
    # fastback louvers lying on the painted tail of the canopy
    for zl in np.linspace(1.42, 2.08, 7):
        yl = float(np.interp(zl, CAN_Z, CAN_Y))
        wl = float(np.interp(zl, CAN_Z, CAN_W)) * 0.62
        d = np.minimum(d, S.round_box(p, (0, yl + 0.006, zl), (wl, 0.012, 0.022), 0.008))
    return d


def nacelles(p):
    m = S.mirror_x(p)
    q = m.copy()
    q[:, 2] = np.abs(q[:, 2])
    d = S.torus(q, (0.62, 0.30, 1.5), 1, 0.30, 0.045)
    d = np.minimum(d, S.cyl(q, (0.62, 0.30, 1.5), 1, 0.14, 0.035, 0.01))
    for a in (0.0, 2.094, 4.189):
        c = V(0.62, 0.30, 1.5)
        e = c + V(math.cos(a), 0, math.sin(a)) * 0.29
        d = np.minimum(d, S.capsule(q, c, e, 0.012))
    return d


def ext_scene(p):
    return np.minimum(np.minimum(np.minimum(body_shell(p), ext_detail(p)), nacelles(p)), canopy_raw(p))


def surface_line(fn, pts, direction, inset):
    """project points onto the surface along direction, pull them inset back"""
    pts = np.asarray(pts, float)
    d = np.asarray(direction, float)
    hit = S.march(fn, pts, d, 3.0)
    return hit - d * (-inset)


def build_exterior(meshes, prefix, step, lights=True, see_through=True, budget=1.0):
    print(f"exterior {prefix} @ {step * 100:.1f} cm")

    def T(n):
        return int(n * budget)

    def ao_ext(scale):
        return lambda v, n: S.bake_ao(ext_scene, v, n, scale, 1.0)

    lo, hi = (-1.1, 0.18, -2.55), (1.1, 1.52, 2.55)
    v, _, f = timed("body", lambda: S.mesh_part(body_shell, lo, hi, step, raw=True))
    cen = v[f].mean(1)
    fn_ = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    fn_ /= np.maximum(np.linalg.norm(fn_, axis=1), 1e-12)[:, None]
    gn = S.grad(body_shell, cen, step * 0.5)
    names = np.full(len(f), "paint", dtype=object)
    names[cen[:, 1] < 0.40] = "black"
    names[(cen[:, 1] < 0.52) & (np.abs(cen[:, 2]) > 2.3)] = "black"           # intake / diffuser surround
    inward = gn[:, 0] * np.sign(cen[:, 0]) < -0.2
    inner = inward & (np.abs(cen[:, 0]) < 0.94) & (cen[:, 1] > 0.33) & (cen[:, 2] > -1.2) & (cen[:, 2] < 1.3)
    names[inner] = "black"                                                    # cabin tub walls
    intake = S.ellipsoid(S.mirror_x(cen), (1.10, 0.62, 1.05), (0.15, 0.12, 0.44)) < 0.0
    names[intake] = "black"
    emit_groups(meshes, prefix, body_shell, v, f, names, T(52000), step, ao_ext(0.25))

    v, _, f = timed("detail", lambda: S.mesh_part(ext_detail, lo, hi, step * 0.7, raw=True))
    emit_groups(meshes, prefix, ext_detail, v, f, np.full(len(f), "carbon"), T(16000), step * 0.7, ao_ext(0.2))

    v, _, f = timed("nacelles", lambda: S.mesh_part(nacelles, (-1.0, 0.18, -1.9), (1.0, 0.42, 1.9), step * 0.6, raw=True))
    cen = v[f].mean(1)
    names = np.where(cen[:, 1] > 0.31, "black", "metal")
    emit_groups(meshes, prefix, nacelles, v, f, names, T(12000), step * 0.6, ao_ext(0.15))

    # canopy: only the dome above the body
    def keep(c):
        return body_outer(c) > -0.004
    v, _, f = timed("canopy", lambda: S.mesh_part(canopy_raw, (-1.0, 0.6, -1.4), (1.0, 1.55, 2.45), step * 0.8, keep, raw=True))
    cen = v[f].mean(1)
    names = np.full(len(f), "glass", dtype=object)
    names[cen[:, 2] > 1.30] = "paint"                                          # painted fastback
    yb_ = body_prof(cen[:, 2])[2]
    names[(cen[:, 1] < yb_ + 0.07) & (names == "glass")] = "black"              # daylight-opening band
    names[(cen[:, 2] > 1.22) & (cen[:, 2] <= 1.30)] = "black"
    emit_groups(meshes, prefix, canopy_raw, v, f, names, T(14000), step * 0.8, ao_ext(0.2))

    if not lights:
        return
    # LED headlight blade traced onto the nose, corner fangs, tail bars, accent line
    xs = np.linspace(-0.84, 0.84, 41)
    head = surface_line(body_outer, [(x, 0.645 - 0.04 * (x / 0.84) ** 2, -3.0) for x in xs], (0, 0, 1), -0.004)
    tube(meshes, prefix + "light", head, 0.013, 8)
    for sx in (-1, 1):
        ys = np.linspace(0.70, 0.50, 9)
        fang = surface_line(body_outer, [(sx * 0.84, y, -3.0) for y in ys], (0, 0, 1), -0.003)
        tube(meshes, prefix + "light", fang, 0.01, 6)
    tail = surface_line(body_outer, [(x, 0.80, 3.0) for x in np.linspace(-0.82, 0.82, 41)], (0, 0, -1), -0.004)
    tube(meshes, prefix + "tail", tail, 0.016, 8)
    tail2 = None and surface_line(body_outer, [(x, 0.60, 3.0) for x in np.linspace(-0.66, 0.66, 31)], (0, 0, -1), -0.003)
    # single hot bar (two lines bloomed into one red panel)
    for sx in (-1, 1):
        zs = np.linspace(-2.05, 2.15, 60)
        line = surface_line(body_outer, [(sx * 1.4, 0.47 + 0.02 * math.sin(z * 0.8), z) for z in zs], (-sx, 0, 0), -0.002)
        tube(meshes, prefix + "accent", line, 0.006, 6)
    # thruster discs (uv.x = radius for the shader)
    for sx in (-0.62, 0.62):
        for sz in (-1.5, 1.5):
            disc(meshes, prefix + "thrust", (sx, 0.262, sz), 0.27)


# ================================================================ cabin (car space)
DASH_POLY = [(-1.28, 0.36), (-1.28, 0.886), (-1.13, 0.886), (-0.95, 0.877), (-0.75, 0.866), (-0.60, 0.852),
             (-0.52, 0.826), (-0.485, 0.79), (-0.478, 0.74), (-0.50, 0.62), (-0.56, 0.48), (-0.64, 0.36)]


# centre screen frame (must match cabin.as csPos / csYaw / csPitch)
# solved by tools/place_cs.py: floats >= 12 mm clear of every cabin surface
CS_POS = V(0.115, 0.925, -0.38)   # raised so the whole screen sits above the 2D bottom bars (tools/place_cs_view.py)
CS_YAW, CS_PITCH = -0.52, -0.20
CS_W, CS_H = 0.21, 0.28


def cs_local(p):
    """car space -> centre-screen local (x right, y up, +z toward the driver)"""
    q = p - CS_POS
    cy, sy = math.cos(-CS_YAW), math.sin(-CS_YAW)
    x = q[:, 0] * cy + q[:, 2] * sy
    z = -q[:, 0] * sy + q[:, 2] * cy
    y = q[:, 1]
    cp, sp = math.cos(-CS_PITCH), math.sin(-CS_PITCH)
    y2 = y * cp - z * sp
    z2 = y * sp + z * cp
    return np.stack([x, y2, z2], -1)


def centre_stack(p):
    q = cs_local(p)
    d = S.box_local(q - V(0, -0.02, -0.075), (CS_W / 2 + 0.035, CS_H / 2 + 0.055, 0.06), 0.025)
    # flare the bottom of the stack down into the console
    d = S.smin(d, S.box_local(q - V(0, -0.20, -0.10), (CS_W / 2 + 0.01, 0.06, 0.07), 0.03), 0.06)
    return d


def dash(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    sag = 0.03 * (x / 0.93) ** 2
    d = S.poly2(z, y + sag, DASH_POLY) - 0.012
    d = S.smax(d, np.abs(x) - 0.925, 0.05)
    # cluster pod rising into the display stem
    d = S.smin(d, S.round_box(p, (-0.37, 0.872, -0.70), (0.27, 0.03, 0.12), 0.03), 0.06)
    # vent slots across the face (passenger side + far driver side)
    d = S.smax(d, -S.round_box(p, (0.47, 0.713, -0.47), (0.36, 0.018, 0.04), 0.012), 0.006)
    d = S.smax(d, -S.round_box(p, (-0.80, 0.713, -0.47), (0.10, 0.018, 0.04), 0.012), 0.006)
    # tweeter pods on the dash top corners
    m = S.mirror_x(p)
    d = S.smax(d, -S.cyl(m, (0.74, 0.885, -0.93), 1, 0.055, 0.012, 0.004), 0.006)
    # knee bolster recess under the column
    d = S.smax(d, -S.ellipsoid(p, (-0.37, 0.52, -0.50), (0.26, 0.12, 0.08)), 0.04)
    return d


def console(p):
    d = S.round_box(p, (0, 0.47, 0.10), (0.15, 0.13, 0.56), 0.05)
    # ramp up into the dash
    rp = S.rot_x(p, (0, 0.52, -0.52), 0.55)
    d = S.smin(d, S.box_local(rp, (0.13, 0.05, 0.16), 0.04), 0.06)
    # armrest cushion
    d = S.smin(d, S.round_box(p, (0, 0.625, 0.42), (0.125, 0.035, 0.22), 0.03), 0.02)
    # gear puck seat + three toggles
    d = S.smax(d, -S.cyl(p, (0, 0.60, -0.12), 1, 0.062, 0.02, 0.004), 0.004)
    d = np.minimum(d, S.torus(p, (0, 0.598, -0.12), 1, 0.052, 0.009))
    for bx in (-0.06, 0.0, 0.06):
        d = np.minimum(d, S.round_box(p, (bx, 0.603, -0.30), (0.018, 0.008, 0.026), 0.006))
    return d


def door(p):
    m = S.mirror_x(p)
    d = S.round_box(m, (0.915, 0.63, 0.03), (0.035, 0.30, 1.0), 0.025)
    # follow the hull's tuck at the bottom
    d = S.smax(d, m[:, 0] - (0.86 + 0.25 * np.clip(m[:, 1] - 0.33, 0, 1)), 0.02)
    d = S.smin(d, S.capsule(m, (0.875, 0.645, -0.30), (0.875, 0.645, 0.70), 0.045), 0.05)   # armrest
    d = S.smin(d, S.round_box(m, (0.92, 0.905, 0.03), (0.07, 0.025, 1.0), 0.02), 0.03)       # sill
    d = S.smax(d, -S.sphere(m, (0.81, 0.47, -0.55), 0.13), 0.02)                           # speaker dish
    d = S.smax(d, -S.round_box(m, (0.90, 0.765, -0.25), (0.03, 0.03, 0.11), 0.02), 0.01)     # handle cup
    d = np.minimum(d, S.capsule(m, (0.893, 0.765, -0.33), (0.893, 0.765, -0.17), 0.011))     # handle
    return d


def seat(p, cx):
    q = p - V(cx, 0, 0)
    d = S.round_box(q, (0, 0.47, 0.18), (0.23, 0.065, 0.26), 0.06)
    for sx in (-1, 1):
        d = S.smin(d, S.capsule(q, (sx * 0.215, 0.52, -0.05), (sx * 0.215, 0.53, 0.40), 0.07), 0.05)
    bk = S.rot_x(q, (0, 0.92, 0.55), -0.26)
    d = S.smin(d, S.box_local(bk, (0.22, 0.40, 0.055), 0.05), 0.06)
    for sx in (-1, 1):
        d = S.smin(d, S.capsule(q, (sx * 0.215, 0.60, 0.48), (sx * 0.19, 1.08, 0.62), 0.075, 0.06), 0.05)
    hr = S.rot_x(q, (0, 1.30, 0.66), -0.26)
    d = S.smin(d, S.box_local(hr, (0.14, 0.11, 0.05), 0.045), 0.06)
    d = S.smax(d, -S.box_local(S.rot_x(q, (0, 1.16, 0.63), -0.26), (0.055, 0.028, 0.2), 0.02), 0.01)  # slot
    return d


def seats(p):
    return np.minimum(seat(p, -0.37), seat(p, 0.40))


def frame(p):
    m = S.mirror_x(p)
    pts = [(0.91, 0.90, -1.10), (0.84, 1.12, -0.62), (0.76, 1.33, -0.2), (0.72, 1.405, 0.1), (0.70, 1.40, 1.25)]
    d = S.chain(m, pts, [0.04, 0.036, 0.034, 0.036, 0.04], 0.03)
    d = S.smin(d, S.capsule(p, (-0.74, 1.40, 0.02), (0.74, 1.40, 0.02), 0.035), 0.04)
    d = S.smin(d, S.capsule(p, (-0.72, 1.41, 1.0), (0.72, 1.41, 1.0), 0.03), 0.04)
    d = S.smin(d, S.capsule(p, (0, 1.42, 0.02), (0, 1.43, 1.0), 0.026), 0.04)
    return d


def floor_(p):
    d = S.round_box(p, (0, 0.335, 0.06), (0.925, 0.03, 1.18), 0.015)
    d = np.minimum(d, S.round_box(p, (0, 0.60, 1.225), (0.90, 0.26, 0.035), 0.03))      # low bulkhead
    rp = S.rot_x(p, (0, 0.90, 1.12), 0.35)                                          # rear deck, sloping into the fastback
    d = S.smin(d, S.box_local(rp, (0.88, 0.016, 0.14), 0.012), 0.03)
    d = np.minimum(d, S.capsule(p, (-0.37, 0.70, -0.52), (-0.37, 0.86, -0.20), 0.05, 0.04))  # column
    return d


def cabin_scene(p):
    d = np.minimum(dash(p), console(p))
    d = np.minimum(d, door(p))
    d = np.minimum(d, seats(p))
    d = np.minimum(d, frame(p))
    return np.minimum(d, floor_(p))


def cab_ao(v, n, scale=0.12):
    return S.bake_ao(cabin_scene, v, n, scale, 1.0)


def build_cabin(meshes, step):
    print(f"cabin @ {step * 100:.1f} cm")
    lo, hi = (-0.96, 0.28, -1.3), (0.96, 1.48, 1.3)

    def face_n(fn, v, f, st):
        return S.grad(fn, v[f].mean(1), st * 0.5)

    v, _, f = timed("dash", lambda: S.mesh_part(dash, lo, (0.96, 0.95, -0.38), step, raw=True))
    # straight material borders: cut the mesh exactly on every classification plane
    v, f = S.slice_planes(v, f, [(1, 0.835), (1, 0.80), (1, 0.792), (1, 0.752), (1, 0.736), (1, 0.69), (1, 0.62),
                                 (2, -0.50), (2, -0.53), (2, -0.55), (2, -0.56), (2, -0.66), (0, 0.10), (0, -0.68)])
    c = v[f].mean(1)
    nm = np.full(len(f), "soft", dtype=object)
    nm[(c[:, 1] > 0.835) | ((c[:, 2] < -0.56) & (c[:, 1] > 0.80))] = "suede"
    nm[(c[:, 1] > 0.752) & (c[:, 1] < 0.792) & (c[:, 2] > -0.53)] = "metal"
    vent = (c[:, 1] > 0.69) & (c[:, 1] < 0.736) & (c[:, 2] > -0.50) & ((c[:, 0] > 0.10) | (c[:, 0] < -0.68))
    nm[vent] = "grille"
    nm[(c[:, 1] < 0.62) & (c[:, 2] > -0.66)] = "leather"
    band = (c[:, 1] >= 0.62) & (c[:, 1] <= 0.752) & (c[:, 2] > -0.55) & (nm != "grille")
    nm[band] = "tan"
    tw = (np.hypot(np.abs(c[:, 0]) - 0.74, c[:, 2] + 0.93) < 0.056) & (c[:, 1] > 0.86)
    nm[tw] = "grille"

    def dflag(v):
        fl = np.zeros(len(v))
        fl[(v[:, 1] > 0.69) & (v[:, 1] < 0.736) & (v[:, 2] > -0.50)] = 3
        fl[(np.hypot(np.abs(v[:, 0]) - 0.74, v[:, 2] + 0.93) < 0.056) & (v[:, 1] > 0.86)] = 4
        return fl
    emit_groups(meshes, "cab_", dash, v, f, nm, 26000, step, cab_ao, dflag)

    st = step * 0.7
    v, _, f = timed("console", lambda: S.mesh_part(console, (-0.25, 0.30, -0.80), (0.25, 0.72, 0.75), st, raw=True))
    v, f = S.slice_planes(v, f, [(2, 0.16), (1, 0.58), (2, -0.52)])
    c = v[f].mean(1)
    fnn = face_n(console, v, f, st)
    nm = np.full(len(f), "black", dtype=object)
    nm[(fnn[:, 1] > 0.6) & (c[:, 2] < 0.16) & (c[:, 2] > -0.52)] = "carbon"
    nm[(c[:, 2] > 0.16) & (c[:, 1] > 0.58)] = "tan"
    nm[(np.abs(fnn[:, 0]) > 0.6)] = "leather"
    ring = np.abs(np.hypot(c[:, 0], c[:, 2] + 0.12) - 0.052) < 0.016
    nm[ring & (c[:, 1] > 0.58)] = "metal"
    tog = (np.abs(c[:, 2] + 0.30) < 0.03) & (c[:, 1] > 0.598) & (np.abs(c[:, 0]) < 0.085)
    nm[tog] = "metal"

    def cflag(v):
        fl = np.zeros(len(v))
        fl[(np.abs(np.hypot(v[:, 0], v[:, 2] + 0.12) - 0.052) < 0.012) & (v[:, 1] > 0.585)] = 5
        return fl
    emit_groups(meshes, "cab_", console, v, f, nm, 12000, st, cab_ao, cflag)

    for sx in (-1, 1):
        x0, x1 = (0.70, 0.96) if sx > 0 else (-0.96, -0.70)
        v, _, f = timed("door", lambda: S.mesh_part(door, (x0, 0.28, -1.05), (x1, 0.96, 1.1), step, raw=True))
        v, f = S.slice_planes(v, f, [(1, 0.87), (1, 0.70), (1, 0.60), (1, 0.56)])
        c = v[f].mean(1)
        ax = np.abs(c[:, 0])
        nm = np.full(len(f), "leather", dtype=object)
        nm[(c[:, 1] > 0.70) & (c[:, 1] < 0.87)] = "suede"
        nm[(c[:, 1] < 0.56)] = "soft"
        nm[(c[:, 1] > 0.60) & (c[:, 1] < 0.70) & (ax < 0.925)] = "tan"
        spk = np.hypot(c[:, 1] - 0.47, c[:, 2] + 0.55) < 0.10
        nm[spk & (ax < 0.93)] = "grille"
        hnd = (np.abs(c[:, 1] - 0.765) < 0.016) & (c[:, 2] > -0.345) & (c[:, 2] < -0.155) & (ax < 0.905)
        nm[hnd] = "metal"

        def gflag(v):
            fl = np.zeros(len(v))
            fl[np.hypot(v[:, 1] - 0.47, v[:, 2] + 0.55) < 0.10] = 4
            return fl
        emit_groups(meshes, "cab_", door, v, f, nm, 9000, step, cab_ao, gflag)

    for cx in (-0.37, 0.40):
        pre = "dseat_" if cx < 0 else "cab_"
        sfn = (lambda c0: (lambda p: seat(p, c0)))(cx)
        v, _, f = timed("seat", lambda: S.mesh_part(sfn, (cx - 0.33, 0.33, -0.18), (cx + 0.33, 1.48, 0.92), step, raw=True))
        c = v[f].mean(1)
        fnn = face_n(sfn, v, f, step)
        lx = np.abs(c[:, 0] - cx)
        nm = np.full(len(f), "leather", dtype=object)
        nm[(lx < 0.135) & ((fnn[:, 1] > 0.75) | (fnn[:, 2] < -0.7))] = "leather2"

        def sflag(v, cx=cx):
            fl = np.zeros(len(v))
            fl[np.abs(v[:, 0] - cx) < 0.135] = 1
            return fl
        emit_groups(meshes, pre, sfn, v, f, nm, 16000, step, cab_ao, sflag)

    st = step * 0.8
    v, _, f = timed("frame", lambda: S.mesh_part(frame, (-0.96, 0.84, -1.16), (0.96, 1.47, 1.30), st, raw=True))
    c = v[f].mean(1)
    nm = np.full(len(f), "suede", dtype=object)
    nm[(np.abs(c[:, 0]) < 0.05) | (np.abs(c[:, 2] - 1.0) < 0.05) | (np.abs(c[:, 2] - 0.02) < 0.045)] = "carbon"
    emit_groups(meshes, "cab_", frame, v, f, nm, 9000, st, cab_ao)

    v, _, f = timed("floor", lambda: S.mesh_part(floor_, (-0.96, 0.28, -0.70), (0.96, 1.22, 1.30), step, raw=True))
    c = v[f].mean(1)
    nm = np.full(len(f), "carpet", dtype=object)
    nm[c[:, 2] > 1.17] = "suede"
    nm[(c[:, 1] > 0.84) & (c[:, 2] > 0.95)] = "carbon"
    nm[(c[:, 2] < -0.15) & (c[:, 1] > 0.6)] = "soft"
    emit_groups(meshes, "cab_", floor_, v, f, nm, 12000, step, cab_ao)

    # ambient light strips (uv.x 0..1 along; the shader traces them on)
    xs = np.linspace(-0.90, 0.90, 48)
    strip = S.march(dash, [(x, 0.758 - 0.03 * (x / 0.93) ** 2, -0.30) for x in xs], np.array([0, 0, -1.0]), 1.0)
    tube(meshes, "cab_amb", strip + np.array([0, 0, 0.004]), 0.0045, 6)
    for sx in (-1, 1):
        zs = np.linspace(-0.93, 0.98, 40)
        line = S.march(door, [(sx * 0.6, 0.71, z) for z in zs], np.array([sx * 1.0, 0, 0]), 0.5)
        tube(meshes, "cab_amb", line + np.array([-sx * 0.004, 0, 0]), 0.004, 6)
        zs = np.linspace(-0.45, 0.62, 30)
        cl = S.march(console, [(sx * 0.4, 0.42, z) for z in zs], np.array([-sx * 1.0, 0, 0]), 0.5)
        tube(meshes, "cab_amb", cl + np.array([sx * 0.003, 0, 0]), 0.0035, 6)
    foot = S.march(dash, [(x, 0.42, -0.2) for x in np.linspace(-0.85, 0.85, 30)], np.array([0, 0, -1.0]), 1.0)
    tube(meshes, "cab_amb", foot + np.array([0, -0.01, 0.006]), 0.004, 6)
    disc(meshes, "cab_puck", (0, 0.596, -0.12), 0.043, n=(0, 1, 0))


# ================================================================ panel-local parts
def cl_body_fn(R, W, H):
    span = W / R

    def fn(p):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        rr = np.hypot(x, z + R)
        ang = np.arctan2(x, z + R)
        dr = np.abs(rr - (R - 0.016)) - 0.02
        dy = np.abs(y) - (H / 2 + 0.014)
        da = (np.abs(ang) - (span / 2 + 0.022)) * rr
        q = np.stack([dr, dy, da], -1)
        d = S.length(np.maximum(q + 0.008, 0)) + np.minimum(q.max(-1) + 0.008, 0) - 0.008
        # inset the glass face 3 mm
        qr = np.stack([rr - (R - 0.003) - 0.01, np.abs(y) - H / 2, (np.abs(ang) - span / 2) * rr], -1)
        cut = S.length(np.maximum(qr, 0)) + np.minimum(qr.max(-1), 0)
        d = S.smax(d, -cut, 0.002)
        d = S.smin(d, S.capsule(p, (0, -H / 2, -0.035), (0, -H / 2 - 0.07, -0.08), 0.032, 0.04), 0.02)
        return d
    return fn


def cs_body_fn(W, H):
    def fn(p):
        d = S.round_box(p, (0, 0, -0.011), (W / 2 + 0.012, H / 2 + 0.012, 0.012), 0.007)
        d = S.smax(d, -S.round_box(p, (0, 0, 0.004), (W / 2, H / 2, 0.006), 0.002), 0.0015)
        d = S.smin(d, S.round_box(p, (0, 0, -0.03), (W / 2 - 0.02, H / 2 - 0.03, 0.012), 0.01), 0.01)
        # neck: forward (car -z) from the housing back into the dash face
        nd = cs_local(np.array([[CS_POS[0], CS_POS[1], CS_POS[2] - 1.0]]))[0] - cs_local(CS_POS[None])[0]
        a = np.array([0.0, -0.02, -0.03])
        b = a + nd * 0.17
        d = S.smin(d, S.capsule(p, a, b, 0.026), 0.018)
        return d
    return fn


YOKE_PATH = []
for t in np.linspace(0, 1, 9):
    YOKE_PATH.append((-0.175 + 0.012 * t, 0.07 - 0.15 * t))
for t in np.linspace(0, 1, 8)[1:]:
    a = math.pi + t * math.pi / 2
    YOKE_PATH.append((-0.125 + 0.038 * math.cos(a), -0.08 + 0.038 * math.sin(a) * 0.6))
for t in np.linspace(0, 1, 6)[1:]:
    YOKE_PATH.append((-0.125 + 0.25 * t, -0.103))
for t in np.linspace(0, 1, 8)[1:]:
    a = 1.5 * math.pi + t * math.pi / 2
    YOKE_PATH.append((0.125 + 0.038 * math.cos(a), -0.08 + 0.038 * math.sin(a) * 0.6))
for t in np.linspace(0, 1, 9)[1:]:
    YOKE_PATH.append((0.163 + 0.012 * t, -0.08 + 0.15 * t))


def yoke_fn(R_H):
    pts = [(x, y, 0.0) for x, y in YOKE_PATH]
    rad = [0.026 if abs(x) > 0.15 else 0.018 for x, y in YOKE_PATH]

    def fn(p):
        q = p.copy()
        q[:, 2] *= 0.8                                  # oval grips
        d = S.chain(q, pts, rad, 0.01)
        for sx in (-1, 1):
            d = S.smin(d, S.capsule(p, (sx * 0.165, -0.01, -0.004), (sx * 0.06, -0.012, -0.008), 0.015), 0.02)
            d = np.minimum(d, S.sphere(p, (sx * 0.11, -0.005, 0.011), 0.011))     # thumb buttons
        d = S.smin(d, S.cyl(p, (0, 0, -0.008), 2, R_H, 0.024, 0.008), 0.015)
        d = S.smax(d, -S.cyl(p, (0, 0, 0.016), 2, R_H * 0.95, 0.004, 0.001), 0.002)
        return d
    return fn


def build_panels(meshes, CL_R, CL_W, CL_H, CS_W, CS_H, R_H, step):
    print(f"panels @ {step * 1000:.1f} mm")
    fn = cl_body_fn(CL_R, CL_W, CL_H)
    v, _, f = timed("cluster", lambda: S.mesh_part(fn, (-0.34, -0.22, -0.20), (0.34, 0.13, 0.06), step, raw=True))
    c = v[f].mean(1)
    rr = np.hypot(c[:, 0], c[:, 2] + CL_R)
    nm = np.full(len(f), "black", dtype=object)
    nm[(rr > CL_R - 0.004) & (np.abs(c[:, 1]) > CL_H / 2 + 0.002)] = "metal"
    emit_groups(meshes, "cl_", fn, v, f, nm, 8000, step, lambda v, n, fn=fn: S.bake_ao(fn, v, n, 0.03))

    fn2 = cs_body_fn(CS_W, CS_H)
    v, _, f = timed("centre", lambda: S.mesh_part(fn2, (-0.17, -0.30, -0.12), (0.17, 0.21, 0.03), step, raw=True))
    c = v[f].mean(1)
    nm = np.full(len(f), "black", dtype=object)
    edge = (np.abs(c[:, 0]) > CS_W / 2 + 0.004) | (np.abs(c[:, 1]) > CS_H / 2 + 0.004)
    nm[edge & (c[:, 2] > -0.02)] = "metal"
    nm[c[:, 1] < -CS_H / 2 - 0.02] = "metal"
    emit_groups(meshes, "cs_", fn2, v, f, nm, 7000, step, lambda v, n, fn=fn2: S.bake_ao(fn, v, n, 0.03))

    fn3 = yoke_fn(R_H)
    st = step * 0.8
    v, _, f = timed("yoke", lambda: S.mesh_part(fn3, (-0.22, -0.15, -0.06), (0.22, 0.11, 0.05), st, raw=True))
    v, f = S.slice_planes(v, f, [(0, 0.14), (0, -0.14), (1, -0.042), (1, -0.028), (1, 0.055)])
    c = v[f].mean(1)
    nm = np.full(len(f), "carbon", dtype=object)
    grip = np.abs(c[:, 0]) > 0.14
    nm[grip] = "leather"                                  # black perforated leather grips
    nm[grip & (np.abs(c[:, 1] + 0.035) < 0.007)] = "tan"   # cognac band
    nm[grip & (c[:, 1] > 0.055)] = "suede"
    nm[np.hypot(c[:, 0], c[:, 1]) < R_H + 0.004] = "black"
    for sx in (-1, 1):
        nm[np.hypot(c[:, 0] - sx * 0.11, c[:, 1] + 0.005) < 0.013] = "metal"

    def yflag(v):
        fl = np.zeros(len(v))
        fl[np.abs(v[:, 0]) > 0.14] = 2
        return fl
    emit_groups(meshes, "yk_", fn3, v, f, nm, 12000, st, lambda v, n, fn=fn3: S.bake_ao(fn, v, n, 0.03), yflag)
