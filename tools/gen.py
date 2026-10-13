#!/usr/bin/env python3
"""Generates scene.rml for Rive City.

Artboards
  * "Rive City"    1600x900 — sky, the 3D world (ScriptedLayout world.as),
                   the screen overlay (prompts + readout) and the boot overlay
                   with the animated Rive logo (logo.rml).
  * "Cluster"      driver display (mapped onto the curved screen behind the yoke)
  * "Console"      centre touchscreen: DRIVE / MEDIA / AMBIENT
  * "Hub"          yoke hub screen
  * "HUD"          windshield head-up display (transparent; AR markers)
  * "BB *"         six billboard designs mapped onto 134 city billboards
  * "Track Row"    playlist row (ArtboardComponentList)

All share the "Drive" view model (playlist rows use "Track"). world.as
writes telemetry and reads `req` (request codes written by listeners).
"""
import hashlib, math, os

# WEB=1: the published web build ships glyph-subset fonts (fonts/web, tools: pyftsubset; ASCII + ° ·)
# and deflated mesh packs (assets/*.rz, tools/zpack.py). Default = raw files for the live preview,
# where the CLI's watchdog fuel counters make in-script inflate ~20x slower than shipped.
FONT_DIR = "fonts/web/" if os.environ.get("WEB") else "fonts/"
# monospace UI font: Iosevka Regular, glyph-subset (ASCII + ° ·), SIL OFL 1.1
MONO_FILE = "fonts/Iosevka-Regular.ttf"
from xml.sax.saxutils import quoteattr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

_next = [10]


def nid():
    _next[0] += 1
    return f"0:{_next[0]}"


class E:
    def __init__(self, _tag, *children, **attrs):
        self.tag = _tag
        self.attrs = {}
        for k, v in attrs.items():
            if v is None:
                continue
            k = k.rstrip("_")
            if isinstance(v, bool):
                v = "true" if v else "false"
            elif isinstance(v, float):
                v = f"{v:.4f}".rstrip("0").rstrip(".") if abs(v) < 1e6 else str(v)
            self.attrs[k] = str(v)
        self.children = [c for c in children if c is not None]

    def add(self, *cs):
        for c in cs:
            if c is None:
                continue
            if isinstance(c, (list, tuple)):
                self.add(*c)
            else:
                self.children.append(c)
        return self

    @property
    def id(self):
        return self.attrs.get("id")

    def assign_ids(self, path="", used=None):
        used = used if used is not None else set()
        if self.tag != "Rive" and "id" not in self.attrs:
            h = int(hashlib.sha1(path.encode()).hexdigest(), 16) % 900_000_000 + 100_000_000
            while f"1:{h}" in used:
                h += 1
            self.attrs["id"] = f"1:{h}"
        if "id" in self.attrs:
            used.add(self.attrs["id"])
        counts = {}
        for c in self.children:
            label = c.tag + ":" + c.attrs.get("name", "")
            counts[label] = counts.get(label, 0) + 1
            c.assign_ids(f"{path}/{label}#{counts[label]}", used)
        return used

    def render(self, ind=0):
        pad = "    " * ind
        a = " ".join(f"{k}={quoteattr(v)}" for k, v in self.attrs.items())
        head = f"{pad}<{self.tag}{(' ' + a) if a else ''}"
        if not self.children:
            return head + "/>\n"
        return head + ">\n" + "".join(c.render(ind + 1) for c in self.children) + f"{pad}</{self.tag}>\n"


def argb(hexrgb, a=255):
    return f"{a:02X}{hexrgb.lstrip('#').upper()}"


# ---------------------------------------------------------------- brand
BLACK = "#000000"
SURF = "#141414"
CARD = "#1A1A1D"
WHITE = "#FFFFFF"
MUTED = "#A0A0A0"
FAINT = "#5C5C5C"
AMBER = "#FFA41C"
TRACK = "#2A2A2E"
PRISM = ["#F30058", "#FF483C", "#FFA41C", "#71FF19", "#19F2FF", "#3084FF"]
AMB = ["#FFA41C", "#19F2FF", "#F30058", "#3084FF", "#71FF19", "#E8ECF4"]
WGHT = 2003265652

F_ORB, F_INTER, F_MONO = nid(), nid(), nid()

# decrypt converters: one per cue (each surface decrypts in on its own boot)
CUES = {"main": "cue", "cl": "bootCl", "cs": "bootCs", "hud": "bootHud", "hub": "bootHub", "title": "titleCue"}
CONV = {k: nid() for k in CUES}
GROUP = ["main"]
NO_DEC = {"speed", "battery", "range", "alt", "clock", "trackTime", "taps", "bbSpeed", "m1x", "m1d", "m2d", "m3d", "readout",
          "gear", "navDist", "warn"} | {f"t{k}{s}" for k in range(1, 5) for s in ("d", "v", "tt", "hx")}
_lift = [0]

LOGO_AB, LOGO_VM, LOGO_SM = "90:547", "90:470", "90:1003"
LOGO_VMI, LOGO_VMI_HUB, LOGO_VMI_BB = "90:471", "90:9001", "90:9003"

# ---------------------------------------------------------------- view models
VM_ID, VMI_ID = nid(), nid()
VM_PROPS = {}
TRK_VM, TRK_PROPS = nid(), {}


def vm_prop(name, typ, default):
    VM_PROPS[name] = (nid(), typ, default)


