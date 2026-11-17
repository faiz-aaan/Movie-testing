"""Turn Higgsfield stills into short brand films using the PDF's "depth" step.

  python3 stills_to_film.py calm|energetic

Depth Anything V2 (Small) -> per-image depth map -> 2.5D camera move (parallax + rack
focus) -> steam / dust / bloom / grade / grain -> titles -> original score -> mp4.
No AI video model is used: every camera move is computed here.
"""
import math, os, subprocess, sys
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
HF = os.path.join(HERE, "higgsfield")
FONTS = os.path.join(HERE, "..", "demo", "fonts")
BUILD = os.path.join(HERE, "build")
FILM = sys.argv[1] if len(sys.argv) > 1 else "calm"
W, H, FPS = 1920, 1080, 24
rng = np.random.default_rng(3)
os.makedirs(BUILD, exist_ok=True)


# ---------- depth (PDF tool 2: Depth Anything V2 Small) ----------
def depth_of(path):
    cache = os.path.join(BUILD, "depth_" + os.path.basename(path) + ".npy")
    if os.path.exists(cache):
        return np.load(cache)
    import torch
    from transformers import pipeline
    pipe = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=-1)
    d = np.array(pipe(Image.open(path).convert("RGB"))["predicted_depth"].squeeze(), np.float32)
    d = (d - d.min()) / (d.max() - d.min() + 1e-6)
    d = cv2.GaussianBlur(cv2.resize(d, (W, H), interpolation=cv2.INTER_CUBIC), (0, 0), 3)
    np.save(cache, d)
    return d


