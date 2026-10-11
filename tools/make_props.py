#!/usr/bin/env python3
"""Hovercar exterior + cockpit -> assets/props.bin + cabin.as

Car local space: metres, x = right, y = up, z = back (forward is -z). The car
origin sits on the hover plane; the body floats from y 0.30 to 1.42.

Exterior: lofted wedge pod (paint), panoramic canopy (glass), dark belly and
intakes, front light bar, rear bar, four thruster pads.

Cockpit (car space unless noted): dashboard loft, door panels, A-pillars and
roof rails around a panoramic glass roof, passenger seat, centre tunnel with a
gear puck, floor, ambient light strips (uv.x = 0..1 along the strip so the
shader can trace them on), steering column.
Panel-local meshes (placed by world.as): driver display arc face + shell,
centre screen face + shell, yoke + hub face. Windshield HUD patch: a cylinder
about the windshield's rake axis, in car space; its parameters go to
cabin.as so world.as can ray-cast eye->world points onto it (AR markers).
"""
import math, os
import numpy as np
from meshpack import Mesh, write

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
meshes = {}


def M(name):
    if name not in meshes:
        meshes[name] = Mesh(name)
    return meshes[name]


def quad(mesh, a, b, c, d, uv=None, ref=None, n=None):
    a, b, c, d = map(lambda p: np.asarray(p, float), (a, b, c, d))
    if n is None:
        n = np.cross(b - a, d - a) + np.cross(d - c, b - c)
        ln = np.linalg.norm(n)
        if ln < 1e-12:
            return
        n = n / ln
        if ref is not None and n @ ((a + b + c + d) / 4 - np.asarray(ref, float)) < 0:
            n = -n
    uv = uv or [(0, 0)] * 4
    mesh.add([(*p, *n, *t) for p, t in zip((a, b, c, d), uv)], [0, 1, 2, 0, 2, 3])


def tri(mesh, a, b, c, ref):
    a, b, c = map(lambda p: np.asarray(p, float), (a, b, c))
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n)
    if ln < 1e-12:
        return
    n /= ln
    if n @ ((a + b + c) / 3 - np.asarray(ref, float)) < 0:
        n = -n
    mesh.add([(*p, *n, 0, 0) for p in (a, b, c)], [0, 1, 2])


def ring_rrect(hw_bot, hw_top, yb, yt, rb, rt, k=4):
    pts = []
    rb = min(rb, (yt - yb) / 2 - 1e-3, hw_bot - 1e-3)
    rt = min(rt, (yt - yb) / 2 - 1e-3, hw_top - 1e-3)
    for (cx, cy), a0, r in (((hw_bot - rb, yb + rb), -math.pi / 2, rb), ((hw_top - rt, yt - rt), 0.0, rt),
                            ((-hw_top + rt, yt - rt), math.pi / 2, rt), ((-hw_bot + rb, yb + rb), math.pi, rb)):
        for j in range(k + 1):
            a = a0 + (math.pi / 2) * j / k
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def loft(stations, matfn, caps=(None, None)):
    """stations: [(z, [(x,y)])] all rings same count. matfn(seg, i, mid)->Mesh"""
    rings = [[(x, y, z) for x, y in r] for z, r in stations]
    n = len(rings[0])
    for s in range(len(rings) - 1):
        A, B = rings[s], rings[s + 1]
        cyA = np.mean([p[1] for p in A]); cyB = np.mean([p[1] for p in B])
        for i in range(n):
            j = (i + 1) % n
            mid = np.mean([A[i], A[j], B[i], B[j]], axis=0)
            m = matfn(s, i, mid)
            if m is not None:
                quad(m, A[i], B[i], B[j], A[j], ref=(0, (cyA + cyB) / 2, mid[2]))
    for cap, ring, sgn in ((caps[0], rings[0], -1), (caps[1], rings[-1], 1)):
        if cap is None:
            continue
        c = np.mean(ring, axis=0)
        for i in range(n):
            tri(cap, c, ring[i], ring[(i + 1) % n], ref=c - np.array([0, 0, sgn * 1.0]))


def boxm(mesh, x0, x1, y0, y1, z0, z1):
    c = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    P = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    for f in ((0, 1, 2, 3), (5, 4, 7, 6), (4, 0, 3, 7), (1, 5, 6, 2), (3, 2, 6, 7), (4, 5, 1, 0)):
        quad(mesh, *[P[i] for i in f], ref=c)


