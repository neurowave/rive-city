// world.as — Rive City (AnimaScript).
//
// A ScriptedLayout that owns the whole 3D world on a GPU canvas: the
// procedural city (textured tower blocks, swarm traffic, billboards whose
// faces are live Rive artboards), the hovercar and its cockpit (driver
// display, centre screen, yoke hub and windshield HUD — all live artboards),
// the sun shadow map, shadowed volumetric haze, HDR bloom/tonemap, the boot
// sequence (logo -> city rise -> dive into the seat -> power-up), autopilot /
// manual driving, AR markers and ray-cast input into every surface.
//
// GENERATED from tools/world_parts/*.as.part by tools/build_world.py — edit
// the parts, not world.as.

import { Layout, Context, DecodedImage, ImageDecodeListener } from "rive/host";
import { Renderer } from "rive/renderer";
import { Artboard } from "rive/artboard";
import { PropertyNumber, PropertyString } from "rive/data";
import { Mat4 } from "rive/mat4";
import { clock } from "rive/os";
import { Mat2D } from "rive/mat2d";
import { Vector } from "rive/vector";
import { Canvas } from "rive/canvas";
import { ImageSampler, ImageWrap, ImageFilter } from "rive/image";
import { BlendMode } from "rive/paint";
import { KeyboardEvent, PointerEvent } from "rive/events";
import { Buffer } from "rive/buffer";
import { formatFixed, formatInt } from "rive/format";
import {
    GPUBuffer, GPUTexture, GPUTextureDesc, GPUTextureViewDesc, GPUSampler, GPUPipeline, GPUPipelineDesc,
    GPUColorTargetDesc, GPUVertexBufferLayout, GPUVertexAttribute, GPUBindGroup, GPUBindGroupLayout, GPUBindGroupUBO,
    GPUBindGroupTexture, GPUBindGroupSampler, GPUCanvas, GPUPassDesc, GPUColorAttachment, GPUDepthStencilDesc,
    GPUTextureView, GPUBlendState, GPURenderPass, GPUShaderModule,
} from "rive/gpu";
import {
    BufferUsage, TextureFormat, TextureType, TextureViewDimension, TextureAspect, Filter, WrapMode, VertexFormat,
    VertexStepMode, CompareFunction, CullMode, LoadOp, StoreOp, IndexFormat, BlendFactor, BlendOp,
} from "rive/gpu_enums";
import { rive_gpu_texture_upload_v1 } from "rive/bindings";
import { PackMesh, Pack, Chunk, loadPack } from "./pack";
import { ChunkedInflate, openZ } from "./inflate";
import * as City from "./cityinfo";
import * as Cab from "./cabin";
import * as TexInfo from "./texinfo";

// ---------------------------------------------------------------- constants
const UBO_SIZE: u32 = 160;
const FRAME_SIZE: u32 = 1120;
const CAR_SN: u32 = 1024;
const SHADOW_N: u32 = 2048;
const SHADOW_HALF: f64 = 700;
const P: f64 = City.P;
const NB: i32 = City.N;
const ROUTE_N: i32 = City.routeN;
const KMH: f64 = 3.6;
const PI: f64 = Math.PI;

const KEY_R: i32 = 82;
const KEY_M: i32 = 77;
const KEY_N: i32 = 78;
const KEY_C: i32 = 67;
const KEY_P: i32 = 80;
const KEY_F: i32 = 70;
const KEY_T: i32 = 84;
const KEY_H: i32 = 72;
const KEY_O: i32 = 79;
const KEY_E: i32 = 69;
const KEY_ESC: i32 = 256;
// the playable SillyScroll board: billboard design 9 = surface 14 (1-based)
const SILLY_DES: i32 = 9;
const N_DES: i32 = 10;
const PLAY_FOV: f64 = 40 * PI / 180;
const KEY_UP: i32 = 265;
const KEY_DOWN: i32 = 264;
const KEY_LEFT: i32 = 263;
const KEY_RIGHT: i32 = 262;
const KEY_W: i32 = 87;
const KEY_A: i32 = 65;
const KEY_S: i32 = 83;
const KEY_D: i32 = 68;
const KEY_ENTER: i32 = 257;
const KEY_KP_ENTER: i32 = 335;
const KEY_SPACE: i32 = 32;
const DRAG_SLOP: f64 = 5;
const COCKPIT_ID: i32 = 200;

const MODE_NAMES: StaticArray<string> = ["CRUISE", "SPORT", "SKY LANE"];
const MODE_CRUISE: StaticArray<f64> = [62, 96, 84];
const MODE_ACCEL: StaticArray<f64> = [3.0, 6.0, 4.0];

const TRACK_TITLE: StaticArray<string> = ["NEON CATHEDRAL", "SKYLANE", "AFTERBURN", "MERIDIAN NIGHTS", "CHROME RAIN", "VECTOR HEART"];
const TRACK_ARTIST: StaticArray<string> = ["VANTA ARC", "LUMEN DRIVE", "ROCKET SQUADRON OST", "HALO STATIC", "KODA & THE PRISM", "NULL SET"];
const TRACK_DUR: StaticArray<f64> = [222, 245, 178, 211, 257, 189];
const NTRACKS: i32 = 6;
const BB_NAMES: StaticArray<string> = ["ROCKET SQUADRON", "RIVE", "KINETIC", "MERIDIAN LIVE", "SKYLINE ARCADE", "HOTEL AURORA", "NISHIKI", "AURA", "DEEPWATER", "SILLY SCROLL"];
const AMB_HEX: StaticArray<u32> = [0xFFA41C, 0x19F2FF, 0xF30058, 0x3084FF, 0x71FF19, 0xE8ECF4];
const AMB_NAMES: StaticArray<string> = ["AMBER", "CYAN", "MAGENTA", "BLUE", "VOLT", "WHITE"];
const BB_LIGHT: StaticArray<f64> = [0.25, 0.45, 1.0, 0.9, 0.9, 1.0, 0.55, 1.0, 0.12, 1.0, 0.55, 0.15, 1.0, 0.1, 0.6, 0.1, 0.8, 1.0, 1.0, 0.4, 0.15, 1.0, 0.12, 0.5, 0.1, 0.75, 1.0, 1.0, 0.72, 0.35];
const NPC_PAINT: StaticArray<u32> = [0xE9E7E2, 0x9A9DA3, 0x23262B, 0x1C1E22, 0x7A1A16, 0x5A5E66, 0x2C4A63, 0x30343B, 0xD9D2C3, 0x6B665C, 0x0F3D3A, 0x22252B];
// shader material ids (lit.wgsl carMaterial)
const MAT_PAINT: f64 = 0;
const MAT_BLACK: f64 = 1;
const MAT_CARBON: f64 = 2;
const MAT_METAL: f64 = 3;
const MAT_GLASS: f64 = 4;
const MAT_LEATHER: f64 = 6;
const MAT_SUEDE: f64 = 7;
const MAT_SOFT: f64 = 8;
const MAT_QUILT: f64 = 9;
const MAT_GRILLE: f64 = 10;
const MAT_CARPET: f64 = 11;

// title: the boot clock holds at T_DIVE (dive start pose = city overview) until ENTER
const T_LOGO: f64 = 2.0;       // Rive logo plays in once the city has fully risen (load time, s)
const T_TITLE_UI: f64 = 2.4;   // FUI: its build (T_TITLE_UI + 0.35) starts as the logo's 0.75 s play-in ends
// boot timeline (seconds since power-on)
const T_LOGO_OUT: f64 = 2.6;
const T_POWER: f64 = 3.5;
const T_DIVE: f64 = 2.8;
const DIVE_DUR: f64 = 7.4;
const T_AMB: f64 = 9.4;
const T_CL: f64 = 9.9;
const T_CS: f64 = 10.2;
const T_HUB: f64 = 10.4;
const T_HUD: f64 = 10.7;
const T_UI: f64 = 11.6;
const T_READY: f64 = 12.0;
const T_GO: f64 = 12.6;
const START_S: f64 = 30;

// ---------------------------------------------------------------- maths
@inline function clamp(x: f64, a: f64, b: f64): f64 {
    return x < a ? a : (x > b ? b : x);
}

@inline function V(x: f64, y: f64, z: f64): Vector {
    return Vector.xyz(<f32>x, <f32>y, <f32>z);
}

function relBG(b: GPUBindGroup?): void {
    if (b != null) {
        b.release();
    }
}

@inline function vcross(a: Vector, b: Vector): Vector {
    let ax = <f64>a.x, ay = <f64>a.y, az = <f64>a.z;
    let bx = <f64>b.x, by = <f64>b.y, bz = <f64>b.z;
    return V(ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx);
}

@inline function vadd(a: Vector, b: Vector, k: f64): Vector {
    return V(<f64>a.x + <f64>b.x * k, <f64>a.y + <f64>b.y * k, <f64>a.z + <f64>b.z * k);
}

function halton(i: i32, b: i32): f64 {
    let f: f64 = 1;
    let r: f64 = 0;
    let n = i;
    while (n > 0) {
        f = f / <f64>b;
        r = r + f * <f64>(n % b);
        n = n / b;
    }
    return r;
}

@inline function vscale(a: Vector, k: f64): Vector {
    return V(<f64>a.x * k, <f64>a.y * k, <f64>a.z * k);
}

@inline function vsub(a: Vector, b: Vector): Vector {
    return V(<f64>a.x - <f64>b.x, <f64>a.y - <f64>b.y, <f64>a.z - <f64>b.z);
}

@inline function vlerp(a: Vector, b: Vector, t: f64): Vector {
    return V(<f64>a.x + (<f64>b.x - <f64>a.x) * t, <f64>a.y + (<f64>b.y - <f64>a.y) * t, <f64>a.z + (<f64>b.z - <f64>a.z) * t);
}

@inline function vdot(a: Vector, b: Vector): f64 {
    return <f64>a.x * <f64>b.x + <f64>a.y * <f64>b.y + <f64>a.z * <f64>b.z;
}

@inline function vlen(a: Vector): f64 {
    return Math.sqrt(vdot(a, a));
}

@inline function vnorm(a: Vector): Vector {
    let l = vlen(a);
    return l > 1e-12 ? vscale(a, 1 / l) : a;
}

function smooth5(x: f64): f64 {
    let t = clamp(x, 0, 1);
    return t * t * t * (t * (t * 6 - 15) + 10);
}

function wrapAng(a: f64): f64 {
    let x = (a + PI) % (2 * PI);
    if (x < 0) {
        x += 2 * PI;
    }
    return x - PI;
}

function wrapS(s: f64): f64 {
    let x = s % <f64>ROUTE_N;
    return x < 0 ? x + <f64>ROUTE_N : x;
}

// route sample as (x, 0, z)
function routeAt(s: f64): Vector {
    let ss = wrapS(s);
    let i = <i32>Math.floor(ss);
    let f = ss - <f64>i;
    let j = (i + 1) % ROUTE_N;
    let x0 = <f64>City.route[i * 2];
    let z0 = <f64>City.route[i * 2 + 1];
    let x1 = <f64>City.route[j * 2];
    let z1 = <f64>City.route[j * 2 + 1];
    return V(x0 + (x1 - x0) * f, 0, z0 + (z1 - z0) * f);
}

// unit direction (x, 0, z)
function routeDir(s: f64): Vector {
    let a = routeAt(s - 2);
    let b = routeAt(s + 2);
    let dx = <f64>b.x - <f64>a.x;
    let dz = <f64>b.z - <f64>a.z;
    let l = Math.sqrt(dx * dx + dz * dz);
    if (l < 1e-6) {
        return V(0, 0, -1);
    }
    return V(dx / l, 0, dz / l);
}

// yaw: forward = (sin yaw, -cos yaw)
@inline function yawOf(fx: f64, fz: f64): f64 {
    return Math.atan2(fx, -fz);
}

function basis(px: f64, py: f64, pz: f64, yaw: f64): Mat4 {
    let fx = Math.sin(yaw);
    let fz = -Math.cos(yaw);
    let rx = -fz;
    let rz = fx;
    return Mat4.values(<f32>rx, 0, <f32>rz, 0, 0, 1, 0, 0, <f32>-fx, 0, <f32>-fz, 0, <f32>px, <f32>py, <f32>pz, 1);
}

@inline function tp(m: Mat4, p: Vector): Vector {
    return m.transformPoint(p.x, p.y, p.z);
}

// Hermite spline through keys (times ts), zero end tangents
function hermiteTan(ps: Array<Vector>, ts: Array<f64>, i: i32): Vector {
    let n = ps.length;
    if (i == 0 || i == n - 1) {
        return V(0, 0, 0);
    }
    return vscale(vsub(ps[i + 1], ps[i - 1]), 1 / (ts[i + 1] - ts[i - 1]));
}

function hermite(ps: Array<Vector>, ts: Array<f64>, x: f64): Vector {
    let n = ps.length;
    if (x <= ts[0]) {
        return ps[0];
    }
    if (x >= ts[n - 1]) {
        return ps[n - 1];
    }
    let k = 0;
    while (k < n - 2 && x > ts[k + 1]) {
        k++;
    }
    let h = ts[k + 1] - ts[k];
    let t = (x - ts[k]) / h;
    let t2 = t * t;
    let t3 = t2 * t;
    let h00 = 2 * t3 - 3 * t2 + 1;
    let h10 = t3 - 2 * t2 + t;
    let h01 = -2 * t3 + 3 * t2;
    let h11 = t3 - t2;
    let m0 = vscale(hermiteTan(ps, ts, k), h);
    let m1 = vscale(hermiteTan(ps, ts, k + 1), h);
    let r = vscale(ps[k], h00);
    r = vadd(r, m0, h10);
    r = vadd(r, ps[k + 1], h01);
    return vadd(r, m1, h11);
}

// critically damped spring; returns new x, writes velocity to out.v
class Spring {
    x: f64 = 0;
    v: f64 = 0;
}

function cdSpring(out: Spring, x: f64, v: f64, target: f64, wn: f64, dt: f64): void {
    let d = x - target;
    let e = Math.exp(-wn * dt);
    let tmp = (v + wn * d) * dt;
    out.x = target + (d + tmp) * e;
    out.v = (v - wn * tmp) * e;
}

// ---------------------------------------------------------------- colour
class Col {
    r: f64;
    g: f64;
    b: f64;
    constructor(r: f64, g: f64, b: f64) {
        this.r = r;
        this.g = g;
        this.b = b;
    }
}

function hex(h: u32): Col {
    return new Col(<f64>((h >> 16) & 255) / 255, <f64>((h >> 8) & 255) / 255, <f64>(h & 255) / 255);
}

function mix3(a: Col, b: Col, t: f64): Col {
    return new Col(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t);
}

function fmtM(m: f64): string {
    if (m < 1000) {
        return formatInt(Math.floor(m / 5 + 0.5) * 5) + " M";
    }
    return formatFixed(m / 1000, 1) + " KM";
}

// golden hour sun raking across the street grid
const SUN_EL: f64 = 33 * PI / 180;
const SHAFT_GAIN: f64 = 0.4;            // screen-space sun shafts (final.wgsl r.shaft)
const SUN_TINT: Vector = Vector.xyz(1.0, 0.82, 0.6);
const SUN_AZ: f64 = 197 * PI / 180;

function sunDir(): Vector {
    return vnorm(V(Math.cos(SUN_EL) * Math.cos(SUN_AZ), Math.sin(SUN_EL), Math.cos(SUN_EL) * Math.sin(SUN_AZ)));
}

function moonDir(): Vector {
    return vnorm(V(0.35, 0.72, 0.42));
}

// ---------------------------------------------------------------- data types
class Obj {
    mesh: PackMesh? = null;
    noRefl: bool = false;     // skip in the 1/3-res mirror pass (hairline geometry that can't resolve there)
    ubo: GPUBuffer? = null;
    bg: GPUBindGroup? = null;
    bgR: GPUBindGroup? = null;
    bgC: GPUBindGroup? = null;
    bgS: GPUBindGroup? = null;
    mode: i32 = 0;
    id: i32 = 0;
    day: Col = new Col(1, 1, 1);
    model: Mat4 = Mat4.identity();
    tex: i32 = 0;
    bright: f64 = 1;
    flash: f64 = 0;
    accentMix: f64 = 0;
    visible: bool = true;
    pass: i32 = 1; // 1 city, 2 cockpit, 3 glass
    cull: bool = false;
    emis: f64 = 0;
    fx: StaticArray<f64> = new StaticArray<f64>(4);
    accent: Col? = null;
    ext: bool = false; // player exterior part
    rough: f64 = 0.5;
    metal: f64 = 0;
    refl: bool = true;
    auxW: f64 = 0;
    glass: bool = false; // player canopy (transparent, world pass, last)
    castCar: bool = false; // casts into the car shadow map
    envMap: bool = false; // samples last frame (screen-space reflections)
    bgCS: GPUBindGroup? = null;
}

class Surf {
    input: Artboard? = null;
    inst: Artboard? = null;
    canvas: Canvas? = null;
    w: f64 = 512;
    h: f64 = 512;
    density: f64 = 1;
    clear: u32 = 0;
    live: bool = true;
    pending: f64 = 0;   // advance time owed while the surface was culled
}


class Npc {
    kind: i32 = 1; // 1 ground same dir, 2 ground opposite, 3 air
    s: f64 = 0;
    v: f64 = 0;
    off: f64 = 0;
    axis: i32 = 0;
    line: f64 = 0;
    alt: f64 = 0;
    dir: f64 = 1;
    pos: Vector = V(0, 0, 0);
    yaw: f64 = 0;
    scale: f64 = 1;
    parts: Array<Obj> = [];
    model: Mat4 = Mat4.identity();
}

class BB {
    c: Vector = V(0, 0, 0);
    nx: f64 = 0;
    nz: f64 = 0;
    rx: f64 = 0;
    rz: f64 = 0;
    w: f64 = 0;
    h: f64 = 0;
    design: i32 = 0;
}

class Marker {
    x: f64 = 0;
    y: f64 = 0;
    op: f64 = 0;
    q: i32 = 0;
    vis: f64 = 1;
    lvis: f64 = 1;
    title: string = "";
    dist: string = "";
    key: f64 = -1;
}

class Cand {
    d: f64 = 0;
    b: BB;
    constructor(d: f64, b: BB) {
        this.d = d;
        this.b = b;
    }
}

class Want {
    wp: Vector = V(0, 0, 0);
    title: string = "";
    dist: string = "";
    key: f64 = 0;
}

class Light {
    x: f64 = 0;
    y: f64 = 0;
    z: f64 = 0;
    r: f64 = 0;
    cr: f64 = 0;
    cg: f64 = 0;
    cb: f64 = 0;
    k: f64 = 0;
}

// six clip planes from a view-projection (WebGPU depth 0..1)
class Frustum {
    p: StaticArray<f64> = new StaticArray<f64>(24);

    set(m: Mat4): void {
        let a = m.m;
        for (let k = 0; k < 6; k++) {
            let r = k >> 1;
            let sgn: f64 = (k & 1) == 0 ? 1 : -1;
            let o = k * 4;
            for (let c = 0; c < 4; c++) {
                let w = <f64>a[c * 4 + 3];
                let v = <f64>a[c * 4 + r];
                if (k == 4) {
                    this.p[o + c] = v;                 // near: z >= 0
                } else if (k == 5) {
                    this.p[o + c] = w - <f64>a[c * 4 + 2]; // far: z <= w
                } else {
                    this.p[o + c] = w + sgn * v;
                }
            }
        }
    }

    visible(c: Chunk): bool {
        for (let k = 0; k < 6; k++) {
            let o = k * 4;
            let a = this.p[o];
            let b = this.p[o + 1];
            let cc = this.p[o + 2];
            let d = this.p[o + 3];
            let x = a > 0 ? c.maxX : c.minX;
            let y = b > 0 ? c.maxY : c.minY;
            let z = cc > 0 ? c.maxZ : c.minZ;
            if (a * x + b * y + cc * z + d < 0) {
                return false;
            }
        }
        return true;
    }
}

class Hit {
    t: f64 = 1e18;
    k: i32 = 0;
    p: Vector = V(0, 0, 0);
}

// HUD declutter: layout sizes mirrored from tools/gen_ui.py (TRK_W/H, MK_W/H, RO_*)
const TRK_W: f64 = 156;
const TRK_H: f64 = 96;
const MK_W: f64 = 190;
const MK_H: f64 = 44;
// readout cluster rect on the HUD artboard (cx 600, RO_W 660, RO_Y 559) + margin
const RO_X0: f64 = 256;
const RO_X1: f64 = 944;
const RO_Y0: f64 = 545;
const RO_Y1: f64 = 720;
// quadrant signs: 0 up-right, 1 up-left, 2 down-right, 3 down-left
const Q_FX: StaticArray<f64> = [1, -1, 1, -1];
const Q_FY: StaticArray<f64> = [1, 1, -1, -1];

class Rect {
    x0: f64;
    y0: f64;
    x1: f64;
    y1: f64;
    constructor(x0: f64, y0: f64, x1: f64, y1: f64) {
        this.x0 = x0;
        this.y0 = y0;
        this.x1 = x1;
        this.y1 = y1;
    }
    hits(o: Rect): bool {
        return this.x0 < o.x1 && o.x0 < this.x1 && this.y0 < o.y1 && o.y0 < this.y1;
    }
}

// one HUD vehicle tracker slot
class Trk {
    key: f64 = -1;
    q: i32 = 0;
    vis: f64 = 1;
    lvis: f64 = 1;
    x: f64 = -500;
    y: f64 = -500;
    s: f64 = 1;
    op: f64 = 0;
    hold: i32 = 0;
    dPrev: f64 = -1;
    vc: f64 = 0;
    hexT: f64 = 0;
    hex: string = "0x0000";
    id: string = "HX-0000";
    cl: string = "SEDAN";
}

class TrkCand {
    d: f64;
    key: f64;
    p: Vector;
    constructor(d: f64, key: f64, p: Vector) {
        this.d = d;
        this.key = key;
        this.p = p;
    }
}

const TRK_CLASSES: StaticArray<string> = ["SEDAN", "COURIER", "CARGO", "PATROL", "TAXI", "SHUTTLE", "FREIGHT", "MEDEVAC"];
const HEXD: string = "0123456789ABCDEF";

function hex4(v: i32): string {
    let s = "0x";
    for (let i = 3; i >= 0; i--) {
        let d = (v >> (i * 4)) & 15;
        s += HEXD.charAt(d);
    }
    return s;
}

function fmt1(v: f64): string {
    let i = <i32>Math.floor(Math.max(v, 0) * 10 + 0.5);
    let w = i / 10;
    let f = i % 10;
    return (w < 10 ? "0" : "") + w.toString() + "." + f.toString();
}

// a decoded facade atlas waiting to be uploaded, one mip level per step
class TexJob {
    data: ArrayBuffer = new ArrayBuffer(0);
    W: i32 = 0;
    tex: GPUTexture? = null;
    layer: u32 = 0;
    mip: i32 = 0;
    y: i32 = 0;
    mips: i32 = 8;
}

// a queued window-map decode (tools/make_winmap.py)
class WinDec {
    data: ArrayBuffer;
    dec: TexDecode;

    constructor(data: ArrayBuffer, dec: TexDecode) {
        this.data = data;
        this.dec = dec;
    }
}

// decodes one facade JPEG (mip-chain atlas) into a texture-array layer
class TexDecode extends ImageDecodeListener {
    world: World;
    tex: GPUTexture;
    layer: u32;

    mips: i32 = TexInfo.mips;

    constructor(world: World, tex: GPUTexture, layer: u32, mips: i32 = TexInfo.mips) {
        super();
        this.world = world;
        this.tex = tex;
        this.layer = layer;
        this.mips = mips;
    }

    // runs inside the decode callback (own 200 ms watchdog): only keep the pixels. The uploads
    // happen in advance(), one mip level per step under a frame budget (World.pumpTex), so a busy
    // machine can't push this callback past the watchdog.
    override onImageDecoded(image: DecodedImage): void {
        let j = new TexJob();
        j.data = image.data;
        j.W = <i32>image.width;
        j.tex = this.tex;
        j.layer = this.layer;
        j.mips = this.mips;
        this.world.texJobs.push(j);
    }

    override onImageDecodeFailed(message: string): void {
        this.world.log("tex decode failed: " + message);
        this.world.texDecoded();
    }
}

// ================================================================ World
export class World extends Layout {
    @input clusterUI: Artboard? = null;
    @input consoleUI: Artboard? = null;
    @input hubUI: Artboard? = null;
    @input hudUI: Artboard? = null;
    @input bbRocket: Artboard? = null;
    @input bbRive: Artboard? = null;
    @input bbKinetic: Artboard? = null;
    @input bbLive: Artboard? = null;
    @input bbArcade: Artboard? = null;
    @input bbHotel: Artboard? = null;
    @input bbKoi: Artboard? = null;
    @input bbAura: Artboard? = null;
    @input bbDeep: Artboard? = null;
    @input bbSilly: Artboard? = null;

    context: Context? = null;
    city: Pack? = null;
    props: Pack? = null;
    objs: Array<Obj> = [];
    surfs: Array<Surf> = [];
    bbs: Array<BB> = [];
    npcs: Array<Npc> = [];
    ext: Array<Obj> = [];
    cab: Array<Obj> = [];
    clFace: Obj? = null;
    csFace: Obj? = null;
    hubFace: Obj? = null;
    yokeParts: Array<Obj> = [];
    clParts: Array<Obj> = [];
    csParts: Array<Obj> = [];
    hudObj: Obj? = null;
    glassObj: Obj? = null;
    ambObj: Obj? = null;
    extGlass: Obj? = null;
    dseat: Array<Obj> = [];
    orbitA: f64 = 0.6;
    orbitBlend: f64 = 0;
    vlim: StaticArray<f64> = new StaticArray<f64>(0);

