// Lossless blob compression: a raw DEFLATE (RFC 1951) decoder plus the chunked "RZ01" container
// written by tools/zpack.py. The inflated bytes are identical to the original blob, so the mesh
// pack loader (pack.as) is unchanged. Chunks are independent (~1 MB raw each) so the load can
// inflate a few per frame under a time budget instead of one long call.
//
//   RZ01 | rawTotal u32 | nChunks u32 | { rawLen u32 | compLen u32 | adler32 u32 | deflate bytes } * nChunks
// Every chunk's Adler-32 is checked after inflating, so a decoder bug can never pass silently.
import { clock } from "rive/os";
import { Buffer } from "rive/buffer";

const LBASE: StaticArray<i32> = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258];
const LEXT: StaticArray<i32> = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0];
const DBASE: StaticArray<i32> = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097,
    6145, 8193, 12289, 16385, 24577];
const DEXT: StaticArray<i32> = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13];
const CLORDER: StaticArray<i32> = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];

// canonical Huffman table (puff.c layout): code counts per length + symbols in code order
const FB: i32 = 10;          // fast-table bits
const FMASK: u32 = 1023;

class Huff {
    counts: Int32Array = new Int32Array(16);
    symbols: Int32Array = new Int32Array(320);
    offs: Int32Array = new Int32Array(16);
    next: Int32Array = new Int32Array(16);
    // fast[bits & 1023] = (symbol << 4) | codeLength for codes up to FB bits, 0 = use the slow path
    fast: Int32Array = new Int32Array(1024);
}

function buildHuff(h: Huff, lengths: Int32Array, off: i32, n: i32): void {
    for (let i = 0; i < 16; i++) {
        h.counts[i] = 0;
    }
    for (let i = 0; i < n; i++) {
        let l = lengths[off + i];
        h.counts[l] = h.counts[l] + 1;
    }
    h.counts[0] = 0;
    let s: i32 = 0;
    for (let i = 0; i < 16; i++) {
        h.offs[i] = s;
        s += h.counts[i];
    }
    for (let i = 0; i < n; i++) {
        let l = lengths[off + i];
        if (l != 0) {
            h.symbols[h.offs[l]] = i;
            h.offs[l] = h.offs[l] + 1;
        }
    }
    // canonical codes -> bit-reversed (deflate reads LSB first) fast lookup entries
    h.fast.fill(0);
    let code: i32 = 0;
    for (let b = 1; b < 16; b++) {
        code = (code + h.counts[b - 1]) << 1;
        h.next[b] = code;
    }
    for (let i = 0; i < n; i++) {
        let l = lengths[off + i];
        if (l == 0 || l > FB) {
            continue;
        }
        let c = h.next[l];
        h.next[l] = c + 1;
        let rev: i32 = 0;
        for (let k = 0; k < l; k++) {
            rev = (rev << 1) | ((c >> k) & 1);
        }
        let entry = (i << 4) | l;
        for (let j = rev; j < 1024; j += 1 << l) {
            h.fast[j] = entry;
        }
    }
}

class Bits {
    src: Uint8Array = new Uint8Array(0);
    pos: i32 = 0;
    end: i32 = 0;
    bb: u32 = 0;
    bc: i32 = 0;
}

function need(r: Bits, n: i32): void {
    while (r.bc < n) {
        let byte: u32 = r.pos < r.end ? <u32>r.src[r.pos] : 0;
        r.pos++;
        r.bb |= byte << <u32>r.bc;
        r.bc += 8;
    }
}

function bits(r: Bits, n: i32): i32 {
    if (n == 0) {
        return 0;
    }
    need(r, n);
    let v = <i32>(r.bb & ((<u32>1 << <u32>n) - 1));
    r.bb = r.bb >>> <u32>n;
    r.bc -= n;
    return v;
}

function decodeSym(r: Bits, h: Huff): i32 {
    let code: i32 = 0;
    let first: i32 = 0;
    let index: i32 = 0;
    for (let len = 1; len < 16; len++) {
        code |= bits(r, 1);
        let count = h.counts[len];
        if (code - count < first) {
            return h.symbols[index + (code - first)];
        }
        index += count;
        first += count;
        first <<= 1;
        code <<= 1;
    }
    return -1;
}

// shared scratch tables (decoding is single-threaded)
const LEN_H = new Huff();
const DIST_H = new Huff();
const FIX_L = new Huff();
const FIX_D = new Huff();
const LENS = new Int32Array(320);
let fixedReady = false;

