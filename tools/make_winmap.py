#!/usr/bin/env python3
"""Window maps for the facade layers -> assets/win.bin (+ build/win_<layer>.png overlays).

The facade photos have no window data, so the shader used to guess "lit windows" from a coarse
grid masked by dark texels -- which lit stains, mullions and half windows, and faded out with the
mips. This finds the actual windows in each tile (art/tile_*.jpg, exactly what the shader samples
at mip 0) and stores, per texel:

  R  u inside the window rectangle (0..1, left -> right)
  G  v inside the window rectangle (0..1, top -> bottom)
  B  (window id 1..127) << 1 | glass bit      (0 = not a window)
  A  255

lit.wgsl uses it for stable per-window lights and interior mapping (rooms behind the glass).
Layers without windows (industrial, roof) get an empty map.

Blob layout (little endian): u32 count, u32 size, u32 mips(=1), count x (u32 off, u32 len), PNGs.
"""
import io
import os
import random
import struct

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SIZE = 1024
# layer name, tile metres (u, v) as exported to lit.wgsl TILE_U / TILE_V, detection params
LAYERS = [
    ("facade_res", (70.0, 70.0), dict(k=0.80, cap=0.30, close=2)),
    ("facade_office", (9.87, 13.46), dict(k=0.85, cap=0.36, grid=True, row=0.45, col=0.5)),
    ("facade_ind", (9.02, 13.54), None),
    ("facade_hk", (42.0, 42.0), dict(k=0.80, cap=0.30, close=2)),
    ("facade_lux", (34.55, 24.66), dict(k=0.85, cap=0.36, grid=True, row=0.62, col=0.45)),
    ("roof", (39.62, 39.62), None),
]
WIN_MIN = (0.45, 0.55)     # metres (w, h)
WIN_MAX = (6.5, 5.0)


def detect(a, tile, p):
    lum = a.mean(axis=2)
    local = ndimage.gaussian_filter(lum, 14, mode="wrap")
    dark = (lum < np.minimum(p["cap"], local * p["k"]))
    dark = ndimage.binary_opening(dark, np.ones((2, 2)))
    c = p["close"]
    merged = ndimage.binary_closing(dark, np.ones((c, c))) if c > 0 else dark
    lab, n = ndimage.label(merged)
    mu, mv = tile[0] / SIZE, tile[1] / SIZE
    wins = []
    for k, sl in enumerate(ndimage.find_objects(lab)):
        if sl is None:
            continue
        ys, xs = sl
        h, w = ys.stop - ys.start, xs.stop - xs.start
        wm, hm = w * mu, h * mv
        if not (WIN_MIN[0] <= wm <= WIN_MAX[0] and WIN_MIN[1] <= hm <= WIN_MAX[1]):
            continue
        fill = (lab[sl] == k + 1).mean()
        if fill < 0.35:
            continue
        wins.append((xs.start, ys.start, xs.stop, ys.stop))
    return dark, wins


def runs(mask, min_len):
    """contiguous True runs of a 1-D mask -> [(start, stop)]"""
    out, start = [], None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        elif not m and start is not None:
            if i - start >= min_len:
                out.append((start, i))
            start = None
    return out


def detect_grid(a, tile, p):
    """regular curtain walls / balconies: glass bands (floors) from the row profile, bays from the
    column profile inside each band, wide bays split into ~3.5 m rooms"""
    lum = ndimage.gaussian_filter(a.mean(axis=2), 1.5, mode="wrap")
    # two materials (glass vs concrete / white slabs): Otsu split of the luminance histogram
    hist, edges = np.histogram(lum, 128, (0, 1))
    w = hist.cumsum().astype(np.float64)
    m = (hist * edges[:-1]).cumsum()
    tot_w, tot_m = w[-1], m[-1]
    between = np.where((w > 0) & (w < tot_w), (tot_m * w / tot_w - m) ** 2 / (w * (tot_w - w) + 1e-9), 0)
    thr = edges[int(np.argmax(between))]
    dark = lum < thr
    print("   otsu", round(float(thr), 3), "dark share", round(float(dark.mean()), 2))
    mu, mv = tile[0] / SIZE, tile[1] / SIZE
    rowf = ndimage.uniform_filter1d(dark.mean(axis=1).astype(np.float32), 5, mode="wrap")
    wins = []
    for y0, y1 in runs(rowf > p["row"], int(0.8 / mv)):
        colf = ndimage.uniform_filter1d(dark[y0:y1].mean(axis=0).astype(np.float32), 3, mode="wrap")
        for x0, x1 in runs(colf > p["col"], int(0.6 / mu)):
            wm = (x1 - x0) * mu
            n = max(1, int(round(wm / 3.5)))
            for k in range(n):
                a0 = x0 + (x1 - x0) * k // n
                a1 = x0 + (x1 - x0) * (k + 1) // n
                wins.append((a0, y0, a1, y1))
    return dark, wins


