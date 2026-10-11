// Loads a mesh pack (tools/meshpack.py) from a blob asset. Vertices are
// already interleaved pos/normal/uv (32 bytes), so loading is just slicing the
// blob into per-mesh buffers.
import { Vector } from "rive/vector";
import { GPUBuffer } from "rive/gpu";
import { BufferUsage } from "rive/gpu_enums";
import { Buffer } from "rive/buffer";

// a frustum-cullable run of triangles (index range + bounds)
export class Chunk {
    first: u32 = 0;
    count: u32 = 0;
    minX: f64 = 0;
    minY: f64 = 0;
    minZ: f64 = 0;
    maxX: f64 = 0;
    maxY: f64 = 0;
    maxZ: f64 = 0;
}

export class PackMesh {
    name: string = "";
    src: ArrayBuffer = new ArrayBuffer(0);
    vOff: u32 = 0;
    iOff: u32 = 0;
    count: u32 = 0;
    vcount: u32 = 0;
    lmin: Vector = Vector.xyz(0, 0, 0);
    lmax: Vector = Vector.xyz(0, 0, 0);
    chunks: Array<Chunk> = [];
    vbuf: GPUBuffer? = null;
    ibuf: GPUBuffer? = null;

    upload(): void {
        if (this.vbuf == null && this.vcount > 0) {
            // straight from the blob, no intermediate copies
            let vb = new GPUBuffer(BufferUsage.vertex, this.vcount * 32);
            vb.update(0, this.src, this.vcount * 32, this.vOff);
            let ib = new GPUBuffer(BufferUsage.index, this.count * 4);
            ib.update(0, this.src, this.count * 4, this.iOff);
            this.vbuf = vb;
            this.ibuf = ib;
        }
    }
}

export class Pack {
    meshes: Map<string, PackMesh> = new Map<string, PackMesh>();

    get(name: string): PackMesh? {
        if (this.meshes.has(name)) {
            return this.meshes.get(name);
        }
        return null;
    }

    upload(): void {
        let vals = this.meshes.values();
        for (let i = 0; i < vals.length; i++) {
            vals[i].upload();
        }
    }
}

export function loadPack(b: ArrayBuffer): Pack? {
    if (b.byteLength < 8) {
        return null;
    }
    let magic = Buffer.readstring(b, 0, 4);
    if (magic != "RMP1" && magic != "RMP2") {
        return null;
    }
    let v2 = magic == "RMP2";
    let n = <i32>Buffer.readu32(b, 4);
    let o: i32 = 8;
    let pack = new Pack();
    for (let k = 0; k < n; k++) {
        let raw = Buffer.readstring(b, <f64>o, 32);
        let z = raw.indexOf(String.fromCharCode(0));
        let name = z >= 0 ? raw.substring(0, z) : raw;
        o += 32;
        let vc = <u32>Buffer.readu32(b, <f64>o);
        let ic = <u32>Buffer.readu32(b, <f64>(o + 4));
        let m = new PackMesh();
        m.name = name;
        m.vcount = vc;
        m.count = ic;
        m.lmin = Vector.xyz(<f32>Buffer.readf32(b, <f64>(o + 8)), <f32>Buffer.readf32(b, <f64>(o + 12)), <f32>Buffer.readf32(b, <f64>(o + 16)));
        m.lmax = Vector.xyz(<f32>Buffer.readf32(b, <f64>(o + 20)), <f32>Buffer.readf32(b, <f64>(o + 24)), <f32>Buffer.readf32(b, <f64>(o + 28)));
        o += 32;
        m.src = b;
        m.vOff = <u32>o;
        o += <i32>vc * 32;
        m.iOff = <u32>o;
        o += <i32>ic * 4;
        if (v2) {
            let nc = <i32>Buffer.readu32(b, <f64>o);
            o += 4;
            for (let c = 0; c < nc; c++) {
                let ch = new Chunk();
                ch.first = <u32>Buffer.readu32(b, <f64>o);
                ch.count = <u32>Buffer.readu32(b, <f64>(o + 4));
                ch.minX = Buffer.readf32(b, <f64>(o + 8));
                ch.minY = Buffer.readf32(b, <f64>(o + 12));
                ch.minZ = Buffer.readf32(b, <f64>(o + 16));
                ch.maxX = Buffer.readf32(b, <f64>(o + 20));
                ch.maxY = Buffer.readf32(b, <f64>(o + 24));
                ch.maxZ = Buffer.readf32(b, <f64>(o + 28));
                m.chunks.push(ch);
                o += 32;
            }
        }
        pack.meshes.set(name, m);
    }
    return pack;
}