    // GPU
    gpu: GPUCanvas? = null;
    bgl: GPUBindGroupLayout? = null;
    frameMain: GPUBuffer? = null;
    frameRefl: GPUBuffer? = null;
    frameCab: GPUBuffer? = null;
    frameShadow: GPUBuffer? = null;
    dummyUbo: GPUBuffer? = null;
    litMS: GPUPipeline? = null;
    litMSCull: GPUPipeline? = null;
    litR: GPUPipeline? = null;
    depthMS: GPUPipeline? = null;
    skyMS: GPUPipeline? = null;
    skyR: GPUPipeline? = null;
    rainMS: GPUPipeline? = null;
    holoMS: GPUPipeline? = null;     // holo blade signs (lit.wgsl vs_holo)
    holoBuf: GPUBuffer? = null;
    holoN: u32 = 0;
    steamMS: GPUPipeline? = null;    // rooftop / street steam (lit.wgsl vs_steam)
    steamBuf: GPUBuffer? = null;
    steamN: u32 = 0;
    glassMS: GPUPipeline? = null;
    swarmPipe: GPUPipeline? = null;
    greebleMS: GPUPipeline? = null;
    greebleShadow: GPUPipeline? = null;
    coneMS: GPUPipeline? = null;
    shadowSkyBG: GPUBindGroup? = null;
    conesObj: Obj? = null;
    shadowPipe: GPUPipeline? = null;
    brightPipe: GPUPipeline? = null;
    blurPipe: GPUPipeline? = null;
    finalPipe: GPUPipeline? = null;
    hdrMSV: GPUTextureView? = null;
    hdrV: GPUTextureView? = null;
    depthMSV: GPUTextureView? = null;
    reflV: GPUTextureView? = null;
    reflDepthV: GPUTextureView? = null;
    dummyV: GPUTextureView? = null;
    albV: GPUTextureView? = null;
    nrmV: GPUTextureView? = null;
    shadowV: GPUTextureView? = null;
    shadowAttV: GPUTextureView? = null;
    shadowDummyV: GPUTextureView? = null;
    clearPipe: GPUPipeline? = null;
    frameCarShadow: GPUBuffer? = null;
    carVP: Mat4 = Mat4.identity();      // relative to carOrigin
    carOrigin: Vector = V(0, 0, 0);
    viewProjRel: Mat4 = Mat4.identity(); // camera-relative (origin = eye) for the GPU
    viewProjBRel: Mat4 = Mat4.identity();
    viewProjRelNJ: Mat4 = Mat4.identity(); // unjittered (TAA reprojection)
    prevVPRel: Mat4 = Mat4.identity();
    prevEye: Vector = V(0, 0, 0);
    jitN: i32 = 0;
    taaPipe: GPUPipeline? = null;
    hudMS: GPUPipeline? = null;
    holoBackMS: GPUPipeline? = null;
    holoBacks: Array<Obj> = [];
    taaUbo: GPUBuffer? = null;
    taaV: Array<GPUTextureView> = [];
    taaBG: Array<GPUBindGroup> = [];
    finBGs: Array<GPUBindGroup> = [];
    taaIdx: i32 = 0;
    trks: Array<Trk> = [new Trk(), new Trk(), new Trk(), new Trk()];
    swCpu: StaticArray<f32> = new StaticArray<f32>(0);
    gpuStage: i32 = 0;
    taaValid: bool = false;
    carShOn: bool = false;
    envV: GPUTextureView? = null;
    envUbo: GPUBuffer? = null;
    envBG: GPUBindGroup? = null;
    envFrames: i32 = 0;
    albTex: GPUTexture? = null;
    nrmTex: GPUTexture? = null;
    texPending: i32 = 0;
    texReady: bool = false;
    texSampler: GPUSampler? = null;
    linSampler: GPUSampler? = null;
    swarmBuf: GPUBuffer? = null;
    swarmN: u32 = 0;
    texJobs: Array<TexJob> = [];
    winQ: Array<WinDec> = [];        // window-map PNGs waiting to be decoded (one per frame)   // facade atlases waiting for upload (pumpTex)
    carChunk: Chunk = new Chunk();   // car bounds for the cockpit-screen visibility test
    dbgNoCull: bool = false;     // --data=dbgFlags=1: render every billboard canvas (A/B)
    bbObjs: Array<Obj> = [];      // billboard design d -> its mesh object (surface 5 + d)
    // quality (HIGH / MED / LOW): dynamic-resolution range, mirror resolution, swarm share
    dynMin: f64 = 1.0;
    dynMax: f64 = 2.0;
    reflDiv: f64 = 3;
    swarmFrac: f64 = 1;
    b1V: GPUTextureView? = null;
    b1tV: GPUTextureView? = null;
    b2V: GPUTextureView? = null;
    b2tV: GPUTextureView? = null;
    b3V: GPUTextureView? = null;
    b3tV: GPUTextureView? = null;
    skyBG: GPUBindGroup? = null;
    skyRBG: GPUBindGroup? = null;
    downUbos: Array<GPUBuffer> = [];
    downBGs: Array<GPUBindGroup> = [];
    blUbos: Array<GPUBuffer> = [];
    blBGs: Array<GPUBindGroup> = [];
    finUbo: GPUBuffer? = null;
    sunU: f64 = 0.5;
    sunV: f64 = -1;
    shaftPipe: GPUPipeline? = null;   // screen-space sun shafts (shafts.wgsl), quarter res
    shaftUbo: GPUBuffer? = null;
    shaftV: GPUTextureView? = null;
    shaftBG: GPUBindGroup? = null;
    finBG: GPUBindGroup? = null;
    shadowVP: Mat4 = Mat4.identity();
    lights: Array<Light> = [];
    rain: f64 = 1;
    scratch: ArrayBuffer = new ArrayBuffer(2048);
    gpuReady: bool = false;
    needsResize: bool = false;
    hostScale: f64 = 1;
    sizeX: f64 = 0;
    sizeY: f64 = 0;
    outScale: f64 = 1;
    gScale: f64 = 1.25;
    dynScale: f64 = 1.5; // dynamic resolution (fill-rate bound): 1.0 .. 1.5
    dynT: f64 = 0;
    dynN: i32 = 0;
    dynHold: f64 = 0;
    gw: i32 = 4;
    gh: i32 = 4;
    rw: i32 = 2;
    rh: i32 = 2;
    b1w: i32 = 2;
    b1h: i32 = 2;
    b2w: i32 = 2;
    b2h: i32 = 2;
    b3w: i32 = 2;
    b3h: i32 = 2;

    // clocks / state
    time: f64 = 0;
    boot: f64 = 0;
    // title screen
    entered: bool = false;
    tt: f64 = 0;          // title clock (since load / replay)
    loadT: f64 = -1;      // since the city finished loading (-1: still loading)
    enterT: f64 = -1;     // since ENTER
    enterOp: f64 = 0;
    worldOp: f64 = 0;
    tmx: f64 = 0;
    tmy: f64 = 0;
    tmxT: f64 = 0;
    tmyT: f64 = 0;
    tiltRoll: f64 = 0;
    titleK: f64 = 1;
    // title holo (camera-attached drum + rings wearing the "Title FUI" artboard)
    holo: Array<Obj> = [];
    holoOn: bool = false;
    holoYaw: f64 = 0;
    holoCued: bool = false;
    nightT: f64 = 0;
    night: f64 = 0;
    riseR: f64 = 0;
    powerR: f64 = 0;
    origin: Vector = V(0, 0, 0);

    // player
    px: f64 = 0;
    pz: f64 = 0;
    yaw: f64 = 0;
    v: f64 = 0;
    alt: f64 = 62;
    altV: f64 = 0;
    altT: f64 = 62;
    steer: f64 = 0;
    yawRate: f64 = 0;
    accel: f64 = 0;
    roll: f64 = 0;
    pitch: f64 = 0;
    apS: f64 = 0;
    autopilot: bool = true;
    mode: i32 = 0;
    battery: f64 = 86;
    bump: f64 = 0;
    carModel: Mat4 = Mat4.identity();
    carPos: Vector = V(0, 0, 0);
    carFwd: Vector = V(0, 0, -1);
    keys: StaticArray<bool> = new StaticArray<bool>(512);
    spring: Spring = new Spring();

    // media / ui state
    track: i32 = 2;
    playing: bool = true;
    progress: f64 = 0;
    ambient: i32 = 0;
    ambC: Col = hex(0xFFA41C);
    taps: i32 = 1287;
    hitT: f64 = 0;
    camMode: i32 = 0; // 0 cockpit, 1 chase
    camBlend: f64 = 0;
    hudOn: bool = true;

    // camera
    eye: Vector = V(0, 10, 10);
    target: Vector = V(0, 0, 0);
    up: Vector = V(0, 1, 0);
    view: Mat4 = Mat4.identity();
    viewProj: Mat4 = Mat4.identity();
    viewProjB: Mat4 = Mat4.identity();
    invVP: Mat4 = Mat4.identity();
    camF: Vector = V(0, 0, -1);
    camR: Vector = V(1, 0, 0);
    camU: Vector = V(0, 1, 0);
    camAspect: f64 = 1.7778;
    fov: f64 = 1;
    inside: bool = false;
    camSpeed: f64 = 0;
    lastEye: Vector = V(0, 0, 0);
    chaseYaw: f64 = 0;
    chaseV: f64 = 0;
    headYaw: f64 = 0;
    headPitch: f64 = 0;
    headVel: f64 = 0;
    releaseT: f64 = 0;
    markers: Array<Marker> = [new Marker(), new Marker(), new Marker()];

    // pointer
    down: bool = false;
    dragging: bool = false;
    downPos: Vector = V(0, 0, 0);
    lastPos: Vector = V(0, 0, 0);
    pressSurf: i32 = 0;
    hoverSurf: i32 = 0;

    // view model
    pNum: Map<string, PropertyNumber> = new Map<string, PropertyNumber>();
    pStr: Map<string, PropertyString> = new Map<string, PropertyString>();
    missing: Map<string, bool> = new Map<string, bool>();
    cNum: Map<string, f64> = new Map<string, f64>();
    cStr: Map<string, string> = new Map<string, string>();
    cLogo: Map<string, bool> = new Map<string, bool>();

    log(msg: string): void {
        let c = this.context;
        if (c != null) {
            c.log(msg);
        }
    }

    // ------------------------------------------------------------ view model
    private numProp(name: string): PropertyNumber? {
        if (this.pNum.has(name)) {
            return this.pNum.get(name);
        }
        if (this.missing.has("n:" + name)) {
            return null;
        }
        let ctx = this.context;
        if (ctx == null) {
            return null;
        }
        let vm = ctx.rootViewModel();
        if (vm == null) {
            return null;
        }
        let q = vm.getNumber(name);
        if (q == null) {
            this.log("world: missing view-model number " + name);
            this.missing.set("n:" + name, true);
            return null;
        }
        this.pNum.set(name, q);
        return q;
    }

    private strProp(name: string): PropertyString? {
        if (this.pStr.has(name)) {
            return this.pStr.get(name);
        }
        if (this.missing.has("s:" + name)) {
            return null;
        }
        let ctx = this.context;
        if (ctx == null) {
            return null;
        }
        let vm = ctx.rootViewModel();
        if (vm == null) {
            return null;
        }
        let q = vm.getString(name);
        if (q == null) {
            this.log("world: missing view-model string " + name);
            this.missing.set("s:" + name, true);
            return null;
        }
        this.pStr.set(name, q);
        return q;
    }

    setN(name: string, v: f64): void {
        if (this.cNum.has(name) && Math.abs(this.cNum.get(name) - v) < 1e-4) {
            return;
        }
        let p = this.numProp(name);
        if (p != null) {
            p.value = v;
            this.cNum.set(name, v);
        }
    }

    setS(name: string, v: string): void {
        if (this.cStr.has(name) && this.cStr.get(name) == v) {
            return;
        }
        let p = this.strProp(name);
        if (p != null) {
            p.value = v;
            this.cStr.set(name, v);
        }
    }

    getN(name: string): f64 {
        let p = this.numProp(name);
        return p != null ? p.value : 0;
    }

    setLogo(name: string, on: bool): void {
        if (this.cLogo.has(name) && this.cLogo.get(name) == on) {
            return;
        }
        let ctx = this.context;
        if (ctx == null) {
            return;
        }
        let vm = ctx.rootViewModel();
        if (vm == null) {
            return;
        }
        let lp = vm.getViewModel(name);
        if (lp == null) {
            return;
        }
        let b = lp.value.getBoolean("showLogo");
        if (b != null) {
            b.value = on;
            this.cLogo.set(name, on);
        }
    }

    // ------------------------------------------------------------ objects
    newObj(mesh: PackMesh?, mode: i32, day: u32, id: i32, pass: i32): Obj {
        let o = new Obj();
        o.mesh = mesh;
        o.mode = mode;
        o.id = id;
        o.day = hex(day);
        o.pass = pass;
        o.refl = pass == 1;
        if (mesh == null) {
            o.visible = false;
        }
        this.objs.push(o);
        return o;
    }

    private pm(name: string): PackMesh? {
        let p = this.props;
        return p != null ? p.get(name) : null;
    }

    private cm(name: string): PackMesh? {
        let c = this.city;
        return c != null ? c.get(name) : null;
    }

    private carMat(name: string, mat: f64, day: u32, id: i32, pass: i32): Obj {
        let o = this.newObj(this.pm(name), 14, day, id, pass);
        o.fx[3] = mat;
        o.rough = 0.5;
        return o;
    }

    // sculpted hovercar parts (tools/make_car.py); prefix "car_" (player, hi-res) or "npc_"
    carParts(prefix: string, paintDay: u32, idBase: i32, thrust: Col, player: bool): Array<Obj> {
        let paint = this.carMat(prefix + "paint", MAT_PAINT, paintDay, idBase, 1);
        let black = this.carMat(prefix + "black", MAT_BLACK, 0x050505, idBase + 2, 1);
        let carbon = this.carMat(prefix + "carbon", MAT_CARBON, 0x0A0A0A, idBase + 2, 1);
        let metal = this.carMat(prefix + "metal", MAT_METAL, 0xA0A0A4, idBase + 2, 1);
        let glass: Obj;
        if (player) {
            glass = this.newObj(this.pm(prefix + "glass"), 22, 0x000000, idBase + 1, 1);
            glass.glass = true;
            glass.refl = false;
        } else {
            glass = this.carMat(prefix + "glass", MAT_GLASS, 0x020203, idBase + 1, 1);
        }
        let light = this.newObj(this.pm(prefix + "light"), 5, 0xF4F1EA, idBase, 1);
        light.emis = 4.5;
        let tail = this.newObj(this.pm(prefix + "tail"), 5, 0xFF2A18, idBase, 1);
        tail.emis = player ? 6.0 : 4.0;
        let accent = this.newObj(this.pm(prefix + "accent"), 5, 0xFFA41C, idBase, 1);
        accent.emis = 2.2;
        let th = this.newObj(this.pm(prefix + "thrust"), 12, 0xFFA41C, idBase, 1);
        th.accent = thrust;
        let parts = [paint, black, carbon, metal, glass, light, tail, accent, th];
        for (let i = 0; i < 4; i++) {
            parts[i].envMap = true;
            parts[i].castCar = player;
        }
        glass.envMap = true;
        return parts;
    }

    private newSurf(input: Artboard?, density: f64, clear: u32): Surf {
        let s = new Surf();
        s.input = input;
        s.density = density;
        s.clear = clear;
        return s;
    }

    // the SillyScroll board and the route sample ~42 m in front of it where the car pulls up
    // stop points for every playable board;
    // the sillyC/sillyS fields hold the CURRENT target, re-picked while driving (pickPlayTarget)
    private findSillyStop(): void {
        for (let i = 0; i < this.bbs.length; i++) {
            let b = this.bbs[i];
            if (b.design != SILLY_DES) {
                continue;
            }
            let best: f64 = 1e9;
            let bestS: f64 = 0;
            for (let s = 0; s < ROUTE_N; s++) {
                let p = routeAt(<f64>s);
                let dn = (<f64>p.x - <f64>b.c.x) * b.nx + (<f64>p.z - <f64>b.c.z) * b.nz;
                if (dn < 20 || dn > 90) {
                    continue;
                }
                let d = routeDir(<f64>s);
                if (-(<f64>d.x * b.nx + <f64>d.z * b.nz) < 0.7) {
                    continue;   // must be heading at the board
                }
                let sc = Math.abs(dn - 42);
                if (sc < best) {
                    best = sc;
                    bestS = <f64>s;
                }
            }
            this.log("world: play board " + BB_NAMES[b.design] + " at " + formatFixed(<f64>b.c.x, 1) + "," +
                formatFixed(<f64>b.c.z, 1) + (best < 1e8 ? " stop s=" + formatFixed(bestS, 0) : " (no stop found)"));
            if (best < 1e8) {
                this.playBs.push(b);
                this.playSs.push(bestS);
                this.playDs.push(-1);
            }
        }
        this.sillyOk = this.playBs.length > 0;
        this.pickPlayTarget();
    }

    // how far the play camera can back off square-on from a board before a building gets in the way
    // (march the board normal at its centre height through the collision grid; capped at 32 m)
    private clearAhead(b: BB): f64 {
        let y = <f64>b.c.y - 0.6;
        let cb = this.collB;
        for (let t: f64 = 2; t <= 34; t += 0.5) {
            let x = <f64>b.c.x + b.nx * t;
            let z = <f64>b.c.z + b.nz * t;
            let gx = <i32>Math.floor((x - this.collX0) / this.collCS);
            let gz = <i32>Math.floor((z - this.collZ0) / this.collCS);
            if (gx < 0 || gz < 0 || gx >= this.collNX || gz >= this.collNZ) {
                continue;
            }
            let c = gz * this.collNX + gx;
            for (let k = this.collStart[c]; k < this.collStart[c + 1]; k++) {
                let i = this.collItems[k] * 6;
                if (x > <f64>cb[i] - 1 && x < <f64>cb[i + 3] + 1 && z > <f64>cb[i + 2] - 1 && z < <f64>cb[i + 5] + 1 &&
                    y > <f64>cb[i + 1] && y < <f64>cb[i + 4]) {
                    let d = Math.max(12, t - 1.5);
                    this.log("world: play camera for " + BB_NAMES[b.design] + " limited to " + formatFixed(d, 1) + " m");
                    return Math.min(32, d);
                }
            }
        }
        return 32;
    }

    // the play board whose stop is next ahead on the route (just-passed counts as here)
    private pickPlayTarget(): void {
        if (this.play != 0 || this.playBs.length == 0) {
            return;
        }
        let bi = 0;
        let bd: f64 = 1e9;
        for (let i = 0; i < this.playBs.length; i++) {
            let d = wrapS(this.playSs[i] - this.apS);
            if (d > <f64>ROUTE_N - 6) {
                d = 0;
            }
            if (d < bd) {
                bd = d;
                bi = i;
            }
        }
        let b = this.playBs[bi];
        if (this.playDs[bi] < 0 && this.collState == 4) {   // grid fully built (collStep)
            this.playDs[bi] = this.clearAhead(b);
        }
        this.sillyD = this.playDs[bi] > 0 ? this.playDs[bi] : 32;
        this.sillyC = b.c;
        this.sillyNx = b.nx;
        this.sillyNz = b.nz;
        this.sillyS = this.playSs[bi];
        this.playDes = b.design;
    }

    private speedLimits(): StaticArray<f64> {
        let lim = new StaticArray<f64>(ROUTE_N);
        for (let s = 0; s < ROUTE_N; s++) {
            let a = routeDir(<f64>s - 5);
            let b = routeDir(<f64>s + 5);
            let ang = Math.acos(clamp(vdot(a, b), -1, 1));
            let kappa = ang / 10;
            lim[s] = kappa > 1e-4 ? Math.min(40, Math.sqrt(4.5 / kappa)) : 40;
        }
        for (let pass = 0; pass < 2; pass++) {
            for (let s = ROUTE_N - 1; s >= 0; s--) {
                let nxt = lim[(s + 1) % ROUTE_N];
                lim[s] = Math.min(lim[s], Math.sqrt(nxt * nxt + 2 * 3.5));
            }
        }
        return lim;
    }

    instanceSurfs(): void {
        let ctx = this.context;
        if (ctx == null) {
            return;
        }
        for (let k = 0; k < this.surfs.length; k++) {
            let sf = this.surfs[k];
            let input = sf.input;
            if (input == null) {
                this.log("world: surface artboard " + (k + 1).toString() + " not bound");
                continue;
            }
            let inst = input.instance(ctx.rootViewModel());
            inst.frameOrigin = true;
            sf.inst = inst;
            sf.w = inst.width;
            sf.h = inst.height;
        }
    }

    // ------------------------------------------------------------ init
    // Loading is staged over the first frames: each host callback has its own
    // 200 ms watchdog, and copying the 35 MB city blob + 12 MB props blob plus
    // building the scene in init() alone overruns it under load.
    loadStage: i32 = 0;
    // SillyScroll stop-and-play: 0 driving, 1 pulling up to the board, 2 stopped + playing
    play: i32 = 0;
    lookHome: bool = false;
    titlePow: f64 = 0;
    blackK: f64 = 1;
    logoSeen: bool = false;   // the title logo has been allowed to show once          // start-up blackout (fades once the city has loaded)        // power radius on the night start screen (follows the city rise)   // ease the head-look back to centre (set when autopilot engages)
    playK: f64 = 0;
    sillyOk: bool = false;
    playBs: Array<BB> = [];
    playSs: Array<f64> = [];
    playDes: i32 = SILLY_DES;
    playDs: Array<f64> = [];   // clear camera distance in front of each play board (-1 = not yet measured)
    sillyD: f64 = 32;
    sillyC: Vector = V(0, 0, 0);
    sillyNx: f64 = 0;
    sillyNz: f64 = 1;
    sillyS: f64 = 0;
    zIn: ChunkedInflate? = null;
    zT: f64 = 0;
    cityP: Pack? = null;
    propsP: Pack? = null;

    override init(context: Context): bool {
        this.context = context;
        // surfaces: 0 cluster, 1 console, 2 hub, 3 hud, 4..12 billboards
        let black: u32 = 0xFF060608;
        let clearT: u32 = 0x00000000;
        this.surfs = [
            this.newSurf(this.clusterUI, 2.0, black),
            this.newSurf(this.consoleUI, 1.6, black),
            this.newSurf(this.hubUI, 2.0, black),
            this.newSurf(this.hudUI, 1.15, clearT),
            this.newSurf(this.bbRocket, 0.75, black),
            this.newSurf(this.bbRive, 0.75, black),
            this.newSurf(this.bbKinetic, 0.75, black),
            this.newSurf(this.bbLive, 0.75, black),
            this.newSurf(this.bbArcade, 0.75, black),
            this.newSurf(this.bbHotel, 0.75, black),
            this.newSurf(this.bbKoi, 0.75, black),
            this.newSurf(this.bbAura, 0.75, black),
            this.newSurf(this.bbDeep, 0.75, black),
            this.newSurf(this.bbSilly, 1.0, black),     // full res: it fills the frame while you play
        ];
        this.instanceSurfs();
        return true;
    }

    // returns true once the scene exists
    private stageLoad(): bool {
        if (this.loadStage >= 5) {
            return true;
        }
        if (this.loadStage == 3) {
            // collision grid, time-budgeted over as many frames as it takes
            if (this.collStep()) {
                this.loadStage = 5;
            }
            return false;
        }
        let ctx = this.context;
        if (ctx == null) {
            return false;
        }
        // stages 0/1: the mesh packs ship deflated (RZ01, tools/zpack.py); inflate them a few chunks per
        // frame under a time budget, then parse the byte-identical pack
        if (this.loadStage == 0 || this.loadStage == 1) {
            let nm = this.loadStage == 0 ? "city" : "props";
            if (this.zIn == null) {
                let b = ctx.blob(nm);
                if (b == null) {
                    this.log("world: " + nm + " blob missing");
                    return false;
                }
                let z = openZ(b);
                if (z == null) {
                    this.zDone(nm, b);  // stored raw
                    return false;
                }
                this.zIn = z;
                this.zT = clock();
            }
            let zi = this.zIn!;
            if (!zi.step(0.022)) {
                return false;
            }
            this.zIn = null;
            if (zi.failed) {
                this.log("world: " + nm + " inflate failed at chunk " + zi.k.toString());
                return false;
            }
            this.log("load: inflate " + nm + " " + zi.out.byteLength.toString() + " bytes in " + ((clock() - this.zT) * 1000).toString() + " ms");
            this.zDone(nm, zi.out);
            return false;
        }
        if (this.cityP == null || this.propsP == null) {
            this.log("world: bad mesh pack");
            return false;
        }
        this.props = this.propsP;
        this.city = this.cityP;
        this.setupScene();
        this.loadStage = 3;
        return false; // collision, then GPU setup, on the next frames
    }

    private zDone(nm: string, b: ArrayBuffer): void {
        if (nm == "city") {
            this.cityP = loadPack(b);
            this.loadStage = 1;
        } else {
            this.propsP = loadPack(b);
            this.loadStage = 2;
        }
    }

