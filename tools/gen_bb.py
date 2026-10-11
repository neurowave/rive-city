# gen_bb.py — billboard artboards (exec'd inside gen.py's namespace).
# Six designs, each a live Rive artboard rendered into a canvas every frame and
# mapped onto many billboards in the city:
#   0 ROCKET SQUADRON (game ad)  1 RIVE (nested animated logo)
#   2 KINETIC (energy drink)  3 MERIDIAN LIVE (data-bound: your speed + track)
#   4 SKYLINE ARCADE (interactive: tap counter + burst)  5 HOTEL AURORA (vertical neon)
#
# Layout rule: every element is PLACED by flex layout (a fill/fill stack root with
# layers, rows and columns). Motion lives on Nodes inside fixed-size "anchor"
# boxes, so animation never fights the layout and nothing is hand-positioned
# against the artboard edge.
import random as _rnd


# ---------------------------------------------------------------- photographic plates on deformable meshes
# AI-generated, textless plates (art/*.jpg). Each sits on a
# triangulated grid Mesh inside its Image; motion is keyed per MeshVertex
# (x/y = keys 24/25), so a fish swims with a travelling body wave, a face sways
# and breathes, a jellyfish pulses -- real Rive mesh deformation, under vector
# motion graphics and type.
IMG = {n: nid() for n in ("face", "koi", "can", "ship", "jelly")}
IMG_SIZE = {"face": (576, 1024), "koi": (1024, 576), "can": (576, 1024), "ship": (1024, 576), "jelly": (576, 1024)}


def _varuint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def mesh_image(name, key, nx, ny, x=0, y=0, scale=1.0, blend=None, opacity=None):
    """Image + grid Mesh. Returns (image element, grid[j][i] of (vertex, x0, y0))."""
    import base64 as _b64
    iw, ih = IMG_SIZE[key]
    grid, verts = [], []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            vx, vy = -iw / 2 + iw * i / nx, -ih / 2 + ih * j / ny
            v = E("MeshVertex", x=round(vx, 2), y=round(vy, 2), u=round(i / nx, 5), v=round(j / ny, 5), name=f"V{j}_{i}", id=nid())
            row.append((v, vx, vy))
            verts.append(v)
        grid.append(row)
    tri = []
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            b, c = a + 1, a + nx + 1
            tri += [a, b, c + 1, a, c + 1, c]
    tib = _b64.b64encode(b"".join(_varuint(t) for t in tri)).decode()
    mesh = E("Mesh", *verts, triangleIndexBytes=tib, name="Mesh", id=nid())
    img = E("Image", mesh, assetId=IMG[key], name=name, id=nid(), x=x, y=y, scaleX=scale, scaleY=scale,
            blendModeValue=blend, opacity=opacity)
    return img, grid


def mesh_anim(anim, grid, frames, fn):
    """key every vertex at `frames` with (x0 + dx, y0 + dy) from fn(i, j, x0, y0, f), linear"""
    for j, row in enumerate(grid):
        for i, (v, x0, y0) in enumerate(row):
            ks_x, ks_y, mx, my = [], [], 0.0, 0.0
            for f in frames:
                dx, dy = fn(i, j, x0, y0, f)
                ks_x.append((f, round(x0 + dx, 2), "linear"))
                ks_y.append((f, round(y0 + dy, 2), "linear"))
                mx, my = max(mx, abs(dx)), max(my, abs(dy))
            if mx > 0.05:
                anim.key(v.id, 24, ks_x)
            if my > 0.05:
                anim.key(v.id, 25, ks_y)


def scanlines(W, H, step=6, alpha=22):
    return node("Scanlines", *[shape(f"S{k}", rect(W, 1.5, x=W / 2, y=k * step), solid(argb("#000000", alpha))) for k in range(int(H / step) + 1)])


def brackets(W, H, col, L=40, th=3, inset=18):
    pts = []
    for sx, sy in ((0, 0), (1, 0), (1, 1), (0, 1)):
        x0 = inset if sx == 0 else W - inset
        y0 = inset if sy == 0 else H - inset
        dx = L if sx == 0 else -L
        dy = L if sy == 0 else -L
        pts.append(poly([(x0 + dx, y0), (x0, y0), (x0, y0 + dy)]))
    return shape("Brackets", *pts, stroke(argb(col), th, "butt"))


def bb_artboard(name, W, H, x):
    s, sid = style(layoutWidthScaleType="fixed", layoutHeightScaleType="fixed")
    ab = E("Artboard", s, name=name, id=nid(), width=W, height=H, isComponent=True, styleId=sid,
           viewModelId=VM_ID, viewModelInstanceId=VMI_ID, x=x, y=2600, clip=True)
    return ab


def stack(name, *kids, **kw):
    ex = dict(kw.pop("extra", {}) or {})
    ex["layoutTypeValue"] = "stack"
    return box(name, *kids, ws=kw.pop("ws", "fill"), hs=kw.pop("hs", "fill"), extra=ex, **kw)


def anchor(name, *nodes, w, h):
    """fixed-size layout box; its nodes draw in local 0..w x 0..h space"""
    return box(name, node(name + " Art", *nodes), w=w, h=h, ws="fixed", hs="fixed", clip=False)


def ot(name, s, size, color=WHITE, **kw):
    return orb(name, s, size, color, dec=False, **kw)


def mt(name, s, size, color=MUTED, **kw):
    return mono(name, s, size, color, dec=False, **kw)


def it(name, s, size, color=WHITE, weight=600, **kw):
    return inter(name, s, size, color, weight=weight, dec=False, **kw)


def NT(name, s, size, color, font, x, y, ox=0, oy=0.5, weight=None, ls=None, bindname=None, align="left"):
    """free text for use inside anchors (animated)"""
    return text(name, s, size, color, font, weight, bindname=bindname, lp=False, x=x, y=y, ox=ox, oy=oy, align=align,
                ls=ls, dec=False)


def chevron(name, col, h=14, th=3.0):
    w = h * 0.55
    return anchor(name, shape("Chev", poly([(w * 0.2, h * 0.15), (w * 0.85, h / 2), (w * 0.2, h * 0.85)]), stroke(argb(col), th)),
                  w=w, h=h)


def hit_layer(name="Hit"):
    return layer(name, fill=argb("#000000", 1), bid=nid())