for n, t, d in [
    ("speed", "string", "0"), ("speedFrac", "number", 0), ("powerFrac", "number", 0), ("gear", "string", "P"),
    ("gP", "number", 1), ("gR", "number", 0.25), ("gN", "number", 0.25), ("gD", "number", 0.25),
    ("ap", "number", 1), ("apLabel", "string", "AUTOPILOT"), ("apSub", "string", "HANDS FREE  ·  LANE + ROUTE LOCK"), ("mode", "number", 0), ("modeName", "string", "CRUISE"),
    ("battery", "string", "86"), ("batteryFrac", "number", 0.86), ("range", "string", "438"),
    ("alt", "string", "0.6"), ("altFrac", "number", 0), ("steer", "number", 0), ("view", "number", 0),
    ("street", "string", "KESTREL AVE"), ("navDist", "string", "420 M"), ("navStreet", "string", "AURORA ST"),
    ("navTurn", "number", 1), ("navVerb", "string", "TURN RIGHT"),
    ("track", "number", 2), ("trackTitle", "string", "AFTERBURN"), ("trackArtist", "string", "ROCKET SQUADRON OST"),
    ("playing", "number", 1), ("progress", "number", 0), ("trackTime", "string", "0:00 / 2:58"),
    ("ambient", "number", 0), ("ambName", "string", "AMBER"), ("taps", "string", "1287"), ("hitT", "number", 0),
    ("bbSpeed", "string", "000"),
    ("clock", "string", "23:47"), ("temp", "string", "17°C"), ("night", "number", 1), ("sunOp", "number", 0.3),
    ("moonOp", "number", 1), ("readout", "string", "AUTOPILOT"), ("warn", "string", ""), ("warnOp", "number", 0),
    ("blackout", "number", 0), ("logoVis", "number", 0), ("uiIn", "number", 0), ("bootBar", "number", 0),
    ("enterOp", "number", 0), ("enterGo", "number", 0), ("loadOp", "number", 1), ("titleOp", "number", 1),
    ("titleBuild", "number", 0), ("titleCue", "number", 0),
    *[p for k in range(1, 5) for p in (
        (f"t{k}x", "number", -500), (f"t{k}y", "number", -500), (f"t{k}s", "number", 1), (f"t{k}op", "number", 0),
        (f"t{k}n", "number", 1), (f"t{k}r", "number", 0), (f"t{k}c", "number", 0),
        (f"t{k}id", "string", "HX-0000"), (f"t{k}cl", "string", "SEDAN"), (f"t{k}d", "string", "00.0"),
        (f"t{k}v", "string", "+00"), (f"t{k}tt", "string", "--.-"), (f"t{k}hx", "string", "0x0000"),
        # declutter: label block position (relative to the target), leader flip, label opacity
        (f"t{k}lx", "number", -600), (f"t{k}ly", "number", -600), (f"t{k}fx", "number", 1), (f"t{k}fy", "number", 1), (f"t{k}lo", "number", 1))],
    *[p for k in range(1, 4) for p in (
        (f"m{k}lx", "number", -600), (f"m{k}ly", "number", -600), (f"m{k}fx", "number", 1), (f"m{k}fy", "number", 1), (f"m{k}lo", "number", 1))],
    ("bootCl", "number", 0), ("bootCs", "number", 0), ("bootHud", "number", 0), ("bootHub", "number", 0),
    ("cue", "number", 0), ("req", "number", 0), ("quality", "number", 0), ("benchSkip", "number", 0), ("dbgFlags", "number", 0),
    ("qs0", "number", 1), ("qs1", "number", 0), ("qs2", "number", 0), ("tab", "number", 0),
    ("m1x", "number", -500), ("m1y", "number", -500), ("m1op", "number", 0), ("m1t", "string", ""), ("m1d", "string", ""),
    ("m2x", "number", -500), ("m2y", "number", -500), ("m2op", "number", 0), ("m2t", "string", ""), ("m2d", "string", ""),
    ("m3x", "number", -500), ("m3y", "number", -500), ("m3op", "number", 0), ("m3t", "string", ""), ("m3d", "string", ""),
    ("logo", "vm", LOGO_VMI), ("logoHub", "vm", LOGO_VMI_HUB), ("logoBB", "vm", LOGO_VMI_BB),
    ("tracks", "list", None),
]:
    vm_prop(n, t, d)

TRACKS = [("NEON CATHEDRAL", "VANTA ARC", "3:42"), ("SKYLANE", "LUMEN DRIVE", "4:05"),
          ("AFTERBURN", "ROCKET SQUADRON OST", "2:58"), ("MERIDIAN NIGHTS", "HALO STATIC", "3:31"),
          ("CHROME RAIN", "KODA & THE PRISM", "4:17"), ("VECTOR HEART", "NULL SET", "3:09")]
for n, t in [("title", "string"), ("artist", "string"), ("dur", "string"), ("index", "index"), ("tap", "number"),
             ("sel", "number")]:
    TRK_PROPS[n] = (nid(), t)
TRK_INSTS = [nid() for _ in TRACKS]


def path(name):
    return f"{VM_ID}-{VM_PROPS[name][0]}"


def tpath(name):
    return f"{TRK_VM}-{TRK_PROPS[name][0]}"


def bind(name, key, **kw):
    return E("DataBindContext", sourcePathIds=path(name), propertyKey=key, **kw)


def tbind(name, key, **kw):
    return E("DataBindContext", sourcePathIds=tpath(name), propertyKey=key, **kw)