    private setupScene(): void {

        // city
        this.newObj(this.cm("ground"), 4, 0x9A9DA2, 1, 1);
        let roads = this.newObj(this.cm("roads"), 3, 0x6E7177, 2, 1);
        roads.accent = hex(0xFFA41C);
        this.newObj(this.cm("marks"), 13, 0x8A8C90, 2, 1);
        this.newObj(this.cm("walks"), 4, 0xA9ACB0, 3, 1);
        this.newObj(this.cm("buildings"), 2, 0xB4B7BD, 4, 1);
        this.newObj(this.cm("far"), 2, 0xA9AEB5, 5, 1);
        this.newObj(this.cm("neon"), 8, 0x8E9097, 6, 1);
        this.newObj(this.cm("beacons"), 8, 0x8E9097, 6, 1);
        let lamps = this.newObj(this.cm("lamps"), 0, 0x3A3C40, 7, 1);
        lamps.rough = 0.4;
        lamps.metal = 0.6;
        this.newObj(this.cm("lampglow"), 8, 0x8E9097, 7, 1);
        this.newObj(this.cm("gates"), 8, 0x8E9097, 8, 1);
        let cables = this.newObj(this.cm("cables"), 0, 0x1B1C20, 9, 1);
        cables.noRefl = true;
        cables.rough = 0.55;
        cables.metal = 0.3;
        let cones = this.newObj(this.cm("cones"), 16, 0xFFFFFF, 20, 1);
        cones.refl = false;
        this.conesObj = cones;
        let gantry = this.newObj(this.cm("gantry"), 0, 0x2A2C30, 9, 1);
        gantry.rough = 0.45;
        gantry.metal = 0.5;
        let bbframe = this.newObj(this.cm("bbframe"), 0, 0x1A1B1E, 10, 1);
        bbframe.rough = 0.5;
        bbframe.metal = 0.4;
        for (let d = 0; d < N_DES; d++) {
            let o = this.newObj(this.cm("bb" + d.toString()), 10, 0x101012, 11 + d, 1);
            o.tex = 5 + d;
            this.bbObjs.push(o);
        }
        // (title visor removed: the curved visor treatment now lives on the in-car HUD)

        // billboards (picking + AR markers)
        for (let i = 0; i < City.bbN; i++) {
            let o = i * 8;
            let b = new BB();
            b.c = V(<f64>City.bb[o], <f64>City.bb[o + 1], <f64>City.bb[o + 2]);
            b.nx = <f64>City.bb[o + 3];
            b.nz = <f64>City.bb[o + 4];
            b.rx = b.nz;
            b.rz = -b.nx;
            b.w = <f64>City.bb[o + 5];
            b.h = <f64>City.bb[o + 6];
            b.design = <i32>City.bb[o + 7];
            this.bbs.push(b);
        }
        this.vlim = this.speedLimits();
        this.findSillyStop();

        // player exterior (back-face culled so the cabin sees out through it)
        let ext = this.carParts("car_", 0x17181C, 30, hex(0xFFA41C), true);   // dark graphite: the light bar pops
        for (let i = 0; i < ext.length; i++) {
            ext[i].ext = true;
            ext[i].cull = true;
        }
        this.ext = ext;
        this.extGlass = ext[4];

        // traffic (a few hero cars near the route; the swarm is instanced)
        for (let i = 1; i <= 4; i++) {
            this.addNpc(1, START_S + 60 + <f64>i * 230, 14 + <f64>i, 4.5, 0, 0, 0.55, 1, 1);
        }
        for (let i = 1; i <= 6; i++) {
            this.addNpc(2, START_S + 40 + <f64>i * 300, 15 + <f64>(i % 3) * 2, -4.5 - <f64>(i % 2) * 4.5, 0, 0, 0.55, -1, 1);
        }
        let alts: StaticArray<f64> = [13, 26, 41, 58];
        for (let i = 1; i <= 26; i++) {
            let axis = i % 2;
            let line = <f64>((i * 3) % (NB + 1)) * P + (i % 4 < 2 ? 4 : -4);
            let alt = alts[i % 4] + <f64>((i * 7) % 5) * 0.6;
            let dir: f64 = ((i / 2) % 2) == 0 ? 1 : -1;
            this.addNpc(3, <f64>((i * 137) % 1000) - 150, 22 + <f64>(i % 5) * 4, 0, axis, line, alt, dir, i % 7 == 0 ? 1.9 : 1);
        }

        // cockpit (sculpted, tools/make_car.py)
        this.cabMat("cab_leather", MAT_LEATHER, 0x2B2826);
        this.cabMat("cab_leather2", MAT_QUILT, 0x8A4824);
        this.cabMat("cab_suede", MAT_SUEDE, 0x34343A);
        this.cabMat("cab_soft", MAT_SOFT, 0x46413C);
        this.cabMat("cab_carbon", MAT_CARBON, 0x0A0A0A);
        this.cabMat("cab_metal", MAT_METAL, 0xA0A0A4);
        this.cabMat("cab_black", MAT_BLACK, 0x050505);
        this.cabMat("cab_grille", MAT_GRILLE, 0x101010);
        this.cabMat("cab_carpet", MAT_CARPET, 0x2C2C2F);
        this.cabMat("cab_tan", MAT_LEATHER, 0x8A4824);
        // driver's seat dissolves with the canopy as the intro camera flies in
        let ds1 = this.cabMat("dseat_leather", MAT_LEATHER, 0x2B2826);
        let ds2 = this.cabMat("dseat_leather2", MAT_QUILT, 0x8A4824);
        this.dseat = [ds1, ds2];
        let puck = this.cabObj("cab_puck", 9, 0x303236, 2);
        puck.fx[1] = 1;
        this.ambObj = this.cabObj("cab_amb", 9, 0x2A2B30, 2);
        // driver display
        let clBody = this.cabMat("cl_black", MAT_BLACK, 0x050505);
        let clTrim = this.cabMat("cl_metal", MAT_METAL, 0xA0A0A4);
        let clFace = this.cabObj("cl_face", 1, 0x060608, 2);
        clFace.tex = 1;
        this.clFace = clFace;
        this.clParts = [clBody, clTrim, clFace];
        // centre screen
        let csBody = this.cabMat("cs_black", MAT_BLACK, 0x050505);
        let csTrim = this.cabMat("cs_metal", MAT_METAL, 0xA0A0A4);
        let csFace = this.cabObj("cs_face", 1, 0x060608, 2);
        csFace.tex = 2;
        this.csFace = csFace;
        this.csParts = [csBody, csTrim, csFace];
        // yoke + hub
        let y1 = this.cabMat("yk_carbon", MAT_CARBON, 0x0A0A0A);
        let y2 = this.cabMat("yk_suede", MAT_SUEDE, 0x2C2C31);
        let y3 = this.cabMat("yk_leather", MAT_LEATHER, 0x2B2826);
        let y4 = this.cabMat("yk_black", MAT_BLACK, 0x050505);
        let y5 = this.cabMat("yk_metal", MAT_METAL, 0xA0A0A4);
        let y6 = this.cabMat("yk_tan", MAT_LEATHER, 0x8A4824);
        let hubF = this.cabObj("hub_face", 1, 0x060608, 2);
        hubF.tex = 3;
        this.hubFace = hubF;
        this.yokeParts = [y1, y2, y3, y4, y5, y6, hubF];
        // glass: HUD + windshield tint
        let hud = this.cabObj("hud", 20, 0, 3);
        hud.tex = 4;
        hud.accent = hex(0xFFA41C);
        this.hudObj = hud;
        this.glassObj = this.cabObj("wglass", 21, 0, 3);

        // start pose
        this.resetPose();
        let bld = this.cm("buildings");
        this.log("world: city " + (bld != null ? (bld.count / 3).toString() : "0") + " tris, " + this.objs.length.toString() +
            " objects, " + this.bbs.length.toString() + " billboards, route " + ROUTE_N.toString() + " m (AnimaScript)");
    }

    private cabId: i32 = COCKPIT_ID;

    private cabObj(mesh: string, mode: i32, day: u32, pass: i32): Obj {
        this.cabId++;
        let o = this.newObj(this.pm(mesh), mode, day, this.cabId, pass);
        o.rough = 0.62;
        this.cab.push(o);
        return o;
    }

    private cabMat(mesh: string, mat: f64, day: u32): Obj {
        let o = this.cabObj(mesh, 14, day, 2);
        o.fx[3] = mat;
        o.castCar = true;
        o.auxW = 2; // interior: cabin fill light
        return o;
    }

    private addNpc(kind: i32, s: f64, v: f64, off: f64, axis: i32, line: f64, alt: f64, dir: f64, scale: f64): void {
        let k = this.npcs.length + 1;
        let pc = NPC_PAINT[(k % 6) * 2];
        let thr = k % 3 == 0 ? hex(0x19F2FF) : (k % 3 == 1 ? hex(0xFFA41C) : hex(0xF30058));
        let n = new Npc();
        n.kind = kind;
        n.s = s;
        n.v = v;
        n.off = off;
        n.axis = axis;
        n.line = line;
        n.alt = alt;
        n.dir = dir;
        n.scale = scale;
        n.parts = this.carParts("npc_", pc, 40 + (k % 40) * 3, thr, false);
        this.npcs.push(n);
    }

    resetPose(): void {
        let p = routeAt(START_S);
        let f = routeDir(START_S);
        this.px = <f64>p.x;
        this.pz = <f64>p.z;
        this.yaw = yawOf(<f64>f.x, <f64>f.z);
        this.apS = START_S;
        this.origin = V(<f64>p.x, 0, <f64>p.z);
    }

    // ------------------------------------------------------------ GPU
    texDecoded(): void {
        this.texPending--;
        if (this.texPending == 0) {
            let vd = new GPUTextureViewDesc();
            vd.dimension = TextureViewDimension.array2D;
            let a = this.albTex;
            let n = this.nrmTex;
            if (a != null && n != null) {
                this.albV = a.view(vd);
                this.nrmV = n.view(vd);

                this.texReady = true;
                this.rebuildBindGroups();
                this.log("world: facade textures ready");
            }
        }
    }

    // facade photos: JPEG mip-chain atlases packed by tools/make_tex.py
    private loadTextures(): void {
        let ctx = this.context!;
        let data = ctx.blob("tex");
        if (data == null) {
            this.log("world: tex blob missing");
            return;
        }
        let count = <i32>Buffer.readu32(data, 0);
        let size = <u32>Buffer.readu32(data, 4);
        let mips = <u32>Buffer.readu32(data, 8);
        let layers = count / 2;
        let td = new GPUTextureDesc();
        td.width = size;
        td.height = size;
        td.depthOrArrayLayers = <u32>layers;
        td.textureType = TextureType.array2D;
        td.numMipmaps = mips;
        let alb = new GPUTexture(td);
        // the normal array also carries the window maps as extra layers (layers .. 2 * layers - 1, mip 0
        // only): the bind group has no spare texture slot (0-7)
        let wdata = ctx.blob("win");
        let wcount = wdata == null ? 0 : <i32>Buffer.readu32(wdata!, 0);
        let tdn = new GPUTextureDesc();
        tdn.width = size;
        tdn.height = size;
        tdn.depthOrArrayLayers = <u32>(layers + wcount);
        tdn.textureType = TextureType.array2D;
        tdn.numMipmaps = mips;
        let nrm = new GPUTexture(tdn);
        this.albTex = alb;
        this.nrmTex = nrm;
        // window maps: same container, PNG, mip 0 only, into the normal array's extra layers
        if (wdata != null && wcount > 0) {
            for (let k = 0; k < wcount; k++) {
                let off = <i32>Buffer.readu32(wdata!, <f64>(12 + k * 8));
                let len = <i32>Buffer.readu32(wdata!, <f64>(16 + k * 8));
                // first half: window maps (mip 0); second half: lit-window masks (mip-chain atlases)
                let mapHalf = wcount / 2;
                // PNG decodes are heavier than the JPEGs: queue them, one per frame (pumpTex)
                this.winQ.push(new WinDec(wdata!.slice(off, off + len), new TexDecode(this, nrm, <u32>(layers + k), k < mapHalf ? 1 : <i32>mips)));
            }
        }
        this.texPending = count + (wdata != null ? wcount : 0);
        for (let k = 0; k < count; k++) {
            let off = <i32>Buffer.readu32(data, <f64>(12 + k * 8));
            let len = <i32>Buffer.readu32(data, <f64>(16 + k * 8));
            let jb = data.slice(off, off + len);
            let tex = k < layers ? alb : nrm;
            ctx.decodeImage(jb, new TexDecode(this, tex, <u32>(k % layers)));
        }
    }

    private dummyArray(): GPUTextureView {
        return this.dummyArrayFill(150);
    }

    private dummyArrayFill(v: u8): GPUTextureView {
        let td = new GPUTextureDesc();
        td.width = 4;
        td.height = 4;
        td.depthOrArrayLayers = <u32>(TexInfo.layers * 3);    // + window maps + lit masks
        td.textureType = TextureType.array2D;
        let t = new GPUTexture(td);
        let white = new ArrayBuffer(64);
        Buffer.fill(white, 0, v);
        for (let l = 0; l < TexInfo.layers * 3; l++) {
            let reg = new rive_gpu_texture_upload_v1();
            reg.layer = <u32>l;
            reg.width = 4;
            reg.height = 4;
            t.upload(reg, white);
        }
        let vd = new GPUTextureViewDesc();
        vd.dimension = TextureViewDimension.array2D;
        return t.view(vd);
    }

    private depthTex(w: u32, h: u32, samples: u32): GPUTexture {
        let td = new GPUTextureDesc();
        td.width = w;
        td.height = h;
        td.format = TextureFormat.depth32float;
        td.renderTarget = true;
        td.sampleCount = samples;
        return new GPUTexture(td);
    }

    private hdrTex(w: u32, h: u32, samples: u32): GPUTexture {
        let td = new GPUTextureDesc();
        td.width = w;
        td.height = h;
        td.format = TextureFormat.rgba16float;
        td.renderTarget = true;
        td.sampleCount = samples;
        return new GPUTexture(td);
    }

    private depthOnly(t: GPUTexture): GPUTextureView {
        let vd = new GPUTextureViewDesc();
        vd.aspect = TextureAspect.depthOnly;
        return t.view(vd);
    }

    private createGPU(): bool {
        let ctx = this.context!;
        let gpu = ctx.gpuCanvas();
        if (gpu == null) {
            return false;
        }
        this.gpu = gpu;
        this.linSampler = new GPUSampler(Filter.linear, Filter.linear, Filter.nearest, WrapMode.clampToEdge, WrapMode.clampToEdge);
        this.texSampler = new GPUSampler(Filter.linear, Filter.linear, Filter.linear, WrapMode.repeat, WrapMode.repeat,
            <CompareFunction>0xFFFFFFFF, 8);
        let c = this.city!;
        let p = this.props!;
        // split over two frames: each host callback has its own 200 ms watchdog
        if (this.gpuStage == 0) {
            c.upload();
            this.gpuStage = 1;
            return false;
        }
        if (this.gpuStage == 1) {
            p.upload();
            this.gpuStage = 2;
            return false;
        }
        if (this.gpuStage == 2) {
        for (let i = 0; i < this.objs.length; i++) {
            this.objs[i].ubo = new GPUBuffer(BufferUsage.uniform, UBO_SIZE);
        }
        this.frameMain = new GPUBuffer(BufferUsage.uniform, FRAME_SIZE);
        this.frameRefl = new GPUBuffer(BufferUsage.uniform, FRAME_SIZE);
        this.frameCab = new GPUBuffer(BufferUsage.uniform, FRAME_SIZE);
        this.frameShadow = new GPUBuffer(BufferUsage.uniform, FRAME_SIZE);
        this.dummyUbo = new GPUBuffer(BufferUsage.uniform, UBO_SIZE);
        this.dummyV = this.hdrTex(4, 4, 1).view();
        this.albV = this.dummyArray();
        this.nrmV = this.dummyArray();

        // shadow atlas: city map [0, N) x [0, N), car map [N, N + CAR_SN) x [0, CAR_SN)
        let st = this.depthTex(SHADOW_N + CAR_SN, SHADOW_N, 1);
        this.shadowV = this.depthOnly(st);
        this.shadowAttV = st.view();
        this.shadowDummyV = this.depthOnly(this.depthTex(4, 4, 1));
        this.frameCarShadow = new GPUBuffer(BufferUsage.uniform, FRAME_SIZE);
        this.envUbo = new GPUBuffer(BufferUsage.uniform, 16);
            this.loadTextures();
            this.gpuStage = 3;
            return false;
        }
        if (this.gpuStage == 3) {
            // swarm instances come precomputed in the city pack (tools/make_city.py)
            let hoi = this.cm("holo_inst");
            if (hoi != null && hoi.vbuf != null) {
                this.holoBuf = hoi.vbuf;
                this.holoN = hoi.vcount;
                this.log("world: holo signs " + hoi.vcount.toString());
            }
            let sti = this.cm("steam_inst");
            if (sti != null && sti.vbuf != null) {
                this.steamBuf = sti.vbuf;
                this.steamN = sti.vcount;
                this.log("world: steam " + sti.vcount.toString() + " vents");
            }
            let si = this.cm("swarm_inst");
            if (si != null && si.vbuf != null) {
                this.swarmBuf = si.vbuf;
                this.swarmN = si.vcount;
                // CPU copy for the HUD trackers (same maths as vs_swarm)
                let nf = <i32>si.vcount * 8;
                let cpu = new StaticArray<f32>(nf);
                for (let q = 0; q < nf; q++) {
                    cpu[q] = <f32>Buffer.readf32(si.src, <f64>si.vOff + <f64>q * 4);
                }
                this.swCpu = cpu;
                this.log("world: swarm " + si.vcount.toString() + " cars");
            } else {
                this.buildSwarm();
            }
            this.gpuStage = 4;
            return false;
        }
        for (let i = 0; i < this.surfs.length; i++) {
            let sf = this.surfs[i];
            sf.canvas = ctx.canvas(<u32>Math.floor(sf.w * sf.density), <u32>Math.floor(sf.h * sf.density));
        }
        return true;
    }

    // swarm: thousands of hovercars streaming down every canyon at stacked altitudes
    private buildSwarm(): void {
        let heights: StaticArray<f64> = [14, 24, 36, 47, 76, 88, 100, 116, 160, 178, 200, 230, 265, 300];
        let lo = <f64>City.LO * P;
        let hi = <f64>City.HI * P;
        let len = hi - lo;
        let MAXN = 9000;
        let inst = new ArrayBuffer(MAXN * 32);
        let f = new Float32Array(MAXN * 8);
        let n = 0;
        let rs: f64 = 1;
        for (let axis = 0; axis < 2; axis++) {
            for (let li = City.LO; li <= City.HI; li++) {
                let line = <f64>li * P;
                for (let hk = 0; hk < heights.length; hk++) {
                    for (let side = -1; side <= 1; side += 2) {
                        rs = (rs * 16807) % 2147483647;
                        let cnt = 4 + <i32>Math.floor(rs / 2147483647 * 8);
                        rs = (rs * 16807) % 2147483647;
                        let off = <f64>side * (3 + rs / 2147483647 * 6);
                        rs = (rs * 16807) % 2147483647;
                        let spd = 22 + rs / 2147483647 * 26;
                        rs = (rs * 16807) % 2147483647;
                        let yy = heights[hk] + rs / 2147483647 * 3;
                        for (let q = 0; q < cnt; q++) {
                            if (n < MAXN) {
                                let o = n * 8;
                                let cx = axis == 0 ? (lo + hi) / 2 : line + off;
                                let cz = axis == 0 ? line + off : (lo + hi) / 2;
                                rs = (rs * 16807) % 2147483647;
                                let sv = spd * (0.92 + rs / 2147483647 * 0.16);
                                rs = (rs * 16807) % 2147483647;
                                // scatter around the lane so traffic fills the canyon volume
                                rs = (rs * 16807) % 2147483647;
                                let jy = (rs / 2147483647 - 0.5) * 9;
                                rs = (rs * 16807) % 2147483647;
                                let jl = (rs / 2147483647 - 0.5) * 4;
                                f[o] = <f32>(cx + (axis == 1 ? jl : 0));
                                f[o + 1] = <f32>(yy + jy);
                                f[o + 2] = <f32>(cz + (axis == 0 ? jl : 0));
                                f[o + 3] = <f32>sv;
                                f[o + 4] = <f32>axis;
                                f[o + 5] = <f32>side;
                                f[o + 6] = <f32>len;
                                f[o + 7] = <f32>(rs / 2147483647);
                                n++;
                            }
                        }
                    }
                }
            }
        }
        let bytes = f.buffer.slice(0, n * 32);
        this.swarmBuf = new GPUBuffer(BufferUsage.vertex, <u32>(n * 32), bytes, true);
        this.swarmN = <u32>n;
        this.log("world: swarm " + n.toString() + " cars");
        inst = bytes;
    }

    private layout32(): GPUVertexBufferLayout {
        let l = new GPUVertexBufferLayout();
        l.stride = 32;
        l.attributes = [
            new GPUVertexAttribute(VertexFormat.float3, 0, 0),
            new GPUVertexAttribute(VertexFormat.float3, 1, 12),
            new GPUVertexAttribute(VertexFormat.float2, 2, 24),
        ];
        return l;
    }

    private depthState(write: bool): GPUDepthStencilDesc {
        let d = new GPUDepthStencilDesc();
        d.format = TextureFormat.depth32float;
        d.compare = CompareFunction.lessEqual;
        d.write = write;
        return d;
    }

    private target(fmt: TextureFormat, blend: GPUBlendState?): GPUColorTargetDesc {
        let t = new GPUColorTargetDesc();
        t.format = fmt;
        t.blend = blend;
        return t;
    }

    private pipe(lit: GPUShaderModule, vs: string, fs: string, vtx: Array<GPUVertexBufferLayout>, color: Array<GPUColorTargetDesc>,
                 depth: GPUDepthStencilDesc?, cull: CullMode, samples: u32, shared: bool): GPUPipeline {
        let d = new GPUPipelineDesc();
        d.vertexModule = lit;
        d.vertexEntryPoint = vs;
        if (fs.length > 0) {
            d.fragmentModule = lit;
            d.fragmentEntryPoint = fs;
        }
        d.vertexBuffers = vtx;
        d.colorTargets = color;
        d.depthStencil = depth;
        d.cullMode = cull;
        d.sampleCount = samples;
        if (shared) {
            d.bindGroupLayouts = [this.bgl];
        }
        return new GPUPipeline(d);
    }

    private makePipelines(): bool {
        let ctx = this.context!;
        let lit = ctx.shader("lit");
        let brS = ctx.shader("bright");
        let blS = ctx.shader("blur");
        let fiS = ctx.shader("final");
        let taS = ctx.shader("taa");
        if (lit == null || brS == null || blS == null || fiS == null || taS == null) {
            this.log("world: shader missing lit=" + (lit == null ? "NULL" : "ok") + " bright=" + (brS == null ? "NULL" : "ok") +
                " blur=" + (blS == null ? "NULL" : "ok") + " final=" + (fiS == null ? "NULL" : "ok") + " taa=" + (taS == null ? "NULL" : "ok"));
            return false;
        }
        this.bgl = GPUBindGroupLayout.fromShader(lit, 0);
        let L = [this.layout32()];
        let HDR = TextureFormat.rgba16float;
        let dW = this.depthState(true);
        let dR = this.depthState(false);
        this.litMS = this.pipe(lit, "vs_main", "fs_main", L, [this.target(HDR, null)], dW, CullMode.none, 4, true);
        this.litMSCull = this.pipe(lit, "vs_main", "fs_main", L, [this.target(HDR, null)], dW, CullMode.back, 4, true);
        this.litR = this.pipe(lit, "vs_main", "fs_main", L, [this.target(HDR, null)], dW, CullMode.none, 1, true);
        let keep = new GPUBlendState();
        keep.srcColor = BlendFactor.zero;
        keep.dstColor = BlendFactor.one;
        keep.srcAlpha = BlendFactor.zero;
        keep.dstAlpha = BlendFactor.one;
        this.depthMS = this.pipe(lit, "vs_main", "fs_depth", L, [this.target(HDR, keep)], dW, CullMode.none, 4, true);
        let inst = new GPUVertexBufferLayout();
        inst.stride = 32;
        inst.stepMode = VertexStepMode.instance;
        inst.attributes = [new GPUVertexAttribute(VertexFormat.float4, 3, 0), new GPUVertexAttribute(VertexFormat.float4, 4, 16)];
        this.swarmPipe = this.pipe(lit, "vs_swarm", "fs_swarm", [this.layout32(), inst], [this.target(HDR, null)], dW, CullMode.back, 4, true);
        this.shadowPipe = this.pipe(lit, "vs_main", "", L, [], this.depthState(true), CullMode.none, 1, true);
        let ginst = new GPUVertexBufferLayout();
        ginst.stride = 32;
        ginst.stepMode = VertexStepMode.instance;
        ginst.attributes = [new GPUVertexAttribute(VertexFormat.float4, 3, 0), new GPUVertexAttribute(VertexFormat.float4, 4, 16)];
        this.greebleMS = this.pipe(lit, "vs_greeble", "fs_greeble", [this.layout32(), ginst], [this.target(HDR, null)], dW, CullMode.back, 4, true);
        let ginst2 = new GPUVertexBufferLayout();
        ginst2.stride = 32;
        ginst2.stepMode = VertexStepMode.instance;
        ginst2.attributes = [new GPUVertexAttribute(VertexFormat.float4, 3, 0), new GPUVertexAttribute(VertexFormat.float4, 4, 16)];
        this.greebleShadow = this.pipe(lit, "vs_greeble", "", [this.layout32(), ginst2], [], this.depthState(true), CullMode.none, 1, true);
        let always = new GPUDepthStencilDesc();
        always.format = TextureFormat.depth32float;
        always.compare = CompareFunction.always;
        always.write = true;
        this.clearPipe = this.pipe(lit, "vs_clear", "", [], [], always, CullMode.none, 1, true);
        this.skyMS = this.pipe(lit, "vs_sky", "fs_sky", [], [this.target(HDR, null)], dR, CullMode.none, 4, true);
        this.skyR = this.pipe(lit, "vs_sky", "fs_sky", [], [this.target(HDR, null)], dR, CullMode.none, 1, true);
        let add = new GPUBlendState();
        add.srcColor = BlendFactor.one;
        add.dstColor = BlendFactor.one;
        add.srcAlpha = BlendFactor.zero;
        add.dstAlpha = BlendFactor.one;
        this.rainMS = this.pipe(lit, "vs_rain", "fs_rain", [], [this.target(HDR, add)], dR, CullMode.none, 4, true);
        // steam: premultiplied over, alpha (encoded distance) untouched
        let pre = new GPUBlendState();
        pre.srcColor = BlendFactor.one;
        pre.dstColor = BlendFactor.oneMinusSrcAlpha;
        pre.srcAlpha = BlendFactor.zero;
        pre.dstAlpha = BlendFactor.one;
        let sinst = new GPUVertexBufferLayout();
        sinst.stride = 32;
        sinst.stepMode = VertexStepMode.instance;
        sinst.attributes = [new GPUVertexAttribute(VertexFormat.float4, 3, 0), new GPUVertexAttribute(VertexFormat.float4, 4, 16)];
        this.steamMS = this.pipe(lit, "vs_steam", "fs_steam", [sinst], [this.target(HDR, pre)], dR, CullMode.none, 4, true);
        this.holoMS = this.pipe(lit, "vs_holo", "fs_holo", [sinst], [this.target(HDR, add)], dR, CullMode.none, 4, true);
        let add2 = new GPUBlendState();
        add2.srcColor = BlendFactor.one;
        add2.dstColor = BlendFactor.one;
        add2.srcAlpha = BlendFactor.zero;
        add2.dstAlpha = BlendFactor.one;
        this.coneMS = this.pipe(lit, "vs_main", "fs_cone", L, [this.target(HDR, add2)], dR, CullMode.none, 4, true);
        let over = new GPUBlendState();
        over.srcColor = BlendFactor.one;
        over.dstColor = BlendFactor.oneMinusSrcAlpha;
        over.srcAlpha = BlendFactor.zero;
        over.dstAlpha = BlendFactor.one;
        this.glassMS = this.pipe(lit, "vs_main", "fs_glass", L, [this.target(HDR, over)], dR, CullMode.none, 4, true);
        let hudB = new GPUBlendState();
        hudB.srcColor = BlendFactor.one;
        hudB.dstColor = BlendFactor.one;
        hudB.srcAlpha = BlendFactor.one;
        hudB.dstAlpha = BlendFactor.one;
        hudB.alphaOp = BlendOp.min;
        this.hudMS = this.pipe(lit, "vs_main", "fs_glass", L, [this.target(HDR, hudB)], dR, CullMode.none, 4, true);
        // title holo backing: multiply (smoked glass) + min alpha (TAA cockpit tag)
        let mulB = new GPUBlendState();
        mulB.srcColor = BlendFactor.zero;
        mulB.dstColor = BlendFactor.srcColor;
        mulB.srcAlpha = BlendFactor.one;
        mulB.dstAlpha = BlendFactor.one;
        mulB.alphaOp = BlendOp.min;
        this.holoBackMS = this.pipe(lit, "vs_main", "fs_glass", L, [this.target(HDR, mulB)], dR, CullMode.none, 4, true);
        this.brightPipe = this.pipe(brS, "vs_full", "fs_bright", [], [this.target(HDR, null)], null, CullMode.none, 1, false);
        this.blurPipe = this.pipe(blS, "vs_full", "fs_blur", [], [this.target(HDR, null)], null, CullMode.none, 1, false);
        let gpu = this.gpu!;
        this.finalPipe = this.pipe(fiS, "vs_full", "fs_final", [], [this.target(<TextureFormat>gpu.format, null)], null, CullMode.none, 1, false);
        this.downUbos = [];
        for (let i = 0; i < 3; i++) {
            this.downUbos.push(new GPUBuffer(BufferUsage.uniform, 16));
        }
        this.blUbos = [];
        for (let i = 0; i < 6; i++) {
            this.blUbos.push(new GPUBuffer(BufferUsage.uniform, 16));
        }
        this.finUbo = new GPUBuffer(BufferUsage.uniform, 96);
        let shS = ctx.shader("shafts");
        if (shS != null) {
            this.shaftPipe = this.pipe(shS!, "vs_full", "fs_shafts", [], [this.target(HDR, null)], null, CullMode.none, 1, false);
            this.shaftUbo = new GPUBuffer(BufferUsage.uniform, 16);
        }
        this.taaPipe = this.pipe(taS!, "vs_full", "fs_taa", [], [this.target(HDR, null)], null, CullMode.none, 1, false);
        this.taaUbo = new GPUBuffer(BufferUsage.uniform, 160);
        return true;
    }

