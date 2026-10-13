#!/usr/bin/env python3
"""Generated facade/roof photos -> tileable albedo + normal/AO texture arrays.

Each layer ships as a JPEG mip-chain atlas (1536x1024: mip0 left, smaller mips
stacked on the right) so the runtime decodes 2 x LAYERS images and uploads every
mip with row copies; no mip generation in script.

Blob layout (little endian):
  u32 count, u32 size(=1024), u32 mips
  count x (u32 offset, u32 length)
  JPEG bytes...   order: albedo layers then normal layers
"""
import io
import os
import struct

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "art", "src")
SIZE = 1024
MIPS = 8          # 1024 .. 8
# name, crop margin (fraction), tile metres (u), tile metres (v)  -> exported to texinfo.as
# name, crop margin, metres per source pixel (estimated from floor counts), periodic grid?
LAYERS = [
    ("facade_res", 0.0, 70 / 1024, False),
    ("facade_office", 0.0, 15 / 1024, True),
    ("facade_ind", 0.0, 18 / 1024, True),
    ("facade_hk", 0.0, 42 / 1024, False),
    ("facade_lux", 0.06, 40 / 902, True),
    ("roof", 0.05, 44 / 1024, False),
]
TILE = []


def best_period(a, axis):
    """Largest-overlap lag L where slice L matches slice 0 (regular facade grids)."""
    n = a.shape[axis]
    lum = a.mean(axis=2)
    if axis == 0:
        lum = lum.T
    best, bl = 1e9, n
    for L in range(int(n * 0.5), n - 8):
        d = np.abs(lum[:, 0:8] - lum[:, L:L + 8]).mean()
        if d < best:
            best, bl = d, L
    return bl


def load(name, margin, periodic):
    im = Image.open(os.path.join(SRC, name + ".png")).convert("RGB")
    w, h = im.size
    mx, my = int(w * margin), int(h * margin)
    im = im.crop((mx, my, w - mx, h - my))
    if periodic:
        a = np.asarray(im).astype(np.float32) / 255.0
        lx, ly = best_period(a, 1), best_period(a, 0)
        print("  period crop", name, lx, ly, "of", a.shape[1], a.shape[0])
        im = im.crop((0, 0, lx, ly))
    return im


def to_arr(im):
    im = im.resize((SIZE, SIZE), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0


def seamless(a, band=0.14):
    s = np.roll(np.roll(a, SIZE // 2, 0), SIZE // 2, 1)
    x = np.linspace(0, 1, SIZE, endpoint=False) + 0.5 / SIZE
    e = np.minimum(x, 1 - x) / band
    w = np.clip(e, 0, 1)
    w = w * w * (3 - 2 * w)
    m = (w[None, :] * w[:, None])[..., None]
    return a * m + s * (1 - m)


def flatten_light(a):
    """Remove the large-scale lighting gradient the generator baked in."""
    lum = a.mean(axis=2)
    im = Image.fromarray((lum * 255).astype(np.uint8))
    low = np.asarray(im.filter(ImageFilter.GaussianBlur(SIZE / 6))).astype(np.float32) / 255.0
    k = (lum.mean() + 1e-3) / (low + 1e-3)
    k = np.clip(k, 0.6, 1.6)[..., None]
    return np.clip(a * (0.35 + 0.65 * k), 0, 1)


def normal_ao(a, strength=3.0):
    lum = a.mean(axis=2)
    # tileable gradients
    gx = (np.roll(lum, -1, 1) - np.roll(lum, 1, 1)) * 0.5
    gy = (np.roll(lum, -1, 0) - np.roll(lum, 1, 0)) * 0.5
    # medium-scale height for a bit of relief
    im = Image.fromarray((lum * 255).astype(np.uint8))
    med = np.asarray(im.filter(ImageFilter.GaussianBlur(3))).astype(np.float32) / 255.0
    gx2 = (np.roll(med, -2, 1) - np.roll(med, 2, 1)) * 0.25
    gy2 = (np.roll(med, -2, 0) - np.roll(med, 2, 0)) * 0.25
    nx = -(gx + gx2 * 2) * strength
    ny = (gy + gy2 * 2) * strength       # +v down in image -> flip so +y is up on the wall
    nz = np.ones_like(nx)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny = nx / l, ny / l
    # cavity AO: darker than the local average = recessed
    big = np.asarray(im.filter(ImageFilter.GaussianBlur(10))).astype(np.float32) / 255.0
    ao = np.clip(1.0 - np.maximum(big - lum, 0) * 3.0, 0.25, 1.0)
    return np.stack([nx * 0.5 + 0.5, ny * 0.5 + 0.5, ao], axis=2)


def atlas(a):
    out = Image.new("RGB", (SIZE + SIZE // 2, SIZE))
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    out.paste(im, (0, 0))
    y = 0
    cur = im
    for m in range(1, MIPS):
        s = SIZE >> m
        cur = cur.resize((s, s), Image.BOX) if m == 1 else cur.resize((s, s), Image.BOX)
        out.paste(cur, (SIZE, y))
        y += s
    return out


def jpeg(im, q=86):
    b = io.BytesIO()
    im.save(b, "JPEG", quality=q, subsampling=0 if q > 90 else 2)
    return b.getvalue()


def main():
    albs, nrms = [], []
    for name, margin, mpp, periodic in LAYERS:
        im = load(name, margin, periodic)
        TILE.append((im.size[0] * mpp, im.size[1] * mpp))
        a = to_arr(im)
        a = flatten_light(a)
        a = seamless(a, 0.04 if periodic else 0.14)
        albs.append(jpeg(atlas(a), 86))
        nrms.append(jpeg(atlas(normal_ao(a)), 90))
        Image.fromarray((a * 255).astype(np.uint8)).save(os.path.join(ROOT, "art", f"tile_{name}.jpg"), quality=85)
        print(name, len(albs[-1]), len(nrms[-1]))
    parts = albs + nrms
    head = struct.pack("<III", len(parts), SIZE, MIPS)
    off = len(head) + 8 * len(parts)
    idx = b""
    for p in parts:
        idx += struct.pack("<II", off, len(p))
        off += len(p)
    data = head + idx + b"".join(parts)
    open(os.path.join(ROOT, "assets", "tex.bin"), "wb").write(data)
    with open(os.path.join(ROOT, "texinfo.as"), "w") as f:
        f.write("// generated by tools/make_tex.py\n")
        f.write(f"export const layers: i32 = {len(LAYERS)};\nexport const size: i32 = {SIZE};\nexport const mips: i32 = {MIPS};\n")
    print("tex.bin", len(data))


if __name__ == "__main__":
    main()
