"""Edit + finish the two EMBER ROAST films from the Blender renders.

  python3 post.py energetic|calm [preview]

  1. RIFE per shot (never across a cut): energetic 12->24 fps, calm 8->32->24 fps;
     one shot stays stepped 12 fps on purpose (stop-motion beat).
  2. Edit to the score: hard cuts + beat flashes (energetic) / dissolves (calm).
  3. 2D steam pinned to the cups / wand using the per-frame track.json Blender wrote.
  4. Grade, bloom/halation, grain, vignette, letterbox (calm), titles and cards.
  5. Upscale 720p -> 1080p, mux the score -> output/<film>.mp4
"""
import json, math, os, subprocess, sys
import cv2, numpy as np, torch
from PIL import Image, ImageDraw, ImageFont
from torch.nn import functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
FILM = sys.argv[1] if len(sys.argv) > 1 else "energetic"
PREVIEW = len(sys.argv) > 2 and sys.argv[2] == "preview"
RD = os.path.join(HERE, "renders", FILM)
FONTS = os.path.join(HERE, "..", "demo", "fonts")
W, H, FPS = 1920, 1080, 24
rng = np.random.default_rng(5)

# ---------------- RIFE ----------------
sys.path.insert(0, os.path.join(HERE, "..", "demo", "models", "RIFE"))
from train_log.RIFE_HDv3 import Model
torch.set_grad_enabled(False); torch.set_num_threads(os.cpu_count())
RIFE = Model(); RIFE.load_model(os.path.join(HERE, "..", "demo", "models", "RIFE", "train_log"), -1); RIFE.eval(); RIFE.device()