function buildFixed(): void {
    let l = new Int32Array(320);
    for (let i = 0; i < 144; i++) {
        l[i] = 8;
    }
    for (let i = 144; i < 256; i++) {
        l[i] = 9;
    }
    for (let i = 256; i < 280; i++) {
        l[i] = 7;
    }
    for (let i = 280; i < 288; i++) {
        l[i] = 8;
    }
    buildHuff(FIX_L, l, 0, 288);
    for (let i = 0; i < 30; i++) {
        l[i] = 5;
    }
    buildHuff(FIX_D, l, 0, 30);
    fixedReady = true;
}

// inflate one raw-deflate stream src[start, end) into out[o0, o0 + len); true when it decodes exactly len bytes
export function inflateRaw(src: Uint8Array, start: i32, end: i32, out: Uint8Array, o0: i32, len: i32): bool {
    if (!fixedReady) {
        buildFixed();
    }
    let r = new Bits();
    r.src = src;
    r.pos = start;
    r.end = end;
    let o = o0;
    let oe = o0 + len;
    let last = 0;
    while (last == 0) {
        last = bits(r, 1);
        let type = bits(r, 2);
        if (type == 0) {
            // stored block: drop to a byte boundary, LEN/NLEN, then raw bytes
            let drop = r.bc & 7;
            r.bb = r.bb >>> <u32>drop;
            r.bc -= drop;
            let n = bits(r, 16);
            let nn = bits(r, 16);
            if ((n ^ 0xFFFF) != nn || o + n > oe) {
                return false;
            }
            while (n > 0 && r.bc > 0) {
                out[o++] = <u8>bits(r, 8);
                n--;
            }
            if (r.pos + n > r.end) {
                return false;
            }
            for (let i = 0; i < n; i++) {
                out[o + i] = r.src[r.pos + i];
            }
            o += n;
            r.pos += n;
            continue;
        }
        let lh: Huff;
        let dh: Huff;
        if (type == 1) {
            lh = FIX_L;
            dh = FIX_D;
        } else if (type == 2) {
            let hlit = bits(r, 5) + 257;
            let hdist = bits(r, 5) + 1;
            let hclen = bits(r, 4) + 4;
            for (let i = 0; i < 19; i++) {
                LENS[i] = 0;
            }
            for (let i = 0; i < hclen; i++) {
                LENS[CLORDER[i]] = bits(r, 3);
            }
            buildHuff(LEN_H, LENS, 0, 19);
            let idx = 0;
            while (idx < hlit + hdist) {
                let sym = decodeSym(r, LEN_H);
                if (sym < 0) {
                    return false;
                }
                if (sym < 16) {
                    LENS[idx++] = sym;
                } else {
                    let v = 0;
                    let rep = 0;
                    if (sym == 16) {
                        if (idx == 0) {
                            return false;
                        }
                        v = LENS[idx - 1];
                        rep = 3 + bits(r, 2);
                    } else if (sym == 17) {
                        rep = 3 + bits(r, 3);
                    } else {
                        rep = 11 + bits(r, 7);
                    }
                    if (idx + rep > hlit + hdist) {
                        return false;
                    }
                    for (let k = 0; k < rep; k++) {
                        LENS[idx++] = v;
                    }
                }
            }
            buildHuff(DIST_H, LENS, hlit, hdist);
            buildHuff(LEN_H, LENS, 0, hlit);
            lh = LEN_H;
            dh = DIST_H;
        } else {
            return false;
        }
        // hot loop: bit buffer in locals, 10-bit table decode, slow canonical walk for longer codes
        let bb = r.bb;
        let bc = r.bc;
        let pos = r.pos;
        let src = r.src;
        let send = r.end;
        let lf = lh.fast;
        let df = dh.fast;
        let ok = true;
        while (true) {
            while (bc < 24) {
                bb |= (pos < send ? <u32>src[pos] : 0) << <u32>bc;
                pos++;
                bc += 8;
            }
            let sym: i32;
            let e = lf[<i32>(bb & FMASK)];
            if (e != 0) {
                let l = e & 15;
                sym = e >> 4;
                bb = bb >>> <u32>l;
                bc -= l;
            } else {
                sym = -1;
                let code: i32 = 0;
                let first: i32 = 0;
                let index: i32 = 0;
                for (let len = 1; len < 16; len++) {
                    code |= <i32>(bb & 1);
                    bb = bb >>> 1;
                    bc--;
                    let count = lh.counts[len];
                    if (code - count < first) {
                        sym = lh.symbols[index + (code - first)];
                        break;
                    }
                    index += count;
                    first += count;
                    first <<= 1;
                    code <<= 1;
                }
                if (sym < 0) {
                    ok = false;
                    break;
                }
            }
            if (sym < 256) {
                if (o >= oe) {
                    ok = false;
                    break;
                }
                unchecked(out[o] = <u8>sym);
                o++;
                continue;
            }
            if (sym == 256) {
                break;
            }
            sym -= 257;
            if (sym >= 29) {
                ok = false;
                break;
            }
            let xb = LEXT[sym];
            let n = LBASE[sym] + <i32>(bb & ((<u32>1 << <u32>xb) - 1));
            bb = bb >>> <u32>xb;
            bc -= xb;
            while (bc < 24) {
                bb |= (pos < send ? <u32>src[pos] : 0) << <u32>bc;
                pos++;
                bc += 8;
            }
            let ds: i32;
            let de = df[<i32>(bb & FMASK)];
            if (de != 0) {
                let l = de & 15;
                ds = de >> 4;
                bb = bb >>> <u32>l;
                bc -= l;
            } else {
                ds = -1;
                let code: i32 = 0;
                let first: i32 = 0;
                let index: i32 = 0;
                for (let len = 1; len < 16; len++) {
                    code |= <i32>(bb & 1);
                    bb = bb >>> 1;
                    bc--;
                    let count = dh.counts[len];
                    if (code - count < first) {
                        ds = dh.symbols[index + (code - first)];
                        break;
                    }
                    index += count;
                    first += count;
                    first <<= 1;
                    code <<= 1;
                }
            }
            if (ds < 0 || ds >= 30) {
                ok = false;
                break;
            }
            if (bc < 13) {
                while (bc < 24) {
                    bb |= (pos < send ? <u32>src[pos] : 0) << <u32>bc;
                    pos++;
                    bc += 8;
                }
            }
            let dx = DEXT[ds];
            let dist = DBASE[ds] + <i32>(bb & ((<u32>1 << <u32>dx) - 1));
            bb = bb >>> <u32>dx;
            bc -= dx;
            if (dist > o - o0 || o + n > oe) {
                ok = false;
                break;
            }
            let from = o - dist;
            if (dist >= n) {
                out.copyWithin(o, from, from + n);
            } else {
                for (let k = 0; k < n; k++) {
                    unchecked(out[o + k] = out[from + k]);
                }
            }
            o += n;
        }
        r.bb = bb;
        r.bc = bc;
        r.pos = pos;
        if (!ok) {
            return false;
        }
    }
    return o == oe;
}

