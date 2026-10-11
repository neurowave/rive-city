# gen_ui.py — cockpit artboards (exec'd inside gen.py's namespace).
# Cluster (driver display), Console (centre touchscreen), Hub (yoke), HUD
# (windshield), Track Row (playlist row component).


# ================================================================ Track Row
def build_track_row():
    W, H = 664, 64
    s, sid = style(layoutWidthScaleType="fixed", layoutHeightScaleType="fixed")
    ab = E("Artboard", s, name="Track Row", id=nid(), width=W, height=H, styleId=sid, isComponent=True,
           viewModelId=TRK_VM, x=5200, y=1200, clip=True)
    c_title, c_bar, c_bg = nid(), nid(), nid()
    play = node("Play", shape("Tri", poly([(-6, -8), (9, 0), (-6, 8)], True), solid(argb(AMBER))), x=0, y=0, opacity=0)
    dot = node("Dot", shape("D", ellipse(6, 6), solid(argb(FAINT))), x=0, y=0)
    icon = box("Icon", node("Icon Art", play, dot), w=28, h=28, ws="fixed", hs="fixed")
    title = ttext("Title", "title", 19, WHITE, F_INTER, 600, cid=c_title)
    artist = ttext("Artist", "artist", 12, MUTED, F_MONO, ls=1.5)
    col = box("Text", title, artist, gap=2, ws="fill", extra={"flexBasis": 0, "flexBasisUnitsValue": "points"})
    dur = ttext("Dur", "dur", 13, MUTED, F_MONO)
    bar = box("Bar", w=4, h=36, ws="fixed", hs="fixed", radius=2, fill=argb(AMBER), bid=nid(), opacity=0)
    rowb = box("Row", bar, icon, col, dur, dir="row", align="center", gap=14, pad=(0, 18, 0, 10), ws="fill", hs="fill",
               radius=12, fill=argb("#18181B", 0), bid=nid())
    bg_cid = fill_color_id(rowb)
    root = box("Root", rowb, w=W, h=H, ws="fixed", hs="fixed", pad=(4, 0, 4, 0))
    ab.add(root)
    on = Anim("Sel On", 12)
    on.color(bg_cid, [(0, argb("#1E1E22", 0)), (12, argb("#202024"))])
    on.color(c_title, [(0, argb(WHITE)), (12, argb(AMBER))])
    on.key(bar.id, 18, [(0, 0), (12, 1)])
    on.key(play.id, 18, [(0, 0), (8, 1)])
    on.key(dot.id, 18, [(0, 1), (8, 0)])
    off = Anim("Sel Off", 12)
    off.color(bg_cid, [(0, argb("#202024")), (12, argb("#1E1E22", 0))])
    off.color(c_title, [(0, argb(AMBER)), (12, argb(WHITE))])
    off.key(bar.id, 18, [(0, 1), (12, 0)])
    off.key(play.id, 18, [(0, 1), (8, 0)])
    off.key(dot.id, 18, [(0, 0), (8, 1)])
    ab.add(on.el, off.el)
    s_off, s_on = nid(), nid()
    lay = sm_layer("Sel", s_off,
                   state(off, go(s_on, cond(None, 0.5, "greaterThan", vmpath=tpath("sel"))), sid=s_off, x=200, y=0),
                   state(on, go(s_off, cond(None, 0.5, "lessThan", vmpath=tpath("sel"))), sid=s_on, x=420, y=0))
    lis = E("StateMachineListenerSingle",
            E("ListenerViewModelChange", E("BindablePropertyNumber", tbind("tap", 636, direction=True), propertyValue=1)),
            targetId=rowb.id, listenerTypeValue="click", name="Tap")
    finish_sm(ab, [lay], [lis], name="Row")
    return ab


