// shafts.wgsl — screen-space sun shafts. Runs at quarter resolution: each pixel marches toward
// the sun's screen position and gathers the SKY seen along the way (HDR alpha encodes distance,
// so the sky is a == 1.0), with exponential decay. The bright slits between the towers smear
// into beams; the towers themselves (nearer than the sky) cut the dark gaps.

struct S {
    sun: vec4f,   // xy sun position (uv, may be off-screen), z march length (0..1 of the way), w decay
};

@group(0) @binding(0) var<uniform> s: S;
@group(0) @binding(1) var tHdr: texture_2d<f32>;
@group(0) @binding(2) var samp: sampler;

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

fn ign(p: vec2f) -> f32 {
    return fract(52.9829189 * fract(dot(p, vec2f(0.06711056, 0.00583715))));
}

fn sky(uv: vec2f) -> vec3f {
    if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) {
        return vec3f(0.0);
    }
    let t = textureSampleLevel(tHdr, samp, uv, 0.0);
    // sky only (alpha = encoded distance; the sky writes 1.0, anything within ~6 km is below 0.985)
    let m = smoothstep(0.985, 0.998, t.a);
    return min(t.rgb, vec3f(6.0)) * m;
}

@fragment
fn fs_shafts(i: VOut) -> @location(0) vec4f {
    let N = 48;
    let step = (i.uv - s.sun.xy) * s.sun.z / f32(N);
    // per-pixel start jitter breaks the stepping bands; the result is upsampled and soft anyway
    var p = i.uv - step * ign(i.pos.xy);
    var w = 1.0;
    var acc = vec3f(0.0);
    var wsum = 0.0;
    for (var k = 0; k < N; k++) {
        p -= step;
        acc += sky(p) * w;
        wsum += w;
        w *= s.sun.w;
    }
    return vec4f(acc / max(wsum, 1e-3), 1.0);
}
