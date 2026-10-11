"""Tiny mesh-pack writer shared by make_city.py and make_props.py.

Format (little endian), read by pack.as:
    "RMP1"  u32 meshCount
    per mesh:  32-byte ascii name, u32 vcount, u32 icount,
               6 x f32 bounds (min xyz, max xyz),
               vcount * 32 bytes (pos.xyz, normal.xyz, uv.xy  float32),
               icount * 4 bytes (u32 indices)
Vertices are already in the layout the GPU pipeline uses, so the loader only
slices the blob — no per-vertex parsing in script (the city is ~200k vertices).
"""
import struct
import numpy as np


class Mesh:
    def __init__(self, name):
        self.name = name
        self.v = []   # list of np arrays (n, 8)
        self.i = []   # list of np arrays (m,) uint32
        self.n = 0

    def add(self, verts, idx):
        verts = np.asarray(verts, dtype=np.float32).reshape(-1, 8)
        idx = np.asarray(idx, dtype=np.uint32).reshape(-1)
        if len(verts) == 0 or len(idx) == 0:
            return
        self.v.append(verts)
        self.i.append(idx + self.n)
        self.n += len(verts)

    def arrays(self):
        if not self.v:
            return np.zeros((0, 8), np.float32), np.zeros((0,), np.uint32)
        return np.concatenate(self.v), np.concatenate(self.i)


def fix_winding(verts, idx):
    """Make every triangle counter-clockwise when seen from the side its vertex
    normals point to (front face = outside)."""
    v = np.asarray(verts, np.float32).reshape(-1, 8)
    t = np.asarray(idx, np.uint32).reshape(-1, 3).copy()
    a, b, c = v[t[:, 0], :3], v[t[:, 1], :3], v[t[:, 2], :3]
    fn = np.cross(b - a, c - a)
    vn = v[t[:, 0], 3:6] + v[t[:, 1], 3:6] + v[t[:, 2], 3:6]
    flip = (fn * vn).sum(1) < 0
    t[flip] = t[flip][:, [0, 2, 1]]
    return v, t.reshape(-1)


def chunk_order(v, i, cell):
    """sort triangles into square xz cells (row-major) -> (idx, chunks)"""
    t = i.reshape(-1, 3)
    cen = v[t, :3].mean(1)
    cx = np.floor(cen[:, 0] / cell).astype(np.int64)
    cz = np.floor(cen[:, 2] / cell).astype(np.int64)
    key = (cz - cz.min()) * 100000 + (cx - cx.min())
    order = np.argsort(key, kind="stable")
    t = t[order]
    key = key[order]
    chunks = []
    starts = np.r_[0, np.nonzero(np.diff(key))[0] + 1, len(key)]
    for a, b in zip(starts[:-1], starts[1:]):
        pts = v[t[a:b].ravel(), :3]
        mn, mx = pts.min(0), pts.max(0)
        mn[1] = min(mn[1], -6.0)          # the city rise starts below the street
        chunks.append((a * 3, (b - a) * 3, *mn, *mx))
    return t.reshape(-1), chunks


def write(path, meshes, chunk=None):
    """chunk: name -> cell size in metres (or None) for frustum-culled meshes"""
    out = bytearray(b"RMP2")
    live = [m for m in meshes if m.n > 0]
    out += struct.pack("<I", len(live))
    nch = 0
    for m in live:
        v, i = m.arrays()
        if not m.name.endswith("_inst"):
            v, i = fix_winding(v, i)
        cell = chunk(m.name) if chunk and not m.name.endswith("_inst") else None
        chunks = []
        if cell:
            i, chunks = chunk_order(v, i, cell)
        name = m.name.encode()[:31].ljust(32, b"\0")
        mn, mx = v[:, :3].min(0), v[:, :3].max(0)
        out += name + struct.pack("<II6f", len(v), len(i), *mn, *mx)
        out += v.astype("<f4").tobytes()
        out += i.astype("<u4").tobytes()
        out += struct.pack("<I", len(chunks))
        for c in chunks:
            out += struct.pack("<II6f", *c)
        nch += len(chunks)
    with open(path, "wb") as f:
        f.write(out)
    tot_v = sum(m.n for m in live)
    tot_i = sum(len(m.arrays()[1]) for m in live)
    print(f"{path}: {len(live)} meshes, {tot_v} verts, {tot_i // 3} tris, {nch} chunks, {len(out) / 1e6:.2f} MB")