# ================================================================ Cluster (driver display)
def build_cluster():
    W, H = 1380, 450
    ab = surface_artboard("Cluster", W, H, 1800)
    cx = W / 2
    # --- speed arc (top) -------------------------------------------------
    a0, a1 = math.radians(198), math.radians(342)
    arc = arc_pts(cx, 470, 520, a0, a1, 72, ry=380)
    ticks = []
    for k in range(0, 33):
        a = a0 + (a1 - a0) * k / 32
        r0 = 0.94 if k % 4 == 0 else 0.97
        ticks.append(poly([(cx + 520 * r0 * math.cos(a), 470 + 380 * r0 * math.sin(a)),
                           (cx + 520 * 1.0 * math.cos(a), 470 + 380 * 1.0 * math.sin(a))]))
    arc_node = node("Arc", shape("Ticks", *ticks, stroke(argb("#5A5A60"), 2, "butt")),
                    shape("Active", poly(arc), stroke(argb(AMBER), 10, "round", trim("powerFrac"))),
                    shape("Track", poly(arc), stroke(argb(TRACK), 10, "round")))
    glint = node("Glint", shape("G", rect(90, 2, x=0, y=0), solid(argb(AMBER))), x=-200, y=58)
    deco = node("Deco", shape("Rule L", poly([(40, 58), (300, 58)]), stroke(argb("#2C2C30"), 1.5)),
                shape("Rule R", poly([(W - 300, 58), (W - 40, 58)]), stroke(argb("#2C2C30"), 1.5)),
                shape("Corner TL", poly([(24, 44), (24, 24), (44, 24)]), stroke(argb(FAINT), 2, "butt")),
                shape("Corner TR", poly([(W - 44, 24), (W - 24, 24), (W - 24, 44)]), stroke(argb(FAINT), 2, "butt")),
                shape("Corner BL", poly([(24, H - 44), (24, H - 24), (44, H - 24)]), stroke(argb(FAINT), 2, "butt")),
                shape("Corner BR", poly([(W - 44, H - 24), (W - 24, H - 24), (W - 24, H - 44)]), stroke(argb(FAINT), 2, "butt")))
    # --- centre -------------------------------------------------------------
    gears = box("Gears", *[orb(f"Gear {g}", g, 22, AMBER if g == "D" else WHITE, opacity_bind=f"g{g}", ls=2, dec=False)
                           for g in "PRND"], dir="row", gap=20, align="center")
    # drive mode hero (speed lives on the HUD only): AUTOPILOT amber / MANUAL white
    ap_tcid, ap_scid = nid(), nid()
    ap_dot = box("AP Dot", w=14, h=14, ws="fixed", hs="fixed", radius=7, fill=argb(AMBER), bid=nid())
    mode_row = box("Mode Row", ap_dot, orb("Mode", "AUTOPILOT", 62, WHITE, bindname="apLabel", lh=66, cid=ap_tcid, ls=2),
                   dir="row", align="center", gap=16)
    ap_rule = box("AP Rule", w=420, h=2, ws="fixed", hs="fixed", fill=argb(AMBER), bid=nid())
    centre = box("Centre",
                 mono("Kicker C", "// DRIVE MODE", 13, AMBER, ls=4),
                 spacer(1, 12),
                 mode_row,
                 spacer(1, 10), ap_rule, spacer(1, 12),
                 mono("Mode Sub", "HANDS FREE  ·  LANE + ROUTE LOCK", 13, MUTED, bindname="apSub", ls=3),
                 spacer(1, 18), gears,
                 align="topCenter", ws="fill", gap=2, pad=(84, 0, 0, 0), bid=nid())
    # --- left: energy ------------------------------------------------------
    def bar(name, bindname, w, col, th=6):
        return art(name, shape(name + " Fill", poly([(0, th / 2), (w, th / 2)]), stroke(argb(col), th, "round", trim(bindname))),
                   shape(name + " Track", poly([(0, th / 2), (w, th / 2)]), stroke(argb(TRACK), th, "round")), w=w, h=th)
    prism = art("Prism", *prism_bar(300, 4), w=300, h=4)
    left = box("Left",
               mono("Kicker L", "// ENERGY", 13, AMBER, ls=4),
               box("Batt Row", orb("Battery", "86", 64, WHITE, bindname="battery", lh=64), orb("Pct", "%", 26, MUTED),
                   dir="row", align="bottomLeft", gap=4),
               inter("Batt Label", "BATTERY", 13, MUTED, 600, ls=4),
               spacer(1, 6), bar("Batt Bar", "batteryFrac", 300, WHITE), spacer(1, 4), prism, spacer(1, 14),
               box("Range Row", orb("Range", "438", 30, WHITE, bindname="range"), mono("Km", "KM  EST. RANGE", 12, MUTED, ls=2),
                   dir="row", align="bottomLeft", gap=10),
               spacer(1, 10),
               box("Power Row", mono("Pw", "POWER", 11, MUTED, ls=3), bar("Power Bar", "powerFrac", 220, AMBER, 4),
                   dir="row", align="center", gap=12),
               w=380, ws="fixed", gap=4, pad=(56, 0, 0, 56), bid=nid())
    # --- right: navigation -------------------------------------------------
    arrow = box("Turn", node("Turn Flip",
                             node("Turn Art",
                                  shape("Stem", poly([(-14, 26), (-14, -4), (12, -4)]), stroke(argb(AMBER), 7, "round")),
                                  shape("Head", poly([(10, -18), (26, -4), (10, 10)], True), solid(argb(AMBER)))),
                             binds=(bind("navTurn", 16),)),
                w=60, h=60, ws="fixed", hs="fixed")
    right = box("Right",
                mono("Kicker R", "// NAV", 13, AMBER, ls=4),
                box("Nav Row", arrow, orb("Nav Dist", "420 M", 46, WHITE, bindname="navDist"), dir="row", align="center", gap=12),
                inter("Nav Verb", "TURN RIGHT", 15, WHITE, 700, bindname="navVerb", ls=3),
                box("Onto", mono("Onto L", "ONTO", 12, MUTED, ls=2), mono("Nav Street", "AURORA ST", 12, WHITE, bindname="navStreet", ls=2),
                    dir="row", gap=8),
                spacer(1, 16),
                box("Alt Row", mono("Alt L", "ALT", 11, MUTED, ls=3), orb("Alt", "0.6", 20, WHITE, bindname="alt"),
                    mono("Alt M", "M", 11, MUTED), dir="row", align="bottomLeft", gap=8),
                spacer(1, 4), bar("Alt Bar", "altFrac", 220, "#19F2FF", 4),
                w=380, ws="fixed", gap=4, align="topRight", pad=(56, 56, 0, 0), bid=nid())
    row = box("Columns", left, centre, right, dir="row", ws="fill", hs="fill", bid=nid())
    strip = box("Strip", mono("St1", "// drive_state", 11, FAINT, ls=2), mono("St2", "CRUISE", 11, WHITE, bindname="modeName", ls=2),
                box("Sp", ws="fill", h=1, hs="fixed"),
                mono("St3", "STREET", 11, FAINT, ls=2), mono("St4", "KESTREL AVE", 11, WHITE, bindname="street", ls=2),
                box("Sp2", w=24, h=1, ws="fixed", hs="fixed"),
                orb("Clock", "23:47", 14, WHITE, bindname="clock"),
                dir="row", align="center", gap=10, ws="fill", pad=(0, 56, 30, 56), bid=nid())
    content = box("Content", layer("Strip Layer", strip, align="bottomCenter"), layer("Cols Layer", row),
                  ws="fill", hs="fill", extra={"layoutTypeValue": "stack"}, bid=nid())
    bg = box("BG", ws="fill", hs="fill", grad=rgrad([(argb("#15151A"), 0), (argb("#060608"), 1)], cx, 120, cx, 900))
    # motion graphics behind the speed: radar pulses, warp streaks + road ribbon (fade in with speed)
    radar = [node(f"Radar {k}", shape("R", ellipse(300, 170), stroke(argb(AMBER, 120), 2.5)), x=cx, y=200, opacity=0, scale=0.3)
             for k in range(3)]
    streak_k = []
    rr2 = __import__("random").Random(9)
    for k in range(32):
        a = k * math.pi * 2 / 32 + rr2.uniform(-0.05, 0.05)
        r0 = rr2.uniform(150, 190)
        streak_k.append(poly([(r0 * math.cos(a), r0 * 0.55 * math.sin(a)), ((r0 + 30) * math.cos(a), (r0 + 30) * 0.55 * math.sin(a))]))
    warp_in = node("Warp In", shape("W", *streak_k, stroke(argb(WHITE, 60), 2, "round")))
    warp = node("Warp", warp_in, x=cx, y=200, binds=(bind("speedFrac", 18),))
    dashes = [node(f"Lane {k}", shape("D", rect(8, 26, r=3), solid(argb(AMBER))), x=cx, y=372, scale=0.3, opacity=0) for k in range(5)]
    edges = node("Edges", shape("L", poly([(cx - 26, 366), (cx - 120, 446)]), stroke(argb(WHITE, 50), 2)),
                 shape("R", poly([(cx + 26, 366), (cx + 120, 446)]), stroke(argb(WHITE, 50), 2)))
    road = node("Road", edges, *dashes, binds=(bind("speedFrac", 18),))
    scan = node("Scan", *[shape(f"S{k}", rect(W, 1.5, x=cx, y=k * 18), solid(argb(WHITE, 9))) for k in range(30)])
    root = box("Root", content, art("Arc Layer", arc_node, glint, deco), art("MoGraph", warp, road, *radar),
               art("Scan Layer", scan), bg, ws="fill", hs="fill", extra={"layoutTypeValue": "stack"}, clip=True)
    ab.add(root)
    # animations
    intro = Anim("Intro", 60)
    intro.key(arc_node.id, 18, [(0, 0), (16, 1)])
    intro.key(left.id, 18, [(0, 0, "hold"), (6, 0), (26, 1)])
    intro.key(left.id, 13, [(6, -70), (30, 0, EASE_OUT)])
    intro.key(centre.id, 18, [(0, 0, "hold"), (12, 0), (30, 1)])
    intro.key(centre.id, 14, [(12, 40), (36, 0, EASE_OUT)])
    intro.key(right.id, 18, [(0, 0, "hold"), (16, 0), (36, 1)])
    intro.key(right.id, 13, [(16, 70), (40, 0, EASE_OUT)])
    intro.key(strip.id, 18, [(0, 0, "hold"), (30, 0), (50, 1)])
    intro.key(deco.id, 18, [(0, 0), (4, 1, "hold"), (6, 0, "hold"), (9, 1, "hold"), (12, 0.3, "hold"), (15, 1)])
    off = Anim("Off", 1)
    for i in (arc_node.id, left.id, centre.id, right.id, strip.id, deco.id):
        off.hold(i, 18, 0)
    glide = Anim("Glint", 240, "loop")
    glide.key(glint.id, 13, [(0, -200, "linear"), (110, W + 200, EASE_IO), (240, W + 200, "hold")])
    ap_on = Anim("AP On", 18)
    ap_on.key(ap_dot.id, 18, [(0, 0), (14, 1)])
    ap_on.color(ap_tcid, [(0, argb(WHITE)), (14, argb(AMBER))])
    ap_on.key(ap_rule.id, 18, [(0, 0.2), (18, 1)])
    ap_off = Anim("AP Off", 18)
    ap_off.key(ap_dot.id, 18, [(0, 1), (14, 0)])
    ap_off.color(ap_tcid, [(0, argb(AMBER)), (14, argb(WHITE))])
    ap_off.key(ap_rule.id, 18, [(0, 1), (18, 0.2)])
    pulse = Anim("AP Pulse", 60, "loop")
    pulse.key(ap_dot.id, 16, [(0, 1), (30, 1.5), (60, 1)])
    pulse.key(ap_dot.id, 17, [(0, 1), (30, 1.5), (60, 1)])
    mg = Anim("MoGraph", 120, "loop")
    for k, rn in enumerate(radar):
        o = k * 40
        fr_s = [(0, 0.3 + 1.3 * ((120 - o) % 120) / 120 if o else 0.3, "linear")]
        mg.key(rn.id, 16, [(0, 0.3, "linear"), (120, 1.6, "linear")] if o == 0 else
               [(0, 0.3 + 1.3 * (120 - o) / 120, "linear"), (o, 1.6, "linear"), (o + 1, 0.3, "linear"), (120, 0.3 + 1.3 * (120 - o) / 120, "linear")])
        mg.key(rn.id, 17, [(0, 0.3, "linear"), (120, 1.6, "linear")] if o == 0 else
               [(0, 0.3 + 1.3 * (120 - o) / 120, "linear"), (o, 1.6, "linear"), (o + 1, 0.3, "linear"), (120, 0.3 + 1.3 * (120 - o) / 120, "linear")])
        mg.key(rn.id, 18, [(0, 0.7, "linear"), (120, 0, "linear")] if o == 0 else
               [(0, 0.7 * o / 120, "linear"), (o, 0, "linear"), (o + 1, 0.7, "linear"), (120, 0.7 * o / 120, "linear")])
    mg.key(warp_in.id, 16, [(0, 1, "linear"), (30, 1.5, "linear"), (31, 1, "linear"), (60, 1.5, "linear"), (61, 1, "linear"), (90, 1.5, "linear"), (91, 1, "linear"), (120, 1.5, "linear")])
    mg.key(warp_in.id, 17, [(0, 1, "linear"), (30, 1.5, "linear"), (31, 1, "linear"), (60, 1.5, "linear"), (61, 1, "linear"), (90, 1.5, "linear"), (91, 1, "linear"), (120, 1.5, "linear")])
    mg.key(warp_in.id, 15, [(0, 0, "linear"), (120, 0.3, "linear")])
    for k, dn in enumerate(dashes):
        o = k * 24
        ys = [(0, 330), (120, 440)]
        fr_y, fr_s2, fr_o = [], [], []
        for f in range(0, 121, 4):
            ph = ((f + o) % 120) / 120.0
            fr_y.append((f, 368 + 80 * ph * ph, "linear"))
            fr_s2.append((f, 0.2 + 0.8 * ph, "linear"))
            fr_o.append((f, min(1.0, ph * 4) * (1 - max(0.0, ph - 0.8) * 5), "linear"))
        mg.key(dn.id, 14, fr_y)
        mg.key(dn.id, 16, fr_s2)
        mg.key(dn.id, 17, fr_s2)
        mg.key(dn.id, 18, fr_o)
    mg.key(scan.id, 14, [(0, 0, "linear"), (120, 18, "linear")])
    ab.add(intro.el, off.el, glide.el, ap_on.el, ap_off.el, pulse.el, mg.el)
    s_on, s_off = nid(), nid()
    ap_layer = sm_layer("Autopilot", s_on,
                        state(ap_on, go(s_off, cond("ap", 0.5, "lessThan")), sid=s_on, x=200, y=0),
                        state(ap_off, go(s_on, cond("ap", 0.5, "greaterThan")), sid=s_off, x=420, y=0))
    finish_sm(ab, [boot_layer(ab, "bootCl", intro, off), loop_layer(glide), ap_layer, loop_layer(mg)], name="Cluster")
    return ab


# ================================================================ Console (centre touchscreen)
MODE_CARDS = [("CRUISE", "62 KM/H  ·  CALM THROTTLE"), ("SPORT", "96 KM/H  ·  SHARP + LOW"), ("SKY LANE", "LIFT TO 26 M  ·  AIR TRAFFIC")]