def beam(mesh, a, b, w, h, uvx=None):
    """Rectangular beam between points a,b (w across x-ish, h across up-ish)."""
    a, b = np.array(a, float), np.array(b, float)
    f = b - a
    L = np.linalg.norm(f)
    f /= L
    up = np.array([0, 1.0, 0]) if abs(f[1]) < 0.9 else np.array([0, 0, 1.0])
    r = np.cross(f, up); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    cs = [r * sx * w / 2 + u * sy * h / 2 for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for i in range(4):
        j = (i + 1) % 4
        nn = cs[i] + cs[j]; nn /= np.linalg.norm(nn)
        uv = [(0, 0), (0, 0), (1, 0), (1, 0)] if uvx else None
        quad(mesh, a + cs[i], a + cs[j], b + cs[j], b + cs[i], uv=uv, n=nn)


# ================================================================ sculpted car + cabin (tools/make_car.py)
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_car

EYE = (-0.37, 1.13, 0.22)
make_car.build_exterior(meshes, "car_", 0.015)
make_car.build_exterior(meshes, "npc_", 0.03, budget=0.12)
make_car.build_cabin(meshes, 0.0105)

# ================================================================ panels (panel-local, facing +z)
# driver display: cylinder arc around local y (centre at z = -R), uv left->right / top->bottom
CL_W, CL_H, CL_R = 0.52, 0.17, 0.85
span = CL_W / CL_R
segs = 24
for i in range(segs):
    a0 = -span / 2 + span * i / segs
    a1 = -span / 2 + span * (i + 1) / segs
    p = lambda a, y: (CL_R * math.sin(a), y, CL_R * math.cos(a) - CL_R)
    n0 = (math.sin(a0), 0, math.cos(a0)); n1 = (math.sin(a1), 0, math.cos(a1))
    u0, u1 = i / segs, (i + 1) / segs
    M("cl_face").add([(*p(a0, -CL_H / 2), *n0, u0, 1), (*p(a1, -CL_H / 2), *n1, u1, 1),
                      (*p(a1, CL_H / 2), *n1, u1, 0), (*p(a0, CL_H / 2), *n0, u0, 0)], [0, 1, 2, 0, 2, 3])
# centre screen: flat quad
CS_W, CS_H = make_car.CS_W, make_car.CS_H
quad(M("cs_face"), (-CS_W / 2, -CS_H / 2, 0), (CS_W / 2, -CS_H / 2, 0), (CS_W / 2, CS_H / 2, 0), (-CS_W / 2, CS_H / 2, 0),
     uv=[(0, 1), (1, 1), (1, 0), (0, 0)], n=(0, 0, 1))

# hub body + face
HF = M("hub_face")
k = 32
R_H = 0.068
for i in range(k):
    a0, a1 = 2 * math.pi * i / k, 2 * math.pi * (i + 1) / k
    p0 = (R_H * math.cos(a0), R_H * math.sin(a0)); p1 = (R_H * math.cos(a1), R_H * math.sin(a1))
    HF.add([(0, 0, 0.0125, 0, 0, 1, 0.5, 0.5),
            (p0[0] * 0.94, p0[1] * 0.94, 0.0125, 0, 0, 1, 0.5 + 0.5 * math.cos(a0), 0.5 - 0.5 * math.sin(a0)),
            (p1[0] * 0.94, p1[1] * 0.94, 0.0125, 0, 0, 1, 0.5 + 0.5 * math.cos(a1), 0.5 - 0.5 * math.sin(a1))], [0, 1, 2])

make_car.build_panels(meshes, CL_R, CL_W, CL_H, CS_W, CS_H, R_H, 0.0032)

# ================================================================ windshield HUD (car space)
Cw = np.array([0, 0.888, -1.12])
Hd = np.array([0, 1.40, -0.02])
A = (Hd - Cw); GL = float(np.linalg.norm(A)); A /= GL
X = np.array([1.0, 0, 0])
Fo = -np.cross(X, A)
Fo /= np.linalg.norm(Fo)
RG = 1.7
O = Cw - Fo * RG
TH0, TH1 = math.radians(-31), math.radians(31)
T0, T1 = 0.08 * GL, 0.98 * GL
INSET = 0.004


def glass_pt(th, t, r=RG):
    return O + A * t + r * (math.sin(th) * X + math.cos(th) * Fo)


nu, nv = 40, 20
for i in range(nu):
    for j in range(nv):
        th0 = TH0 + (TH1 - TH0) * i / nu; th1 = TH0 + (TH1 - TH0) * (i + 1) / nu
        t0 = T0 + (T1 - T0) * j / nv; t1 = T0 + (T1 - T0) * (j + 1) / nv
        r = RG - INSET
        pts = [glass_pt(th0, t0, r), glass_pt(th1, t0, r), glass_pt(th1, t1, r), glass_pt(th0, t1, r)]
        uvs = [(i / nu, 1 - j / nv), ((i + 1) / nu, 1 - j / nv), ((i + 1) / nu, 1 - (j + 1) / nv), (i / nu, 1 - (j + 1) / nv)]
        nn = [-(math.sin(th) * X + math.cos(th) * Fo) for th in (th0, th1, th1, th0)]
        M("hud").add([(*p, *n, *uv) for p, n, uv in zip(pts, nn, uvs)], [0, 1, 2, 0, 2, 3])
# full windshield tint patch (glass presence: reflections / streak)
TW0, TW1 = math.radians(-31.5), math.radians(31.5)
for i in range(nu):
    for j in range(nv):
        th0 = TW0 + (TW1 - TW0) * i / nu; th1 = TW0 + (TW1 - TW0) * (i + 1) / nu
        t0 = 0.02 * GL + 0.96 * GL * j / nv; t1 = 0.02 * GL + 0.96 * GL * (j + 1) / nv
        r = RG - INSET * 2
        pts = [glass_pt(th0, t0, r), glass_pt(th1, t0, r), glass_pt(th1, t1, r), glass_pt(th0, t1, r)]
        uvs = [(i / nu, 1 - j / nv), ((i + 1) / nu, 1 - j / nv), ((i + 1) / nu, 1 - (j + 1) / nv), (i / nu, 1 - (j + 1) / nv)]
        nn = [-(math.sin(th) * X + math.cos(th) * Fo) for th in (th0, th1, th1, th0)]
        M("wglass").add([(*p, *n, *uv) for p, n, uv in zip(pts, nn, uvs)], [0, 1, 2, 0, 2, 3])

write(os.path.join(ROOT, "assets", "props.bin"), list(meshes.values()))


def v3(v):
    return f"Vector.xyz({v[0]:.5f}, {v[1]:.5f}, {v[2]:.5f})"


def vx(v):
    return f"Vector.xyz({v[0]:.5f}, {v[1]:.5f}, {v[2]:.5f})"


AS = f"""// GENERATED by tools/make_props.py - do not edit
import {{ Vector }} from "rive/vector";
export const eye: Vector = {vx(EYE)};
// windshield HUD cylinder: P(th, t) = O + A*t + R*(sin th * X + cos th * F)
export const glassO: Vector = {vx(O)};
export const glassA: Vector = {vx(A)};
export const glassX: Vector = {vx(X)};
export const glassF: Vector = {vx(Fo)};
export const glassR: f64 = {RG - INSET:.5f};
export const th0: f64 = {TH0:.5f};
export const th1: f64 = {TH1:.5f};
export const t0: f64 = {T0:.5f};
export const t1: f64 = {T1:.5f};
// driver display (arc, panel-local: centre of the cylinder at z = -R)
export const clW: f64 = {CL_W};
export const clH: f64 = {CL_H};
export const clR: f64 = {CL_R};
export const clPos: Vector = Vector.xyz(-0.37, 0.965, -0.64);
export const clPitch: f64 = -0.16;
// centre screen (flat)
export const csW: f64 = {CS_W};
export const csH: f64 = {CS_H};
export const csPos: Vector = Vector.xyz({make_car.CS_POS[0]}, {make_car.CS_POS[1]}, {make_car.CS_POS[2]});
export const csYaw: f64 = {make_car.CS_YAW};
export const csPitch: f64 = {make_car.CS_PITCH};
// yoke
export const ykPos: Vector = Vector.xyz(-0.37, 0.92, -0.13);
export const ykTilt: f64 = -0.42;
export const hubR: f64 = {R_H * 0.94:.5f};
"""
open(os.path.join(ROOT, "cabin.as"), "w").write(AS)

print({m.name: sum(len(i) for i in m.i) // 3 for m in meshes.values()})