    private objBG(ubo: GPUBuffer, frame: GPUBuffer, tv: GPUTextureView, rv: GPUTextureView, shadowPass: bool): GPUBindGroup {
        return new GPUBindGroup(this.bgl!,
            [new GPUBindGroupUBO(0, ubo), new GPUBindGroupUBO(3, frame)],
            [
                new GPUBindGroupTexture(1, tv),
                new GPUBindGroupTexture(4, rv),
                new GPUBindGroupTexture(5, this.albV!),
                new GPUBindGroupTexture(6, this.nrmV!),
                new GPUBindGroupTexture(7, shadowPass ? this.shadowDummyV! : this.shadowV!),
            ],
            [new GPUBindGroupSampler(2, this.texSampler!)]);
    }

    private casts(o: Obj): bool {
        return o.pass == 1 && (o.mode == 2 || o.id == 9 || o.id == 10);
    }

    rebuildBindGroups(): void {
        if (this.bgl == null || this.frameMain == null || this.dummyV == null) {
            return;
        }
        let views = new Array<GPUTextureView?>(this.surfs.length + 1);
        for (let i = 0; i < this.surfViews.length; i++) {
            this.surfViews[i].release();
        }
        this.surfViews = [];
        for (let k = 0; k < this.surfs.length; k++) {
            let c = this.surfs[k].canvas;
            if (c != null) {
                let sv = c.image.view()!;
                this.surfViews.push(sv);
                views[k + 1] = sv;
            }
        }
        let fallback = views[1];
        if (fallback == null) {
            return;
        }
        let dummy = this.dummyV!;
        let rv = this.reflV;
        let reflV = rv != null ? rv : dummy;
        let fm = this.frameMain!;
        let fr = this.frameRefl!;
        let fc = this.frameCab!;
        let fs = this.frameShadow!;
        let fcs = this.frameCarShadow!;
        let ev = this.envV;
        let envV = ev != null ? ev : dummy;
        // release the previous set: every rebuild/resize used to leak ~800 GPU handles
        for (let i = 0; i < this.objs.length; i++) {
            let o = this.objs[i];
            relBG(o.bg);
            relBG(o.bgR);
            relBG(o.bgC);
            relBG(o.bgS);
            relBG(o.bgCS);
            o.bg = null;
            o.bgR = null;
            o.bgC = null;
            o.bgS = null;
            o.bgCS = null;
        }
        relBG(this.skyBG);
        relBG(this.skyRBG);
        relBG(this.shadowSkyBG);
        for (let i = 0; i < this.objs.length; i++) {
            let o = this.objs[i];
            let tv = fallback;
            if (o.tex > 0 && o.tex < views.length) {
                let vv = views[o.tex];
                if (vv != null) {
                    tv = vv;
                }
            }
            let ubo = o.ubo!;
            let road = o.mode == 3 || o.mode == 4 || o.mode == 13;
            o.bg = this.objBG(ubo, fm, tv, road ? reflV : (o.envMap ? envV : dummy), false);
            if (o.refl) {
                o.bgR = this.objBG(ubo, fr, tv, dummy, false);
            }
            if (o.pass >= 2) {
                o.bgC = this.objBG(ubo, fc, tv, dummy, false);
            }
            if (this.casts(o)) {
                o.bgS = this.objBG(ubo, fs, tv, dummy, true);
            }
            if (o.castCar) {
                o.bgCS = this.objBG(ubo, fcs, tv, dummy, true);
            }
        }
        let du = this.dummyUbo!;
        this.skyBG = this.objBG(du, fm, fallback, dummy, false);
        this.skyRBG = this.objBG(du, fr, fallback, dummy, false);
        this.shadowSkyBG = this.objBG(du, fs, fallback, dummy, true);
    }

    private postBG(pipe: GPUPipeline, ubo: GPUBuffer, src: GPUTextureView): GPUBindGroup {
        return new GPUBindGroup(pipe.getBindGroupLayout(0), [new GPUBindGroupUBO(0, ubo)], [new GPUBindGroupTexture(1, src)],
            [new GPUBindGroupSampler(2, this.linSampler!)]);
    }

    private rtTexs: Array<GPUTexture> = [];
    private surfViews: Array<GPUTextureView> = [];
    private rtViews: Array<GPUTextureView> = [];
    private rtBGs: Array<GPUBindGroup> = [];

    private rtH(w: u32, h: u32, samples: u32): GPUTexture {
        let t = this.hdrTex(w, h, samples);
        this.rtTexs.push(t);
        return t;
    }

    private rtD(w: u32, h: u32, samples: u32): GPUTexture {
        let t = this.depthTex(w, h, samples);
        this.rtTexs.push(t);
        return t;
    }

    private rtV(t: GPUTexture): GPUTextureView {
        let v = t.view();
        this.rtViews.push(v);
        return v;
    }

    private rtDV(t: GPUTexture): GPUTextureView {
        let v = this.depthOnly(t);
        this.rtViews.push(v);
        return v;
    }

    private rtBG(b: GPUBindGroup): GPUBindGroup {
        this.rtBGs.push(b);
        return b;
    }

    private doResize(): void {
        let gpu = this.gpu;
        if (gpu == null) {
            return;
        }
        let scale = this.hostScale;
        this.outScale = clamp(Math.max(scale, 1.0), 1, 2);
        // MSAA 4x on top of this; 1.5x on Retina is plenty
        this.gScale = Math.min(this.dynScale, scale > 1.5 ? scale : 1.25);
        let ow = <u32>Math.max(1, Math.floor(this.sizeX * this.outScale));
        let oh = <u32>Math.max(1, Math.floor(this.sizeY * this.outScale));
        this.gw = <i32>Math.max(4, Math.floor(this.sizeX * this.gScale));
        this.gh = <i32>Math.max(4, Math.floor(this.sizeY * this.gScale));
        gpu.resize(ow, oh);
        if (this.litMS == null) {
            if (!this.makePipelines()) {
                return;
            }
        }
        // free the previous size's targets + bind groups (each dynamic-resolution
        // step used to leak every render target: hundreds of MB at Retina)
        for (let i = 0; i < this.rtBGs.length; i++) {
            this.rtBGs[i].release();
        }
        for (let i = 0; i < this.rtViews.length; i++) {
            this.rtViews[i].release();
        }
        for (let i = 0; i < this.rtTexs.length; i++) {
            this.rtTexs[i].release();
        }
        this.rtBGs = [];
        this.rtViews = [];
        this.rtTexs = [];
        let gw = <u32>this.gw;
        let gh = <u32>this.gh;
        this.hdrMSV = this.rtV(this.rtH(gw, gh, 4));
        this.depthMSV = this.rtDV(this.rtD(gw, gh, 4));
        this.hdrV = this.rtV(this.rtH(gw, gh, 1));
        this.rw = <i32>Math.max(2, Math.floor(<f64>gw / this.reflDiv));
        this.rh = <i32>Math.max(2, Math.floor(<f64>gh / this.reflDiv));
        this.reflV = this.rtV(this.rtH(<u32>this.rw, <u32>this.rh, 1));
        this.reflDepthV = this.rtDV(this.rtD(<u32>this.rw, <u32>this.rh, 1));
        this.b1w = <i32>Math.max(2, gw / 4);
        this.b1h = <i32>Math.max(2, gh / 4);
        this.b2w = <i32>Math.max(2, gw / 8);
        this.b2h = <i32>Math.max(2, gh / 8);
        this.b3w = <i32>Math.max(2, gw / 16);
        this.b3h = <i32>Math.max(2, gh / 16);
        this.b1V = this.rtV(this.rtH(<u32>this.b1w, <u32>this.b1h, 1));
        this.b1tV = this.rtV(this.rtH(<u32>this.b1w, <u32>this.b1h, 1));
        this.b2V = this.rtV(this.rtH(<u32>this.b2w, <u32>this.b2h, 1));
        this.b2tV = this.rtV(this.rtH(<u32>this.b2w, <u32>this.b2h, 1));
        this.b3V = this.rtV(this.rtH(<u32>this.b3w, <u32>this.b3h, 1));
        this.b3tV = this.rtV(this.rtH(<u32>this.b3w, <u32>this.b3h, 1));
        this.envV = this.rtV(this.rtH(<u32>this.b1w, <u32>this.b1h, 1));
        this.shaftV = this.rtV(this.rtH(<u32>this.b1w, <u32>this.b1h, 1));
        if (this.shaftPipe != null) {
            this.shaftBG = this.rtBG(this.postBG(this.shaftPipe!, this.shaftUbo!, this.hdrV!));
        }
        this.envFrames = 0;
        this.rebuildBindGroups();
        let bp = this.brightPipe!;
        let lp = this.blurPipe!;
        this.downBGs = [
            this.rtBG(this.postBG(bp, this.downUbos[0], this.hdrV!)),
            this.rtBG(this.postBG(bp, this.downUbos[1], this.b1V!)),
            this.rtBG(this.postBG(bp, this.downUbos[2], this.b2V!)),
        ];
        this.blBGs = [
            this.rtBG(this.postBG(lp, this.blUbos[0], this.b1V!)),
            this.rtBG(this.postBG(lp, this.blUbos[1], this.b1tV!)),
            this.rtBG(this.postBG(lp, this.blUbos[2], this.b2V!)),
            this.rtBG(this.postBG(lp, this.blUbos[3], this.b2tV!)),
            this.rtBG(this.postBG(lp, this.blUbos[4], this.b3V!)),
            this.rtBG(this.postBG(lp, this.blUbos[5], this.b3tV!)),
        ];
        this.envBG = this.rtBG(this.postBG(bp, this.envUbo!, this.hdrV!));
        let fp = this.finalPipe!;
        this.finBG = this.rtBG(new GPUBindGroup(fp.getBindGroupLayout(0), [new GPUBindGroupUBO(0, this.finUbo!)],
            [
                new GPUBindGroupTexture(1, this.hdrV!),
                new GPUBindGroupTexture(2, this.b1V!),
                new GPUBindGroupTexture(3, this.b2V!),
                new GPUBindGroupTexture(4, this.b3V!),
                new GPUBindGroupTexture(6, this.shaftV!),
            ],
            [new GPUBindGroupSampler(5, this.linSampler!)]));
        // TAA ping-pong: taaV[k] is written from hdrV + history taaV[1 - k]
        this.taaV = [this.rtV(this.rtH(gw, gh, 1)), this.rtV(this.rtH(gw, gh, 1))];
        let tp_ = this.taaPipe!;
        this.taaBG = [];
        this.finBGs = [];
        for (let k = 0; k < 2; k++) {
            this.taaBG.push(this.rtBG(new GPUBindGroup(tp_.getBindGroupLayout(0), [new GPUBindGroupUBO(0, this.taaUbo!)],
                [new GPUBindGroupTexture(1, this.hdrV!), new GPUBindGroupTexture(2, this.taaV[1 - k])],
                [new GPUBindGroupSampler(3, this.linSampler!)])));
            this.finBGs.push(this.rtBG(new GPUBindGroup(fp.getBindGroupLayout(0), [new GPUBindGroupUBO(0, this.finUbo!)],
                [
                    new GPUBindGroupTexture(1, this.taaV[k]),
                    new GPUBindGroupTexture(2, this.b1V!),
                    new GPUBindGroupTexture(3, this.b2V!),
                    new GPUBindGroupTexture(4, this.b3V!),
                    new GPUBindGroupTexture(6, this.shaftV!),
                ],
                [new GPUBindGroupSampler(5, this.linSampler!)])));
        }
        this.taaValid = false;
    }

    private trySetup(): void {
        let t0 = clock();
        let st = this.loadStage;
        let done = this.stageLoad();
        if (st < 5) {
            this.log("load: stage " + st.toString() + " " + ((clock() - t0) * 1000).toString() + " ms");
        }
        if (!done) {
            return;
        }
        if (this.city == null || this.context == null) {
            return;
        }
        if (!this.gpuReady) {
            let t1 = clock();
            let gs = this.gpuStage;
            let ok = this.createGPU();
            this.log("load: createGPU." + gs.toString() + " " + ((clock() - t1) * 1000).toString() + " ms");
            if (!ok) {
                return;
            }
            this.gpuReady = true;
            this.needsResize = true;
        }
        if (this.needsResize && this.sizeX > 0) {
            this.needsResize = false;
            let t2 = clock();
            this.doResize();
            this.log("load: resize " + ((clock() - t2) * 1000).toString() + " ms");
        }
    }

    override resize(width: f64, height: f64, scale: f64): void {
        this.sizeX = width;
        this.sizeY = height;
        this.hostScale = scale;
        this.needsResize = true;
        this.trySetup();
    }

    // ------------------------------------------------------------ driving
    private nearestS(x: f64, z: f64): f64 {
        let best = this.apS;
        let bd: f64 = 1e18;
        for (let d = -40; d <= 60; d++) {
            let s = wrapS(Math.floor(this.apS) + <f64>d);
            let r = routeAt(s);
            let dd = (<f64>r.x - x) * (<f64>r.x - x) + (<f64>r.z - z) * (<f64>r.z - z);
            if (dd < bd) {
                bd = dd;
                best = s;
            }
        }
        if (bd > 900) {
            // far off route (manual driving): global search
            for (let s = 0; s < ROUTE_N; s += 3) {
                let r = routeAt(<f64>s);
                let dd = (<f64>r.x - x) * (<f64>r.x - x) + (<f64>r.z - z) * (<f64>r.z - z);
                if (dd < bd) {
                    bd = dd;
                    best = <f64>s;
                }
            }
        }
        return best;
    }

    // ---- building collision: boxes from tools/make_city.py (coll_inst), bucketed in a grid
    collB: StaticArray<f32> = new StaticArray<f32>(0);
    collStart: StaticArray<i32> = new StaticArray<i32>(0);
    collItems: StaticArray<i32> = new StaticArray<i32>(0);
    collNX: i32 = 0;
    collNZ: i32 = 0;
    collX0: f64 = 0;
    collZ0: f64 = 0;
    collCS: f64 = 24;

    private collCnt: StaticArray<i32> = new StaticArray<i32>(1);
    private collState: i32 = 0;
    private collI: i32 = 0;
    private collN: i32 = 0;

    // incremental under a per-frame time budget: the host watchdog is 200 ms per
    // callback and a loaded machine (editors open) runs this 5-8x slower
    collStep(): bool {
        let t0 = clock();
        let budget = 0.03;
        if (this.collState == 0) {
            let m = this.cm("coll_inst");
            if (m == null) {
                this.log("world: no collision boxes");
                this.collState = 3;
                return true;
            }
            let n = <i32>m.vcount;
            this.collN = n;
            this.collB = new StaticArray<f32>(n * 6);
            this.collX0 = -P - 60;
            this.collZ0 = -P - 60;
            let size = <f64>(NB + 2) * P + 120;
            let nx = <i32>Math.ceil(size / this.collCS);
            this.collNX = nx;
            this.collNZ = nx;
            this.collCnt = new StaticArray<i32>(nx * nx + 1);
            this.collI = 0;
            this.collState = 1;
        }
        if (this.collState == 1) {
            let m = this.cm("coll_inst")!;
            let src = m.src;
            let b = this.collB;
            while (this.collI < this.collN) {
                let i = this.collI;
                let o = <f64>m.vOff + <f64>i * 32;
                for (let j = 0; j < 6; j++) {
                    b[i * 6 + j] = <f32>Buffer.readf32(src, o + <f64>j * 4);
                }
                this.collI++;
                if ((i & 255) == 0 && clock() - t0 > budget) {
                    return false;
                }
            }
            this.collI = 0;
            this.collState = 2;
        }
        if (this.collState == 2) {
            if (!this.collPassStep(0, t0, budget)) {
                return false;
            }
            let nx = this.collNX;
            let cnt = this.collCnt;
            for (let c = 0; c < nx * nx; c++) {
                cnt[c + 1] += cnt[c];
            }
            this.collStart = new StaticArray<i32>(nx * nx + 1);
            for (let c = 0; c <= nx * nx; c++) {
                this.collStart[c] = cnt[c];
            }
            this.collItems = new StaticArray<i32>(cnt[nx * nx]);
            this.collI = 0;
            this.collState = 3;
        }
        if (this.collState == 3) {
            if (!this.collPassStep(1, t0, budget)) {
                return false;
            }
            this.collState = 4;
            this.log("world: collision " + this.collN.toString() + " boxes, " + this.collItems.length.toString() + " grid refs");
        }
        return true;
    }

    private collPassStep(pass: i32, t0: f64, budget: f64): bool {
        let b = this.collB;
        let n = this.collN;
        let nx = this.collNX;
        let cnt = this.collCnt;
        while (this.collI < n) {
            let i = this.collI;
            let cx0 = <i32>Math.floor((<f64>b[i * 6] - 2 - this.collX0) / this.collCS);
            let cx1 = <i32>Math.floor((<f64>b[i * 6 + 3] + 2 - this.collX0) / this.collCS);
            let cz0 = <i32>Math.floor((<f64>b[i * 6 + 2] - 2 - this.collZ0) / this.collCS);
            let cz1 = <i32>Math.floor((<f64>b[i * 6 + 5] + 2 - this.collZ0) / this.collCS);
            cx0 = <i32>Math.max(0, cx0);
            cz0 = <i32>Math.max(0, cz0);
            cx1 = <i32>Math.min(nx - 1, cx1);
            cz1 = <i32>Math.min(nx - 1, cz1);
            for (let cz = cz0; cz <= cz1; cz++) {
                for (let cx = cx0; cx <= cx1; cx++) {
                    let c = cz * nx + cx;
                    if (pass == 0) {
                        cnt[c + 1] = cnt[c + 1] + 1;
                    } else {
                        this.collItems[cnt[c]] = i;
                        cnt[c] = cnt[c] + 1;
                    }
                }
            }
            this.collI++;
            if ((i & 255) == 0 && clock() - t0 > budget) {
                return false;
            }
        }
        this.collI = 0;
        return true;
    }

    private collide(): void {
        // hovercar vs buildings at the current altitude: push out, slide along walls
        let r: f64 = 1.7;
        let y0 = this.alt + 0.15;
        let y1 = this.alt + 1.5;
        let fx = Math.sin(this.yaw);
        let fz = -Math.cos(this.yaw);
        let hitNX: f64 = 0;
        let hitNZ: f64 = 0;
        let hits = 0;
        if (this.collState == 4) {   // the grid is built over several frames (collStep)
            for (let it = 0; it < 2; it++) {
                let gx = <i32>Math.floor((this.px - this.collX0) / this.collCS);
                let gz = <i32>Math.floor((this.pz - this.collZ0) / this.collCS);
                if (gx < 0 || gz < 0 || gx >= this.collNX || gz >= this.collNZ) {
                    break;
                }
                let c = gz * this.collNX + gx;
                let b = this.collB;
                for (let k = this.collStart[c]; k < this.collStart[c + 1]; k++) {
                    let i = this.collItems[k] * 6;
                    if (<f64>b[i + 4] < y0 || <f64>b[i + 1] > y1) {
                        continue;
                    }
                    let bx0 = <f64>b[i] - 0.6;
                    let bz0 = <f64>b[i + 2] - 0.6;
                    let bx1 = <f64>b[i + 3] + 0.6;
                    let bz1 = <f64>b[i + 5] + 0.6;
                    let qx = clamp(this.px, bx0, bx1);
                    let qz = clamp(this.pz, bz0, bz1);
                    let dx = this.px - qx;
                    let dz = this.pz - qz;
                    let d2 = dx * dx + dz * dz;
                    if (d2 >= r * r) {
                        continue;
                    }
                    let nx: f64 = 0;
                    let nz: f64 = 0;
                    let pen: f64 = 0;
                    if (d2 < 1e-8) {
                        // centre inside the box: leave by the nearest face
                        let l = this.px - bx0;
                        let rr = bx1 - this.px;
                        let tt = this.pz - bz0;
                        let bb = bz1 - this.pz;
                        let mn = Math.min(Math.min(l, rr), Math.min(tt, bb));
                        if (mn == l) {
                            nx = -1;
                        } else if (mn == rr) {
                            nx = 1;
                        } else if (mn == tt) {
                            nz = -1;
                        } else {
                            nz = 1;
                        }
                        pen = mn + r;
                    } else {
                        let d = Math.sqrt(d2);
                        nx = dx / d;
                        nz = dz / d;
                        pen = r - d;
                    }
                    this.px += nx * pen;
                    this.pz += nz * pen;
                    hitNX += nx;
                    hitNZ += nz;
                    hits++;
                }
            }
        }
        if (hits > 0) {
            let l = Math.sqrt(hitNX * hitNX + hitNZ * hitNZ);
            if (l > 1e-6) {
                let nx = hitNX / l;
                let nz = hitNZ / l;
                let into = -(fx * nx + fz * nz); // 1 = head-on
                if (into > 0) {
                    if (into > 0.75 && this.v > 7) {
                        this.bump = 1;
                    }
                    this.v *= 1 - 0.5 * into * into * into;
                    // turn along the wall so the car slides instead of sticking
                    let tx = -nz;
                    let tz = nx;
                    if (tx * fx + tz * fz < 0) {
                        tx = -tx;
                        tz = -tz;
                    }
                    let want = yawOf(tx, tz);
                    this.yaw = wrapAng(this.yaw + wrapAng(want - this.yaw) * 0.3 * into);
                }
            }
        }
        this.px = clamp(this.px, -P + 2, <f64>NB * P + P - 2);
        this.pz = clamp(this.pz, -P + 2, <f64>NB * P + P - 2);
    }

    // route distance (m) still to go to the SillyScroll stop; just-passed counts as 0
    private sillyAhead(): f64 {
        let d = wrapS(this.sillyS - this.apS);
        return d > <f64>ROUTE_N - 6 ? 0 : d;
    }

    // render quality: 0 HIGH (default), 1 MED, 2 LOW
    quality: i32 = 0;

    private setQuality(q: i32): void {
        this.quality = q;
        this.setN("qs0", q == 0 ? 1 : 0);
        this.setN("qs1", q == 1 ? 1 : 0);
        this.setN("qs2", q == 2 ? 1 : 0);
        this.applyQuality();
    }

    private applyQuality(): void {
        let q = this.quality;
        this.dynMin = q == 0 ? 1.0 : (q == 1 ? 0.85 : 0.7);
        this.dynMax = q == 0 ? 2.0 : (q == 1 ? 1.5 : 1.0);
        this.reflDiv = q == 0 ? 3 : (q == 1 ? 4 : 5);
        this.swarmFrac = q == 2 ? 0.6 : 1;
        this.dynScale = clamp(this.dynScale, this.dynMin, this.dynMax);
        this.needsResize = true;
    }

    private setAutopilot(on: bool): void {
        if (on && !this.autopilot) {
            this.lookHome = true;
        }
        this.autopilot = on;
    }

    private togglePlay(): void {
        if (!this.sillyOk || !this.entered) {
            return;
        }
        if (this.play > 0) {
            this.play = 0;
            this.setAutopilot(true);
            return;
        }
        this.play = 1;
        this.setAutopilot(true);
    }