def build_vms():
    props, vals = [], []
    for name, (pid, typ, default) in VM_PROPS.items():
        if typ == "string":
            props.append(E("ViewModelPropertyString", name=name, id=pid))
            vals.append(E("ViewModelInstanceString", propertyValue=default, viewModelPropertyId=pid))
        elif typ == "vm":
            props.append(E("ViewModelPropertyViewModel", name=name, id=pid, viewModelReferenceId=LOGO_VM))
            vals.append(E("ViewModelInstanceViewModel", propertyValue=default, viewModelPropertyId=pid))
        elif typ == "list":
            props.append(E("ViewModelPropertyList", name=name, id=pid))
            vals.append(E("ViewModelInstanceList",
                          *[E("ViewModelInstanceListItem", viewModelId=TRK_VM, viewModelInstanceId=i) for i in TRK_INSTS],
                          viewModelPropertyId=pid))
        else:
            props.append(E("ViewModelPropertyNumber", name=name, id=pid))
            vals.append(E("ViewModelInstanceNumber", propertyValue=float(default), viewModelPropertyId=pid))
    root = E("ViewModel", *props, E("ViewModelInstance", *vals, exports=True, name="Default", id=VMI_ID),
             name="Drive", id=VM_ID, defaultInstanceId=VMI_ID)
    tprops = []
    for name, (pid, typ) in TRK_PROPS.items():
        if typ == "string":
            tprops.append(E("ViewModelPropertyString", name=name, id=pid))
        elif typ == "index":
            tprops.append(E("ViewModelPropertySymbolListIndex", symbolTypeValue="15", name=name, id=pid))
        else:
            tprops.append(E("ViewModelPropertyNumber", name=name, id=pid))
    insts = []
    for k, (ti, ar, du) in enumerate(TRACKS):
        insts.append(E("ViewModelInstance",
                       E("ViewModelInstanceString", propertyValue=ti, viewModelPropertyId=TRK_PROPS["title"][0]),
                       E("ViewModelInstanceString", propertyValue=ar, viewModelPropertyId=TRK_PROPS["artist"][0]),
                       E("ViewModelInstanceString", propertyValue=du, viewModelPropertyId=TRK_PROPS["dur"][0]),
                       E("ViewModelInstanceSymbolListIndex", viewModelPropertyId=TRK_PROPS["index"][0]),
                       E("ViewModelInstanceNumber", propertyValue=0.0, viewModelPropertyId=TRK_PROPS["tap"][0]),
                       E("ViewModelInstanceNumber", propertyValue=1.0 if k == 2 else 0.0, viewModelPropertyId=TRK_PROPS["sel"][0]),
                       exports=True, name=f"Track {k + 1}", id=TRK_INSTS[k]))
    trk = E("ViewModel", *tprops, *insts, name="Track", id=TRK_VM, defaultInstanceId=TRK_INSTS[0])
    return [trk, root]


# ---------------------------------------------------------------- layout helpers
def style(**kw):
    sid = nid()
    attrs = {}
    for k, v in kw.items():
        if v is None:
            continue
        attrs[k] = v
        for unit_key in ("padding", "margin", "gap", "position"):
            if k.startswith(unit_key) and not k.endswith("UnitsValue") and k != "positionTypeValue":
                attrs[k + "UnitsValue"] = "points"
    return E("LayoutComponentStyle", id=sid, name="Style", **attrs), sid


def box(name, *children, w=None, h=None, ws="hug", hs="hug", dir="column", align="topLeft",
        pad=None, gap=None, fill=None, radius=None, stroke=None, clip=None, grow=None, bid=None,
        opacity=None, extra=None, binds=(), grad=None):
    st = dict(layoutWidthScaleType=ws, layoutHeightScaleType=hs, flexDirectionValue=dir, layoutAlignmentType=align)
    if pad is not None:
        t, r, b, l = pad if isinstance(pad, (tuple, list)) else (pad,) * 4
        st.update(paddingTop=t, paddingRight=r, paddingBottom=b, paddingLeft=l)
    if gap is not None:
        st.update(gapHorizontal=gap, gapVertical=gap)
    if radius is not None:
        st.update(cornerRadiusTL=radius, linkCornerRadius=True)
    if grow is not None:
        st["flexGrow"] = grow
    if extra:
        st.update(extra)
    s, sid = style(**st)
    lc = E("LayoutComponent", s, name=name, id=bid or nid(), styleId=sid,
           width=w if w is not None else 0, height=h if h is not None else 0, clip=clip, opacity=opacity)
    for b in binds:
        lc.add(b)
    if fill is not None:
        lc.add(E("Fill", E("SolidColor", colorValue=fill, name="C", id=nid()), name="Fill"))
    if grad is not None:
        lc.add(grad)
    if stroke is not None:
        col, th = stroke
        lc.add(E("Stroke", E("SolidColor", colorValue=col, name="C", id=nid()), thickness=th, name="Stroke"))
    lc.add(*children)
    return lc


def fill_color_id(b):
    for c in b.children:
        if c.tag == "Fill":
            return c.children[0].id
    return None


def stroke_color_id(b):
    for c in b.children:
        if c.tag == "Stroke":
            return c.children[0].id
    return None


def text(name, s, size, color=WHITE, font=None, weight=None, bindname=None, ls=None, lh=None,
         align="left", tid=None, opacity_bind=None, lp=True, x=None, y=None, ox=None, oy=None, dec=True, cid=None,
         rid=None, conv=None):
    sid = nid()
    font = font or F_INTER
    paint = E("TextStylePaint",
              E("Fill", E("SolidColor", colorValue=argb(color), name="C", id=cid or nid()), name="Fill"),
              fontSize=size, fontAssetId=font, letterSpacing=ls, lineHeight=lh, id=sid, name="Style")
    if weight is not None:
        paint.add(E("TextStyleAxis", tag=WGHT, axisValue=weight, name="Weight"))
    run = E("TextValueRun", styleId=sid, text=s, name="Run", id=rid or nid())
    if dec and not bindname and s.strip():
        _lift[0] += 1
        bindname = f"txt{_lift[0]}"
        vm_prop(bindname, "string", s)
    if bindname:
        if conv:
            run.add(bind(bindname, 268, converterId=conv))
        elif dec and bindname not in NO_DEC:
            run.add(bind(bindname, 268, converterId=CONV[GROUP[0]]))
        else:
            run.add(bind(bindname, 268))
    kids = []
    if lp:
        kids.append(E("LayoutParticipant", layoutWidthScaleType="hug", layoutHeightScaleType="hug", name="Layout"))
    if opacity_bind:
        kids.append(bind(opacity_bind, 18))
    return E("Text", *kids, paint, run, name=name, id=tid or nid(), sizingValue="autoWidth", wrapValue="noWrap",
             alignValue=align, x=x, y=y, originX=ox, originY=oy)


def ttext(name, prop, size, color=WHITE, font=None, weight=None, ls=None, cid=None):
    """Text bound to the Track item VM."""
    sid = nid()
    paint = E("TextStylePaint", E("Fill", E("SolidColor", colorValue=argb(color), name="C", id=cid or nid()), name="Fill"),
              fontSize=size, fontAssetId=font or F_INTER, letterSpacing=ls, id=sid, name="Style")
    if weight is not None:
        paint.add(E("TextStyleAxis", tag=WGHT, axisValue=weight, name="Weight"))
    run = E("TextValueRun", tbind(prop, 268), styleId=sid, text=prop, name="Run")
    return E("Text", E("LayoutParticipant", layoutWidthScaleType="hug", layoutHeightScaleType="hug", name="Layout"),
             paint, run, name=name, id=nid(), sizingValue="autoWidth", wrapValue="noWrap", alignValue="left")


