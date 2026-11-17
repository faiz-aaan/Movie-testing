"""KRONOS - 15s brand film in the style of the two reference lyric videos.

Graphic language borrowed (not the people / footage):
  * bronze CG hero object (maze dial) on black, slow push-in, dust + bokeh   [ref 2]
  * wide-tracked serif credits that resolve letter by letter                   [ref 1 + 2]
  * 1-word lyric cards whose letters drop / scatter / converge                 [ref 1]
  * depth-driven camera move with rack focus over a 3D maze                    [ref 2]
  * red/yellow halftone "comic" interlude, brush type, stepped frames          [ref 2 + ref 1 red chapter]
  * title assembles from scattered letters, sparks, end card on the motif      [ref 1 + 2]

Writes raw RGB frames to ffmpeg -> build/master_24.mp4 (1920x1080, 24 fps, no grade).
"""
import math, os, subprocess, sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, "build")
F = os.path.join(HERE, "fonts")
W, H, FPS, DUR = 1920, 1080, 24, 15.0
NF = int(FPS * DUR)
rng = np.random.default_rng(42)

CUTS = dict(s2=2.5, time=3.75, s3=6.0, s4=9.0, noone=9.6, s5=11.5, title=12.05)
CREAM = np.array([236, 224, 200], np.float32)
GOLD_HI = np.array([255, 226, 160], np.float32)
GOLD_LO = np.array([150, 92, 40], np.float32)
RED = np.array([168, 22, 20], np.float32)
YEL = np.array([246, 204, 96], np.float32)


# ---------- helpers ----------
def clamp01(x): return max(0.0, min(1.0, x))
def ease_out(x): x = clamp01(x); return 1 - (1 - x) ** 3
def ease_in_out(x): x = clamp01(x); return x * x * (3 - 2 * x)
def ease_back(x, s=1.7):
    x = clamp01(x) - 1
    return x * x * ((s + 1) * x + s) + 1


def font(name, size, wght=None):
    f = ImageFont.truetype(os.path.join(F, name), size)
    if wght is not None:
        f.set_variation_by_axes([wght])
    return f


_glyphs = {}
def glyph(fnt_key, ch):
    k = (fnt_key, ch)
    if k not in _glyphs:
        f = FONTS[fnt_key]
        x0, y0, x1, y1 = f.getbbox(ch, anchor="ls")
        pad = 40
        im = Image.new("L", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), 0)
        ImageDraw.Draw(im).text((pad - x0, pad - y0), ch, font=f, fill=255, anchor="ls")
        a = np.asarray(im, np.float32) / 255
        # glyph anchor = baseline-left mapped to centre of advance
        adv = f.getlength(ch)
        cx = pad - x0 + adv / 2
        cy = pad - y0  # baseline
        _glyphs[k] = (a, cx, cy, adv)
    return _glyphs[k]


def layout(fnt_key, text, cx, baseline_y, tracking):
    """Return [(ch, x_center, baseline_y)] for tracked text centred on cx."""
    f = FONTS[fnt_key]
    advs = [f.getlength(c) for c in text]
    total = sum(advs) + tracking * (len(text) - 1)
    x = cx - total / 2
    out = []
    for c, a in zip(text, advs):
        out.append((c, x + a / 2, baseline_y))
        x += a + tracking
    return out


def stamp(mask, fnt_key, ch, x, y, scale=1.0, angle=0.0, alpha=1.0, blur=0.0):
    """Max-composite one glyph onto a float mask (H,W)."""
    if ch == " " or alpha <= 0.003:
        return
    a, gx, gy, _ = glyph(fnt_key, ch)
    M = cv2.getRotationMatrix2D((gx, gy), angle, scale)
    M[0, 2] += x - gx
    M[1, 2] += y - gy
    g = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
    if blur > 0.4:
        g = cv2.GaussianBlur(g, (0, 0), blur)
    np.maximum(mask, g * alpha, out=mask)


def over(img, mask, color, opacity=1.0):
    m = (mask * opacity)[..., None]
    return img * (1 - m) + np.asarray(color, np.float32) * m


def add(img, layer, gain=1.0):
    return img + layer * gain