    private drive(dt: f64): void {
        let k = this.keys;
        let up = k[KEY_UP] || k[KEY_W];
        let dn = k[KEY_DOWN] || k[KEY_S];
        let lf = k[KEY_LEFT] || k[KEY_A];
        let rt = k[KEY_RIGHT] || k[KEY_D];
        if ((up || dn || lf || rt) && this.play > 0) {
            this.play = 0;      // steering leaves the board and hands the car back
        }
        if ((up || dn || lf || rt) && this.autopilot && this.boot >= T_GO) {
            this.autopilot = false;
        }
        let go = this.boot >= T_GO;
        let a: f64 = 0;
        let yawRateT: f64 = 0;
        this.apS = this.nearestS(this.px, this.pz);
        let maxRate = Math.min(1.25, (this.v + 0.5) / 6.5);
        let cruise = MODE_CRUISE[this.mode];
        let accelMax = MODE_ACCEL[this.mode];
        if (this.play > 0 && !this.autopilot) {
            this.autopilot = true;
        }
        if (this.autopilot) {
            let tgt: f64 = 0;
            if (go) {
                tgt = cruise / KMH;
                let look = <i32>Math.floor(wrapS(this.apS + this.v * 0.9 + 3));
                tgt = Math.min(tgt, this.vlim[look] * (this.mode == 1 ? 1.25 : 1));
                if (this.play > 0) {
                    // pull up to the SillyScroll stop: brake on a comfortable ramp, then hold
                    let dist = this.sillyAhead();
                    if (this.play == 1) {
                        tgt = Math.min(tgt, Math.sqrt(2 * 2.6 * Math.max(dist - 0.4, 0)));
                        if (dist < 1.5 && this.v < 1.2) {
                            this.play = 2;
                        }
                    } else {
                        tgt = 0;
                    }
                }
            }
            a = clamp((tgt - this.v) * 1.4, -7, accelMax);
            let la = 6 + this.v * 0.55;
            let t = routeAt(this.apS + la);
            let dyaw = wrapAng(yawOf(<f64>t.x - this.px, <f64>t.z - this.pz) - this.yaw);
            yawRateT = clamp(dyaw * (1.6 + this.v * 0.05), -maxRate, maxRate);
        } else {
            if (up && go) {
                a = accelMax;
            } else if (dn) {
                a = this.v > 0.5 ? -9 : -2.5;
            } else {
                a = -0.6 - this.v * 0.012;
            }
            let st: f64 = (rt ? 1 : 0) - (lf ? 1 : 0);
            yawRateT = st * maxRate * (this.v < 0 ? -1 : 1);
        }
        let topV = cruise / KMH * 1.25;
        this.v = clamp(this.v + a * dt, -6, topV);
        if (!this.autopilot && Math.abs(this.v) < 0.05 && !up && !dn) {
            this.v = 0;
        }
        this.yawRate += (yawRateT - this.yawRate) * (1 - Math.exp(-dt * 7));
        this.yaw = wrapAng(this.yaw + this.yawRate * dt);
        this.steer = clamp(this.yawRate / Math.max(maxRate, 0.05), -1, 1);
        let fx = Math.sin(this.yaw);
        let fz = -Math.cos(this.yaw);
        this.px += fx * this.v * dt;
        this.pz += fz * this.v * dt;
        if (!this.autopilot) {
            this.collide();
        }
        this.accel += (a - this.accel) * (1 - Math.exp(-dt * 4));
        // altitude: canyon lane / sky lane
        this.altT = this.mode == 2 ? 140 : 62;
        cdSpring(this.spring, this.alt, this.altV, this.altT, 1.7, dt);
        this.alt = this.spring.x;
        this.altV = this.spring.v;
        let lat = this.v * this.yawRate;
        // hovercraft attitude: bank hard into turns, nose dips on throttle, lifts on brake
        this.roll += (clamp(lat * 0.03, -0.3, 0.3) - this.roll) * (1 - Math.exp(-dt * 3));
        this.pitch += (clamp(-this.accel * 0.011 + this.altV * 0.015, -0.11, 0.11) - this.pitch) * (1 - Math.exp(-dt * 3.5));
        let bob = Math.sin(this.time * 1.7) * 0.025 + Math.sin(this.time * 2.9) * 0.01;
        this.carModel = basis(this.px, this.alt + bob, this.pz, this.yaw) * Mat4.fromRotationZ(<f32>-this.roll) * Mat4.fromRotationX(<f32>this.pitch);
        this.carPos = V(this.px, this.alt, this.pz);
        this.carFwd = V(fx, 0, fz);
        this.bump *= Math.exp(-dt * 5);
        this.battery = Math.max(5, this.battery - Math.max(this.v, 0) * dt * 0.0009);
    }

    private placeCar(parts: Array<Obj>, m: Mat4): void {
        for (let i = 0; i < parts.length; i++) {
            parts[i].model = m;
        }
    }

    private simNpcs(dt: f64): void {
        let lo = -2 * P;
        let hi = (<f64>NB + 2) * P;
        for (let i = 0; i < this.npcs.length; i++) {
            let c = this.npcs[i];
            let go = this.boot >= T_GO - 1.5;
            if (c.kind <= 2) {
                let look = <i32>Math.floor(wrapS(c.s + c.v * 0.8 * c.dir));
                let tgt = go ? Math.min(c.v, this.vlim[look] * 0.95) : 0;
                c.s = wrapS(c.s + tgt * dt * c.dir);
                let p = routeAt(c.s);
                let f = routeDir(c.s);
                let x = <f64>p.x - <f64>f.z * c.off;
                let z = <f64>p.z + <f64>f.x * c.off;
                c.yaw = yawOf(<f64>f.x * c.dir, <f64>f.z * c.dir);
                c.pos = V(x, c.alt, z);
                let bob = Math.sin(this.time * 1.9 + c.s) * 0.03;
                c.model = basis(x, c.alt + bob, z, c.yaw);
            } else {
                let sp = this.boot > T_DIVE ? c.v : c.v * 0.3;
                c.s += sp * dt * c.dir;
                if (c.s > hi) {
                    c.s -= hi - lo;
                } else if (c.s < lo) {
                    c.s += hi - lo;
                }
                let x: f64 = 0;
                let z: f64 = 0;
                let fx: f64 = 0;
                let fz: f64 = 0;
                if (c.axis == 0) {
                    x = c.s;
                    z = c.line;
                    fx = c.dir;
                } else {
                    x = c.line;
                    z = c.s;
                    fz = c.dir;
                }
                let bob = Math.sin(this.time * 1.3 + c.line) * 0.25;
                c.pos = V(x, c.alt + bob, z);
                c.yaw = yawOf(fx, fz);
                c.model = basis(x, c.alt + bob, z, c.yaw) * Mat4.fromUniformScale(<f32>c.scale);
            }
            this.placeCar(c.parts, c.model);
        }
    }

    // ------------------------------------------------------------ camera
    private cEye: Vector = V(0, 0, 0);
    private cTgt: Vector = V(0, 0, 0);
    private cUp: Vector = V(0, 1, 0);

    private cockpitCam(): void {
        let m = this.carModel;
        let e = Cab.eye;
        let lat = this.v * this.yawRate;
        let hx = <f64>e.x - clamp(lat * 0.006, -0.05, 0.05);
        let hz = <f64>e.z + clamp(this.accel * 0.004, -0.03, 0.04);
        let hy = <f64>e.y + 0.03 + this.bump * 0.02 * Math.sin(this.time * 60);
        let eye = m.transformPoint(<f32>hx, <f32>hy, <f32>hz);
        let hp = -0.035 + this.headPitch;
        let hyw = this.headYaw - this.steer * 0.06;
        let dx = Math.sin(hyw) * Math.cos(hp);
        let dy = Math.sin(hp);
        let dz = -Math.cos(hyw) * Math.cos(hp);
        this.cEye = eye;
        this.cTgt = m.transformPoint(<f32>(hx + dx), <f32>(hy + dy), <f32>(hz + dz));
        // keep half the bank in first person: dynamic, not nauseating
        this.cUp = vnorm(vadd(vnorm(vsub(m.transformPoint(<f32>hx, <f32>(hy + 1), <f32>hz), eye)), V(0, 1, 0), 1));
    }

    private hEye: Vector = V(0, 0, 0);
    private hTgt: Vector = V(0, 0, 0);

    private chaseCam(dt: f64): void {
        let d = wrapAng(this.yaw - this.chaseYaw);
        cdSpring(this.spring, 0, this.chaseV, d, 2.6, dt);
        this.chaseYaw = this.yaw - this.spring.x;
        this.chaseV = this.spring.v;
        let yaw = this.chaseYaw + this.headYaw * 2;
        let fx = Math.sin(yaw);
        let fz = -Math.cos(yaw);
        let p = this.carPos;
        let back = 9.0;
        let h = 2.1 + this.headPitch * -8;
        // swing to the outside of the turn so the bank reads in profile
        let lat = this.v * this.yawRate;
        this.camSwing += (clamp(-lat * 0.16, -2.4, 2.4) - this.camSwing) * (1 - Math.exp(-dt * 2));
        let rx = -fz;
        let rz = fx;
        this.hEye = V(<f64>p.x - fx * back + rx * this.camSwing, <f64>p.y + h, <f64>p.z - fz * back + rz * this.camSwing);
        this.hTgt = V(<f64>p.x + fx * 14, <f64>p.y + 1.3, <f64>p.z + fz * 14);
        // roll with the car's bank plus a slow drift: a camera operator, not a rig
        let a = this.roll * 0.6 + Math.sin(this.time * 0.23) * 0.03 + Math.sin(this.time * 0.61) * 0.012;
        this.hUp = V(Math.sin(a) * rx, Math.cos(a), Math.sin(a) * rz);
    }

    private camSwing: f64 = 0;
    private hUp: Vector = V(0, 1, 0);

    private dFov: f64 = 1;

    // from a backlit skyline, plunge into the car's canyon, race the swarm
    // down the street, settle behind the car and drop through the canopy
    private diveCam(x: f64): void {
        let p = this.carPos;
        let f = this.carFwd;
        let r = V(-<f64>f.z, 0, <f64>f.x);
        let up = V(0, 1, 0);
        let gy = V(<f64>p.x, 0, <f64>p.z);
        let sd = sunDir();
        let sh = vnorm(V(<f64>sd.x, 0, <f64>sd.z));
        // opening shot (= title overview): close enough that the near towers read as
        // dark silhouettes against the bright sky slit, not haze
        let p0 = vadd(vadd(vadd(gy, sh, -720), up, 235), r, 90);
        let p1 = vadd(vadd(vadd(gy, f, -560), up, 250), r, 40);
        let p2 = vadd(vadd(gy, f, -300), up, <f64>p.y + 14);
        let p3 = vadd(vadd(vadd(p, f, -46), up, 9), r, 5);
        let p4 = vadd(vadd(p, f, -9.0), up, 2.6);
        let p5 = vadd(vadd(vadd(p, f, -2.2), up, 1.35), r, -0.2);
        let ps: Array<Vector> = [p0, p1, p2, p3, p4, p5, this.cEye];
        let ts: Array<f64> = [0, 0.26, 0.5, 0.7, 0.85, 0.94, 1.0];
        let t0 = vadd(vadd(gy, sh, 520), up, 95);
        let t1 = vadd(vadd(gy, f, -120), up, 40);
        let t2 = vadd(p, up, 2);
        let t3 = vadd(p, f, 6);
        let t4 = vadd(vadd(p, f, 4), up, 0.8);
        let t5 = vadd(vadd(p, f, 6), up, 1.0);
        let tg: Array<Vector> = [t0, t1, t2, t3, t4, t5, this.cTgt];
        let q = smooth5(x);
        let q2 = Math.pow(x, 0.92);
        let qq = q * 0.6 + smooth5(q2) * 0.4;
        this.eye = hermite(ps, ts, qq);
        this.target = hermite(tg, ts, qq);
        this.dFov = 60 * PI / 180 + Math.sin(PI * qq) * 22 * PI / 180;
    }

    private updateCamera(dt: f64): void {
        if (this.sizeX <= 0) {
            return;
        }
        // after release the look settles briefly (short glide, same limits as the drag)
        if (!this.dragging) {
            this.headYaw = clamp(this.headYaw + this.headVel * dt, -1.3, 1.3);
            this.headVel *= Math.exp(-dt * 8);
            // the view stays where the driver left it; it only eases home when autopilot engages
            if (this.lookHome) {
                let k = 1 - Math.exp(-dt * 1.8);
                this.headYaw -= this.headYaw * k;
                this.headPitch -= this.headPitch * k;
                if (Math.abs(this.headYaw) + Math.abs(this.headPitch) < 1e-3) {
                    this.lookHome = false;
                }
            }
        }
        this.camBlend += ((this.camMode >= 1 ? 1 : 0) - this.camBlend) * (1 - Math.exp(-dt * 3.2));
        this.orbitBlend += ((this.camMode == 2 ? 1 : 0) - this.orbitBlend) * (1 - Math.exp(-dt * 2.4));
        this.cockpitCam();
        this.chaseCam(dt);
        let cb = smooth5(this.camBlend);
        let eye = vlerp(this.cEye, this.hEye, cb);
        let tgt = vlerp(this.cTgt, this.hTgt, cb);
        let up = vlerp(this.cUp, this.camMode == 2 ? V(0, 1, 0) : this.hUp, cb);
        let fov = 68 * PI / 180 + cb * -12 * PI / 180;
        if (this.orbitBlend > 0.001) {
            // showroom orbit: slow turntable around the car, drag to swing
            this.orbitA += dt * 0.18;
            let a = this.orbitA + this.yaw + this.headYaw * 2.5;
            let d = 5.6 - this.headPitch * 4;
            let oe = vadd(this.carPos, V(Math.sin(a) * d, 1.15 + this.headPitch * 3, -Math.cos(a) * d), 1);
            let ot = vadd(this.carPos, V(0, 0.62, 0), 1);
            let ob = smooth5(this.orbitBlend);
            eye = vlerp(eye, oe, ob);
            tgt = vlerp(tgt, ot, ob);
            fov = fov + (40 * PI / 180 - fov) * ob;
        }
        let x = (this.boot - T_DIVE) / DIVE_DUR;
        if (x < 1) {
            this.diveCam(Math.max(x, 0));
            eye = this.eye;
            tgt = this.target;
            fov = this.dFov;
            // title: a slow crane/orbit drift over the overview, eased out as the dive takes over
            let wd = this.entered ? Math.exp(-this.enterT * 1.6) : 1;
            if (wd > 0.001) {
                let tt = this.tt;
                let dr = V(Math.sin(tt * 0.11) * 60, Math.sin(tt * 0.083) * 18 - 10, Math.cos(tt * 0.07) * 45 - 45);
                eye = vadd(eye, dr, wd);
                tgt = vadd(tgt, V(Math.sin(tt * 0.06) * 30, 0, 0), wd);
                // home screen: the camera looks a touch toward the mouse (eased), the eye slides the
                // other way for parallax, and it banks slightly into the move
                let km = 1 - Math.exp(-dt * 2.6);
                this.tmx += (this.tmxT - this.tmx) * km;
                this.tmy += (this.tmyT - this.tmy) * km;
                let fw = vsub(tgt, eye);
                let L = vlen(fw);
                let rt = vnorm(vcross(fw, V(0, 1, 0)));
                tgt = vadd(vadd(tgt, rt, this.tmx * L * 0.07 * wd), V(0, 1, 0), -this.tmy * L * 0.045 * wd);
                eye = vadd(vadd(eye, rt, -this.tmx * 22 * wd), V(0, 1, 0), this.tmy * 8 * wd);
                this.tiltRoll = -this.tmx * 0.045 * wd;
            } else {
                this.tiltRoll = 0;
            }
            up = vlerp(V(0, 1, 0), this.cUp, smooth5((x - 0.9) / 0.1));
            if (Math.abs(this.tiltRoll) > 1e-5) {
                let rr = vnorm(vcross(vsub(tgt, eye), V(0, 1, 0)));
                up = vnorm(vadd(up, rr, this.tiltRoll));
            }
        }
        // SillyScroll: once stopped, float out of the seat to a square-on framing of the board
        this.playK += ((this.play == 2 ? 1 : 0) - this.playK) * (1 - Math.exp(-dt * 1.7));
        if (this.playK > 0.001 && this.sillyOk && x >= 1) {
            let pk = smooth5(this.playK);
            let n = V(this.sillyNx, 0, this.sillyNz);
            // 20 m board ~ 85% of the frame height; closer (wider) where buildings limit the pull-back
            let D = Math.min(this.sillyD, 11.8 / Math.tan(PLAY_FOV / 2));
            let pfov = 2 * Math.atan(11.8 / D);
            let pe = vadd(vadd(this.sillyC, n, D), V(0, 1, 0), -0.6);
            eye = vadd(vlerp(eye, pe, pk), V(0, 1, 0), Math.sin(PI * pk) * 4);
            tgt = vlerp(tgt, this.sillyC, pk);
            up = vnorm(vlerp(up, V(0, 1, 0), pk));
            fov = fov + (pfov - fov) * pk;
        }
        let dist = vlen(vsub(eye, this.cEye));
        this.inside = dist < 0.25 && cb < 0.02;
        // speed of the image for the zoom blur
        let sp = vlen(vsub(eye, this.lastEye)) / Math.max(dt, 1e-3);
        this.lastEye = eye;
        if (x < 1) {
            this.camSpeed = Math.min(sp / 120, 1) * Math.pow(Math.sin(PI * clamp(x, 0, 1)), 0.5);
        } else {
            this.camSpeed = 0;
        }
        this.eye = eye;
        this.target = tgt;
        this.up = up;
        let aspect = this.sizeX / Math.max(this.sizeY, 1);
        let yfov = fov;
        if (aspect < 1.5) {
            yfov = 2 * Math.atan(Math.tan(fov / 2) * 1.5 / aspect);
        }
        this.fov = yfov;
        this.view = Mat4.lookAtVector(eye, tgt, up);
        let near = this.inside ? 0.25 : clamp(dist * 0.05, 0.02, 0.5);
        if (<f64>eye.y > 120) {
            near = Math.max(near, <f64>eye.y * 0.02);
        }
        let pM = Mat4.perspective(<f32>yfov, <f32>aspect, <f32>near, 5000);
        let pB = Mat4.perspective(<f32>yfov, <f32>aspect, 0.015, 8);
        this.viewProj = pM * this.view;
        this.viewProjB = pB * this.view;
        // GPU matrices built at the origin: no 1 km translation to cancel in f32
        let viewRel = Mat4.lookAtVector(V(0, 0, 0), vsub(tgt, eye), up);
        this.viewProjRelNJ = pM * viewRel;
        // TAA: sub-pixel Halton(2,3) jitter on the world projection only (the
        // cockpit pass stays put so the screens never swim)
        this.jitN = (this.jitN + 1) % 8;
        let jx = (halton(this.jitN + 1, 2) - 0.5) * 2 / Math.max(<f64>this.gw, 1);
        let jy = (halton(this.jitN + 1, 3) - 0.5) * 2 / Math.max(<f64>this.gh, 1);
        let J = Mat4.values(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, <f32>jx, <f32>jy, 0, 1);
        this.viewProjRel = J * pM * viewRel;
        this.viewProjBRel = pB * viewRel;
        let inv = this.viewProj.invert();
        this.invVP = inv != null ? inv : Mat4.identity();
        // picking basis (exact; no inverse of a far-plane matrix in f32)
        let cf = vnorm(vsub(tgt, eye));
        let cr = vnorm(vcross(cf, up));
        this.camF = cf;
        this.camR = cr;
        this.camU = vcross(cr, cf);
        this.camAspect = aspect;
    }

    // ------------------------------------------------------------ cockpit placement
    private placeCockpit(): void {
        let m = this.carModel;
        for (let i = 0; i < this.cab.length; i++) {
            this.cab[i].model = m;
        }
        let cl = m * Mat4.fromTranslation(Cab.clPos.x, Cab.clPos.y, Cab.clPos.z) * Mat4.fromRotationX(<f32>Cab.clPitch);
        this.placeCar(this.clParts, cl);
        let cs = m * Mat4.fromTranslation(Cab.csPos.x, Cab.csPos.y, Cab.csPos.z) * Mat4.fromRotationY(<f32>Cab.csYaw) *
            Mat4.fromRotationX(<f32>Cab.csPitch);
        this.placeCar(this.csParts, cs);
        let yk = m * Mat4.fromTranslation(Cab.ykPos.x, Cab.ykPos.y, Cab.ykPos.z) * Mat4.fromRotationX(<f32>Cab.ykTilt) *
            Mat4.fromRotationZ(<f32>(-this.steer * 0.9));
        this.placeCar(this.yokeParts, yk);
        this.placeCar(this.ext, m);
        // canopy dissolve as the camera flies into the seat
        let dg = vlen(vsub(this.eye, tp(m, Cab.eye)));
        let eg = this.extGlass;
        if (eg != null) {
            eg.fx[2] = clamp(1 - (dg - 0.6) / 3.2, 0, 1);
        }
        // the driver's own seat dissolves as the intro camera flies through it
        // and stays hidden while seated (it would fill the view on head turns)
        let sd = this.inside || this.camMode == 0 && dg < 0.3 ? 1 : clamp(1 - (dg - 0.35) / 1.6, 0, 1);
        for (let i = 0; i < this.dseat.length; i++) {
            this.dseat[i].fx[2] = sd;
        }
    }

    // ------------------------------------------------------------ AR markers (eye -> world ray onto the windshield)
    private gU: f64 = 0;
    private gV: f64 = 0;

    private glassUV(wp: Vector): bool {
        let inv = this.carModel.invert();
        if (inv == null) {
            return false;
        }
        let o = Cab.eye;
        let q = tp(inv, wp);
        let d = vsub(q, o);
        let len = vlen(d);
        if (len < 1e-4) {
            return false;
        }
        d = vscale(d, 1 / len);
        if (<f64>d.z > -0.05) {
            return false;
        }
        let A = Cab.glassA;
        let w = vsub(o, Cab.glassO);
        let wp2 = vadd(w, A, -vdot(w, A));
        let dp = vadd(d, A, -vdot(d, A));
        let a = vdot(dp, dp);
        let b = 2 * vdot(wp2, dp);
        let c = vdot(wp2, wp2) - Cab.glassR * Cab.glassR;
        let disc = b * b - 4 * a * c;
        if (disc < 0 || a < 1e-9) {
            return false;
        }
        let s = (-b + Math.sqrt(disc)) / (2 * a);
        let hit = vadd(o, d, s);
        let rel = vsub(hit, Cab.glassO);
        let t = vdot(rel, A);
        let radial = vadd(rel, A, -t);
        let th = Math.atan2(vdot(radial, Cab.glassX), vdot(radial, Cab.glassF));
        let gu = (th - Cab.th0) / (Cab.th1 - Cab.th0);
        let gv = 1 - (t - Cab.t0) / (Cab.t1 - Cab.t0);
        // the HUD is a virtual image on a VISOR: a cylinder r 2.5 m around the eye (lit.wgsl HUD_*),
        // so it bows toward the edges like a helmet visor; arc length maps to HUD artboard x
        let k = 2.5 / Math.max(Math.sqrt(<f64>d.x * <f64>d.x + <f64>d.z * <f64>d.z), 1e-4);
        let hy = <f64>d.y * k;
        let thv = Math.atan2(<f64>d.x, -<f64>d.z);
        let u = (600 + 2.5 * thv / 0.0028) / 2000;
        let v = (617 - hy / 0.0028) / 1240;
        this.gU = u;
        this.gV = v;
        return gu > 0.02 && gu < 0.98 && gv > 0.04 && gv < 0.96 && u > 0.02 && u < 0.98 && v > 0.03 && v < 0.97;
    }

    private updateMarkers(dt: f64): void {
        let hud = this.surfs[3];
        let W = hud.w;
        let H = hud.h;
        let cands = new Array<Cand>();
        let p = this.carPos;
        let f = this.carFwd;
        for (let i = 0; i < this.bbs.length; i++) {
            let b = this.bbs[i];
            let dx = <f64>b.c.x - <f64>p.x;
            let dz = <f64>b.c.z - <f64>p.z;
            let d = Math.sqrt(dx * dx + dz * dz);
            let along = dx * <f64>f.x + dz * <f64>f.z;
            if (d < 260 && d > 22 && along > d * 0.6 && (b.nx * -dx + b.nz * -dz) > 0) {
                cands.push(new Cand(d, b));
            }
        }
        cands.sort((a: Cand, b: Cand): i32 => (a.d < b.d ? -1 : (a.d > b.d ? 1 : 0)));
        let want = new Array<Want>();
        for (let i = 0; i < Math.min(3, cands.length); i++) {
            let b = cands[i].b;
            let w = new Want();
            w.wp = V(<f64>b.c.x, <f64>b.c.y + b.h * 0.5 + 1.2, <f64>b.c.z);
            w.title = BB_NAMES[b.design];
            w.dist = fmtM(cands[i].d);
            w.key = <f64>b.design * 1000 + Math.floor(<f64>b.c.x);
            want.push(w);
        }
        for (let k = 0; k < 3; k++) {
            let mk = this.markers[k];
            let tOp: f64 = 0;
            if (k < want.length && this.inside && this.hudOn) {
                let w = want[k];
                if (this.glassUV(w.wp)) {
                    let u = this.gU;
                    let v = this.gV;
                    if (mk.key != w.key) {
                        mk.key = w.key;
                        mk.x = u * W;
                        mk.y = v * H;
                    }
                    let kk = 1 - Math.exp(-dt * 14);
                    mk.x += (u * W - mk.x) * kk;
                    mk.y += (v * H - mk.y) * kk;
                    mk.title = w.title;
                    mk.dist = w.dist;
                    tOp = 1;
                }
            }
            mk.op += (tOp - mk.op) * (1 - Math.exp(-dt * 8));
            let n = "m" + (k + 1).toString();
            this.setN(n + "x", Math.floor(mk.x * 2 + 0.5) / 2);
            this.setN(n + "y", Math.floor(mk.y * 2 + 0.5) / 2);
            this.setN(n + "op", Math.floor(mk.op * 100 + 0.5) / 100);
            this.setS(n + "t", mk.title);
            this.setS(n + "d", mk.dist);
        }
    }

    // ------------------------------------------------------------ HUD declutter
    // Trackers (nearest first) then billboard markers claim screen space in priority
    // order. An item whose reticle/brackets land on a higher-priority one fades out;
    // each label tries its previous quadrant, then the others, and must stay on the
    // glass, off the readout cluster and off everything already placed.
    private freeAt(r: Rect, occ: Array<Rect>, W: f64, H: f64): bool {
        if (r.x0 < 30 || r.y0 < 30 || r.x1 > W - 30 || r.y1 > H - 30) {
            return false;
        }
        for (let i = 0; i < occ.length; i++) {
            if (r.hits(occ[i])) {
                return false;
            }
        }
        return true;
    }

