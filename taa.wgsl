// taa.wgsl — temporal anti-aliasing for the world layer.
// The main pass is rendered with a per-frame sub-pixel jitter. Each pixel's
// distance from the eye is packed into the HDR alpha (0.5..1 = world, log2
// encoded; < 0.4 = cockpit, which is not jittered and passes straight through).
// We rebuild the camera-relative position, reproject it into last frame with
// the eye delta (camera-relative, so no f32 cancellation), clamp the history to
// the current 3x3 neighbourhood (variance clipping) and blend.

struct T {
    invVP: mat4x4<f32>,   // inverse of the current camera-relative viewProj (unjittered)
    prevVP: mat4x4<f32>,  // previous camera-relative viewProj (unjittered)
    delta: vec4f,         // xyz eye(now) - eye(prev), w history valid
    params: vec4f,        // xy texel size, z current weight, w unused
};

@group(0) @binding(0) var<uniform> t: T;
@group(0) @binding(1) var tCur: texture_2d<f32>;
@group(0) @binding(2) var tHist: texture_2d<f32>;
@group(0) @binding(3) var samp: sampler;

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

fn decodeDist(a: f32) -> f32 {
    let x = clamp((a - 0.5) * 2.0, 0.0, 1.0);
    return exp2(x * 13.0) - 1.0;
}

// tonemapped-space weights keep fireflies from dominating the blend
fn lw(c: vec3f) -> f32 {
    return 1.0 / (1.0 + dot(c, vec3f(0.2126, 0.7152, 0.0722)));
}

@fragment
fn fs_taa(i: VOut) -> @location(0) vec4f {
    let uv = i.uv;
    let cur = textureSampleLevel(tCur, samp, uv, 0.0);
    // neighbourhood statistics (taken for every pixel: uniform control flow)
    let d = t.params.xy;
    var m1 = vec3f(0.0);
    var m2 = vec3f(0.0);
    for (var y = -1; y <= 1; y++) {
        for (var x = -1; x <= 1; x++) {
            let s = textureSampleLevel(tCur, samp, uv + vec2f(f32(x), f32(y)) * d, 0.0).rgb;
            m1 += s;
            m2 += s * s;
        }
    }
    if (cur.a < 0.4 || t.delta.w < 0.5) {
        return cur;
    }
    let ndc = vec2f(uv.x * 2.0 - 1.0, 1.0 - uv.y * 2.0);
    let pa = t.invVP * vec4f(ndc, 0.0, 1.0);
    let pb = t.invVP * vec4f(ndc, 1.0, 1.0);
    let dir = normalize(pb.xyz / pb.w - pa.xyz / pa.w);
    let p = dir * decodeDist(cur.a) + t.delta.xyz;
    let pc = t.prevVP * vec4f(p, 1.0);
    if (pc.w <= 0.01) {
        return cur;
    }
    let puv = vec2f(pc.x / pc.w * 0.5 + 0.5, 0.5 - pc.y / pc.w * 0.5);
    if (puv.x < 0.0 || puv.y < 0.0 || puv.x > 1.0 || puv.y > 1.0) {
        return cur;
    }
    var hist = textureSampleLevel(tHist, samp, puv, 0.0);
    if (hist.a < 0.4) {
        return cur;
    }
    let mu = m1 / 9.0;
    let sig = sqrt(max(m2 / 9.0 - mu * mu, vec3f(0.0)));
    let hc = clamp(hist.rgb, mu - sig * 1.25, mu + sig * 1.25);
    // fast motion -> lean on the current frame
    let motion = length((puv - uv) / d);
    let wc = clamp(t.params.z + motion * 0.02, t.params.z, 0.5);
    let a = wc * lw(cur.rgb);
    let b = (1.0 - wc) * lw(hc);
    let c = (cur.rgb * a + hc * b) / (a + b);
    return vec4f(c, cur.a);
}
