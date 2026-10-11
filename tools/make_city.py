#!/usr/bin/env python3
"""Procedural city -> assets/city.bin + cityinfo.as

World: metres, x = east, y = up, z = south. A street grid (pitch P) with
canyon streets, stepped towers (rect / chamfered / round shafts, podiums,
setback tiers, crowns, spires), skybridges, neon edge strips, street lamps,
floating sky-lane gates, street-spanning billboard gantries, wall and
rooftop billboards, and a ring of far silhouette towers.

Materials (toon.wgsl modes):
  2 buildings (uv.x = per-building hash, uv.y = tier top height)
  3 roads (uv.x = along, uv.y = across)   4 ground / pavement
  8 neon (uv.x = palette index, uv.y = flicker phase)   0 plain toon
Billboard faces are grouped per design (bb0..bb5) with 0..1 uvs.
"""
import math, os, random
import numpy as np
from meshpack import Mesh, write

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
rng = random.Random(7)

P = 100.0          # block pitch
RW = 9.0           # road half width (2 lanes of 4.5 m each way)
WALK = 5.0         # sidewalk
N = 7              # drivable blocks per axis (streets 0..7)
LO, HI = -6, N + 6 # visual block range
LANE = 2.25        # player lane offset from the centre line
CX = CZ = N * P / 2

meshes = {}


def M(name):
    if name not in meshes:
        meshes[name] = Mesh(name)
    return meshes[name]


def quad(mesh, a, b, c, d, n, uv=((0, 0), (1, 0), (1, 1), (0, 1))):
    mesh.add([(*p, *n, *t) for p, t in zip((a, b, c, d), uv)], [0, 1, 2, 0, 2, 3])