    private labelRect(q: i32, ax: f64, ay: f64, lead: f64, w: f64, h: f64): Rect {
        let x0 = Q_FX[q] > 0 ? ax + lead : ax - lead - w;
        let y0 = Q_FY[q] > 0 ? ay - lead - h : ay + lead;
        return new Rect(x0, y0, x0 + w, y0 + h);
    }

    private declutterHud(dt: f64): void {
        let hud = this.surfs[3];
        let W = hud.w;
        let H = hud.h;
        let occ = new Array<Rect>();
        occ.push(new Rect(RO_X0, RO_Y0, RO_X1, RO_Y1));
        let kf = 1 - Math.exp(-dt * 12);
        // trackers by distance
        let order = new Array<i32>();
        for (let k = 0; k < 4; k++) {
            order.push(k);
        }
        let trks = this.trks;
        order.sort((a: i32, b: i32): i32 => (trks[a].dPrev < trks[b].dPrev ? -1 : 1));
        for (let n = 0; n < 4; n++) {
            let k = order[n];
            let tk = trks[k];
            let nm = "t" + (k + 1).toString();
            let show = tk.op > 0.05 && tk.key >= 0;
            let lshow = false;
            let lr = new Rect(-600, -600, -600, -600);
            if (show) {
                let rr = 58 * tk.s;
                let ret = new Rect(tk.x - rr, tk.y - rr, tk.x + rr, tk.y + rr);
                let clash = false;
                for (let i = 1; i < occ.length; i++) {
                    if (ret.hits(occ[i])) {
                        clash = true;
                        break;
                    }
                }
                if (ret.hits(occ[0])) {
                    clash = true;
                }
                show = !clash;
                if (show) {
                    occ.push(ret);
                    for (let t = 0; t < 5; t++) {
                        let q = t == 0 ? tk.q : t - 1;
                        let r = this.labelRect(q, tk.x, tk.y, 62 * tk.s, TRK_W, TRK_H);
                        if (this.freeAt(r, occ, W, H)) {
                            tk.q = q;
                            lr = r;
                            lshow = true;
                            break;
                        }
                    }
                    if (lshow) {
                        occ.push(lr);
                    }
                }
            }
            tk.vis += ((show ? 1 : 0) - tk.vis) * kf;
            tk.lvis += ((lshow ? 1 : 0) - tk.lvis) * kf;
            this.setN(nm + "op", Math.floor(tk.op * tk.vis * 100 + 0.5) / 100);
            this.setN(nm + "fx", Q_FX[tk.q]);
            this.setN(nm + "fy", Q_FY[tk.q]);
            if (lshow) {
                this.setN(nm + "lx", Math.floor(lr.x0 + 0.5));
                this.setN(nm + "ly", Math.floor(lr.y0 + 0.5));
            }
            this.setN(nm + "lo", Math.floor(tk.op * tk.vis * tk.lvis * 100 + 0.5) / 100);
        }
        // billboard markers (already nearest-first)
        for (let k = 0; k < 3; k++) {
            let mk = this.markers[k];
            let nm = "m" + (k + 1).toString();
            let show = mk.op > 0.05;
            let lshow = false;
            let lr = new Rect(-600, -600, -600, -600);
            if (show) {
                let br = new Rect(mk.x - 32, mk.y - 32, mk.x + 32, mk.y + 32);
                for (let i = 0; i < occ.length; i++) {
                    if (br.hits(occ[i])) {
                        show = false;
                        break;
                    }
                }
                if (show) {
                    occ.push(br);
                    for (let t = 0; t < 5; t++) {
                        let q = t == 0 ? mk.q : t - 1;
                        let r = this.labelRect(q, mk.x, mk.y, 46, MK_W, MK_H);
                        if (this.freeAt(r, occ, W, H)) {
                            mk.q = q;
                            lr = r;
                            lshow = true;
                            break;
                        }
                    }
                    if (lshow) {
                        occ.push(lr);
                    }
                }
            }
            mk.vis += ((show ? 1 : 0) - mk.vis) * kf;
            mk.lvis += ((lshow ? 1 : 0) - mk.lvis) * kf;
            this.setN(nm + "op", Math.floor(mk.op * mk.vis * 100 + 0.5) / 100);
            this.setN(nm + "fx", Q_FX[mk.q]);
            this.setN(nm + "fy", Q_FY[mk.q]);
            if (lshow) {
                this.setN(nm + "lx", Math.floor(lr.x0 + 0.5));
                this.setN(nm + "ly", Math.floor(lr.y0 + 0.5));
            }
            this.setN(nm + "lo", Math.floor(mk.op * mk.vis * mk.lvis * 100 + 0.5) / 100);
        }
    }

    // ------------------------------------------------------------ HUD vehicle trackers
    private updateTrackers(dt: f64): void {
        let hud = this.surfs[3];
        let W = hud.w;
        let H = hud.h;
        let e = this.eye;
        let cf = this.camF;
        let live = this.inside && this.hudOn && this.boot >= T_HUD;
        let cands = new Array<TrkCand>();
        if (live) {
            let ex = <f64>e.x;
            let ey = <f64>e.y;
            let ez = <f64>e.z;
            let fx = <f64>cf.x;
            let fy = <f64>cf.y;
            let fz = <f64>cf.z;
            // swarm (instanced): rebuild positions like vs_swarm
            let sw = this.swCpu;
            let n = sw.length / 8;
            let t = this.time;
            for (let i = 0; i < n; i++) {
                let o = i * 8;
                let ly = <f64>sw[o + 1];
                if (Math.abs(ly - ey) > 60) {
                    continue;
                }
                let len = <f64>sw[o + 6];
                let seed = <f64>sw[o + 7];
                let sp = <f64>sw[o + 3];
                let u = seed * 7.13 + t * sp / len;
                let s0 = (u - Math.floor(u)) * len - len * 0.5;
                let dir = <f64>sw[o + 5];
                let px = <f64>sw[o];
                let pz = <f64>sw[o + 2];
                if (<f64>sw[o + 4] > 0.5) {
                    pz += dir * s0;
                } else {
                    px += dir * s0;
                }
                let py = ly + Math.sin(t * 1.7 + seed * 40) * 0.35;
                let dx = px - ex;
                let dy = py - ey;
                let dz = pz - ez;
                let along = dx * fx + dy * fy + dz * fz;
                if (along < 8 || along > 130) {
                    continue;
                }
                let d = Math.sqrt(dx * dx + dy * dy + dz * dz);
                if (along < d * 0.86) {
                    continue;
                }
                cands.push(new TrkCand(d, <f64>i, V(px, py, pz)));
            }
            for (let i = 0; i < this.npcs.length; i++) {
                let c = this.npcs[i];
                let p = c.pos;
                let dx = <f64>p.x - ex;
                let dy = <f64>p.y + 0.6 - ey;
                let dz = <f64>p.z - ez;
                let along = dx * fx + dy * fy + dz * fz;
                let d = Math.sqrt(dx * dx + dy * dy + dz * dz);
                if (along > 6 && along < 160 && along > d * 0.86) {
                    cands.push(new TrkCand(d, 100000 + <f64>i, V(<f64>p.x, <f64>p.y + 0.6, <f64>p.z)));
                }
            }
            cands.sort((a: TrkCand, b: TrkCand): i32 => (a.d < b.d ? -1 : (a.d > b.d ? 1 : 0)));
            if (cands.length > 10) {
                cands = cands.slice(0, 10);
            }
        }
        // keep slots locked on their targets; free slots take the nearest new ones
        let taken = new Array<bool>(cands.length);
        let slotC = new Array<i32>(4);
        for (let k = 0; k < 4; k++) {
            slotC[k] = -1;
            let tk = this.trks[k];
            // hysteresis: a locked target holds its slot while it stays in the nearest 8
            for (let j = 0; j < cands.length; j++) {
                if (!taken[j] && cands[j].key == tk.key) {
                    slotC[k] = j;
                    taken[j] = true;
                    break;
                }
            }
        }
        for (let k = 0; k < 4; k++) {
            if (slotC[k] >= 0) {
                continue;
            }
            for (let j = 0; j < Math.min(4, cands.length); j++) {
                if (!taken[j]) {
                    slotC[k] = j;
                    taken[j] = true;
                    break;
                }
            }
        }
        for (let k = 0; k < 4; k++) {
            let tk = this.trks[k];
            let tOp: f64 = 0;
            let j = slotC[k];
            // only in the upper windshield band: below it the dash and cluster sit in front
            if (j >= 0 && this.glassUV(cands[j].p) && this.gV * H < 600 && this.gV * H > 90 && this.gU * W > 120 && this.gU * W < W - 360) {
                let c = cands[j];
                let ux = this.gU * W;
                let uy = this.gV * H;
                if (tk.key != c.key) {
                    // new lock: drop to zero first so the Lock animation replays
                    tk.key = c.key;
                    tk.x = ux;
                    tk.y = uy;
                    tk.op = 0;
                    tk.hold = 3;
                    tk.dPrev = c.d;
                    tk.vc = 0;
                    let hsh = <i32>((c.key * 2654435761) % 65536);
                    tk.id = (c.key >= 100000 ? "KX-" : "HX-") + ((hsh % 9000) + 1000).toString();
                    tk.cl = TRK_CLASSES[(hsh >> 3) % TRK_CLASSES.length];
                }
                let kk = 1 - Math.exp(-dt * 16);
                tk.x += (ux - tk.x) * kk;
                tk.y += (uy - tk.y) * kk;
                tk.s = clamp(52 / c.d, 0.72, 1.3);
                let vcNow = dt > 0 ? (tk.dPrev - c.d) / dt : 0;
                tk.vc += (vcNow - tk.vc) * (1 - Math.exp(-dt * 4));
                tk.dPrev = c.d;
                tk.hexT -= dt;
                if (tk.hexT <= 0) {
                    tk.hexT = 0.18;
                    tk.hex = hex4(<i32>(Math.random() * 65535));
                }
                if (tk.hold > 0) {
                    tk.hold--;
                } else {
                    tOp = 1;
                }
                let n = "t" + (k + 1).toString();
                let kmh = tk.vc * 3.6;
                let ak = <i32>Math.min(99, Math.abs(Math.round(kmh)));
                this.setS(n + "d", fmt1(c.d));
                this.setS(n + "v", (kmh >= 0 ? "+" : "-") + (ak < 10 ? "0" : "") + ak.toString() + " KM/H");
                this.setS(n + "tt", tk.vc > 0.6 ? "TTC " + fmt1(Math.min(c.d / tk.vc, 99)) : "TTC --.-");
                this.setS(n + "hx", tk.hex);
                this.setS(n + "id", tk.id);
                this.setS(n + "cl", tk.cl);
                let threat = clamp((32 - c.d) / 20, 0, 1);
                this.setN(n + "r", Math.floor(threat * 50 + 0.5) / 50);
                this.setN(n + "n", Math.floor((1 - threat) * 50 + 0.5) / 50);
                this.setN(n + "c", Math.floor(clamp(tk.vc / 20, 0, 1) * 50 + 0.5) / 50);
            } else {
                tk.key = -1;
            }
            tk.op += (tOp - tk.op) * (tOp > tk.op ? 1 - Math.exp(-dt * 10) : 1 - Math.exp(-dt * 14));
            if (tOp == 0 && tk.op < 0.04) {
                tk.op = 0;
            }
            let n = "t" + (k + 1).toString();
            this.setN(n + "x", Math.floor(tk.x * 2 + 0.5) / 2);
            this.setN(n + "y", Math.floor(tk.y * 2 + 0.5) / 2);
            this.setN(n + "s", Math.floor(tk.s * 100 + 0.5) / 100);
            this.setN(n + "op", Math.floor(tk.op * 100 + 0.5) / 100);
        }
    }

    // ------------------------------------------------------------ telemetry -> view model
    private stName: string = "";
    private stNext: string = "";
    private stTo: f64 = 0;
    private stTurn: f64 = 1;

    private streetAt(s: f64): void {
        for (let i = 0; i < City.streets.length; i++) {
            let st = City.streets[i];
            let ss = s;
            if (ss < st.s0) {
                ss += <f64>ROUTE_N;
            }
            if (ss >= st.s0 && ss < st.s1) {
                this.stName = st.name;
                this.stNext = st.next;
                this.stTo = st.s1 - ss;
                this.stTurn = st.turn;
                return;
            }
        }
        let st = City.streets[0];
        this.stName = st.name;
        this.stNext = st.next;
        this.stTo = 0;
        this.stTurn = st.turn;
    }

    private writeTelemetry(): void {
        let b = this.boot;
        let kmh = Math.abs(this.v) * KMH;
        let sw: f64 = 0;
        if (b > T_CL + 0.4 && b < T_CL + 1.7) {
            sw = Math.sin(PI * (b - T_CL - 0.4) / 1.3);
        }
        let maxK: f64 = 160;
        this.setN("speedFrac", Math.max(kmh / maxK, sw));
        let shown = Math.floor(kmh + 0.5);
        if (sw > 0) {
            shown = Math.floor(sw * maxK + 0.5);
        }
        this.setS("speed", formatInt(shown));
        this.setS("bbSpeed", formatInt(Math.floor(kmh + 0.5), 3, true));
        let pw = clamp(this.accel * Math.max(this.v, 0) / 60, 0, 1);
        this.setN("powerFrac", Math.max(pw * 0.8 + Math.min(kmh / maxK, 1) * 0.2, sw));
        this.setN("batteryFrac", Math.max(this.battery / 100, sw));
        this.setS("battery", formatInt(Math.floor(this.battery + 0.5)));
        this.setS("range", formatInt(Math.floor(this.battery * 5.1 + 0.5)));
        this.setS("alt", formatFixed(this.alt, 1));
        this.setN("altFrac", clamp((this.alt - 62) / 78, 0, 1));
        let gear = b >= T_READY ? (this.v < -0.3 ? "R" : "D") : "P";
        this.setS("gear", gear);
        this.setN("gP", gear == "P" ? 1 : 0.25);
        this.setN("gR", gear == "R" ? 1 : 0.25);
        this.setN("gN", gear == "N" ? 1 : 0.25);
        this.setN("gD", gear == "D" ? 1 : 0.25);
        this.setN("ap", this.autopilot ? 1 : 0);
        this.setS("apLabel", this.autopilot ? "AUTOPILOT" : "MANUAL");
        this.setS("apSub", this.autopilot ? "HANDS FREE  ·  LANE + ROUTE LOCK" : "HANDS ON  ·  WASD TO STEER");
        this.setN("mode", <f64>this.mode);
        this.setS("modeName", MODE_NAMES[this.mode]);
        this.setN("steer", this.steer);
        this.setN("view", <f64>this.camMode);
        // navigation
        this.streetAt(this.apS);
        this.setS("street", this.stName);
        this.setS("navDist", fmtM(this.stTo));
        this.setS("navStreet", this.stNext);
        this.setN("navTurn", this.stTurn);
        this.setS("navVerb", this.stTurn > 0 ? "TURN RIGHT" : "TURN LEFT");
        // media
        let dur = TRACK_DUR[this.track];
        this.setN("track", <f64>this.track);
        this.setS("trackTitle", TRACK_TITLE[this.track]);
        this.setS("trackArtist", TRACK_ARTIST[this.track]);
        this.setN("playing", this.playing ? 1 : 0);
        this.setN("progress", this.progress / dur);
        let el = Math.floor(this.progress);
        this.setS("trackTime", formatInt(Math.floor(el / 60)) + ":" + formatInt(el % 60, 2, true) + " / " +
            formatInt(Math.floor(dur / 60)) + ":" + formatInt(dur % 60, 2, true));
        this.setN("ambient", <f64>this.ambient);
        this.setS("ambName", AMB_NAMES[this.ambient]);
        this.setS("taps", formatInt(<f64>this.taps, 4, true));
        this.setN("hitT", this.hitT > 0 ? 1 : 0);
        // clock / climate
        let mins = Math.floor(this.time / 60);
        let hh: f64 = 23;
        let mm: f64 = 47 + mins;
        if (this.nightT < 0.5) {
            hh = 14;
            mm = 20 + mins;
        }
        hh = (hh + Math.floor(mm / 60)) % 24;
        mm = mm % 60;
        this.setS("clock", formatInt(hh, 2, true) + ":" + formatInt(mm, 2, true));
        this.setS("temp", this.nightT > 0.5 ? "17°C" : "24°C");
        this.setN("night", this.night);
        this.setN("sunOp", 1 - 0.7 * this.night);
        this.setN("moonOp", 0.3 + 0.7 * this.night);
        this.pickPlayTarget();
        let ahead = this.sillyOk ? this.sillyAhead() : 1e9;
        let pname = BB_NAMES[this.playDes];
        if (this.play == 2) {
            this.setS("readout", pname + "  ·  DRAG THE CHARACTERS TO MIX THEM  ·  E TO DRIVE ON");
        } else if (this.play == 1) {
            this.setS("readout", "PULLING UP TO " + pname + "  ·  " + formatInt(ahead) + " M  ·  E TO CANCEL");
        } else if (ahead < 420 && this.entered) {
            this.setS("readout", pname + " AHEAD  ·  " + formatInt(ahead) + " M  ·  PRESS E TO STOP AND PLAY");
        } else this.setS("readout", (this.autopilot ? "AUTOPILOT" : "MANUAL") + "  ·  " + MODE_NAMES[this.mode] + "  ·  " + this.stName +
            "  ·  " + (this.camMode == 0 ? "COCKPIT" : (this.camMode == 1 ? "CHASE" : "SHOWROOM")) + "  ·  " + (this.nightT > 0.5 ? "NIGHT" : "DAY"));
        let warn = "";
        if (this.bump > 0.2) {
            warn = "PROXIMITY";
        } else if (Math.abs(this.alt - this.altT) > 2) {
            warn = this.altT > 100 ? "ASCENDING · SKY LANE 140 M" : "DESCENDING · CANYON LANE 62 M";
        } else if (b >= T_HUD && b < T_GO + 1.2) {
            warn = "SYSTEMS ONLINE";
        }
        this.setS("warn", warn);
        this.setN("warnOp", warn.length > 0 ? 1 : 0);
        // boot overlays + staged intros
        this.setN("uiIn", smooth5((b - T_UI) / 0.8));
        this.setN("bootBar", clamp(b / T_LOGO_OUT, 0, 1));
        this.setN("bootCl", b >= T_CL ? 1 : 0);
        this.setN("bootCs", b >= T_CS ? 1 : 0);
        this.setN("bootHub", b >= T_HUB ? 1 : 0);
        this.setN("bootHud", b >= T_HUD ? 1 : 0);
        this.setLogo("logoHub", b >= T_HUB + 0.2);
        // billboard logo cycles in / out (its own In / Out animations)
        let cyc = this.time % 7.0;
        this.setLogo("logoBB", b > T_POWER && cyc < 5.4);
    }

    // ------------------------------------------------------------ title screen
    private updateTitle(d: f64): void {
        // Rive logo plays in over the city overview, out on ENTER
        // the logo waits for the city to finish rising
        this.setLogo("logo", !this.entered && this.loadT >= T_LOGO);
        // the logo artboard rests in its shown pose; keep it invisible until its play-in is due
        if (this.loadT >= T_LOGO) {
            this.logoSeen = true;
        }
        this.setN("logoVis", this.logoSeen ? 1 : 0);
        let ready = this.loadT >= T_TITLE_UI;
        let tgt: f64 = !this.entered && ready ? 1 : 0;
        let rate: f64 = tgt > this.enterOp ? 3.0 : 6.0;
        this.enterOp += (tgt - this.enterOp) * (1 - Math.exp(-d * rate));
        if (this.enterOp < 0.01 && tgt == 0) {
            this.enterOp = 0;
        }
        this.setN("enterOp", Math.floor(this.enterOp * 100 + 0.5) / 100);
        this.setN("enterGo", this.entered ? 1 : 0);
        let lo = this.loadT < 0 ? 1 : 1 - clamp(this.loadT / 0.4, 0, 1);
        this.setN("loadOp", lo);
        // black until the city exists, then a 0.6 s fade as it appears (first load only: a return
        // to the title replays the rise without going dark)
        if (this.loadT >= 0.5) {
            // after the rendered city has faded in over the artboard sky (worldOp, 0.8 s)
            this.blackK = Math.max(0, this.blackK - d / 0.6);
        }
        this.setN("blackout", Math.floor(smooth5(this.blackK) * 100 + 0.5) / 100);
        // title grade + scrim ease out over the first second of the dive
        this.titleK = this.entered ? Math.max(0, 1 - this.enterT / 1.6) : 1;
        this.setN("titleOp", Math.floor(smooth5(this.titleK) * 100 + 0.5) / 100);
        // the rendered city fades in over the artboard sky once it has loaded
        this.worldOp = this.loadT < 0 ? 0 : smooth5(this.loadT / 0.8);
    }

    // Title visor: the live "Title FUI" artboard on the inside of a 150 deg cylinder centred on
    // the camera (r 4 m), wider than the view, so its bands bow toward the screen corners like a
    // helmet visor. Brow band drops in and sweeps open from the centre; button band springs up
    // from below and unrolls; both flicker on while the artboard assembles. ENTER: press flash,
    // brow retracts up, button band drops away, both collapse to the centre.
    private placeHolo(dt: f64): void {
        // title CTA (2D, main artboard): build when the city is up, decrypt cue as the cursor types
        let tb = this.loadT - T_TITLE_UI;
        this.holoOn = false;
        this.setN("titleBuild", tb >= 0.35 ? 1 : 0);
        if (tb < 0.35) {
            this.holoCued = false;
        } else if (!this.holoCued && tb >= 1.25) {
            this.holoCued = true;
            this.setN("titleCue", this.getN("titleCue") + 1);
        }
    }

    private enterCity(): void {
        if (this.entered || this.loadT < 0) {
            return;
        }
        this.entered = true;
        this.enterT = 0;
    }

    private selectTrack(k: i32): void {
        this.track = ((k % NTRACKS) + NTRACKS) % NTRACKS;
        this.progress = 0;
        this.playing = true;
    }

    private handleRequests(): void {
        let req = this.getN("req");
        if (req != 0) {
            if (req == 60) {
                this.enterCity();
            } else if (req == 1) {
                this.setAutopilot(!this.autopilot);
            } else if (req == 2) {
                this.mode = this.mode == 2 ? 0 : 2;
            } else if (req == 3) {
                this.nightT = 1 - this.nightT;
            } else if (req == 4) {
                this.camMode = this.camMode == 0 ? 1 : 0;
            } else if (req == 5) {
                this.mode = (this.mode + 1) % 3;
            } else if (req >= 70 && req <= 72) {
                this.setQuality(<i32>req - 70);
            } else if (req == 80) {
                this.togglePlay();
            } else if (req == 6) {
                this.reboot();
            } else if (req == 7) {
                this.camMode = this.camMode == 2 ? 0 : 2;
            } else if (req >= 10 && req <= 12) {
                this.mode = <i32>req - 10;
            } else if (req == 20) {
                this.taps++;
                this.hitT = 0.7;
            } else if (req == 40) {
                this.playing = !this.playing;
            } else if (req == 41) {
                this.selectTrack(this.track + 1);
            } else if (req == 42) {
                this.selectTrack(this.track - 1);
            } else if (req >= 50 && req <= 55) {
                this.ambient = <i32>req - 50;
            }
            // reset directly: the change cache already holds 0
            let rp = this.numProp("req");
            if (rp != null) {
                rp.value = 0;
            }
        }
        // playlist rows write their own `tap`; the script owns the selection
        let ctx = this.context;
        if (ctx == null) {
            return;
        }
        let vm = ctx.rootViewModel();
        if (vm == null) {
            return;
        }
        let list = vm.getList("tracks");
        if (list == null) {
            return;
        }
        for (let i = 0; i < list.length; i++) {
            let item = list.get(i);
            let tpn = item.getNumber("tap");
            if (tpn != null && tpn.value != 0) {
                tpn.value = 0;
                this.selectTrack(i);
            }
            let sel = item.getNumber("sel");
            if (sel != null) {
                let want: f64 = i == this.track ? 1 : 0;
                if (sel.value != want) {
                    sel.value = want;
                }
            }
        }
    }

    // ------------------------------------------------------------ lights (billboards spill onto the street)
    private updateLights(): void {
        let e = this.eye;
        let cands = new Array<Cand>();
        for (let i = 0; i < this.bbs.length; i++) {
            let b = this.bbs[i];
            let dx = <f64>b.c.x - <f64>e.x;
            let dz = <f64>b.c.z - <f64>e.z;
            let d2 = dx * dx + dz * dz;
            if (d2 < 320 * 320) {
                cands.push(new Cand(d2, b));
            }
        }
        cands.sort((a: Cand, b: Cand): i32 => (a.d < b.d ? -1 : (a.d > b.d ? 1 : 0)));
        let out = new Array<Light>();
        let k = this.night * 0.9 + 0.1;
        for (let i = 0; i < Math.min(16, cands.length); i++) {
            let b = cands[i].b;
            let L = new Light();
            let dd = 4 + b.w * 0.15;
            L.x = <f64>b.c.x + b.nx * dd;
            L.y = <f64>b.c.y - b.h * 0.25;
            L.z = <f64>b.c.z + b.nz * dd;
            L.r = 26 + b.w * 2.2;
            L.cr = BB_LIGHT[b.design * 3];
            L.cg = BB_LIGHT[b.design * 3 + 1];
            L.cb = BB_LIGHT[b.design * 3 + 2];
            let pk: f64 = this.powerR > vlen(vsub(b.c, this.origin)) + 30 ? 1 : 0;
            L.k = k * pk * (1 + b.w / 24);
            out.push(L);
        }
        this.lights = out;
    }

    // ------------------------------------------------------------ per frame
    fpsT: f64 = 0;
    fpsN: i32 = 0;
    fpsMax: f64 = 0;

