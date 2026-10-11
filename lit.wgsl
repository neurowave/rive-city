// lit.wgsl — HDR forward renderer for Rive City.
// One shader, many materials (o.params.y = mode):
//   0 lit surface (paint, metal, trim)  1 live Rive screen (cockpit)
//   2 tower facades (windows, glass, panels)  3 wet road (planar reflection)
//   4 wet pavement / ground  5 flat emissive  8 neon tubes  9 cabin ambient strip
//   10 billboard face (live Rive artboard)  11 cockpit interior  12 thrusters
//   13 road paint (zebra)
// Extra entry points: sky (fullscreen), rain (procedural instanced streaks),
// glass (windshield HUD + rain-beaded tint).
// Output: linear HDR rgb; alpha = 1 for the world, 0.25 for the cockpit
// (final.wgsl masks the speed blur with it).

struct Light { pos: vec4f, col: vec4f, };

struct Frame {
    viewProj: mat4x4<f32>,
    view: mat4x4<f32>,
    invViewProj: mat4x4<f32>,
    cam: vec4f,      // xyz camera, w time
    fogA: vec4f,     // rgb horizon haze, w density
    fogB: vec4f,     // rgb zenith, w height falloff (m)
    misc: vec4f,     // x night, y rain, z screen w, w screen h
    sun: vec4f,      // xyz towards the moon/sun, w intensity
    street: vec4f,   // x neon street glow, y exposure, z reflection pass (1), w cockpit pass (1)
    rise: vec4f,     // xy origin xz, z rise radius, w power radius
    car: vec4f,      // xyz car, w headlights
    carFwd: vec4f,   // xy forward xz, z speed, w altitude
    cabin: vec4f,    // xyz cabin glow (world), w strength
    ambC: vec4f,     // rgb cabin ambient colour, w lights count
    lights: array<Light, 16>,
    shadowVP: mat4x4<f32>,
    sunCol: vec4f,   // rgb sun radiance, w shadows on (1)
    skyZen: vec4f,   // rgb zenith, w cloud cover
    skyHor: vec4f,   // rgb horizon, w fog density at street level
    fogC: vec4f,     // rgb fog ambient (sky light in the haze), w height falloff (m)
    carVP: mat4x4<f32>, // sun camera fitted around the player car (cabin shadows)
    carSh: vec4f,    // x car shadows on, y cabin glass transmission
    // camera-relative rendering: viewProj has no large translation; vertices
    // subtract this origin (the eye) first, so f32 precision is spent near the
    // camera instead of on the city's ~1 km world coordinates (z-fighting in the car)
    origin: vec4f,
    carOrigin: vec4f, // carVP is relative to this point (the car)
};

struct Obj {
    model: mat4x4<f32>,
    base: vec4f,     // rgb albedo, w roughness
    params: vec4f,   // x mask, y mode, z metal, w emissive scale
    aux: vec4f,      // x brightness, y flash, z accent mix, w spare
    accent: vec4f,   // rgb accent, w emissive
    fx: vec4f,       // x glitch, y trace / scan progress, z dissolve, w spare
};

@group(0) @binding(0) var<uniform> o: Obj;
@group(0) @binding(1) var tex: texture_2d<f32>;
@group(0) @binding(2) var samp: sampler;
@group(0) @binding(3) var<uniform> f: Frame;
@group(0) @binding(4) var refl: texture_2d<f32>;
@group(0) @binding(5) var albA: texture_2d_array<f32>;
@group(0) @binding(6) var nrmA: texture_2d_array<f32>;
@group(0) @binding(7) var shadowTex: texture_depth_2d;

const CAR_SN = 1024;
var<private> gCar: bool = false;

const SHADOW_N = 2048;
// tools/make_tex.py tile sizes (metres) per facade layer
const TILE_U = array<f32, 6>(70.0, 9.87, 9.02, 42.0, 34.55, 39.62);
const TILE_V = array<f32, 6>(70.0, 13.46, 13.54, 42.0, 24.66, 39.62);
// typical window size (m) and window coverage per facade layer (tools/make_winmap.py)
const WIN_SZ = array<vec2f, 6>(vec2f(1.16, 1.16), vec2f(3.21, 2.53), vec2f(1.0, 1.0), vec2f(1.0, 1.03), vec2f(2.45, 2.36), vec2f(1.0, 1.0));
const WIN_COV = array<f32, 6>(0.18, 0.65, 0.0, 0.14, 0.57, 0.0);

struct VIn {
    @location(0) pos: vec3f,
    @location(1) nrm: vec3f,
    @location(2) uv: vec2f,
};

struct VOut {
    @builtin(position) clip: vec4f,
    @location(0) wpos: vec3f,
    @location(1) wnrm: vec3f,
    @location(2) uv: vec2f,
};

const PI = 3.14159265;

fn hash2(p: vec2f) -> f32 {
    return fract(sin(dot(p, vec2f(127.1, 311.7))) * 43758.5453);
}

fn hash3(p: vec3f) -> f32 {
    return fract(sin(dot(p, vec3f(127.1, 311.7, 74.7))) * 43758.5453);
}