# ---------------------------------------------------------------- 0 ROCKET SQUADRON
def bb_rocket():
    W, H = 1024, 512
    ab = bb_artboard("BB Rocket", W, H, 0)
    rr = _rnd.Random(11)
    far = node("Stars Far", *[shape(f"F{k}", ellipse(2, 2), solid(argb(WHITE, rr.randint(60, 150))), x=rr.uniform(0, 2 * W),
                                    y=rr.uniform(0, H)) for k in range(80)])
    near = node("Stars Near", *[shape(f"N{k}", ellipse(s, s), solid(argb(WHITE, rr.randint(150, 255))), x=rr.uniform(0, 2 * W),
                                      y=rr.uniform(0, H)) for k, s in enumerate([rr.choice([3, 3, 4, 5]) for _ in range(40)])])
    streaks = node("Streaks", *[shape(f"Sk{k}", rect(rr.uniform(60, 220), 2, x=rr.uniform(0, 2 * W), y=rr.uniform(20, H - 20)),
                                      solid(argb("#7FB4FF", rr.randint(60, 140)))) for k in range(22)])
    ring = node("Ring", shape("R", ellipse(1060, 180), stroke(argb(AMBER, 160), 3)), rot=-0.18)
    planet = node("Planet",
                  ring,
                  shape("Rim", ellipse(700, 700), stroke(argb(AMBER), 4)),
                  shape("Body", ellipse(700, 700), rgrad([(argb("#2B3C8C"), 0), (argb("#070A1E"), 1)], -180, -180, 320, 320)),
                  shape("Atmo", ellipse(780, 780), rgrad([(argb("#3084FF", 70), 0.85), (argb("#3084FF", 0), 1)], 0, 0, 390, 390)),
                  x=900, y=720)

    def ship(name, sc, col=AMBER):
        flame = node("Flame", shape("F1", poly([(0, -9), (-80, 0), (0, 9)], True), solid(argb(col))),
                     shape("F2", poly([(0, -5), (-44, 0), (0, 5)], True), solid(argb(WHITE))), x=-54, y=4)
        trail = shape("Trail", rect(420, 3, x=-260, y=4), lgrad([(argb(col, 0), 0), (argb(col, 180), 1)], -470, 0, -50, 0))
        n = node(name, trail, flame,
                 shape("Fin T", poly([(-40, -6), (-60, -34), (-30, -34), (0, -6)], True), solid(argb("#C9CCD2"))),
                 shape("Hull", poly([(-56, -12), (60, -4), (86, 4), (60, 12), (-56, 18), (-62, 4)], True), solid(argb("#F2F2F4"))),
                 shape("Stripe", poly([(-40, 4), (70, 4), (60, 10), (-46, 12)], True), solid(argb(col))),
                 shape("Canopy", poly([(10, -6), (44, -3), (30, 2), (6, 1)], True), solid(argb("#0D1530"))),
                 shape("Fin B", poly([(-36, 14), (-58, 34), (-28, 34), (4, 14)], True), solid(argb("#9DA2AA"))),
                 x=0, y=0, scale=sc)
        return n, flame
    lead, f1 = ship("Lead", 1.5)
    wing1, f2 = ship("Wing L", 0.9, "#19F2FF")
    wing2, f3 = ship("Wing R", 0.9, "#F30058")
    wing1.attrs.update(x="-170", y="-70")
    wing2.attrs.update(x="-190", y="80")
    lasers = node("Lasers", *[shape(f"L{k}", rect(90, 3, x=160 + k * 140, y=4), solid(argb("#FF483C"))) for k in range(3)])
    squad = node("Squadron", lasers, wing2, wing1, lead, x=-400, y=260, scale=0.55)
    # text column (layout placed)
    t1 = NT("T1", "ROCKET", 96, WHITE, F_ORB, 0, 48, weight=900, ls=4)
    t2 = NT("T2", "SQUADRON", 96, WHITE, F_ORB, 0, 146, weight=900, ls=4)
    title = anchor("Title", t1, t2, w=600, h=196)
    pr = node("Prism Bar", *prism_bar(540, 8))
    prism = anchor("Prism", pr, w=540, h=8)
    shine = node("Shine", shape("S", poly([(0, 0), (26, 0), (6, 60), (-20, 60)], True), solid(argb(WHITE, 150))), x=-60, y=0)
    cta_row = box("CTA Row", ot("C", "PLAY FREE", 20, BLACK, ls=2), chevron("Chev", BLACK, 16, 3.5), dir="row", align="center", gap=10,
                  ws="fill", hs="fill")
    cta = stack("CTA", layer("Shine L", anchor("Shine A", shine, w=230, h=56), align="topLeft", clip=True), cta_row,
                w=230, h=56, ws="fixed", hs="fixed", radius=28, fill=argb(AMBER), clip=True)
    col = box("Text", mt("Kick", "SEASON 03  ·  LAUNCH DAY", 20, AMBER, ls=4), title, prism, spacer(1, 4),
              it("Sub", "SQUAD UP OVER MERIDIAN", 19, "#9FB0D8", ls=3), spacer(1, 10), cta,
              gap=12, ws="fill", hs="fill", align="centerLeft", pad=(0, 0, 0, 62))
    # photographic key art on a mesh: the starfighter banks and bobs, nebula stays put
    PX, PS = W / 2 + 270, 1.3
    plate, pgrid = mesh_image("Plate", "ship", 12, 6, x=PX, y=H / 2, scale=PS)
    SCX, SCY, SIG = 20.0, 10.0, 300.0           # hull centre (plate px)
    CKX, CKY = -102.0, -91.0                     # cockpit canopy (plate px)
    def bank(i, j, x0, y0, f):
        w = math.exp(-((x0 - SCX) ** 2 + (y0 - SCY) ** 2) / (2 * SIG * SIG))
        ph = 2 * math.pi * f / 480
        th = math.sin(ph) * 0.07
        bx, by = math.sin(ph * 2) * 10, math.sin(ph) * 16
        return w * (-th * (y0 - SCY) + bx), w * (th * (x0 - SCX) + by)
    shade_l = shape("Shade", rect(W, H, x=W / 2, y=H / 2), lgrad([(argb("#000000", 255), 0), (argb("#000000", 190), 0.4), (argb("#000000", 0), 0.66)], 0, 0, W, 0))
    ret = node("Reticle", shape("R", ellipse(150, 150), stroke(argb(AMBER, 200), 2)),
               shape("T", poly([(-95, 0), (-80, 0)]), poly([(80, 0), (95, 0)]), poly([(0, -95), (0, -80)]), poly([(0, 80), (0, 95)]),
                     stroke(argb(AMBER), 3, "butt")),
               NT("Rt", "SQN-03  ·  LOCK", 13, AMBER, F_MONO, 86, -86, ls=3), x=PX + PS * CKX, y=H / 2 + PS * CKY, scale=0.7)
    root = stack("Root", col, anchor("Squad Layer", squad, w=W, h=H), anchor("Ret L", ret, w=W, h=H),
                 anchor("Streak Layer", streaks, w=W, h=H), anchor("Shade L", shade_l, w=W, h=H),
                 anchor("Scan L", scanlines(W, H, 6, 18), w=W, h=H), anchor("Plate L", plate, w=W, h=H),
                 fill=argb("#000000"), clip=True)
    ab.add(root)
    a = Anim("Loop", 480, "loop")
    mesh_anim(a, pgrid, list(range(0, 481, 8)), bank)
    def ck(f):
        dx, dy = bank(0, 0, CKX, CKY, f)
        return PX + PS * (CKX + dx), H / 2 + PS * (CKY + dy)
    a.key(ret.id, 13, [(f, ck(f)[0], "linear") for f in range(0, 481, 8)])
    a.key(ret.id, 14, [(f, ck(f)[1], "linear") for f in range(0, 481, 8)])
    a.key(ret.id, 15, [(0, 0, "linear"), (480, 6.2831853, "linear")])
    a.key(streaks.id, 13, [(0, 0, "linear"), (480, -3 * W, "linear")])
    a.key(squad.id, 13, [(0, -420), (110, 700, EASE_OUT), (360, 820, EASE), (480, 1500, (0.6, 0, 1, 1))])
    a.key(squad.id, 14, [(0, 420), (110, 300, EASE_OUT), (240, 270), (360, 310), (480, 170)])
    a.key(squad.id, 15, [(0, -0.22), (110, 0.04), (240, -0.06), (360, 0.05), (480, -0.25)])
    a.key(lasers.id, 18, [(0, 0, "hold"), (150, 1, "hold"), (156, 0, "hold"), (200, 1, "hold"), (206, 0, "hold"), (290, 1, "hold"), (296, 0, "hold")])
    a.key(lasers.id, 13, [(0, 0, "hold"), (150, 0), (156, 200), (200, 0, "hold"), (206, 200), (290, 0, "hold"), (296, 200)])
    for fl in (f1, f2, f3):
        a.key(fl.id, 16, [(f, 1.0 if (f // 4) % 2 else 1.45, "hold") for f in range(0, 480, 4)])
    a.key(t1.id, 13, [(0, -700), (34, 0, EASE_OUT), (440, 0), (466, 800, (0.6, 0, 1, 1))])
    a.key(t2.id, 13, [(0, -900), (44, 0, EASE_OUT), (446, 0), (472, 900, (0.6, 0, 1, 1))])
    a.key(pr.id, 16, [(0, 0, "hold"), (40, 0), (70, 1, EASE_OUT), (440, 1), (470, 0)])
    a.key(shine.id, 13, [(0, -60, "hold"), (300, -60), (340, 290, "linear"), (480, 290, "hold")])
    ab.add(a.el)
    finish_sm(ab, [loop_layer(a)], name="BB")
    return ab


# ---------------------------------------------------------------- 1 RIVE
def bb_rive():
    W, H = 1024, 512
    ab = bb_artboard("BB Rive", W, H, 1100)
    logo_box = box("Logo Box", node("Logo", E("NestedArtboard", E("NestedStateMachine", animationId=LOGO_SM, name="Logo SM"),
                                              artboardId=LOGO_AB, name="BB Logo", x=0, y=0, scaleX=0.62, scaleY=0.62,
                                              dataBindPathIds=path("logoBB"), id=nid())),
                   w=496, h=248, ws="fixed", hs="fixed")
    tag = it("Tag", "THE ENGINE FOR INTERACTIVE EVERYTHING", 24, WHITE, weight=700, ls=6)
    kick_row = box("Kick Row", mt("Kick", "// rive.app", 18, AMBER, ls=3), mt("K2", "::  runtime_state = ACTIVE", 14, FAINT, ls=2),
                   dir="row", gap=18, align="center")
    col = box("Column", logo_box, tag, spacer(1, 2), kick_row, gap=12, ws="fill", hs="fill", align="center", pad=(0, 0, 40, 0))
    # perspective floor grid scrolling toward the viewer
    gl = []
    for k in range(-14, 15):
        gl.append(shape(f"V{k}", poly([(W / 2 + k * 26, 0), (W / 2 + k * 120, 260)]), stroke(argb("#FFA41C", 46), 1.5)))
    hl = [shape(f"H{k}", poly([(0, (k / 10) ** 2 * 260), (W, (k / 10) ** 2 * 260)]), stroke(argb("#FFA41C", 40), 1.5)) for k in range(1, 11)]
    hlines = node("H Lines", *hl)
    grid = node("Grid", *gl, hlines, x=0, y=300)
    fade = shape("Fade", rect(W, 140, x=W / 2, y=320), lgrad([(argb("#050506"), 0), (argb("#050506", 0), 1)], 0, 250, 0, 390))
    # prism particles orbiting the logo
    orbit = node("Orbit", *[shape(f"P{k}", ellipse(10, 10), solid(argb(PRISM[k])), x=330 * math.cos(k * math.pi / 3),
                                  y=110 * math.sin(k * math.pi / 3)) for k in range(6)], x=W / 2, y=180)
    sweep = node("Sweep", shape("S", rect(W, 3, x=W / 2, y=0), lgrad([(argb(WHITE, 0), 0), (argb(WHITE, 70), 0.5), (argb(WHITE, 0), 1)], 0, 0, W, 0)))
    corners = []
    for i, (cx, cy, sx, sy) in enumerate([(30, 30, 1, 1), (W - 30, 30, -1, 1), (30, H - 54, 1, -1), (W - 30, H - 54, -1, -1)]):
        corners.append(node(f"Corner {i}", shape("C", poly([(0, 34 * sy), (0, 0), (34 * sx, 0)]), stroke(argb(WHITE, 140), 3, "butt")),
                            x=cx, y=cy))
    seg = 64
    strip = node("Strip", *[shape(f"Seg {k}", rect(seg - 6, 10, x=k * seg + seg / 2, y=5), solid(argb(PRISM[k % 6]))) for k in range(40)])
    strip_l = layer("Strip Layer", anchor("Strip A", strip, w=W, h=10), align="bottomLeft", pad=(0, 0, 18, 0), clip=True)
    root = stack("Root", col, strip_l, anchor("FX", sweep, *corners, orbit, w=W, h=H), anchor("Floor", fade, grid, w=W, h=H),
                 fill=argb("#050506"), clip=True)
    ab.add(root)
    a = Anim("Strip", 120, "loop")
    a.key(strip.id, 13, [(0, 0, "linear"), (120, -6 * seg, "linear")])
    b = Anim("Tag", 420, "loop")
    b.key(tag.id, 18, [(0, 0), (30, 1), (380, 1), (420, 0)])
    c = Anim("Grid", 90, "loop")
    c.key(hlines.id, 14, [(0, 0, "linear"), (90, 26, "linear")])
    d = Anim("Orbit", 600, "loop")
    d.key(orbit.id, 15, [(0, 0, "linear"), (600, 6.2831853, "linear")])
    e = Anim("Sweep", 240, "loop")
    e.key(sweep.id, 14, [(0, -20, "linear"), (160, H + 20, "linear"), (240, H + 20, "hold")])
    for i, cn in enumerate(corners):
        e.key(cn.id, 18, [(0, 0.4), (60 + i * 10, 1), (200, 1), (240, 0.4)])
    ab.add(a.el, b.el, c.el, d.el, e.el)
    finish_sm(ab, [loop_layer(a), loop_layer(b), loop_layer(c), loop_layer(d), loop_layer(e)], name="BB")
    return ab


# ---------------------------------------------------------------- 2 KINETIC
def bb_kinetic():
    W, H = 1024, 512
    ab = bb_artboard("BB Kinetic", W, H, 2200)
    rr = _rnd.Random(7)
    rays = node("Rays", *[shape(f"R{k}", poly([(0, 0), (900 * math.cos(a - 0.09), 900 * math.sin(a - 0.09)),
                                              (900 * math.cos(a + 0.09), 900 * math.sin(a + 0.09))], True), solid(argb("#B6FF2E", 26)))
                          for k, a in enumerate([k * math.pi / 9 for k in range(18)])], x=200, y=256)
    bubbles = [node(f"Bub{k}", shape("B", ellipse(s, s), stroke(argb(WHITE, 170), 2.5)), x=rr.uniform(90, 310), y=560)
               for k, s in enumerate([rr.choice([10, 14, 18, 24]) for _ in range(12)])]
    bolt_fx = node("Bolt FX", shape("B", poly([(16, -120), (-40, 10), (0, 10), (-24, 120), (56, -20), (14, -20)], True), solid(argb(WHITE))),
                   x=320, y=200, opacity=0)
    can_img, cgrid = mesh_image("Can Plate", "can", 4, 8, scale=0.46)
    can = node("Can", can_img, x=200, y=250)
    word_t = NT("K", "KINETIC", 132, "#B6FF2E", F_ORB, 0, 80, weight=900)
    word = node("Word", word_t, rot=-0.06)
    word_a = anchor("Word A", word, w=600, h=150)
    chip = box("Chip", ot("C", "NEW: VOLT LIME", 20, BLACK, ls=2), pad=(12, 22, 12, 22), radius=6, fill=argb("#B6FF2E"))
    col = box("Text", word_a, mt("S", "ZERO SUGAR  ·  FULL VOLTAGE", 24, WHITE, ls=4), spacer(1, 10), chip, gap=8, ws="fill", hs="fill",
              align="centerLeft", pad=(0, 0, 0, 48))
    art_col = anchor("Can Art", *bubbles, can, bolt_fx, w=400, h=H)
    row = box("Row", col, art_col, dir="row", ws="fill", hs="fill")
    root = stack("Root", row, anchor("Scan", scanlines(W, H, 6, 30), w=W, h=H), anchor("Ray Layer", rays, w=W, h=H),
                 grad=lgrad([(argb("#0A1404"), 0), (argb("#000000"), 1)], 0, 0, W, H), clip=True)
    # rays sit behind the can: move their centre to the can column
    rays.attrs.update(x=str(W - 200), y="256")
    ab.add(root)
    a = Anim("Loop", 240, "loop")
    a.key(rays.id, 15, [(0, 0, "linear"), (240, 0.6981317, "linear")])
    a.key(can.id, 14, [(0, 250), (30, 210, (0.2, 0.8, 0.4, 1)), (60, 250, (0.6, 0, 0.8, 0.2)), (70, 244), (80, 250),
                       (150, 250), (180, 210, (0.2, 0.8, 0.4, 1)), (210, 250, (0.6, 0, 0.8, 0.2)), (220, 244), (240, 250)])
    a.key(can.id, 15, [(0, 0), (30, -0.14), (60, 0), (180, 0.14), (210, 0), (240, 0)])
    a.key(word.id, 16, [(0, 1), (56, 1), (62, 1.07), (76, 1, BACK_OUT), (206, 1), (212, 1.07), (226, 1, BACK_OUT), (240, 1)])
    a.key(word.id, 17, [(0, 1), (56, 1), (62, 1.07), (76, 1, BACK_OUT), (206, 1), (212, 1.07), (226, 1, BACK_OUT), (240, 1)])
    a.key(word.id, 13, [(0, 0), (60, 0), (62, 6, "hold"), (64, -4, "hold"), (66, 0), (210, 0), (212, 6, "hold"), (214, -4, "hold"), (216, 0)])
    a.key(bolt_fx.id, 18, [(0, 0, "hold"), (60, 1, "hold"), (63, 0, "hold"), (66, 0.8, "hold"), (70, 0, "hold"), (210, 1, "hold"), (213, 0, "hold")])
    for k, bnode in enumerate(bubbles):
        st = (k * 37) % 240
        a.key(bnode.id, 14, [(0, 560 - (st / 240) * 620, "linear"), (240 - st, -60, "linear"), (240 - st + 1, 560, "linear"), (240, 560 - (st / 240) * 620, "linear")]
              if st > 0 else [(0, 560, "linear"), (240, -60, "linear")])
    # jelly wobble of the can after each landing (frames 60 and 210), keyed on the mesh
    def wob(i, j, x0, y0, f):
        v = (y0 + 512) / 1024
        amp = 0.0
        for land in (60, 210):
            t = f - land
            if 0 <= t < 60:
                amp += 34 * math.exp(-t / 16) * math.sin(t * 0.55)
        return amp * (0.5 - v) * math.cos(v * 3.0), -abs(amp) * 0.35 * (1 - v)
    mesh_anim(a, cgrid, list(range(0, 241, 3)), wob)
    ab.add(a.el)
    finish_sm(ab, [loop_layer(a)], name="BB")
    return ab


# ---------------------------------------------------------------- 3 MERIDIAN LIVE (data bound)
def bb_live():
    W, H = 1024, 512
    ab = bb_artboard("BB Live", W, H, 3300)
    dot = node("Live Dot", shape("D", ellipse(16, 16), solid(argb("#FF2E3C"))), shape("Halo", ellipse(30, 30), stroke(argb("#FF2E3C", 120), 2)), x=8, y=8)
    head = box("Head", anchor("Dot", dot, w=16, h=16), ot("H1", "MERIDIAN", 30, WHITE, ls=4), ot("H2", "LIVE", 30, "#FF2E3C", ls=4),
               box("Grow", ws="fill"), mt("Clock", "23:47", 22, WHITE, ls=3, bindname="clock"), dir="row", align="center", gap=14, ws="fill")
    rule = box("Rule", ws="fill", h=2, hs="fixed", fill=argb("#2C2C30"))
    bar = node("Bar", shape("B", rect(380, 10, x=190, y=5), lgrad([(argb(AMBER), 0), (argb("#FF483C"), 1)], 0, 0, 380, 0)),
               binds=(bind("speedFrac", 16),))
    bar_bg = box("Bar BG", anchor("Bar A", bar, w=380, h=10), w=380, h=10, ws="fixed", hs="fixed", fill=argb("#24242A"), radius=5, clip=True)
    spd = box("Speed", mt("K", "YOUR SPEED", 18, MUTED, ls=4),
              box("V Row", ot("V", "000", 150, AMBER, bindname="bbSpeed"), mt("U", "KM/H", 22, WHITE, ls=6), dir="row", align="bottomLeft", gap=12),
              bar_bg, gap=10, ws="fill", hs="fill", extra={"flexBasis": 0, "flexBasisUnitsValue": "points"})
    rr = _rnd.Random(5)
    eqb = [node(f"EQ{k}", shape("B", rect(10, 80, x=0, y=-40, r=2), solid(argb(PRISM[(k // 4) % 6]))), x=8 + k * 15, y=80, sy=0.4)
           for k in range(24)]
    eq = anchor("EQ", *eqb, w=24 * 15, h=80)
    skip = box("Skip", mt("Hint", "TAP TO SKIP", 16, MUTED, ls=3), chevron("Chev", MUTED, 12, 2.2), dir="row", align="center", gap=8)
    now = box("Now", mt("K", "NOW PLAYING", 18, MUTED, ls=4), ot("T", "AFTERBURN", 40, WHITE, bindname="trackTitle"),
              mt("A", "ROCKET SQUADRON OST", 18, AMBER, ls=2, bindname="trackArtist"), spacer(1, 6), eq, spacer(1, 4), skip,
              gap=8, ws="fill", hs="fill", extra={"flexBasis": 0, "flexBasisUnitsValue": "points"})
    body = box("Body", spd, now, dir="row", gap=40, ws="fill", hs="fill")
    col = box("Column", head, rule, body, gap=22, ws="fill", hs="fill", pad=(34, 44, 70, 44))
    tick_txt = "SKY LANE 26 OPEN  ·  NEON ST GRIDLOCK CLEARED  ·  ROCKET SQUADRON S03 LIVE NOW  ·  RAIN 2% AFTER MIDNIGHT  ·  BUILT WITH RIVE  ·  "
    ticker = node("Ticker", NT("T1", tick_txt, 20, BLACK, F_MONO, 0, 26, ls=2), NT("T2", tick_txt, 20, BLACK, F_MONO, 1800, 26, ls=2))
    band = layer("Band L", box("Band", anchor("Tick A", ticker, w=W, h=52), ws="fill", h=52, hs="fixed", fill=argb(AMBER), clip=True),
                 align="bottomLeft")
    hit = hit_layer()
    root = stack("Root", hit, band, col, grad=lgrad([(argb("#0C0C10"), 0), (argb("#16161C"), 1)], 0, 0, 0, H), clip=True)
    ab.add(root)
    a = Anim("Ticker", 1200, "loop")
    a.key(ticker.id, 13, [(0, 0, "linear"), (1200, -1800, "linear")])
    b = Anim("Pulse", 60, "loop")
    b.key(dot.id, 18, [(0, 1), (30, 0.25), (60, 1)])
    c = Anim("EQ", 96, "loop")
    for e in eqb:
        c.key(e.id, 17, [(f, rr.uniform(0.12, 1.0) if 0 < f < 96 else 0.4) for f in range(0, 97, 8)])
    ab.add(a.el, b.el, c.el)
    finish_sm(ab, [loop_layer(a), loop_layer(b), loop_layer(c)], [req_listener(hit.id, 41, "Skip Track")], name="BB")
    return ab


# ---------------------------------------------------------------- 4 SKYLINE ARCADE (interactive)
def bb_arcade():
    W, H = 1024, 512
    ab = bb_artboard("BB Arcade", W, H, 4400)
    vl = [shape(f"V{k}", poly([(W / 2 + (k - 10) * 30, 0), (W / 2 + (k - 10) * 140, 220)]), stroke(argb("#F30058", 150), 2)) for k in range(21)]
    hlines = node("H", *[shape(f"H{k}", poly([(0, (k / 9) ** 2 * 220), (W, (k / 9) ** 2 * 220)]), stroke(argb("#F30058", 120), 2)) for k in range(1, 10)])
    grid = node("Grid", *vl, hlines, x=0, y=320)
    sun = node("Sun", shape("S", ellipse(260, 260), lgrad([(argb("#FFA41C"), 0), (argb("#F30058"), 1)], 0, -130, 0, 130)),
               *[shape(f"Cut{k}", rect(280, 4 + k * 2, x=0, y=30 + k * 22), solid(argb("#2A0B3A"))) for k in range(5)], x=W / 2, y=250)
    rings = [node(f"Ring{k}", shape("R", ellipse(120, 120), stroke(argb(PRISM[(k * 2) % 6]), 6)), x=W / 2, y=250, opacity=0, scale=0.2)
             for k in range(3)]
    # marching invaders
    px = [(1, 0), (5, 0), (2, 1), (4, 1), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (0, 3), (1, 3), (3, 3), (5, 3), (6, 3),
          (0, 4), (1, 4), (2, 4), (3, 4), (4, 4), (5, 4), (6, 4), (0, 5), (2, 5), (4, 5), (6, 5)]
    def invader(k, col):
        return node(f"Inv{k}", *[shape(f"p{i}", rect(6, 6, x=x * 6, y=y * 6), solid(argb(col))) for i, (x, y) in enumerate(px)],
                    x=120 + k * 110, y=150)
    invs = node("Invaders", *[invader(k, PRISM[(k + 3) % 6]) for k in range(8)])
    title_row = box("Title Row", ot("T", "SKYLINE ARCADE", 52, WHITE, ls=5), ws="fill", align="center")
    taps = layer("Taps L", box("Taps", mt("L", "TAPS", 16, MUTED, ls=4), ot("V", "1287", 34, AMBER, bindname="taps"), align="center", gap=4),
                 align="topRight", pad=(30, 40, 0, 0))
    tap_t = ot("Tap", "TAP TO PLAY", 40, "#19F2FF", ls=8)
    tap_l = layer("Tap L", box("Tap Box", tap_t, pad=(8, 24, 8, 24), radius=10, fill=argb("#12061C", 200)), align="bottomCenter", pad=(0, 0, 36, 0))
    flash = layer("Flash", fill=argb(WHITE), opacity=0, bid=nid())
    hit = hit_layer()
    head = layer("Head L", title_row, align="topCenter", pad=(34, 0, 0, 0))
    root = stack("Root", hit, flash, taps, tap_l, head, anchor("Inv Layer", invs, w=W, h=H), anchor("Burst", *rings, w=W, h=H),
                 anchor("Scene", sun, grid, w=W, h=H),
                 grad=lgrad([(argb("#12061C"), 0), (argb("#2A0B3A"), 0.6), (argb("#12061C"), 1)], 0, 0, 0, H), clip=True)
    ab.add(root)
    idle = Anim("Idle", 120, "loop")
    idle.key(tap_t.id, 18, [(0, 1), (60, 0.35), (120, 1)])
    idle.key(hlines.id, 14, [(0, 0, "linear"), (120, 24, "linear")])
    march = Anim("March", 240, "loop")
    march.key(invs.id, 13, [(f, (f // 20 % 6 if f // 20 % 12 < 6 else 6 - f // 20 % 6) * 14 - 40, "hold") for f in range(0, 240, 20)])
    march.key(invs.id, 14, [(0, -40, "hold"), (120, -30, "hold"), (240, -40, "hold")])
    burst = Anim("Burst", 50)
    for k, r in enumerate(rings):
        burst.key(r.id, 18, [(0, 0, "hold"), (k * 5, 1), (40 + k * 3, 0)])
        burst.key(r.id, 16, [(0, 0.2, "hold"), (k * 5, 0.2), (40 + k * 3, 6 + k, EASE_OUT)])
        burst.key(r.id, 17, [(0, 0.2, "hold"), (k * 5, 0.2), (40 + k * 3, 6 + k, EASE_OUT)])
    burst.key(flash.id, 18, [(0, 0.55), (14, 0)])
    burst.key(sun.id, 16, [(0, 1.15), (30, 1, BACK_OUT)])
    burst.key(sun.id, 17, [(0, 1.15), (30, 1, BACK_OUT)])
    rest = Anim("Rest", 1)
    for r in rings:
        rest.hold(r.id, 18, 0)
    rest.hold(flash.id, 18, 0)
    ab.add(idle.el, march.el, burst.el, rest.el)
    s_r, s_b = nid(), nid()
    lay = sm_layer("Burst", s_r,
                   state(rest, go(s_b, cond("hitT", 0.5, "greaterThan")), sid=s_r, x=200, y=0),
                   state(burst, go(s_r, cond("hitT", 0.5, "lessThan"), exit_pct=100), sid=s_b, x=420, y=0, reset=True))
    finish_sm(ab, [loop_layer(idle), loop_layer(march), lay], [req_listener(hit.id, 20, "Tap")], name="BB")
    return ab


# ---------------------------------------------------------------- 5 HOTEL AURORA (vertical neon)
def bb_hotel():
    W, H = 512, 1024
    ab = bb_artboard("BB Hotel", W, H, 5500)
    letters = [ot(f"L{k}", ch, 100, "#19F2FF") for k, ch in enumerate("HOTEL")]
    aur = ot("A", "AURORA", 64, "#F30058", ls=4)
    vac = ot("V", "VACANCY", 34, AMBER, ls=6)
    stars = [node(f"S{k}", shape("S", poly([(0, -12), (3, -3), (12, 0), (3, 3), (0, 12), (-3, 3), (-12, 0), (-3, -3)], True), solid(argb(WHITE))),
                  x=x, y=y) for k, (x, y) in enumerate([(70, 640), (440, 620), (90, 930), (420, 940), (256, 600)])]
    # marquee bulbs chasing around the frame
    bulbs = []
    per = 2 * (W - 40) + 2 * (H - 40)
    n = 44
    for k in range(n):
        d = k / n * per
        if d < W - 40:
            x, y = 20 + d, 20
        elif d < W - 40 + H - 40:
            x, y = W - 20, 20 + d - (W - 40)
        elif d < 2 * (W - 40) + H - 40:
            x, y = W - 20 - (d - (W - 40) - (H - 40)), H - 20
        else:
            x, y = 20, H - 20 - (d - 2 * (W - 40) - (H - 40))
        bulbs.append(node(f"B{k}", shape("B", ellipse(12, 12), solid(argb(AMBER))), x=x, y=y, opacity=0.25))
    frame = node("Frame", shape("F", rect(W - 70, H - 70, x=W / 2, y=H / 2, r=24), stroke(argb("#F30058"), 6)),
                 shape("F2", rect(W - 100, H - 100, x=W / 2, y=H / 2, r=18), stroke(argb("#19F2FF", 120), 3)))
    col = box("Column", *letters, spacer(1, 16), aur, spacer(1, 30), vac, gap=2, ws="fill", hs="fill", align="center", pad=(40, 0, 40, 0))
    root = stack("Root", col, anchor("Deco", *bulbs, frame, *stars, w=W, h=H), fill=argb("#07060C"), clip=True)
    ab.add(root)
    a = Anim("Sequence", 300, "loop")
    for k, l in enumerate(letters):
        on = 12 + k * 14
        a.key(l.id, 18, [(0, 0.12, "hold"), (on, 1, "hold"), (on + 3, 0.3, "hold"), (on + 6, 1, "hold"), (250, 1, "hold"), (256, 0.12, "hold")])
    a.key(aur.id, 18, [(0, 0.1, "hold"), (90, 1, "hold"), (93, 0.4, "hold"), (97, 1, "hold"), (250, 1, "hold"), (256, 0.1, "hold")])
    a.key(vac.id, 18, [(f, (0.25 if f in (150, 156, 200) else 1) if f >= 110 else 0.1, "hold") for f in range(0, 300, 6)])
    for k, s in enumerate(stars):
        a.key(s.id, 15, [(0, 0, "linear"), (300, 1.2 + 0.3 * k, "linear")])
        a.key(s.id, 16, [(0, 0.6), (75 + k * 20, 1.2), (150 + k * 20, 0.6), (300, 0.6)])
        a.key(s.id, 17, [(0, 0.6), (75 + k * 20, 1.2), (150 + k * 20, 0.6), (300, 0.6)])
    a.key(frame.id, 18, [(0, 0.5), (20, 1), (280, 1), (300, 0.5)])
    ch = Anim("Chase", 44, "loop")
    for k, bnode in enumerate(bulbs):
        ch.key(bnode.id, 18, [(f, 1.0 if (f + k) % 4 == 0 else 0.22, "hold") for f in range(0, 44, 2)])
    ab.add(a.el, ch.el)
    finish_sm(ab, [loop_layer(a), loop_layer(ch)], name="BB")
    return ab



# ---------------------------------------------------------------- 6 NISHIKI (koi on a mesh)
def bb_koi():
    W, H = 1024, 512
    ab = bb_artboard("BB Koi", W, H, 7700)
    T = 72
    def wave(i, j, x0, y0, f):
        u = (x0 + 512) / 1024
        amp = 6 + 46 * u ** 1.6
        ph = 2 * math.pi * (f / T) - u * 5.2
        return 0.0, amp * math.sin(ph)
    swim = Anim("Swim", T, "loop")
    fish, grid = mesh_image("Koi", "koi", 16, 3, scale=0.7)
    mesh_anim(swim, grid, list(range(0, T + 1, 3)), wave)
    fish2, grid2 = mesh_image("Koi 2", "koi", 16, 3, scale=0.46)
    mesh_anim(swim, grid2, list(range(0, T + 1, 3)), lambda i, j, x0, y0, f: wave(i, j, x0, y0, (f + 30) % T))
    koi_n = node("Koi Path", fish, x=W + 300, y=360)
    koi2 = node("Koi Path 2", fish2, x=W + 240, y=180)
    # water: dark gradient + caustic lines + ripple rings (vector)
    rr = _rnd.Random(21)
    caus = node("Caustics", *[shape(f"C{k}", poly([(x, y), (x + rr.uniform(80, 220), y + rr.uniform(-30, 30)),
                                                   (x + rr.uniform(220, 380), y + rr.uniform(-20, 40))]),
                                     stroke(argb("#3FE0FF", rr.randint(14, 34)), rr.uniform(1.5, 3.5)))
                              for k, (x, y) in enumerate([(rr.uniform(-200, W), rr.uniform(0, H)) for _ in range(26)])])
    rings = [node(f"Ring{k}", shape("R", ellipse(120, 60), stroke(argb("#9FF4FF", 140), 2)), x=rr.uniform(200, 900), y=rr.uniform(120, 400),
                  scale=0.2, opacity=0) for k in range(4)]
    seal = node("Seal", shape("Dot", ellipse(12, 12), solid(argb(WHITE)), x=8, y=-6), shape("Hanko", ellipse(46, 46), stroke(argb(WHITE), 4)),
                shape("Sq", rect(76, 76, x=0, y=0, r=6), solid(argb("#E8202A"))))
    t1 = NT("T1", "NISHIKI", 104, WHITE, F_ORB, 0, 52, weight=900, ls=10)
    title = anchor("Title", t1, w=620, h=110)
    col = box("Text", box("Seal Row", anchor("Seal A", node("Seal P", seal, x=38, y=38), w=76, h=76),
                          box("Kick Col", mt("K1", "KOI NOIR  ·  OMAKASE", 20, "#9FF4FF", ls=4), mt("K2", "LEVEL 42  ·  OPEN TILL 4AM", 16, MUTED, ls=3),
                              gap=6), dir="row", align="center", gap=18),
              title, gap=10, ws="fill", hs="fill", align="topLeft", pad=(44, 0, 0, 52))
    root = stack("Root", col, anchor("Fx", *rings, w=W, h=H), anchor("Fish Layer", koi2, koi_n, w=W, h=H), anchor("Water", caus, w=W, h=H),
                 anchor("Scan", scanlines(W, H), w=W, h=H),
                 grad=lgrad([(argb("#03141A"), 0), (argb("#000000"), 1)], 0, 0, 0, H), clip=True)
    ab.add(root)
    a = Anim("Loop", 600, "loop")
    a.key(koi_n.id, 13, [(0, W + 300, "linear"), (600, -300, "linear")])
    a.key(koi_n.id, 14, [(0, 360), (150, 330), (300, 400), (450, 340), (600, 360)])
    a.key(koi_n.id, 15, [(0, 0.08), (150, -0.1), (300, 0.12), (450, -0.06), (600, 0.08)])
    # second, smaller koi half a loop behind (wraps at the edges, always one fish on screen)
    a.key(koi2.id, 13, [(0, W / 2 - 60, "linear"), (300, -240, "hold"), (301, W + 240, "linear"), (600, W / 2 - 60, "linear")])
    a.key(koi2.id, 14, [(0, 200), (150, 160), (300, 220), (450, 170), (600, 200)])
    a.key(koi2.id, 15, [(0, -0.1), (150, 0.08), (300, -0.04), (450, 0.1), (600, -0.1)])
    a.key(caus.id, 13, [(0, 0, "linear"), (600, -160, "linear")])
    for k, r_ in enumerate(rings):
        o = k * 150
        a.key(r_.id, 16, [(0, 0.2, "hold"), (o, 0.2), (o + 140, 2.4, EASE_OUT), (min(600, o + 141), 0.2, "hold")])
        a.key(r_.id, 17, [(0, 0.2, "hold"), (o, 0.2), (o + 140, 2.4, EASE_OUT), (min(600, o + 141), 0.2, "hold")])
        a.key(r_.id, 18, [(0, 0, "hold"), (o, 0.9), (o + 140, 0), (600, 0, "hold")])
    ab.add(a.el, swim.el)
    finish_sm(ab, [loop_layer(a), loop_layer(swim)], name="BB")
    return ab


# ---------------------------------------------------------------- 7 AURA (face on a mesh, neon portrait)
def bb_aura():
    W, H = 512, 1024
    ab = bb_artboard("BB Aura", W, H, 8900)
    face, grid = mesh_image("Face", "face", 6, 10, x=W / 2 - 52, y=H / 2, scale=1.02)
    T = 360
    def sway(i, j, x0, y0, f):
        v = (y0 + 512) / 1024                     # 0 top .. 1 bottom
        u = (x0 + 288) / 576
        ph = 2 * math.pi * f / T
        tilt = math.sin(ph) * 16 * (1 - v) ** 1.4  # head tilts from the neck
        breathe = math.sin(ph * 2) * 5 * v * (1 - v) * 4
        hair = math.sin(ph * 2 + v * 4) * 7 * max(0.0, 0.35 - u) / 0.35   # loose hair at the left edge
        return tilt + hair, -breathe * 0.6 + math.sin(ph) * 3 * (1 - v)
    a = Anim("Sway", T, "loop")
    mesh_anim(a, grid, list(range(0, T + 1, 10)), sway)
    letters = [NT(f"L{k}", ch, 80, "#F30058", F_ORB, 0, 64 + k * 98, ox=0.5, weight=900, align="center") for k, ch in enumerate("AURA")]
    word = node("Word", *letters, x=458, y=0)
    scan = node("Scan", shape("S", rect(W, 3, x=W / 2, y=0), solid(argb("#19F2FF", 160))),
                shape("G", rect(W, 40, x=W / 2, y=-20), lgrad([(argb("#19F2FF", 0), 0), (argb("#19F2FF", 50), 1)], 0, -40, 0, 0)), x=0, y=-40)
    eye = node("Eye Lock", shape("R", ellipse(110, 110), stroke(argb("#19F2FF", 170), 1.5)),
               shape("T", poly([(-70, 0), (-58, 0)]), poly([(58, 0), (70, 0)]), poly([(0, -70), (0, -58)]), poly([(0, 58), (0, 70)]),
                     stroke(argb("#19F2FF", 200), 2, "butt")),
               NT("Ed", "IRIS 0.92  ·  LUMEN 4", 11, "#19F2FF", F_MONO, 64, -60, ls=2), x=258, y=322, opacity=0)
    foot = box("Foot", mt("F1", "LUMEN SKIN  ·  SERIES 04", 18, WHITE, ls=4), mt("F2", "BE SEEN IN THE DARK", 14, "#F30058", ls=6),
               gap=8, ws="fill", hs="fill", align="bottomLeft", pad=(0, 0, 40, 34))
    deco = anchor("Deco", brackets(W, H, "#19F2FF", 46, 2.5), word, eye, scan, w=W, h=H)
    root = stack("Root", foot, deco, anchor("Scan L", scanlines(W, H, 5, 30), w=W, h=H), anchor("Face L", face, w=W, h=H),
                 fill=argb("#000000"), clip=True)
    ab.add(root)
    m = Anim("Motion", 480, "loop")
    m.key(scan.id, 14, [(0, -40, "linear"), (240, H + 40, "linear"), (480, H + 40, "hold")])
    for k, l in enumerate(letters):
        on = 20 + k * 10
        m.key(l.id, 18, [(0, 0.15, "hold"), (on, 1, "hold"), (on + 3, 0.35, "hold"), (on + 6, 1, "hold"), (440, 1, "hold"), (446, 0.2, "hold"), (450, 1, "hold")])
    m.key(eye.id, 18, [(0, 0, "hold"), (120, 0), (134, 1), (260, 1), (276, 0)])
    m.key(eye.id, 16, [(120, 1.8), (140, 1, EASE_OUT)])
    m.key(eye.id, 17, [(120, 1.8), (140, 1, EASE_OUT)])
    ab.add(a.el, m.el)
    finish_sm(ab, [loop_layer(a), loop_layer(m)], name="BB")
    return ab


# ---------------------------------------------------------------- 8 DEEPWATER (jellyfish on a mesh)
def bb_deep():
    W, H = 512, 1024
    ab = bb_artboard("BB Deep", W, H, 9600)
    jelly, grid = mesh_image("Jelly", "jelly", 6, 12, scale=0.95)
    T = 150
    def pulse(i, j, x0, y0, f):
        v = (y0 + 512) / 1024
        ph = 2 * math.pi * f / T
        if v < 0.42:   # bell: squeeze + stretch
            k = math.sin(ph) * 0.09 * (1 - abs(v - 0.28) / 0.28)
            return x0 * k, -abs(math.sin(ph)) * 10 * (0.42 - v) / 0.42
        sw = (v - 0.42) / 0.58
        return math.sin(ph - sw * 4.5) * 34 * sw ** 1.3, math.sin(ph) * -6 * sw
    a = Anim("Pulse", T, "loop")
    mesh_anim(a, grid, list(range(0, T + 1, 5)), pulse)
    drift = node("Drift", jelly, x=W / 2, y=470)
    rr = _rnd.Random(5)
    parts = [node(f"P{k}", shape("P", ellipse(s, s), solid(argb("#9FF4FF", rr.randint(80, 200)))), x=rr.uniform(20, W - 20), y=rr.uniform(0, H))
             for k, s in enumerate([rr.choice([2, 3, 3, 4, 6]) for _ in range(40)])]
    rings = [node(f"Sonar{k}", shape("R", ellipse(200, 200), stroke(argb("#19F2FF", 160), 2)), x=W / 2, y=300, scale=0.3, opacity=0) for k in range(3)]
    gauge = node("Gauge", *[shape(f"G{k}", poly([(0, k * 40), (14 if k % 5 else 26, k * 40)]), stroke(argb(WHITE, 120), 2, "butt")) for k in range(40)],
                 *[NT(f"GN{k}", f"{(k * 200):04d}", 11, MUTED, F_MONO, 32, k * 200, ls=1) for k in range(8)], x=24, y=0)
    t1 = NT("T1", "DEEPWATER", 46, WHITE, F_ORB, 0, 30, weight=900, ls=3)
    title = anchor("Title", t1, w=440, h=64)
    foot = box("Foot", mt("K", "// AQUARIUM  ·  DECK 88", 16, "#19F2FF", ls=4), title, mt("S", "NIGHT DIVE  ·  OPEN NOW", 14, MUTED, ls=4),
               gap=8, ws="fill", hs="fill", align="bottomLeft", pad=(0, 0, 40, 40))
    root = stack("Root", foot, anchor("Gauge L", gauge, w=W, h=H), anchor("Fx", *rings, *parts, w=W, h=H), anchor("Jelly L", drift, w=W, h=H),
                 anchor("Scan", scanlines(W, H, 6, 26), w=W, h=H),
                 grad=lgrad([(argb("#02121C"), 0), (argb("#000000"), 1)], 0, 0, 0, H), clip=True)
    ab.add(root)
    m = Anim("Motion", 600, "loop")
    m.key(drift.id, 14, [(0, 500), (300, 420), (600, 500)])
    m.key(drift.id, 13, [(0, W / 2), (200, W / 2 + 18), (400, W / 2 - 14), (600, W / 2)])
    m.key(gauge.id, 14, [(0, 0, "linear"), (600, -400, "linear")])
    for k, p in enumerate(parts):
        y0 = float(p.attrs["y"])
        st = (k * 47) % 600
        m.key(p.id, 14, [(0, y0, "linear"), (600, y0 - 260, "linear")])
    for k, r_ in enumerate(rings):
        o = k * 200
        m.key(r_.id, 16, [(0, 0.3, "hold"), (o, 0.3), (o + 160, 2.6, EASE_OUT), (min(600, o + 161), 0.3, "hold")])
        m.key(r_.id, 17, [(0, 0.3, "hold"), (o, 0.3), (o + 160, 2.6, EASE_OUT), (min(600, o + 161), 0.3, "hold")])
        m.key(r_.id, 18, [(0, 0, "hold"), (o, 0.8), (o + 160, 0), (600, 0, "hold")])
    ab.add(a.el, m.el)
    finish_sm(ab, [loop_layer(a), loop_layer(m)], name="BB")
    return ab


def build_billboards():
    return [bb_rocket(), bb_rive(), bb_kinetic(), bb_live(), bb_arcade(), bb_hotel(), bb_koi(), bb_aura(), bb_deep()]