    // upload queued facade mips: one mip level per step, ~12 ms per frame
    private pumpTex(): void {
        if (this.winQ.length > 0 && this.texJobs.length == 0) {
            let q = this.winQ.shift();
            this.context!.decodeImage(q.data, q.dec);
            return;
        }
        let t0 = clock();
        while (this.texJobs.length > 0 && clock() - t0 < 0.012) {
            let j = this.texJobs[0];
            let tex = j.tex;
            let size = <i32>TexInfo.size;
            let m = j.mip;
            if (tex != null && m < j.mips) {
                let sz = size >> m;
                let reg = new rive_gpu_texture_upload_v1();
                reg.mipLevel = <u32>m;
                reg.layer = j.layer;
                reg.width = <u32>sz;
                reg.height = <u32>sz;
                if (m == 0) {
                    reg.bytesPerRow = <u32>(j.W * 4);
                    tex.upload(reg, j.data);
                } else {
                    let oy = j.y;
                    j.y += sz;
                    let mb = new ArrayBuffer(sz * sz * 4);
                    for (let row = 0; row < sz; row++) {
                        Buffer.copy(mb, <f64>(row * sz * 4), j.data, <f64>(((oy + row) * j.W + size) * 4), <f64>(sz * 4));
                    }
                    reg.bytesPerRow = 0;
                    tex.upload(reg, mb);
                }
                j.mip = m + 1;
            }
            if (tex == null || j.mip >= j.mips) {
                this.texJobs.shift();
                this.texDecoded();
            }
        }
    }

    override advance(seconds: f64): bool {
        this.trySetup();
        this.pumpTex();
        // live frame-time log (real elapsed time in the preview window)
        this.fpsT += seconds;
        this.fpsN++;
        this.fpsMax = Math.max(this.fpsMax, seconds);
        // dynamic resolution: hold ~60 fps; the renderer is fill-rate bound
        this.dynT += seconds;
        this.dynN++;
        this.dynHold -= seconds;
        if (this.dynT >= 1.0) {
            let avg = this.dynT / <f64>this.dynN;
            let want = this.dynScale;
            if (avg > 0.0175) {
                want = Math.max(this.dynMin, this.dynScale - 0.125);
            } else if (avg < 0.0105 && this.dynHold <= 0) {
                want = Math.min(this.dynMax, this.dynScale + 0.125);
            }
            if ((<i32>this.getN("dbgFlags") & 2) != 0) {
                want = 1.5;     // --data=dbgFlags=2: lock the render scale for A/B timing
            }
            if (want != this.dynScale && this.tt > 3) {
                this.dynScale = want;
                this.needsResize = true;
                this.dynHold = 4;
            }
            this.dynT = 0;
            this.dynN = 0;
        }
        if (this.fpsT >= 5) {
            this.log("perf: " + formatFixed(this.fpsT / <f64>this.fpsN * 1000, 2) + " ms avg, " +
                formatFixed(<f64>this.fpsN / this.fpsT, 1) + " fps, worst " + formatFixed(this.fpsMax * 1000, 1) + " ms, " +
                formatInt(<f64>this.gw) + "x" + formatInt(<f64>this.gh) + " internal (x" + formatFixed(this.gScale, 3) + ")");
            this.fpsT = 0;
            this.fpsN = 0;
            this.fpsMax = 0;
        }
        let d = Math.min(seconds, 1.0 / 20);
        this.time += d;
        this.tt += d;
        // title: hold the boot clock at the dive's opening shot until ENTER
        this.dbgNoCull = (<i32>this.getN("dbgFlags") & 1) != 0;
        // bench/debug: --data=benchSkip=1 jumps straight into the drive once the city is loaded
        if (!this.entered && this.loadT >= 0 && this.getN("benchSkip") > 0) {
            this.enterCity();
            this.boot = T_GO + 2;
        }
        this.boot = this.entered ? this.boot + d : Math.min(this.boot + d, T_DIVE);
        if (this.entered) {
            this.enterT += d;
        }
        if (this.city != null) {
            this.loadT = this.loadT < 0 ? 0 : this.loadT + d;
        }
        this.updateTitle(d);
        this.night += (this.nightT - this.night) * (1 - Math.exp(-d * 2.0));
        this.hitT = Math.max(0, this.hitT - d);
        // city rise (behind the title logo) + power waves from the car
        let rb = this.loadT - 0.35;
        this.riseR = rb <= 0 ? 0 : 30 + 5200 * Math.pow(rb / 3.4, 1.7);
        let pb = this.boot - T_POWER;
        this.powerR = pb <= 0 ? 0 : 20 + 2600 * Math.pow(pb / 4.4, 1.8);
        // night start screen: the city powers up right behind the rise (windows, neon, screens) instead
        // of waiting for the car; it stays powered on entering, and replays on a return to the title
        if (!this.entered) {
            this.titlePow = this.nightT > 0.5 ? Math.max(0, this.riseR - 250) : 0;
        }
        this.powerR = Math.max(this.powerR, this.titlePow);
        // ambient colour eases
        this.ambC = mix3(this.ambC, hex(AMB_HEX[this.ambient]), 1 - Math.exp(-d * 5));
        // media clock
        if (this.playing) {
            this.progress += d;
            if (this.progress >= TRACK_DUR[this.track]) {
                this.selectTrack(this.track + 1);
            }
        }
        if (this.city == null) {
            return true;
        }
        this.handleRequests();
        this.drive(d);
        this.simNpcs(d);
        this.updateCamera(d);
        this.placeCockpit();
        this.placeHolo(d);
        this.updateLights();
        this.updateMarkers(d);
        this.updateTrackers(d);
        this.declutterHud(d);
        this.writeTelemetry();
        for (let k = 0; k < this.surfs.length; k++) {
            let sf = this.surfs[k];
            let inst = sf.inst;
            if (inst != null) {
                if (k > 3) {
                    // billboards: sf.live is set by draw()'s exact frustum test (last frame). Hidden
                    // ones don't advance; they catch up (capped) when they come back into view.
                    if (sf.live) {
                        inst.advance(Math.min(seconds + sf.pending, 0.25));
                        sf.pending = 0;
                    } else {
                        sf.pending = Math.min(sf.pending + seconds, 0.25);
                    }
                } else {
                    // cockpit surfaces only matter near the car
                    sf.live = vlen(vsub(this.eye, this.carPos)) < 40;
                    if (sf.live) {
                        inst.advance(seconds);
                    }
                }
            }
        }
        return true;
    }

    // ------------------------------------------------------------ uniforms
    @inline private w4(off: f64, x: f64, y: f64, z: f64, w: f64): void {
        let b = this.scratch;
        Buffer.writef32(b, off, x);
        Buffer.writef32(b, off + 4, y);
        Buffer.writef32(b, off + 8, z);
        Buffer.writef32(b, off + 12, w);
    }

    shCx: f64 = 1e9;
    shCz: f64 = 1e9;
    shValid: bool = false;
    shDirty: bool = true;
    shadowRenders: i32 = 0;

    private writeUBO(o: Obj): void {
        let ubo = o.ubo;
        if (ubo == null) {
            return;
        }
        o.model.writeToBuffer(this.scratch, 0);
        let c = o.day;
        // authored as sRGB, shaded in linear
        this.w4(64, Math.pow(c.r, 2.2), Math.pow(c.g, 2.2), Math.pow(c.b, 2.2), o.rough);
        this.w4(80, 0, <f64>o.mode, o.metal, o.emis);
        this.w4(96, o.bright, o.flash, o.accentMix, o.auxW);
        let a = o.accent;
        let ac = a != null ? a : this.ambC;
        this.w4(112, ac.r, ac.g, ac.b, o.emis);
        this.w4(128, o.fx[0], o.fx[1], o.fx[2], o.fx[3]);
        ubo.update(0, this.scratch, UBO_SIZE);
    }

    private updateSunCam(): void {
        let e = this.eye;
        let fwd = vsub(this.target, e);
        let fl = Math.sqrt(<f64>fwd.x * <f64>fwd.x + <f64>fwd.z * <f64>fwd.z);
        let fx: f64 = 0;
        let fz: f64 = 0;
        if (fl > 1e-4) {
            fx = <f64>fwd.x / fl;
            fz = <f64>fwd.z / fl;
        }
        // centre the map a little ahead of the camera, snapped to limit shimmer
        let snap: f64 = 8;
        let cx = Math.floor((<f64>e.x + fx * SHADOW_HALF * 0.55) / snap + 0.5) * snap;
        let cz = Math.floor((<f64>e.z + fz * SHADOW_HALF * 0.55) / snap + 0.5) * snap;
        // casters are static: re-render only when the snapped centre moves,
        // while the city is still rising, or after night (no shadows) ends
        this.shDirty = !this.shValid || cx != this.shCx || cz != this.shCz || this.riseR < 6000;
        this.shCx = cx;
        this.shCz = cz;
        let c = V(cx, 120, cz);
        let view = Mat4.lookAtVector(vadd(c, sunDir(), 1600), c, V(0, 1, 0));
        // explicit RH ortho, z: -near -> 0, -far -> 1 (WebGPU depth range)
        let h = SHADOW_HALF;
        let n: f64 = 10;
        let fa: f64 = 3400;
        let proj = Mat4.values(<f32>(1 / h), 0, 0, 0, 0, <f32>(1 / h), 0, 0, 0, 0, <f32>(-1 / (fa - n)), 0, 0, 0, <f32>(-n / (fa - n)), 1);
        this.shadowVP = proj * view;
    }

    // tight sun camera around the player car: cabin + body self-shadowing
    private updateCarSunCam(): void {
        let c = this.carModel.transformPoint(0, 0.85, 0.1);
        this.carOrigin = c;
        // relative to the car: shadow depth compares stay sub-millimetre
        let view = Mat4.lookAtVector(vscale(sunDir(), 20), V(0, 0, 0), V(0, 1, 0));
        let h: f64 = 3.1;
        let n: f64 = 0.5;
        let fa: f64 = 40;
        let proj = Mat4.values(<f32>(1 / h), 0, 0, 0, 0, <f32>(1 / h), 0, 0, 0, 0, <f32>(-1 / (fa - n)), 0, 0, 0, <f32>(-n / (fa - n)), 1);
        this.carVP = proj * view;
        this.carShOn = this.night < 0.5 && vlen(vsub(this.eye, this.carPos)) < 90;
    }

    private writeFrame(ubo: GPUBuffer?, vp: Mat4, org: Vector, reflPass: bool, cabPass: bool): void {
        if (ubo == null) {
            return;
        }
        let b = this.scratch;
        vp.writeToBuffer(b, 0);
        this.view.writeToBuffer(b, 64);
        this.invVP.writeToBuffer(b, 128);
        let nt = this.night;
        let e = this.eye;
        this.w4(192, <f64>e.x, <f64>e.y, <f64>e.z, this.time);
        let hz = mix3(hex(0xB9AFA6), hex(0x3A1424), nt);
        let zz = mix3(hex(0x6F7F95), hex(0x05060C), nt);
        this.w4(208, hz.r, hz.g, hz.b, 0.0034 + 0.0012 * nt);
        this.w4(224, zz.r, zz.g, zz.b, 85);
        // the main pass samples the reflection texture at its own screen position
        let rs: f64 = reflPass ? 0.5 : 1;
        this.w4(240, nt, this.rain * nt, <f64>this.gw * rs, <f64>this.gh * rs);
        let sd = vnorm(vadd(vscale(sunDir(), 1 - nt), moonDir(), nt));
        this.w4(256, <f64>sd.x, <f64>sd.y, <f64>sd.z, 1);
        this.w4(272, 1.0 + 0.4 * nt, 1, reflPass ? 1 : 0, cabPass ? 1 : 0);
        this.w4(288, <f64>this.origin.x, <f64>this.origin.z, this.riseR, this.powerR);
        let hl: f64 = this.boot > T_AMB ? 1 : 0;
        this.w4(304, <f64>this.carPos.x, <f64>this.carPos.y, <f64>this.carPos.z, hl * (0.3 + 0.7 * nt));
        this.w4(320, <f64>this.carFwd.x, <f64>this.carFwd.z, this.v, this.alt);
        let gp = tp(this.carModel, Cab.csPos);
        this.w4(336, <f64>gp.x, <f64>gp.y, <f64>gp.z, (0.25 + 0.6 * nt) * clamp((this.boot - T_AMB) / 1.5, 0, 1));
        let ac = this.ambC;
        this.w4(352, ac.r, ac.g, ac.b, <f64>this.lights.length);
        for (let i = 0; i < 16; i++) {
            let off = <f64>(368 + i * 32);
            if (i < this.lights.length) {
                let l = this.lights[i];
                this.w4(off, l.x, l.y, l.z, l.r);
                this.w4(off + 16, l.cr, l.cg, l.cb, l.k);
            } else {
                this.w4(off, 0, -1000, 0, 0);
                this.w4(off + 16, 0, 0, 0, 0);
            }
        }
        // sky / sun / haze
        this.shadowVP.writeToBuffer(b, 880);
        // w: shadows on (>= 0.5); 0.5..1 also carries the fog-beam strength (softer under the title)
        let beamK = 1 - 0.65 * smooth5(this.titleK);
        this.w4(944, 7.2 + (0.05 - 7.2) * nt, 5.0 + (0.06 - 5.0) * nt, 3.2 + (0.09 - 3.2) * nt, nt < 0.5 ? 0.5 + 0.5 * beamK : 0);
        this.w4(960, 0.27 + (0.006 - 0.27) * nt, 0.37 + (0.008 - 0.37) * nt, 0.54 + (0.018 - 0.54) * nt, 0.5);
        this.w4(976, 1.0 + (0.10 - 1.0) * nt, 0.78 + (0.045 - 0.78) * nt, 0.6 + (0.08 - 0.6) * nt, 0.0025 + 0.0008 * nt);
        this.w4(992, 0.5 + (0.05 - 0.5) * nt, 0.5 + (0.035 - 0.5) * nt, 0.53 + (0.07 - 0.53) * nt, 200);
        this.carVP.writeToBuffer(b, 1008);
        this.w4(1072, this.carShOn ? 1 : 0, 0.62, 0, 0);
        this.w4(1088, <f64>org.x, <f64>org.y, <f64>org.z, 0);
        let co = this.carOrigin;
        this.w4(1104, <f64>co.x, <f64>co.y, <f64>co.z, 0);
        ubo.update(0, b, FRAME_SIZE);
    }

    // null frustum = draw everything
    private cull: Frustum? = null;
    private frMain: Frustum = new Frustum();
    private frRefl: Frustum = new Frustum();
    private frShadow: Frustum = new Frustum();
    drawn: f64 = 0;
    total: f64 = 0;
    cullLogged: bool = false;

    // would any chunk of o be drawn by the main or the mirror pass this frame?
    private objSeen(o: Obj): bool {
        let m = o.mesh;
        if (!o.visible || m == null) {
            return false;
        }
        let ch = m.chunks;
        if (ch.length == 0) {
            return true;
        }
        for (let i = 0; i < ch.length; i++) {
            if (this.frMain.visible(ch[i]) || this.frRefl.visible(ch[i])) {
                return true;
            }
        }
        return false;
    }

    private drawObj(pass: GPURenderPass, o: Obj, bg: GPUBindGroup): void {
        let m = o.mesh;
        if (m == null) {
            return;
        }
        let vb = m.vbuf;
        let ib = m.ibuf;
        if (vb == null || ib == null) {
            return;
        }
        pass.setBindGroup(0, bg);
        pass.setVertexBuffer(0, vb);
        pass.setIndexBuffer(ib, <u32>IndexFormat.uint32);
        let fr = this.cull;
        let ch = m.chunks;
        if (fr == null || ch.length == 0) {
            pass.drawIndexed(m.count);
            return;
        }
        // merge consecutive visible chunks into one draw
        let runFirst: u32 = 0;
        let runCount: u32 = 0;
        for (let i = 0; i < ch.length; i++) {
            let c = ch[i];
            this.total += <f64>c.count;
            if (fr.visible(c)) {
                this.drawn += <f64>c.count;
                if (runCount > 0 && runFirst + runCount == c.first) {
                    runCount += c.count;
                } else {
                    if (runCount > 0) {
                        pass.drawIndexed(runCount, 1, runFirst);
                    }
                    runFirst = c.first;
                    runCount = c.count;
                }
            }
        }
        if (runCount > 0) {
            pass.drawIndexed(runCount, 1, runFirst);
        }
    }

    private frameFx(): void {
        let b = this.boot;
        let cl = this.clFace;
        if (cl != null) {
            cl.fx[1] = clamp((b - T_CL) / 0.5, 0, 1);
            cl.bright = b >= T_CL ? 1 : 0;
        }
        let cs = this.csFace;
        if (cs != null) {
            cs.fx[1] = clamp((b - T_CS) / 0.55, 0, 1);
            cs.bright = b >= T_CS ? 1 : 0;
        }
        let hb = this.hubFace;
        if (hb != null) {
            hb.fx[1] = clamp((b - T_HUB) / 0.4, 0, 1);
            hb.bright = b >= T_HUB ? 1 : 0;
        }
        let hd = this.hudObj;
        if (hd != null) {
            hd.fx[1] = clamp((b - T_HUD) / 1.1, 0, 1);
            hd.bright = this.hudOn ? 1 : 0;
        }
        let am = this.ambObj;
        if (am != null) {
            am.fx[1] = clamp((b - T_AMB) / 0.9, 0, 1);
        }
        let gl = this.glassObj;
        if (gl != null) {
            gl.bright = 1;
        }
        for (let i = 0; i < this.ext.length; i++) {
            let o = this.ext[i];
            if (o.mode == 12) {
                o.bright = 0.6 + clamp(this.v / 25, 0, 0.6) + clamp(this.altV * 0.1, 0, 0.4);
            }
        }
    }

    private colorAtt(view: GPUTextureView?, resolve: GPUTextureView?, load: LoadOp): GPUColorAttachment {
        let c = new GPUColorAttachment();
        c.view = view;
        c.resolveTarget = resolve;
        c.loadOp = load;
        c.storeOp = StoreOp.store;
        return c;
    }

    private full(gpu: GPUCanvas, view: GPUTextureView, pipe: GPUPipeline, bg: GPUBindGroup): void {
        let pd = new GPUPassDesc();
        pd.color = [this.colorAtt(view, null, LoadOp.clear)];
        let p = gpu.beginRenderPass(pd);
        p.setPipeline(pipe);
        p.setBindGroup(0, bg);
        p.draw(3);
        p.finish();
    }

    // shaft strength: sun in front of the view (also when just off-screen), by day, out of the title
    private shaftK(): f64 {
        let sd = sunDir();
        let fwd = vnorm(vsub(this.target, this.eye));
        let facing = <f64>fwd.x * <f64>sd.x + <f64>fwd.y * <f64>sd.y + <f64>fwd.z * <f64>sd.z;
        let o4 = new StaticArray<f32>(4);
        this.viewProj.transformVec4(o4, <f32>(<f64>this.eye.x + <f64>sd.x * 5000), <f32>(<f64>this.eye.y + <f64>sd.y * 5000),
            <f32>(<f64>this.eye.z + <f64>sd.z * 5000), 1);
        let cw = <f64>o4[3];
        if (cw <= 0.01 || facing <= 0) {
            return 0;
        }
        this.sunU = (<f64>o4[0] / cw) * 0.5 + 0.5;
        this.sunV = 1 - ((<f64>o4[1] / cw) * 0.5 + 0.5);
        let t = clamp(facing / 0.55, 0, 1);
        // half strength under the title: the white logo needs its contrast
        return t * t * (3 - 2 * t) * (1 - this.night) * SHAFT_GAIN * (1 - 0.85 * smooth5(this.titleK));
    }

    private u16(ubo: GPUBuffer, x: f64, y: f64, z: f64, w: f64): void {
        this.w4(0, x, y, z, w);
        ubo.update(0, this.scratch, 16);
    }

    private imgSampler: ImageSampler = ImageSampler(ImageWrap.clamp, ImageWrap.clamp, ImageFilter.bilinear);

