// final.wgsl — HDR composite: speed (zoom) blur on the world only (alpha
// masks the cockpit), three bloom levels, a little anamorphic streak, ACES
// tonemap, chromatic aberration at the edges, vignette and grain.

struct R {
    params: vec4f,  // x exposure, y time, z ca strength, w grain
    blur: vec4f,    // xy zoom centre (uv), z strength, w title grade (0..1)
    bloom: vec4f,   // x,y,z level gains, w vignette
    grade: vec4f,   // rgb lift tint, w saturation
    wb: vec4f,      // rgb white balance gains, w contrast (0 = off)
    shaft: vec4f,   // rgb sun-shaft gain (0 = off)
};

@group(0) @binding(0) var<uniform> r: R;
@group(0) @binding(1) var tHdr: texture_2d<f32>;
@group(0) @binding(2) var tB1: texture_2d<f32>;
@group(0) @binding(3) var tB2: texture_2d<f32>;
@group(0) @binding(4) var tB3: texture_2d<f32>;
@group(0) @binding(5) var samp: sampler;
@group(0) @binding(6) var tShaft: texture_2d<f32>;

struct VOut { @builtin(position) pos: vec4f, @location(0) uv: vec2f, };

@vertex
fn vs_full(@builtin(vertex_index) vi: u32) -> VOut {
    var o: VOut;
    let x = f32((vi << 1u) & 2u);
    let y = f32(vi & 2u);
    o.pos = vec4f(x * 2.0 - 1.0, 1.0 - y * 2.0, 0.0, 1.0);
    o.uv = vec2f(x, y);
    return o;
}

fn hash2(p: vec2f) -> f32 {
    return fract(sin(dot(p, vec2f(127.1, 311.7))) * 43758.5453);
}

fn aces(x: vec3f) -> vec3f {
    let a = 2.51;
    let b = 0.03;
    let c = 2.43;
    let d = 0.59;
    let e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), vec3f(0.0), vec3f(1.0));
}

@fragment
fn fs_final(i: VOut) -> @location(0) vec4f {
    let uv = i.uv;
    let here = textureSample(tHdr, samp, uv);
    var c = here.rgb;
    let world = step(0.4, here.a);
    // lens fringing only toward the corners (quadratic), never across the frame
    let ca = (uv - 0.5) * length(uv - 0.5) * 2.0 * r.params.z * world;
    c = vec3f(textureSample(tHdr, samp, uv + ca).r, c.g, textureSample(tHdr, samp, uv - ca).b);
    // contrast-adaptive sharpening (CAS-style): undo the TAA / resample softness, clamped to the
    // local min/max so edges never ring or halo
    {
        let ts = 1.0 / vec2f(textureDimensions(tHdr));
        let n0 = textureSampleLevel(tHdr, samp, uv + vec2f(ts.x, 0.0), 0.0).rgb;
        let n1 = textureSampleLevel(tHdr, samp, uv - vec2f(ts.x, 0.0), 0.0).rgb;
        let n2 = textureSampleLevel(tHdr, samp, uv + vec2f(0.0, ts.y), 0.0).rgb;
        let n3 = textureSampleLevel(tHdr, samp, uv - vec2f(0.0, ts.y), 0.0).rgb;
        let mn = min(min(min(n0, n1), min(n2, n3)), here.rgb);
        let mx = max(max(max(n0, n1), max(n2, n3)), here.rgb);
        let avg = (n0 + n1 + n2 + n3) * 0.25;
        // weaker where the neighbourhood is already contrasty (CAS's amount term)
        let amt = 0.55 * (1.0 - smoothstep(0.0, 1.0, max(mx.g - mn.g, 0.0) / max(mx.g, 0.02)) * 0.6);
        let cs = clamp(here.rgb + (here.rgb - avg) * amt, mn, mx);
        c += cs - here.rgb;
    }
    let k = r.blur.z * world;
    if (k > 0.002) {
        let dir = uv - r.blur.xy;
        let len = length(dir);
        var acc = c;
        var wsum = 1.0;
        for (var s = 1; s <= 10; s++) {
            let t = f32(s) / 10.0;
            let q = uv - dir * t * k * smoothstep(0.03, 0.5, len);
            let sq = textureSampleLevel(tHdr, samp, q, 0.0);
            let w = step(0.4, sq.a) * (1.0 - 0.7 * t);
            acc += sq.rgb * w;
            wsum += w;
        }
        c = acc / wsum;
    }
    // title grade: darken the WORLD only (dimmer exposure + bottom gradient under the visor UI);
    // the visor's own pixels are tagged (alpha < 0.4) and stay at full brightness
    let tk = r.blur.w;
    if (tk > 0.001) {
        let dk = (1.0 - 0.22 * tk) * (1.0 - tk * 0.6 * smoothstep(0.42, 1.0, uv.y));
        c *= mix(1.0, dk, world);
    }
    let b1 = textureSample(tB1, samp, uv).rgb;
    let b2 = textureSample(tB2, samp, uv).rgb;
    let b3 = textureSample(tB3, samp, uv).rgb;
    c += b1 * r.bloom.x + b2 * r.bloom.y + b3 * r.bloom.z;
    // sun shafts: light in the air in front of the city (world only: the cabin occludes them);
    // weaker over open sky so the beams read against the towers instead of just brightening the sky
    let skyHere = smoothstep(0.985, 0.998, here.a);
    c += textureSample(tShaft, samp, uv).rgb * r.shaft.rgb * world * (1.0 - 0.85 * skyHere);
    var st = vec3f(0.0);
    for (var s = -6; s <= 6; s++) {
        let w = 1.0 - abs(f32(s)) / 7.0;
        st += textureSample(tB2, samp, uv + vec2f(f32(s) * 0.012, 0.0)).rgb * w;
    }
    c += st * vec3f(0.5, 0.7, 1.0) * 0.012;
    c *= r.params.x * r.wb.rgb;
    c += r.grade.rgb;
    var m = aces(c);
    // filmic S-curve: deeper blacks, brighter highlights (cinematic range)
    m = mix(m, m * m * (3.0 - 2.0 * m), 0.3 + r.wb.w);
    // shadows lean neutral/teal, highlights warm
    let lm = dot(m, vec3f(0.2126, 0.7152, 0.0722));
    m = m * mix(vec3f(0.97, 1.0, 1.02), vec3f(1.04, 1.0, 0.94), smoothstep(0.15, 0.6, lm) * r.wb.w * 2.0);
    let l = dot(m, vec3f(0.2126, 0.7152, 0.0722));
    m = mix(vec3f(l), m, r.grade.w);
    let v = 1.0 - r.bloom.w * pow(length((uv - 0.5) * vec2f(1.0, 0.85)) * 1.3, 2.6);
    m *= v;
    // start screen: a soft black gradient after bloom, darkest at the bottom edge, fully clear from
    // ~72% up the screen so the bright sky bloom stays untouched
    let tg = pow(smoothstep(0.28, 1.0, uv.y), 1.1);
    m *= 1.0 - r.blur.w * 0.75 * tg;
    m = pow(max(m, vec3f(0.0)), vec3f(1.0 / 2.2));
    m += (hash2(uv * 1931.0 + vec2f(r.params.y * 61.0, 0.0)) - 0.5) * r.params.w;
    return vec4f(clamp(m, vec3f(0.0), vec3f(1.0)), 1.0);
}