fn vnoise(p: vec2f) -> f32 {
    let i = floor(p);
    let fr = fract(p);
    let u = fr * fr * (3.0 - 2.0 * fr);
    let a = hash2(i);
    let b = hash2(i + vec2f(1.0, 0.0));
    let c = hash2(i + vec2f(0.0, 1.0));
    let d = hash2(i + vec2f(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

fn fbm(p: vec2f) -> f32 {
    var s = 0.0;
    var a = 0.5;
    var q = p;
    for (var k = 0; k < 4; k++) {
        s += a * vnoise(q);
        q = q * 2.03 + vec2f(1.7, 9.2);
        a *= 0.5;
    }
    return s;
}

fn riseK(x: f32) -> f32 {
    if (x <= 0.0) { return 0.0; }
    return 1.0 - exp(-4.2 * x) * cos(5.0 * x);
}

fn neonCol(i: i32) -> vec3f {
    switch (i) {
        case 0: { return vec3f(1.0, 0.45, 0.05); }     // amber
        case 1: { return vec3f(0.02, 0.85, 1.0); }     // cyan
        case 2: { return vec3f(1.0, 0.02, 0.35); }     // magenta
        case 3: { return vec3f(0.12, 0.35, 1.0); }     // blue
        case 4: { return vec3f(0.35, 1.0, 0.08); }     // green
        case 5: { return vec3f(1.0, 0.06, 0.04); }     // red
        case 6: { return vec3f(1.0, 0.78, 0.55); }     // warm white
        default: { return vec3f(0.75, 0.88, 1.0); }    // cool white
    }
}

// low-frequency colour field of the neon light that floods each street
fn neonField(p: vec2f) -> vec3f {
    let q = p / 70.0;
    let i = floor(q);
    let fr = fract(q);
    let u = fr * fr * (3.0 - 2.0 * fr);
    var acc = vec3f(0.0);
    for (var y = 0; y < 2; y++) {
        for (var x = 0; x < 2; x++) {
            let c = i + vec2f(f32(x), f32(y));
            let h = hash2(c);
            var col = vec3f(1.0, 0.1, 0.5);           // magenta
            if (h > 0.35) { col = vec3f(0.05, 0.75, 1.0); }   // cyan
            if (h > 0.62) { col = vec3f(1.0, 0.42, 0.08); }   // amber
            if (h > 0.86) { col = vec3f(0.35, 0.25, 1.0); }   // violet
            let w = select(1.0 - u.x, u.x, x == 1) * select(1.0 - u.y, u.y, y == 1);
            acc += col * w;
        }
    }
    return acc;
}

fn powerK(wp: vec3f, salt: f32) -> f32 {
    let d = distance(wp.xz, f.rise.xy);
    let x = (f.rise.w - d) / 60.0 - salt * 0.8;
    if (x <= 0.0) { return 0.0; }
    if (x < 0.5) {
        return step(0.45, hash2(vec2f(floor(f.cam.w * 24.0), salt * 91.0)));
    }
    return 1.0;
}

@vertex
fn vs_main(v: VIn) -> VOut {
    var out: VOut;
    var wp = o.model * vec4f(v.pos, 1.0);
    let mode = i32(o.params.y + 0.5);
    if (mode == 2 || mode == 8 || mode == 10) {
        let d = distance(wp.xz, f.rise.xy);
        let k = riseK((f.rise.z - d) / 90.0);
        wp = vec4f(wp.x, mix(-4.0, wp.y, k), wp.z, 1.0);
    }
    out.clip = f.viewProj * vec4f(wp.xyz - f.origin.xyz, 1.0);
    out.wpos = wp.xyz;
    out.wnrm = (o.model * vec4f(v.nrm, 0.0)).xyz;
    out.uv = v.uv;
    return out;
}

// ---------------------------------------------------------------- lighting
fn sunDir() -> vec3f {
    return normalize(f.sun.xyz);
}

// physically-flavoured sky: zenith/horizon gradient, warm glow around the sun
fn skyColor(dir: vec3f) -> vec3f {
    let L = sunDir();
    let h = clamp(dir.y, -0.3, 1.0);
    var c = mix(f.skyHor.rgb, f.skyZen.rgb, pow(smoothstep(-0.02, 0.6, h), 0.7));
    let mu = max(dot(dir, L), 0.0);
    c += f.sunCol.rgb * (pow(mu, 8.0) * 0.08 + pow(mu, 64.0) * 0.25) * (1.0 - f.misc.x * 0.8);
    // below the horizon: the haze-filled city floor
    c = mix(c, f.fogC.rgb * 0.8, smoothstep(0.0, -0.15, h));
    return c;
}

fn fogColor(dir: vec3f) -> vec3f {
    return skyColor(dir);
}

fn sunShadow(wp: vec3f, nd: f32) -> f32 {
    if (f.sunCol.w < 0.5) { return 1.0; }
    let s = f.shadowVP * vec4f(wp, 1.0);
    let uv = vec2f(s.x * 0.5 + 0.5, 0.5 - s.y * 0.5);
    if (uv.x <= 0.001 || uv.y <= 0.001 || uv.x >= 0.999 || uv.y >= 0.999 || s.z >= 1.0) { return 1.0; }
    let bias = 0.0006 + 0.0012 * (1.0 - nd);
    let pf = uv * f32(SHADOW_N) - 0.5;
    let i0 = vec2i(floor(pf));
    let fr = fract(pf);
    let z = s.z - bias;
    let a = select(0.0, 1.0, z <= textureLoad(shadowTex, clamp(i0, vec2i(0), vec2i(SHADOW_N - 1)), 0));
    let b = select(0.0, 1.0, z <= textureLoad(shadowTex, clamp(i0 + vec2i(1, 0), vec2i(0), vec2i(SHADOW_N - 1)), 0));
    let c = select(0.0, 1.0, z <= textureLoad(shadowTex, clamp(i0 + vec2i(0, 1), vec2i(0), vec2i(SHADOW_N - 1)), 0));
    let d = select(0.0, 1.0, z <= textureLoad(shadowTex, clamp(i0 + vec2i(1, 1), vec2i(0), vec2i(SHADOW_N - 1)), 0));
    return mix(mix(a, b, fr.x), mix(c, d, fr.x), fr.y);
}

// hard lookup for the fog march
fn sunVis(p: vec3f) -> f32 {
    let s = f.shadowVP * vec4f(p, 1.0);
    let uv = vec2f(s.x * 0.5 + 0.5, 0.5 - s.y * 0.5);
    if (uv.x <= 0.0 || uv.y <= 0.0 || uv.x >= 1.0 || uv.y >= 1.0 || s.z >= 1.0) { return 1.0; }
    let d = textureLoad(shadowTex, vec2i(uv * f32(SHADOW_N)), 0);
    return select(0.0, 1.0, s.z - 0.001 <= d);
}

// player car self-shadowing (A-pillars, roof frame, dash -> sun shafts in the cabin)
fn carShadow(wp: vec3f, nd: f32) -> f32 {
    if (f.carSh.x < 0.5) { return 1.0; }
    let s = f.carVP * vec4f(wp - f.carOrigin.xyz, 1.0);
    let uv = vec2f(s.x * 0.5 + 0.5, 0.5 - s.y * 0.5);
    if (uv.x <= 0.002 || uv.y <= 0.002 || uv.x >= 0.998 || uv.y >= 0.998 || s.z >= 1.0 || s.z <= 0.0) { return 1.0; }
    let bias = (0.006 + 0.02 * (1.0 - nd)) / 39.5;
    let pf = uv * f32(CAR_SN) - 0.5;
    let i0 = vec2i(floor(pf));
    let fr = fract(pf);
    let z = s.z - bias;
    var acc = 0.0;
    var wsum = 0.0;
    for (var y = -1; y <= 2; y++) {
        for (var x = -1; x <= 2; x++) {
            let wx = select(select(1.0, fr.x, x == 2), 1.0 - fr.x, x == -1);
            let wy = select(select(1.0, fr.y, y == 2), 1.0 - fr.y, y == -1);
            let w = wx * wy;
            // the car's map lives to the right of the city map in the same atlas
            let d = textureLoad(shadowTex, clamp(i0 + vec2i(x, y), vec2i(0), vec2i(CAR_SN - 1)) + vec2i(SHADOW_N, 0), 0);
            acc += w * select(0.0, 1.0, z <= d);
            wsum += w;
        }
    }
    return acc / wsum;
}

// world pixels carry their eye distance in the HDR alpha for TAA reprojection
// (0.5..1, log2 encoded); cockpit pixels write 0.25
fn worldAlpha(wp: vec3f) -> f32 {
    let d = distance(f.cam.xyz, wp);
    return 0.5 + 0.5 * clamp(log2(d + 1.0) / 13.0, 0.0, 1.0);
}

fn ign(p: vec2f) -> f32 {
    return fract(52.9829189 * fract(dot(p, vec2f(0.06711056, 0.00583715))));
}

// single-scattering height fog with shadowed sun shafts
fn volFog(ro: vec3f, rd: vec3f, dist: f32, px: vec2f) -> vec4f {
    let H = f.fogC.w;
    let d0 = f.skyHor.w;
    let L = sunDir();
    let mu = dot(rd, L);
    let g = 0.72;
    let hg = (1.0 - g * g) / (4.0 * PI * pow(1.0 + g * g - 2.0 * g * mu, 1.5));
    let phase = min(hg * 0.8, 0.4) + 0.012;
    let sunC = f.sunCol.rgb;
    let amb = f.fogC.rgb;
    let dmax = min(dist, 2600.0);
    let reflp = f.street.z > 0.5;
    if (reflp || f.sunCol.w < 0.5) {
        // analytic (no shafts) for the mirror pass
        let hAvg = max(0.5 * (ro.y + ro.y + rd.y * dmax), 0.0);
        let od = d0 * exp(-hAvg / H) * dmax;
        let T = exp(-od);
        return vec4f((amb + sunC * phase * 0.5) * (1.0 - T), T);
    }
    // samples crowd the near field (quadratic spacing: ~13 m steps up close, long ones far out)
    // so the gaps between towers resolve into shafts instead of averaging into flat haze
    let N = 14;
    let j = fract(ign(px) + f.cam.w * 7.31);
    var T = 1.0;
    var acc = vec3f(0.0);
    for (var k = 0; k < N; k++) {
        let x0 = f32(k) / f32(N);
        let x1 = f32(k + 1) / f32(N);
        let xs = (f32(k) + j) / f32(N);
        let tt = dmax * xs * xs;
        let stp = dmax * (x1 * x1 - x0 * x0);
        let p = ro + rd * tt;
        let dens = d0 * (exp(-max(p.y, 0.0) / H) + 0.04);
        let sig = dens * stp;
        // beam strength (sunCol.w 0.5..1): below 1 the shadowing blends toward a flat average
        let vis = mix(0.75, sunVis(p), clamp((f.sunCol.w - 0.5) * 2.0, 0.0, 1.0));
        let Ls = sunC * vis * phase + amb;
        let a = 1.0 - exp(-sig);
        acc += T * a * Ls;
        T *= exp(-sig);
    }
    // whatever lies beyond the march (far sky) gets the unshadowed remainder
    if (dist > dmax) {
        let rest = d0 * 0.06 * min(dist - dmax, 4000.0);
        let a = 1.0 - exp(-rest);
        acc += T * a * (sunC * phase + amb);
        T *= 1.0 - a;
    }
    return vec4f(acc, T);
}

fn applyFogPx(c: vec3f, wp: vec3f, px: vec2f) -> vec3f {
    let dv = wp - f.cam.xyz;
    let d = length(dv);
    let fg = volFog(f.cam.xyz, dv / max(d, 1e-3), d, px);
    return c * fg.a + fg.rgb;
}

// environment for glossy reflections: sky above, dark hazy city below
fn env(r: vec3f, rough: f32) -> vec3f {
    var c = skyColor(r);
    let below = smoothstep(0.12, -0.05, r.y);
    c = mix(c, f.fogC.rgb * 0.5, below * 0.85);
    // night: a band of lit windows / neon on the horizon
    let az = atan2(r.z, r.x);
    let band = 1.0 - smoothstep(0.0, 0.35 + rough * 0.5, abs(r.y - 0.05));
    // fine grid of lit windows: coarse cells read as camouflage on curved paint
    let cellE = floor(vec2f(az * 220.0, r.y * 140.0));
    let g = step(0.86, hash2(cellE)) * band;
    c += vec3f(1.0, 0.7, 0.4) * g * 0.5 * (1.0 - rough) * f.misc.x;
    return c;
}

fn spotHead(wp: vec3f) -> f32 {
    let fw = normalize(f.carFwd.xy);
    let rel = wp.xz - f.car.xz;
    let along = dot(rel, fw);
    let side = dot(rel, vec2f(-fw.y, fw.x));
    if (along < 1.5) { return 0.0; }
    let spread = abs(side) / (along * 0.36 + 0.9);
    let k = (1.0 - smoothstep(0.4, 1.0, spread)) * (1.0 - smoothstep(18.0, 60.0, along));
    let hk = 1.0 - smoothstep(0.0, 4.0, abs(wp.y - (f.car.y - 0.5)));
    return k * hk * f.car.w;
}

// canyon occlusion: deep streets get less sky
fn canyonAO(wp: vec3f, n: vec3f) -> f32 {
    let hk = smoothstep(-10.0, 180.0, wp.y);
    return mix(0.3, 1.0, hk) * (0.75 + 0.25 * max(n.y, 0.0));
}

fn shade(albedo: vec3f, rough: f32, metal: f32, n: vec3f, wp: vec3f, v: vec3f) -> vec3f {
    return shadeAO(albedo, rough, metal, n, wp, v, 1.0);
}

fn shadeAO(albedo: vec3f, rough: f32, metal: f32, n: vec3f, wp: vec3f, v: vec3f, ao: f32) -> vec3f {
    let night = f.misc.x;
    let cab = f.street.w > 0.5;
    let L = sunDir();
    let ndl = max(dot(n, L), 0.0);
    var sh = 1.0;
    if (ndl > 0.0) {
        sh = sunShadow(wp, ndl);
        if (gCar) { sh *= carShadow(wp, ndl); }
        if (cab) { sh *= f.carSh.y; }
    }
    // sky + bounce ambient
    let up = n.y * 0.5 + 0.5;
    var occ = select(canyonAO(wp, n), 0.6, cab) * ao;
    if (gCar) { occ = (0.85 + 0.15 * max(n.y, 0.0)) * ao; }
    // city walls sit in deep shadow (high-contrast canyons); car + cabin keep their fill
    let ambK = select(0.58, 1.0, gCar || cab);
    let skyAmb = mix(f.fogC.rgb * 0.9, f.skyZen.rgb * 1.1, up) * ambK;
    // warm light bounced off the sunlit faces across the canyon: stronger
    // higher up, on walls rather than floors
    let canyonGI = smoothstep(10.0, 220.0, wp.y) * (1.0 - abs(n.y)) * select(1.0, 0.0, cab);
    let bounce = f.sunCol.rgb * (select(0.035, 0.07, gCar) * (1.0 - up * select(1.0, 0.5, gCar)) + 0.05 * canyonGI) * (1.0 - night);
    var lightIn = (skyAmb + bounce) * occ;
    // street neon spill at night
    let streetC = neonField(wp.xz) * f.street.x * powerK(wp, 0.1);
    let spill = exp(-max(wp.y, 0.0) / 22.0);
    lightIn += streetC * spill * 0.25 * night;
    lightIn += f.sunCol.rgb * ndl * sh;
    if (o.aux.w > 1.5) {
        // cabin fill: sky through the panoramic roof + canyon haze through the windshield
        let fwd = vec3f(f.carFwd.x, 0.0, f.carFwd.y);
        let dayK = 1.0 - night * 0.75;
        lightIn += (f.skyZen.rgb * 1.3 + f.fogC.rgb * 0.9 + f.sunCol.rgb * 0.035) * ao * (0.55 + 0.45 * max(n.y, 0.0)) * dayK;
        lightIn += f.skyHor.rgb * 0.6 * max(dot(n, fwd), 0.0) * ao * dayK;
        // ambient light pools spilling off the strips (dash, doors, console, footwells)
        let lpc = carLocal(wp);
        let dDash = length(vec2f(lpc.y - 0.75, lpc.z + 0.47));
        let dDoor = length(vec2f(abs(lpc.x) - 0.6, lpc.y - 0.71));
        let dCon = length(vec2f(abs(lpc.x) - 0.4, lpc.y - 0.42));
        let dFoot = length(vec2f(lpc.y - 0.28, lpc.z + 0.36));
        let pool = exp(-dDash * 13.0) + exp(-dDoor * 11.0) + exp(-dCon * 13.0) * 0.8 + exp(-dFoot * 4.5) * 0.9;
        let breathe = 0.86 + 0.14 * sin(f.cam.w * 0.9);
        lightIn += f.ambC.rgb * pool * f.cabin.w * 2.2 * breathe * ao;
    }
    // point lights: billboards near the camera
    var spec = vec3f(0.0);
    let cnt = i32(f.ambC.w + 0.5);
    for (var i = 0; i < 16; i++) {
        if (i >= cnt) { break; }
        let lt = f.lights[i];
        let dv = lt.pos.xyz - wp;
        let d = length(dv);
        if (d > lt.pos.w) { continue; }
        let l = dv / max(d, 1e-3);
        let x = d / lt.pos.w;
        let fall = (1.0 - x * x * x * x);
        let att = fall * fall / (1.0 + d * d * 0.02);
        let nl = max(dot(n, l), 0.0);
        let c = lt.col.rgb * lt.col.w * att * select(1.0, 0.3, cab);
        lightIn += c * nl;
        let hv = normalize(l + v);
        spec += c * pow(max(dot(n, hv), 0.0), mix(200.0, 8.0, rough)) * (1.0 - rough) * 2.0;
    }
    let hl = spotHead(wp);
    lightIn += vec3f(1.0, 0.95, 0.85) * hl * 2.2 * max(n.y, 0.2);
    let cd = distance(wp, f.cabin.xyz);
    let cg = f.cabin.w / (1.0 + cd * cd * 9.0);
    lightIn += f.ambC.rgb * cg * max(dot(n, normalize(f.cabin.xyz - wp)), 0.0);

    let diff = albedo * (1.0 - metal) * lightIn;
    let ndv = max(dot(n, v), 0.0);
    let F0 = mix(vec3f(0.04), albedo, metal);
    let fres = F0 + (vec3f(1.0) - F0) * pow(1.0 - ndv, 5.0) * (1.0 - rough * 0.7);
    let r = reflect(-v, n);
    let envc = env(r, rough) * pow(1.0 - rough, 2.0) * select(1.0, 0.5, cab) * occ;
    // sun specular
    let hs = normalize(L + v);
    let sspec = f.sunCol.rgb * sh * pow(max(dot(n, hs), 0.0), mix(400.0, 12.0, rough)) * (1.0 - rough) * ndl * 3.0;
    return diff + envc * fres + (spec + sspec) * mix(vec3f(0.15), vec3f(1.0), fres) * 1.5 * (1.0 - rough * 0.6);
}

fn sanitize(c: vec3f) -> vec3f {
    var x = clamp(c, vec3f(0.0), vec3f(60.0));
    if (!(x.x <= 60.0 && x.y <= 60.0 && x.z <= 60.0)) { x = vec3f(0.0); }
    return x;
}

// ---------------------------------------------------------------- car materials (mode 14)
fn carLocal(wp: vec3f) -> vec3f {
    let R = mat3x3<f32>(o.model[0].xyz, o.model[1].xyz, o.model[2].xyz);
    let s2 = dot(o.model[0].xyz, o.model[0].xyz);
    return (transpose(R) * (wp - o.model[3].xyz)) / s2;
}

fn carDir(l: vec3f) -> vec3f {
    return normalize((o.model * vec4f(l, 0.0)).xyz);
}

// derivative bump (Mikkelsen): perturb n by a scalar height field
fn bumpN(n: vec3f, wp: vec3f, h: f32) -> vec3f {
    let dpx = dpdx(wp);
    let dpy = dpdy(wp);
    let dhx = dpdx(h);
    let dhy = dpdy(h);
    let r1 = cross(dpy, n);
    let r2 = cross(n, dpx);
    let det = dot(dpx, r1);
    let g = sign(det) * (dhx * r1 + dhy * r2);
    return normalize(abs(det) * n - g);
}

fn seamLine(d: f32, w: f32) -> f32 {
    let fw = max(fwidth(d), 1e-5);
    return 1.0 - smoothstep(w, w + fw * 1.5, abs(d));
}

// paint shut-lines, from car-local position
fn paintSeams(lp: vec3f, ln: vec3f) -> f32 {
    let ax = abs(lp.x);
    var s = 0.0;
    let side = step(0.6, abs(ln.x));
    let top = step(0.35, ln.y);
    let doorY = step(0.36, lp.y) * step(lp.y, 0.9);
    s = max(s, seamLine(lp.z + 1.08, 0.0016) * side * doorY);
    s = max(s, seamLine(lp.z - 0.62, 0.0016) * side * doorY);
    s = max(s, seamLine(lp.z + 1.32, 0.0016) * top * step(ax, 0.84) * step(lp.z, -1.0));
    s = max(s, seamLine(ax - 0.78, 0.0016) * top * step(lp.z, -1.32) * step(-2.25, lp.z));
    s = max(s, seamLine(lp.z - 1.98, 0.0016) * top * step(ax, 0.80));
    s = max(s, seamLine(lp.y - 0.53, 0.0016) * step(lp.z, -1.95) * (1.0 - top));
    return s;
}

fn planeUV(lp: vec3f, ln: vec3f) -> vec2f {
    let a = abs(ln);
    if (a.x > a.y && a.x > a.z) { return lp.zy; }
    if (a.y > a.z) { return lp.xz; }
    return lp.xy;
}

// screen-space environment: last frame's image where the mirror ray lands on screen
fn carEnv(wp: vec3f, r: vec3f, rough: f32) -> vec3f {
    var e = env(r, rough);
    if (o.aux.w > 0.5) {
        let tp = wp + r * 70.0;
        let c = f.viewProj * vec4f(tp - f.origin.xyz, 1.0);
        if (c.w > 0.1) {
            let uv = vec2f(c.x / c.w * 0.5 + 0.5, 0.5 - c.y / c.w * 0.5);
            var edge = smoothstep(0.0, 0.12, min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y)));
            // rays bouncing back toward the camera land on the surface's own
            // neighbourhood in screen space (the tail bar flooded the rear panel red)
            let vv = normalize(f.cam.xyz - wp);
            edge *= 1.0 - smoothstep(-0.25, 0.25, dot(r, vv));
            if (edge > 0.0) {
                let sc = textureSampleLevel(refl, samp, clamp(uv, vec2f(0.001), vec2f(0.999)), 0.0).rgb;
                e = mix(e, sc, edge * 0.85);
            }
        }
    }
    return e;
}

struct CarMat { albedo: vec3f, rough: f32, metal: f32, coat: f32, n: vec3f, sheen: f32, ao: f32 };

fn carMaterial(i: VOut, nIn: vec3f, v: vec3f) -> CarMat {
    var m: CarMat;
    let id = i32(o.fx.w + 0.5);
    let lp = carLocal(i.wpos);
    let ln = normalize((transpose(mat3x3<f32>(o.model[0].xyz, o.model[1].xyz, o.model[2].xyz)) * nIn));
    let flag = i32(i.uv.y + 0.5);
    let puv = planeUV(lp, ln);
    m.albedo = o.base.rgb;
    m.rough = o.base.w;
    m.metal = o.params.z;
    m.coat = 0.0;
    m.n = nIn;
    m.sheen = 0.0;
    m.ao = clamp(i.uv.x, 0.0, 1.0);
    // height fields evaluated for every material (derivatives need uniform flow)
    let grain = vnoise(puv * 700.0) * 0.6 + vnoise(puv * 1900.0) * 0.4;
    // diamond quilting
    let qd = vec2f(puv.x + puv.y, puv.x - puv.y) * (0.7071 / 0.042);
    let qf = fract(qd);
    let qe = min(min(qf.x, 1.0 - qf.x), min(qf.y, 1.0 - qf.y));
    let pillow = sqrt(clamp(qe * 2.0, 0.0, 1.0)) * 0.0016;
    let fwq = max(fwidth(qe), 1e-4);
    // perforation: fade holes to their average tone once they shrink below a pixel
    let pv = puv * 330.0;
    let fwp = max(fwidth(pv.x), fwidth(pv.y));
    let perfK = 1.0 - smoothstep(0.25, 0.7, fwp);
    let isQuilt = select(0.0, 1.0, flag == 1 && id == 9);
    let knurl = abs(fract((lp.x * 0.7 + lp.z) * 600.0) - 0.5) + abs(fract((lp.x * 0.7 - lp.z) * 600.0) - 0.5);
    let isKnurl = select(0.0, 1.0, flag == 5);
    var h = 0.0;
    if (id == 6 || id == 9) { h = grain * 0.00025 + pillow * isQuilt; }
    if (id == 7) { h = grain * 0.00008; }
    if (id == 3) { h = knurl * 0.0003 * isKnurl; }
    let hb = h;
    m.n = bumpN(nIn, i.wpos, hb);
    if (id == 0) {
        // clearcoat metallic paint with flake and shut-lines
        let seam = paintSeams(lp, ln);
        m.rough = 0.42;
        m.metal = 0.25;
        m.coat = 1.0 - seam;
        m.albedo = m.albedo * (1.0 - 0.9 * seam);
        m.ao *= 1.0 - 0.5 * seam;
    } else if (id == 1) {
        m.albedo = vec3f(0.012);
        m.rough = 0.3;
        m.coat = 0.9;
    } else if (id == 2) {
        // carbon fibre: 2x2 twill, tow direction drives the sheen
        let cuv = puv * 160.0;
        let cell = floor(cuv);
        let tw = (i32(cell.x) + i32(floor(cell.y / 2.0) * 2.0) + 1000) % 4;
        let alongU = tw < 2;
        let fib = vnoise(select(cuv.yx, cuv, alongU) * vec2f(1.0, 40.0));
        var tl = vec3f(0.0);
        let a = abs(ln);
        if (a.x > a.y && a.x > a.z) { tl = select(vec3f(0.0, 1.0, 0.0), vec3f(0.0, 0.0, 1.0), alongU); }
        else if (a.y > a.z) { tl = select(vec3f(0.0, 0.0, 1.0), vec3f(1.0, 0.0, 0.0), alongU); }
        else { tl = select(vec3f(0.0, 1.0, 0.0), vec3f(1.0, 0.0, 0.0), alongU); }
        let tw3 = carDir(tl);
        let hv = normalize(sunDir() + v);
        let aniso = 0.35 + 0.65 * (1.0 - abs(dot(tw3, hv)));
        m.albedo = vec3f(0.018, 0.019, 0.021) * (0.6 + 0.9 * aniso) * (0.85 + 0.3 * fib);
        m.rough = 0.38;
        m.metal = 0.2;
        m.coat = 1.0;
    } else if (id == 3) {
        // brushed aluminium (streaks run along local x)
        let st = hash2(vec2f(floor(lp.y * 3500.0), floor(lp.z * 60.0))) * 0.6 + vnoise(vec2f(lp.x * 8.0, lp.y * 2500.0)) * 0.4;
        m.albedo = vec3f(0.62, 0.62, 0.64) * (0.88 + 0.2 * st) * (1.0 - 0.5 * isKnurl * knurl);
        m.rough = 0.2 + 0.14 * st;
        m.metal = 1.0;
    } else if (id == 4) {
        m.albedo = vec3f(0.004, 0.005, 0.006);
        m.rough = 0.05;
        m.coat = 1.0;
    } else if (id == 6 || id == 9) {
        // leather: grain, quilting with contrast stitching
        m.rough = 0.48 + 0.18 * grain;
        m.albedo = m.albedo * (0.85 + 0.3 * grain);
        if (flag == 1 && id == 9) {
            // diamond quilting: soft grooves, fine tone-on-tone stitching, AA'd
            let fw = fwq;
            let groove = 1.0 - smoothstep(0.0, 0.05 + fw, qe);
            let line = 1.0 - smoothstep(0.012, 0.012 + fw * 1.5, abs(qe - 0.1));
            let dash = smoothstep(0.35, 0.45, fract((qd.x + qd.y) * 7.0)) * (1.0 - smoothstep(0.85, 0.95, fract((qd.x + qd.y) * 7.0)));
            let st = line * dash * (1.0 - smoothstep(0.15, 0.6, fw * 10.0));
            m.albedo = mix(m.albedo * (1.0 - 0.45 * groove), m.albedo * 1.6 + vec3f(0.03), st * 0.6);
            m.ao *= 1.0 - 0.35 * groove;
        }
        if (flag == 2) {
            let hp = fract(pv) - 0.5;
            let hole = 1.0 - smoothstep(0.16, 0.24, length(hp));
            m.albedo *= mix(0.88, 1.0 - 0.8 * hole, perfK);
        }
        m.sheen = 0.1;
    } else if (id == 7) {
        // suede / alcantara: matte, velvet rim
        m.albedo = m.albedo * (0.85 + 0.3 * grain);
        m.rough = 0.92;
        m.sheen = 0.6;
        if (flag == 2) {
            let hp = fract(pv) - 0.5;
            m.albedo *= mix(0.9, 1.0 - 0.75 * (1.0 - smoothstep(0.16, 0.24, length(hp))), perfK);
        }
    } else if (id == 8) {
        m.albedo = m.albedo * (0.92 + 0.16 * grain);
        m.rough = 0.66;
    } else if (id == 10) {
        // grilles: vent slats / speaker mesh
        m.albedo = vec3f(0.035);
        m.rough = 0.4;
        m.metal = 0.7;
        if (flag == 3) {
            let sl = fract(lp.y * 160.0);
            let gap = 1.0 - smoothstep(0.3, 0.42, abs(sl - 0.5));
            m.albedo *= 1.0 - 0.9 * gap;
            m.ao *= 1.0 - 0.8 * gap;
        }
        if (flag == 4) {
            let g = vec2f(puv.x + puv.y * 0.5, puv.y * 0.866) * 260.0;
            let hp = fract(g) - 0.5;
            let hole = 1.0 - smoothstep(0.18, 0.28, length(hp));
            m.albedo *= 1.0 - 0.9 * hole;
            m.ao *= 1.0 - 0.6 * hole;
        }
    } else if (id == 11) {
        m.albedo = m.albedo * (0.75 + 0.5 * grain);
        m.rough = 1.0;
        m.sheen = 0.3;
    }
    return m;
}

// ---------------------------------------------------------------- materials
@fragment
fn fs_main(i: VOut, @builtin(front_facing) ff: bool) -> @location(0) vec4f {
    // reflection pass: clip everything below the street plane
    if (f.street.z > 0.5 && i.wpos.y < -0.02) { discard; }
    var n = normalize(i.wnrm);
    if (!ff) { n = -n; }
    let v = normalize(f.cam.xyz - i.wpos);
    let mode = i32(o.params.y + 0.5);
    let night = f.misc.x;
    let t = f.cam.w;
    var albedo = o.base.rgb;
    var rough = o.base.w;
    var metal = o.params.z;
    var emis = vec3f(0.0);
    var fogged = true;
    var col: vec3f;

    // derivatives for the facade atlas, taken in uniform control flow
    let duvx = dpdx(i.uv);
    let duvy = dpdy(i.uv);
    let dpx = dpdx(i.wpos);
    let dpy = dpdy(i.wpos);
    if (o.fx.z > 0.0) {
        let dz = hash2(floor(i.clip.xy * 0.5));
        if (dz < o.fx.z) { discard; }
    }

    if (mode == 2) {
        // ------------------------------------------------ textured tower-block facades
        let layerF = floor(i.uv.x / 10000.0);
        var ao = 1.0;
        if (layerF < 0.0) {
            albedo = vec3f(0.02);
            rough = 0.9;
        } else {
            let li = i32(clamp(layerF, 0.0, 5.0));
            var tuv: vec2f;
            var sc: vec2f;
            if (li == 5) {
                sc = vec2f(1.0 / TILE_U[5]);
                tuv = vec2f(i.uv.x - 55000.0, i.uv.y) * sc;
            } else {
                sc = vec2f(1.0 / TILE_U[li], -1.0 / TILE_V[li]);
                tuv = vec2f(i.uv.x - layerF * 10000.0, i.uv.y) * sc;
            }
            let gx = duvx * sc;
            let gy = duvy * sc;
            let ta = textureSampleGrad(albA, samp, tuv, li, gx, gy);
            let tn = textureSampleGrad(nrmA, samp, tuv, li, gx, gy);
            albedo = pow(ta.rgb, vec3f(2.2)) * mix(vec3f(0.98, 0.9, 0.78), vec3f(1.05), f.misc.x);
            // detail mapping: when the photo is magnified (close walls), procedural grit keeps it crisp
            let magK = 1.0 - smoothstep(0.5, 1.6, max(length(gx), length(gy)) * 1024.0);
            if (magK > 0.0) {
                let grit = (vnoise(i.uv * 23.0) - 0.5) * 0.55 + (vnoise(i.uv * 71.0 + 3.1) - 0.5) * 0.35;
                albedo *= 1.0 + grit * magK;
            }
            ao = tn.b;
            rough = 0.82;
            if (li != 5 && abs(n.y) < 0.5) {
                let T = normalize(cross(vec3f(0.0, 1.0, 0.0), n));
                let nt = vec2f(tn.r * 2.0 - 1.0, tn.g * 2.0 - 1.0);
                n = normalize(n + T * nt.x * 1.2 + vec3f(0.0, 1.0, 0.0) * nt.y * 1.2);
                // windows from the window map (exact texel, mip 0): stable per-window lights,
                // rooms behind the glass (interior mapping), statistical glow when far away
                let ng = normalize(i.wnrm) * select(-1.0, 1.0, ff);
                let lum = dot(ta.rgb, vec3f(0.3, 0.59, 0.11));
                // the photo's dark glass stays glossy everywhere (sky-reflection bands by day)
                let glassP = smoothstep(0.2, 0.08, lum);
                rough = mix(0.82, 0.12, glassP);
                metal = glassP * 0.15;
                let wtx = vec2i(clamp(fract(tuv) * 1024.0, vec2f(0.0), vec2f(1023.0)));
                // window maps ride in the normal array's extra layers (6 + layer), mip 0
                let wt = textureLoad(nrmA, wtx, li + 6, 0);
                let wcode = u32(wt.b * 255.0 + 0.5);
                let isWin = wcode >= 2u;
                let glassB = select(0.0, 1.0, isWin && (wcode & 1u) == 1u);
                // window width on screen (px): rooms from ~8 px, the filtered lit mask below that
                let fpx = max(length(gx), length(gy)) * 1024.0;
                let winPx = WIN_SZ[li].x / TILE_U[li] * 1024.0 / max(fpx, 1e-3);
                let nearK = smoothstep(5.0, 9.0, winPx);
                let pk = powerK(i.wpos, 0.2);
                // lit-window masks (layers 12..17): 3 random assignments, picked per tile
                let tileId = floor(tuv);
                let var_ = u32(hash2(tileId + vec2f(layerF * 7.0, 3.0)) * 2.999);
                let selv = vec3f(select(0.0, 1.0, var_ == 0u), select(0.0, 1.0, var_ == 1u), select(0.0, 1.0, var_ == 2u));
                if (nearK > 0.0 && glassB > 0.5) {
                    let rid = hash3(vec3f(f32(wcode >> 1u), tileId.x + layerF * 31.0, tileId.y));
                    let wsz = WIN_SZ[li];
                    // facade tangent along +u, from the screen derivatives (uniform flow above)
                    let det = duvx.x * duvy.y - duvy.x * duvx.y;
                    var Tu = (dpx * duvy.y - dpy * duvx.y) / select(det, 1e-6, abs(det) < 1e-9);
                    Tu = normalize(Tu - ng * dot(Tu, ng) + vec3f(1e-6, 0.0, 0.0));
                    let rd = normalize(i.wpos - f.cam.xyz);
                    let d = vec3f(dot(rd, Tu), rd.y, max(dot(rd, -ng), 0.02));
                    let rw = wsz.x * 1.3 + 0.5;
                    let rh = max(wsz.y * 1.25, 2.7);
                    let rdp = 3.0 + fract(rid * 5.3) * 3.0;
                    let yb = -wsz.y * 0.5 - (rh - wsz.y) * 0.35;
                    let p0 = vec3f((wt.r - 0.5) * wsz.x, (0.5 - wt.g) * wsz.y, 0.0);
                    let tx = (select(-rw * 0.5, rw * 0.5, d.x > 0.0) - p0.x) / select(d.x, 1e-5, abs(d.x) < 1e-5);
                    let ty = (select(yb, yb + rh, d.y > 0.0) - p0.y) / select(d.y, 1e-5, abs(d.y) < 1e-5);
                    let tz = (rdp - p0.z) / d.z;
                    let th = min(min(abs(tx), abs(ty)), tz);
                    let hp = p0 + d * th;
                    // palette per room
                    let pr = fract(rid * 3.7);
                    var wallC = vec3f(0.55, 0.46, 0.36);
                    if (pr > 0.3) { wallC = vec3f(0.38, 0.42, 0.48); }
                    if (pr > 0.55) { wallC = vec3f(0.42, 0.46, 0.4); }
                    if (pr > 0.8) { wallC = vec3f(0.62, 0.56, 0.47); }
                    var sc_ = wallC;
                    var shadeK = 1.0;
                    if (th == tz) {
                        // back wall: a picture / shelf
                        let pic = step(abs(hp.x + rw * (fract(rid * 9.1) - 0.5) * 0.4), 0.35) * step(abs(hp.y - (yb + 1.6)), 0.25);
                        sc_ = mix(wallC, vec3f(0.15, 0.2, 0.3) + 0.4 * vec3f(fract(rid * 11.0), fract(rid * 17.0), fract(rid * 23.0)), pic);
                    } else if (th == abs(ty)) {
                        if (d.y < 0.0) {
                            sc_ = select(vec3f(0.22, 0.15, 0.1), vec3f(0.18, 0.18, 0.2), fract(rid * 13.0) > 0.5);
                            shadeK = 0.7;
                        } else {
                            sc_ = wallC * 1.15 + 0.1;
                        }
                    } else {
                        sc_ = wallC * 0.82;
                    }
                    // furniture block against the back wall (sofa / desk)
                    let bx = rw * (0.18 + 0.15 * fract(rid * 7.0));
                    let bmin = vec3f(-bx, yb, rdp - 0.9);
                    let bmax = vec3f(bx, yb + 0.55 + 0.4 * fract(rid * 19.0), rdp);
                    let inv = 1.0 / select(d, vec3f(1e-5), abs(d) < vec3f(1e-5));
                    let t0 = (bmin - p0) * inv;
                    let t1 = (bmax - p0) * inv;
                    let tn = max(max(min(t0.x, t1.x), min(t0.y, t1.y)), min(t0.z, t1.z));
                    let tf = min(min(max(t0.x, t1.x), max(t0.y, t1.y)), max(t0.z, t1.z));
                    if (tn < tf && tn > 0.0 && tn < th) {
                        sc_ = vec3f(0.09, 0.08, 0.08) + 0.08 * fract(rid * 29.0);
                        shadeK = 0.8;
                    }
                    let hz = p0 + d * min(th, select(th, tn, tn < tf && tn > 0.0));
                    // by day ~45% of the night-lit rooms stay on (at full warmth), the rest switch on at dusk
                    let lit = dot(textureLoad(nrmA, wtx, li + 12, 0).rgb, selv) * pk * mix(step(fract(rid * 17.3), 0.45), 1.0, night);
                    var lc = vec3f(1.0, 0.72, 0.45);
                    if (fract(rid * 7.7) > 0.6) { lc = vec3f(1.0, 0.88, 0.72); }
                    if (fract(rid * 7.7) > 0.88) { lc = vec3f(0.62, 0.8, 1.0); }
                    // ceiling lamp falloff + a lamp panel, deeper = dimmer
                    let lampD = length(vec2f(hz.x, hz.z - rdp * 0.45));
                    let lampI = 0.45 + 0.85 * exp(-lampD * lampD * 0.35);
                    // corner occlusion on the surface that was hit + falloff toward the back
                    let ex = rw * 0.5 - abs(hp.x);
                    let ey = min(hp.y - yb, yb + rh - hp.y);
                    let ez = rdp - hp.z;
                    var dEdge = min(ex, ey);
                    if (th == abs(ty)) { dEdge = min(ex, ez); }
                    if (th == abs(tx)) { dEdge = min(ey, ez); }
                    let cao = 0.4 + 0.6 * smoothstep(0.0, 0.8, dEdge);
                    let depthK = 1.0 - 0.5 * clamp(hz.z / rdp, 0.0, 1.0);
                    let grain = 0.85 + 0.3 * vnoise(vec2f(hp.x + hp.z, hp.y + hp.z) * 3.0 + rid * 40.0);
                    let roomK = cao * depthK * grain;
                    var inter = sc_ * shadeK * roomK * lc * lampI * lit * mix(0.8, 1.15, night);
                    if (th == abs(ty) && d.y > 0.0) {
                        inter += lc * lit * 3.0 * step(abs(hp.x), 0.45) * step(abs(hp.z - rdp * 0.45), 0.3);
                    }
                    // dark rooms: dim daylight by day, a TV glow in some at night
                    let tv = step(0.9, fract(rid * 41.0)) * night * (0.6 + 0.4 * sin(t * 9.0 + rid * 50.0));
                    inter += sc_ * shadeK * roomK * (1.0 - lit) * (mix(vec3f(0.06, 0.065, 0.075), vec3f(0.004), night) + vec3f(0.1, 0.2, 0.5) * tv);
                    // blinds in some windows (on the glass plane, lit from behind)
                    if (fract(rid * 3.1) < 0.22) {
                        let drop = 0.25 + 0.6 * fract(rid * 6.7);
                        let slat = step(0.35, fract(p0.y * 9.0)) * step(1.0 - drop, wt.g * -1.0 + 1.0);
                        let bl = select(0.0, 1.0, wt.g < drop) * (0.75 + 0.25 * slat);
                        inter = mix(inter, (lc * lit * 0.9 + vec3f(0.05)) * vec3f(0.8, 0.75, 0.68), bl);
                    }
                    let fres = 0.04 + 0.96 * pow(1.0 - max(dot(ng, v), 0.0), 5.0);
                    emis += inter * (1.0 - fres) * nearK;
                    // at night the glass darkens so the rooms read; by day the photo + its reflections stay
                    let gk = nearK * night;
                    albedo = mix(albedo, albedo * 0.35, gk);
                    rough = mix(rough, 0.3, gk);
                }
                if (nearK < 1.0) {
                    // far: the filtered lit-window mask (same windows, averaged by the mips), a little
                    // brighter further out so the skyline keeps glittering at night
                    let em = dot(textureSampleGrad(nrmA, samp, tuv, li + 12, gx, gy).rgb, selv);
                    // by day the sun swamps distant windows; at night the skyline glitters
                    let farB = 1.0 + 0.6 * (1.0 - smoothstep(1.0, 4.0, winPx)) * night;
                    emis += vec3f(1.0, 0.74, 0.48) * em * pk * mix(0.1, 1.15, night) * farB * (1.0 - nearK);
                }
            }
        }
        col = shadeAO(albedo, rough, metal, n, i.wpos, v, ao) + emis;
    } else if (mode == 3 || mode == 4 || mode == 13) {
        // ------------------------------------------------ wet street
        let wet = 0.55 + 0.45 * f.misc.y;
        var puddle = smoothstep(0.5, 0.68, fbm(i.wpos.xz * 0.09)) * wet;
        albedo = vec3f(0.035, 0.036, 0.04);
        if (mode == 4) {
            albedo = vec3f(0.07, 0.07, 0.075);
            let tile = step(0.94, fract(i.wpos.x * 0.5)) + step(0.94, fract(i.wpos.z * 0.5));
            albedo *= 1.0 - 0.4 * clamp(tile, 0.0, 1.0);
            puddle *= 0.6;
        }
        if (mode == 3) {
            let across = abs(i.uv.y);
            let dash = step(0.45, fract(i.uv.x / 10.0));
            let centre = 1.0 - step(0.12, abs(across - 0.2));
            let lane = (1.0 - step(0.09, abs(across - 4.5))) * dash;
            let edge = 1.0 - step(0.09, abs(across - 8.5));
            let paint = max(max(lane, edge), centre) * step(across, 50.0);
            albedo = mix(albedo, mix(vec3f(0.55), vec3f(0.6, 0.38, 0.06), centre), paint);
            puddle *= 1.0 - paint * 0.5;
        }
        if (mode == 13) {
            albedo = vec3f(0.22);
            puddle *= 0.3;
        }
        rough = mix(0.55, 0.03, puddle);
        // rain ripples perturb the reflection
        let cellp = floor(i.wpos.xz * 1.5);
        let fp = fract(i.wpos.xz * 1.5) - 0.5;
        let ph = fract(t * 1.3 + hash2(cellp));
        let ring = sin(clamp(length(fp) - ph * 0.5, -0.1, 0.1) * 60.0) * (1.0 - ph) * f.misc.y;
        let rip = vec2f(fp * ring * 0.012);
        let base = shade(albedo, rough, 0.0, n, i.wpos, v);
        // planar reflection (rendered from the mirrored camera)
        let suv = i.clip.xy / vec2f(f.misc.z, f.misc.w);
        let warp = (fbm(i.wpos.xz * 0.6 + vec2f(t * 0.2, 0.0)) - 0.5) * 0.012 * (1.0 - puddle * 0.6);
        let ruv = suv + rip + vec2f(warp, warp * 0.3);
        // glossy (blurred) away from the puddles, mirror-sharp in them
        let bl = (1.0 - puddle) * 0.012;
        var rc = textureSampleLevel(refl, samp, clamp(ruv, vec2f(0.001), vec2f(0.999)), 0.0).rgb * 0.36;
        rc += textureSampleLevel(refl, samp, clamp(ruv + vec2f(bl, bl * 2.5), vec2f(0.001), vec2f(0.999)), 0.0).rgb * 0.16;
        rc += textureSampleLevel(refl, samp, clamp(ruv + vec2f(-bl, bl * 2.5), vec2f(0.001), vec2f(0.999)), 0.0).rgb * 0.16;
        rc += textureSampleLevel(refl, samp, clamp(ruv + vec2f(bl, -bl * 2.5), vec2f(0.001), vec2f(0.999)), 0.0).rgb * 0.16;
        rc += textureSampleLevel(refl, samp, clamp(ruv + vec2f(-bl, -bl * 2.5), vec2f(0.001), vec2f(0.999)), 0.0).rgb * 0.16;
        let ndv = max(dot(n, v), 0.0);
        let fres = 0.03 + 0.97 * pow(1.0 - ndv, 5.0);
        let strength = mix(0.07 + 0.1 * wet, 0.9, puddle) * mix(fres, 1.0, 0.2 + 0.5 * puddle) * select(1.0, 0.6, mode == 4);
        col = base + rc * strength * select(1.0, 0.0, f.street.z > 0.5);
    } else if (mode == 8) {
        // ------------------------------------------------ neon tubes
        let c = neonCol(i32(i.uv.x + 0.5));
        let pk = powerK(i.wpos, i.uv.y);
        let fl = select(1.0, 0.15, hash2(vec2f(floor(t * 13.0 + i.uv.y * 50.0), i.uv.y * 17.0)) < 0.01);
        let on = pk * fl;
        let core = mix(c, vec3f(1.0), 0.15);
        col = core * on * mix(2.0, 4.0, night) + c * 0.02;
        fogged = true;
    } else if (mode == 10) {
        // ------------------------------------------------ billboard face
        var uv = i.uv;
        let pk = powerK(i.wpos, 0.3);
        let dd = distance(i.wpos.xz, f.rise.xy);
        let bootx = (f.rise.w - dd) / 60.0 - 0.24;
        let g = max(o.fx.x, (1.0 - smoothstep(0.4, 1.4, bootx)) * step(0.0, bootx));
        let row = floor(uv.y * 40.0);
        uv.x += (hash2(vec2f(row, floor(t * 20.0))) - 0.5) * g * 0.08;
        // per-screen seed from its position (each design shares one mesh)
        let seed = hash2(floor(i.wpos.xz / 9.0) + floor(i.wpos.y / 9.0) * 7.0);
        // slow rolling interference band + rare horizontal tear
        let roll = fract(uv.y * 1.3 + t * (0.05 + seed * 0.05) + seed);
        let band = smoothstep(0.0, 0.05, roll) * (1.0 - smoothstep(0.05, 0.16, roll));
        // (no uv displacement: horizontal shifts read as screen tearing)
        let tx = textureSample(tex, samp, uv);
        var c = pow(max(tx.rgb, vec3f(0.0)), vec3f(2.2));
        // LED wall: RGB subpixel stripes + dark pixel gaps, faded out once a pixel is under ~2 screen px (no moire)
        let pxs = i.uv * vec2f(256.0, 128.0) * select(1.0, 0.5, o.aux.w > 0.5);
        let px = fract(pxs);
        let fw = max(fwidth(pxs.x), fwidth(pxs.y));
        let near = 1.0 - smoothstep(0.25, 0.6, fw);
        let gap = smoothstep(0.0, 0.18, min(min(px.x, 1.0 - px.x), min(px.y, 1.0 - px.y)) * 2.0);
        let sp = floor(px.x * 3.0);
        let sub = select(select(vec3f(0.35, 0.35, 1.9), vec3f(0.35, 1.9, 0.35), sp < 1.5), vec3f(1.9, 0.35, 0.35), sp < 0.5);
        c *= mix(vec3f(0.86 + 0.14 * gap), sub * gap, near * 0.85);
        // mismatched LED modules: per-tile brightness/tint drift, the odd dead or flickering tile
        let tile = floor(i.uv * vec2f(12.0, 6.0) * select(vec2f(1.0), vec2f(0.5, 2.0), o.aux.w > 0.5));
        let th = hash2(tile + seed * 31.0);
        c *= (0.84 + 0.3 * th) * vec3f(1.0, 0.95 + 0.08 * hash2(tile + 3.1), 0.93 + 0.1 * hash2(tile + 7.7));
        let dead = step(0.985, th);
        c *= mix(1.0, 0.12 + 0.5 * step(0.5, hash2(vec2f(floor(t * 14.0), th * 50.0))), dead);
        // brightness hum + rare dropouts, raised blacks, band glow
        c *= 1.0 + 0.04 * sin(t * 47.0 + seed * 40.0) - 0.35 * step(0.996, hash2(vec2f(floor(t * 9.0), seed * 13.0)));
        c *= 1.0 + band * 0.35;
        // grime: rain-streaked dust thicker toward the bottom edge + panel edge falloff
        let grime = vnoise(vec2f(i.uv.x * 34.0 + seed * 20.0, i.uv.y * 3.0)) * 0.6 + vnoise(vec2f(i.uv.x * 90.0, i.uv.y * 9.0 + seed)) * 0.4;
        c *= 1.0 - 0.32 * smoothstep(0.35, 0.9, grime) * (0.4 + 0.6 * i.uv.y);
        let e2 = min(min(i.uv.x, 1.0 - i.uv.x), min(i.uv.y, 1.0 - i.uv.y));
        c *= 0.72 + 0.28 * smoothstep(0.0, 0.04, e2);
        c += vec3f(0.006, 0.007, 0.009);
        let noise = hash2(floor(i.uv * vec2f(160.0, 80.0)) + vec2f(floor(t * 30.0)));
        c = mix(c, vec3f(noise) * 0.6, g * 0.7);
        col = c * pk * mix(1.1, 1.9, night) + vec3f(0.01);
        // a little glass sheen over the panel
        let r = reflect(-v, n);
        col += env(r, 0.2) * 0.04;
    } else if (mode == 1) {
        // ------------------------------------------------ cockpit display
        // rotated-grid 4x supersample in screen space: the canvas has no mips,
        // so a single tap aliases text whenever the texture is minified
        let ux = dpdx(i.uv);
        let uy = dpdy(i.uv);
        var lin = vec3f(0.0);
        lin += pow(max(textureSample(tex, samp, i.uv + ux * 0.125 + uy * 0.375).rgb, vec3f(0.0)), vec3f(2.2));
        lin += pow(max(textureSample(tex, samp, i.uv - ux * 0.375 + uy * 0.125).rgb, vec3f(0.0)), vec3f(2.2));
        lin += pow(max(textureSample(tex, samp, i.uv + ux * 0.375 - uy * 0.125).rgb, vec3f(0.0)), vec3f(2.2));
        lin += pow(max(textureSample(tex, samp, i.uv - ux * 0.125 - uy * 0.375).rgb, vec3f(0.0)), vec3f(2.2));
        var c = lin * 0.25 * o.aux.x * 1.6;
        let rv = o.fx.y;
        let edgeK = smoothstep(rv - 0.04, rv, 1.0 - i.uv.y);
        c = mix(c, vec3f(0.002), edgeK);
        c += vec3f(1.0, 0.6, 0.25) * 3.0 * (1.0 - smoothstep(0.0, 0.02, abs((1.0 - i.uv.y) - rv))) * step(rv, 0.999) * step(0.001, rv);
        let r = reflect(-v, n);
        let fres = 0.04 + 0.96 * pow(1.0 - max(dot(n, v), 0.0), 5.0);
        col = c + fogColor(r) * fres * 0.25 + vec3f(o.aux.y);
        fogged = false;
    } else if (mode == 9) {
        // ------------------------------------------------ cabin ambient strip
        let tr = o.fx.y;
        let on = step(i.uv.x, tr);
        let head = (1.0 - smoothstep(0.0, 0.05, abs(i.uv.x - tr))) * step(tr, 0.999);
        col = f.ambC.rgb * on * (0.45 + 2.6 * f.cabin.w) + vec3f(1.0, 0.9, 0.8) * head * 1.5;
        fogged = false;
    } else if (mode == 5) {
        col = o.base.rgb * o.accent.w * o.aux.x;
    } else if (mode == 12) {
        let r = i.uv.x;
        let pulse = 0.85 + 0.15 * sin(t * 18.0 + i.wpos.x * 3.0);
        col = mix(vec3f(1.0, 0.9, 0.8) * 3.0, o.accent.rgb * 2.0, smoothstep(0.0, 0.8, r)) * pulse * o.aux.x;
    } else if (mode == 14) {
        // ------------------------------------------------ hovercar (exterior + cabin)
        gCar = true;
        let m = carMaterial(i, n, v);
        col = shadeAO(m.albedo, m.rough, m.metal, m.n, i.wpos, v, m.ao);
        let ndv = max(dot(n, v), 0.0);
        if (m.sheen > 0.0) {
            col += m.albedo * (f.fogC.rgb + f.sunCol.rgb * 0.05) * pow(1.0 - ndv, 3.0) * m.sheen * m.ao;
        }
        if (m.coat > 0.0) {
            // clear coat: mirror reflection of the city + a hard sun glint
            let r = reflect(-v, n);
            let fc = 0.04 + 0.96 * pow(1.0 - ndv, 5.0);
            let cab = f.street.w > 0.5;
            let ec = carEnv(i.wpos, r, 0.02) * select(1.0, 0.35, cab);
            let L = sunDir();
            let ndl = max(dot(n, L), 0.0);
            var sh = 1.0;
            if (ndl > 0.0) { sh = sunShadow(i.wpos, ndl) * carShadow(i.wpos, ndl); }
            let hs = normalize(L + v);
            let glint = f.sunCol.rgb * sh * pow(max(dot(n, hs), 0.0), 900.0) * 12.0 * ndl;
            // metallic flake sparkle in the sun
            let lp = carLocal(i.wpos);
            let cellF = floor(lp * 1300.0);
            let fl = hash3(cellF);
            let fn2 = normalize(n + (vec3f(hash3(cellF + 1.7), hash3(cellF + 3.1), hash3(cellF + 5.3)) - 0.5) * 0.6);
            let sp = pow(max(dot(fn2, hs), 0.0), 160.0) * step(0.55, fl) * select(0.0, 1.0, i32(o.fx.w + 0.5) == 0);
            col = col * (1.0 - fc * m.coat) + (ec * fc + glint + f.sunCol.rgb * sh * sp * 0.6 * ndl) * m.coat * m.ao;
        }
        fogged = f.street.w < 0.5;
    } else if (mode == 11) {
        // ------------------------------------------------ cockpit interior
        col = shade(albedo, rough, metal, n, i.wpos, v);
        // light from the city through the glass roof (tinted by the street)
        let cityC = neonField(f.car.xz + vec2f(sin(t * 0.3) * 30.0, cos(t * 0.23) * 30.0)) * night * 0.08;
        col += albedo * cityC * max(n.y, 0.0) * 3.0;
        fogged = false;
    } else {
        col = shade(albedo, rough, metal, n, i.wpos, v);
        col = mix(col, o.accent.rgb * 2.0, o.aux.z);
        col += vec3f(o.aux.y);
    }
    if (fogged) {
        col = applyFogPx(col, i.wpos, i.clip.xy);
    }
    let a = select(worldAlpha(i.wpos), 0.25, f.street.w > 0.5);
    return vec4f(sanitize(col), a);
}

// ---------------------------------------------------------------- swarm traffic (instanced)
struct SwIn {
    @location(0) pos: vec3f,
    @location(1) nrm: vec3f,
    @location(2) uv: vec2f,
    @location(3) lane: vec4f,   // xyz lane centre, w speed (m/s)
    @location(4) info: vec4f,   // x axis (0 = along x, 1 = along z), y dir, z lane length, w seed
};

struct SwOut {
    @builtin(position) clip: vec4f,
    @location(0) wpos: vec3f,
    @location(1) wnrm: vec3f,
    @location(2) uv: vec2f,
    @location(3) seed: f32,
};

@vertex
fn vs_swarm(v: SwIn) -> SwOut {
    var out: SwOut;
    let len = v.info.z;
    let seed = v.info.w;
    let s = fract(seed * 7.13 + f.cam.w * v.lane.w / len) * len - len * 0.5;
    let dir = v.info.y;
    var fwd = vec3f(dir, 0.0, 0.0);
    if (v.info.x > 0.5) { fwd = vec3f(0.0, 0.0, dir); }
    let right = vec3f(fwd.z, 0.0, -fwd.x);
    let bob = sin(f.cam.w * 1.7 + seed * 40.0) * 0.35;
    let c = v.lane.xyz + fwd * s + vec3f(0.0, bob, 0.0);
    // rise with the city
    let d = distance(c.xz, f.rise.xy);
    let k = riseK((f.rise.z - d) / 90.0);
    var sp = v.pos * 1.6;
    // light streaks: tagged rear vertices of the light bars trail behind the car
    // distant traffic reads as streams of light: streaks lengthen with distance (up to ~22 m)
    let farK = clamp((distance(c, f.cam.xyz) - 120.0) / 600.0, 0.0, 1.0);
    sp.z -= v.uv.y * clamp(v.lane.w * 0.09, 0.0, 4.0) * (1.0 + farK * mix(1.0, 2.0, f.misc.x));
    let wp = c + right * sp.x + vec3f(0.0, sp.y, 0.0) + fwd * sp.z - vec3f(0.0, select(0.0, 3000.0, k < 0.98), 0.0);
    out.clip = f.viewProj * vec4f(wp - f.origin.xyz, 1.0);
    out.wpos = wp;
    out.wnrm = right * v.nrm.x + vec3f(0.0, v.nrm.y, 0.0) + fwd * v.nrm.z;
    out.uv = v.uv;
    out.seed = seed;
    return out;
}

@fragment
fn fs_swarm(i: SwOut) -> @location(0) vec4f {
    let n = normalize(i.wnrm);
    let v = normalize(f.cam.xyz - i.wpos);
    let code = i32(i.uv.x + 0.5);
    let night = f.misc.x;
    let h = fract(i.seed * 13.7);
    var albedo = vec3f(0.04, 0.04, 0.045);
    if (h > 0.35) { albedo = vec3f(0.18, 0.19, 0.21); }
    if (h > 0.6) { albedo = vec3f(0.62, 0.63, 0.65); }
    if (h > 0.82) { albedo = vec3f(0.38, 0.05, 0.035); }
    if (h > 0.93) { albedo = vec3f(0.05, 0.22, 0.28); }
    var col: vec3f;
    if (code == 1) {
        col = vec3f(1.0, 0.04, 0.03) * mix(5.0, 10.0, night);
    } else if (code == 2) {
        col = vec3f(1.0, 0.94, 0.86) * mix(5.0, 12.0, night);
    } else if (code == 3) {
        col = select(vec3f(0.1, 0.6, 1.0), vec3f(1.0, 0.45, 0.1), h > 0.5) * mix(2.5, 6.0, night);
    }
    if (code >= 1 && code <= 3) {
        // light bars keep their original intensity: the streaks carry the streams, not bloom
    } else if (code == 4) {
        // tinted canopy: dark glass with a sky reflection
        let r = reflect(-v, n);
        col = shade(vec3f(0.015), 0.06, 0.2, n, i.wpos, v) + env(r, 0.1) * (0.04 + 0.5 * pow(1.0 - max(dot(n, v), 0.0), 4.0));
    } else {
        // glossy clearcoat body
        let r = reflect(-v, n);
        let fr = 0.04 + 0.96 * pow(1.0 - max(dot(n, v), 0.0), 5.0);
        col = shade(albedo, 0.28, 0.35, n, i.wpos, v) + env(r, 0.15) * fr * 0.6;
    }
    col = applyFogPx(col, i.wpos, i.clip.xy);
    return vec4f(sanitize(col), worldAlpha(i.wpos));
}

// ---------------------------------------------------------------- depth clear (atlas region)
@vertex
fn vs_clear(@builtin(vertex_index) vi: u32) -> @builtin(position) vec4f {
    let x = f32((vi << 1u) & 2u);
    let y = f32(vi & 2u);
    return vec4f(x * 2.0 - 1.0, 1.0 - y * 2.0, 1.0, 1.0);
}

// ---------------------------------------------------------------- greebles (instanced AC units, balconies, rails)
struct GrIn {
    @location(0) pos: vec3f,
    @location(1) nrm: vec3f,
    @location(2) uv: vec2f,
    @location(3) a: vec4f,      // centre xyz, size x
    @location(4) b: vec4f,      // size y, size z, type, tint
};

@vertex
fn vs_greeble(v: GrIn) -> VOut {
    var out: VOut;
    let size = vec3f(v.a.w, v.b.x, v.b.y);
    var wp = v.a.xyz + v.pos * size;
    let d = distance(v.a.xz, f.rise.xy);
    let k = riseK((f.rise.z - d) / 90.0);
    wp.y = mix(-4.0, wp.y, k);
    out.clip = f.viewProj * vec4f(wp - f.origin.xyz, 1.0);
    // distance cull: small clutter vanishes into the haze; clip the whole box away
    let dc = distance(v.a.xyz, f.cam.xyz);
    let big = max(size.x, max(size.y, size.z));
    let maxd = select(420.0, 170.0, big < 1.6);
    if (dc > maxd) {
        out.clip = vec4f(0.0, 0.0, -2.0, 1.0);
    }
    out.wpos = wp;
    out.wnrm = v.nrm;
    out.uv = vec2f(v.b.z, v.b.w);
    return out;
}

@fragment
fn fs_greeble(i: VOut) -> @location(0) vec4f {
    let n = normalize(i.wnrm);
    let v = normalize(f.cam.xyz - i.wpos);
    let ty = i32(i.uv.x + 0.5);
    let tint = i.uv.y;
    var albedo = mix(vec3f(0.52, 0.5, 0.47), vec3f(0.36, 0.35, 0.34), tint);
    var rough = 0.6;
    var metal = 0.25;
    if (ty == 1) {
        albedo = mix(vec3f(0.34, 0.31, 0.27), vec3f(0.22, 0.21, 0.205), tint) * (0.85 + 0.3 * vnoise(i.wpos.xz * 2.0 + i.wpos.y));
        // weathered panels: seams + vertical rain streaks (reads as built, not boxes)
        let ax = dot(i.wpos.xz, vec2f(1.0 - abs(n.x), 1.0 - abs(n.z)));
        let seam = max(step(0.93, fract(i.wpos.y * 0.62)), step(0.95, fract(ax * 0.45)));
        let streak = vnoise(vec2f(ax * 2.7, i.wpos.y * 0.18));
        albedo *= (1.0 - 0.45 * seam) * (0.62 + 0.45 * streak);
        rough = 0.9;
        metal = 0.0;
    } else if (ty == 2) {
        albedo = vec3f(0.1, 0.1, 0.11);
        rough = 0.45;
        metal = 0.6;
    } else if (ty == 3) {
        // cantilevered room window: dark glass with mullions, often lit
        let mull = step(0.92, fract(dot(i.wpos.xz, vec2f(0.8, 0.8)) + 0.5));
        let litK = step(0.45, tint) * powerK(i.wpos, 0.2);
        var wcol = vec3f(1.0, 0.7, 0.42);
        if (fract(tint * 7.3) > 0.7) { wcol = vec3f(0.62, 0.85, 1.0); }
        let em = wcol * litK * (1.0 - mull) * mix(1.4, 2.2, f.misc.x) * (0.6 + 0.4 * fract(tint * 13.0));
        let gc = shade(vec3f(0.03), 0.15, 0.2, n, i.wpos, v) + em;
        return vec4f(sanitize(applyFogPx(gc, i.wpos, i.clip.xy)), worldAlpha(i.wpos));
    } else {
        // AC unit: fan grille on the outward face
        let g = fract(dot(i.wpos, vec3f(9.0, 9.0, 9.0) * (1.0 - abs(n))));
        albedo *= 0.8 + 0.25 * step(0.5, g);
    }
    let col = shade(albedo, rough, metal, n, i.wpos, v);
    return vec4f(sanitize(applyFogPx(col, i.wpos, i.clip.xy)), worldAlpha(i.wpos));
}

// ---------------------------------------------------------------- light cones (additive, in the haze)
@fragment
fn fs_cone(i: VOut) -> @location(0) vec4f {
    let v = normalize(f.cam.xyz - i.wpos);
    let n = normalize(i.wnrm);
    let edge = pow(abs(dot(n, v)), 1.6);
    let along = clamp(i.uv.y, 0.0, 1.0);
    let fade = pow(1.0 - along, 1.6) * smoothstep(0.0, 0.06, along);
    let col = neonCol(i32(i.uv.x + 0.5));
    let pk = powerK(i.wpos, 0.4);
    let dist = distance(f.cam.xyz, i.wpos);
    let T = exp(-dist * 0.0022);
    let near = smoothstep(1.0, 8.0, dist);
    let k = mix(0.5, 1.4, f.misc.x) * pk;
    return vec4f(col * edge * fade * k * T * near, 0.0);
}

// ---------------------------------------------------------------- depth pre-pass (kills overdraw on the facades)
@fragment
fn fs_depth(i: VOut) -> @location(0) vec4f {
    return vec4f(0.0);
}

// ---------------------------------------------------------------- sky
struct SkyOut { @builtin(position) pos: vec4f, @location(0) ndc: vec2f, };

@vertex
fn vs_sky(@builtin(vertex_index) vi: u32) -> SkyOut {
    var out: SkyOut;
    let x = f32((vi << 1u) & 2u);
    let y = f32(vi & 2u);
    let p = vec2f(x * 2.0 - 1.0, 1.0 - y * 2.0);
    out.pos = vec4f(p, 0.99999, 1.0);
    out.ndc = p;
    return out;
}

@fragment
fn fs_sky(i: SkyOut) -> @location(0) vec4f {
    let a = f.invViewProj * vec4f(i.ndc, 0.0, 1.0);
    let b = f.invViewProj * vec4f(i.ndc, 1.0, 1.0);
    var dir = normalize(b.xyz / b.w - a.xyz / a.w);
    if (f.street.z > 0.5) { dir.y = -dir.y; }
    let night = f.misc.x;
    var c = skyColor(dir);
    let L = sunDir();
    if (dir.y > 0.0) {
        let uv = dir.xz / (dir.y + 0.12) * 0.7 + vec2f(f.cam.w * 0.003, f.cam.w * 0.0015);
        let cl = fbm(uv * 1.1);
        let cover = smoothstep(0.62 - f.skyZen.w * 0.3, 0.95, cl);
        let mu = max(dot(dir, L), 0.0);
        let litC = f.sunCol.rgb * (0.12 + 0.5 * pow(mu, 6.0)) + f.skyZen.rgb * 0.6;
        let under = mix(litC, f.fogC.rgb * 2.0, night);
        c = mix(c, under * (0.6 + 0.4 * cl), cover * (1.0 - smoothstep(0.05, 0.9, dir.y)) * 0.8);
        let st = step(0.9965, hash2(floor(dir.xz / (dir.y + 0.2) * 420.0)));
        c += vec3f(st) * (1.0 - cover) * night * 1.5 * smoothstep(0.15, 0.5, dir.y);
    }
    // sun / moon disc
    let md = dot(dir, L);
    c += f.sunCol.rgb * smoothstep(0.99955, 0.9998, md) * mix(30.0, 4.0, night);
    // haze + god rays toward the sky
    let fg = volFog(f.cam.xyz, dir, 6000.0, i.pos.xy);
    c = c * fg.a + fg.rgb;
    // the bright slit of sky between the towers carries the frame by day
    c *= mix(1.45, 1.0, night);
    return vec4f(c, 1.0);
}

// ---------------------------------------------------------------- steam
// Vents from the city pack (steam_inst): rooftop stacks (kind 0) and street manholes (kind 1).
// Each vent draws ST_P camera-facing puffs on staggered life cycles: rise, grow, drift with the
// wind, fade. Lighting is per puff (sun with forward scattering + shadow map, haze ambient, neon
// at night) and the same volumetric fog as the city. Premultiplied, alpha channel untouched.
const ST_P: u32 = 14u;

struct StIn {
    @location(3) a: vec4f,   // xyz vent mouth, w radius
    @location(4) b: vec4f,   // x seed, y kind, z rate, w unused
};

struct StOut {
    @builtin(position) pos: vec4f,
    @location(0) uv: vec2f,
    @location(1) col: vec3f,
    @location(2) k: f32,
    @location(3) fog: vec4f,
    @location(4) sd: f32,
};

@vertex
fn vs_steam(@builtin(vertex_index) vi: u32, v: StIn) -> StOut {
    var out: StOut;
    let k = f32(vi / 6u);
    let corner = vi % 6u;
    let seed = v.b.x;
    let street = v.b.y > 0.5;
    let life = select(17.0, 9.0, street);
    let t = fract(f.cam.w / life + k / f32(ST_P) + seed * 7.31);
    let r0 = v.a.w;
    let rise = select(48.0, 15.0, street) * (1.0 - pow(1.0 - t, 1.8));
    let wind = vec3f(3.0, 0.0, 1.3) * t * life * select(0.6, 0.22, street);
    let jit = vec3f(hash2(vec2f(k, seed * 91.0)) - 0.5, 0.0, hash2(vec2f(seed * 37.0, k)) - 0.5) * r0 * 1.4;
    var c = v.a.xyz + vec3f(0.0, rise, 0.0) + wind + jit * (0.35 + t);
    // rise with the city (title intro): vents of towers still underground stay hidden
    let d0 = distance(v.a.xz, f.rise.xy);
    let rk = riseK((f.rise.z - d0) / 90.0);
    let size = r0 * (1.0 + t * select(5.5, 4.0, street));
    let cam = f.cam.xyz;
    let toCam = cam - c;
    let dist = length(toCam);
    let fwd = toCam / max(dist, 1e-3);
    let right = normalize(cross(vec3f(0.0, 1.0, 0.0), fwd));
    let up = cross(fwd, right);
    var uv = vec2f(-1.0, -1.0);
    if (corner == 1u) { uv = vec2f(1.0, -1.0); }
    if (corner == 2u || corner == 4u) { uv = vec2f(1.0, 1.0); }
    if (corner == 5u) { uv = vec2f(-1.0, 1.0); }
    let q = c + (right * uv.x + up * uv.y) * size;
    out.pos = f.viewProj * vec4f(q - f.origin.xyz, 1.0);
    let ang = seed * 40.0 + k * 2.3 + t * 1.5;
    let cs = cos(ang);
    let sn = sin(ang);
    out.uv = vec2f(uv.x * cs - uv.y * sn, uv.x * sn + uv.y * cs);
    let a = smoothstep(0.0, 0.12, t) * pow(1.0 - t, 1.6) * select(0.4, 0.6, street);
    let near = smoothstep(size * 0.5, size * 2.2 + 2.0, dist);
    let far = 1.0 - smoothstep(500.0, 1100.0, dist);
    // puffs only a few pixels across read as dots (worst against the night canyon): fade them out
    let angSz = size / max(dist, 1.0);
    let night0 = f.misc.x;
    let szK = smoothstep(mix(0.006, 0.012, night0), mix(0.02, 0.035, night0), angSz);
    // the title's beam softening (sunCol.w 0.5..1) thins the plumes too: one crosses the title shot
    let titleSoft = mix(0.4, 1.0, clamp((f.sunCol.w - 0.5) * 2.0 / 0.999, 0.0, 1.0));
    out.k = a * near * far * szK * mix(1.0, 0.55, night0) * select(titleSoft, 1.0, night0 > 0.5) * select(0.0, 1.0, rk > 0.98) * (1.0 - f.street.z);
    if (out.k < 0.002) {
        out.pos = vec4f(2.0, 2.0, 2.0, 1.0);
    }
    let L = sunDir();
    let mu = dot(-fwd, L);
    let g = 0.6;
    let hg = (1.0 - g * g) / (4.0 * PI * pow(1.0 + g * g - 2.0 * g * mu, 1.5));
    let night = f.misc.x;
    let sunL = f.sunCol.rgb * (0.3 + hg * 1.1) * sunVis(c) * (1.0 - night);
    let amb = f.fogC.rgb * 1.3 + f.skyZen.rgb * 0.25;
    out.col = sunL + amb + neonField(c.xz) * night * 0.7;
    out.fog = volFog(cam, -fwd, dist, vec2f(0.0));
    out.sd = seed * 13.0 + k * 1.7;
    return out;
}

@fragment
fn fs_steam(i: StOut) -> @location(0) vec4f {
    let r = length(i.uv);
    if (r > 1.0) {
        discard;
    }
    let n = fbm(i.uv * 1.6 + vec2f(i.sd, i.sd * 0.7) + vec2f(0.0, -f.cam.w * 0.05));
    let d = smoothstep(1.0, 0.15, r + (n - 0.5) * 0.75);
    let a = clamp(d * i.k, 0.0, 1.0);
    let c = i.col * i.fog.a + i.fog.rgb;
    return vec4f(c * a, a);
}

// ---------------------------------------------------------------- holo blade signs
// Vertical holograms projected out from the facades over the sidewalks (holo_inst in the city pack).
// Content is procedural: scrolling columns of alien glyphs, frame, scanlines, a sweep band,
// glitch and flicker. Additive light, attenuated by the haze in front.
struct HoIn {
    @location(3) a: vec4f,   // xyz centre, w half width (across the street)
    @location(4) b: vec4f,   // x 1 = plane normal along x, y half height, z seed, w palette index
};

struct HoOut {
    @builtin(position) pos: vec4f,
    @location(0) uv: vec2f,
    @location(1) info: vec4f,   // x seed, y palette, z aspect (h / w), w intensity
    @location(2) T: f32,
};

fn holoPal(k: f32) -> vec3f {
    let i = u32(k + 0.5) % 4u;
    if (i == 0u) { return vec3f(1.0, 0.16, 0.55); }
    if (i == 1u) { return vec3f(0.18, 0.85, 1.0); }
    if (i == 2u) { return vec3f(1.0, 0.55, 0.12); }
    return vec3f(0.35, 1.0, 0.55);
}

@vertex
fn vs_holo(@builtin(vertex_index) vi: u32, v: HoIn) -> HoOut {
    var out: HoOut;
    var uv = vec2f(0.0, 0.0);
    if (vi == 1u) { uv = vec2f(1.0, 0.0); }
    if (vi == 2u || vi == 4u) { uv = vec2f(1.0, 1.0); }
    if (vi == 5u) { uv = vec2f(0.0, 1.0); }
    var across = vec3f(1.0, 0.0, 0.0);
    if (v.b.x > 0.5) { across = vec3f(0.0, 0.0, 1.0); }
    let c = v.a.xyz;
    let d0 = distance(c.xz, f.rise.xy);
    let rk = riseK((f.rise.z - d0) / 90.0);
    let p = c + across * (uv.x * 2.0 - 1.0) * v.a.w + vec3f(0.0, (uv.y * 2.0 - 1.0) * v.b.y, 0.0)
        - vec3f(0.0, select(0.0, 3000.0, rk < 0.98), 0.0);
    out.pos = f.viewProj * vec4f(p - f.origin.xyz, 1.0);
    out.uv = uv;
    let seed = v.b.z;
    let t = f.cam.w;
    // flicker: mostly steady, the odd stutter / brown-out
    let fl = hash2(vec2f(floor(t * 14.0), seed * 97.0));
    let flick = select(1.0, 0.25 + 0.5 * fl, fl < 0.07) * (0.88 + 0.12 * sin(t * 31.0 + seed * 50.0));
    let dist = distance(c, f.cam.xyz);
    let fade = (1.0 - smoothstep(700.0, 1200.0, dist)) * smoothstep(3.0, 12.0, dist);
    out.info = vec4f(seed, v.b.w, v.b.y / max(v.a.w, 0.1), flick * fade * mix(1.5, 1.8, f.misc.x));
    let fg = volFog(f.cam.xyz, normalize(c - f.cam.xyz), dist, vec2f(0.0));
    out.T = fg.a;
    if (out.info.w < 0.003) {
        out.pos = vec4f(2.0, 2.0, 2.0, 1.0);
    }
    return out;
}

@fragment
fn fs_holo(i: HoOut) -> @location(0) vec4f {
    let seed = i.info.x;
    let t = f.cam.w;
    var uv = i.uv;
    // glitch: a band of rows slips sideways now and then
    let gl = hash2(vec2f(floor(t * 6.0), seed * 13.0));
    let band = step(abs(fract(uv.y * 3.0 + gl * 5.0) - 0.5), 0.06) * step(0.82, gl);
    uv.x += band * (gl - 0.9) * 0.6;
    let col = holoPal(i.info.y);
    let asp = i.info.z;
    // frame
    let ex = min(uv.x, 1.0 - uv.x);
    let ey = min(uv.y, 1.0 - uv.y) * asp;
    let frame = (1.0 - smoothstep(0.012, 0.03, ex)) + (1.0 - smoothstep(0.012, 0.03, ey));
    // glyph column: 5x7 cells, text scrolls down
    let m = 0.14;
    let gu = (uv.x - m) / (1.0 - 2.0 * m);
    let rows = max(floor(asp * 1.25), 3.0);
    let gv = uv.y * rows + t * (0.35 + seed * 0.4);
    var glyph = 0.0;
    if (gu > 0.0 && gu < 1.0) {
        let cell = floor(gv);
        let fy = fract(gv);
        let lit = step(0.18, hash2(vec2f(cell, seed * 31.0)));
        let px = vec2f(floor(gu * 5.0), floor(fy * 8.0));
        let on = step(0.52, hash2(px + vec2f(cell * 7.0, seed * 61.0))) * step(px.y, 6.5);
        let sub = abs(fract(vec2f(gu * 5.0, fy * 8.0)) - 0.5);
        let dot_ = 1.0 - smoothstep(0.32, 0.46, max(sub.x, sub.y));
        glyph = on * dot_ * lit;
    }
    // scanlines + a sweep band running down the sign
    let scan = 0.72 + 0.28 * sin(uv.y * asp * 90.0 + t * 8.0);
    let sw = fract(uv.y - t * 0.22 + seed);
    let sweep = exp(-pow((sw - 0.5) * 10.0, 2.0));
    // soft projection haze filling the plane, brighter near the facade edge (the projector)
    let haze = 0.06 + 0.1 * smoothstep(0.4, 1.0, uv.x);
    let k = (glyph * 1.0 + frame * 0.9 + haze) * scan + sweep * (0.18 + glyph * 0.5);
    let edge = smoothstep(0.0, 0.02, ex) * smoothstep(0.0, 0.02, min(uv.y, 1.0 - uv.y));
    let c = col * k * edge * i.info.w * 3.2 * i.T;
    return vec4f(c, 0.0);
}

// ---------------------------------------------------------------- rain
struct RainOut { @builtin(position) pos: vec4f, @location(0) k: f32, @location(1) col: vec3f, };

@vertex
fn vs_rain(@builtin(vertex_index) vi: u32) -> RainOut {
    var out: RainOut;
    let fi = f32(vi / 6u);
    let box = vec3f(46.0, 30.0, 46.0);
    let seed = vec3f(hash2(vec2f(fi, 1.3)), hash2(vec2f(fi, 7.1)), hash2(vec2f(fi, 3.7)));
    let fall = 22.0 + seed.y * 8.0;
    var p = seed * box;
    p.y -= f.cam.w * fall;
    // wrap the volume around the camera
    let c = f.cam.xyz;
    p = c + (fract((p - c) / box + 0.5) - 0.5) * box;
    // streak: falling + the car's motion
    let vel = vec3f(f.carFwd.x * -f.carFwd.z, -fall, f.carFwd.y * -f.carFwd.z);
    let len = 0.035 * length(vel);
    let dirv = normalize(vel);
    let toCam = normalize(c - p);
    let side = normalize(cross(dirv, toCam)) * 0.006;
    let corner = vi % 6u;
    var q = p;
    var along = 0.0;
    if (corner == 1u || corner == 2u || corner == 4u) { along = 1.0; }
    var s = -1.0;
    if (corner == 2u || corner == 4u || corner == 5u) { s = 1.0; }
    q = p + dirv * len * along + side * s;
    out.pos = f.viewProj * vec4f(q - f.origin.xyz, 1.0);
    let d = distance(p, c);
    out.k = (1.0 - smoothstep(8.0, 20.0, d)) * smoothstep(1.2, 3.5, d) * f.misc.y * mix(0.25, 1.0, along);
    out.col = neonField(p.xz) * 0.6 + vec3f(0.5, 0.55, 0.6);
    return out;
}

@fragment
fn fs_rain(i: RainOut) -> @location(0) vec4f {
    let c = i.col * i.k * 0.16;
    return vec4f(c, 0.0);
}

// ---------------------------------------------------------------- windshield
// HUD virtual image plane (car space); world.as glassUV uses the same numbers
const HUD_EYE = vec3f(-0.37, 1.13, 0.22);
const HUD_D = 2.5;
const HUD_S = 0.0028;      // metres per HUD artboard pixel on the plane
const HUD_W = 2000.0;
const HUD_H = 1240.0;
const HUD_CX = 600.0;
const HUD_HY = 617.0;
// cluster display frame in car space (tools/make_props.py / cabin.as)
const CL_C = vec3f(-0.37, 0.965, -0.64);
const CL_N = vec3f(0.0, 0.1593, 0.9872);     // RX(-0.16) * +z
const CL_Y = vec3f(0.0, 0.9872, -0.1593);
const CL_W = 0.52;
const CL_H = 0.17;
const CS_C = vec3f(0.035, 0.84, -0.52);

fn windshield(i: VOut, nIn: vec3f, v: vec3f) -> vec4f {
    let night = f.misc.x;
    let n = select(nIn, -nIn, dot(nIn, v) < 0.0);
    let ndv = abs(dot(n, v));
    let fres = 0.04 + 0.96 * pow(1.0 - ndv, 5.0);
    let t = f.cam.w;
    // outside world reflected faintly (sky / haze)
    var c = env(reflect(-v, n), 0.1) * fres * 0.6;
    // the cabin reflected in the glass: the driver display, mirrored, and the
    // centre screen's glow - the tell-tale of a real windshield
    let R = mat3x3<f32>(o.model[0].xyz, o.model[1].xyz, o.model[2].xyz);
    let lp = carLocal(i.wpos);
    let lv = transpose(R) * v;
    let ln = transpose(R) * n;
    let rl = reflect(-lv, ln);
    let den = dot(rl, CL_N);
    if (den < -0.05) {
        let tt = dot(CL_C - lp, CL_N) / den;
        if (tt > 0.0) {
            let hp = lp + rl * tt - CL_C;
            let u = hp.x / CL_W + 0.5;
            let w = 0.5 - dot(hp, CL_Y) / CL_H;
            let inside = step(0.0, u) * step(u, 1.0) * step(0.0, w) * step(w, 1.0);
            let tx = textureSampleLevel(tex, samp, vec2f(u, w), 0.0).rgb;
            let lum = dot(pow(max(tx, vec3f(0.0)), vec3f(2.2)), vec3f(0.3, 0.55, 0.15));
            let soft = inside * smoothstep(0.0, 0.08, u) * smoothstep(1.0, 0.92, u) * smoothstep(0.0, 0.15, w) * smoothstep(1.0, 0.85, w);
            c += mix(vec3f(lum), pow(max(tx, vec3f(0.0)), vec3f(2.2)), 0.6) * soft * (0.012 + 0.06 * fres);
        }
    }
    // centre screen glow and the amber dash strip as soft reflected shapes
    let toCs = normalize(CS_C - lp);
    c += f.ambC.rgb * pow(max(dot(rl, toCs), 0.0), 220.0) * 0.12;
    // rain beads (night) and sunlit dust / wiper arcs on the outer surface
    let duv = i.uv * vec2f(240.0, 120.0);
    let cell = floor(duv + vec2f(0.0, t * 0.05));
    let fp = fract(duv + vec2f(0.0, t * 0.05)) - 0.5;
    let hsh = hash2(cell);
    let r = 0.12 + 0.2 * hash2(cell + vec2f(3.0, 1.0));
    let off = vec2f(hash2(cell + vec2f(9.0, 2.0)) - 0.5, hash2(cell + vec2f(2.0, 7.0)) - 0.5) * 0.4;
    let dd = length(fp - off);
    let drop = step(0.8, hsh) * (1.0 - smoothstep(r * 0.7, r, dd));
    let rim = drop * smoothstep(r * 0.4, r * 0.95, dd);
    let dropC = neonField(f.car.xz + i.uv * 60.0) * 0.4 + vec3f(0.3);
    let wet = f.misc.y * night;
    c += dropC * (rim * 0.22 + drop * 0.04) * wet * (0.3 + 0.7 * night);
    let L = sunDir();
    let sunF = pow(max(dot(-v, L), 0.0), 3.0) * (1.0 - night);
    let wc = i.uv - vec2f(0.5, 1.15);
    let wiper = 0.5 + 0.5 * sin(length(wc) * 160.0 + fbm(i.uv * 6.0) * 3.0);
    let dust = (fbm(i.uv * vec2f(90.0, 50.0)) * 0.7 + 0.3 * wiper) * smoothstep(0.55, 0.9, fbm(i.uv * 7.0 + 3.0));
    c += f.sunCol.rgb * dust * sunF * 0.035;
    // grey-blue shade band across the top of the glass
    let band = smoothstep(0.30, 0.08, i.uv.y);
    let edgeK = smoothstep(0.0, 0.12, i.uv.x) * smoothstep(1.0, 0.88, i.uv.x);
    let a = (0.03 + fres * 0.22 + band * 0.32 + drop * 0.12 * wet) * o.aux.x * edgeK;
    c += vec3f(0.02, 0.03, 0.045) * band * 0.2;
    return vec4f(sanitize(c * o.aux.x * edgeK), a);
}

// ---------------------------------------------------------------- glass (HUD + windshield)
@fragment
fn fs_glass(i: VOut) -> @location(0) vec4f {
    let mode = i32(o.params.y + 0.5);
    let v = normalize(f.cam.xyz - i.wpos);
    let n = normalize(i.wnrm);
    if (mode == 20) {
        // HUD: a virtual image reflected off the laminated windshield. Light only
        // (additive), a faint ghost from the glass' second surface, soft edges,
        // and it dims outside the projector's eyebox when the head turns.
        let rv = o.fx.y;
        let front = i.uv.x * 0.8 + (1.0 - i.uv.y) * 0.2;
        let vis = smoothstep(front - 0.02, front, rv * 1.05);
        let head = (1.0 - smoothstep(0.0, 0.012, abs(front - rv * 1.05))) * step(rv, 0.99) * step(0.01, rv);
        // virtual image on a VISOR: the eye ray through this glass point hits a cylinder of radius
        // HUD_D around the projector eye; arc length -> artboard x, so the HUD bows at its edges
        let oc = carLocal(f.cam.xyz);
        let lp = carLocal(i.wpos);
        let dl = lp - oc;
        let ro = oc - HUD_EYE;
        let qa = max(dl.x * dl.x + dl.z * dl.z, 1e-8);
        let qb = 2.0 * (ro.x * dl.x + ro.z * dl.z);
        let qc = ro.x * ro.x + ro.z * ro.z - HUD_D * HUD_D;
        let tt = (-qb + sqrt(max(qb * qb - 4.0 * qa * qc, 0.0))) / (2.0 * qa);
        let hp = ro + dl * tt;
        let th = atan2(hp.x, -hp.z);
        let hu = vec2f((HUD_CX + HUD_D * th / HUD_S) / HUD_W, (HUD_HY - hp.y / HUD_S) / HUD_H) + vec2f(step(-0.01, hp.z) * 9.0, 0.0);
        let inA = step(0.0, hu.x) * step(hu.x, 1.0) * step(0.0, hu.y) * step(hu.y, 1.0);
        let t0 = textureSample(tex, samp, hu) * inA;
        let tg = textureSample(tex, samp, hu + vec2f(0.0006, -0.0026)) * inA;
        let tb = (textureSample(tex, samp, hu + vec2f(0.0012, 0.0)) + textureSample(tex, samp, hu - vec2f(0.0012, 0.0)) +
                  textureSample(tex, samp, hu + vec2f(0.0, 0.002)) + textureSample(tex, samp, hu - vec2f(0.0, 0.002))) * 0.25 * inA;
        let fwd = normalize((o.model * vec4f(0.0, 0.0, -1.0, 0.0)).xyz);
        let eyebox = smoothstep(0.80, 0.95, dot(-v, fwd));
        let lit = pow(max(t0.rgb, vec3f(0.0)), vec3f(2.2));
        let ghost = pow(max(tg.rgb, vec3f(0.0)), vec3f(2.2)) * 0.18;
        let halo = pow(max(tb.rgb, vec3f(0.0)), vec3f(2.2)) * 0.35;
        let k = o.aux.x * vis * mix(0.25, 1.0, eyebox);
        let c = (lit * 1.7 + ghost + halo) * k + o.accent.rgb * head * 2.0;
        // alpha is min()-blended: lit HUD pixels become cockpit (0.25) for TAA
        return vec4f(c, select(1.0, 0.25, max(c.r, max(c.g, c.b)) > 0.004));
    }
    if (mode == 23) {
        // title holo: the live "Title FUI" artboard wrapped on a curved drum / gyro rings.
        // fx.x brightness (flicker + press flash), fx.y build reveal, fx.z 0 drum / 1 ring
        let ux = dpdx(i.uv);
        let uy = dpdy(i.uv);
        var lin = vec3f(0.0);
        lin += pow(max(textureSample(tex, samp, i.uv + ux * 0.125 + uy * 0.375).rgb, vec3f(0.0)), vec3f(2.2));
        lin += pow(max(textureSample(tex, samp, i.uv - ux * 0.375 + uy * 0.125).rgb, vec3f(0.0)), vec3f(2.2));
        lin += pow(max(textureSample(tex, samp, i.uv + ux * 0.375 - uy * 0.125).rgb, vec3f(0.0)), vec3f(2.2));
        lin += pow(max(textureSample(tex, samp, i.uv - ux * 0.125 - uy * 0.375).rgb, vec3f(0.0)), vec3f(2.2));
        lin *= 0.25;
        let ring = o.fx.z > 0.5;
        let rv = o.fx.y;
        // drum unrolls from the centre outward; rings sweep round
        let du = select(abs(i.uv.x - 0.5) * 2.0, i.uv.x, ring);
        let m = 1.0 - smoothstep(rv - 0.025, rv, du);
        let front = (1.0 - smoothstep(0.0, 0.012, abs(du - rv))) * step(rv, 0.995) * step(0.005, rv);
        let fa = dot(n, v);
        let back = select(1.0, 0.22, fa < 0.0);
        let tt = f.cam.w;
        let scanl = 0.86 + 0.14 * sin(i.uv.y * 640.0 * 3.14159);
        let bandY = fract(i.uv.y * select(2.4, 0.0, ring) - tt * 0.45);
        let band = exp(-pow((bandY - 0.5) * 7.0, 2.0));
        let rim = pow(1.0 - abs(fa), 4.0);
        let cy = vec3f(0.10, 0.85, 1.0);
        var c = lin * 3.0 * scanl * (1.0 + band * 0.35) * m;
        // (no glass-body glow: the band itself must stay invisible, only the UI is light)
        c += cy * front * 2.6;                                    // hot reveal edge
        c *= o.fx.x * back;
        return vec4f(sanitize(c), select(1.0, 0.25, max(c.r, max(c.g, c.b)) > 0.004));
    }
    if (mode == 24) {
        // title visor backing: smoked glass behind the light (multiply-blended).
        // fx.x strength, fx.y reveal (from the centre), fx.z window (|u-.5|*2 <= z),
        // fx.w = v0*512 + v1 (band's texture rows, for the soft top/bottom fade)
        let du = abs(i.uv.x - 0.5) * 2.0;
        let m = 1.0 - smoothstep(o.fx.y - 0.025, o.fx.y, du);
        let v0 = floor(o.fx.w) / 512.0;
        let v1 = fract(o.fx.w);
        let vv = (i.uv.y - v0) / max(v1 - v0, 1e-3);
        let vf = smoothstep(0.0, 0.12, vv) * smoothstep(1.0, 0.88, vv);
        let win = o.fx.z;
        let ef = smoothstep(win, win * 0.94, du);
        let cover = m * clamp(o.fx.x, 0.0, 1.0) * vf * ef;
        return vec4f(vec3f(1.0 - cover), select(1.0, 0.25, cover > 0.01));
    }
    if (mode == 21) {
        return windshield(i, n, v);
    }
    if (mode == 22) {
        // player canopy from outside: dark smoked glass, the cabin shows through
        let nn = select(n, -n, dot(n, v) < 0.0);
        let ndv = max(dot(nn, v), 0.0);
        let fc = 0.04 + 0.96 * pow(1.0 - ndv, 5.0);
        let r = reflect(-v, nn);
        let L = sunDir();
        let hs = normalize(L + v);
        let sh = sunShadow(i.wpos, max(dot(nn, L), 0.0));
        var c = carEnv(i.wpos, r, 0.02) * (0.08 + fc * 0.9);
        c += f.sunCol.rgb * sh * pow(max(dot(nn, hs), 0.0), 1200.0) * 14.0;
        let k = 1.0 - o.fx.z;
        let a = (0.42 + 0.5 * fc) * k;
        let fg = volFog(f.cam.xyz, -v, distance(f.cam.xyz, i.wpos), i.clip.xy);
        return vec4f(sanitize(c * k * fg.a + fg.rgb * a), a);
    }
    // windshield: fresnel tint, travelling sheen, rain beads
    let night = f.misc.x;
    let fres = pow(1.0 - abs(dot(n, v)), 3.0);
    let t = f.cam.w;
    var c = env(reflect(-v, n), 0.1) * (0.03 + fres * 0.3);
    let duv = i.uv * vec2f(240.0, 120.0);
    let cell = floor(duv + vec2f(0.0, t * 0.05));
    let fp = fract(duv + vec2f(0.0, t * 0.05)) - 0.5;
    let hsh = hash2(cell);
    let r = 0.12 + 0.2 * hash2(cell + vec2f(3.0, 1.0));
    let off = vec2f(hash2(cell + vec2f(9.0, 2.0)) - 0.5, hash2(cell + vec2f(2.0, 7.0)) - 0.5) * 0.4;
    let dd = length(fp - off);
    let drop = step(0.8, hsh) * (1.0 - smoothstep(r * 0.7, r, dd));
    let rim = drop * smoothstep(r * 0.4, r * 0.95, dd);
    let dropC = neonField(f.car.xz + i.uv * 60.0) * 0.4 + vec3f(0.3);
    c += dropC * (rim * 0.22 + drop * 0.04) * f.misc.y * (0.3 + 0.7 * night);
    let edgeK = smoothstep(0.0, 0.12, i.uv.x) * smoothstep(1.0, 0.88, i.uv.x);
    let a = (0.03 + fres * 0.18 + drop * 0.12 * f.misc.y) * o.aux.x * edgeK;
    return vec4f(c * o.aux.x * edgeK, a);
}
