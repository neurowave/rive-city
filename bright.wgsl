// bright.wgsl — bloom down-sampler. First level thresholds the HDR scene
// (soft knee, firefly clamp); later levels are plain box downsamples.

struct B {
    params: vec4f, // xy = source texel size, z = threshold (0 = none), w = knee
};

@group(0) @binding(0) var<uniform> b: B;
@group(0) @binding(1) var tSrc: texture_2d<f32>;
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

@fragment
fn fs_bright(i: VOut) -> @location(0) vec4f {
    let d = b.params.xy;
    var c = vec3f(0.0);
    c += textureSample(tSrc, samp, i.uv + vec2f(-d.x, -d.y)).rgb;
    c += textureSample(tSrc, samp, i.uv + vec2f(d.x, -d.y)).rgb;
    c += textureSample(tSrc, samp, i.uv + vec2f(-d.x, d.y)).rgb;
    c += textureSample(tSrc, samp, i.uv + vec2f(d.x, d.y)).rgb;
    c *= 0.5;
    c += textureSample(tSrc, samp, i.uv + vec2f(-2.0 * d.x, 0.0)).rgb * 0.125;
    c += textureSample(tSrc, samp, i.uv + vec2f(2.0 * d.x, 0.0)).rgb * 0.125;
    c += textureSample(tSrc, samp, i.uv + vec2f(0.0, -2.0 * d.y)).rgb * 0.125;
    c += textureSample(tSrc, samp, i.uv + vec2f(0.0, 2.0 * d.y)).rgb * 0.125;
    c *= 0.5 / 0.75;
    let th = b.params.z;
    if (th > 0.0) {
        let br = max(c.r, max(c.g, c.b));
        let knee = b.params.w;
        var soft = clamp(br - th + knee, 0.0, 2.0 * knee);
        soft = soft * soft / (4.0 * knee + 1e-4);
        let w = max(soft, br - th) / max(br, 1e-4);
        c = c * w;
        c = c / (1.0 + max(c.r, max(c.g, c.b)) * 0.05);
    }
    return vec4f(c, 1.0);
}