def build(a, tile, p, rnd):
    out = np.zeros((SIZE, SIZE, 4), np.uint8)
    out[..., 3] = 255
    if p is None:
        return out, [], None
    dark, wins = detect_grid(a, tile, p) if p.get("grid") else detect(a, tile, p)
    if p.get("grid"):
        # curtain walls: the dark mask keeps the mullions as wall
        glass = ndimage.binary_dilation(dark, np.ones((2, 2)))
    else:
        # punched windows: the whole opening is glass (curtains / AC units must not cut the room)
        glass = np.zeros_like(dark)
        for (x0, y0, x1, y1) in wins:
            glass[y0 + 1:y1 - 1, x0 + 1:x1 - 1] = True
    for (x0, y0, x1, y1) in wins:
        wid = rnd.randint(1, 127)
        u = (np.arange(x0, x1) - x0 + 0.5) / (x1 - x0)
        v = (np.arange(y0, y1) - y0 + 0.5) / (y1 - y0)
        out[y0:y1, x0:x1, 0] = np.clip(u[None, :] * 255, 0, 255).astype(np.uint8)
        out[y0:y1, x0:x1, 1] = np.clip(v[:, None] * 255, 0, 255).astype(np.uint8)
        out[y0:y1, x0:x1, 2] = (wid << 1) | glass[y0:y1, x0:x1].astype(np.uint8)
    return out, wins, dark


MIPS = 8
LIT_SHARE = 0.4     # night share of lit rooms (the shader dims by day)


def lit_atlas(m, wins):
    """3 random lit-room assignments (R, G, B) of the real window glass, with a box-filtered mip
    chain in the facade atlas layout (mip0 left, smaller mips stacked on the right): far
    towers sample the averaged windows instead of flat cells, near ones the exact mask"""
    lit = np.zeros((SIZE, SIZE, 3), np.float32)
    glass = (m[..., 2] & 1).astype(np.float32)
    for ch in range(3):
        r = random.Random(1000 + ch)
        for (x0, y0, x1, y1) in wins:
            if r.random() < LIT_SHARE:
                lit[y0:y1, x0:x1, ch] = glass[y0:y1, x0:x1]
    out = Image.new("RGB", (SIZE + SIZE // 2, SIZE))
    cur = lit
    out.paste(Image.fromarray((cur * 255 + 0.5).astype(np.uint8)), (0, 0))
    y = 0
    for k in range(1, MIPS):
        s_ = SIZE >> k
        cur = cur.reshape(s_, 2, s_, 2, 3).mean(axis=(1, 3))
        out.paste(Image.fromarray((cur * 255 + 0.5).astype(np.uint8)), (SIZE, y))
        y += s_
    b = io.BytesIO()
    out.save(b, "PNG", optimize=True)
    return b.getvalue()


def main():
    rnd = random.Random(31337)
    pngs = []
    lits = []
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    for name, tile, p in LAYERS:
        path = os.path.join(ROOT, "art", f"tile_{name}.jpg")
        a = np.asarray(Image.open(path).convert("RGB").resize((SIZE, SIZE))).astype(np.float32) / 255.0
        m, wins, dark = build(a, tile, p, rnd)
        lits.append(lit_atlas(m, wins))
        b = io.BytesIO()
        Image.fromarray(m).save(b, "PNG", optimize=True)
        pngs.append(b.getvalue())
        if wins:
            ws = np.array([(x1 - x0) * tile[0] / SIZE for x0, y0, x1, y1 in wins])
            hs = np.array([(y1 - y0) * tile[1] / SIZE for x0, y0, x1, y1 in wins])
            cov = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in wins) / SIZE ** 2
            print(f"{name:14s} windows {len(wins):4d}  median {np.median(ws):.2f} x {np.median(hs):.2f} m  cover {cov:.2f}"
                  f"  png {len(pngs[-1]) // 1024} KB")
            ov = Image.fromarray((a * 255).astype(np.uint8)).convert("RGB")
            d = ImageDraw.Draw(ov)
            for (x0, y0, x1, y1) in wins:
                d.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(255, 40, 160))
            ov.resize((768, 768)).save(os.path.join(ROOT, "build", f"win_{name}.png"))
        else:
            print(f"{name:14s} no windows  png {len(pngs[-1]) // 1024} KB")
    # container: window maps (mip 0) then lit-mask atlases (full mip chain)
    pngs = pngs + lits
    head = struct.pack("<III", len(pngs), SIZE, 1)
    off = len(head) + 8 * len(pngs)
    idx = b""
    for p_ in pngs:
        idx += struct.pack("<II", off, len(p_))
        off += len(p_)
    data = head + idx + b"".join(pngs)
    open(os.path.join(ROOT, "assets", "win.bin"), "wb").write(data)
    print("win.bin", len(data))


if __name__ == "__main__":
    main()