def orb(name, s, size, color=WHITE, **kw):
    return text(name, s, size, color, font=F_ORB, weight=900, **kw)


def mono(name, s, size, color=MUTED, **kw):
    return text(name, s, size, color, font=F_MONO, **kw)


def inter(name, s, size, color=WHITE, weight=500, **kw):
    return text(name, s, size, color, font=F_INTER, weight=weight, **kw)


def node(name, *children, x=0, y=0, rot=None, opacity=None, scale=None, sx=None, sy=None, binds=(), nid_=None):
    return E("Node", *binds, *children, name=name, x=x, y=y, id=nid_ or nid(), rotation=rot, opacity=opacity,
             scaleX=sx if sx is not None else scale, scaleY=sy if sy is not None else scale)


def shape(name, *children, x=0, y=0, opacity=None, rot=None):
    return E("Shape", *children, name=name, x=x, y=y, id=nid(), opacity=opacity, rotation=rot)


def solid(col, cid=None):
    return E("Fill", E("SolidColor", colorValue=col, name="C", id=cid or nid()), name="Fill")


def stroke(col, th, cap="round", trim=None, cid=None):
    s = E("Stroke", E("SolidColor", colorValue=col, name="C", id=cid or nid()), thickness=th, cap=cap, join="round", name="Stroke")
    if trim is not None:
        s.add(trim)
    return s


def lgrad(stops, x0, y0, x1, y1):
    return E("Fill", E("LinearGradient", *[E("GradientStop", colorValue=c, position=p) for c, p in stops],
                       startX=x0, startY=y0, endX=x1, endY=y1, name="G"), name="Fill")


def rgrad(stops, x0, y0, x1, y1):
    return E("Fill", E("RadialGradient", *[E("GradientStop", colorValue=c, position=p) for c, p in stops],
                       startX=x0, startY=y0, endX=x1, endY=y1, name="G"), name="Fill")


def poly(pts, closed=False, name="Path"):
    return E("PointsPath", *[E("StraightVertex", x=round(px, 2), y=round(py, 2)) for px, py in pts],
             isClosed=closed, name=name)


def rect(w, h, x=0, y=0, r=None, ox=None, oy=None):
    return E("Rectangle", width=w, height=h, x=x, y=y, cornerRadiusTL=r, linkCornerRadius=True if r else None,
             originX=ox, originY=oy)


def ellipse(w, h, x=0, y=0):
    return E("Ellipse", width=w, height=h, x=x, y=y)


def arc_pts(cx, cy, r, a0, a1, n=48, ry=None):
    ry = ry if ry is not None else r
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + ry * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def trim(bindname, end=0.3):
    return E("TrimPath", bind(bindname, 115), name="Trim", start=0, end=end, modeValue=1)


def layer(name, *children, align="center", **kw):
    return box(name, *children, ws="fill", hs="fill", align=align, **kw)


def art(name, *children, w=None, h=None):
    if w is not None:
        return box(name, node(name + " Art", *children), w=w, h=h, ws="fixed", hs="fixed", clip=False)
    return box(name, node(name + " Art", *children), ws="fill", hs="fill")


def spacer(w=1, h=1):
    return box("Gap", w=w, h=h, ws="fixed", hs="fixed")


# ---------------------------------------------------------------- animation / state machines
EASE = (0.25, 0.1, 0.25, 1.0)
EASE_OUT = (0.16, 1.0, 0.3, 1.0)
EASE_IO = (0.65, 0.0, 0.35, 1.0)
BACK_OUT = (0.34, 1.56, 0.64, 1.0)


def kf(value, frame, interp="cubic", kind="KeyFrameDouble", ease=EASE):
    k = E(kind, value=value, frame=frame, interpolationType=interp)
    if interp == "cubic":
        k.add(E("CubicEaseInterpolator", x1=ease[0], y1=ease[1], x2=ease[2], y2=ease[3]))
    return k


class Anim:
    def __init__(self, name, duration, loop=None, fps=60):
        self.id = nid()
        self.el = E("LinearAnimation", name=name, id=self.id, duration=duration, loopValue=loop, fps=fps)
        self.objs = {}

    def key(self, obj, prop, frames, kind="KeyFrameDouble", ease=EASE):
        """frames: [(frame, value[, ease|'hold'|'linear'])]"""
        ko = self.objs.get(obj)
        if ko is None:
            ko = E("KeyedObject", objectId=obj)
            self.objs[obj] = ko
            self.el.add(ko)
        kp = E("KeyedProperty", propertyKey=prop)
        for fr in frames:
            f, v = fr[0], fr[1]
            e = fr[2] if len(fr) > 2 else ease
            if kind in ("KeyFrameColor",) and e not in ("hold", "linear") and not isinstance(e, tuple):
                e = EASE
            if e == "hold":
                kp.add(kf(v, f, "hold", kind))
            elif e == "linear":
                kp.add(kf(v, f, "linear", kind))
            else:
                kp.add(kf(v, f, "cubic", kind, e))
        ko.add(kp)
        return self

    def hold(self, obj, prop, value, kind="KeyFrameDouble"):
        return self.key(obj, prop, [(0, value, "hold")], kind)

    def color(self, obj, frames):
        return self.key(obj, 37, frames, "KeyFrameColor")


def cond(name, value, op="equal", vmpath=None):
    p = vmpath or path(name)
    return E("TransitionViewModelCondition",
             E("TransitionPropertyViewModelComparator", E("BindablePropertyNumber", E("DataBindContext", sourcePathIds=p, propertyKey=636))),
             E("TransitionValueNumberComparator", value=float(value)), opValue=op)


def go(to, *conds, ms=None, exit_pct=None):
    t = E("StateTransition", *conds, stateToId=to, duration=ms)
    if exit_pct is not None:
        t.attrs.update(enableExitTime="true", exitTimeIsPercetange="true", exitTime=str(exit_pct))
    return t