def rife_mid(a, b):
    h, w = a.shape[:2]; ph, pw = ((h - 1) // 32 + 1) * 32, ((w - 1) // 32 + 1) * 32
    T = lambda f: F.pad(torch.from_numpy(f.transpose(2, 0, 1).copy()).float()[None] / 255, (0, pw - w, 0, ph - h))
    m = RIFE.inference(T(a), T(b), 1.0)
    return (m[0, :, :h, :w].clamp(0, 1).numpy().transpose(1, 2, 0) * 255).round().astype(np.uint8)


def load_shot(name, mode):
    """Return (frames at 24 fps as uint8 RGB list, track dict per src frame, src_fps)."""
    d = os.path.join(RD, name)
    files = sorted(f for f in os.listdir(d) if f.endswith(".png"))
    src = [cv2.cvtColor(cv2.imread(os.path.join(d, f)), cv2.COLOR_BGR2RGB) for f in files]
    tr = json.load(open(os.path.join(d, "track.json")))
    cache = os.path.join(HERE, "build", "rife_cache", FILM, name + f"_{mode}.npy")
    if os.path.exists(cache) and not PREVIEW:
        return list(np.load(cache)), tr
    if mode == "step" or PREVIEW:
        k = 2 if tr["fps"] == 12 else 3
        out = [f for f in src for _ in range(k)]
    elif mode == "x2":
        out = []
        for a, b in zip(src, src[1:]):
            out += [a, rife_mid(a, b)]
        out += [src[-1], src[-1]]
    else:  # x4 then 32->24
        dense = []
        for a, b in zip(src, src[1:]):
            m = rife_mid(a, b); dense += [a, rife_mid(a, m), m, rife_mid(m, b)]
        dense += [src[-1]] * 4
        n_out = int(round(len(src) / 8 * 24))
        out = [dense[min(len(dense) - 1, round(i * 32 / 24))] for i in range(n_out)]
    if not PREVIEW:
        os.makedirs(os.path.dirname(cache), exist_ok=True); np.save(cache, np.stack(out))
    print("  shot", name, len(src), "->", len(out), flush=True)
    return out, tr


def track_at(tr, t_local):
    """screen point dict at shot-local time (sec), from per-source-frame track."""
    f = min(tr["n"], max(1, int(t_local * tr["fps"]) + 1))
    return tr["pts"].get(str(f)) or tr["pts"][max(tr["pts"], key=int)]


# ---------------- look helpers ----------------
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
RR = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
VIG = np.clip(1.12 - 0.42 * RR ** 2, 0.3, 1)[..., None]
GRAIN = [rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(8)]

noise = np.zeros((1024, 1024), np.float32)
for s, a in ((4, 1.0), (8, 0.55), (16, 0.3), (32, 0.15)):
    noise += a * cv2.resize(rng.normal(0, 1, (s, s)).astype(np.float32), (1024, 1024), interpolation=cv2.INTER_CUBIC)
noise = (noise - noise.min()) / (noise.max() - noise.min())


def steam(img, x, y, scale, t, strength=0.6, rise=0.12, warm=(255, 240, 225)):
    """Wispy steam rising from screen point (x, y) in px. Lightens the plate."""
    ws, hs = int(260 * scale), int(620 * scale)
    if ws < 8 or hs < 8:
        return img
    x0, y0 = int(x - ws / 2), int(y - hs)
    X0, Y0, X1, Y1 = max(x0, 0), max(y0, 0), min(x0 + ws, W), min(int(y), H)
    if X1 <= X0 or Y1 <= Y0:
        return img
    gy, gx = np.mgrid[Y0:Y1, X0:X1].astype(np.float32)
    v = (y - gy) / hs                 # 0 at the cup, 1 at the top
    u = (gx - x) / ws                 # -0.5..0.5
    sway = 0.18 * np.sin(v * 5 + t * 1.3) * v
    spread = 0.10 + 0.32 * v
    mask = np.exp(-((u - sway) / spread) ** 2) * np.clip(v * 8, 0, 1) * np.clip((1 - v) * 1.6, 0, 1)
    mx = ((u * 1.4 + 0.5 + 0.3 * np.sin(v * 3 + t * 0.7)) * 512) % 1024
    my = ((v * 1.6 - t * rise) * 512) % 1024
    n = cv2.remap(noise, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    d = (np.clip((n - 0.42) * 3.2, 0, 1) * mask * strength)[..., None]
    reg = img[Y0:Y1, X0:X1]
    img[Y0:Y1, X0:X1] = reg + (np.array(warm, np.float32) - reg) * d * 0.55
    return img


def bloom(img, thr, gain, sigma, tint=(1, 1, 1)):
    l = img.max(-1, keepdims=True)
    hi = img * np.clip((l - thr) / (255 - thr), 0, 1)
    small = cv2.resize(hi, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    g = cv2.GaussianBlur(small, (0, 0), sigma / 4)
    return img + cv2.resize(g, (W, H)) * gain * np.array(tint, np.float32)


def grade(img, kind):
    x = np.clip(img / 255, 0, 1)
    lum = (x * [0.2126, 0.7152, 0.0722]).sum(-1, keepdims=True)
    if kind == "energetic":
        x = lum + (x - lum) * 1.12
        x = x + 0.10 * (x - 0.5) * (1 - np.abs(x - 0.5) * 2)   # S-curve
        x = x + np.clip(lum - 0.55, 0, 1) * np.array([0.06, 0.02, -0.04]) + np.clip(0.3 - lum, 0, 1) * np.array([-0.02, 0.0, 0.03])
    else:
        x = lum + (x - lum) * 0.82
        x = 0.025 + x * 0.96                                     # lifted film blacks
        x = x + np.clip(0.35 - lum, 0, 1) * np.array([-0.03, 0.02, 0.05]) + np.clip(lum - 0.45, 0, 1) * np.array([0.07, 0.03, -0.05])
    return np.clip(x, 0, 1) * 255


_txt = {}
def text_mask(s, font, size, track=0, wght=None):
    k = (s, font, size, track, wght)
    if k not in _txt:
        f = ImageFont.truetype(os.path.join(FONTS, font), size)
        if wght:
            f.set_variation_by_axes([wght])
        widths = [f.getlength(c) for c in s]
        tw = int(sum(widths) + track * (len(s) - 1)) + 40
        a = Image.new("L", (tw, int(size * 1.5)), 0); d = ImageDraw.Draw(a)
        x = 20
        for c, w_ in zip(s, widths):
            d.text((x, int(size * 0.2)), c, font=f, fill=255); x += w_ + track
        _txt[k] = np.asarray(a, np.float32) / 255
    return _txt[k]


def put(img, m, cx, cy, color, alpha=1.0, scale=1.0, shadow=0.0):
    if alpha <= 0.002:
        return img
    if scale != 1.0:
        m = cv2.resize(m, (max(1, int(m.shape[1] * scale)), max(1, int(m.shape[0] * scale))), interpolation=cv2.INTER_LINEAR)
    h, w = m.shape; x0, y0 = int(cx - w / 2), int(cy - h / 2)
    X0, Y0, X1, Y1 = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if X1 <= X0 or Y1 <= Y0:
        return img
    mm = m[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0][..., None] * alpha
    if shadow:
        sh = cv2.GaussianBlur(mm[..., 0], (0, 0), 14)[..., None] * shadow
        img[Y0:Y1, X0:X1] *= 1 - sh
    img[Y0:Y1, X0:X1] = img[Y0:Y1, X0:X1] * (1 - mm) + np.array(color, np.float32) * mm
    return img


def clamp01(v): return max(0.0, min(1.0, v))
def eo(v): v = clamp01(v); return 1 - (1 - v) ** 3


# ---------------- edits ----------------
CREAM, ORANGE, INK = (245, 236, 220), (236, 98, 34), (18, 12, 9)

if FILM == "energetic":
    EDIT = [  # (kind, name/text, start, dur, mode, extras)
        ("shot", "e01_neon", 0.0, 1.0, "x2", {}),
        ("shot", "e02_beans", 1.0, 2.0, "x2", {"title": ("FRESH", 0.25)}),
        ("shot", "e03_porta", 3.0, 1.0, "x2", {"flash": 1}),
        ("shot", "e04_pour", 4.0, 1.5, "x2", {"title": ("ROASTED", 0.2), "steam": ("pour_top", 0.9, 0.35)}),
        ("shot", "e05_whip", 5.5, 0.5, "x2", {}),
        ("shot", "e06_steam", 6.0, 1.0, "x2", {"steam": ("wand_tip", 2.2, 0.95), "flash": 1}),
        ("shot", "e07_slide", 7.0, 1.5, "x2", {"title": ("DAILY", 0.3)}),
        ("shot", "e08_latte", 8.5, 1.0, "x2", {}),
        ("card", "WAKE UP.", 9.5, 1.0, None, {}),
        ("shot", "e09_fpv", 10.5, 4.0, "x2", {"flash": 1}),
        ("shot", "e10_lamps", 14.5, 1.0, "x2", {}),
        ("shot", "e11_shelves", 15.5, 1.0, "x2", {}),
        ("shot", "e12_crash", 16.5, 1.0, "x2", {"flash": 1}),
        ("shot", "e13_rain", 17.5, 1.5, "step", {}),
        ("card3", ["SIP.", "SMILE.", "REPEAT."], 19.0, 1.5, None, {}),
        ("shot", "e14_orbit", 20.5, 2.5, "x2", {"steam": ("hero_top", 1.0, 0.5), "flash": 1}),
        ("shot", "e15_wide", 23.0, 2.5, "x2", {"title": ("YOUR NEW SPOT", 0.4)}),
        ("shot", "e16_sign", 25.5, 3.0, "x2", {"logo": True}),
        ("end", None, 28.5, 1.5, None, {}),
    ]
else:
    EDIT = [
        ("shot", "c01_window", 0.0, 5.0, "x4", {"caption": ("it's raining again.", 1.2, 4.2)}),
        ("shot", "c02_pendant", 5.0, 4.0, "x4", {}),
        ("shot", "c03_steam", 9.0, 5.0, "x4", {"steam": ("hero_top", 1.25, 0.75), "caption": ("slow down.", 10.4, 13.4)}),
        ("shot", "c04_dolly", 14.0, 5.0, "x4", {}),
        ("shot", "c05_rack", 19.0, 4.0, "x4", {"steam": ("table_top", 0.7, 0.5), "caption": ("stay a while.", 19.8, 22.6)}),
        ("shot", "c06_wide", 23.0, 4.0, "x4", {}),
        ("shot", "c07_sign", 27.0, 3.0, "x4", {"logo": True}),
    ]

DUR = 30.0
NF = int(DUR * FPS)
shots = {}
print("loading + interpolating shots ...", flush=True)
for kind, name, st, du, mode, ex in EDIT:
    if kind == "shot":
        shots[name] = load_shot(name, mode)


def shot_frame(name, t_local):
    fr, _ = shots[name]
    i = min(len(fr) - 1, max(0, int(round(t_local * FPS))))
    return cv2.resize(fr[i], (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)


def segment_at(t):
    for seg in EDIT:
        if seg[2] <= t < seg[2] + seg[3]:
            return seg
    return EDIT[-1]


def render_segment(seg, t):
    kind, name, st, du, mode, ex = seg
    lt = t - st
    if kind == "shot":
        img = shot_frame(name, lt)
        if "steam" in ex:
            key, sc_, strength = ex["steam"]
            p = track_at(shots[name][1], lt)[key]
            if p[2] > 0:
                img = steam(img, p[0] * W, p[1] * H, sc_ * (0.9 / max(p[2], 0.3)) ** 0.6, t, strength,
                            rise=0.22 if FILM == "energetic" else 0.08)
        return img
    if kind == "card":
        img = np.full((H, W, 3), ORANGE, np.float32)
        m = text_mask(name, "BebasNeue-Regular.ttf", 330, 18)
        s = 1.35 - 0.35 * eo(lt / 0.18) + 0.03 * lt
        return put(img, m, W / 2 + rng.normal(0, 2), H / 2 + rng.normal(0, 2), INK, 1.0, s)
    if kind == "card3":
        k = min(2, int(lt / 0.5)); wl = lt - k * 0.5
        img = np.full((H, W, 3), ORANGE if k != 1 else INK, np.float32)
        m = text_mask(name[k], "BebasNeue-Regular.ttf", 360, 16)
        return put(img, m, W / 2, H / 2, INK if k != 1 else ORANGE, 1.0, 1.3 - 0.3 * eo(wl / 0.15))
    if kind == "end":
        img = np.full((H, W, 3), INK, np.float32)
        a = eo(lt / 0.3)
        m = text_mask("EMBER ROAST", "BebasNeue-Regular.ttf", 230, 26)
        glow = np.zeros((H, W, 3), np.float32); glow = put(glow, m, W / 2, H / 2 - 40, ORANGE, a, 1.15 - 0.15 * a)
        img = img + cv2.GaussianBlur(glow, (0, 0), 25) * 1.2
        img = put(img, m, W / 2, H / 2 - 40, ORANGE, a, 1.15 - 0.15 * a)
        m2 = text_mask("OPEN DAILY  /  7AM  /  @EMBERROAST", "Cinzel.ttf", 34, 10, 600)
        return put(img, m2, W / 2, H / 2 + 120, CREAM, eo((lt - 0.3) / 0.4) * 0.9)


def frame(i):
    t = i / FPS
    seg = segment_at(t)
    if FILM == "calm":
        # dissolves: blend with the neighbouring shot within +-0.5 s of every cut
        img = render_segment(seg, t)
        idx = EDIT.index(seg)
        for j, cut in ((idx + 1, seg[2] + seg[3]), (idx, seg[2])):
            if 0 < j < len(EDIT) and abs(t - cut) < 0.5:
                other = EDIT[j] if j != idx else EDIT[idx - 1]
                w_ = clamp01(0.5 + (t - cut) / 1.0)
                o = render_segment(other, t)
                img = img * (w_ if j == idx else 1 - w_) + o * (1 - w_ if j == idx else w_)
                break
    else:
        img = render_segment(seg, t)
    kind, name, st, du, mode, ex = seg
    lt = t - st
    # titles
    if "title" in ex:
        s, t0 = ex["title"]
        m = text_mask(s, "BebasNeue-Regular.ttf", 210, 22)
        p = (lt - t0) / 0.16
        if p > 0:
            img = put(img, m, W / 2, H * 0.80, CREAM, clamp01(p * 2), 1.5 - 0.5 * eo(p), shadow=0.7)
    if "caption" in ex:
        s, a0, a1 = ex["caption"]
        a = clamp01((t - a0) / 0.9) * clamp01((a1 - t) / 0.9)
        m = text_mask(s, "CormorantGaramond-Italic.ttf", 64, 3, 400)
        img = put(img, m, W / 2, H - 205, CREAM, a * 0.95, 1.0, shadow=0.5)
    if ex.get("logo"):
        a = eo((lt - 0.6) / 0.8)
        if FILM == "energetic":
            m = text_mask("OPEN DAILY 7AM", "BebasNeue-Regular.ttf", 120, 14)
            img = put(img, m, W / 2, H * 0.82, CREAM, a, 1.2 - 0.2 * a, shadow=0.8)
        else:
            m = text_mask("EMBER ROAST", "Cinzel.ttf", 64, 30, 600)
            img = put(img, m, W / 2, H - 230, CREAM, a * 0.95, 1.0, shadow=0.6)
            m2 = text_mask("open late, every night", "CormorantGaramond-Italic.ttf", 44, 2, 400)
            img = put(img, m2, W / 2, H - 175, CREAM, eo((lt - 1.2) / 0.8) * 0.85, 1.0, shadow=0.5)
    # finish
    if FILM == "energetic":
        img = bloom(img, 170, 0.55, 30, (1.0, 0.85, 0.7))
        img = grade(img, "energetic")
        if kind == "shot" and ex.get("flash") and lt < 0.25:
            img = img + 255 * 0.5 * math.exp(-lt / 0.06) * np.array([1, 0.85, 0.7], np.float32)
        if kind == "shot" and lt < 0.12:  # RGB split on every cut
            sft = int(10 * (1 - lt / 0.12))
            img[..., 0] = np.roll(img[..., 0], sft, 1); img[..., 2] = np.roll(img[..., 2], -sft, 1)
        img = img * VIG
        g = 6
    else:
        img = bloom(img, 150, 0.7, 45, (1.0, 0.55, 0.35))  # halation
        img = grade(img, "calm")
        img = img * VIG
        img *= clamp01(t / 1.2) * clamp01((DUR - t) / 1.6)
        g = 8
    img = img + cv2.resize(GRAIN[i % 8], (W, H))[..., None] * g
    if FILM == "calm":
        bar = 138; img[:bar] = 0; img[-bar:] = 0
    return np.clip(img, 0, 255).astype(np.uint8)


os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
out = os.path.join(HERE, "output", f"ember_roast_{FILM}{'_preview' if PREVIEW else ''}.mp4")
audio = os.path.join(HERE, "build", f"score_{FILM}.wav")
ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                       "-i", audio, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                       "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
for i in range(NF):
    ff.stdin.write(frame(i).tobytes())
    if i % 48 == 0:
        print(f"frame {i}/{NF}", flush=True)
ff.stdin.close(); ff.wait()
print("->", out)
