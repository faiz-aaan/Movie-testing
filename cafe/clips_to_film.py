"""Edit Higgsfield AI video clips (Seedance 2.0 Mini, 720p) into the two EMBER ROAST films.

  python3 clips_to_film.py calm|energetic

Reuses the finishing look from stills_to_film.py (titles, bloom, grade, grain, music).
Clips are upscaled 720p -> 1080p with Lanczos + a light unsharp; picture is graded as one piece.
"""
import math, os, subprocess, sys
import cv2, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stills_to_film as S  # noqa: E402  (takes FILM from argv)

FILM, W, H, FPS = S.FILM, S.W, S.H, S.FPS
CL = os.path.join(HERE, "higgsfield", "clips")

if FILM == "calm":
    DUR, DISSOLVE = 16.0, 0.7
    SHOTS = [  # clip, shot start, shot end, clip offset (s), extras
        ("v5_rain.mp4", 0.0, 4.6, 0.0, {"caption": ("it's raining again.", 0.8, 4.0)}),
        ("v6_pendants.mp4", 4.0, 7.6, 0.3, {}),
        ("v7_table.mp4", 7.0, 11.2, 0.0, {"caption": ("slow down.", 7.8, 10.6)}),
        ("v8_grouphead.mp4", 10.6, 13.6, 0.6, {"caption": ("stay a while.", 11.2, 13.4)}),
        ("v5_rain.mp4", 13.0, 16.0, 4.95, {"endcard": True}),
    ]
    WAV = os.path.join(S.BUILD, "stills_calm.wav")
else:
    DUR, DISSOLVE = 10.0, 0.0
    SHOTS = [
        ("v1_espresso.mp4", 0.0, 2.0, 0.3, {"title": ("FRESH", 0.25)}),
        ("v2_beans.mp4", 2.0, 3.5, 0.15, {"title": ("ROASTED", 0.2)}),
        ("v3_latte.mp4", 3.5, 5.0, 0.5, {"title": ("DAILY", 0.2)}),
        ("v4_wide.mp4", 5.0, 7.0, 0.6, {"title": ("YOUR NEW SPOT", 0.3)}),
        ("v1_espresso.mp4", 7.0, 10.0, 4.95, {"endcard": True}),
    ]
    WAV = os.path.join(S.BUILD, "stills_energetic.wav")

_clips = {}
def frames(name):
    if name not in _clips:
        cap = cv2.VideoCapture(os.path.join(CL, name)); fr = []
        while True:
            ok, f = cap.read()
            if not ok: break
            fr.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        _clips[name] = fr
    return _clips[name]


def clip_frame(name, ct, zoom=0.0):
    fr = frames(name)
    f = fr[min(len(fr) - 1, max(0, int(round(ct * 24))))]
    img = cv2.resize(f, (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    blur = cv2.GaussianBlur(img, (0, 0), 1.2)
    img = np.clip(img + (img - blur) * 0.6, 0, 255)       # light unsharp after the 1.5x upscale
    if zoom:
        M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, 1 + zoom)
        img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return img


def shot_img(idx, t):
    name, s, e, off, ex = SHOTS[idx]
    lt = max(0.0, t - s)
    if ex.get("endcard"):
        img = clip_frame(name, off, zoom=0.05 * min(1.0, lt / (e - s)))
        return img * (0.42 if FILM == "calm" else 0.30)
    return clip_frame(name, off + lt)


def frame(i):
    t = i / FPS
    cur = max(k for k, sh in enumerate(SHOTS) if sh[1] <= t)
    img = shot_img(cur, t)
    if DISSOLVE and cur > 0:
        a = S.clamp01((t - SHOTS[cur][1]) / DISSOLVE)
        if a < 1:
            img = shot_img(cur - 1, min(t, SHOTS[cur - 1][2])) * (1 - a) + img * a
    name, s, e_, off, ex = SHOTS[cur]
    lt = t - s
    CREAM, ORANGE = S.CREAM, S.ORANGE
    if "title" in ex:
        txt, t0 = ex["title"]; p = (lt - t0) / 0.16
        if p > 0 and lt < (e_ - s) - 0.1:
            img = S.put(img, S.text_mask(txt, "BebasNeue-Regular.ttf", 210, 22), W / 2, H * 0.80, CREAM, S.clamp01(p * 2), 1.5 - 0.5 * S.ease_out(p), shadow=0.7)
    if "caption" in ex:
        txt, a0, a1 = ex["caption"]
        a = S.clamp01((t - a0) / 0.8) * S.clamp01((a1 - t) / 0.8)
        img = S.put(img, S.text_mask(txt, "CormorantGaramond-Italic.ttf", 64, 3, 400), W / 2, H - 215, CREAM, a * 0.95, 1.0, shadow=0.5)
    if ex.get("endcard"):
        a = S.ease_out((lt - 0.4) / 0.8)
        if FILM == "calm":
            img = S.put(img, S.text_mask("EMBER ROAST", "Cinzel.ttf", 96, 36, 600), W / 2, H / 2 - 20, CREAM, a * 0.97, 1.0, shadow=0.6)
            img = S.put(img, S.text_mask("open late, every night", "CormorantGaramond-Italic.ttf", 50, 2, 400), W / 2, H / 2 + 70, CREAM, S.ease_out((lt - 1.2) / 0.8) * 0.85, 1.0)
        else:
            m = S.text_mask("EMBER ROAST", "BebasNeue-Regular.ttf", 240, 26)
            glow = np.zeros((H, W, 3), np.float32); glow = S.put(glow, m, W / 2, H / 2 - 40, ORANGE, a, 1.15 - 0.15 * a)
            img = img + cv2.GaussianBlur(glow, (0, 0), 25) * 1.2
            img = S.put(img, m, W / 2, H / 2 - 40, ORANGE, a, 1.15 - 0.15 * a)
            img = S.put(img, S.text_mask("OPEN DAILY  /  7AM  /  @EMBERROAST", "Cinzel.ttf", 34, 10, 600), W / 2, H / 2 + 120, CREAM, S.ease_out((lt - 0.5) / 0.5) * 0.9)
    if FILM == "energetic":
        img = S.bloom(img, 175, 0.45, 30, (1.0, 0.85, 0.7)); img = S.grade(img, "energetic")
        if lt < 0.14 and cur > 0:
            sft = int(12 * (1 - lt / 0.14)); img[..., 0] = np.roll(img[..., 0], sft, 1); img[..., 2] = np.roll(img[..., 2], -sft, 1)
            img = img + 255 * 0.45 * math.exp(-lt / 0.05) * np.array([1, 0.85, 0.7], np.float32)
        g = 5
    else:
        img = S.bloom(img, 150, 0.5, 45, (1.0, 0.6, 0.4)); img = S.grade(img, "calm")
        img = img * S.clamp01(t / 1.0) * S.clamp01((DUR - t) / 1.4)
        g = 7
    img = img * S.VIG + cv2.resize(S.GRAIN[i % 8], (W, H))[..., None] * g
    if FILM == "calm":
        img[:130] = 0; img[-130:] = 0
    return np.clip(img, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    out = os.path.join(HERE, "output", f"ember_roast_{FILM}_hf_video.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", WAV, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "224k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    n = int(DUR * FPS)
    for i in range(n):
        ff.stdin.write(frame(i).tobytes())
        if i % 48 == 0: print(f"frame {i}/{n}", flush=True)
    ff.stdin.close(); ff.wait()
    print("->", out)