    override draw(renderer: Renderer): void {
        let gpu = this.gpu;
        if (!this.gpuReady || gpu == null || this.litMS == null || this.hdrMSV == null || this.skyBG == null) {
            return;
        }
        if (gpu.width == 0) {
            return;
        }
        this.frameFx();
        // 2. per-object uniforms + sun camera
        let inside = this.inside;
        let nearCar = vlen(vsub(this.eye, this.carPos)) < 30;
        let ssr: f64 = this.envFrames > 1 && !inside ? 1 : 0;
        for (let i = 0; i < this.objs.length; i++) {
            let o = this.objs[i];
            if (o.envMap) {
                o.auxW = ssr;
            }
            if (o.visible && o.bg != null) {
                this.writeUBO(o);
            }
        }
        this.updateSunCam();
        this.updateCarSunCam();
        let zero = V(0, 0, 0);
        let e = this.eye;
        this.writeFrame(this.frameCarShadow, this.carVP, this.carOrigin, false, false);
        let vpR = this.viewProj * Mat4.fromScale(1, -1, 1);
        // mirror pass: mirror(wp) - eye == mirror(wp - mirror(eye))
        let vpRRel = this.viewProjRel * Mat4.fromScale(1, -1, 1);
        this.writeFrame(this.frameShadow, this.shadowVP, zero, false, false);
        this.writeFrame(this.frameMain, this.viewProjRel, e, false, false);
        this.writeFrame(this.frameRefl, vpRRel, V(<f64>e.x, -<f64>e.y, <f64>e.z), true, false);
        this.writeFrame(this.frameCab, this.viewProjBRel, e, false, true);
        this.frMain.set(this.viewProj);
        this.frRefl.set(vpR);
        this.frShadow.set(this.shadowVP);
        // 1. live Rive surfaces -> textures. A billboard canvas renders only when a chunk of its design
        // passes the main or mirrored frustum (the same test the draws use), so a skipped canvas is
        // never sampled (a canvas that skips a frame samples as undefined). Cockpit screens follow
        // sf.live (set in advance: near the car).
        // cockpit screens: the HUD only shows from the seat; cluster / console / hub only when the car
        // itself is inside the main frustum (chase / showroom see them through the canopy)
        let cc = this.carChunk;
        let p0 = this.carPos;
        cc.minX = <f64>p0.x - 4;
        cc.maxX = <f64>p0.x + 4;
        cc.minY = <f64>p0.y - 2;
        cc.maxY = <f64>p0.y + 3;
        cc.minZ = <f64>p0.z - 4;
        cc.maxZ = <f64>p0.z + 4;
        let carSeen = this.inside || this.frMain.visible(cc) || this.frRefl.visible(cc);
        for (let i = 0; i < this.surfs.length; i++) {
            let sf = this.surfs[i];
            if (i < 4 && sf.live) {
                sf.live = i == 3 ? this.inside : carSeen;
            }
            if (i >= 4) {
                sf.live = this.dbgNoCull;
                for (let j = 0; j < this.bbObjs.length && !sf.live; j++) {
                    let bo = this.bbObjs[j];
                    sf.live = bo.tex == i + 1 && this.objSeen(bo);
                }
            }
            let c = sf.canvas;
            let inst = sf.inst;
            if (c != null && inst != null && sf.live) {
                let r = c.beginFrame(sf.clear);
                if (r != null) {
                    r.save();
                    let k = <f32>(<f64>c.width / sf.w);
                    r.transform(Mat2D.withScale(k, k));
                    inst.draw(r);
                    r.restore();
                    c.endFrame();
                }
            }
        }
        this.drawn = 0;
        this.total = 0;

        // 2b. sun shadow map
        let sp = this.shadowPipe;
        if (this.night >= 0.5) {
            this.shValid = false;
        }
        if (sp != null && this.night < 0.5 && this.shDirty) {
            this.shValid = true;
            this.shadowRenders++;
            let pd = new GPUPassDesc();
            pd.depthView = this.shadowAttV;
            pd.depthLoadOp = LoadOp.clear;
            pd.depthStoreOp = StoreOp.store;
            pd.depthClearValue = 1;
            let ps = gpu.beginRenderPass(pd);
            ps.setViewport(0, 0, <f32>SHADOW_N, <f32>SHADOW_N);
            ps.setScissor(0, 0, SHADOW_N, SHADOW_N);
            ps.setPipeline(sp);
            this.cull = this.frShadow;
            for (let i = 0; i < this.objs.length; i++) {
                let o = this.objs[i];
                let bg = o.bgS;
                if (o.visible && bg != null) {
                    this.drawObj(ps, o, bg);
                }
            }
            let gb = this.cm("gbox");
            let gi = this.cm("greeble_inst");
            if (this.greebleShadow != null && gb != null && gi != null && gb.vbuf != null && gi.vbuf != null) {
                ps.setPipeline(this.greebleShadow!);
                ps.setBindGroup(0, this.shadowSkyBG!);
                ps.setVertexBuffer(0, gb.vbuf!);
                ps.setVertexBuffer(1, gi.vbuf!);
                ps.setIndexBuffer(gb.ibuf!, <u32>IndexFormat.uint32);
                ps.drawIndexed(gb.count, gi.vcount);
            }
            ps.finish();
            this.cull = null;
        }

        // 2c. car self-shadow map
        if (sp != null && this.carShOn) {
            let pd = new GPUPassDesc();
            pd.depthView = this.shadowAttV;
            pd.depthLoadOp = LoadOp.load;
            pd.depthStoreOp = StoreOp.store;
            let pc = gpu.beginRenderPass(pd);
            pc.setViewport(<f32>SHADOW_N, 0, <f32>CAR_SN, <f32>CAR_SN);
            pc.setScissor(SHADOW_N, 0, CAR_SN, CAR_SN);
            // clear just the car's region (the city map stays cached)
            pc.setPipeline(this.clearPipe!);
            pc.setBindGroup(0, this.skyBG!);
            pc.draw(3);
            pc.setPipeline(sp);
            for (let i = 0; i < this.objs.length; i++) {
                let o = this.objs[i];
                let bg = o.bgCS;
                if (o.visible && bg != null) {
                    this.drawObj(pc, o, bg);
                }
            }
            pc.finish();
        }

        // 3. mirrored world for the wet streets
        {
            let pd = new GPUPassDesc();
            pd.color = [this.colorAtt(this.reflV, null, LoadOp.clear)];
            pd.depthView = this.reflDepthV;
            pd.depthLoadOp = LoadOp.clear;
            pd.depthStoreOp = StoreOp.discard;
            let pr = gpu.beginRenderPass(pd);
            pr.setPipeline(this.litR!);
            this.cull = this.frRefl;
            for (let i = 0; i < this.objs.length; i++) {
                let o = this.objs[i];
                let m = o.mode;
                let bg = o.bgR;
                if (o.visible && bg != null && o.refl && m != 3 && m != 4 && m != 13 && !(o.ext && inside) && !o.noRefl) {
                    this.drawObj(pr, o, bg);
                }
            }
            this.cull = null;
            pr.setPipeline(this.skyR!);
            pr.setBindGroup(0, this.skyRBG!);
            pr.draw(3);
            pr.finish();
        }

        // 4. world (MSAA HDR)
        {
            let pd = new GPUPassDesc();
            pd.color = [this.colorAtt(this.hdrMSV, inside ? null : this.hdrV, LoadOp.clear)];
            pd.depthView = this.depthMSV;
            pd.depthLoadOp = LoadOp.clear;
            pd.depthStoreOp = StoreOp.discard;
            let pass = gpu.beginRenderPass(pd);
            this.cull = this.frMain;
            // depth pre-pass for the big occluders (facades are the expensive shader)
            pass.setPipeline(this.depthMS!);
            for (let i = 0; i < this.objs.length; i++) {
                let o = this.objs[i];
                let bg = o.bg;
                if (o.visible && bg != null && o.mode == 2) {
                    this.drawObj(pass, o, bg);
                }
            }
            let cur = 0;
            for (let i = 0; i < this.objs.length; i++) {
                let o = this.objs[i];
                let bg = o.bg;
                let drawIt = bg != null && o.visible;
                if (drawIt && o.pass == 2) {
                    drawIt = !inside && nearCar;
                } else if (drawIt && o.pass == 3) {
                    drawIt = false;
                }
                if (drawIt && (o.glass || o.mode == 16)) {
                    drawIt = false;
                }
                if (drawIt && bg != null) {
                    let want = o.cull ? 2 : 1;
                    if (want != cur) {
                        pass.setPipeline(want == 2 ? this.litMSCull! : this.litMS!);
                        cur = want;
                    }
                    this.drawObj(pass, o, bg);
                }
            }
            this.cull = null;
            let gb = this.cm("gbox");
            let gi = this.cm("greeble_inst");
            if (this.greebleMS != null && gb != null && gi != null && gb.vbuf != null && gi.vbuf != null) {
                pass.setPipeline(this.greebleMS!);
                pass.setBindGroup(0, this.skyBG!);
                pass.setVertexBuffer(0, gb.vbuf!);
                pass.setVertexBuffer(1, gi.vbuf!);
                pass.setIndexBuffer(gb.ibuf!, <u32>IndexFormat.uint32);
                pass.drawIndexed(gb.count, gi.vcount);
            }
            let swm = this.cm("swarmcar");
            let swp = this.swarmPipe;
            let swb = this.swarmBuf;
            if (swp != null && swm != null && swb != null && swm.vbuf != null) {
                pass.setPipeline(swp);
                pass.setBindGroup(0, this.skyBG!);
                pass.setVertexBuffer(0, swm.vbuf!);
                pass.setVertexBuffer(1, swb);
                pass.setIndexBuffer(swm.ibuf!, <u32>IndexFormat.uint32);
                pass.drawIndexed(swm.count, <u32>Math.max(1, Math.floor(<f64>this.swarmN * this.swarmFrac)));
            }
            pass.setPipeline(this.skyMS!);
            pass.setBindGroup(0, this.skyBG!);
            pass.draw(3);
            // light cones hanging in the haze
            let co = this.conesObj;
            if (co != null && co.bg != null && co.visible && this.coneMS != null) {
                pass.setPipeline(this.coneMS!);
                this.cull = this.frMain;
                this.drawObj(pass, co, co.bg!);
                this.cull = null;
            }
            // the player's smoked canopy, see-through to the sculpted cabin
            if (!inside) {
                pass.setPipeline(this.glassMS!);
                for (let i = 0; i < this.ext.length; i++) {
                    let o = this.ext[i];
                    let bg = o.bg;
                    if (o.glass && o.visible && bg != null) {
                        this.drawObj(pass, o, bg);
                    }
                }
            }
            // holo blade signs (additive light)
            let hob = this.holoBuf;
            if (this.holoMS != null && hob != null && this.holoN > 0) {
                pass.setPipeline(this.holoMS!);
                pass.setBindGroup(0, this.skyBG!);
                pass.setVertexBuffer(0, hob);
                pass.draw(6, this.holoN);
            }
            // steam plumes (after the opaque city + cones, before rain)
            let stb = this.steamBuf;
            if (this.steamMS != null && stb != null && this.steamN > 0) {
                pass.setPipeline(this.steamMS!);
                pass.setBindGroup(0, this.skyBG!);
                pass.setVertexBuffer(0, stb);
                pass.draw(6 * 14, this.steamN);
            }
            if (this.rain * this.night > 0.02) {
                pass.setPipeline(this.rainMS!);
                pass.setBindGroup(0, this.skyBG!);
                pass.draw(6 * 1100);
            }
            pass.finish();
        }
        // 4b. last-frame environment for the car's screen-space reflections
        if (!inside && this.envBG != null) {
            this.u16(this.envUbo!, 1.5 / <f64>this.gw, 1.5 / <f64>this.gh, 0, 0);
            this.full(gpu, this.envV!, this.brightPipe!, this.envBG!);
            this.envFrames++;
        } else {
            this.envFrames = 0;
        }

        // 5. cockpit (fresh depth range) + glass, resolve
        if (inside) {
            let pd = new GPUPassDesc();
            pd.color = [this.colorAtt(this.hdrMSV, this.hdrV, LoadOp.load)];
            pd.depthView = this.depthMSV;
            pd.depthLoadOp = LoadOp.clear;
            pd.depthStoreOp = StoreOp.discard;
            let pb = gpu.beginRenderPass(pd);
            pb.setPipeline(this.litMS!);
            for (let i = 0; i < this.cab.length; i++) {
                let o = this.cab[i];
                let bg = o.bgC;
                if (bg != null && o.visible && o.pass == 2) {
                    this.drawObj(pb, o, bg);
                }
            }
            pb.setPipeline(this.glassMS!);
            let gl = this.glassObj;
            if (gl != null && gl.bgC != null) {
                this.drawObj(pb, gl, gl.bgC!);
            }
            let hd = this.hudObj;
            if (hd != null && hd.bgC != null && this.boot >= T_HUD) {
                // additive light; alpha min() tags lit HUD pixels as cockpit so TAA never smears them
                pb.setPipeline(this.hudMS!);
                this.drawObj(pb, hd, hd.bgC!);
            }
            pb.finish();
        }

        // 5c. title holo: fresh depth, additive light (alpha-tagged so TAA keeps it crisp)
        if (this.holoOn && this.holo.length > 0) {
            let pd = new GPUPassDesc();
            pd.color = [this.colorAtt(this.hdrMSV, this.hdrV, LoadOp.load)];
            pd.depthView = this.depthMSV;
            pd.depthLoadOp = LoadOp.clear;
            pd.depthStoreOp = StoreOp.discard;
            let ph = gpu.beginRenderPass(pd);
            if (this.holoBackMS != null) {
                ph.setPipeline(this.holoBackMS!);
                for (let i = 0; i < this.holoBacks.length; i++) {
                    let hb = this.holoBacks[i];
                    if (hb.visible && hb.bgC != null) {
                        this.drawObj(ph, hb, hb.bgC!);
                    }
                }
            }
            ph.setPipeline(this.hudMS!);
            for (let i = 0; i < this.holo.length; i++) {
                let o = this.holo[i];
                let bg = o.bgC;
                if (o.visible && bg != null) {
                    this.drawObj(ph, o, bg);
                }
            }
            ph.finish();
        }

        if (!this.cullLogged && this.time > 22) {
            this.cullLogged = true;
            this.log("world: culling drew " + formatFixed(this.drawn / Math.max(this.total, 1) * 100, 1) + "% of chunked city indices");
        }
        // 5b. temporal AA (world layer; cockpit passes through)
        let useTaa = this.taaPipe != null && this.taaBG.length == 2;
        if (useTaa) {
            let b = this.scratch;
            let inv = this.viewProjRelNJ.invert();
            (inv != null ? inv! : Mat4.identity()).writeToBuffer(b, 0);
            this.prevVPRel.writeToBuffer(b, 64);
            let ce = this.eye;
            let pe = this.prevEye;
            let dx = <f64>ce.x - <f64>pe.x;
            let dy = <f64>ce.y - <f64>pe.y;
            let dz = <f64>ce.z - <f64>pe.z;
            let ok = this.taaValid && dx * dx + dy * dy + dz * dz < 40 * 40;
            this.w4(128, dx, dy, dz, ok ? 1 : 0);
            this.w4(144, 1 / <f64>this.gw, 1 / <f64>this.gh, 0.1, 0);
            this.taaUbo!.update(0, b, 160);
            this.full(gpu, this.taaV[this.taaIdx], this.taaPipe!, this.taaBG[this.taaIdx]);
            this.prevVPRel = this.viewProjRelNJ;
            this.prevEye = this.eye;
            this.taaValid = true;
        }

        // 5c. sun shafts: march toward the sun's screen position over the sky
        let shK = this.shaftK();
        if (this.shaftPipe != null && this.shaftBG != null) {
            this.u16(this.shaftUbo!, this.sunU, this.sunV, 0.55, 0.965);
            this.full(gpu, this.shaftV!, this.shaftPipe!, this.shaftBG!);
        }

        // 6. bloom chain
        this.u16(this.downUbos[0], 1.5 / <f64>this.gw, 1.5 / <f64>this.gh, 1.5, 0.7);
        this.u16(this.downUbos[1], 1 / <f64>this.b1w, 1 / <f64>this.b1h, 0, 0);
        this.u16(this.downUbos[2], 1 / <f64>this.b2w, 1 / <f64>this.b2h, 0, 0);
        for (let i = 0; i < 6; i++) {
            let lvl = i / 2;
            let bw = <f64>(lvl == 0 ? this.b1w : (lvl == 1 ? this.b2w : this.b3w));
            let bh = <f64>(lvl == 0 ? this.b1h : (lvl == 1 ? this.b2h : this.b3h));
            let horiz = i % 2 == 0;
            this.u16(this.blUbos[i], horiz ? 1 / bw : 0, horiz ? 0 : 1 / bh, 1.3, 0);
        }
        let bp = this.brightPipe!;
        let lp = this.blurPipe!;
        this.full(gpu, this.b1V!, bp, this.downBGs[0]);
        this.full(gpu, this.b1tV!, lp, this.blBGs[0]);
        this.full(gpu, this.b1V!, lp, this.blBGs[1]);
        this.full(gpu, this.b2V!, bp, this.downBGs[1]);
        this.full(gpu, this.b2tV!, lp, this.blBGs[2]);
        this.full(gpu, this.b2V!, lp, this.blBGs[3]);
        this.full(gpu, this.b3V!, bp, this.downBGs[2]);
        this.full(gpu, this.b3tV!, lp, this.blBGs[4]);
        this.full(gpu, this.b3V!, lp, this.blBGs[5]);

        // 7. composite
        let nt = this.night;
        let spd = clamp((Math.abs(this.v) - 12) / 30, 0, 1) * 0.04 * (1 - this.camBlend * 0.5);
        let zoom = Math.max(spd, this.camSpeed * 0.045);
        let fwd = vsub(this.target, this.eye);
        let o4 = new StaticArray<f32>(4);
        this.viewProj.transformVec4(o4, <f32>(<f64>this.eye.x + <f64>fwd.x * 50), <f32>(<f64>this.eye.y + <f64>fwd.y * 50),
            <f32>(<f64>this.eye.z + <f64>fwd.z * 50), 1);
        let zx: f64 = 0.5;
        let zy: f64 = 0.5;
        let cw = <f64>o4[3];
        if (cw > 0.01) {
            zx = clamp((<f64>o4[0] / cw) * 0.5 + 0.5, 0.1, 0.9);
            zy = clamp(1 - ((<f64>o4[1] / cw) * 0.5 + 0.5), 0.1, 0.9);
        }
        this.w4(0, 0.58 + 0.12 * nt, this.time, 0.001, 0.016);
        this.w4(16, zx, zy, zoom, smooth5(this.titleK));
        this.w4(32, 0.09, 0.13, 0.2, 0.32);
        this.w4(48, 0.004 * nt, 0.002 * nt, 0.008 * nt, 1.18 - 0.06 * nt);
        let dy = 1 - nt;
        this.w4(64, 1 + 0.06 * dy, 1, 1 - 0.1 * dy, 0.34 * dy + 0.08 * nt);
        let sc = SUN_TINT;
        this.w4(80, sc.x * shK, sc.y * shK, sc.z * shK, 0);
        this.finUbo!.update(0, this.scratch, 96);
        {
            let pd = new GPUPassDesc();
            pd.color = [this.colorAtt(null, null, LoadOp.clear)];
            let p3 = gpu.beginRenderPass(pd);
            p3.setPipeline(this.finalPipe!);
            p3.setBindGroup(0, useTaa ? this.finBGs[this.taaIdx] : this.finBG!);
            p3.draw(3);
            p3.finish();
        }
        if (useTaa) {
            this.taaIdx = 1 - this.taaIdx;
        }
        renderer.save();
        let inv = <f32>(1 / this.outScale);
        renderer.transform(Mat2D.withScale(inv, inv));
        renderer.drawImage(gpu.image, this.imgSampler, BlendMode.srcOver, <f32>this.worldOp);
        renderer.restore();
    }

    // ------------------------------------------------------------ input
    private reboot(): void {
        // back to the title: overview + logo + ENTER THE CITY, the city rises again
        this.boot = 0;
        this.entered = false;
        this.tt = 0;
        this.enterT = -1;
        if (this.loadT >= 0) {
            this.loadT = 0;
        }
        this.v = 0;
        this.autopilot = true;
        this.mode = 0;
        this.alt = 62;
        this.altV = 0;
        this.resetPose();
        this.headYaw = 0;
        this.headPitch = 0;
        this.headVel = 0;
        this.camMode = 0;
        this.camBlend = 0;
        this.instanceSurfs();
        this.rebuildBindGroups();
        this.cLogo.clear();
        this.setLogo("logo", false);
        this.setLogo("logoHub", false);
        this.setLogo("logoBB", false);
        // bump the decrypt cues so every string replays
        this.setN("cue", this.getN("cue") + 1);
    }

    override keyboardEvent(event: KeyboardEvent): bool {
        if (event.control || event.meta || event.alt) {
            return false;
        }
        let k = <i32>event.key;
        // title screen: only ENTER / SPACE (go), N (day/night) and R are live
        if (!this.entered && k != KEY_ENTER && k != KEY_KP_ENTER && k != KEY_SPACE && k != KEY_N && k != KEY_R) {
            return false;
        }
        let held = k == KEY_UP || k == KEY_DOWN || k == KEY_LEFT || k == KEY_RIGHT || k == KEY_W || k == KEY_A || k == KEY_S || k == KEY_D;
        if (held) {
            if (event.phase == "down" || event.phase == "repeat") {
                this.keys[k] = true;
            } else if (event.phase == "up") {
                this.keys[k] = false;
            }
            return true;
        }
        if (event.phase != "down") {
            return false;
        }
        if (!this.entered && (k == KEY_ENTER || k == KEY_KP_ENTER || k == KEY_SPACE)) {
            this.enterCity();
            return true;
        }
        if (k == KEY_R) {
            this.reboot();
        } else if (k == KEY_N) {
            this.nightT = 1 - this.nightT;
        } else if (k == KEY_M) {
            this.mode = (this.mode + 1) % 3;
        } else if (k == KEY_F) {
            this.mode = this.mode == 2 ? 0 : 2;
        } else if (k == KEY_C) {
            this.camMode = this.camMode == 1 ? 0 : 1;
        } else if (k == KEY_O) {
            // showroom orbit around the car
            this.camMode = this.camMode == 2 ? 0 : 2;
        } else if (k == KEY_P) {
            this.setAutopilot(!this.autopilot);
        } else if (k == KEY_T) {
            this.selectTrack(this.track + 1);
        } else if (k == KEY_H) {
            this.hudOn = !this.hudOn;
        } else if (k == KEY_E) {
            this.togglePlay();
        } else if (k == KEY_ESC && this.play > 0) {
            this.play = 0;
        } else {
            return false;
        }
        return true;
    }

    // ray from a screen position (world space)
    private ro: Vector = V(0, 0, 0);
    private rd: Vector = V(0, 0, -1);

    private screenRay(pos: Vector): void {
        let nx = <f64>pos.x / this.sizeX * 2 - 1;
        let ny = 1 - <f64>pos.y / this.sizeY * 2;
        // analytic ray from the camera basis: unprojecting through the inverse of
        // a near 0.25 / far 5000 matrix at ~1 km world coords loses metres in f32
        // and made screen clicks miss depending on where the car was
        let th = Math.tan(this.fov / 2);
        let d = vadd(vadd(this.camF, this.camR, nx * th * this.camAspect), this.camU, ny * th);
        this.ro = this.eye;
        this.rd = vnorm(d);
    }

    private tryFlat(hit: Hit, k: i32, o: Obj?, w: f64, h: f64, zp: f64, round: f64, only: i32): void {
        if (o == null || (only != 0 && only != k)) {
            return;
        }
        let inv = o.model.invert();
        if (inv == null) {
            return;
        }
        let a = tp(inv, this.ro);
        let b = tp(inv, vadd(this.ro, this.rd, 1));
        let dz = <f64>b.z - <f64>a.z;
        if (Math.abs(dz) < 1e-9) {
            return;
        }
        let t = (zp - <f64>a.z) / dz;
        if (t <= 0) {
            return;
        }
        let x = <f64>a.x + (<f64>b.x - <f64>a.x) * t;
        let y = <f64>a.y + (<f64>b.y - <f64>a.y) * t;
        let u = x / w + 0.5;
        let v = 0.5 - y / h;
        if (round > 0) {
            if (x * x + y * y > round * round && only == 0) {
                return;
            }
        } else if ((u < 0 || u > 1 || v < 0 || v > 1) && only == 0) {
            return;
        }
        let wt = vlen(vsub(V(x, y, zp), a));
        if (wt < hit.t) {
            let sf = this.surfs[k - 1];
            hit.t = wt;
            hit.k = k;
            hit.p = V(u * sf.w, v * sf.h, 0);
        }
    }

    private tryArc(hit: Hit, k: i32, o: Obj?, only: i32): void {
        if (o == null || (only != 0 && only != k)) {
            return;
        }
        let inv = o.model.invert();
        if (inv == null) {
            return;
        }
        let a = tp(inv, this.ro);
        let b = tp(inv, vadd(this.ro, this.rd, 1));
        let R = Cab.clR;
        let ox = <f64>a.x;
        let oz = <f64>a.z + R;
        let dx = <f64>b.x - <f64>a.x;
        let dy = <f64>b.y - <f64>a.y;
        let dz = <f64>b.z - <f64>a.z;
        let A_ = dx * dx + dz * dz;
        let B_ = 2 * (ox * dx + oz * dz);
        let C_ = ox * ox + oz * oz - R * R;
        let disc = B_ * B_ - 4 * A_ * C_;
        if (disc < 0 || A_ < 1e-12) {
            return;
        }
        let t = (-B_ + Math.sqrt(disc)) / (2 * A_);
        let x = <f64>a.x + dx * t;
        let y = <f64>a.y + dy * t;
        let z = <f64>a.z + dz * t;
        let span = Cab.clW / R;
        let ang = Math.atan2(x, z + R);
        let u = (ang + span / 2) / span;
        let v = 0.5 - y / Cab.clH;
        if ((u < 0 || u > 1 || v < 0 || v > 1) && only == 0) {
            return;
        }
        let wt = vlen(vsub(V(x, y, z), a));
        if (wt < hit.t) {
            let sf = this.surfs[k - 1];
            hit.t = wt;
            hit.k = k;
            hit.p = V(u * sf.w, v * sf.h, 0);
        }
    }

    // pick a cockpit screen / billboard (1-based surface index, artboard coords)
    private pick(pos: Vector, only: i32): Hit {
        let hit = new Hit();
        if (this.sizeX <= 0) {
            return hit;
        }
        this.screenRay(pos);
        if (this.inside || this.camMode == 0) {
            this.tryArc(hit, 1, this.clFace, only);
            this.tryFlat(hit, 2, this.csFace, Cab.csW, Cab.csH, 0, 0, only);
            this.tryFlat(hit, 3, this.hubFace, Cab.hubR * 2, Cab.hubR * 2, 0.0125, Cab.hubR, only);
        }
        if (hit.k > 0) {
            return hit;
        }
        let ro = this.ro;
        let rd = this.rd;
        for (let i = 0; i < this.bbs.length; i++) {
            let bb = this.bbs[i];
            let k = 5 + bb.design;
            if (only == 0 || only == k) {
                let denom = <f64>rd.x * bb.nx + <f64>rd.z * bb.nz;
                if (denom < -1e-6) {
                    let t = ((<f64>bb.c.x - <f64>ro.x) * bb.nx + (<f64>bb.c.z - <f64>ro.z) * bb.nz) / denom;
                    if (t > 0 && t < hit.t) {
                        let hp = vadd(ro, rd, t);
                        let lx = (<f64>hp.x - <f64>bb.c.x) * bb.rx + (<f64>hp.z - <f64>bb.c.z) * bb.rz;
                        let ly = <f64>hp.y - <f64>bb.c.y;
                        let u = lx / bb.w + 0.5;
                        let v = 0.5 - ly / bb.h;
                        if (u >= 0 && u <= 1 && v >= 0 && v <= 1) {
                            let sf = this.surfs[k - 1];
                            hit.t = t;
                            hit.k = k;
                            hit.p = V(u * sf.w, v * sf.h, 0);
                        }
                    }
                }
            }
        }
        return hit;
    }

    private surfInst(k: i32): Artboard? {
        if (k <= 0 || k > this.surfs.length) {
            return null;
        }
        return this.surfs[k - 1].inst;
    }

    override pointerMove(event: PointerEvent): void {
        let pos = event.position;
        if (!this.entered) {
            // home screen: remember where the mouse is (-1..1) for the camera tilt
            this.tmxT = clamp(<f64>pos.x / Math.max(this.sizeX, 1) * 2 - 1, -1, 1);
            this.tmyT = clamp(<f64>pos.y / Math.max(this.sizeY, 1) * 2 - 1, -1, 1);
            return;
        }
        if (this.down && this.pressSurf > 0) {
            let h = this.pick(pos, this.pressSurf);
            let inst = this.surfInst(this.pressSurf);
            if (h.k > 0 && inst != null) {
                inst.pointerMove(new PointerEvent(event.id, h.p));
            }
            event.hit();
            return;
        }
        if (this.down && this.play == 2) {
            event.hit();
            return;
        }
        if (this.down) {
            let dx = <f64>pos.x - <f64>this.downPos.x;
            let dy = <f64>pos.y - <f64>this.downPos.y;
            if (!this.dragging && dx * dx + dy * dy > DRAG_SLOP * DRAG_SLOP) {
                this.dragging = true;
                this.lookHome = false;
            }
            if (this.dragging) {
                let mx = <f64>pos.x - <f64>this.lastPos.x;
                let my = <f64>pos.y - <f64>this.lastPos.y;
                this.headYaw = clamp(this.headYaw - mx * 0.004, -1.3, 1.3);
                this.headPitch = clamp(this.headPitch - my * 0.003, -0.45, 0.5);
                this.headVel = this.headVel * 0.5 - mx * 0.004 * 30;
                this.lastPos = pos;
                event.hit();
                return;
            }
            this.lastPos = pos;
        }
        let h = this.pick(pos, 0);
        if (h.k != this.hoverSurf && this.hoverSurf > 0) {
            let inst = this.surfInst(this.hoverSurf);
            if (inst != null) {
                inst.pointerExit(new PointerEvent(event.id, V(-100, -100, 0)));
            }
        }
        this.hoverSurf = h.k;
        if (h.k > 0) {
            let inst = this.surfInst(h.k);
            if (inst != null) {
                inst.pointerMove(new PointerEvent(event.id, h.p));
            }
        }
    }

    private pressP: Vector = V(0, 0, 0);

    private rayHitsCar(pos: Vector): bool {
        this.screenRay(pos);
        let c = tp(this.carModel, V(0, 0.75, 0.1));
        let oc = vsub(c, this.ro);
        let t = vdot(oc, this.rd);
        if (t < 0) {
            return false;
        }
        let d2 = vdot(oc, oc) - t * t;
        return d2 < 2.4 * 2.4;
    }

    override pointerDown(event: PointerEvent): void {
        // title: any click engages (the holo button floats over the whole view)
        if (!this.entered) {
            this.enterCity();
            return;
        }
        this.down = true;
        this.dragging = false;
        this.downPos = event.position;
        this.lastPos = event.position;
        this.headVel = 0;
        let h = this.pick(event.position, 0);
        this.pressSurf = h.k;
        this.pressP = h.p;
        if (h.k > 0) {
            let inst = this.surfInst(h.k);
            if (inst != null) {
                inst.pointerDown(new PointerEvent(event.id, h.p));
            }
        }
        event.hit();
    }

    override pointerUp(event: PointerEvent): void {
        if (this.pressSurf > 0) {
            let h = this.pick(event.position, this.pressSurf);
            let inst = this.surfInst(this.pressSurf);
            // always release the pressed artboard, even if the camera moved away
            // meanwhile (a stuck press leaves its listeners dead)
            if (inst != null) {
                inst.pointerUp(new PointerEvent(event.id, h.k > 0 ? h.p : this.pressP));
            }
        }
        if (this.dragging) {
            this.releaseT = this.time;
        }
        this.down = false;
        this.dragging = false;
        this.pressSurf = 0;
        event.hit();
    }

    override pointerExit(event: PointerEvent): void {
        this.tmxT = 0;
        this.tmyT = 0;
        if (this.pressSurf > 0) {
            let pi = this.surfInst(this.pressSurf);
            if (pi != null) {
                pi.pointerUp(new PointerEvent(event.id, this.pressP));
            }
        }
        this.down = false;
        this.dragging = false;
        this.pressSurf = 0;
        if (this.hoverSurf > 0) {
            let inst = this.surfInst(this.hoverSurf);
            if (inst != null) {
                inst.pointerExit(new PointerEvent(event.id, V(-100, -100, 0)));
            }
        }
        this.hoverSurf = 0;
    }
}