function adler32(b: Uint8Array, o: i32, n: i32): u32 {
    let a: u32 = 1;
    let c: u32 = 0;
    let i = o;
    let e = o + n;
    while (i < e) {
        let blk = e - i < 5552 ? e - i : 5552;
        let be = i + blk;
        while (i < be) {
            a += <u32>unchecked(b[i]);
            c += a;
            i++;
        }
        a %= 65521;
        c %= 65521;
    }
    return (c << 16) | a;
}

export class ChunkedInflate {
    src: Uint8Array = new Uint8Array(0);
    out: ArrayBuffer = new ArrayBuffer(0);
    dst: Uint8Array = new Uint8Array(0);
    blob: ArrayBuffer = new ArrayBuffer(0);
    n: i32 = 0;
    k: i32 = 0;
    pos: i32 = 12;
    o: i32 = 0;
    failed: bool = false;

    // inflate whole chunks until the time budget (seconds) is spent; true once finished (or failed)
    step(budget: f64): bool {
        let t0 = clock();
        while (this.k < this.n) {
            let raw = <i32>Buffer.readu32(this.blob, <f64>this.pos);
            let comp = <i32>Buffer.readu32(this.blob, <f64>(this.pos + 4));
            let want = <u32>Buffer.readu32(this.blob, <f64>(this.pos + 8));
            let s = this.pos + 12;
            if (s + comp > this.src.length || this.o + raw > this.dst.length || !inflateRaw(this.src, s, s + comp, this.dst, this.o, raw) ||
                adler32(this.dst, this.o, raw) != want) {
                this.failed = true;
                return true;
            }
            this.pos = s + comp;
            this.o += raw;
            this.k++;
            if (clock() - t0 > budget) {
                break;
            }
        }
        return this.k >= this.n;
    }
}

// a ChunkedInflate when the blob is an RZ01 container, null when it is stored raw
export function openZ(b: ArrayBuffer): ChunkedInflate? {
    if (b.byteLength < 12 || Buffer.readstring(b, 0, 4) != "RZ01") {
        return null;
    }
    let z = new ChunkedInflate();
    z.blob = b;
    z.src = Uint8Array.wrap(b);
    let total = <i32>Buffer.readu32(b, 4);
    z.n = <i32>Buffer.readu32(b, 8);
    z.out = new ArrayBuffer(total);
    z.dst = Uint8Array.wrap(z.out);
    return z;
}