def boxm(mesh, x0, x1, y0, y1, z0, z1, uv=(0, 0), top=True, bottom=False):
    u, v = uv
    t = [(u, v)] * 4
    quad(mesh, (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1), t)
    quad(mesh, (x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (0, 0, -1), t)
    quad(mesh, (x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (1, 0, 0), t)
    quad(mesh, (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (-1, 0, 0), t)
    if top:
        quad(mesh, (x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0), (0, 1, 0), t)
    if bottom:
        quad(mesh, (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0), t)


def prism(mesh, poly, y0, y1, uv, top=True):
    """Convex polygon footprint [(x,z)] (any winding) extruded y0..y1."""
    cx = sum(p[0] for p in poly) / len(poly)
    cz = sum(p[1] for p in poly) / len(poly)
    n = len(poly)
    for i in range(n):
        ax, az = poly[i]
        bx, bz = poly[(i + 1) % n]
        nx, nz = bz - az, -(bx - ax)
        ln = math.hypot(nx, nz) or 1
        nx, nz = nx / ln, nz / ln
        mx, mz = (ax + bx) / 2 - cx, (az + bz) / 2 - cz
        if mx * nx + mz * nz < 0:
            nx, nz = -nx, -nz
        quad(mesh, (ax, y0, az), (bx, y0, bz), (bx, y1, bz), (ax, y1, az), (nx, 0, nz), [uv] * 4)
    if top:
        verts = [(cx, y1, cz, 0, 1, 0, *uv)] + [(x, y1, z, 0, 1, 0, *uv) for x, z in poly]
        idx = []
        for i in range(n):
            idx += [0, 1 + i, 1 + (i + 1) % n]
        mesh.add(verts, idx)


def rect_poly(x0, z0, x1, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def chamfer_poly(x0, z0, x1, z1, c):
    c = min(c, (x1 - x0) * 0.3, (z1 - z0) * 0.3)
    return [(x0 + c, z0), (x1 - c, z0), (x1, z0 + c), (x1, z1 - c), (x1 - c, z1), (x0 + c, z1), (x0, z1 - c), (x0, z0 + c)]


def round_poly(x0, z0, x1, z1, k=16):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    rx, rz = (x1 - x0) / 2, (z1 - z0) / 2
    return [(cx + rx * math.cos(2 * math.pi * i / k), cz + rz * math.sin(2 * math.pi * i / k)) for i in range(k)]


def inset(poly, d):
    cx = sum(p[0] for p in poly) / len(poly)
    cz = sum(p[1] for p in poly) / len(poly)
    out = []
    for x, z in poly:
        dx, dz = x - cx, z - cz
        l = math.hypot(dx, dz) or 1
        out.append((x - dx / l * d * 1.0, z - dz / l * d * 1.0))
    return out


# neon palette indices (toon.wgsl): 0 amber 1 cyan 2 magenta 3 blue 4 green 5 red 6 warm white 7 cool white
NEON_W = [(0, 5), (6, 3), (1, 3), (7, 2), (2, 1.5), (3, 1.2), (5, 0.6), (4, 0.4)]


def neon_pick():
    tot = sum(w for _, w in NEON_W)
    r = rng.random() * tot
    for i, w in NEON_W:
        r -= w
        if r <= 0:
            return i
    return 0


def neon_bar(a, b, th, col, phase=None, mesh="neon"):
    """Thin box between two points (axis aligned or not)."""
    ph = rng.random() if phase is None else phase
    a, b = np.array(a, float), np.array(b, float)
    d = b - a
    L = np.linalg.norm(d)
    if L < 1e-6:
        return
    f = d / L
    up = np.array([0, 1.0, 0]) if abs(f[1]) < 0.9 else np.array([1.0, 0, 0])
    r = np.cross(f, up); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    h = th / 2
    corners = [a + (r * sx + u * sy) * h for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    corners2 = [c + d for c in corners]
    m = M(mesh)
    uv = [(col, ph)] * 4
    for i in range(4):
        j = (i + 1) % 4
        nn = (corners[i] + corners[j]) / 2 - a
        nn /= (np.linalg.norm(nn) or 1)
        quad(m, corners[i], corners[j], corners2[j], corners2[i], tuple(nn), uv)


billboards = []   # dicts: c, n, w, h, design
PORTRAIT_DES = (5, 7, 8)
SILLY_DES = 9            # the playable SillyScroll board (1491x1500 artboard, ~square)
SILLY_A = 1491 / 1500
LAND_DES = [0, 1, 2, 3, 4, 6]
# landscape / portrait screen sizes (m) with weights: mostly mid, some tiny, rare megas
LAND_SIZES = [((12.0, 6.0), 3), ((18.0, 9.0), 4), ((24.0, 12.0), 3), ((22.0, 7.0), 1.5), ((32.0, 16.0), 1.2), ((40.0, 20.0), 0.6)]
PORT_SIZES = [((6.0, 12.0), 3), ((7.0, 14.0), 3), ((8.0, 20.0), 2), ((10.0, 20.0), 1.2), ((12.0, 30.0), 0.7)]


def pick_size(sizes, maxw, maxh):
    ok = [(s, wt) for s, wt in sizes if s[0] <= maxw and s[1] <= maxh]
    if not ok:
        return None
    tot = sum(wt for _, wt in ok)
    r = rng.random() * tot
    for s, wt in ok:
        r -= wt
        if r <= 0:
            return s
    return ok[-1][0]


BB_REJECT = [0]
BB_WHY = []


def bb_volume(c, n, w, h, back=1.0, front=0.5):
    """world AABB of a screen + frame + top light bar (normals are axis aligned)"""
    nx, nz = n
    lat, vy = w / 2 + 0.7, h / 2 + 0.9
    if nx != 0:
        xs = sorted((c[0] - nx * back, c[0] + nx * front))
        return (xs[0], c[1] - vy, c[2] - lat, xs[1], c[1] + vy, c[2] + lat)
    zs = sorted((c[2] - nz * back, c[2] + nz * front))
    return (c[0] - lat, c[1] - vy, zs[0], c[0] + lat, c[1] + vy, zs[1])


def _hits(v, boxes, pad=0.0):
    x0, y0, z0, x1, y1, z1 = v
    out = []
    for bx in boxes:
        a0, b0, c0, a1, b1, c1 = bx
        if a0 < x1 + pad and x0 - pad < a1 and b0 < y1 + pad and y0 - pad < b1 and c0 < z1 + pad and z0 - pad < c1:
            out.append(bx)
    return out


def bb_fit(c, n, w, h, back=0.95, max_shift=3.4):
    """Find how far a screen must stand off its wall to clear facade relief (ledges, fins,
    pilasters), then check nothing else (other buildings, skybridges, blade signs, other
    screens) touches it. Returns the outward shift in metres, or None if it can't fit."""
    nx, nz = n
    N = np.array([nx, 0, nz], float)
    shift = 0.0
    for _ in range(4):
        cc = c + N * shift
        hits = _hits(bb_volume(cc, n, w, h, back), COLL)
        if not hits:
            break
        need = 0.0
        for (a0, b0, c0, a1, b1, c1) in hits:
            bp = cc - N * back       # back plane of the frame
            reach = ((a1 - bp[0]) if nx > 0 else (bp[0] - a0)) if nx != 0 else ((c1 - bp[2]) if nz > 0 else (bp[2] - c0))
            need = max(need, reach)
        if shift + need + 0.15 > max_shift:
            BB_WHY.append(("coll",))
            return None
        shift += need + 0.15
    else:
        BB_WHY.append(("coll",))
        return None
    v = bb_volume(c + N * shift, n, w, h, back)
    if _CAB_NP[0] is None or len(_CAB_NP[0]) != len(CABSEG):
        _CAB_NP[0] = np.asarray(CABSEG, float).reshape(-1, 6)
    C = _CAB_NP[0]
    if len(C) and np.any((C[:, 0] < v[3] + 0.3) & (v[0] - 0.3 < C[:, 3]) & (C[:, 1] < v[4] + 0.3) & (v[1] - 0.3 < C[:, 4])
                         & (C[:, 2] < v[5] + 0.3) & (v[2] - 0.3 < C[:, 5])):
        BB_WHY.append(("cable",))
        return None
    if _hits(v, BLADES, 0.5):
        BB_WHY.append(("blade",))
        return None
    for b in billboards:
        if _hits(v, [bb_volume(b["c"], b["n"], b["w"], b["h"])], 1.0):
            BB_WHY.append(("screen",))
            return None
    return shift


def billboard(c, n, w, h, design, frame=True, back=False, check=True):
    """Face quad centred at c facing n=(nx,nz). Frame behind it. Skipped (False) if it would
    intersect a building, skybridge or another screen."""
    c = np.array(c, float)
    shift = 0.0
    if check:
        shift = bb_fit(c, n, w, h)
        if shift is None:
            BB_REJECT[0] += 1
            return None
        c = c + np.array([n[0], 0, n[1]], float) * shift
    nx, nz = n
    rx, rz = -nz, nx          # right as seen from the front... (viewer looks along -n)
    # viewer faces -n; their right = (nz*-1?) compute: forward f=-n, right = (-f.z, f.x)
    fx, fz = -nx, -nz
    rx, rz = -fz, fx
    R = np.array([rx, 0, rz])
    U = np.array([0, 1.0, 0])
    Nn = np.array([nx, 0, nz])
    hw, hh = w / 2, h / 2
    p = c + Nn * 0.05
    a, b, cc, d = p - R * hw - U * hh, p + R * hw - U * hh, p + R * hw + U * hh, p - R * hw + U * hh
    # cover-crop the artboard (2:1 landscape, 1:2 portrait) to this screen's aspect
    A = SILLY_A if design == SILLY_DES else (0.5 if design in PORTRAIT_DES else 2.0)
    asp = w / h
    u0, u1, v0, v1 = 0.0, 1.0, 0.0, 1.0
    if asp < A:
        uw = asp / A
        u0, u1 = 0.5 - uw / 2, 0.5 + uw / 2
    else:
        vh = A / asp
        v0, v1 = 0.5 - vh / 2, 0.5 + vh / 2
    quad(M(f"bb{design}"), a, b, cc, d, (nx, 0, nz), ((u0, v1), (u1, v1), (u1, v0), (u0, v0)))
    billboards.append(dict(c=c + Nn * 0.05, n=(nx, nz), w=w, h=h, design=design))
    if frame:
        fm = M("bbframe")
        t = 0.55
        dep = 0.9
        back_c = c - Nn * dep
        # border bars
        for (p0, p1) in ((a, b), (b, cc), (cc, d), (d, a)):
            mid0 = p0 - Nn * dep / 2
            seg = p1 - p0
            L = np.linalg.norm(seg)
            f = seg / L
            side = np.cross(f, Nn)
            pts = []
            for s1, s2 in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                pts.append(side * s1 * t + Nn * s2 * dep / 2)
            for i in range(4):
                j = (i + 1) % 4
                q0, q1 = p0 + pts[i] - Nn * 0.0, p0 + pts[j]
                nn = (pts[i] + pts[j]) / 2
                nn = nn / (np.linalg.norm(nn) or 1)
                quad(fm, q0, q1, q1 + seg, q0 + seg, tuple(nn))
        # back panel
        bp = c - Nn * dep
        quad(fm, bp + R * hw - U * hh, bp - R * hw - U * hh, bp - R * hw + U * hh, bp + R * hw + U * hh, (-nx, 0, -nz))
        # light bar on top
        neon_bar(d + U * (t + 0.15) + Nn * 0.3, cc + U * (t + 0.15) + Nn * 0.3, 0.22, 6, 0.0)
        # stood off the wall to clear facade relief: steel arms back to the wall
        if shift > 0.3:
            for s_ in (-1, 1):
                for v_ in (-0.3, 0.3):
                    p0 = bp + R * s_ * (hw - 1.2) + U * v_ * h
                    p1 = p0 - Nn * (shift + 0.2)
                    lo, hi = np.minimum(p0, p1) - 0.18, np.maximum(p0, p1) + 0.18
                    boxm(M("gantry"), lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
    if back:
        billboard(c - np.array([nx, 0, nz]) * 1.0, (-nx, -nz), w, h, LAND_DES[(LAND_DES.index(design) + 3) % 6] if design in LAND_DES else design,
                  frame=False, check=False)
    return shift


# ---------------------------------------------------------------- route
def S(i):
    return i * P


ROUTE_IJ = [(1, 6), (1, 1), (5, 1), (5, 3), (6, 3), (6, 6)]
AVES = ["KESTREL AVE", "ORBIT AVE", "HALCYON AVE", "VECTOR AVE", "MERIDIAN AVE", "LUMEN AVE", "SPECTRA AVE", "NOVA AVE"]
STS = ["CIPHER ST", "AURORA ST", "NEON ST", "QUANTA ST", "PULSE ST", "ZENITH ST", "PRISM ST", "ECHO ST"]


def build_route():
    pts = [(S(i), S(j)) for i, j in ROUTE_IJ]
    n = len(pts)
    corners = []
    for k in range(n):
        p0, p1, p2 = np.array(pts[k - 1]), np.array(pts[k]), np.array(pts[(k + 1) % n])
        din = (p1 - p0) / np.linalg.norm(p1 - p0)
        dout = (p2 - p1) / np.linalg.norm(p2 - p1)
        rin = np.array([-din[1], din[0]])
        rout = np.array([-dout[1], dout[0]])
        corners.append((p1 + rin * LANE + rout * LANE, din, dout))
    out = []
    R = 11.0
    for k in range(n):
        c, din, dout = corners[k]
        cn, din2, dout2 = corners[(k + 1) % n]
        # arc at corner k from c - din*R to c + dout*R, then straight to next corner start
        a0 = c - din * R
        a1 = c + dout * R
        # quadratic bezier through corner (smooth enough at 1 m sampling)
        steps = 24
        for s in range(steps):
            t = s / steps
            q = (1 - t) ** 2 * a0 + 2 * (1 - t) * t * c + t * t * a1
            out.append(q)
        b0 = a1
        b1 = cn - din2 * R
        L = np.linalg.norm(b1 - b0)
        m = max(1, int(L / 2))
        for s in range(m):
            out.append(b0 + (b1 - b0) * s / m)
    # resample to 1 m
    out = np.array(out + [out[0]])
    seg = np.linalg.norm(np.diff(out, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = cum[-1]
    nn = int(total)
    xs = np.interp(np.arange(nn) * total / nn, cum, out[:, 0])
    zs = np.interp(np.arange(nn) * total / nn, cum, out[:, 1])
    res = list(zip(xs, zs))
    # street names per straight
    streets = []
    for k in range(n):
        i0, j0 = ROUTE_IJ[k]
        i1, j1 = ROUTE_IJ[(k + 1) % n]
        name = AVES[i0] if i0 == i1 else STS[j0]
        streets.append(name)
    # s ranges: find nearest resampled index to each corner
    marks = []
    for k in range(n):
        c = corners[k][0]
        d = [(x - c[0]) ** 2 + (z - c[1]) ** 2 for x, z in res]
        marks.append(int(np.argmin(d)))
    segs = []
    for k in range(n):
        s0 = marks[k]
        s1 = marks[(k + 1) % n]
        if s1 <= s0:
            s1 += nn
        segs.append(dict(s0=s0, s1=s1, name=streets[k], next=streets[(k + 1) % n],
                         turn=turn_dir(k)))
    return res, segs, corners


def turn_dir(k):
    n = len(ROUTE_IJ)
    p0, p1, p2 = [np.array(ROUTE_IJ[(k + o) % n], float) for o in (0, 1, 2)]
    a, b = p1 - p0, p2 - p1
    cr = a[0] * b[1] - a[1] * b[0]
    return 1 if cr > 0 else -1   # +1 right turn (x east, z south)


route, route_segs, route_corners = build_route()


def street_steam():
    """manhole vents along the route, either side of the lane line: you drive through the plumes"""
    acc = 0.0
    nxt = srng.uniform(40, 90)
    for k in range(1, len(route)):
        (x0, z0), (x1, z1) = route[k - 1], route[k]
        dl = math.hypot(x1 - x0, z1 - z0)
        acc += dl
        if acc < nxt or dl < 1e-6:
            continue
        acc = 0.0
        nxt = srng.uniform(70, 150)
        nx, nz = -(z1 - z0) / dl, (x1 - x0) / dl
        off = srng.choice((-1, 1)) * srng.uniform(1.5, 7.0)
        STEAM.append((x1 + nx * off, 0.15, z1 + nz * off, srng.uniform(1.4, 2.4), srng.random(), 1.0,
                      0.07 + srng.random() * 0.04, 0.0))

# ---------------------------------------------------------------- ground + roads
G = M("ground")
E0, E1 = S(LO) - 2600, S(HI) + 2600
quad(G, (E0, -0.02, E1), (E1, -0.02, E1), (E1, -0.02, E0), (E0, -0.02, E0), (0, 1, 0))

R_ = M("roads")
XS = [S(i) for i in range(LO, HI + 1)]
for zi in XS:
    for k in range(len(XS) - 1):
        x0, x1 = XS[k] + RW, XS[k + 1] - RW
        # along x at z = zi ; uv = (along, across)
        quad(R_, (x0, 0, zi + RW), (x1, 0, zi + RW), (x1, 0, zi - RW), (x0, 0, zi - RW), (0, 1, 0),
             ((x0, RW), (x1, RW), (x1, -RW), (x0, -RW)))
for xi in XS:
    for k in range(len(XS) - 1):
        z0, z1 = XS[k] + RW, XS[k + 1] - RW
        quad(R_, (xi - RW, 0, z1), (xi + RW, 0, z1), (xi + RW, 0, z0), (xi - RW, 0, z0), (0, 1, 0),
             ((z1, -RW), (z1, RW), (z0, RW), (z0, -RW)))
for xi in XS:
    for zi in XS:
        quad(R_, (xi - RW, 0, zi + RW), (xi + RW, 0, zi + RW), (xi + RW, 0, zi - RW), (xi - RW, 0, zi - RW), (0, 1, 0),
             [(0, 99)] * 4)

# zebra crossings (drivable area + 1)
ZB = M("marks")
for xi in [S(i) for i in range(-1, N + 2)]:
    for zi in [S(j) for j in range(-1, N + 2)]:
        for sgn in (-1, 1):
            # crossing the x-street just east/west of the intersection
            x0 = xi + sgn * (RW + 1.0)
            x1 = xi + sgn * (RW + 4.0)
            for k in range(8):
                z = zi - RW + 0.8 + k * 2.2
                quad(ZB, (min(x0, x1), 0.012, z + 1.1), (max(x0, x1), 0.012, z + 1.1), (max(x0, x1), 0.012, z), (min(x0, x1), 0.012, z), (0, 1, 0))
            z0 = zi + sgn * (RW + 1.0)
            z1 = zi + sgn * (RW + 4.0)
            for k in range(8):
                x = xi - RW + 0.8 + k * 2.2
                quad(ZB, (x, 0.012, max(z0, z1)), (x + 1.1, 0.012, max(z0, z1)), (x + 1.1, 0.012, min(z0, z1)), (x, 0.012, min(z0, z1)), (0, 1, 0))

# block slabs (sidewalk level)
W_ = M("walks")
for bi in range(LO, HI):
    for bj in range(LO, HI):
        x0, x1 = S(bi) + RW, S(bi + 1) - RW
        z0, z1 = S(bj) + RW, S(bj + 1) - RW
        boxm(W_, x0, x1, 0, 0.22, z0, z1)

# ---------------------------------------------------------------- towers
B = M("buildings")
tower_tops = []   # (x, z, h, poly) for the dive / crowns
skybridge_count = 0


def tier_uv(h_top, hsh):
    return (hsh, h_top)


def add_neon_ring(poly, y, col, th=0.35):
    n = len(poly)
    cx = sum(p[0] for p in poly) / n
    cz = sum(p[1] for p in poly) / n
    ph = rng.random()
    for i in range(n):
        ax, az = poly[i]
        bx, bz = poly[(i + 1) % n]
        # push out a hair so it sits proud of the wall
        def out(x, z):
            dx, dz = x - cx, z - cz
            l = math.hypot(dx, dz) or 1
            return x + dx / l * 0.25, z + dz / l * 0.25
        ax, az = out(ax, az)
        bx, bz = out(bx, bz)
        neon_bar((ax, y, az), (bx, y, bz), th, col, ph)


def add_corner_strips(poly, y0, y1, col):
    n = len(poly)
    cx = sum(p[0] for p in poly) / n
    cz = sum(p[1] for p in poly) / n
    ph = rng.random()
    step = 1 if n <= 8 else n // 4
    for i in range(0, n, step):
        x, z = poly[i]
        dx, dz = x - cx, z - cz
        l = math.hypot(dx, dz) or 1
        x, z = x + dx / l * 0.3, z + dz / l * 0.3
        neon_bar((x, y0, z), (x, y1, z), 0.4, col, ph)


def drivable(bi, bj):
    return 0 <= bi < N and 0 <= bj < N


# facade texture layers (tools/make_tex.py): 0 res 1 office 2 industrial 3 hk 4 lux 5 roof
L_RES, L_OFFICE, L_IND, L_HK, L_LUX, L_ROOF = 0, 1, 2, 3, 4, 5


COLL = []   # collision boxes for the drivable car: x0, y0, z0, x1, y1, z1


def tbox(m, x0, x1, y0, y1, z0, z1, L, off, top=True, bottom=False):
    """Box whose side uvs are (layer*10000 + offset + along-metres, height-metres)."""
    if x1 - x0 < 0.05 or z1 - z0 < 0.05 or y1 - y0 < 0.05:
        return
    if m is meshes.get("buildings"):
        COLL.append((x0, y0, z0, x1, y1, z1))
    U = L * 10000 + off
    quad(m, (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1), ((U + x0, y0), (U + x1, y0), (U + x1, y1), (U + x0, y1)))
    quad(m, (x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (0, 0, -1), ((U - x1, y0), (U - x0, y0), (U - x0, y1), (U - x1, y1)))
    quad(m, (x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (1, 0, 0), ((U - z1, y0), (U - z0, y0), (U - z0, y1), (U - z1, y1)))
    quad(m, (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (-1, 0, 0), ((U + z0, y0), (U + z1, y0), (U + z1, y1), (U + z0, y1)))
    if top:
        R = L_ROOF * 10000 + 5000
        quad(m, (x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0), (0, 1, 0), ((R + x0, z1), (R + x1, z1), (R + x1, z0), (R + x0, z0)))
    if bottom:
        quad(m, (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0), [(-5, 0)] * 4)


def tcyl(m, cx, cz, r, y0, y1, L, off, k=10, top=True):
    U = L * 10000 + off
    if m is meshes.get("buildings"):
        COLL.append((cx - r, y0, cz - r, cx + r, y1, cz + r))
    for i in range(k):
        a0, a1 = 2 * math.pi * i / k, 2 * math.pi * (i + 1) / k
        p0 = (cx + r * math.cos(a0), cz + r * math.sin(a0))
        p1 = (cx + r * math.cos(a1), cz + r * math.sin(a1))
        am = (a0 + a1) / 2
        n = (math.cos(am), 0, math.sin(am))
        u0, u1 = U + r * a0, U + r * a1
        quad(m, (p1[0], y0, p1[1]), (p0[0], y0, p0[1]), (p0[0], y1, p0[1]), (p1[0], y1, p1[1]), n, ((u1, y0), (u0, y0), (u0, y1), (u1, y1)))
    if top:
        R = L_ROOF * 10000 + 5000
        verts = [(cx, y1, cz, 0, 1, 0, R + cx, cz)]
        for i in range(k):
            a0 = 2 * math.pi * i / k
            x, z = cx + r * math.cos(a0), cz + r * math.sin(a0)
            verts.append((x, y1, z, 0, 1, 0, R + x, z))
        idx = []
        for i in range(k):
            idx += [0, 1 + (i + 1) % k, 1 + i]
        m.add(verts, idx)


def pick_layer(h):
    if h > 230:
        return rng.choices([L_OFFICE, L_LUX, L_RES], [4, 2, 3])[0]
    if h > 120:
        return rng.choices([L_RES, L_HK, L_OFFICE, L_LUX], [4, 3, 2, 1])[0]
    return rng.choices([L_HK, L_RES, L_IND], [4, 3, 2])[0]


grng = random.Random(4242)          # greebles: own stream, the city layout stays put
srng = random.Random(9090)          # steam vents: own stream too
STEAM = []   # (x, y, z, radius, seed, kind 0 stack / 1 street, rate, 0)
GSTAT = {"ac": 0, "balc": 0, "cones": 0, "rooms": 0, "deep": 0, "pipes": 0}


GINST = []   # instanced greebles: centre xyz, size xyz, type, tint


def face_box(m, side, fx, a0, a1, y0, y1, d0, d1, uv):
    """axis-aligned box on tower face `side` (0 -x, 1 +x, 2 -z, 3 +z) at plane
    coord fx, spanning a0..a1 along the face, d0..d1 outward -> instance"""
    if side == 0:
        bx = (fx - d1, fx - d0, a0, a1)
    elif side == 1:
        bx = (fx + d0, fx + d1, a0, a1)
    elif side == 2:
        bx = (a0, a1, fx - d1, fx - d0)
    else:
        bx = (a0, a1, fx + d0, fx + d1)
    x0, x1, z0, z1 = bx
    GINST.append(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2, x1 - x0, y1 - y0, z1 - z0, uv[0], uv[1]))


def greebles(x0, x1, y0, y1, z0, z1):
    """Dense-city clutter on one tower section: balcony runs with rails, AC units."""
    G = M("greeble")
    FL = 3.4
    for side in range(4):
        fx = (x0, x1, z0, z1)[side]
        s0, s1 = ((z0, z1), (z0, z1), (x0, x1), (x0, x1))[side]
        span = s1 - s0
        if span < 6:
            continue
        nfl = int((y1 - y0 - 1.0) / FL)
        # balcony runs
        if grng.random() < 0.5 and nfl >= 2:
            w = span * grng.uniform(0.3, 0.85)
            a0 = s0 + grng.uniform(0.5, span - w - 0.5) if span - w > 1 else s0 + 0.5
            a1 = min(s1 - 0.5, a0 + w)
            dep = grng.uniform(0.8, 1.5)
            tint = grng.random()
            for k in range(1, nfl):
                fy = y0 + k * FL
                face_box(G, side, fx, a0, a1, fy - 0.2, fy, 0.0, dep, (1, tint))
                face_box(G, side, fx, a0, a1, fy, fy + 1.0, dep - 0.06, dep, (2, tint))
                GSTAT["balc"] += 1
        # how far this face may project: street faces keep clear of the traffic
        # (swarm lanes reach ~13 m from a street's centre); alley faces stay shallow
        if side in (0, 1):
            dist = (fx - math.floor(fx / P) * P) if side == 0 else (math.ceil(fx / P) * P - fx)
        else:
            dist = (fx - math.floor(fx / P) * P) if side == 2 else (math.ceil(fx / P) * P - fx)
        maxd = 2.5 if dist > 40 else min(7.0, dist - (RW + 4.5))
        # dense-city look: whole rooms cantilevered off the face, stacked irregularly
        if maxd >= 2.5 and nfl >= 4 and y0 < 170 and grng.random() < 0.24:
            for _col in range(grng.randint(1, 3)):
                rw = grng.uniform(3.0, 6.0)
                if span < rw + 2:
                    break
                ac = grng.uniform(s0 + rw / 2 + 0.5, s1 - rw / 2 - 0.5)
                k0 = grng.randint(0, max(0, nfl - 4))
                k1 = min(nfl - 1, k0 + grng.randint(3, 14))
                lit = grng.random()
                for k in range(k0, k1):
                    if grng.random() < 0.12:
                        continue
                    fy = y0 + k * FL
                    dep = grng.uniform(2.5, maxd)
                    a = ac + grng.uniform(-0.8, 0.8)
                    w = rw * grng.uniform(0.85, 1.15)
                    t = grng.random()
                    face_box(G, side, fx, a - w / 2, a + w / 2, fy + 0.15, fy + 3.2, 0.0, dep, (1, t))
                    # window panel on the outward face (type 3: lit by its tint)
                    face_box(G, side, fx, a - w * 0.36, a + w * 0.36, fy + 1.05, fy + 2.45, dep, dep + 0.08,
                             (3, (lit + k * 0.37) % 1.0))
                    # steel brace under the pod
                    face_box(G, side, fx, a - 0.15, a + 0.15, fy - 0.6, fy + 0.15, 0.0, dep * 0.8, (2, 0.5))
                    GSTAT["rooms"] += 1
        # deep caged balcony stacks with posts and side rails
        elif maxd >= 2.0 and nfl >= 3 and grng.random() < 0.2:
            w = min(span - 1, grng.uniform(5, 14))
            a0 = s0 + grng.uniform(0.5, max(0.6, span - w - 0.5))
            a1 = a0 + w
            dep = grng.uniform(2.0, min(3.5, maxd))
            tint = grng.random()
            k0 = grng.randint(0, max(0, nfl - 3))
            for k in range(k0, min(nfl, k0 + grng.randint(3, 12))):
                fy = y0 + k * FL
                face_box(G, side, fx, a0, a1, fy - 0.25, fy, 0.0, dep, (1, tint))
                face_box(G, side, fx, a0, a1, fy + 0.9, fy + 1.05, dep - 0.08, dep, (2, tint))      # top rail
                face_box(G, side, fx, a0, a0 + 0.08, fy, fy + 1.05, 0.0, dep, (2, tint))            # side rails
                face_box(G, side, fx, a1 - 0.08, a1, fy, fy + 1.05, 0.0, dep, (2, tint))
                for pa in np.arange(a0 + 1.5, a1 - 0.5, 1.5):                                     # posts
                    face_box(G, side, fx, pa - 0.05, pa + 0.05, fy, fy + FL - 0.25, dep - 0.1, dep, (2, tint))
                GSTAT["deep"] += 1
        # vertical service pipes
        if grng.random() < 0.35 and y1 - y0 > 10:
            for _ in range(grng.randint(1, 3)):
                a = grng.uniform(s0 + 0.5, s1 - 0.5)
                r = grng.uniform(0.12, 0.3)
                face_box(G, side, fx, a - r, a + r, y0, min(y1, 175), 0.15, 0.15 + 2 * r, (2, grng.random()))
                GSTAT["pipes"] += 1
        # bolted-on boxes: utility rooms, shacks, signage cabinets
        if grng.random() < 0.45:
            for _ in range(grng.randint(2, 7)):
                bw = grng.uniform(1.5, 4.5)
                bh = grng.uniform(1.2, 3.4)
                if s1 - s0 < bw + 1.0:
                    continue
                a = grng.uniform(s0 + bw / 2 + 0.3, s1 - bw / 2 - 0.3)
                top = min(y1, 170) - bh
                if top < y0 + 2.5:
                    continue
                by = grng.uniform(y0 + 2, top)
                face_box(G, side, fx, a - bw / 2, a + bw / 2, by, by + bh, 0.0, grng.uniform(0.7, 2.0), (1, grng.random()))
        # AC units under the windows
        if y0 > 160:
            continue
        nb = int(span / 2.6)
        p = 0.09 if y0 < 90 else 0.05
        for k in range(nfl):
            fy = y0 + k * FL + 0.35
            for b in range(nb):
                if grng.random() < p:
                    a = s0 + (b + 0.5) * 2.6 + grng.uniform(-0.4, 0.4)
                    w = grng.uniform(0.7, 1.0)
                    face_box(G, side, fx, a - w / 2, a + w / 2, fy, fy + grng.uniform(0.5, 0.7), 0.0,
                             grng.uniform(0.4, 0.6), (0, grng.random()))
                    GSTAT["ac"] += 1


def floodlight(x0, x1, z0, z1, h):
    """a lamp on a face throwing a cone of light into the haze"""
    side = grng.randrange(4)
    fx = (x0, x1, z0, z1)[side]
    s0, s1 = ((z0, z1), (z0, z1), (x0, x1), (x0, x1))[side]
    a = grng.uniform(s0 + 1, s1 - 1)
    y = grng.uniform(14, min(h - 4, 150))
    out = ((-1, 0), (1, 0), (0, -1), (0, 1))[side]
    if side < 2:
        px, pz = fx + out[0] * 0.6, a
    else:
        px, pz = a, fx + out[1] * 0.6
    apex = np.array([px, y, pz])
    dirv = np.array([out[0] * grng.uniform(0.3, 0.9), -1.0, out[1] * grng.uniform(0.3, 0.9)])
    dirv /= np.linalg.norm(dirv)
    L = grng.uniform(16, 34)
    rad = L * grng.uniform(0.22, 0.34)
    col = 7 if grng.random() < 0.6 else 6
    # orthonormal frame
    t1 = np.cross(dirv, [0, 0, 1.0]) if abs(dirv[2]) < 0.9 else np.cross(dirv, [1.0, 0, 0])
    t1 /= np.linalg.norm(t1)
    t2 = np.cross(dirv, t1)
    K = 14
    verts, idx = [], []
    for i in range(K + 1):
        ang = 2 * math.pi * i / K
        rdir = t1 * math.cos(ang) + t2 * math.sin(ang)
        nrm = rdir - dirv * (rad / L)
        nrm /= np.linalg.norm(nrm)
        verts.append((*(apex + rdir * 0.25), *nrm, col, 0.0))
        verts.append((*(apex + dirv * L + rdir * rad), *nrm, col, 1.0))
    for i in range(K):
        a0, b0, a1, b1 = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
        idx += [a0, b0, b1, a0, b1, a1]
    M("cones").add(verts, idx)
    boxm(M("neon"), px - 0.35, px + 0.35, y - 0.2, y + 0.2, pz - 0.35, pz + 0.35, (col, grng.random()))
    GSTAT["cones"] += 1


def tower(x0, z0, x1, z1, h, bi, bj, faces_street):
    """Dense tower block: stacked jittered sections, bolted-on annexes,
    ledges, pipes and rooftop clutter. Returns the street-level shaft bounds."""
    L = pick_layer(h)
    off = rng.uniform(2000, 8000)
    hsh = rng.random()
    # podium (industrial / same material)
    ph = 0.0
    lx0, lz0, lx1, lz1 = x0, z0, x1, z1
    if h > 40:
        ph = rng.uniform(8, 22)
        tbox(B, x0, x1, 0.2, ph, z0, z1, L_IND if rng.random() < 0.6 else L, off)
        if rng.random() < 0.55:
            add_neon_ring(rect_poly(x0 - 0.1, z0 - 0.1, x1 + 0.1, z1 + 0.1), rng.uniform(4.2, 6.0), neon_pick(), 0.22)
    ins = rng.uniform(0.5, 4.0) if ph > 0 else 0.0
    cx0, cz0, cx1, cz1 = x0 + ins, z0 + ins, x1 - ins, z1 - ins
    shaft = (cx0, cz0, cx1, cz1)
    y = max(ph, 0.2)
    first = True
    while y < h - 1:
        seg = rng.uniform(16, 55)
        y1 = min(h, y + seg)
        if h - y1 < 10:
            y1 = h
        # jitter each side; overhangs up to 3 m into the sidewalk above the podium
        lim = 3.0 if y > 14 else 0.0
        jx0 = max(x0 - lim, cx0 + rng.uniform(-2.5, 2.5))
        jx1 = min(x1 + lim, cx1 + rng.uniform(-2.5, 2.5))
        jz0 = max(z0 - lim, cz0 + rng.uniform(-2.5, 2.5))
        jz1 = min(z1 + lim, cz1 + rng.uniform(-2.5, 2.5))
        if first:
            jx0, jz0, jx1, jz1 = cx0, cz0, cx1, cz1
            first = False
        if jx1 - jx0 < 8 or jz1 - jz0 < 8:
            jx0, jz0, jx1, jz1 = cx0, cz0, cx1, cz1
        tbox(B, jx0, jx1, y, y1, jz0, jz1, L, off)
        greebles(jx0, jx1, y, y1, jz0, jz1)
        # ledge slab
        if rng.random() < 0.6:
            e = rng.uniform(0.4, 1.2)
            tbox(B, jx0 - e, jx1 + e, y1 - 0.7, y1, jz0 - e, jz1 + e, L_IND, off + 300, bottom=True)
        # annexes bolted to the faces
        for _ in range(rng.randint(0, 4)):
            side = rng.randrange(4)
            ah = rng.uniform(8, min(45, y1 - y + 6))
            ay = rng.uniform(y, max(y, y1 - ah))
            aw = rng.uniform(5, 18)
            ad = rng.uniform(1.5, 5.0)
            AL = L if rng.random() < 0.6 else rng.choice([L_HK, L_IND, L_RES])
            ao = off + rng.uniform(0, 500)
            if side in (0, 1):
                span0, span1 = jz0, jz1
            else:
                span0, span1 = jx0, jx1
            if span1 - span0 < aw + 1:
                continue
            t0 = rng.uniform(span0, span1 - aw)
            if side == 0:
                tbox(B, jx0 - ad, jx0 + 0.5, ay, ay + ah, t0, t0 + aw, AL, ao)
            elif side == 1:
                tbox(B, jx1 - 0.5, jx1 + ad, ay, ay + ah, t0, t0 + aw, AL, ao)
            elif side == 2:
                tbox(B, t0, t0 + aw, ay, ay + ah, jz0 - ad, jz0 + 0.5, AL, ao)
            else:
                tbox(B, t0, t0 + aw, ay, ay + ah, jz1 - 0.5, jz1 + ad, AL, ao)
        # setback
        if rng.random() < 0.3 and (cx1 - cx0) > 22 and (cz1 - cz0) > 22:
            d = rng.uniform(2, 5)
            cx0, cz0, cx1, cz1 = cx0 + d, cz0 + d, cx1 - d, cz1 - d
        y = y1
    for _ in range(2 if grng.random() < 0.35 else 0):
        floodlight(cx0, cx1, cz0, cz1, h)
    # pipes / risers down the faces
    for _ in range(rng.randint(0, 5)):
        side = rng.randrange(4)
        r = rng.uniform(0.25, 0.7)
        py1 = rng.uniform(h * 0.3, h)
        if side == 0:
            px, pz = cx0 - r - 0.1, rng.uniform(cz0 + 1, cz1 - 1)
        elif side == 1:
            px, pz = cx1 + r + 0.1, rng.uniform(cz0 + 1, cz1 - 1)
        elif side == 2:
            px, pz = rng.uniform(cx0 + 1, cx1 - 1), cz0 - r - 0.1
        else:
            px, pz = rng.uniform(cx0 + 1, cx1 - 1), cz1 + r + 0.1
        tbox(B, px - r, px + r, max(ph, 0.2), py1, pz - r, pz + r, L_IND, off + 900)
    # rooftop clutter
    rcx, rcz = (cx0 + cx1) / 2, (cz0 + cz1) / 2
    rw, rd = (cx1 - cx0) / 2, (cz1 - cz0) / 2
    for _ in range(rng.randint(2, 7)):
        kx, kz = rcx + rng.uniform(-rw * 0.7, rw * 0.7), rcz + rng.uniform(-rd * 0.7, rd * 0.7)
        if rng.random() < 0.4:
            cr = rng.uniform(1.2, 3.0)
            ctop = h + rng.uniform(3, 7)
            tcyl(B, kx, kz, cr, h, ctop, L_IND, off + 1200)
            # some stacks vent steam (own RNG: the city layout stays put)
            if srng.random() < 0.15:
                STEAM.append((kx, ctop + 0.2, kz, cr * 0.85, srng.random(), 0.0, 0.08 + srng.random() * 0.06, 0.0))
        else:
            sx, sz = rng.uniform(1.5, 6), rng.uniform(1.5, 6)
            tbox(B, kx - sx, kx + sx, h, h + rng.uniform(1.5, 6), kz - sz, kz + sz, L_IND, off + 1500)
    if h > 160 and rng.random() < 0.5:
        sh = rng.uniform(18, 60)
        tbox(B, rcx - 0.8, rcx + 0.8, h, h + sh, rcz - 0.8, rcz + 0.8, L_IND, off)
        neon_bar((rcx, h + sh, rcz), (rcx, h + sh + 1.4, rcz), 1.2, 5, 0.5, mesh="beacons")
    tower_tops.append((rcx, rcz, h, rect_poly(*shaft), shaft, 0, ph))
    return shaft, 0, ph


def height_at(x, z):
    d = math.hypot(x - CX, z - CZ)
    hmax = 80 + 300 * math.exp(-(d / 650) ** 2)
    r = rng.random()
    if r < 0.25:
        return rng.uniform(24, 55)          # low-rise: lets the sun into the canyons
    return max(40, hmax * rng.uniform(0.35, 1.2))


lot_info = {}
for bi in range(LO, HI):
    for bj in range(LO, HI):
        bx0, bx1 = S(bi) + RW + WALK, S(bi + 1) - RW - WALK
        bz0, bz1 = S(bj) + RW + WALK, S(bj + 1) - RW - WALK
        kind = rng.choices([1, 2, 4], [1, 3, 5])[0]
        lots = []
        if kind == 1:
            lots = [(bx0, bz0, bx1, bz1)]
        elif kind == 2:
            if rng.random() < 0.5:
                mx = (bx0 + bx1) / 2
                lots = [(bx0, bz0, mx - 1, bz1), (mx + 1, bz0, bx1, bz1)]
            else:
                mz = (bz0 + bz1) / 2
                lots = [(bx0, bz0, bx1, mz - 1), (bx0, mz + 1, bx1, bz1)]
        else:
            mx, mz = (bx0 + bx1) / 2, (bz0 + bz1) / 2
            lots = [(bx0, bz0, mx - 1, mz - 1), (mx + 1, bz0, bx1, mz - 1), (bx0, mz + 1, mx - 1, bz1), (mx + 1, mz + 1, bx1, bz1)]
        built = []
        # open alleys between towers so light and air get into the block
        lots = [(x0 + rng.uniform(0, 5), z0 + rng.uniform(0, 5), x1 - rng.uniform(0, 5), z1 - rng.uniform(0, 5)) for (x0, z0, x1, z1) in lots]
        for (x0, z0, x1, z1) in lots:
            h = height_at((x0 + x1) / 2, (z0 + z1) / 2)
            if kind == 1:
                h *= 1.25
            shaft, sk, ph = tower(x0, z0, x1, z1, h, bi, bj, True)
            built.append((x0, z0, x1, z1, h, shaft, sk, ph))
        lot_info[(bi, bj)] = built
        # skybridges between neighbouring towers
        if len(built) >= 2 and rng.random() < 0.7:
            a, b = built[0], built[1]
            lo_h = min(a[4], b[4])
            if lo_h > 45:
                y = rng.uniform(22, lo_h - 12)
                (ax0, az0, ax1, az1), (bx0_, bz0_, bx1_, bz1_) = a[5], b[5]
                hsh = rng.random()
                if abs(az0 - bz0_) < 1 and ax1 < bx0_:   # side by side in x
                    zc = (max(az0, bz0_) + min(az1, bz1_)) / 2
                    boxm(B, ax1 - 1, bx0_ + 1, y, y + 5, zc - 3.5, zc + 3.5, uv=(hsh, y + 5), bottom=True)
                    COLL.append((ax1 - 1, y, zc - 3.5, bx0_ + 1, y + 5, zc + 3.5))
                    neon_bar((ax1, y - 0.2, zc - 3.6), (bx0_, y - 0.2, zc - 3.6), 0.25, neon_pick())
                    neon_bar((ax1, y - 0.2, zc + 3.6), (bx0_, y - 0.2, zc + 3.6), 0.25, neon_pick())
                    skybridge_count += 1
                elif abs(ax0 - bx0_) < 1 and az1 < bz0_:
                    xc = (max(ax0, bx0_) + min(ax1, bx1_)) / 2
                    boxm(B, xc - 3.5, xc + 3.5, y, y + 5, az1 - 1, bz0_ + 1, uv=(hsh, y + 5), bottom=True)
                    COLL.append((xc - 3.5, y, az1 - 1, xc + 3.5, y + 5, bz0_ + 1))
                    neon_bar((xc - 3.6, y - 0.2, az1), (xc - 3.6, y - 0.2, bz0_), 0.25, neon_pick())
                    neon_bar((xc + 3.6, y - 0.2, az1), (xc + 3.6, y - 0.2, bz0_), 0.25, neon_pick())
                    skybridge_count += 1

# ---------------------------------------------------------------- street clutter: cables, lanterns, blade signs
crng = random.Random(777)
CAB = M("cables")


CABSEG = []   # cable segment AABBs (screens must not be threaded by a cable)
_CAB_NP = [None]


def cable(a, b, sag, r):
    """catenary-ish sagging cable as a thin 6-sided tube"""
    a, b = np.array(a, float), np.array(b, float)
    pts = []
    K = 12
    for i in range(K + 1):
        t = i / K
        p = a + (b - a) * t
        p[1] -= sag * 4 * t * (1 - t)
        pts.append(p)
    for i in range(K):
        CABSEG.append(tuple(np.minimum(pts[i], pts[i + 1])) + tuple(np.maximum(pts[i], pts[i + 1])))
    for i in range(K):
        p0, p1 = pts[i], pts[i + 1]
        d = p1 - p0
        L = np.linalg.norm(d)
        fd = d / L
        up = np.array([0, 1.0, 0]) if abs(fd[1]) < 0.9 else np.array([1.0, 0, 0])
        rr = np.cross(fd, up); rr /= np.linalg.norm(rr)
        uu = np.cross(rr, fd)
        ring0, ring1 = [], []
        for k in range(6):
            ang = k * math.pi / 3
            nrm = rr * math.cos(ang) + uu * math.sin(ang)
            ring0.append((p0 + nrm * r, nrm))
            ring1.append((p1 + nrm * r, nrm))
        for k in range(6):
            k2 = (k + 1) % 6
            verts = [(*ring0[k][0], *ring0[k][1], 0, 0), (*ring0[k2][0], *ring0[k2][1], 0, 0),
                     (*ring1[k2][0], *ring1[k2][1], 0, 0), (*ring1[k][0], *ring1[k][1], 0, 0)]
            CAB.add(verts, [0, 1, 2, 0, 2, 3])
    return pts


def in_band(y):
    # keep the player's canyon lane (≈62 m) and the sky lane (≈140 m) clear
    return not (52 < y < 74 or 128 < y < 152)


n_cables = n_lant = n_blades = 0
BLADES = []   # blade sign volumes (screens must clear them too)
FAC = RW + WALK            # facade line from a street centre line
for axis in (0, 1):
    for k in range(LO + 1, HI):
        line = k * P
        along0, along1 = (LO + 0.5) * P, (HI - 0.5) * P
        t = along0 + crng.uniform(5, 30)
        while t < along1:
            # skip intersections
            if abs(((t + P / 2) % P) - P / 2) > FAC + 2:
                near = 0 <= k <= N and -P < t < (N + 1) * P
                nb = crng.randint(1, 4) if near else crng.randint(1, 2)
                y = crng.uniform(9, 120)
                if in_band(y):
                    for c in range(nb):
                        yy = y + c * crng.uniform(0.3, 0.9)
                        tt = t + c * crng.uniform(-0.6, 0.6)
                        sag = crng.uniform(0.8, 3.2)
                        a = (tt, yy, line - FAC) if axis == 0 else (line - FAC, yy, tt)
                        b = (tt + crng.uniform(-6, 6), yy + crng.uniform(-3, 3), line + FAC) if axis == 0 else \
                            (line + FAC, yy + crng.uniform(-3, 3), tt + crng.uniform(-6, 6))
                        pts = cable(a, b, sag, crng.uniform(0.035, 0.08))
                        n_cables += 1
                        if c == 0 and near and crng.random() < 0.35:
                            col = crng.choice([2, 2, 0, 1, 4, 6])
                            for q in range(2, 11, crng.choice([2, 3])):
                                p = pts[q]
                                boxm(M("neon"), p[0] - 0.22, p[0] + 0.22, p[1] - 0.95, p[1] - 0.35, p[2] - 0.22, p[2] + 0.22,
                                     (col, crng.random()))
                                n_lant += 1
            t += crng.uniform(14, 46) if (0 <= k <= N) else crng.uniform(30, 90)

# vertical blade signs on street-facing faces of near towers
for (bi, bj), built in lot_info.items():
    if not (-1 <= bi <= N and -1 <= bj <= N):
        continue
    for (x0, z0, x1, z1, h, *_rest) in built:
        for side in range(4):
            fx = (x0, x1, z0, z1)[side]
            # is this face looking onto a street?
            frac = (fx / P) % 1.0
            dist = min(frac, 1 - frac) * P
            if dist > FAC + 6:
                continue
            s0, s1 = ((z0, z1), (z0, z1), (x0, x1), (x0, x1))[side]
            out = (-1, 1, -1, 1)[side]
            # outward = toward the street centre
            ctr = round(fx / P) * P
            if (ctr - fx) * out < 0:
                continue
            a = s0 + crng.uniform(3, 12)
            while a < s1 - 3:
                if crng.random() < 0.5:
                    hgt = crng.uniform(4, 12)
                    y0 = crng.uniform(5, min(48, h - hgt - 2)) if h > 20 else 5
                    if in_band(y0) and in_band(y0 + hgt):
                        dep = crng.uniform(1.6, 3.0)
                        col = crng.choice([0, 1, 2, 3, 4, 5, 6, 7, 2, 4])
                        th = 0.35
                        if side < 2:
                            bx = (fx + out * 0.2, fx + out * (0.2 + dep)) if out > 0 else (fx + out * (0.2 + dep), fx + out * 0.2)
                            boxm(M("neon"), bx[0], bx[1], y0, y0 + hgt, a - th / 2, a + th / 2, (col, crng.random()))
                            BLADES.append((bx[0], y0, a - th, bx[1], y0 + hgt, a + th))
                            GINST.append(((bx[0] + bx[1]) / 2, y0 + hgt / 2, a, abs(bx[1] - bx[0]) + 0.25, hgt + 0.3, th - 0.1, 2, 0.5))
                        else:
                            bz = (fx + out * 0.2, fx + out * (0.2 + dep)) if out > 0 else (fx + out * (0.2 + dep), fx + out * 0.2)
                            boxm(M("neon"), a - th / 2, a + th / 2, y0, y0 + hgt, bz[0], bz[1], (col, crng.random()))
                            BLADES.append((a - th, y0, bz[0], a + th, y0 + hgt, bz[1]))
                            GINST.append((a, y0 + hgt / 2, (bz[0] + bz[1]) / 2, th - 0.1, hgt + 0.3, abs(bz[1] - bz[0]) + 0.25, 2, 0.5))
                        n_blades += 1
                a += crng.uniform(8, 22)
print("street clutter: cables", n_cables, "lanterns", n_lant, "blade signs", n_blades)


# ---------------------------------------------------------------- billboards
# wall billboards on rect shafts facing a street (drivable area +1)
for (bi, bj), built in lot_info.items():
    if not (-1 <= bi <= N and -1 <= bj <= N):
        continue
    for (x0, z0, x1, z1, h, shaft, sk, ph) in built:
        if sk != 0 or h < 30:
            continue
        sx0, sz0, sx1, sz1 = shaft
        bx0, bx1 = S(bi) + RW + WALK, S(bi + 1) - RW - WALK
        bz0, bz1 = S(bj) + RW + WALK, S(bj + 1) - RW - WALK
        faces = []
        if abs(x0 - bx0) < 6: faces.append(("w", sx0, (sz0, sz1)))
        if abs(x1 - bx1) < 6: faces.append(("e", sx1, (sz0, sz1)))
        if abs(z0 - bz0) < 6: faces.append(("n", sz0, (sx0, sx1)))
        if abs(z1 - bz1) < 6: faces.append(("s", sz1, (sx0, sx1)))
        for side, plane, (a0, a1) in faces:
            if rng.random() > 0.42:
                continue
            width = a1 - a0
            portrait = rng.random() < 0.34 or width < 14
            room = min(h - max(ph + 2, 34) - 3, 150 - 34)
            sz = pick_size(PORT_SIZES if portrait else LAND_SIZES, width - 2, room)
            if sz is None:
                continue
            w, hh = sz
            des = rng.choice((7, 8, 7, 8, 5)) if portrait else rng.choice(LAND_DES + [6])
            ymin = max(ph + 2, 34) + hh / 2
            ymax = min(h - hh / 2 - 3, 150 if hh > 18 else 125)
            if ymax < ymin:
                continue
            y = rng.uniform(ymin, ymax)
            t = rng.uniform(a0 + w / 2 + 1, a1 - w / 2 - 1)
            off = 1.0
            if side == "w":
                billboard((plane - off, y, t), (-1, 0), w, hh, des)
            elif side == "e":
                billboard((plane + off, y, t), (1, 0), w, hh, des)
            elif side == "n":
                billboard((t, y, plane - off), (0, -1), w, hh, des)
            else:
                billboard((t, y, plane + off), (0, 1), w, hh, des)

# route billboards on BUILDINGS (no street-spanning gantries: the air-traffic lanes
# flew straight through them). At every cross street along a route straight, the
# corner buildings on the far side present a face to oncoming traffic: mount a
# screen there, held off the wall by steel brackets, so it is still seen head-on.
GT = M("gantry")
route_designs = [0, 6, 2, 0, 1, 6, 3, 0, 4, 6, 2, 1]
route_port = [8, 7]
gk_all = [0]
gkp = 0
gk = 0
used_faces = set()


SILLY = dict(placed=False, leg=-1, step=0, info=None)


def facade_screen(plane_axis, plane, nrm, lat0, lat1, h, near_lat):
    """mount a screen on a face; plane_axis 'z' -> face plane z=plane spanning x in [lat0, lat1]"""
    global gk, gkp
    span = lat1 - lat0
    if span < 10 or h < 40:
        return False
    # the playable SillyScroll board: one big square screen early on the first leg, where the car
    # can pull up in front of it (world script computes the stop point from its centre + normal)
    if not SILLY["placed"] and SILLY["leg"] == 0 and SILLY["step"] >= 1 and span >= 21 and h >= 85:
        w = hh = min(20.0, span - 3)
        lat = near_lat + (w / 2 + 1.5) * (1 if near_lat == lat0 else -1)
        y = 62.0 + 3.0           # canyon-lane eye height, a touch above so the dash doesn't cut it
        off = 2.2
        if plane_axis == "z":
            c = (lat, y, plane + nrm * off)
            sh = billboard(c, (0, nrm), w, hh, SILLY_DES)
        else:
            c = (plane + nrm * off, y, lat)
            sh = billboard(c, (nrm, 0), w, hh, SILLY_DES)
        if sh is not None:
            SILLY["placed"] = True
            SILLY["info"] = (c, w, plane_axis, nrm)
            print("silly board", c, w, plane_axis, nrm)
            return True
    if gk_all[0] % 3 == 1 and h > 70 and span >= 13:
        # every third route screen: a tall AURA / DEEPWATER banner facing oncoming traffic
        w, hh = (12.0, 28.0) if (h > 120 and span >= 16) else (10.0, 20.0)
    elif span >= 44 and h > 110 and rng.random() < 0.6:
        w, hh = 40.0, 20.0          # megascreen
    elif span >= 36 and h > 95:
        w, hh = 32.0, 16.0
    elif span >= 27:
        w, hh = rng.choice([(24.0, 12.0), (22.0, 7.0)])
    elif span >= 21:
        w, hh = 18.0, 9.0
    elif h > 120:
        w, hh = 10.0, 26.0          # tower banner
    else:
        w, hh = 8.0, 16.0
    if w + 3 > span:
        return False
    gk_all[0] += 1
    if w > hh:
        des = route_designs[gk % len(route_designs)]
        gk += 1
    else:
        des = route_port[gkp % len(route_port)]
        gkp += 1
    # hug the street-side end of the face so it reads from the route
    lat = near_lat + (w / 2 + 1.5) * (1 if near_lat == lat0 else -1)
    y = min(h - hh / 2 - 4, rng.uniform(46, 78) if hh < 22 else rng.uniform(50, 70))
    if y - hh / 2 < 30:
        return False
    off = 2.2
    if plane_axis == "z":
        c = (lat, y, plane + nrm * off)
        sh = billboard(c, (0, nrm), w, hh, des)
        if sh is None:
            return False
        off += sh
        for sx in (-1, 1):   # brackets into the wall
            bx = lat + sx * (w / 2 - 1.5)
            for by in (y - hh / 4, y + hh / 4):
                boxm(GT, bx - 0.25, bx + 0.25, by - 0.25, by + 0.25, min(plane, plane + nrm * (off - 0.6)), max(plane, plane + nrm * (off - 0.6)))
    else:
        c = (plane + nrm * off, y, lat)
        sh = billboard(c, (nrm, 0), w, hh, des)
        if sh is None:
            return False
        off += sh
        for sz in (-1, 1):
            bz = lat + sz * (w / 2 - 1.5)
            for by in (y - hh / 4, y + hh / 4):
                boxm(GT, min(plane, plane + nrm * (off - 0.6)), max(plane, plane + nrm * (off - 0.6)), by - 0.25, by + 0.25, bz - 0.25, bz + 0.25)
    return True


for k in range(len(ROUTE_IJ)):
    i0, j0 = ROUTE_IJ[k]
    i1, j1 = ROUTE_IJ[(k + 1) % len(ROUTE_IJ)]
    ns = i0 == i1
    a0, a1 = (j0, j1) if ns else (i0, i1)
    d = 1 if a1 > a0 else -1
    line = S(i0) if ns else S(j0)          # route street centre line
    li = i0 if ns else j0
    for ci, cs in enumerate(range(a0 + d, a1 + d, d)):    # every cross street incl. the turn
        cross = S(cs)
        SILLY["leg"] = k
        SILLY["step"] = ci
        # far-side blocks: along +d past the cross street
        blk = cs if d > 0 else cs - 1
        for side in (-1, 1):
            bl = li if side > 0 else li - 1
            key = (bl, blk) if ns else (blk, bl)
            best = None
            for (x0, z0, x1, z1, h, shaft, sk, ph) in lot_info.get(key, []):
                sx0, sz0, sx1, sz1 = shaft
                if ns:
                    plane = sz0 if d > 0 else sz1
                    gap = abs(plane - cross)
                    lat0, lat1 = sx0, sx1
                else:
                    plane = sx0 if d > 0 else sx1
                    gap = abs(plane - cross)
                    lat0, lat1 = sz0, sz1
                near = lat0 if side > 0 else lat1
                latd = abs(near - line)
                if gap > RW + WALK + 18 or latd > RW + WALK + 16 or h < 40:
                    continue
                if best is None or gap + latd < best[0]:
                    best = (gap + latd, plane, lat0, lat1, h, near)
            if best and (key, side, d) not in used_faces:
                used_faces.add((key, side, d))
                _, plane, lat0, lat1, h, near = best
                facade_screen("z" if ns else "x", plane, -d, lat0, lat1, h, near)
print("route facade screens", gk)

# giant screen on the tallest rect tower near the route start (the dive passes it)
best = None
for (bi, bj), built in lot_info.items():
    if not (0 <= bi < N and 0 <= bj < N):
        continue
    for (x0, z0, x1, z1, h, shaft, sk, ph) in built:
        if sk == 0 and (shaft[2] - shaft[0]) > 34:
            score = h - 0.3 * math.hypot((x0 + x1) / 2 - S(2), (z0 + z1) / 2 - S(5))
            if best is None or score > best[0]:
                best = (score, shaft, h)
giant = None
if best:
    _, (sx0, sz0, sx1, sz1), h = best
    # west face looking toward Kestrel Ave (x = 100)
    w = min(sx1 - sx0, sz1 - sz0) - 4
    gw, gh = w, w / 2
    gy = min(h - gh / 2 - 6, 95)
    billboard(((sx0 + sx1) / 2, gy, sz1 + 1.2), (0, 1), gw, gh, 0)
    giant = billboards[-1]

# rooftop billboards on low buildings in the drivable area
for (bi, bj), built in lot_info.items():
    if not (0 <= bi < N and 0 <= bj < N):
        continue
    for (x0, z0, x1, z1, h, shaft, sk, ph) in built:
        if h > 62 or rng.random() > 0.5:
            continue
        sx0, sz0, sx1, sz1 = shaft
        cxx, czz = (sx0 + sx1) / 2, (sz0 + sz1) / 2
        # face the nearer street
        dxs = [(abs(cxx - S(bi)), (-1, 0)), (abs(S(bi + 1) - cxx), (1, 0)), (abs(czz - S(bj)), (0, -1)), (abs(S(bj + 1) - czz), (0, 1))]
        _, n = min(dxs)
        span = (sz1 - sz0) if n[0] != 0 else (sx1 - sx0)
        sz = pick_size([((16.0, 8.0), 3), ((22.0, 11.0), 3), ((30.0, 15.0), 1.5), ((26.0, 8.0), 1)], span - 2, 99)
        if sz is None:
            continue
        w, hh = sz
        y = h + 4 + hh / 2
        if n[0] != 0:
            px = sx1 - 3 if n[0] > 0 else sx0 + 3
            c = (px, y, czz)
        else:
            pz = sz1 - 3 if n[1] > 0 else sz0 + 3
            c = (cxx, y, pz)
        billboard(c, n, w, hh, rng.choice([0, 1, 2, 3, 4, 6, 1, 6]))
        # struts
        for s in (-0.35, 0.35):
            if n[0] != 0:
                boxm(GT, c[0] - n[0] * 1.5 - 0.3, c[0] - n[0] * 1.5 + 0.3, h, y - hh / 2, c[2] + s * w - 0.3, c[2] + s * w + 0.3)
            else:
                boxm(GT, c[0] + s * w - 0.3, c[0] + s * w + 0.3, h, y - hh / 2, c[2] - n[1] * 1.5 - 0.3, c[2] - n[1] * 1.5 + 0.3)

# ---------------------------------------------------------------- lamps + sky gates
LP = M("lamps")
for zi in [S(j) for j in range(-1, N + 2)]:
    for x in np.arange(S(-1) + 25, S(N + 1), 25):
        if abs((x % P) - 0) < RW + 6 or abs((x % P) - P) < RW + 6:
            continue
        for sgn in (-1, 1):
            z = zi + sgn * (RW + 1.2)
            boxm(LP, x - 0.14, x + 0.14, 0.2, 8.5, z - 0.14, z + 0.14)
            boxm(LP, x - 0.12, x + 0.12, 8.3, 8.6, z - sgn * 2.4, z)
            neon_bar((x, 8.2, z - sgn * 2.3), (x, 8.2, z - sgn * 0.6), 0.32, 6, 0.0, mesh="lampglow")
for xi in [S(i) for i in range(-1, N + 2)]:
    for z in np.arange(S(-1) + 25, S(N + 1), 25):
        if abs((z % P) - 0) < RW + 6 or abs((z % P) - P) < RW + 6:
            continue
        for sgn in (-1, 1):
            x = xi + sgn * (RW + 1.2)
            boxm(LP, x - 0.14, x + 0.14, 0.2, 8.5, z - 0.14, z + 0.14)
            boxm(LP, x - sgn * 2.4, x, 8.3, 8.6, z - 0.12, z + 0.12)
            neon_bar((x - sgn * 2.3, 8.2, z), (x - sgn * 0.6, 8.2, z), 0.32, 6, 0.0, mesh="lampglow")

# sky-lane gates: floating hoops over the streets (the SKY lane at ~26 m)
gates = []

# ---------------------------------------------------------------- far silhouettes
FAR = M("far")
for _ in range(1600):
    a = rng.uniform(0, 2 * math.pi)
    r = 1450 + (rng.random() ** 1.6) * 3800
    x, z = CX + r * math.cos(a), CZ + r * math.sin(a)
    w = rng.uniform(30, 90)
    d = rng.uniform(30, 90)
    h = rng.uniform(120, 560) * (1.25 if r < 1600 else 1.0)
    hsh = rng.random()
    FL = pick_layer(h)
    fo = rng.uniform(2000, 8000)
    tbox(FAR, x - w / 2, x + w / 2, 0, h * 0.62, z - d / 2, z + d / 2, FL, fo)
    tbox(FAR, x - w / 3, x + w / 3, h * 0.62, h, z - d / 3, z + d / 3, FL, fo)
    if rng.random() < 0.25:
        neon_bar((x, h + 2, z), (x, h + 3.5, z), 3.0, 5, rng.random(), mesh="beacons")

# ---------------------------------------------------------------- swarm car (instanced traffic)
# local metres, +z forward; uv.x material code: 0 body 1 tail light 2 head light 3 thruster 4 glass
SW = M("swarmcar")
# Lofted hover sedan (~300 tris, instanced ~8k times): tapered rounded body,
# dark glass canopy, thin LED bars. uv = (material code, stretch); stretch = 1
# marks light vertices the vertex shader drags backwards into a speed streak.


def loft(mesh, stations, code, n=12, ex=4.0, cap_back=True, cap_front=True):
    """stations: [(z, half-width, y-bottom, y-top)] -> rounded superellipse rings"""
    rings = []
    for (z, hw, yb, yt) in stations:
        yc, hh = (yb + yt) / 2, (yt - yb) / 2
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            ca, sa = math.cos(a), math.sin(a)
            x = hw * math.copysign(abs(ca) ** (2 / ex), ca)
            y = yc + hh * math.copysign(abs(sa) ** (2 / ex), sa)
            ring.append(np.array([x, y, z]))
        rings.append(ring)
    verts, idx = [], []
    for i in range(len(rings) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            p = [rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]]
            nrm = np.cross(p[1] - p[0], p[3] - p[0])
            # outward: away from the station centre line
            ctr = np.array([0, (stations[i][2] + stations[i][3]) / 2, p[0][2]])
            if np.dot(nrm, (p[0] + p[2]) / 2 - ctr) < 0:
                nrm = -nrm
            ln = np.linalg.norm(nrm)
            if ln < 1e-9:
                continue
            nrm = nrm / ln
            base = len(verts)
            # smooth-ish: per-vertex radial normals blended with the face normal
            for q in p:
                rad = q - np.array([0, ctr[1], q[2]])
                rad = rad / (np.linalg.norm(rad) + 1e-9)
                nn = rad * 0.6 + nrm * 0.4
                nn /= np.linalg.norm(nn)
                verts.append((*q, *nn, code, 0))
            idx += [base, base + 1, base + 2, base, base + 2, base + 3]
    for ci, (cap, ring, sgn) in enumerate(((cap_back, rings[0], -1), (cap_front, rings[-1], 1))):
        if not cap:
            continue
        c = sum(ring) / len(ring)
        base = len(verts)
        verts.append((*c, 0, 0, sgn, code, 0))
        for q in ring:
            verts.append((*q, 0, 0, sgn, code, 0))
        for k in range(n):
            a, b = base + 1 + k, base + 1 + (k + 1) % n
            idx += [base, b, a] if sgn < 0 else [base, a, b]
    mesh.add(verts, idx)


loft(SW, [(-2.40, 0.72, -0.12, 0.30), (-2.25, 0.88, -0.24, 0.34), (-1.60, 0.98, -0.30, 0.38), (-0.60, 1.00, -0.30, 0.40),
          (0.40, 1.00, -0.30, 0.40), (1.30, 0.95, -0.28, 0.35), (2.00, 0.78, -0.22, 0.25), (2.35, 0.52, -0.12, 0.13),
          (2.46, 0.26, -0.03, 0.04)], 0)
loft(SW, [(-1.25, 0.46, 0.30, 0.42), (-0.70, 0.66, 0.30, 0.76), (0.30, 0.66, 0.30, 0.80), (0.95, 0.44, 0.30, 0.46)], 4, n=10)


def light_bar(x0, x1, y0, y1, z0, z1, code, stretch_back):
    """thin emissive bar; with stretch_back its rear vertices trail behind at speed"""
    b = len(SW.v)
    boxm(SW, x0, x1, y0, y1, z0, z1, uv=(code, 0), bottom=True)
    if stretch_back:
        for j in range(b, len(SW.v)):
            arr = np.array(SW.v[j], np.float32).reshape(-1, 8)
            arr[arr[:, 2] <= z0 + 1e-4, 7] = 1.0
            SW.v[j] = arr


light_bar(-0.84, 0.84, 0.13, 0.20, -2.44, -2.36, 1, True)     # tail LED bar
light_bar(-0.95, -0.80, -0.05, 0.22, -2.30, -2.10, 1, True)   # tail corner fins
light_bar(0.80, 0.95, -0.05, 0.22, -2.30, -2.10, 1, True)
light_bar(-0.44, 0.44, 0.00, 0.045, 2.36, 2.41, 2, False)     # front LED blade
light_bar(-0.80, -0.50, 0.05, 0.09, 2.02, 2.20, 2, False)      # headlight fangs
light_bar(0.50, 0.80, 0.05, 0.09, 2.02, 2.20, 2, False)
light_bar(-0.70, -0.36, -0.33, -0.29, -1.70, -0.90, 3, True)   # thruster pads
light_bar(0.36, 0.70, -0.33, -0.29, -1.70, -0.90, 3, True)
print("swarm car tris", sum(len(np.asarray(i).reshape(-1)) for i in SW.i) // 3)

# ---------------------------------------------------------------- write
ci = M("coll_inst")
ci.v.append(np.asarray([(*b, 0, 0) for b in COLL], np.float32).reshape(-1, 8))
ci.i.append(np.zeros(3, np.uint32))
ci.n = len(COLL)
print("collision boxes", len(COLL))
# swarm traffic instances, precomputed (was a 150 ms loop at load: watchdog risk).
# Exact port of World.buildSwarm's Park-Miller RNG so traffic is unchanged.
si = M("swarm_inst")
_heights = [14, 24, 36, 47, 76, 88, 100, 116, 160, 178, 200, 230, 265, 300]
_lo, _hi = LO * P, HI * P
_len = _hi - _lo
_rs = 1.0
_sw = []
for _axis in range(2):
    for _li in range(LO, HI + 1):
        _line = _li * P
        for _hk in range(len(_heights)):
            for _side in (-1, 1):
                _rs = (_rs * 16807) % 2147483647
                _cnt = 4 + math.floor(_rs / 2147483647 * 8)
                _rs = (_rs * 16807) % 2147483647
                _off = _side * (3 + _rs / 2147483647 * 6)
                _rs = (_rs * 16807) % 2147483647
                _spd = 22 + _rs / 2147483647 * 26
                _rs = (_rs * 16807) % 2147483647
                _yy = _heights[_hk] + _rs / 2147483647 * 3
                for _q in range(_cnt):
                    if len(_sw) < 9000:
                        _cx = (_lo + _hi) / 2 if _axis == 0 else _line + _off
                        _cz = _line + _off if _axis == 0 else (_lo + _hi) / 2
                        _rs = (_rs * 16807) % 2147483647
                        _sv = _spd * (0.92 + _rs / 2147483647 * 0.16)
                        _rs = (_rs * 16807) % 2147483647
                        _rs = (_rs * 16807) % 2147483647
                        _jy = (_rs / 2147483647 - 0.5) * 9
                        _rs = (_rs * 16807) % 2147483647
                        _jl = (_rs / 2147483647 - 0.5) * 4
                        _sw.append((_cx + (_jl if _axis == 1 else 0), _yy + _jy, _cz + (_jl if _axis == 0 else 0),
                                    _sv, _axis, _side, _len, _rs / 2147483647))
si.v.append(np.asarray(_sw, np.float32).reshape(-1, 8))
si.i.append(np.zeros(3, np.uint32))
si.n = len(_sw)
print("swarm instances", len(_sw))
# holo blade signs projected from the facades over the sidewalks (own RNG)
HOLO = []
hrng = random.Random(5150)
for _axis in (0, 1):            # 0: street along x (line z = li*P), 1: street along z (line x = li*P)
    for _li in range(0, N + 1):
        _line = _li * P
        for _side in (-1, 1):
            _t = hrng.uniform(10, 70)
            while _t < N * P - 10:
                _m = _t % P
                if _m < RW + WALK + 8 or _m > P - (RW + WALK + 8):
                    _t += hrng.uniform(15, 30)
                    continue
                _w = hrng.uniform(3.0, 4.5)
                _lat = _line + _side * (10.8 - _w / 2)
                _hh = hrng.uniform(5, 12)
                _cy = hrng.uniform(18, 60) + _hh
                if _axis == 0:
                    HOLO.append((_t, _cy, _lat, _w / 2, 1.0, _hh, hrng.random(), float(hrng.randrange(4))))
                else:
                    HOLO.append((_lat, _cy, _t, _w / 2, 0.0, _hh, hrng.random(), float(hrng.randrange(4))))
                _t += hrng.uniform(70, 160)
ho = M("holo_inst")
ho.v.append(np.asarray(HOLO, np.float32).reshape(-1, 8))
ho.i.append(np.zeros(3, np.uint32))
ho.n = len(HOLO)
print("holo signs", len(HOLO))
# steam vents (rooftop stacks recorded in tower(), street vents along the route)
street_steam()
st = M("steam_inst")
st.v.append(np.asarray(STEAM, np.float32).reshape(-1, 8))
st.i.append(np.zeros(3, np.uint32))
st.n = len(STEAM)
print("steam vents", len(STEAM), "street", sum(1 for v in STEAM if v[5] > 0.5))
# keep every billboard clear: drop greebles in the volume in front of a screen
_G = np.asarray(GINST, np.float64).reshape(-1, 8)
_keep = np.ones(len(_G), bool)
for _b in billboards:
    _c = np.asarray(_b["c"], float)
    _nx, _nz = _b["n"]
    _rx, _rz = -_nz, _nx
    _d = _G[:, :3] - _c
    _along = _d[:, 0] * _nx + _d[:, 2] * _nz
    _lat = _d[:, 0] * _rx + _d[:, 2] * _rz
    _ha = np.abs(_G[:, 3] * _nx) + np.abs(_G[:, 5] * _nz)     # half... full size along the normal
    _hl = np.abs(_G[:, 3] * _rx) + np.abs(_G[:, 5] * _rz)
    _hit = ((_along + _ha / 2 > -3.5) & (_along - _ha / 2 < 10.0) & (np.abs(_lat) - _hl / 2 < _b["w"] / 2 + 1.5)
            & (np.abs(_d[:, 1]) - _G[:, 4] / 2 < _b["h"] / 2 + 1.5))
    _keep &= ~_hit
print("greebles cleared from billboards", int((~_keep).sum()), "screens rejected for clearance", BB_REJECT[0])
import collections as _co
print("why", _co.Counter(w[0] for w in BB_WHY))
GINST = [tuple(r) for r in _G[_keep]]
# audit: every placed screen (frame + light bar, front of the wall) vs every solid
_bad = 0
_GB = [(g[0] - g[3] / 2, g[1] - g[4] / 2, g[2] - g[5] / 2, g[0] + g[3] / 2, g[1] + g[4] / 2, g[2] + g[5] / 2) for g in GINST]
for _i, _b in enumerate(billboards):
    _v = bb_volume(_b["c"], _b["n"], _b["w"], _b["h"], back=0.9, front=0.4)
    _o = [bb_volume(b2["c"], b2["n"], b2["w"], b2["h"]) for j, b2 in enumerate(billboards) if j != _i]
    _C = _CAB_NP[0] if _CAB_NP[0] is not None else np.zeros((0, 6))
    _cab = len(_C) and np.any((_C[:, 0] < _v[3]) & (_v[0] < _C[:, 3]) & (_C[:, 1] < _v[4]) & (_v[1] < _C[:, 4]) & (_C[:, 2] < _v[5]) & (_v[2] < _C[:, 5]))
    if _hits(_v, COLL) or _hits(_v, BLADES) or _hits(_v, _GB) or _hits(_v, _o) or _cab:
        _bad += 1
print("AUDIT screens intersecting geometry:", _bad, "of", len(billboards))
gi = M("greeble_inst")
gi.v.append(np.asarray(GINST, np.float32).reshape(-1, 8))
gi.i.append(np.zeros(3, np.uint32))
gi.n = len(GINST)
boxm(M("gbox"), -0.5, 0.5, -0.5, 0.5, -0.5, 0.5, (0, 0), bottom=True)
# ---------------------------------------------------------------- title visor meshes (camera-centred, see world 4_sim)
# The inside of a 150 deg cylinder (r 4 m) around the camera, wearing the "Title FUI" artboard:
# a brow band (v 0..120/512) and a button band (v 160..400/512). Normals point at the axis.
TT_W, TT_H, TT_TOP, TT_BOT = 5120, 640, (0, 120), (160, 400)
VIS_R, VIS_SPAN = 4.0, math.radians(150)


def visor_band(mesh, v0, v1, height, segs=120):
    a0, a1 = -VIS_SPAN / 2, VIS_SPAN / 2
    for i in range(segs):
        t0, t1 = a0 + (a1 - a0) * i / segs, a0 + (a1 - a0) * (i + 1) / segs
        u0, u1 = i / segs, (i + 1) / segs
        vs = []
        for (t, u, y, v) in ((t0, u0, -height / 2, v1), (t1, u1, -height / 2, v1), (t1, u1, height / 2, v0), (t0, u0, height / 2, v0)):
            vs.append((VIS_R * math.sin(t), y, -VIS_R * math.cos(t), -math.sin(t), 0.0, math.cos(t), u, v))
        mesh.add(vs, [0, 2, 1, 0, 3, 2])


_pxm = TT_W / (VIS_R * VIS_SPAN)
visor_band(M("visor_top"), TT_TOP[0] / TT_H, TT_TOP[1] / TT_H, (TT_TOP[1] - TT_TOP[0]) / _pxm)
visor_band(M("visor_bot"), TT_BOT[0] / TT_H, TT_BOT[1] / TT_H, (TT_BOT[1] - TT_BOT[0]) / _pxm)
print("visor band heights", round((TT_TOP[1] - TT_TOP[0]) / _pxm, 3), round((TT_BOT[1] - TT_BOT[0]) / _pxm, 3))
write(os.path.join(ROOT, "assets", "city.bin"), list(meshes.values()),
      chunk=lambda n: None if n in ("swarmcar", "gbox", "greeble_inst", "coll_inst", "swarm_inst", "steam_inst", "holo_inst", "visor_top",
                                    "visor_bot") else (600 if n == "far" else 160))


def lua_num(v):
    return f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def f2(v):
    return f"{v:.2f}"


L = ["// GENERATED by tools/make_city.py - do not edit", ""]
L.append(f"export const P: f64 = {P};\nexport const RW: f64 = {RW};\nexport const WALK: f64 = {WALK};\nexport const N: i32 = {N};")
L.append(f"export const LO: i32 = {LO};\nexport const HI: i32 = {HI};\nexport const LANE: f64 = {LANE};")
L.append(f"export const routeN: i32 = {len(route)};")
L.append("export const route: StaticArray<f32> = [" + ",".join(f"{f2(x)},{f2(z)}" for x, z in route) + "];")
L.append("export class Street { s0: f64 = 0; s1: f64 = 0; name: string = \"\"; next: string = \"\"; turn: f64 = 0; }")
L.append("function st(s0: f64, s1: f64, name: string, next: string, turn: f64): Street {\n    let s = new Street();\n    s.s0 = s0; s.s1 = s1; s.name = name; s.next = next; s.turn = turn;\n    return s;\n}")
L.append("export const streets: Array<Street> = [")
L.append(",\n".join(f'    st({x["s0"]}, {x["s1"]}, "{x["name"]}", "{x["next"]}", {x["turn"]})' for x in route_segs))
L.append("];")
L.append("// billboards: cx, cy, cz, nx, nz, w, h, design")
L.append("export const bbN: i32 = " + str(len(billboards)) + ";")
L.append("export const bb: StaticArray<f32> = [" + ",".join(f"{f2(b['c'][0])},{f2(b['c'][1])},{f2(b['c'][2])},{b['n'][0]:.0f},{b['n'][1]:.0f},{f2(b['w'])},{f2(b['h'])},{b['design']}" for b in billboards) + "];")
if giant:
    L.append(f"export const giant: StaticArray<f32> = [{f2(giant['c'][0])}, {f2(giant['c'][1])}, {f2(giant['c'][2])}, {giant['n'][0]:.0f}, {giant['n'][1]:.0f}, {f2(giant['w'])}, {f2(giant['h'])}];")
open(os.path.join(ROOT, "cityinfo.as"), "w").write("\n".join(L) + "\n")

tris = {m.name: (sum(len(i) for i in m.i) // 3) for m in meshes.values()}
print("city meshes:", tris)
print("total tris", sum(tris.values()), "billboards", len(billboards), "route", len(route), "m", "skybridges", skybridge_count,
      "gates", len(gates), "giant", giant is not None)

print("greebles", GSTAT, "instances", len(GINST))