def load(name):
    p = os.path.join(HF, name)
    img = cv2.resize(cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2RGB), (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    return img, depth_of(p)


yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
RR = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
VIG = np.clip(1.12 - 0.42 * RR ** 2, 0.3, 1)[..., None]
GRAIN = [rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(8)]

noise = np.zeros((1024, 1024), np.float32)
for s, a in ((4, 1.0), (8, 0.55), (16, 0.3), (32, 0.15)):
    noise += a * cv2.resize(rng.normal(0, 1, (s, s)).astype(np.float32), (1024, 1024), interpolation=cv2.INTER_CUBIC)
noise = (noise - noise.min()) / (noise.max() - noise.min())

ND = 140
DUST = dict(x=rng.uniform(0, W, ND), y=rng.uniform(0, H, ND), vx=rng.normal(5, 8, ND), vy=rng.normal(-9, 5, ND),
            r=rng.uniform(1.0, 3.0, ND), b=rng.uniform(0.3, 1.0, ND), ph=rng.uniform(0, 6.28, ND))


def clamp01(v): return max(0.0, min(1.0, v))
def ease_io(u): u = clamp01(u); return u * u * (3 - 2 * u)
def ease_out(u): u = clamp01(u); return 1 - (1 - u) ** 3


def dust(img, t, gain):
    lay = np.zeros((H, W), np.float32)
    x = (DUST["x"] + DUST["vx"] * t) % W; y = (DUST["y"] + DUST["vy"] * t) % H
    tw = 0.6 + 0.4 * np.sin(DUST["ph"] + t * 3)
    for i in range(ND):
        cv2.circle(lay, (int(x[i]), int(y[i])), max(1, int(DUST["r"][i])), float(DUST["b"][i] * tw[i]), -1, cv2.LINE_AA)
    lay = cv2.GaussianBlur(lay, (0, 0), 1.6)
    return img + lay[..., None] * np.array([255, 205, 150], np.float32) * gain


def steam(img, x, y, scale, t, strength=0.6, rise=0.1):
    ws, hs = int(260 * scale), int(620 * scale)
    x0, y0 = int(x - ws / 2), int(y - hs)
    X0, Y0, X1, Y1 = max(x0, 0), max(y0, 0), min(x0 + ws, W), min(int(y), H)
    if X1 <= X0 or Y1 <= Y0: return img
    gy, gx = np.mgrid[Y0:Y1, X0:X1].astype(np.float32)
    v = (y - gy) / hs; u = (gx - x) / ws
    sway = 0.18 * np.sin(v * 5 + t * 1.3) * v
    mask = np.exp(-((u - sway) / (0.10 + 0.32 * v)) ** 2) * np.clip(v * 8, 0, 1) * np.clip((1 - v) * 1.6, 0, 1)
    mx = ((u * 1.4 + 0.5 + 0.3 * np.sin(v * 3 + t * 0.7)) * 512) % 1024
    my = ((v * 1.6 - t * rise) * 512) % 1024
    n = cv2.remap(noise, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    d = (np.clip((n - 0.42) * 3.2, 0, 1) * mask * strength)[..., None]
    reg = img[Y0:Y1, X0:X1]
    img[Y0:Y1, X0:X1] = reg + (np.array([255, 240, 225], np.float32) - reg) * d * 0.55
    return img


def bloom(img, thr, gain, sigma, tint):
    l = img.max(-1, keepdims=True)
    hi = img * np.clip((l - thr) / (255 - thr), 0, 1)
    g = cv2.GaussianBlur(cv2.resize(hi, (W // 4, H // 4), interpolation=cv2.INTER_AREA), (0, 0), sigma / 4)
    return img + cv2.resize(g, (W, H)) * gain * np.array(tint, np.float32)


def grade(img, kind):
    x = np.clip(img / 255, 0, 1)
    lum = (x * [0.2126, 0.7152, 0.0722]).sum(-1, keepdims=True)
    if kind == "energetic":
        x = lum + (x - lum) * 1.1
        x = x + 0.10 * (x - 0.5) * (1 - np.abs(x - 0.5) * 2)
        x = x + np.clip(lum - 0.55, 0, 1) * np.array([0.05, 0.02, -0.03])
    else:
        x = lum + (x - lum) * 0.9
        x = 0.02 + x * 0.97
        x = x + np.clip(0.35 - lum, 0, 1) * np.array([-0.02, 0.015, 0.04]) + np.clip(lum - 0.45, 0, 1) * np.array([0.05, 0.02, -0.04])
    return np.clip(x, 0, 1) * 255


_txt = {}
def text_mask(s, font, size, track=0, wght=None):
    k = (s, font, size, track, wght)
    if k not in _txt:
        f = ImageFont.truetype(os.path.join(FONTS, font), size)
        if wght: f.set_variation_by_axes([wght])
        ws = [f.getlength(c) for c in s]
        a = Image.new("L", (int(sum(ws) + track * (len(s) - 1)) + 40, int(size * 1.5)), 0); d = ImageDraw.Draw(a)
        x = 20
        for c, w_ in zip(s, ws):
            d.text((x, int(size * 0.2)), c, font=f, fill=255); x += w_ + track
        _txt[k] = np.asarray(a, np.float32) / 255
    return _txt[k]


def put(img, m, cx, cy, color, alpha=1.0, scale=1.0, shadow=0.0):
    if alpha <= 0.002: return img
    if scale != 1.0:
        m = cv2.resize(m, (max(1, int(m.shape[1] * scale)), max(1, int(m.shape[0] * scale))), interpolation=cv2.INTER_LINEAR)
    h, w = m.shape; x0, y0 = int(cx - w / 2), int(cy - h / 2)
    X0, Y0, X1, Y1 = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if X1 <= X0 or Y1 <= Y0: return img
    mm = m[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0][..., None] * alpha
    if shadow:
        img[Y0:Y1, X0:X1] *= 1 - cv2.GaussianBlur(mm[..., 0], (0, 0), 14)[..., None] * shadow
    img[Y0:Y1, X0:X1] = img[Y0:Y1, X0:X1] * (1 - mm) + np.array(color, np.float32) * mm
    return img


# ---------- 2.5D camera ----------
def parallax(img, d, e, zoom=0.08, zpar=0.10, panx=0.0, pany=0.0, focus=None, blur=0.0, roll=0.0):
    sc = 1 + e * (zoom + zpar * d)
    cx, cy = W / 2, H / 2
    mapx = (cx + (xx - cx) / sc + panx * e * (d - 0.35)).astype(np.float32)
    mapy = (cy + (yy - cy) / sc + pany * e * (d - 0.35)).astype(np.float32)
    if roll:
        a = math.radians(roll * e); c, s = math.cos(a), math.sin(a)
        rx, ry = mapx - cx, mapy - cy
        mapx, mapy = (cx + rx * c - ry * s).astype(np.float32), (cy + rx * s + ry * c).astype(np.float32)
    out = cv2.remap(img, mapx, mapy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    if focus is not None and blur > 0:
        dw = cv2.remap(d, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        k = np.clip(np.abs(dw - focus) * 2.6 - 0.06, 0, 1)[..., None]
        out = out * (1 - k) + cv2.GaussianBlur(out, (0, 0), blur) * k
    return out


CREAM, ORANGE, INK = (245, 236, 220), (236, 98, 34), (18, 12, 9)

# ---------- film definitions ----------
if FILM == "calm":
    DUR, DISSOLVE = 16.0, 0.7
    SHOTS = [  # image, start, end, camera kwargs, extras
        ("soul_rain.png", 0.0, 4.6, dict(zoom=0.10, zpar=0.12, panx=-60, focus=(0.5, 0.2), blur=5), {"caption": ("it's raining again.", 0.8, 4.0)}),
        ("soul_pendants.png", 4.0, 7.6, dict(zoom=0.06, zpar=0.16, panx=70, pany=-18, focus=(0.3, 0.7), blur=6), {}),
        ("soul_rain_table.png", 7.0, 11.2, dict(zoom=0.12, zpar=0.12, panx=-50, focus=(0.7, 0.3), blur=5),
         {"steam": (1029, 826, 0.55, 0.45), "caption": ("slow down.", 7.8, 10.6)}),
        ("soul_grouphead.png", 10.6, 13.6, dict(zoom=0.05, zpar=0.12, panx=40, focus=(0.5, 0.5), blur=4), {"caption": ("stay a while.", 11.2, 13.4)}),
        ("soul_rain.png", 13.0, 16.0, dict(zoom=0.04, zpar=0.06, focus=(0.5, 0.5), blur=0), {"endcard": True}),
    ]
    AUDIO = lambda: audio_calm()
else:
    DUR, DISSOLVE = 10.0, 0.0
    SHOTS = [
        ("z_espresso.png", 0.0, 2.0, dict(zoom=0.16, zpar=0.20, panx=40, focus=(0.7, 0.4), blur=6), {"title": ("FRESH", 0.25)}),
        ("z_beans.png", 2.0, 3.5, dict(zoom=0.12, zpar=0.24, panx=-80, pany=20, focus=(0.9, 0.4), blur=7, roll=3), {"title": ("ROASTED", 0.2)}),
        ("z_latte_top.png", 3.5, 5.0, dict(zoom=0.14, zpar=0.12, panx=50, roll=-4, focus=(0.6, 0.6), blur=5), {"title": ("DAILY", 0.2)}),
        ("z_wide_energetic.png", 5.0, 7.0, dict(zoom=0.10, zpar=0.28, panx=-110, pany=-10, focus=(0.2, 0.6), blur=6), {"title": ("YOUR NEW SPOT", 0.3)}),
        ("z_espresso.png", 7.0, 10.0, dict(zoom=0.03, zpar=0.04, focus=(0.5, 0.5), blur=0), {"endcard": True}),
    ]
    AUDIO = lambda: audio_energetic()

CACHE = {}
def get(name):
    if name not in CACHE: CACHE[name] = load(name)
    return CACHE[name]


def shot_img(idx, t):
    name, s, e_, cam, ex = SHOTS[idx]
    img, d = get(name)
    lt = t - s
    u = ease_io(lt / (e_ - s)) if FILM == "calm" else ease_out(lt / (e_ - s))
    kw = dict(cam)
    f0, f1 = kw.pop("focus"); kw["focus"] = f0 + (f1 - f0) * u
    out = parallax(img, d, u, **kw)
    if "steam" in ex:
        x, y, sc_, st = ex["steam"]
        out = steam(out, x, y, sc_, t, st, 0.08)
    if ex.get("endcard"):
        out = out * (0.42 if FILM == "calm" else 0.30)
    return out


def audio_calm():
    out = os.path.join(BUILD, "stills_calm.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-t", "16", "-i", os.path.join(BUILD, "score_calm.wav"),
                    "-af", "afade=t=out:st=13.5:d=2.5", out], check=True)
    return out


def audio_energetic():
    sys.path.insert(0, HERE)
    import scores as S
    T = S.Track(10.0); beat = 0.5
    T.put(0.15, S.pour(1.5), 0.9); T.put(2.0, S.rattle(1.4), 0.8, 0.2); T.put(3.45, S.hat(True), 0.6)
    for cut in (2.0, 3.5, 5.0):
        T.put(cut - 0.35, S.whoosh(0.4), 0.8); T.put(cut, S.kick(1.2), 1.0)
    T.put(6.2, S.riser(0.8), 1.0)
    T.put(7.0, S.kick(1.4), 1.0); T.put(7.0, S.braam(2.4, 36.7), 0.9)
    t = 0.0
    while t < 6.4:
        pos = round((t % 2.0) / 0.125)
        if pos in (0, 8): T.put(t, S.kick(), 0.8)
        if pos in (4, 12): T.put(t, S.clap(), 0.65)
        T.put(t, S.hat(open_=(pos % 4 == 2)), 0.35 if pos % 2 else 0.5, 0.3)
        if pos in (0, 6, 8, 11): T.put(t, S.sub([41.2, 49.0][int(t // 2) % 2], 0.3), 0.7)
        t += 0.125
    T.reverb(0.1, 0.4)
    p = os.path.join(BUILD, "stills_energetic.wav"); T.write(p, 0.4)
    return p


def frame(i):
    t = i / FPS
    idx = max(k for k, sh in enumerate(SHOTS) if sh[1] <= t) if any(sh[1] <= t for sh in SHOTS) else 0
    # in a dissolve window, blend with the next shot
    cur = idx
    nxt = idx + 1 if idx + 1 < len(SHOTS) else None
    img = shot_img(cur, t)
    if DISSOLVE and nxt is not None:
        k0 = SHOTS[nxt][1]
        if t >= k0 - 1e-6 or False:
            pass
        # incoming shot starts at its own start; fade over the first DISSOLVE seconds
    if DISSOLVE and cur > 0:
        a = clamp01((t - SHOTS[cur][1]) / DISSOLVE)
        if a < 1:
            img = shot_img(cur - 1, min(t, SHOTS[cur - 1][2])) * (1 - a) + img * a
    name, s, e_, cam, ex = SHOTS[cur]
    lt = t - s
    if "title" in ex:
        txt, t0 = ex["title"]
        p = (lt - t0) / 0.16
        if p > 0 and lt < (e_ - s) - 0.1:
            img = put(img, text_mask(txt, "BebasNeue-Regular.ttf", 210, 22), W / 2, H * 0.80, CREAM, clamp01(p * 2), 1.5 - 0.5 * ease_out(p), shadow=0.7)
    if "caption" in ex:
        txt, a0, a1 = ex["caption"]
        a = clamp01((t - a0) / 0.8) * clamp01((a1 - t) / 0.8)
        img = put(img, text_mask(txt, "CormorantGaramond-Italic.ttf", 64, 3, 400), W / 2, H - 215, CREAM, a * 0.95, 1.0, shadow=0.5)
    if ex.get("endcard"):
        a = ease_out((lt - 0.4) / 0.8)
        if FILM == "calm":
            img = put(img, text_mask("EMBER ROAST", "Cinzel.ttf", 96, 36, 600), W / 2, H / 2 - 20, CREAM, a * 0.97, 1.0, shadow=0.6)
            img = put(img, text_mask("open late, every night", "CormorantGaramond-Italic.ttf", 50, 2, 400), W / 2, H / 2 + 70, CREAM, ease_out((lt - 1.2) / 0.8) * 0.85, 1.0)
        else:
            m = text_mask("EMBER ROAST", "BebasNeue-Regular.ttf", 240, 26)
            glow = np.zeros((H, W, 3), np.float32); glow = put(glow, m, W / 2, H / 2 - 40, ORANGE, a, 1.15 - 0.15 * a)
            img = img + cv2.GaussianBlur(glow, (0, 0), 25) * 1.2
            img = put(img, m, W / 2, H / 2 - 40, ORANGE, a, 1.15 - 0.15 * a)
            img = put(img, text_mask("OPEN DAILY  /  7AM  /  @EMBERROAST", "Cinzel.ttf", 34, 10, 600), W / 2, H / 2 + 120, CREAM, ease_out((lt - 0.5) / 0.5) * 0.9)
    # finish
    img = dust(img, t, 0.5 if FILM == "calm" else 0.35)
    if FILM == "energetic":
        img = bloom(img, 170, 0.5, 30, (1.0, 0.85, 0.7)); img = grade(img, "energetic")
        if lt < 0.14 and cur > 0:
            sft = int(12 * (1 - lt / 0.14)); img[..., 0] = np.roll(img[..., 0], sft, 1); img[..., 2] = np.roll(img[..., 2], -sft, 1)
            img = img + 255 * 0.45 * math.exp(-lt / 0.05) * np.array([1, 0.85, 0.7], np.float32)
        g = 6
    else:
        img = bloom(img, 150, 0.6, 45, (1.0, 0.6, 0.4)); img = grade(img, "calm")
        img = img * clamp01(t / 1.0) * clamp01((DUR - t) / 1.4)
        g = 8
    img = img * VIG + cv2.resize(GRAIN[i % 8], (W, H))[..., None] * g
    if FILM == "calm":
        img[:130] = 0; img[-130:] = 0
    return np.clip(img, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    wav = AUDIO()
    out = os.path.join(HERE, "output", f"ember_roast_{FILM}_hf_stills.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "224k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    n = int(DUR * FPS)
    for i in range(n):
        ff.stdin.write(frame(i).tobytes())
        if i % 48 == 0: print(f"frame {i}/{n}", flush=True)
    ff.stdin.close(); ff.wait()
    print("->", out)
