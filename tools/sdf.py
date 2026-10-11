"""Tiny vectorised SDF modelling kit (numpy) + marching-cubes extraction.

Points are (N, 3) float arrays. Every primitive returns (N,) distances.
Parts are meshed with skimage's marching cubes; normals come from the SDF
gradient (smooth shading), per-face materials from a callback, and per-vertex
ambient occlusion is baked against a scene SDF.
"""
import math
import numpy as np
from skimage.measure import marching_cubes


def V(*a):
    return np.array(a, dtype=np.float64)


def length(v):
    return np.sqrt((v * v).sum(-1))


# ---------------------------------------------------------------- primitives
def round_box(p, c, b, r):
    q = np.abs(p - np.asarray(c)) - (np.asarray(b) - r)
    return length(np.maximum(q, 0.0)) + np.minimum(q.max(-1), 0.0) - r


def box_local(q, b, r):
    q = np.abs(q) - (np.asarray(b) - r)
    return length(np.maximum(q, 0.0)) + np.minimum(q.max(-1), 0.0) - r


def ellipsoid(p, c, r):
    r = np.asarray(r, float)
    q = (p - np.asarray(c)) / r
    k0 = length(q)
    k1 = length(q / r)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def sphere(p, c, r):
    return length(p - np.asarray(c)) - r


def capsule(p, a, b, ra, rb=None):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    rb = ra if rb is None else rb
    pa = p - a
    ba = b - a
    h = np.clip((pa @ ba) / max(ba @ ba, 1e-12), 0.0, 1.0)
    return length(pa - h[:, None] * ba) - (ra + (rb - ra) * h)


def chain(p, pts, r, k=0.0):
    """capsules through a polyline; r scalar or per-point list"""
    rs = r if isinstance(r, (list, tuple, np.ndarray)) else [r] * len(pts)
    d = None
    for i in range(len(pts) - 1):
        di = capsule(p, pts[i], pts[i + 1], rs[i], rs[i + 1])
        d = di if d is None else (smin(d, di, k) if k > 0 else np.minimum(d, di))
    return d


def cyl(p, c, axis, r, h, rr=0.0):
    """capped cylinder along axis (0,1,2), half height h, edge rounding rr"""
    q = p - np.asarray(c)
    ax = q[:, axis]
    rad = np.sqrt((q * q).sum(-1) - ax * ax)
    dx = rad - (r - rr)
    dy = np.abs(ax) - (h - rr)
    return np.minimum(np.maximum(dx, dy), 0.0) + np.sqrt(np.maximum(dx, 0) ** 2 + np.maximum(dy, 0) ** 2) - rr


def torus(p, c, axis, R, r):
    q = p - np.asarray(c)
    ax = q[:, axis]
    rad = np.sqrt(np.maximum((q * q).sum(-1) - ax * ax, 0.0))
    return np.sqrt((rad - R) ** 2 + ax * ax) - r


def poly2(px, py, poly):
    """exact signed distance to a closed 2D polygon (list of (x, y))"""
    P = np.asarray(poly, float)
    n = len(P)
    d = np.full(px.shape, np.inf)
    s = np.ones(px.shape)
    for i in range(n):
        j = (i - 1) % n
        e = P[j] - P[i]
        wx = px - P[i, 0]
        wy = py - P[i, 1]
        t = np.clip((wx * e[0] + wy * e[1]) / (e @ e), 0.0, 1.0)
        bx = wx - e[0] * t
        by = wy - e[1] * t
        d = np.minimum(d, bx * bx + by * by)
        c1 = py >= P[i, 1]
        c2 = py < P[j, 1]
        c3 = e[0] * wy > e[1] * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return s * np.sqrt(d)


# ---------------------------------------------------------------- operators
def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def rot_x(p, c, ang):
    """points into a frame rotated by ang about x through c"""
    q = p - np.asarray(c)
    ca, sa = math.cos(ang), math.sin(ang)
    return np.stack([q[:, 0], ca * q[:, 1] + sa * q[:, 2], -sa * q[:, 1] + ca * q[:, 2]], -1)


def mirror_x(p):
    q = p.copy()
    q[:, 0] = np.abs(q[:, 0])
    return q


# ---------------------------------------------------------------- extraction
def grad(fn, pts, eps):
    out = np.zeros_like(pts)
    for a in range(3):
        o = np.zeros(3)
        o[a] = eps
        out[:, a] = fn(pts + o) - fn(pts - o)
    n = length(out)
    return out / np.maximum(n, 1e-12)[:, None]


def evaluate(fn, lo, hi, step):
    lo = np.asarray(lo, float)
    hi = np.asarray(hi, float)
    nx, ny, nz = [int(math.ceil((hi[a] - lo[a]) / step)) + 1 for a in range(3)]
    xs = lo[0] + np.arange(nx) * step
    ys = lo[1] + np.arange(ny) * step
    zs = lo[2] + np.arange(nz) * step
    vol = np.empty((nx, ny, nz), np.float32)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    for k, z in enumerate(zs):
        pts = np.stack([X.ravel(), Y.ravel(), np.full(X.size, z)], -1)
        vol[:, :, k] = fn(pts).reshape(nx, ny)
    return vol


