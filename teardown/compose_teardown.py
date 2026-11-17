"""Compose the 30 s vertical teardown film.

  python3 compose_teardown.py                # full render -> output/teardown_nothing_headphone_vu_tv.mp4
  python3 compose_teardown.py stills 2 8 12  # save stills at those times (s) to build/still_*.jpg

Timeline (s): real HP 0-3.2 | CGI headphones 3.2-18.1 | real TV 18.1-20.3 | CGI TV 20.3-28.5 | end card 28.5-30
Labels are pinned to the exploded parts using track.json written by teardown_scene.py.
Spec text comes from manufacturer / retailer listings (see README); the exploded geometry is illustrative.
"""
import json, math, os, subprocess, sys
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, "build")
FONTS = os.path.join(HERE, "..", "demo", "fonts")
W, H, FPS, DUR = 1080, 1920, 24, 30.0
HP0, HP_LEN, TVR0, TVR_LEN, TV0, TV_LEN, END0 = 3.2, 14.9, 18.1, 2.2, 20.3, 8.2, 28.5
rng = np.random.default_rng(8)

CREAM, RED = (243, 238, 228), (232, 52, 38)


def clamp01(v): return max(0.0, min(1.0, v))
def ease_out(u): u = clamp01(u); return 1 - (1 - u) ** 3
def ease_io(u): u = clamp01(u); return u * u * (3 - 2 * u)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


F_TITLE, F_SUB = "Barlow-SemiBold.ttf", "Barlow-Regular.ttf"
BEBAS = "BebasNeue-Regular.ttf"

# ---------- inputs ----------
def read_video(path):
    cap = cv2.VideoCapture(path); fr = []
    while True:
        ok, f = cap.read()
        if not ok: break
        fr.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    return fr


REAL_HP = read_video(os.path.join(B, "real_hp.mp4"))
REAL_TV = read_video(os.path.join(B, "real_tv.mp4"))
TRK = {k: json.load(open(os.path.join(HERE, "renders", k, "track.json"))) for k in ("hp", "tv")}


def cgi_frame(which, local_t):
    """Blender frame at 24 fps (RIFE output) or, if absent, the raw 12 fps frame."""
    k = int(local_t * FPS) + 1
    p = os.path.join(B, f"{which}24", f"{k:04d}.png")
    if not os.path.exists(p):
        n = TRK[which]["n"]
        p = os.path.join(HERE, "renders", which, f"{min(n, k // 2 + 1):04d}.png")
    im = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2RGB)
    im = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    blur = cv2.GaussianBlur(im, (0, 0), 1.4)
    return np.clip(im + (im - blur) * 0.5, 0, 255)


def anchor(which, key, local_t):
    tr = TRK[which]; f = local_t * 12 + 1
    f0 = int(math.floor(f)); f1 = min(tr["n"], f0 + 1); f0 = max(1, min(tr["n"], f0)); u = f - math.floor(f)
    a, b = tr["pts"][str(f0)][key], tr["pts"][str(f1)][key]
    return a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u


# ---------- look ----------
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
RR = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
VIG = np.clip(1.1 - 0.5 * RR ** 2, 0.25, 1)[..., None]
GLOW = np.exp(-((xx - W / 2) ** 2 / (W * 0.55) ** 2 + (yy - H * 0.48) ** 2 / (H * 0.4) ** 2))[..., None]
GRAIN = [rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(8)]


def grade_real(img):
    x = np.clip(img / 255, 0, 1)
    lum = (x * [0.2126, 0.7152, 0.0722]).sum(-1, keepdims=True)
    x = lum + (x - lum) * 0.86
    x = 0.5 + (x - 0.5) * 1.16
    x = x + np.clip(lum - 0.5, 0, 1) * np.array([0.05, 0.015, -0.04]) + np.clip(0.4 - lum, 0, 1) * np.array([-0.03, 0.0, 0.05])
    return np.clip(x, 0, 1) * 255