def build_console(row_ab):
    W, H = 720, 960
    ab = surface_artboard("Console", W, H, 3300)
    anims, layers, lis = [], [], []
    # --- status bar --------------------------------------------------------
    bars = node("Signal", *[shape(f"S{k}", rect(5, 6 + k * 4, x=k * 8, y=-(6 + k * 4) / 2), solid(argb(WHITE if k < 3 else FAINT)))
                            for k in range(4)])
    status = box("Status",
                 orb("Clock", "23:47", 22, WHITE, bindname="clock"),
                 box("Sp", ws="fill", h=1, hs="fixed"),
                 orb("Model", "RIVE  R-1", 13, WHITE, ls=5),
                 box("Sp2", ws="fill", h=1, hs="fixed"),
                 inter("Temp", "17°C", 18, WHITE, 600, bindname="temp", dec=False),
                 art("Signal Box", bars, w=34, h=20),
                 dir="row", align="center", ws="fill", h=64, hs="fixed", pad=(0, 28, 0, 28), gap=14, bid=nid())
    # --- tabs ------------------------------------------------------------------
    tab_names = ["DRIVE", "MEDIA", "AMBIENT"]
    tab_boxes, tab_cids = [], []
    for k, nm in enumerate(tab_names):
        cid = nid()
        b = box(f"Tab {nm}", orb(f"Tab L{k}", nm, 15, WHITE, ls=3, cid=cid), ws="fill", hs="fill", align="center",
                extra={"flexBasis": 0, "flexBasisUnitsValue": "points"}, bid=nid(), fill=argb("#000000", 1))
        tab_boxes.append(b)
        tab_cids.append(cid)
        lis.append(set_listener(b.id, "tab", k, f"Tab {nm}"))
    ind = node("Indicator", shape("Ind", rect(120, 4, x=0, y=0, r=2), solid(argb(AMBER))), x=120, y=70)
    tabs = box("Tabs", layer("Tab Ind", art("Ind Art", ind)), layer("Tab Row", box("Row", *tab_boxes, dir="row", ws="fill", hs="fill")),
               ws="fill", h=76, hs="fixed", extra={"layoutTypeValue": "stack"}, bid=nid())
    tab_rule = box("Tab Rule", ws="fill", h=1, hs="fixed", fill=argb("#2A2A2E"))

    # --- DRIVE panel ------------------------------------------------------------
    cards, card_layers = [], []
    for k, (nm, sub) in enumerate(MODE_CARDS):
        tcid, rcid = nid(), nid()
        radio = node("Radio", shape("Ring", ellipse(26, 26), stroke(argb(FAINT), 2, cid=rcid)),
                     node("Fill Dot", shape("Dot", ellipse(14, 14), solid(argb(AMBER))), opacity=0))
        radio_dot = radio.children[1]
        c = box(f"Mode {nm}",
                mono("Idx", f"0{k + 1}", 13, FAINT, ls=2, dec=False),
                box("Col", orb("Name", nm, 24, WHITE, cid=tcid, ls=1), mono("Sub", sub, 11, MUTED, ls=1.5), gap=6,
                    ws="fill", extra={"flexBasis": 0, "flexBasisUnitsValue": "points"}),
                art("Radio Box", radio, w=30, h=30),
                dir="row", align="center", gap=18, pad=(0, 24, 0, 22), ws="fill", h=92, hs="fixed", radius=14,
                fill=argb(CARD), stroke=(argb("#2C2C31"), 1.5), bid=nid())
        scid = stroke_color_id(c)
        cards.append(c)
        lis.append(req_listener(c.id, 10 + k, f"Mode {nm}"))
        on = Anim(f"Mode {k} On", 16)
        on.color(scid, [(0, argb("#2C2C31")), (16, argb(AMBER))])
        on.color(tcid, [(0, argb(WHITE)), (16, argb(AMBER))])
        on.color(rcid, [(0, argb(FAINT)), (16, argb(AMBER))])
        on.key(radio_dot.id, 18, [(0, 0), (10, 1)])
        on.key(radio_dot.id, 16, [(0, 0.2), (16, 1, BACK_OUT)])
        on.key(radio_dot.id, 17, [(0, 0.2), (16, 1, BACK_OUT)])
        off = Anim(f"Mode {k} Off", 16)
        off.color(scid, [(0, argb(AMBER)), (16, argb("#2C2C31"))])
        off.color(tcid, [(0, argb(AMBER)), (16, argb(WHITE))])
        off.color(rcid, [(0, argb(AMBER)), (16, argb(FAINT))])
        off.key(radio_dot.id, 18, [(0, 1), (10, 0)])
        anims += [on, off]
        s_on, s_off = nid(), nid()
        card_layers.append(sm_layer(f"Mode {k}", s_off,
                                    state(off, go(s_on, cond("mode", k)), sid=s_off, x=200, y=0),
                                    state(on, go(s_off, cond("mode", k, "notEqual")), sid=s_on, x=420, y=0)))
    layers += card_layers

    def switch_row(name, sub, prop, code, labels=None, thr=0.5):
        tcid, kcid = nid(), nid()
        knob = node("Knob", shape("K", ellipse(28, 28), solid(argb(WHITE), cid=kcid)), x=-18, y=0)
        track = box("Track", art("Knob Art", knob, w=0, h=0), w=72, h=36, ws="fixed", hs="fixed", radius=18,
                    fill=argb("#3A3A40"), align="center", bid=nid())
        trk_cid = fill_color_id(track)
        lab = box("Labels", orb("L", name, 18, WHITE, ls=2, cid=tcid), mono("S", sub, 11, MUTED, ls=1.5), gap=5,
                  ws="fill", extra={"flexBasis": 0, "flexBasisUnitsValue": "points"})
        r = box(f"Row {name}", lab, track, dir="row", align="center", ws="fill", h=84, hs="fixed", pad=(0, 22, 0, 24),
                radius=14, fill=argb(CARD), gap=12, bid=nid())
        lis.append(req_listener(r.id, code, f"Toggle {name}"))
        on = Anim(f"{name} On", 16)
        on.key(knob.id, 13, [(0, -18), (16, 18, BACK_OUT)])
        on.color(trk_cid, [(0, argb("#3A3A40")), (16, argb(AMBER))])
        on.color(kcid, [(0, argb(WHITE)), (16, argb("#111111"))])
        off = Anim(f"{name} Off", 16)
        off.key(knob.id, 13, [(0, 18), (16, -18, BACK_OUT)])
        off.color(trk_cid, [(0, argb(AMBER)), (16, argb("#3A3A40"))])
        off.color(kcid, [(0, argb("#111111")), (16, argb(WHITE))])
        anims.extend([on, off])
        s_on, s_off = nid(), nid()
        layers.append(sm_layer(f"Switch {name}", s_off,
                               state(off, go(s_on, cond(prop, thr, "greaterThan")), sid=s_off, x=200, y=0),
                               state(on, go(s_off, cond(prop, thr, "lessThan")), sid=s_on, x=420, y=0)))
        return r

    def stat(label, bindname, unit):
        return box(f"Stat {label}", mono("L", label, 10, MUTED, ls=3),
                   box("V", orb("Val", "0", 26, WHITE, bindname=bindname), mono("U", unit, 11, MUTED), dir="row", align="bottomLeft", gap=6),
                   gap=6, ws="fill", extra={"flexBasis": 0, "flexBasisUnitsValue": "points"})
    stats = box("Stats", stat("BATTERY", "battery", "%"), stat("RANGE", "range", "KM"), stat("ALTITUDE", "alt", "M"),
                dir="row", ws="fill", pad=(10, 6, 0, 6))
    drive = box("Drive Panel",
                mono("K1", "// DRIVE MODE", 13, AMBER, ls=4), *cards, spacer(1, 4),
                switch_row("AUTOPILOT", "LANE  ·  SPEED  ·  ROUTE", "ap", 1),
                switch_row("CHASE CAM", "COCKPIT  /  THIRD PERSON", "view", 4),
                switch_row("NIGHT", "MERIDIAN AFTER DARK", "night", 3),
                stats,
                ws="fill", hs="fill", gap=12, pad=(24, 28, 0, 28), bid=nid())

    # --- MEDIA panel --------------------------------------------------------------
    eq = []
    for k in range(9):
        eq.append(node(f"EQ {k}", shape("B", rect(14, 80, x=0, y=-40, r=3), solid(argb(PRISM[k % 6]))), x=40 + k * 18, y=170))
    vinyl = node("Vinyl", shape("Ring1", ellipse(150, 150), stroke(argb("#2C2C31"), 2)),
                 shape("Ring2", ellipse(110, 110), stroke(argb("#2C2C31"), 2)),
                 shape("Notch", poly([(0, -75), (0, -55)]), stroke(argb(AMBER), 3)), x=110, y=92)
    cover = box("Cover", art("Cover Art", vinyl, *eq, w=220, h=220), w=220, h=220, ws="fixed", hs="fixed", radius=18, clip=True,
                grad=lgrad([(argb("#24161A"), 0), (argb("#0B0B10"), 1)], 0, 0, 220, 220))

    def icon_btn(name, pts_list, size=56, code=0, filled=False):
        shp = [shape(f"{name} {i}", poly(p, True), solid(argb(BLACK if filled else WHITE))) for i, p in enumerate(pts_list)]
        b = box(name, art(name + " Icon", *shp, w=0, h=0), w=size, h=size, ws="fixed", hs="fixed", radius=size / 2, align="center",
                fill=argb(AMBER) if filled else argb("#232327"), bid=nid())
        lis.append(req_listener(b.id, code, name))
        return b
    prev_b = icon_btn("Prev", [[(6, -9), (-6, 0), (6, 9)], [(-8, -9), (-5, -9), (-5, 9), (-8, 9)]], 52, 42)
    play_pts = [(-6, -11), (11, 0), (-6, 11)]
    pause_pts = [[(-8, -10), (-2, -10), (-2, 10), (-8, 10)], [(2, -10), (8, -10), (8, 10), (2, 10)]]
    pp_play = node("PP Play", shape("T", poly(play_pts, True), solid(argb(BLACK))), opacity=0)
    pp_pause = node("PP Pause", *[shape(f"P{i}", poly(p, True), solid(argb(BLACK))) for i, p in enumerate(pause_pts)])
    play_b = box("Play", art("Play Icon", pp_play, pp_pause, w=0, h=0), w=68, h=68, ws="fixed", hs="fixed", radius=34,
                 align="center", fill=argb(AMBER), bid=nid())
    lis.append(req_listener(play_b.id, 40, "Play Pause"))
    next_b = icon_btn("Next", [[(-6, -9), (6, 0), (-6, 9)], [(8, -9), (5, -9), (5, 9), (8, 9)]], 52, 41)
    controls = box("Controls", prev_b, play_b, next_b, dir="row", align="center", gap=18)
    prog = art("Progress", shape("Fill", poly([(0, 2), (380, 2)]), stroke(argb(AMBER), 4, "round", trim("progress"))),
               shape("Track", poly([(0, 2), (380, 2)]), stroke(argb(TRACK), 4, "round")), w=380, h=4)
    np = box("Now Playing", cover,
             box("NP Text", mono("K2", "NOW PLAYING", 12, AMBER, ls=4),
                 orb("Title", "AFTERBURN", 24, WHITE, bindname="trackTitle"),
                 mono("Artist", "ROCKET SQUADRON OST", 12, MUTED, bindname="trackArtist", ls=1.5),
                 spacer(1, 14), prog, spacer(1, 2), mono("Time", "0:00 / 2:58", 11, MUTED, bindname="trackTime"),
                 spacer(1, 12), controls,
                 gap=6, ws="fill", extra={"flexBasis": 0, "flexBasisUnitsValue": "points"}),
             dir="row", gap=22, ws="fill", align="topLeft")
    lst = E("ArtboardComponentList", bind("tracks", 800), name="Rows", id=nid())
    physics = E("ElasticScrollPhysics", friction=3, speedMultiplier=1.2, elasticFactor=0.7, name="Physics", id=nid())
    ab.add(physics)
    scroll_body = box("Scroll Body", E("ScrollConstraint", directionValue="vertical", physicsId=physics.id, name="Scroll"),
                      box("List Box", lst, gap=4),
                      spacer(1, 30), ws="hug", hs="hug", bid=nid())
    viewport = box("Queue", scroll_body, w=664, h=416, ws="fixed", hs="fixed", clip=True)
    media = box("Media Panel", np, spacer(1, 6), mono("K3", "// QUEUE", 13, AMBER, ls=4), viewport,
                ws="fill", hs="fill", gap=12, pad=(26, 28, 0, 28), bid=nid())
    eq_anim = Anim("EQ", 120, "loop")
    import random as _r
    rr = _r.Random(3)
    for k, e in enumerate(eq):
        fr = [(0, 0.3)]
        for f in range(12, 121, 12):
            fr.append((f, rr.uniform(0.15, 1.0) if f < 120 else 0.3))
        eq_anim.key(e.id, 17, fr)
    vin = Anim("Vinyl", 240, "loop")
    vin.key(vinyl.id, 15, [(0, 0, "linear"), (240, 6.2831853, "linear")])
    pp_on = Anim("Playing", 8)
    pp_on.key(pp_play.id, 18, [(0, 1), (8, 0)])
    pp_on.key(pp_pause.id, 18, [(0, 0), (8, 1)])
    pp_off = Anim("Paused", 8)
    pp_off.key(pp_play.id, 18, [(0, 0), (8, 1)])
    pp_off.key(pp_pause.id, 18, [(0, 1), (8, 0)])
    anims += [eq_anim, vin, pp_on, pp_off]
    s_p, s_q = nid(), nid()
    layers.append(sm_layer("Play State", s_p,
                           state(pp_on, go(s_q, cond("playing", 0.5, "lessThan")), sid=s_p, x=200, y=0),
                           state(pp_off, go(s_p, cond("playing", 0.5, "greaterThan")), sid=s_q, x=420, y=0)))
    s_e1, s_e2 = nid(), nid()
    eq_idle = Anim("EQ Idle", 1)
    for e in eq:
        eq_idle.hold(e.id, 17, 0.12)
    anims.append(eq_idle)
    layers.append(sm_layer("EQ", s_e1,
                           state(eq_anim, go(s_e2, cond("playing", 0.5, "lessThan"), ms=200), sid=s_e1, x=200, y=0),
                           state(eq_idle, go(s_e1, cond("playing", 0.5, "greaterThan"), ms=200), sid=s_e2, x=420, y=0)))
    layers.append(loop_layer(vin))

    # --- AMBIENT panel ----------------------------------------------------------------
    ring_cid, glow_cid = nid(), nid()
    orb_cids = [nid(), nid(), nid()]
    ring = node("Ring", shape("Glow", ellipse(300, 300), stroke(argb(AMBER, 60), 40, cid=glow_cid)),
                shape("R", ellipse(300, 300), stroke(argb(AMBER), 10, cid=ring_cid)), x=0, y=0)

    def seg_arc(r, a0, a1, n=10):
        return [(r * math.cos(a0 + (a1 - a0) * i / n), r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    # thick rounded arc segments (no hairlines: they shimmer when the canvas is minified on the 3D screen)
    spin = node("Spin", shape("Segs", *[poly(seg_arc(176, k * math.pi / 6 + 0.1, (k + 1) * math.pi / 6 - 0.1)) for k in range(12)],
                              stroke(argb("#34343C"), 8, "round")))
    spin2 = node("Spin2", shape("Segs2", *[poly(seg_arc(198, k * math.pi / 3 + 0.3, k * math.pi / 3 + 0.75)) for k in range(6)],
                                stroke(argb(AMBER, 150), 6, "round", cid=orb_cids[2])))
    mood = node("Mood", shape("O1", ellipse(250, 250), solid(argb(AMBER, 40), cid=orb_cids[0])),
                shape("O2", ellipse(170, 170), solid(argb(AMBER, 70), cid=orb_cids[1])))
    sparks = node("Sparks", *[shape(f"P{k}", ellipse(10, 10), solid(argb(WHITE, 200)), x=150 * math.cos(k * 1.047), y=150 * math.sin(k * 1.047))
                              for k in range(6)])
    preview = box("Preview", art("Preview Art", spin2, spin, sparks, ring, mood, w=0, h=0),
                  layer("Preview Text", box("PT", mono("Lk", "CABIN", 12, MUTED, ls=5), orb("Amb Name", "AMBER", 34, WHITE, bindname="ambName"),
                                            align="center", gap=6)),
                  ws="fill", h=380, hs="fixed", align="center", extra={"layoutTypeValue": "stack"})
    sw_rows = []
    sw_boxes = []
    sel_nodes = []
    for k, col in enumerate(AMB):
        seln = node("Sel", shape("SR", ellipse(80, 80), stroke(argb(WHITE), 3)), opacity=0)
        sel_nodes.append(seln)
        b = box(f"Swatch {k}", art("Sw Art", seln, shape("C", ellipse(60, 60), solid(argb(col))), w=0, h=0),
                w=96, h=96, ws="fixed", hs="fixed", align="center", bid=nid(), fill=argb("#000000", 1))
        sw_boxes.append(b)
        lis.append(req_listener(b.id, 50 + k, f"Ambient {k}"))
    sw_rows.append(box("Sw Row 1", *sw_boxes[:3], dir="row", gap=40, align="center"))
    sw_rows.append(box("Sw Row 2", *sw_boxes[3:], dir="row", gap=40, align="center"))
    ambient = box("Ambient Panel", mono("K4", "// CABIN LIGHT", 13, AMBER, ls=4), preview, *sw_rows, spacer(1, 14),
                  box("Note", mono("N1", "PICK A COLOUR  ·  THE 3D CABIN RELIGHTS LIVE", 11, MUTED, ls=1.5), ws="fill", align="center"),
                  ws="fill", hs="fill", gap=18, pad=(24, 28, 0, 28), align="topCenter", bid=nid())
    for k, col in enumerate(AMB):
        a = Anim(f"Amb {k}", 18)
        a.color(ring_cid, [(0, argb(col)), (18, argb(col))])
        a.color(glow_cid, [(0, argb(col, 60)), (18, argb(col, 60))])
        a.color(orb_cids[0], [(0, argb(col, 40)), (18, argb(col, 40))])
        a.color(orb_cids[1], [(0, argb(col, 70)), (18, argb(col, 70))])
        a.color(orb_cids[2], [(0, argb(col, 150)), (18, argb(col, 150))])
        for j, sn in enumerate(sel_nodes):
            if j == k:
                a.key(sn.id, 18, [(0, 0), (12, 1)])
                a.key(sn.id, 16, [(0, 0.6), (18, 1, BACK_OUT)])
                a.key(sn.id, 17, [(0, 0.6), (18, 1, BACK_OUT)])
            else:
                a.hold(sn.id, 18, 0)
        a.key(ring.id, 16, [(0, 0.9), (18, 1, BACK_OUT)])
        a.key(ring.id, 17, [(0, 0.9), (18, 1, BACK_OUT)])
        anims.append(a)
    amb_states = [nid() for _ in AMB]
    layers.append(sm_layer("Ambient", amb_states[0], *[
        state(anims[-6 + k], *[go(amb_states[j], cond("ambient", j), ms=0) for j in range(6) if j != k], sid=amb_states[k],
              x=200 + 200 * k, y=0) for k in range(6)]))
    sp = Anim("Spin", 600, "loop")
    sp.key(spin.id, 15, [(0, 0, "linear"), (600, 6.2831853, "linear")])
    sp.key(spin2.id, 15, [(0, 0, "linear"), (600, -12.566371, "linear")])
    sp.key(sparks.id, 15, [(0, 0, "linear"), (600, 6.2831853 * 3, "linear")])
    for k in range(4):
        sp.key(mood.id, 16, [(0, 0.92), (75, 1.08), (150, 0.92), (225, 1.08), (300, 0.92), (375, 1.08), (450, 0.92), (525, 1.08), (600, 0.92)])
        sp.key(mood.id, 17, [(0, 0.92), (75, 1.08), (150, 0.92), (225, 1.08), (300, 0.92), (375, 1.08), (450, 0.92), (525, 1.08), (600, 0.92)])
        break
    anims.append(sp)
    layers.append(loop_layer(sp))

    # --- panels + tabs state -------------------------------------------------------------
    panels = [drive, media, ambient]
    stack = box("Panels", *reversed(panels), ws="fill", hs="fill", extra={"layoutTypeValue": "stack"}, bid=nid())
    tab_states = [nid() for _ in panels]
    for k in range(3):
        a = Anim(f"Tab {k}", 22)
        for j, pn in enumerate(panels):
            if j == k:
                a.key(pn.id, 18, [(0, 0), (16, 1)])
                a.key(pn.id, 13, [(0, 40), (22, 0, EASE_OUT)])
            else:
                a.key(pn.id, 18, [(0, 0, "hold")])
                a.key(pn.id, 13, [(0, -1200, "hold")])
            a.color(tab_cids[j], [(0, argb(AMBER if j == k else MUTED)), (10, argb(AMBER if j == k else MUTED))])
        a.key(ind.id, 13, [(0, 120 + 240 * k - 30 * (1 if k > 0 else 0)), (18, 120 + 240 * k, BACK_OUT)])
        anims.append(a)
    tab_anims = anims[-3:]
    layers.append(sm_layer("Tabs", tab_states[0], *[
        state(tab_anims[k], *[go(tab_states[j], cond("tab", j)) for j in range(3) if j != k], sid=tab_states[k], x=200 + 220 * k, y=200)
        for k in range(3)]))

    root = box("Root", status, tabs, tab_rule, stack, ws="fill", hs="fill", bid=nid(),
               grad=lgrad([(argb("#101013"), 0), (argb("#060608"), 1)], 0, 0, 0, H))
    ab.add(root)
    # intro
    intro = Anim("Intro", 70)
    intro.key(status.id, 18, [(0, 0, "hold"), (2, 0), (18, 1)])
    intro.key(status.id, 14, [(2, -50), (24, 0, EASE_OUT)])
    intro.key(tabs.id, 18, [(0, 0, "hold"), (10, 0), (26, 1)])
    intro.key(tab_rule.id, 18, [(0, 0, "hold"), (14, 0), (30, 1)])
    intro.key(stack.id, 18, [(0, 0, "hold"), (20, 0), (40, 1)])
    intro.key(stack.id, 14, [(20, 60), (48, 0, EASE_OUT)])
    off = Anim("Off", 1)
    for i in (status.id, tabs.id, tab_rule.id, stack.id):
        off.hold(i, 18, 0)
    anims += [intro, off]
    for a in anims:
        ab.add(a.el)
    finish_sm(ab, [boot_layer(ab, "bootCs", intro, off)] + layers, lis, name="Console")
    return ab


# ================================================================ Hub (yoke)
def build_hub():
    """Yoke hub: layout-centred stack (face, rings, content), motion on nodes."""
    W = 320
    c = W / 2
    ab = surface_artboard("Hub", W, W, 4200)
    # content column: kicker, RIVE logo (box = scaled artboard size), mode label
    logo_box = box("Logo Box", node("Logo", E("NestedArtboard", E("NestedStateMachine", animationId=LOGO_SM, name="Logo SM"),
                                              artboardId=LOGO_AB, name="Hub Logo", x=0, y=0, scaleX=0.24, scaleY=0.24,
                                              dataBindPathIds=path("logoHub"), id=nid())),
                   w=192, h=96, ws="fixed", hs="fixed")
    label = text("AP L", "AUTOPILOT", 13, AMBER, F_MONO, bindname="apLabel", ls=3)
    kick = text("Kick", "R-1  ::  HUB", 10, FAINT, F_MONO, ls=3, dec=False)
    content = box("Content", kick, logo_box, label, gap=2, align="center")
    content_l = box("Content L", content, ws="fill", hs="fill", align="center")
    # rings: drawn around the anchor's centre
    def arc(r, a0, a1, n=18):
        return [(r * math.cos(a0 + (a1 - a0) * i / n), r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    dashes = node("Dashes", shape("D", *[poly([(146 * math.cos(a), 146 * math.sin(a)), (156 * math.cos(a), 156 * math.sin(a))])
                                         for a in [k * math.pi / 12 for k in range(24)]], stroke(argb("#4A4A52"), 5, "butt")))
    prism = node("Prism Arcs", *[shape(f"A{k}", poly(arc(132, k * math.pi / 3 + 0.12, (k + 1) * math.pi / 3 - 0.12)),
                                       stroke(argb(PRISM[k]), 4, "butt")) for k in range(6)])
    ap_ring = node("AP Ring", shape("A", ellipse(250, 250), stroke(argb(AMBER), 4)), binds=(bind("ap", 18),))
    sweep = node("Sweep", shape("S", poly(arc(118, -0.5, 0.5, 12)), stroke(argb(WHITE, 200), 3, "round")))
    pulse = node("Pulse", shape("P", ellipse(232, 232), stroke(argb(AMBER, 90), 2)))
    rings = anchor_c("Rings", W, dashes, prism, ap_ring, sweep, pulse)
    face = node("Face", shape("Disc", ellipse(W, W), rgrad([(argb("#1C1C22"), 0), (argb("#060608"), 1)], 0, -60, 0, 200)),
                shape("Rim", ellipse(W - 6, W - 6), stroke(argb("#2A2A30"), 3)))
    face_l = anchor_c("Face", W, face)
    root = box("Root", content_l, rings, face_l, ws="fill", hs="fill", extra={"layoutTypeValue": "stack"})
    ab.add(root)
    intro = Anim("Intro", 50)
    intro.key(content.id, 18, [(0, 0), (24, 1)])
    intro.key(dashes.id, 15, [(0, -3.0), (40, 0, EASE_OUT)])
    intro.key(dashes.id, 18, [(0, 0), (12, 1)])
    intro.key(prism.id, 18, [(0, 0, "hold"), (14, 0), (34, 1)])
    intro.key(prism.id, 16, [(0, 0.6, "hold"), (14, 0.6), (40, 1, BACK_OUT)])
    intro.key(prism.id, 17, [(0, 0.6, "hold"), (14, 0.6), (40, 1, BACK_OUT)])
    off = Anim("Off", 1)
    for n_ in (content, dashes, prism, sweep, pulse):
        off.hold(n_.id, 18, 0)
    rot = Anim("Rotate", 900, "loop")
    rot.key(dashes.id, 15, [(0, 0, "linear"), (900, 6.2831853, "linear")])
    rot.key(prism.id, 15, [(0, 0, "linear"), (900, -6.2831853, "linear")])
    sw = Anim("Sweep", 150, "loop")
    sw.key(sweep.id, 15, [(0, 0, "linear"), (150, 6.2831853, "linear")])
    sw.key(pulse.id, 16, [(0, 0.9), (75, 1.08), (150, 0.9)])
    sw.key(pulse.id, 17, [(0, 0.9), (75, 1.08), (150, 0.9)])
    sw.key(pulse.id, 18, [(0, 1), (75, 0.2), (150, 1)])
    for a in (intro, off, rot, sw):
        ab.add(a.el)
    finish_sm(ab, [boot_layer(ab, "bootHub", intro, off), loop_layer(rot), loop_layer(sw)], name="Hub")
    return ab


def anchor_c(name, W, *nodes):
    """full-size layer whose nodes are centred on the artboard (layout-placed)"""
    return box(name, box(name + " A", node(name + " Art", *nodes), w=0, h=0, ws="fixed", hs="fixed", clip=False),
               ws="fill", hs="fill", align="center")


# ================================================================ HUD (windshield)

# ---------------------------------------------------------------- vehicle trackers (HUD)
CYAN = "#19F2FF"
RED = "#FF3B30"


def abs_box(name, *children, lx=None, ly=None, x=0, y=0, op=None, **kw):
    """absolutely-positioned layout (out of the parent's flex flow). lx/ly: view-model numbers
    bound to positionLeft/positionTop, so the script can place it in artboard pixels."""
    ex = dict(kw.pop("extra", {}) or {})
    ex.update(positionTypeValue="absolute", positionLeft=x, positionTop=y)
    lc = box(name, *children, extra=ex, binds=((bind(op, 18),) if op else ()), **kw)
    st = lc.children[0]
    if lx:
        st.add(bind(lx, 516))
    if ly:
        st.add(bind(ly, 518))
    return lc


# HUD layout constants -- mirrored in world 4_sim (declutter solver)
TRK_W, TRK_H, TRK_CLOS_H = 156, 96, 14
MK_W, MK_H = 190, 44
RO_W, RO_SIDE, RO_MID, RO_Y, RO_GAP = 660, 200, 260, 559, 36


def build_trackers():
    """GMUNK-style lock-on trackers for nearby traffic: counter-rotating
    segmented rings, diamond ticks, leader line + data block (id, class,
    distance, closing speed bar, time-to-contact). Cyan, cross-fading to red
    as a vehicle closes in. Position/scale/opacity/strings from the script."""
    roots, anims, layers, blocks = [], [], [], []
    for k in range(1, 5):
        def ring_set(col, opb):
            segs = []
            for q in range(8):
                a0 = q * math.pi / 4 + 0.09
                segs.append(poly(arc_pts(0, 0, 34, a0, a0 + math.pi / 4 - 0.18, 6)))
            ra = node("Ring A", shape("RA", *segs, stroke(argb(col, 220), 2.2, "butt")))
            segs2 = []
            for q in range(3):
                a0 = q * 2 * math.pi / 3
                segs2.append(poly(arc_pts(0, 0, 44, a0, a0 + 1.2, 10)))
            rb = node("Ring B", shape("RB", *segs2, stroke(argb(col, 140), 1.2, "butt")))
            ticks = []
            for q in range(4):
                a = q * math.pi / 2
                cxq, cyq = 52 * math.cos(a), 52 * math.sin(a)
                ticks.append(poly([(cxq + 4 * math.cos(a + 1.57), cyq + 4 * math.sin(a + 1.57)), (cxq + 6 * math.cos(a), cyq + 6 * math.sin(a)),
                                   (cxq - 4 * math.cos(a + 1.57), cyq - 4 * math.sin(a + 1.57)), (cxq - 2 * math.cos(a), cyq - 2 * math.sin(a))], True))
            tk = node("Ticks", shape("T", *ticks, solid(argb(col, 230))))
            pip = shape("Pip", ellipse(5, 5), solid(argb(col)))
            cross = shape("Cross", poly([(-12, 0), (-6, 0)]), poly([(6, 0), (12, 0)]), poly([(0, -12), (0, -6)]), poly([(0, 6), (0, 12)]),
                          stroke(argb(col, 200), 1.2, "butt"))
            return node("Rings", rb, ra, tk, pip, cross, binds=(bind(opb, 18),)), ra, rb, tk
        rn, ra, rb, tk = ring_set(CYAN, f"t{k}n")
        rr, ra2, rb2, tk2 = ring_set(RED, f"t{k}r")
        reticle = node("Reticle", rn, rr)
        # leader (flips per quadrant) + data block (a layout, placed by the declutter solver)
        lead = node("Lead Flip", shape("Lead", poly([(40, -40), (62, -62)]), stroke(argb(WHITE, 160), 1.0, "butt")),
                    binds=(bind(f"t{k}fx", 16), bind(f"t{k}fy", 17)))
        TW = TRK_W
        hdr = box("Hdr", box("HL", mono("Kick", "TRK // LOCK", 8, CYAN, ls=3, dec=False), ws="fill"),
                  mono("Hx", "0x0000", 8, MUTED, bindname=f"t{k}hx", ls=1.5), dir="row", ws="fill", align="centerLeft")
        idr = box("IdRow", box("IL", orb("Id", "HX-0000", 15, WHITE, bindname=f"t{k}id", ls=1), ws="fill"),
                  mono("Cl", "SEDAN", 8, CYAN, bindname=f"t{k}cl", ls=2), dir="row", ws="fill", align="centerLeft")
        rule = box("Rule", w=TW, h=1, ws="fixed", hs="fixed", fill=argb(WHITE, 70))
        dist = box("Dist", orb("D", "00.0", 20, WHITE, bindname=f"t{k}d"), mono("Du", "M", 8, CYAN, ls=2, dec=False),
                   dir="row", align="bottomLeft", gap=5)
        vel = box("Vel", mono("V", "+00", 9, WHITE, bindname=f"t{k}v", ls=1), mono("Tt", "TTC --.-", 8, MUTED, bindname=f"t{k}tt", ls=1.5),
                  align="topRight", gap=3)
        drow = box("DRow", box("DL", dist, ws="fill"), vel, dir="row", ws="fill", align="centerLeft")
        clos = anchor("Closing", shape("Clos", poly([(0, 2), (TW, 2)]), stroke(argb(CYAN), 3, "butt", trim(f"t{k}c"))),
                      shape("ClosT", poly([(0, 2), (TW, 2)]), stroke(argb(WHITE, 45), 3, "butt")),
                      *[shape(f"Sc{q}", poly([(q * TW / 10, 6), (q * TW / 10, 9 if q % 5 else 12)]), stroke(argb(WHITE, 90), 1, "butt"))
                        for q in range(11)], w=TW, h=TRK_CLOS_H)
        lay = abs_box(f"Tracker {k} Block", hdr, idr, rule, drow, clos, w=TW, h=TRK_H, ws="fixed", hs="fixed", gap=4,
                      lx=f"t{k}lx", ly=f"t{k}ly", op=f"t{k}lo", x=-600, y=-600)
        blocks.append(lay)
        data = node("Data", lead)
        inner = node("Inner", data, reticle)
        root = node(f"Tracker {k}", inner,
                    binds=(bind(f"t{k}x", 13), bind(f"t{k}y", 14), bind(f"t{k}s", 16), bind(f"t{k}s", 17), bind(f"t{k}op", 18)))
        roots.append(root)
        # lock-on: rings collapse in spinning, data block slides in
        lock = Anim(f"Lock {k}", 34)
        lock.key(reticle.id, 16, [(0, 2.4), (22, 1, EASE_OUT)])
        lock.key(reticle.id, 17, [(0, 2.4), (22, 1, EASE_OUT)])
        lock.key(reticle.id, 15, [(0, -1.6), (26, 0, EASE_OUT)])
        lock.key(data.id, 18, [(0, 0, "hold"), (12, 0), (24, 1)])
        idle = Anim(f"Unlock {k}", 1)
        idle.hold(reticle.id, 16, 2.4)
        idle.hold(reticle.id, 17, 2.4)
        idle.hold(data.id, 18, 0)
        spin = Anim(f"Spin {k}", 360, "loop")
        for a_, rate in ((ra, 1), (ra2, 1), (rb, -2), (rb2, -2)):
            spin.key(a_.id, 15, [(0, 0, "linear"), (360, rate * 6.2831853, "linear")])
        for t_ in (tk, tk2):
            spin.key(t_.id, 16, [(0, 1), (30, 1.12), (60, 1), (360, 1)])
            spin.key(t_.id, 17, [(0, 1), (30, 1.12), (60, 1), (360, 1)])
        anims += [lock, idle, spin]
        s_i, s_l = nid(), nid()
        layers.append(sm_layer(f"Track {k}", s_i,
                               state(idle, go(s_l, cond(f"t{k}op", 0.6, "greaterThan")), sid=s_i, x=200, y=0),
                               state(lock, go(s_i, cond(f"t{k}op", 0.05, "lessThan")), sid=s_l, x=420, y=0)))
        layers.append(loop_layer(spin))
    return roots, anims, layers, blocks


def build_hud():
    W, H = 2000, 1240
    ab = surface_artboard("HUD", W, H, 4700)
    cx = 600   # in front of the driver (the HUD patch is centred on the car)
    hy = 617   # eye-level horizon on the glass (see make_props T0/T1)
    A_ = AMBER
    # horizon / pitch ladder
    lad = []
    for sgn in (-1, 1):
        lad.append(poly([(cx + sgn * 50, hy), (cx + sgn * 170, hy)]))
        lad.append(poly([(cx + sgn * 170, hy), (cx + sgn * 170, hy + 7)]))
    for k in range(-2, 3):
        if k == 0:
            continue
        lad.append(poly([(cx + k * 40, hy - 4), (cx + k * 40, hy + 4)]))
    horizon = node("Horizon", shape("Lad", *lad, stroke(argb(WHITE, 120), 1.5, "butt")),
                   shape("Bore", poly([(cx - 14, hy + 7), (cx, hy), (cx + 14, hy + 7)]), stroke(argb(A_), 2.5, "round")))
    # ---- readout cluster: ONE layout (warning row / horizon gap / nav | speed | mode+alt), so nothing
    # in it can collide whatever the strings are. Columns are fixed width; speed stays centred.
    brk = lambda nm, pts: anchor(nm, shape("B", poly(pts), stroke(argb(A_), 2, "butt")), w=10, h=30)
    warn = box("Warn", brk("BrL", [(10, 0), (0, 0), (0, 30), (10, 30)]),
               orb("W", "SYSTEMS ONLINE", 15, A_, bindname="warn", ls=3),
               brk("BrR", [(0, 0), (10, 0), (10, 30), (0, 30)]), dir="row", align="center", gap=14, binds=(bind("warnOp", 18),))
    warn_row = box("Warn Row", warn, w=RO_W, h=30, ws="fixed", hs="fixed", align="center")
    arrow = anchor("Arrow A", node("Arrow Flip", node("Arrow", shape("Stem", poly([(-9, 17), (-9, -3), (8, -3)]), stroke(argb(A_), 4.5, "round")),
                                                   shape("Head", poly([(6, -13), (17, -3), (6, 7)], True), solid(argb(A_)))),
                                   binds=(bind("navTurn", 16),), x=15, y=17), w=30, h=34)
    navc = box("Nav", arrow, box("NavT", orb("Nd", "420 M", 22, WHITE, bindname="navDist"), mono("Ns", "AURORA ST", 9, A_, bindname="navStreet", ls=2), gap=3),
               w=RO_SIDE, ws="fixed", dir="row", align="centerRight", gap=10)
    spdc = box("Speed", orb("Spd", "0", 54, WHITE, bindname="speed"), mono("Unit", "KM/H", 11, A_, ls=4, dec=False),
               w=RO_MID, ws="fixed", align="topCenter", gap=0)
    tape = anchor("Alt Tape", shape("T", poly([(0, 3), (110, 3)]), stroke(argb(WHITE, 90), 2, "butt")),
                  shape("F", poly([(0, 3), (110, 3)]), stroke(argb("#19F2FF"), 3, "butt", trim("altFrac"))), w=110, h=6)
    altr = box("AltRow", mono("AltL", "ALT", 8, A_, ls=3, dec=False), orb("Alt", "0.6", 15, WHITE, bindname="alt"),
               mono("AltM", "M", 8, A_, dec=False), dir="row", align="bottomLeft", gap=6)
    rightc = box("Right", orb("Mode", "CRUISE", 13, WHITE, bindname="modeName", ls=2), altr, tape,
                 w=RO_SIDE, ws="fixed", align="centerLeft", gap=5)
    main_row = box("Main Row", navc, spdc, rightc, w=RO_W, ws="fixed", dir="row", align="topCenter")
    readout = box("Readout", warn_row, box("Horizon Gap", w=RO_W, h=RO_GAP, ws="fixed", hs="fixed"), main_row,
                  w=RO_W, ws="fixed", align="topCenter")
    ro_root = abs_box("Readout Root", readout, x=cx - RO_W // 2, y=RO_Y)
    # ---- AR markers: brackets on the target, leader flips per quadrant, label is a layout block
    markers, labels = [], []
    for k in (1, 2, 3):
        L = 16
        corners = []
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append(poly([(sx * 26, sy * 26 - sy * L), (sx * 26, sy * 26), (sx * 26 - sx * L, sy * 26)]))
        lab = abs_box(f"Marker {k} Label", orb("Mt", "BILLBOARD", 13, WHITE, bindname=f"m{k}t", ls=1),
                      mono("Md", "120 M", 9, A_, bindname=f"m{k}d", ls=2),
                      box("Rule", w=MK_W, h=1, ws="fixed", hs="fixed", fill=argb(WHITE, 150)),
                      w=MK_W, h=MK_H, ws="fixed", hs="fixed", gap=4, align="bottomLeft",
                      lx=f"m{k}lx", ly=f"m{k}ly", op=f"m{k}lo", x=-600, y=-600)
        labels.append(lab)
        m = node(f"Marker {k}",
                 node("Brackets", shape("Br", *corners, stroke(argb(A_), 2, "butt"))),
                 node("Lead Flip", shape("Lead", poly([(26, -26), (46, -46)]), stroke(argb(WHITE, 170), 1.2, "butt")),
                      binds=(bind(f"m{k}fx", 16), bind(f"m{k}fy", 17))),
                 binds=(bind(f"m{k}x", 13), bind(f"m{k}y", 14), bind(f"m{k}op", 18)))
        markers.append(m)
    trk_roots, trk_anims, trk_layers, trk_blocks = build_trackers()
    ab.add(*trk_blocks, *labels, *trk_roots, *markers, ro_root, horizon)
    br = Anim("Bracket Breathe", 90, "loop")
    for m in markers:
        brn = m.children[3]  # first child after binds is Brackets node
        br.key(brn.id, 16, [(0, 1), (45, 1.12), (90, 1)])
        br.key(brn.id, 17, [(0, 1), (45, 1.12), (90, 1)])
    ab.add(br.el, *[a.el for a in trk_anims])
    finish_sm(ab, [loop_layer(br)] + trk_layers, name="HUD")
    return ab



# ================================================================ title visor (texture for the camera-centred cylinder bands)
# The visor is the inside of a 150 deg cylinder around the camera (r 4 m): ~2.5 texture px per screen
# px at the centre, so sizes below are 2.5x their on-screen size. Visible u ~ 0.2 .. 0.8.
# Regions (mirrored in make_city.py visor meshes + world 4_sim):
TT_W, TT_H = 5120, 640
TT_TOP = (0, 120)               # top band (brow): v 0 .. 120/512
TT_BOT = (160, 400)             # bottom band (button): v 160/512 .. 400/512
TT_PANEL = 820                  # bottom button panel width (px) -> smoked backing window


def build_title_fui():
    W, H = TT_W, TT_H
    ab = surface_artboard("Title FUI", W, H, 12000, bg=None)
    CY_ = "#19F2FF"
    A_ = AMBER
    cx = W / 2
    # ======================= top band: heading tape + sector labels joined by a hairline
    TH = TT_TOP[1] - TT_TOP[0]
    ly = 64
    hair = node("Hair", shape("HL", poly([(0, ly), (cx - 330, ly)]), stroke(argb(WHITE, 80), 2, "butt")),
                shape("HR", poly([(cx + 330, ly), (W, ly)]), stroke(argb(WHITE, 80), 2, "butt")), x=cx, y=0)
    hair_in = node("Hair In", hair, x=-cx)
    # heading tape (centre, scrolls) + caret
    tape_ticks = [shape(f"Hk{q}", poly([(q * 20, 40), (q * 20, 40 - (22 if q % 5 == 0 else 10))]), stroke(argb(WHITE, 210 if q % 5 == 0 else 120), 2, "butt"))
                  for q in range(70)]
    tape_lbl = [NT(f"Hn{q}", f"{(q * 5) % 360:03d}", 18, WHITE, F_MONO, q * 100, 8, ox=0.5, ls=2) for q in range(14)]
    tape = node("Tape", *tape_ticks, *tape_lbl, x=0, y=0)
    tape_a = box("Tape Box", anchor("Tape A", tape, w=600, h=46), w=600, h=46, ws="fixed", hs="fixed", clip=True)
    caret = anchor("Caret", shape("C", poly([(-10, 0), (10, 0), (0, 14)], True), solid(argb(A_))), w=0, h=14)
    head = box("Heading", tape_a, box("Caret Row", node("Caret N", caret.children[-1], x=0, y=0) if False else caret, w=600, h=14, ws="fixed",
                                     hs="fixed", align="center"), gap=4, align="topCenter")
    hdg_n = mono("Hdg", "HDG 047  ·  ALT 235 M", 18, A_, ls=4, dec=False)
    centre_top = box("Top C", head, hdg_n, gap=6, align="topCenter", w=660, ws="fixed")
    def label_block(name, title_s, sub_s, col, align):
        t_ = mono(name + "T", title_s, 26, WHITE, ls=7, dec=False)
        s_ = mono(name + "S", sub_s, 18, col, ls=4, dec=False)
        return box(name, t_, s_, gap=6, align=align, w=700, ws="fixed"), t_, s_
    lb, lt, ls_ = label_block("TL", "MERIDIAN  //  SECTOR 07", "GRID 47.19 / 88.02   ·   HAZE 0.42", CY_, "topRight")
    rb, rt_, rs_ = label_block("TR", "ENTRY SEQUENCE  /  01", "AUTOPILOT STANDBY   ·   LANE 140", A_, "topLeft")
    top_row = box("Top Row", box("LbDim", lb, opacity=0.6), box("Gap1", w=330, h=1, ws="fixed", hs="fixed"),
                  box("CtDim", centre_top, opacity=0.55), box("Gap2", w=330, h=1, ws="fixed", hs="fixed"), box("RbDim", rb, opacity=0.6),
                  dir="row", align="topCenter", w=W, ws="fixed", pad=(76, 0, 0, 0))
    top = stack("Top Band", top_row, anchor("Hair L", hair_in, w=W, h=TH), w=W, h=TH, ws="fixed", hs="fixed")
    # ======================= bottom band: button panel (centre) + rulers / readouts to the edges
    BH = TT_BOT[1] - TT_BOT[0]
    PW = TT_PANEL
    ret_ring = node("Ret Ring", shape("Rg", *[poly(arc_pts(0, 0, 17, q * math.pi / 2 + 0.2, q * math.pi / 2 + 1.37, 6)) for q in range(4)],
                                     stroke(argb(WHITE, 220), 2, "butt")))
    ret_sq = node("Ret Sq", shape("Sq", rect(18, 18, x=0, y=0), stroke(argb(A_), 3, "butt")), rot=0.785398)
    ret = node("Ret", ret_ring, ret_sq, shape("Dot", ellipse(5, 5), solid(argb(A_))), x=20, y=20)
    reticle = anchor("Reticle", ret, w=40, h=40)
    chevs = [shape(f"Chev{q}", poly([(q * 16, 8), (q * 16 + 10, 20), (q * 16, 32)]), stroke(argb(A_), 3.5, "butt")) for q in range(3)]
    chev_a = anchor("Chevrons", *chevs, w=44, h=40)
    word = orb("Enter", "ENTER THE CITY", 46, WHITE, ls=14)
    # button: content row with real layout padding; the four bracket corners are layout children of
    # a stack that hugs that row, so the frame always sits exactly the padding away from the text
    main_row = box("Enter Row", reticle, word, chev_a, dir="row", align="center", gap=30, pad=(22, 64, 22, 64))
    L_ = 26
    corner_pts = {0: [(L_, 0), (0, 0), (0, L_)], 1: [(0, 0), (L_, 0), (L_, L_)], 2: [(L_, 0), (L_, L_), (0, L_)], 3: [(0, 0), (0, L_), (L_, L_)]}
    br = []
    corners = []
    for k, (sx, sy) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        n_ = node(f"Br{k}", shape("B", poly(corner_pts[k]), stroke(argb(WHITE, 170), 3, "butt")))
        br.append((n_, sx, sy))
        corners.append(anchor(f"Corner{k}", n_, w=L_, h=L_))
    corner_box = box("Corners",
                     box("CTop", corners[0], box("CTs", ws="fill", h=1, hs="fixed"), corners[1], dir="row", ws="fill", align="topLeft"),
                     box("CMid", ws="fill", hs="fill"),
                     box("CBot", corners[3], box("CBs", ws="fill", h=1, hs="fixed"), corners[2], dir="row", ws="fill", align="topLeft"),
                     ws="fill", hs="fill")
    FW_ = 1000
    scan = node("Scan", shape("S", rect(3, 60, x=0, y=44), solid(argb(CY_, 200))),
                shape("G", rect(90, 60, x=-45, y=44), lgrad([(argb(CY_, 0), 0), (argb(CY_, 55), 1)], -90, 0, 0, 0)), x=-160)
    frame = stack("Enter Frame", main_row, corner_box, box("Scan Box", anchor("Scan L", scan, w=10, h=88), ws="fill", hs="fill"),
                  ws="hug", hs="hug", clip=True)
    hdr = box("Hdr", box("HdL", mono("H1", "01  /  ENTRY", 18, MUTED, ls=5, dec=False), ws="fill"),
              mono("H2", "STATUS  READY", 18, CY_, ls=4, dec=False), dir="row", ws="fill", align="centerLeft", pad=(0, 6, 0, 6))
    kc = box("KC", box("Key", mono("Kk", "ENTER", 17, WHITE, ls=3, dec=False), pad=(3, 9, 3, 9), radius=5, stroke=(argb(WHITE, 170), 1.5)),
             mono("Press", "PRESS TO ENGAGE", 17, A_, ls=5, dec=False), dir="row", gap=14, align="center")
    hint = box("Hint", box("HL", kc, ws="fill"), mono("Lvl", "LVL 00  >  88", 17, MUTED, ls=4, dec=False), dir="row", ws="fill",
               align="centerLeft", pad=(0, 6, 0, 6))
    panel = box("Panel", box("Hdr Dim", hdr, ws="fill", opacity=0.6), frame, box("Hint Dim", hint, ws="fill", opacity=0.65),
                gap=10, align="topCenter")
    # rulers from the panel out to both edges (+ readouts riding on them)
    def ruler(name, flip):
        n_ = (W - PW) // 2
        tk = [shape(f"{name}{q}", poly([(q * 24, 0), (q * 24, 16 if q % 5 == 0 else 7)]), stroke(argb(WHITE, 190 if q % 5 == 0 else 90), 2, "butt"))
              for q in range(n_ // 24)]
        groups = [node(f"{name}G{g}", *tk[g * 8:(g + 1) * 8]) for g in range((len(tk) + 7) // 8)]
        base = shape(f"{name}B", poly([(0, 0), (n_, 0)]), stroke(argb(WHITE, 110), 2, "butt"))
        return anchor(name, node(name + " Art", base, *groups, x=n_ if flip else 0, y=0, sx=-1 if flip else 1), w=n_, h=20), groups
    rl0, rl_g = ruler("RulL", True)
    rr0, rr_g = ruler("RulR", False)
    rl = box("RulL Box", rl0, ws="fill", h=20, hs="fixed", align="topRight", clip=True)
    rr = box("RulR Box", rr0, ws="fill", h=20, hs="fixed", align="topLeft", clip=True)
    def readout(name, lines, col, align):
        rows = [mono(f"{name}{k}", s_, 18, col if k == 0 else MUTED, ls=4, dec=False) for k, s_ in enumerate(lines)]
        segs = [box(f"{name}Sg{k}", w=26, h=6, ws="fixed", hs="fixed", fill=argb(col)) for k in range(8)]
        return box(name, *rows, box(name + "Bar", *segs, dir="row", gap=5), gap=8, align=align), rows, segs
    rdl, rdl_r, rdl_s = readout("RdL", ["RIVE RENDERER  //  GPU", "ARTBOARD > TEXTURE", "VISOR  R 4.0 M  ·  150 DEG"], CY_, "topRight")
    rdr, rdr_r, rdr_s = readout("RdR", ["TRAFFIC  8,437", "SKYLANE  140 M", "UPLINK  ESTABLISHED"], A_, "topLeft")
    side_l = box("Side L", rl, box("SLr", rdl, ws="fill", align="topRight", pad=(0, 300, 0, 0)), gap=14, align="topRight", ws="fill",
                 opacity=0.55)
    side_r = box("Side R", rr, box("SRr", rdr, ws="fill", align="topLeft", pad=(0, 0, 0, 300)), gap=14, align="topLeft", ws="fill",
                 opacity=0.55)
    bot = box("Bottom Band", side_l, panel, side_r, dir="row", w=W, h=BH, ws="fixed", hs="fixed", align="center", gap=28)
    root = box("Root", top, box("GapTB", w=W, h=TT_BOT[0] - TT_TOP[1], ws="fixed", hs="fixed"), bot, ws="fill", hs="fill", align="topLeft")
    ab.add(root)
    # ---------------- build (~150 frames, staggered out from the centre)
    b = Anim("Build", 150)
    hid = Anim("Hidden", 1)
    b.key(hair.id, 16, [(0, 0), (4, 0), (40, 1, EASE_OUT)])
    hid.hold(hair.id, 16, 0)
    for gl in (rl_g, rr_g):
        for g, grp in enumerate(gl):
            o = 10 + g * 1.4
            b.key(grp.id, 18, [(0, 0, "hold"), (o, 0, "hold"), (o + 1, 1, "hold"), (o + 3, 0.25, "hold"), (o + 5, 1)])
            hid.hold(grp.id, 18, 0)
    for k, (n_, sx, sy) in enumerate(br):
        dx, dy = (-220 if sx == 0 else 220), (-60 if sy == 0 else 60)
        b.key(n_.id, 13, [(0, dx), (14 + k * 3, dx), (36 + k * 3, 0, EASE_OUT)])
        b.key(n_.id, 14, [(0, dy), (14 + k * 3, dy), (36 + k * 3, 0, EASE_OUT)])
        b.key(n_.id, 18, [(0, 0, "hold"), (14 + k * 3, 1)])
        hid.hold(n_.id, 18, 0)
    b.key(ret.id, 16, [(0, 0), (34, 0), (58, 1, EASE_OUT)])
    b.key(ret.id, 17, [(0, 0), (34, 0), (58, 1, EASE_OUT)])
    b.key(ret.id, 15, [(34, -6.28), (64, 0, EASE_OUT)])
    hid.hold(ret.id, 16, 0)
    hid.hold(ret.id, 17, 0)
    b.key(word.id, 18, [(0, 0, "hold"), (40, 0, "hold"), (42, 1, "hold"), (44, 0.2, "hold"), (47, 1, "hold"), (49, 0.4, "hold"), (52, 1)])
    hid.hold(word.id, 18, 0)
    for q, c_ in enumerate(chevs):
        b.key(c_.id, 18, [(0, 0, "hold"), (64 + q * 5, 0), (68 + q * 5, 1)])
        b.key(c_.id, 13, [(64 + q * 5, -30), (78 + q * 5, 0, EASE_OUT)])
        hid.hold(c_.id, 18, 0)
    for k, e_ in enumerate([hdr, hint, centre_top]):
        st = (20, 92, 8)[k]
        b.key(e_.id, 18, [(0, 0, "hold"), (st, 0, "hold"), (st + 1, 1, "hold"), (st + 3, 0, "hold"), (st + 6, 1)])
        hid.hold(e_.id, 18, 0)
    for blk, rows, st0 in ((lb, [lt, ls_], 18), (rb, [rt_, rs_], 26), (rdl, rdl_r, 40), (rdr, rdr_r, 48)):
        for k, r_ in enumerate(rows):
            b.key(r_.id, 18, [(0, 0, "hold"), (st0 + k * 8, 0, "hold"), (st0 + k * 8 + 1, 1, "hold"), (st0 + k * 8 + 3, 0.2, "hold"), (st0 + k * 8 + 5, 1)])
            hid.hold(r_.id, 18, 0)
    for segs, st0 in ((rdl_s, 70), (rdr_s, 78)):
        for k, s_ in enumerate(segs):
            b.key(s_.id, 18, [(0, 0, "hold"), (st0 + k * 4, 0, "hold"), (st0 + k * 4 + 1, 1)])
            hid.hold(s_.id, 18, 0)
    b.key(scan.id, 13, [(0, -160, "hold"), (52, -160), (104, FW_ + 160)])
    # ---------------- idle
    idle = Anim("Idle", 240, "loop")
    idle.key(ret_ring.id, 15, [(0, 0, "linear"), (240, 6.2831853, "linear")])
    idle.key(ret_sq.id, 15, [(0, 0.785398, "linear"), (240, 0.785398 - 3.1415927, "linear")])
    idle.key(scan.id, 13, [(0, -160, "hold"), (60, -160, "linear"), (170, FW_ + 160, "linear"), (240, FW_ + 160, "hold")])
    idle.key(tape.id, 13, [(0, 0, "linear"), (120, -60, EASE_IO), (240, 0, EASE_IO)])
    for q, c_ in enumerate(chevs):
        o = q * 10
        idle.key(c_.id, 18, [(0, 0.25), (o, 0.25), (o + 8, 1), (o + 30, 0.25), (60, 0.25), (60 + o, 0.25), (68 + o, 1), (90 + o, 0.25), (240, 0.25)])
    idle.key(kc.id, 18, [(0, 1, "hold"), (100, 0.25, "hold"), (112, 1, "hold"), (220, 0.25, "hold"), (232, 1, "hold")])
    # ---------------- out
    out = Anim("Out", 30)
    for k, (n_, sx, sy) in enumerate(br):
        dx, dy = (-300 if sx == 0 else 300), (-30 if sy == 0 else 30)
        out.key(n_.id, 13, [(0, 0), (18, dx, (0.6, 0.0, 0.9, 0.4))])
        out.key(n_.id, 14, [(0, 0), (18, dy, (0.6, 0.0, 0.9, 0.4))])
    for k, e_ in enumerate([word, hdr, hint, chev_a, reticle, lb, rb, rdl, rdr, centre_top]):
        out.key(e_.id, 18, [(0, 1, "hold"), (2 + k, 0.2, "hold"), (4 + k, 1, "hold"), (6 + k, 0)])
    out.key(hair.id, 16, [(0, 1), (20, 0, (0.6, 0.0, 0.9, 0.4))])
    ab.add(b.el, hid.el, idle.el, out.el)
    s_h, s_b, s_i, s_o = nid(), nid(), nid(), nid()
    finish_sm(ab, [sm_layer("Title", s_h,
                            state(hid, go(s_b, cond("titleBuild", 0.5, "greaterThan")), sid=s_h, x=100, y=0),
                            state(b, go(s_i, exit_pct=100), go(s_h, cond("titleBuild", 0.5, "lessThan")), sid=s_b, x=300, y=0),
                            state(idle, go(s_o, cond("enterGo", 0.5, "greaterThan")), go(s_h, cond("titleBuild", 0.5, "lessThan")), sid=s_i, x=500, y=0),
                            state(out, go(s_h, cond("titleBuild", 0.5, "lessThan")), sid=s_o, x=700, y=0))], name="Title")
    return ab