def decimate(v, f, target):
    import pyfqmr
    if target is None or len(f) <= target:
        return v, f
    s = pyfqmr.Simplify()
    s.setMesh(v.astype(np.float64), f.astype(np.int32))
    s.simplify_mesh(target_count=int(target), aggressiveness=7, max_iterations=400, preserve_border=True, verbose=False)
    v2, f2, _ = s.getMesh()
    return np.asarray(v2, float), np.asarray(f2, np.int64)


def mesh_part(fn, lo, hi, step, keep=None, target=None, raw=False):
    """-> verts (N,3), normals (N,3), faces (M,3); raw=True skips decimation"""
    vol = evaluate(fn, lo, hi, step)
    # close the volume so every surface is watertight at the box edge
    vol[0, :, :] = vol[-1, :, :] = np.maximum(vol[0, :, :], step)
    vol[:, 0, :] = vol[:, -1, :] = np.maximum(vol[:, 0, :], step)
    vol[:, :, 0] = vol[:, :, -1] = np.maximum(vol[:, :, 0], step)
    if vol.min() >= 0 or vol.max() <= 0:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    v, f, _, _ = marching_cubes(vol, 0.0, spacing=(step, step, step), allow_degenerate=False)
    v = v + np.asarray(lo, float)
    if keep is not None:
        cen = v[f].mean(1)
        f = f[keep(cen)]
        used, inv = np.unique(f.ravel(), return_inverse=True)
        v = v[used]
        f = inv.reshape(-1, 3)
    if raw:
        return v, None, f
    v, f = decimate(v, f, target)
    # pull decimated vertices back onto the surface, then SDF normals
    for _ in range(2):
        g = grad(fn, v, step * 0.5)
        v = v - g * fn(v)[:, None]
    n = grad(fn, v, step * 0.5)
    return v, n, f


def split_decimate(fn, v, f, names, target, step):
    """decimate each material group on its own (borders kept), reproject,
    SDF normals -> list of (name, v, n, f)"""
    out = []
    total = max(len(f), 1)
    for name in np.unique(names):
        sel = f[names == name]
        used, inv = np.unique(sel.ravel(), return_inverse=True)
        gv = v[used]
        gf = inv.reshape(-1, 3)
        if target is not None:
            gv, gf = decimate(gv, gf, max(64, int(target * len(sel) / total)))
        for _ in range(2):
            g = grad(fn, gv, step * 0.5)
            gv = gv - g * fn(gv)[:, None]
        gn = grad(fn, gv, step * 0.5)
        out.append((name, gv, gn, gf))
    return out


def bake_ao(scene, v, n, scale, k=1.0):
    """SDF ambient occlusion: 5 taps along the normal"""
    occ = np.zeros(len(v))
    w = 1.0
    for i in range(1, 6):
        h = scale * i / 5.0
        d = scene(v + n * h)
        occ += (h - np.minimum(d, h)) * w
        w *= 0.6
    return np.clip(1.0 - k * occ / (scale * 0.9), 0.0, 1.0)


def march(fn, o, d, tmax=5.0):
    """sphere trace single rays (arrays of origins, one dir)"""
    o = np.asarray(o, float)
    d = np.asarray(d, float)
    t = np.zeros(len(o))
    for _ in range(160):
        dd = fn(o + d * t[:, None])
        t += np.maximum(dd, 1e-4) * 0.9
        if (np.abs(dd) < 2e-4).all() or (t > tmax).all():
            break
    return o + d * t[:, None]


def slice_plane(v, f, axis, val):
    """Split every triangle crossing the plane v[axis] == val, so per-face
    material classification against that plane gets a straight border instead
    of a marching-cubes sawtooth. Shared edges get one shared new vertex."""
    d = v[:, axis] - val
    s = d[f] > 0
    cnt = s.sum(1)
    cross = (cnt == 1) | (cnt == 2)
    if not cross.any():
        return v, f
    keep = f[~cross]
    fc = f[cross]
    sc = s[cross]
    lone_mask = np.where((cnt[cross] == 1)[:, None], sc, ~sc)
    li = np.argmax(lone_mask, 1)
    r = np.arange(len(fc))
    a = fc[r, li]
    b = fc[r, (li + 1) % 3]
    c = fc[r, (li + 2) % 3]
    # unique new vertices per undirected edge
    e = np.concatenate([np.stack([a, b], 1), np.stack([a, c], 1)])
    ek = np.sort(e, 1)
    uk, inv = np.unique(ek, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    da, db = d[uk[:, 0]], d[uk[:, 1]]
    t = (da / np.where(np.abs(da - db) < 1e-12, 1e-12, da - db))[:, None]
    nv = v[uk[:, 0]] + (v[uk[:, 1]] - v[uk[:, 0]]) * t
    base = len(v)
    pab = base + inv[: len(fc)]
    pac = base + inv[len(fc):]
    t1 = np.stack([a, pab, pac], 1)
    t2 = np.stack([pab, b, c], 1)
    t3 = np.stack([pab, c, pac], 1)
    return np.concatenate([v, nv]), np.concatenate([keep, t1, t2, t3])


def slice_planes(v, f, planes):
    for axis, val in planes:
        v, f = slice_plane(v, f, axis, val)
    # drop slivers (zero-area) created when vertices sit on a plane
    p = v[f]
    area = np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
    return v, f[area > 1e-12]