_sp = [0]


def state(anim, *kids, sid=None, x=None, y=None, reset=None):
    _sp[0] += 1
    n = _sp[0]
    return E("AnimationState", *kids, id=sid or nid(), animationId=anim.id if isinstance(anim, Anim) else anim,
             x=x if x is not None else 200 + (n % 6) * 180, y=y if y is not None else ((n // 6) % 10) * 120, reset=reset)


def sm_layer(name, entry_to, *states):
    return E("StateMachineLayer", E("AnyState", x=0, y=-160), E("ExitState", x=400, y=-160),
             E("EntryState", E("StateTransition", stateToId=entry_to), x=0, y=0), *states, name=name, id=nid())


def loop_layer(anim):
    st = nid()
    return sm_layer(anim.attrs["name"] if isinstance(anim, E) else anim.el.attrs["name"], st, state(anim, sid=st, x=200, y=0))


def req_listener(target, code, name, ltype="click"):
    return E("StateMachineListenerSingle",
             E("ListenerViewModelChange", E("BindablePropertyNumber", bind("req", 636, direction=True), propertyValue=code)),
             targetId=target, listenerTypeValue=ltype, name=name)


def set_listener(target, prop, value, name):
    return E("StateMachineListenerSingle",
             E("ListenerViewModelChange", E("BindablePropertyNumber", bind(prop, 636, direction=True), propertyValue=value)),
             targetId=target, listenerTypeValue="click", name=name)


def surface_artboard(name, W, H, x, y=1200, comp=True, bg=None):
    s, sid = style(layoutWidthScaleType="fixed", layoutHeightScaleType="fixed")
    ab = E("Artboard", s, name=name, id=nid(), width=W, height=H, styleId=sid, isComponent=comp,
           viewModelId=VM_ID, viewModelInstanceId=VMI_ID, x=x, y=y, clip=True)
    return ab


def finish_sm(ab, layers, listeners=(), name="Main"):
    sm = E("StateMachine", *layers, *listeners, name=name, id=nid())
    ab.attrs["defaultStateMachineId"] = sm.id
    ab.add(sm)
    return sm


def boot_layer(ab, cue, intro_anim, off_anim):
    """Off (hidden) until the cue number reaches 1, then the intro plays once
    and holds; back to Off when the cue drops (R replays)."""
    s_off, s_in = nid(), nid()
    return sm_layer("Boot", s_off,
                    state(off_anim, go(s_in, cond(cue, 0.5, "greaterThan")), sid=s_off, x=200, y=0),
                    state(intro_anim, go(s_off, cond(cue, 0.5, "lessThan")), sid=s_in, x=420, y=0, reset=True))


def keyed_opacity_off(anim, ids):
    for i in ids:
        anim.hold(i, 18, 0)


# ---------------------------------------------------------------- shared vector bits
def keycap(label=None, arrow=None, size=12):
    if arrow:
        tri = {"up": [(0, -4.5), (-5, 3.5), (5, 3.5)], "down": [(0, 4.5), (-5, -3.5), (5, -3.5)],
               "left": [(-4.5, 0), (3.5, -5), (3.5, 5)], "right": [(4.5, 0), (-3.5, -5), (-3.5, 5)]}[arrow]
        inner = box("Arrow", node("Arrow Art", shape("Tri", poly(tri, True), solid(argb(WHITE)))), w=10, h=10, ws="fixed", hs="fixed")
    else:
        inner = mono("Key", label, size, WHITE, dec=False)
    return box(f"Key {label or arrow}", inner, h=22, hs="fixed", align="center", pad=(0, 7, 0, 7), radius=4,
               stroke=(argb(WHITE, 120), 1.2), extra={"minWidth": 22, "minWidthUnitsValue": "points"})


def prompt(*parts):
    return box("Prompt", *parts, dir="row", align="center", gap=6)


def prism_bar(w, h, name="Prism"):
    seg = w / 6
    return [shape(f"{name} {k}", rect(seg - 3, h, x=k * seg + seg / 2, y=h / 2), solid(argb(c))) for k, c in enumerate(PRISM)]


# ================================================================ artboards (gen_ui.py / gen_bb.py share this namespace)
for _f in ("gen_ui.py", "gen_bb.py"):
    exec(compile(open(os.path.join(HERE, _f)).read(), os.path.join(HERE, _f), "exec"))


# ---------------------------------------------------------------- title CTA: plain "ENTER THE CITY"
# Rest state is just the words. The build is FUI motion graphics on hold keyframes: corner ticks
# snap in, a micro label blinks, an underline steps across, a block cursor blinks then types the
# words in (a clip layout whose width steps per character, the cursor is the next layout sibling so
# it rides the edge) while the decrypt converter scrambles them, then everything but the words
# vanishes. Exit: the cursor comes back and backspaces it out.
CTA_SIZE, CTA_LS = 11, 4.5
CTA_WT = 167            # measured rendered width of the words (px, incl. trailing letter spacing); None = hug


def build_cta():
    GROUP[0] = "title"
    words = orb("CTA", "ENTER THE CITY", CTA_SIZE, WHITE, ls=CTA_LS)
    GROUP[0] = "main"
    WT = CTA_WT
    H_ = 16
    if WT is None:
        reveal = box("Reveal", words, hs="fixed", h=H_, align="centerLeft")
    else:
        reveal = box("Reveal", words, w=WT, h=H_, ws="fixed", hs="fixed", clip=True, align="centerLeft")
    cursor = box("Cursor", w=6, h=12, ws="fixed", hs="fixed", fill=argb(WHITE), opacity=0)
    row = box("CTA Row", reveal, cursor, dir="row", align="center", gap=2)
    PX, PY = 24, 10
    L_ = 7
    cpts = {0: [(L_, 0), (0, 0), (0, L_)], 1: [(0, 0), (L_, 0), (L_, L_)], 2: [(L_, 0), (L_, L_), (0, L_)], 3: [(0, 0), (0, L_), (L_, L_)]}
    corners, cnodes = [], []
    for k in range(4):
        n_ = node(f"Ck{k}", shape("B", poly(cpts[k]), stroke(argb(WHITE, 200), 1.5, "butt")))
        cnodes.append(n_)
        corners.append(anchor(f"Corner{k}", n_, w=L_, h=L_))
    corner_box = box("Corners",
                     box("CTop", corners[0], box("CTs", ws="fill", h=1, hs="fixed"), corners[1], dir="row", ws="fill"),
                     box("CMid", ws="fill", hs="fill"),
                     box("CBot", corners[3], box("CBs", ws="fill", h=1, hs="fixed"), corners[2], dir="row", ws="fill"),
                     ws="fill", hs="fill", opacity=0)
    ul_pad = box("UL Pad", w=0, h=1, ws="fixed", hs="fixed")
    ul = box("UL", w=0, h=1.5, ws="fixed", hs="fixed", fill=argb(WHITE, 220))
    ul_row = box("UL Row", box("ULr", ul_pad, ul, dir="row"), ws="fill", hs="fill", align="bottomLeft", pad=(0, PX, 4, PX))
    label = mono("Micro", "// ENTRY_SEQ  01", 7, AMBER, ls=2, dec=False)
    label_box = box("Micro Box", label, ws="fill", hs="fill", align="topLeft", pad=(0, PX, 0, PX), opacity=0)
    cta = stack("CTA", box("CTA Pad", row, pad=(PY, PX, PY, PX)), corner_box, ul_row, label_box, ws="hug", hs="hug")
    return cta, dict(words=words, reveal=reveal, cursor=cursor, cnodes=cnodes, corner_box=corner_box, ul=ul, ul_pad=ul_pad,
                     label_box=label_box)


def cta_anims(p):
    WT = CTA_WT or 300
    N = 14
    hid = Anim("CTA Hidden", 1)
    hid.hold(p["reveal"].id, 7, 0)
    hid.hold(p["cursor"].id, 18, 0)
    hid.hold(p["corner_box"].id, 18, 0)
    hid.hold(p["label_box"].id, 18, 0)
    hid.hold(p["ul"].id, 7, 0)
    hid.hold(p["ul_pad"].id, 7, 0)
    # timing: typing 3 frames / char, cursor blinks 12 frames on / 12 off (reads clearly)
    BL = 12
    t0 = 40
    t1 = t0 + 3 * N
    END = t1 + 5 * BL + 4
    b = Anim("CTA Build", END)
    H = "hold"
    # corners: blink in from wide and snap home in two jumps, blink out before the rest state
    b.key(p["corner_box"].id, 18, [(0, 1, H), (5, 0, H), (9, 1, H), (t1 + 24, 0, H), (t1 + 30, 1, H), (t1 + 36, 0, H)])
    for k, n_ in enumerate(p["cnodes"]):
        sx = -1 if k in (0, 3) else 1
        sy = -1 if k in (0, 1) else 1
        b.key(n_.id, 13, [(0, sx * 16, H), (5, sx * 6, H), (10, 0, H)])
        b.key(n_.id, 14, [(0, sy * 6, H), (5, sy * 2, H), (10, 0, H)])
    # micro label: blink on, gone near the end
    b.key(p["label_box"].id, 18, [(0, 0, H), (5, 1, H), (9, 0, H), (13, 1, H), (t1 + 18, 0, H), (t1 + 24, 1, H), (t1 + 30, 0, H)])
    # underline: steps across, then steps off to the right
    b.key(p["ul"].id, 7, [(0, 0, H), (8, WT * 0.25, H), (12, WT * 0.6, H), (16, WT, H),
                          (t1 + 8, WT * 0.55, H), (t1 + 12, WT * 0.2, H), (t1 + 16, 0, H)])
    b.key(p["ul_pad"].id, 7, [(0, 0, H), (t1 + 8, WT * 0.45, H), (t1 + 12, WT * 0.8, H), (t1 + 16, 0, H)])
    # cursor: two clear blinks, solid while typing, two clear blinks, gone (width 0 -> words re-centre)
    b.key(p["cursor"].id, 18, [(0, 0, H), (16, 1, H), (16 + BL, 0, H), (t0, 1, H),
                               (t1 + BL, 0, H), (t1 + 2 * BL, 1, H), (t1 + 3 * BL, 0, H), (t1 + 4 * BL, 1, H), (t1 + 5 * BL, 0, H)])
    b.key(p["cursor"].id, 7, [(0, 6, H), (t1 + 5 * BL, 0, H)])
    # typewriter: the clip opens one character per 3 frames
    b.key(p["reveal"].id, 7, [(0, 0, H)] + [(t0 + 3 * i, WT * i / N, H) for i in range(1, N + 1)])
    rest = Anim("CTA Rest", 1)
    rest.hold(p["reveal"].id, 7, WT)
    rest.hold(p["cursor"].id, 18, 0)
    rest.hold(p["cursor"].id, 7, 0)
    rest.hold(p["corner_box"].id, 18, 0)
    rest.hold(p["label_box"].id, 18, 0)
    rest.hold(p["ul"].id, 7, 0)
    # out: cursor returns and blinks once, backspaces the words (2 frames / char), blinks, gone
    OB = 12 + 2 * N
    out = Anim("CTA Out", OB + 3 * BL)
    out.key(p["cursor"].id, 7, [(0, 6, H)])
    out.key(p["cursor"].id, 18, [(0, 1, H), (OB + BL, 0, H), (OB + 2 * BL, 1, H), (OB + 3 * BL, 0, H)])
    out.key(p["reveal"].id, 7, [(0, WT, H)] + [(12 + 2 * i, WT * (N - i - 1) / N, H) for i in range(N)])
    out.key(p["corner_box"].id, 18, [(0, 1, H), (6, 0, H)])
    return hid, b, rest, out


class _Ref:
    """an artboard defined in another markup file (silly.rml), referenced by id"""
    def __init__(self, id_):
        self.id = id_


def build_main(surfs):
    W, H = 1600, 900
    main_lis = []
    names = ["clusterUI", "consoleUI", "hubUI", "hudUI", "bbRocket", "bbRive", "bbKinetic", "bbLive", "bbArcade", "bbHotel", "bbKoi", "bbAura", "bbDeep", "bbSilly"]
    world = E("ScriptedLayout",
              *[E("ScriptInputArtboard", artboardId=a.id, name=n) for n, a in zip(names, surfs)],
              E("FocusData"),
              scriptAssetId=SCRIPTS["world"], name="World", id=nid())
    stage = box("Stage", world, ws="fill", hs="fill")

    def sky(name, top, mid, bot, opacity_bind=None):
        g = lgrad([(argb(top), 0), (argb(mid), 0.55), (argb(bot), 1)], 0, 0, 0, H)
        return box(name, ws="fill", hs="fill", binds=(bind(opacity_bind, 18),) if opacity_bind else (), grad=g)
    sky_day = sky("Sky Day", "#8E9AA8", "#C3CAD2", "#D3D7DB")
    sky_night = sky("Sky Night", "#020205", "#0B0A12", "#211A1A", "night")

    # ---- title: city overview + Rive logo + GMUNK-style "ENTER THE CITY" FUI (no black screen)
    logo = box("Title Logo", node("Logo Node", E("NestedArtboard", E("NestedStateMachine", animationId=LOGO_SM, name="Logo SM"),
                                                 artboardId=LOGO_AB, name="Rive Logo", x=-76.4, y=-22, scaleX=0.554, scaleY=0.554,
                                                 dataBindPathIds=path("logo"), id=nid())),
               w=290, h=127, ws="fixed", hs="fixed", binds=(bind("logoVis", 18),))
    FW = 640
    CY_ = "#19F2FF"
    strip = []
    seg = 40
    for k in range(30):
        strip.append(shape(f"Seg {k}", rect(seg - 4, 3, x=k * seg + seg / 2, y=1.5), solid(argb(PRISM[k % 6]))))
    strip_node = node("Strip", *strip)
    loader = box("Loader", strip_node, w=240, h=3, ws="fixed", hs="fixed", clip=True, binds=(bind("loadOp", 18),))
    cta, cta_p = build_cta()
    title_col = box("Title Column", logo, cta, align="topCenter", gap=8, pad=(0, 0, 40, 0))
    # soft scrim so the white logo + FUI read over the bright golden-hour haze
    # bottom-only scrim: the sky up top stays bright, the visor UI sits on darkened city below
    scrim = box("Scrim", ws="fill", hs="fill", grad=lgrad([(argb("#000000", 0), 0), (argb("#000000", 0), 0.45), (argb("#000000", 90), 0.75),
                                                           (argb("#000000", 150), 1)], 0, 0, 0, H), binds=(bind("titleOp", 18),))
    # cinematic lower title: anchored to the bottom, sitting in the dark start-screen gradient
    title = layer("Title Overlay", title_col, align="bottomCenter", pad=(0, 0, 200, 0))
    fade = box("Fade", ws="fill", hs="fill", fill=argb(BLACK), binds=(bind("blackout", 18),))

    # screen overlay: brand tag, readout, prompts
    def pill(*kids, **kw):
        return box("Pill", *kids, dir="row", align="center", pad=kw.pop("pad", (0, 14, 0, 14)), h=30, hs="fixed", radius=15,
                   fill=argb("#0B0B0D", 205), stroke=(argb(WHITE, 26), 1), gap=10, **kw)
    # top-left pill: render-quality switch (deliberately unbranded)
    qsegs = []
    for k, lab in enumerate(("HIGH", "MED", "LOW")):
        seg_ = stack(f"Quality {lab}", box(f"Q {lab} Label", mono(f"Q {lab}", lab, 10, WHITE, ls=1.5, dec=False), pad=(0, 8, 0, 8),
                                            h=20, hs="fixed", align="center"),
                     box(f"Q {lab} On", ws="fill", hs="fill", radius=10, fill=argb(AMBER, 92), stroke=(argb(AMBER, 200), 1),
                         binds=(bind(f"qs{k}", 18),)),
                     ws="hug", hs="hug", bid=nid())
        main_lis.append(req_listener(seg_.id, 70 + k, f"Quality {lab}"))
        qsegs.append(seg_)
    qswitch = box("Quality Switch", mono("Q Label", "QUALITY", 10, MUTED, ls=1.5, dec=False), *qsegs, dir="row", align="center", gap=4)
    tag = box("Tag", pill(qswitch, pad=(0, 6, 0, 14)),
              ws="fill", align="topLeft", pad=(18, 22, 0, 22))
    readout = pill(box("Dot", w=6, h=6, ws="fixed", hs="fixed", radius=3, fill=argb(AMBER)),
                   mono("Readout Text", "AUTOPILOT", 11, WHITE, bindname="readout", ls=2))
    p = lambda *a: prompt(*a)

    def cp(key, label, code):
        # clickable keycap prompt: same request codes the console uses
        b = box(f"Prompt {key}", keycap(key), mono(f"P {key}", label, 10, WHITE, ls=1.2, dec=False), dir="row", align="center",
                gap=6, pad=(4, 4, 4, 4), radius=6, fill=argb("#FFFFFF", 1), bid=nid())
        main_lis.append(req_listener(b.id, code, f"Prompt {key}"))
        return b
    prompts = box("Prompts",
                  p(keycap("W"), keycap("A"), keycap("S"), keycap("D"), mono("P1", "DRIVE", 10, WHITE, ls=1.2, dec=False)),
                  cp("P", "AUTOPILOT", 1),
                  cp("F", "SKY LANE", 2),
                  cp("M", "MODE", 5),
                  cp("C", "CHASE", 4),
                  cp("O", "SHOWROOM", 7),
                  cp("N", "DAY/NIGHT", 3),
                  cp("T", "TRACK", 41),
                  cp("E", "STOP + PLAY", 80),
                  cp("R", "REPLAY", 6),
                  p(mono("P9", "DRAG", 10, AMBER, ls=1.2, dec=False), mono("P10", "LOOK", 10, WHITE, ls=1.2, dec=False)),
                  p(mono("P11", "CLICK", 10, AMBER, ls=1.2, dec=False), mono("P12", "SCREENS + BILLBOARDS", 10, WHITE, ls=1.2, dec=False)),
                  dir="row", gap=14, align="center", pad=(0, 14, 0, 14), h=34, hs="fixed", radius=17,
                  fill=argb("#0B0B0D", 205), stroke=(argb(WHITE, 26), 1))
    bottom = box("Bottom", readout, prompts, ws="fill", align="bottomCenter", gap=8, pad=(0, 0, 14, 0))
    overlay = layer("Overlay", layer("Overlay Bottom", bottom, align="bottomCenter"), layer("Overlay Top", tag, align="topLeft"),
                    binds=(bind("uiIn", 18),), extra={"layoutTypeValue": "stack"})

    root = box("Root", title, overlay, fade, stage, sky_night, sky_day, ws="fill", hs="fill", extra={"layoutTypeValue": "stack"})
    s, sid = style()
    ab = E("Artboard", s, root, name="Main", id=nid(), width=W, height=H, styleId=sid,
           viewModelId=VM_ID, viewModelInstanceId=VMI_ID)
    strip_anim = Anim("Loader", 60, "loop")
    # (the prism loading strip is gone; the empty "Loader" state still carries the world focus action)
    c_hid, c_b, c_rest, c_out = cta_anims(cta_p)
    ab.add(strip_anim.el, c_hid.el, c_b.el, c_rest.el, c_out.el)
    st_idle = nid()
    s_h, s_b, s_r, s_o = nid(), nid(), nid(), nid()
    finish_sm(ab, [sm_layer("Loader", st_idle, state(strip_anim, E("FocusActionTarget", targetId=world.id), sid=st_idle, x=200, y=0)),
                   sm_layer("CTA", s_h,
                            state(c_hid, go(s_b, cond("titleBuild", 0.5, "greaterThan")), sid=s_h, x=100, y=0),
                            state(c_b, go(s_r, exit_pct=100), go(s_h, cond("titleBuild", 0.5, "lessThan")), sid=s_b, x=300, y=0),
                            state(c_rest, go(s_o, cond("enterGo", 0.5, "greaterThan")), go(s_h, cond("titleBuild", 0.5, "lessThan")), sid=s_r,
                                  x=500, y=0),
                            state(c_out, go(s_h, cond("titleBuild", 0.5, "lessThan")), sid=s_o, x=700, y=0))],
              [E("StateMachineListenerSingle", E("FocusActionTarget", targetId=world.id),
                 targetId=ab.id, listenerTypeValue="down", name="Refocus World")] + main_lis, name="Main")
    return ab


SCRIPTS = {}


def pack_file(name):
    """raw mesh pack (assets/<name>.bin, written by make_city.py / make_props.py) for fast local loads;
    the compressed pack (assets/<name>.rz, tools/zpack.py) for WEB builds or when only that is present"""
    raw = f"assets/{name}.bin"
    if os.environ.get("WEB") or not os.path.exists(os.path.join(ROOT, raw)):
        return f"assets/{name}.rz"
    return raw


def main():
    for k in ("pack", "cityinfo", "cabin", "world"):
        SCRIPTS[k] = nid()
    for k in CUES:
        SCRIPTS["dec_" + k] = nid()
    row = build_track_row()
    GROUP[0] = "cl"
    cluster = build_cluster()
    GROUP[0] = "cs"
    console = build_console(row)
    GROUP[0] = "hub"
    hub = build_hub()
    GROUP[0] = "hud"
    hud = build_hud()
    GROUP[0] = "main"
    bbs = build_billboards()
    surfs = [cluster, console, hub, hud] + bbs + [_Ref("1:59684")]   # SillyScroll (silly.rml)
    mainab = build_main(surfs)
    src = open(os.path.join(ROOT, "tools", "decrypt.as.tmpl")).read()
    for k, cue in CUES.items():
        with open(os.path.join(ROOT, f"dec_{k}.as"), "w") as f:
            f.write(f"// GENERATED by tools/gen.py from tools/decrypt.as.tmpl (cue = {cue})\n" +
                    src.replace('"cueFace"', f'"{cue}"').replace("class Decrypt", f"class Decrypt_{k}"))
    comps = [a for a in surfs if not isinstance(a, _Ref)] + [row]   # _Ref artboards live in their own markup file
    doc = E("Rive",
            mainab, *comps,
            *[E("ComponentAsset", artboardId=a.id, name=a.attrs["name"]) for a in comps],
            *build_vms(),
            E("FontAsset", file="fonts/Orbitron.ttf", name="Orbitron", id=F_ORB),   # full file: "Orbitron" is a Reserved Font Name (no subsets)
            E("FontAsset", file=FONT_DIR + "Inter.ttf", name="Inter", id=F_INTER),
            E("FontAsset", file=MONO_FILE, name="Mono", id=F_MONO),
            *[E("ImageAsset", file=(f"art/{k}_a.png" if k in ("koi", "jelly", "can") else f"art/{k}.jpg"), name=k, id=v) for k, v in IMG.items()],
            E("BlobAsset", file=pack_file("city"), name="city", id=nid()),
            E("BlobAsset", file=pack_file("props"), name="props", id=nid()),
            E("BlobAsset", file="assets/tex.bin", name="tex", id=nid()),
            E("BlobAsset", file="assets/win.bin", name="win", id=nid()),
            E("ScriptAsset", file="world.as", name="world", id=SCRIPTS["world"]),
            *[E("ScriptAsset", file=f"dec_{k}.as", name=f"dec_{k}", id=SCRIPTS["dec_" + k]) for k in CUES],
            *[E("ScriptedDataConverter", id=CONV[k], scriptAssetId=SCRIPTS["dec_" + k], name=f"Decrypt {k}") for k in CUES],
            version="1", kind="fragment")
    doc.assign_ids()
    out = doc.render()
    with open(os.path.join(ROOT, "scene.rml"), "w") as f:
        f.write("<!-- GENERATED by tools/gen.py — edit the generator, not this file -->\n" + out)
    print("scene.rml:", out.count("\n"), "lines")


if __name__ == "__main__":
    main()
