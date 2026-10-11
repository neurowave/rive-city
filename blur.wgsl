// blur.wgsl — separable 9-tap gaussian (linear-sampled offsets).

struct B {
    params: vec4f, // xy = texel step in uv (direction * 1/size), z = radius scale
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
fn fs_blur(i: VOut) -> @location(0) vec4f {
    let d = b.params.xy * b.params.z;
    var c = textureSample(tSrc, samp, i.uv) * 0.2270270;
    c += textureSample(tSrc, samp, i.uv + d * 1.3846154) * 0.3162162;
    c += textureSample(tSrc, samp, i.uv - d * 1.3846154) * 0.3162162;
    c += textureSample(tSrc, samp, i.uv + d * 3.2307692) * 0.0702703;
    c += textureSample(tSrc, samp, i.uv - d * 3.2307692) * 0.0702703;
    return vec4f(c.rgb, 1.0);
}
