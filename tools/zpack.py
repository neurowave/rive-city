"""Pack a blob as RZ01: independent 64 KB raw-deflate chunks, each with its Adler-32, (inflate.as decodes them under a
per-frame budget). Lossless; the inflated bytes are identical to the input.
usage: zpack.py in.bin out.rz"""
import struct, sys, zlib

CH = 1 << 16   # small chunks: each decodes in a few ms, so no frame trips the runtime's script watchdog


def zpack(data):
    parts = []
    for i in range(0, len(data), CH):
        raw = data[i:i + CH]
        c = zlib.compressobj(9, zlib.DEFLATED, -15, 9)
        comp = c.compress(raw) + c.flush()
        assert zlib.decompress(comp, -15) == raw
        parts.append(struct.pack("<III", len(raw), len(comp), zlib.adler32(raw) & 0xFFFFFFFF) + comp)
    return b"RZ01" + struct.pack("<II", len(data), len(parts)) + b"".join(parts)


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    d = open(src, "rb").read()
    z = zpack(d)
    open(dst, "wb").write(z)
    print(f"{src}: {len(d)} -> {dst}: {len(z)} ({len(z) / len(d):.1%})")