def place_rgba(rgba_f, scale, angle, cx, cy):
    """Warp a float RGBA sprite into frame space; returns (rgb, alpha)."""
    h, w = rgba_f.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    M[0, 2] += cx - w / 2
    M[1, 2] += cy - h / 2
    out = cv2.warpAffine(rgba_f, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    return out[..., :3], out[..., 3:4]


# ---------- assets ----------
FONTS = {
    "cinzel": font("Cinzel.ttf", 56, 600),
    "cinzel_sm": font("Cinzel.ttf", 30, 600),
    "cinzel_big": font("Cinzel.ttf", 196, 800),
    "bebas": font("BebasNeue-Regular.ttf", 330),
    "bebas2": font("BebasNeue-Regular.ttf", 300),
    "marker": font("PermanentMarker-Regular.ttf", 200),
    "marker_sm": font("PermanentMarker-Regular.ttf", 120),
}

def load_rgba(p):
    a = np.asarray(Image.open(p).convert("RGBA"), np.float32)
    a[..., :3] *= a[..., 3:4] / 255  # premultiply
    a[..., 3] /= 255
    return a

DISC = load_rgba(os.path.join(B, "disc.png"))
RING = load_rgba(os.path.join(B, "disc_ring.png"))
FIELD = np.asarray(Image.open(os.path.join(B, "field.png")).convert("RGB"), np.float32)
DEPTH = np.asarray(Image.open(os.path.join(B, "field_depth.png")).convert("L"), np.float32) / 255

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rr = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
VIGNETTE = np.clip(1.15 - 0.55 * rr ** 1.8, 0.25, 1)[..., None]
BG_DARK = (np.array([34, 22, 13], np.float32) * np.clip(1 - rr * 0.8, 0, 1)[..., None] ** 1.5)

# grunge for distressed type
gr = rng.normal(0, 1, (H // 4, W // 4)).astype(np.float32)
gr = cv2.resize(cv2.GaussianBlur(gr, (0, 0), 1.2), (W, H))
GRUNGE = np.clip((gr - 0.9) * 2.5, 0, 1)  # specks to cut out of letters
scr = np.zeros((H, W), np.float32)
for _ in range(90):
    x0, y0 = rng.uniform(0, W), rng.uniform(0, H)
    ang, ln = rng.uniform(-0.4, 0.4), rng.uniform(20, 160)
    cv2.line(scr, (int(x0), int(y0)), (int(x0 + ln * math.cos(ang)), int(y0 + ln * math.sin(ang))), 1.0, 1, cv2.LINE_AA)
GRUNGE = np.clip(GRUNGE + scr * 0.8, 0, 1)

GRAIN = [rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]

# particles
ND = 260
dust = dict(x=rng.uniform(0, W, ND), y=rng.uniform(0, H, ND), vx=rng.normal(6, 10, ND), vy=rng.normal(-8, 6, ND),
            r=rng.uniform(0.8, 2.6, ND), b=rng.uniform(0.25, 1.0, ND), ph=rng.uniform(0, 6.28, ND))
NB = 14
bok = dict(x=rng.uniform(0, W, NB), y=rng.uniform(0, H, NB), r=rng.uniform(25, 85, NB), vx=rng.normal(0, 8, NB), b=rng.uniform(0.15, 0.4, NB))


def dust_layer(t, gain=1.0, warm=(255, 200, 140)):
    lay = np.zeros((H, W), np.float32)
    x = (dust["x"] + dust["vx"] * t) % W
    y = (dust["y"] + dust["vy"] * t) % H
    tw = 0.6 + 0.4 * np.sin(dust["ph"] + t * 3)
    for i in range(ND):
        cv2.circle(lay, (int(x[i] * 4), int(y[i] * 4)), int(dust["r"][i] * 4), float(dust["b"][i] * tw[i]), -1, cv2.LINE_AA, 2)
    lay = cv2.GaussianBlur(lay, (0, 0), 1.3)
    bl = np.zeros((H, W), np.float32)
    bx = (bok["x"] + bok["vx"] * t) % W
    for i in range(NB):
        cv2.circle(bl, (int(bx[i]), int(bok["y"][i])), int(bok["r"][i]), float(bok["b"][i]), -1, cv2.LINE_AA)
    bl = cv2.GaussianBlur(bl, (0, 0), 6)
    return (lay[..., None] * 0.9 + bl[..., None] * 0.35) * np.array(warm, np.float32) * gain


class Sparks:
    def __init__(self, t0, cx, cy, n=170, seed=1):
        r = np.random.default_rng(seed)
        ang = r.uniform(0, 2 * np.pi, n)
        sp = r.uniform(250, 1300, n)
        self.t0, self.cx, self.cy = t0, cx, cy
        self.vx, self.vy = np.cos(ang) * sp, np.sin(ang) * sp * 0.6 - 150
        self.life = r.uniform(0.4, 1.4, n)

    def layer(self, t):
        lay = np.zeros((H, W), np.float32)
        dt = t - self.t0
        if dt < 0 or dt > 1.6:
            return lay[..., None] * 0
        drag = (1 - np.exp(-dt * 2.2)) / 2.2
        x = self.cx + self.vx * drag
        y = self.cy + self.vy * drag + 420 * dt * dt
        tx = x - self.vx * np.exp(-dt * 2.2) * 0.035
        ty = y - (self.vy * np.exp(-dt * 2.2) + 840 * dt) * 0.035
        a = np.clip(1 - dt / self.life, 0, 1)
        for i in range(len(x)):
            if a[i] > 0:
                cv2.line(lay, (int(tx[i] * 4), int(ty[i] * 4)), (int(x[i] * 4), int(y[i] * 4)), float(a[i]), 1, cv2.LINE_AA, 2)
        glow = cv2.GaussianBlur(lay, (0, 0), 4)
        return (lay * 1.4 + glow * 2.5)[..., None] * np.array([255, 190, 110], np.float32)


def flash(t, at, gain=0.55, decay=0.09, color=(255, 200, 140)):
    if t < at:
        return 0.0
    return np.array(color, np.float32) * gain * math.exp(-(t - at) / decay)


def logo_bug(img, opacity=0.55):
    m = np.zeros((H, W), np.float32)
    cv2.circle(m, (1830, 84), 30, 1.0, 2, cv2.LINE_AA)
    stamp(m, "cinzel_sm", "K", 1830, 95, 1.0)
    return over(img, m, CREAM, opacity)


# ---------- shots ----------
def shot1(t):
    """0-2.5  credits resolve letter by letter in dust and a light sweep."""
    img = BG_DARK.copy()
    sweep = np.exp(-(((xx - (-300 + t * 1000)) * 0.8 + (yy - 540) * 0.5) / 260) ** 2)[..., None]
    img = add(img, sweep * np.array([70, 45, 25], np.float32))
    img = add(img, dust_layer(t, 0.55))
    m = np.zeros((H, W), np.float32)
    r = np.random.default_rng(3)
    line1 = layout("cinzel", "KRONOS HOROLOGY", W / 2, 540, 30)
    starts = r.uniform(0.25, 1.25, len(line1))
    for (c, x, y), s in zip(line1, starts):
        p = ease_out((t - s) / 0.7)
        stamp(m, "cinzel", c, x, y - 10 * (1 - p), 1.0, 0, p, 9 * (1 - p))
    for c, x, y in layout("cinzel_sm", "PRESENTS", W / 2, 612, 22):
        p = ease_out((t - 1.45) / 0.6)
        stamp(m, "cinzel_sm", c, x, y, 1.0, 0, p * 0.8, 4 * (1 - p))
    out_fade = 1 - ease_in_out((t - 2.15) / 0.35)
    img = over(img, m * out_fade, CREAM)
    return img


def disc_frame(t, scale, cx=960, cy=560, darken=1.0, spin=8.0):
    img = BG_DARK.copy()
    rgb, a = place_rgba(DISC, scale, 20 + spin * t, cx, cy)
    img = img * (1 - a) + rgb * darken
    rgb2, a2 = place_rgba(RING, scale * 1.03, -14 * t, cx, cy)
    img = img * (1 - a2) + rgb2 * darken
    # travelling specular light across the metal
    lx = cx + math.cos(t * 0.9) * 500 * scale
    spec = np.exp(-(((xx - lx) / (380 * scale)) ** 2 + ((yy - (cy - 250 * scale)) / (300 * scale)) ** 2))[..., None]
    img = img + spec * a * np.array([120, 80, 40], np.float32) * darken
    return img


def shot2(t):
    """2.5-6.0  bronze maze dial push-in; 'TIME' drops in on the beat."""
    lt = t - CUTS["s2"]
    hit = lt - (CUTS["time"] - CUTS["s2"])
    punch = 0.035 * math.exp(-max(hit, 0) / 0.18) if hit >= 0 else 0
    s = 0.60 + 0.14 * ease_in_out(lt / 3.5) + punch
    dk = 1.0 - 0.35 * ease_out(hit / 0.4) if hit >= 0 else 1.0
    img = disc_frame(lt, s, darken=dk)
    img = add(img, dust_layer(t, 0.8))
    if hit >= -0.1:
        m = np.zeros((H, W), np.float32)
        for i, (c, x, y) in enumerate(layout("bebas", "TIME", W / 2, 680, 46)):
            p = (hit - 0.06 * i) / 0.32
            if p <= 0:
                continue
            e = ease_back(p, 1.3)
            stamp(m, "bebas", c, x, y - 220 * (1 - e), 1.0 + 0.25 * (1 - ease_out(p)), 0, clamp01(p * 2), 10 * (1 - clamp01(p)))
        m *= 1 - GRUNGE * 0.85
        shadow = cv2.GaussianBlur(m, (0, 0), 18)
        img = img * (1 - 0.6 * shadow[..., None])
        img = over(img, m, CREAM)
    # small credit, ref-2 style wide tracking
    m2 = np.zeros((H, W), np.float32)
    p = ease_out((lt - 0.4) / 0.8) * (1 - ease_out((lt - 2.6) / 0.5))
    for c, x, y in layout("cinzel_sm", "CALIBRE  K-01  AUTOMATIC", W / 2, 1010, 16):
        stamp(m2, "cinzel_sm", c, x, y, 1.0, 0, p * 0.75)
    img = over(img, m2, CREAM)
    img = add(img, np.ones((1, 1, 1), np.float32) * flash(t, CUTS["s2"]))
    img = add(img, np.ones((1, 1, 1), np.float32) * flash(t, CUTS["time"], 0.25, 0.12))
    return logo_bug(img)


def shot3(t):
    """6.0-9.0  Depth-Anything parallax push over the maze + rack focus; 'BENDS' warps."""
    lt = t - CUTS["s3"]
    e = ease_in_out(lt / 3.0) + 0.35 * clamp01((lt - 2.0) / 1.0) ** 2  # accelerate into the cut
    cx, cy = W / 2, 330
    sc = 1.0 + e * (0.05 + 0.30 * DEPTH)
    mapx = (cx + (xx - cx) / sc).astype(np.float32)
    mapy = (cy + (yy - cy) / sc - 60 * e * DEPTH).astype(np.float32)
    img = cv2.remap(FIELD, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    d = cv2.remap(DEPTH, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    focus = 0.15 + 0.55 * ease_in_out(lt / 2.6)
    blur = cv2.GaussianBlur(img, (0, 0), 7)
    k = np.clip(np.abs(d - focus) * 3.2, 0, 1)[..., None]
    img = img * (1 - k) + blur * k
    sunp = 1 + 0.25 * math.sin(lt * 5)
    img = add(img, np.exp(-(((xx - W * 0.62) / 260) ** 2 + ((yy - 300) / 160) ** 2))[..., None] * np.array([120, 70, 30], np.float32) * sunp)
    img = add(img, dust_layer(t, 1.1, (255, 215, 160)))
    # BENDS: letters slide in with rotation, then the whole word bends on a sine wave
    m = np.zeros((H, W), np.float32)
    for i, (c, x, y) in enumerate(layout("bebas2", "BENDS", W / 2, 560, 40)):
        p = (lt - 0.35 - 0.07 * i) / 0.45
        if p <= 0:
            continue
        e2 = ease_out(p)
        stamp(m, "bebas2", c, x + (1 - e2) * (300 + 80 * i), y, 1.0, (1 - e2) * -35, clamp01(p * 1.5), 8 * (1 - clamp01(p)))
    amp = 26 * math.sin(lt * 3.1) * (0.4 + 0.6 * clamp01(lt - 0.8))
    wy = (yy + amp * np.sin(xx / 210 + lt * 4)).astype(np.float32)
    m = cv2.remap(m, xx, wy, cv2.INTER_LINEAR)
    m *= 1 - GRUNGE * 0.85
    m *= 1 - ease_in_out((lt - 2.55) / 0.3)
    sh = cv2.GaussianBlur(m, (0, 0), 16)
    img = img * (1 - 0.5 * sh[..., None])
    img = over(img, m, CREAM)
    leak = clamp01((lt - 2.3) / 0.7) ** 2
    img = add(img, np.exp(-(((xx - W * 0.7) / 700) ** 2))[..., None] * np.array([255, 150, 70], np.float32) * leak * 0.9)
    img = add(img, np.ones((1, 1, 1), np.float32) * flash(t, CUTS["s3"], 0.5))
    return logo_bug(img)


# halftone helpers
CELL = 10
HX = (xx % CELL) - CELL / 2 + 0.5
HY = (yy % CELL) - CELL / 2 + 0.5
HD = np.hypot(HX, HY)


def halftone(gray):
    small = cv2.resize(gray, (W // CELL, H // CELL), interpolation=cv2.INTER_AREA)
    up = cv2.resize(small, (W, H), interpolation=cv2.INTER_NEAREST)
    r = np.sqrt(np.clip(up, 0, 1)) * CELL * 0.72
    dots = np.clip(r - HD + 0.5, 0, 1)[..., None]
    col = np.where((up > 0.55)[..., None], YEL, RED)
    base = RED * 0.22 * np.clip(gray * 1.6, 0, 1)[..., None]
    return base + dots * col


def shot4(t):
    """9.0-11.5  red/yellow halftone chapter, stepped frames, brush type, ink wipe."""
    lt = t - CUTS["s4"]
    st = math.floor(lt * 12) / 12  # 12 fps stop-motion feel
    if st < 1.35:
        src = disc_frame(st * 6, 1.25 + 0.15 * st, 960, 540, spin=40)
    else:
        sc = 1.15 + 0.2 * (st - 1.35)
        mapx = (W / 2 + (xx - W / 2) / sc).astype(np.float32)
        mapy = (330 + (yy - 330) / sc).astype(np.float32)
        src = cv2.remap(FIELD, mapx, mapy, cv2.INTER_LINEAR)
    g = cv2.cvtColor(np.clip(src, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    g = np.clip((g - 0.12) * 1.9, 0, 1)
    img = halftone(g)
    jr = np.random.default_rng(int(st * 12) + 7)
    m = np.zeros((H, W), np.float32)
    for c, x, y in layout("marker", "FOR", 620, 470, 6):
        p = clamp01((lt - 0.05) / 0.12)
        stamp(m, "marker", c, x + jr.normal(0, 3), y + jr.normal(0, 3), 1.0 + 0.3 * (1 - p), -6, p)
    hit = lt - (CUTS["noone"] - CUTS["s4"])
    for i, (c, x, y) in enumerate(layout("marker", "NO ONE", 1080, 700, 4)):
        p = clamp01((hit - 0.04 * i) / 0.1)
        stamp(m, "marker", c, x + jr.normal(0, 4), y + jr.normal(0, 4), 1.0 + 0.5 * (1 - p), -6 + jr.normal(0, 1.5), p)
    m *= 1 - GRUNGE * 0.6
    img = over(img, m, YEL)
    # glitch: shift a few row bands on beats
    if (lt % 0.3125) < 0.06:
        for _ in range(4):
            y0 = int(jr.uniform(0, H - 80)); hgt = int(jr.uniform(12, 70))
            img[y0:y0 + hgt] = np.roll(img[y0:y0 + hgt], int(jr.normal(0, 60)), axis=1)
    # ink swipes to black
    wipe = np.zeros((H, W), np.float32)
    for k in range(4):
        p = ease_in_out((lt - 1.75 - 0.1 * k) / 0.45)
        if p <= 0:
            continue
        y0 = 120 + k * 260
        pts = np.array([[-200, y0], [-200 + p * 2500, y0 - 180], [-200 + p * 2500, y0 + 200], [-200, y0 + 380]], np.int32)
        cv2.fillPoly(wipe, [pts], 1.0, cv2.LINE_AA)
    wipe = np.clip(wipe - GRUNGE * 0.5 * (wipe < 0.99), 0, 1)
    img = over(img, wipe, RED * 0.55)
    img = img * (1 - ease_in_out((lt - 2.25) / 0.25))
    # letterbox panel like the reference interlude
    img[:110] *= 0.0
    img[-110:] *= 0.0
    img = add(img, np.ones((1, 1, 1), np.float32) * flash(t, CUTS["s4"], 0.7, 0.07, (255, 120, 80)))
    return logo_bug(img, 0.4)


SPARKS = Sparks(CUTS["title"], 960, 500)
GOLD_GRAD = (GOLD_LO + (GOLD_HI - GOLD_LO) * np.clip(1 - (yy[..., None] - 360) / 220, 0, 1)).astype(np.float32)


def shot5(t):
    """11.5-15  end card: title assembles from scattered letters, sparks, tagline."""
    lt = t - CUTS["s5"]
    img = disc_frame(lt + 3, 1.55 + 0.05 * lt, 960, 620, darken=0.30, spin=3)
    img = cv2.GaussianBlur(img, (0, 0), 3)
    img = add(img, dust_layer(t, 0.7))
    m = np.zeros((H, W), np.float32)
    r = np.random.default_rng(11)
    land = CUTS["title"] - CUTS["s5"]
    letters = layout("cinzel_big", "KRONOS", W / 2, 560, 58)
    for i, (c, x, y) in enumerate(letters):
        ox, oy, oa = r.uniform(-700, 700), r.uniform(-380, 380), r.uniform(-60, 60)
        p = (lt - (land - 0.5) - 0.03 * i) / 0.5
        if p <= 0:
            continue
        e = ease_out(p)
        stamp(m, "cinzel_big", c, x + ox * (1 - e), y + oy * (1 - e), 1.0 + 0.6 * (1 - e), oa * (1 - e), clamp01(p * 1.6), 14 * (1 - clamp01(p)))
    shine = np.exp(-((xx - (-400 + max(lt - 1.3, 0) * 1700) + (yy - 450) * 0.6) / 90) ** 2)[..., None]
    col = GOLD_GRAD + shine * 160
    glow = cv2.GaussianBlur(m, (0, 0), 30)[..., None]
    img = img + glow * np.array([200, 120, 50], np.float32) * 0.5
    img = img * (1 - m[..., None]) + col * m[..., None]
    m2 = np.zeros((H, W), np.float32)
    p = ease_out((lt - 1.25) / 0.9)
    for c, x, y in layout("cinzel", "TIME BENDS FOR NO ONE", W / 2, 690, 14 + 16 * p):
        stamp(m2, "cinzel", c, x, y, 0.62, 0, p)
    p3 = ease_out((lt - 2.0) / 0.7)
    for c, x, y in layout("cinzel_sm", "AUTOMATIC CHRONOGRAPH  -  EST. 2026", W / 2, 990, 12):
        stamp(m2, "cinzel_sm", c, x, y, 0.8, 0, p3 * 0.95)
    img = over(img, m2, CREAM)
    img = add(img, SPARKS.layer(t))
    img = add(img, np.ones((1, 1, 1), np.float32) * flash(t, CUTS["title"], 0.45, 0.12))
    img = img * (1 - ease_in_out((lt - 2.9) / 0.6))
    return img


def frame(i):
    t = i / FPS
    if t < CUTS["s2"]:
        img = shot1(t)
    elif t < CUTS["s3"]:
        img = shot2(t)
    elif t < CUTS["s4"]:
        img = shot3(t)
    elif t < CUTS["s5"]:
        img = shot4(t)
    else:
        img = shot5(t)
    # global film finish: vignette, flicker, grain, gentle gate weave
    img = img * VIGNETTE * (1 + 0.02 * math.sin(i * 1.7) * math.sin(i * 0.37))
    g = cv2.resize(GRAIN[i % len(GRAIN)], (W, H))[..., None]
    img = img + g * 7
    dx, dy = 1.2 * math.sin(i * 0.9), 0.8 * math.sin(i * 1.3 + 1)
    img = cv2.warpAffine(img.astype(np.float32), np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REFLECT)
    return np.clip(img, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stills":
        for s in sys.argv[2:]:
            i = int(float(s) * FPS)
            Image.fromarray(frame(i)).save(os.path.join(B, f"still_{s}.jpg"), quality=90)
        sys.exit()
    out = os.path.join(B, "master_24.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for i in range(NF):
        ff.stdin.write(frame(i).tobytes())
        if i % 24 == 0:
            print(f"frame {i}/{NF}", flush=True)
    ff.stdin.close(); ff.wait()
    print("master ->", out)