def bloom(img, thr, gain):
    l = img.max(-1, keepdims=True)
    hi = img * np.clip((l - thr) / (255 - thr), 0, 1)
    g = cv2.GaussianBlur(cv2.resize(hi, (W // 4, H // 4), interpolation=cv2.INTER_AREA), (0, 0), 12)
    return img + cv2.resize(g, (W, H)) * gain


def finish(img, i, grain=6):
    img = img * VIG + cv2.resize(GRAIN[i % 8], (W, H))[..., None] * grain
    return np.clip(img, 0, 255)


_txt = {}
def text_mask(s, fname, size, track=0):
    k = (s, fname, size, track)
    if k not in _txt:
        f = font(fname, size)
        ws = [f.getlength(c) for c in s]
        a = Image.new("L", (int(sum(ws) + track * (len(s) - 1)) + 40, int(size * 1.5)), 0); d = ImageDraw.Draw(a)
        x = 20
        for c, w_ in zip(s, ws):
            d.text((x, int(size * 0.18)), c, font=f, fill=255); x += w_ + track
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
        img[Y0:Y1, X0:X1] *= 1 - cv2.GaussianBlur(mm[..., 0], (0, 0), 16)[..., None] * shadow
    img[Y0:Y1, X0:X1] = img[Y0:Y1, X0:X1] * (1 - mm) + np.array(color, np.float32) * mm
    return img


def flash(img, lt, strength=0.8, decay=0.07):
    if lt < 0: return img
    return img + 255 * strength * math.exp(-lt / decay) * np.array([1, 0.97, 0.93], np.float32)


def rgb_split(img, lt, px=14, dur=0.16):
    if 0 <= lt < dur:
        s = int(px * (1 - lt / dur)); img[..., 0] = np.roll(img[..., 0], s, 1); img[..., 2] = np.roll(img[..., 2], -s, 1)
    return img


# ---------- label cards ----------
def wrap(text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= maxw: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur)
    return lines


_cards = {}
def card(title, sub, width):
    k = (title, sub, width)
    if k in _cards: return _cards[k]
    ft, fs = font(F_TITLE, 38), font(F_SUB, 27)
    lines = wrap(sub, fs, width - 48)
    h = 22 + 44 + 8 + 34 * len(lines) + 18
    im = Image.new("RGBA", (width, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, width - 1, h - 1], radius=12, fill=(9, 11, 15, 205), outline=(255, 255, 255, 70), width=2)
    d.rectangle([0, 14, 5, h - 14], fill=(*RED, 255))
    d.text((24, 18), title, font=ft, fill=(246, 246, 246, 255))
    for j, ln in enumerate(lines):
        d.text((24, 18 + 44 + 8 + 34 * j), ln, font=fs, fill=(186, 192, 202, 255))
    a = np.asarray(im, np.float32) / 255
    _cards[k] = (a[..., :3] * 255, a[..., 3], h)
    return _cards[k]


def blit_card(img, c, x0, yc, alpha):
    rgb, a, h = c
    y0 = int(yc - h / 2); w = rgb.shape[1]
    X0, Y0, X1, Y1 = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if X1 <= X0 or Y1 <= Y0: return img
    aa = (a[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0] * alpha)[..., None]
    img[Y0:Y1, X0:X1] = img[Y0:Y1, X0:X1] * (1 - aa) + rgb[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0] * aa
    return img


def leader(frame_u8, p0, p1, prog, alpha, t):
    """line from anchor p0 growing toward p1, with a pulsing dot at p0 (draws on uint8)"""
    if alpha <= 0.01: return
    col = tuple(int(c * (0.35 + 0.65 * alpha)) for c in CREAM)
    pe = (int(p0[0] + (p1[0] - p0[0]) * prog), int(p0[1] + (p1[1] - p0[1]) * prog))
    cv2.line(frame_u8, (int(p0[0]), int(p0[1])), pe, col, 2, cv2.LINE_AA)
    cv2.circle(frame_u8, (int(p0[0]), int(p0[1])), 6, col, -1, cv2.LINE_AA)
    r = int(14 + 6 * math.sin(t * 6))
    cv2.circle(frame_u8, (int(p0[0]), int(p0[1])), r, col, 2, cv2.LINE_AA)


HP_LABELS = [  # key, t_on (local), side, slot_y, title, subtitle
    ("plate", 6.6, "R", 0.16, "CONTROLS", "Roller, paddle and a customisable button on the outer plate."),
    ("housing", 7.4, "L", 0.29, "4 MICS + USB-C", "Four microphones feed adaptive noise cancelling, up to 42 dB."),
    ("mainboard", 8.2, "R", 0.41, "BLUETOOTH BOARD", "Bluetooth 5.3 with LDAC. The exact chip is not publicly disclosed."),
    ("battery", 9.0, "L", 0.51, "BATTERY", "Up to 80 hours of playback with noise cancelling off."),
    ("driver", 9.8, "L", 0.66, "40 mm DRIVER", "Dynamic driver tuned with KEF. 20 Hz to 40 kHz."),
    ("cushion", 10.6, "R", 0.75, "MEMORY FOAM", "Soft foam cushion that seals the ear for passive isolation."),
]
HP_OFF = 12.4
TV_LABELS = [
    ("panel", 2.9, "LCD PANEL", "The screen itself: a grid of pixels with colour filters."),
    ("backlight", 3.5, "LED BACKLIGHT + LIGHT GUIDE", "White LEDs light a plate that spreads the glow evenly."),
    ("boards_main", 4.1, "MAIN BOARD", "Processor, RAM, storage and tuner. The TV's brain."),
    ("boards_psu", 4.7, "POWER BOARD", "Turns wall power into the voltages every part needs."),
    ("boards_spk", 5.3, "SPEAKERS", "Small drivers mounted in the lower back."),
    ("back", 5.9, "BACK COVER", "Holds every board and the wall-mount points."),
]
TV_STEP, TV_OFF = 0.6, 6.7
HP_SIDE_X = {"L": 36, "R": W - 36 - 372}


def hp_labels(img, lt, t_abs):
    pend = []
    for key, t_on, side, slot, title, sub in HP_LABELS:
        a = ease_out((lt - t_on) / 0.3) * (1 - ease_io((lt - HP_OFF) / 0.4))
        if a <= 0.01: continue
        c = card(title, sub, 372)
        x0 = HP_SIDE_X[side]; yc = slot * H
        ax, ay = anchor("hp", key, lt)
        p0 = (ax * W, ay * H)
        p1 = (x0 + (372 if side == "L" else 0), yc)
        # slide-in
        img = blit_card(img, c, x0 + int((-1 if side == "L" else 1) * 26 * (1 - ease_out((lt - t_on) / 0.3))), yc, a)
        pend.append((p0, p1, ease_out((lt - t_on - 0.05) / 0.3), a))
    return img, pend


def tv_labels(img, lt):
    pend = []
    for k, (key, t_on, title, sub) in enumerate(TV_LABELS):
        t_off = t_on + TV_STEP if k < len(TV_LABELS) - 1 else TV_OFF
        a = ease_out((lt - t_on) / 0.18) * (1 - ease_io((lt - (t_off - 0.14)) / 0.14))
        if a <= 0.01: continue
        c = card(title, sub, 960)
        x0 = (W - 960) // 2; yc = 0.9 * H
        ax, ay = anchor("tv", key, lt)
        p0 = (ax * W, ay * H); p1 = (W / 2, yc - c[2] / 2)
        img = blit_card(img, c, x0, yc, a)
        pend.append((p0, p1, ease_out((lt - t_on - 0.03) / 0.2), a))
    return img, pend


def tag(img, a=0.8):
    m = text_mask("TEARDOWN 01", F_TITLE, 26, 6)
    img = put(img, m, 190, 78, CREAM, a)
    cv2.circle(img, (62, 80), 8, RED, -1, cv2.LINE_AA)
    return img


def footer(img, s, a=0.55):
    return put(img, text_mask(s, F_SUB, 22, 1), W / 2, H * 0.968, CREAM, a)


def bg_glow(img, tint=(18, 22, 34), k=1.0):
    lum = img.max(-1, keepdims=True)
    return img + GLOW * np.array(tint, np.float32) * np.clip(1 - lum / 34, 0, 1) * k


# ---------- segments ----------
def seg_real(frames, lt, i, name_lines, t_title):
    img = grade_real(frames[min(len(frames) - 1, int(lt * FPS))].astype(np.float32))
    # titles
    a = ease_out((lt - t_title) / 0.35)
    m1 = text_mask(name_lines[0], F_TITLE, 54, 9)
    img = put(img, m1, W / 2, H * 0.115, CREAM, a, 1.0, shadow=0.75)
    p = (lt - t_title - 0.5) / 0.25
    img = put(img, text_mask("TEARDOWN", BEBAS, 330, 10), W / 2, H * 0.19, (255, 255, 255), clamp01(p * 2), 1.35 - 0.35 * ease_out(p), shadow=0.8)
    if p > 0:
        cv2.circle(img, (int(W / 2 - 330 * 1.0), int(H * 0.285)), 9, RED, -1, cv2.LINE_AA)
    return img


def scan_hud(img, lt, t0, t1):
    if not (t0 <= lt <= t1): return img
    u = (lt - t0) / (t1 - t0); y = int(H * (0.06 + 0.88 * u))
    band = np.exp(-((yy - y) / 14.0) ** 2)[..., None]
    img = img + band * np.array([120, 200, 255], np.float32) * 1.4
    img[::6, :, :] *= 0.985
    return img


def frame(i):
    t = i / FPS
    if t < HP0:                                                       # REAL headphones
        img = seg_real(REAL_HP, t, i, ["NOTHING HEADPHONE (1)"], 0.35)
        img = scan_hud(img, t, 2.1, 3.1)
        img = bloom(img, 200, 0.25); img = finish(img, i, 5)
        img *= clamp01(t / 0.35)
        img = tag(img)
    elif t < TVR0:                                                    # CGI headphones
        lt = t - HP0
        img = cgi_frame("hp", min(lt, HP_LEN - 0.05))
        img = bg_glow(img)
        img = bloom(img, 150, 0.55)
        img = finish(img, i, 5)
        img = rgb_split(img, lt); img = flash(img, lt, 0.9, 0.09)
        img, pend = hp_labels(img, lt, t)
        img = tag(img)
        img = footer(img, "Illustrative exploded view. Specs from manufacturer and retailer listings.")
        out = np.clip(img, 0, 255).astype(np.uint8)
        for p0, p1, prog, a in pend: leader(out, p0, p1, prog, a, t)
        return out
    elif t < TV0:                                                     # REAL TV
        lt = t - TVR0
        img = seg_real(REAL_TV, lt, i, ["VU TV"], 0.15)
        img = bloom(img, 200, 0.25); img = finish(img, i, 5)
        img = rgb_split(img, lt); img = flash(img, lt, 0.9, 0.09)
        img = tag(img)
    elif t < END0:                                                    # CGI TV
        lt = t - TV0
        img = cgi_frame("tv", min(lt, TV_LEN - 0.05))
        img = bg_glow(img)
        img = bloom(img, 150, 0.55)
        img = finish(img, i, 5)
        img = rgb_split(img, lt); img = flash(img, lt, 0.9, 0.09)
        img, pend = tv_labels(img, lt)
        img = tag(img)
        img = footer(img, "Typical LED TV layout. The exact chips inside this Vu model are not public.", 0.6)
        out = np.clip(img, 0, 255).astype(np.uint8)
        for p0, p1, prog, a in pend: leader(out, p0, p1, prog, a, t)
        return out
    else:                                                             # END CARD
        lt = t - END0
        img = np.zeros((H, W, 3), np.float32) + np.array([8, 9, 13], np.float32)
        img = bg_glow(img, (26, 30, 44), 1.4)
        img = flash(img, lt, 0.5, 0.08)
        img = put(img, text_mask("TEARDOWN", BEBAS, 360, 12), W / 2, H * 0.42, (255, 255, 255), ease_out(lt / 0.4), 1.2 - 0.2 * ease_out(lt / 0.4))
        cv2.circle(img, (int(W / 2 - 360), int(H * 0.5)), 10, RED, -1, cv2.LINE_AA)
        img = put(img, text_mask("NOTHING HEADPHONE (1)", F_TITLE, 52, 7), W / 2, H * 0.56, CREAM, ease_out((lt - 0.3) / 0.4))
        img = put(img, text_mask("+  VU TV", F_TITLE, 52, 7), W / 2, H * 0.60, CREAM, ease_out((lt - 0.45) / 0.4))
        img = put(img, text_mask("Illustrative exploded views", F_SUB, 26, 2), W / 2, H * 0.95, CREAM, 0.5 * ease_out((lt - 0.8) / 0.4))
        img = finish(img, i, 4)
        img *= 1 - ease_io((lt - 1.2) / 0.3)
    return np.clip(img, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stills":
        for s in sys.argv[2:]:
            cv2.imwrite(os.path.join(B, f"still_{s}.jpg"), cv2.cvtColor(frame(int(float(s) * FPS)), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
        sys.exit()
    out = os.path.join(HERE, "output", "teardown_nothing_headphone_vu_tv.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", os.path.join(B, "td_score.wav"), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    n = int(DUR * FPS)
    for i in range(n):
        ff.stdin.write(frame(i).tobytes())
        if i % 48 == 0: print(f"frame {i}/{n}", flush=True)
    ff.stdin.close(); ff.wait()
    print("->", out)
