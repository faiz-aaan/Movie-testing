"""Procedural hero assets for the KRONOS demo film.

Builds (into demo/build/):
  disc.png      - bronze circular maze dial with roman numerals (RGBA)
  disc_ring.png - outer ornamental ring that counter-rotates (RGBA)
  field.png     - low-angle bronze maze field plate (RGB) used for depth parallax
"""
import math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "build")
os.makedirs(OUT, exist_ok=True)
FONT = os.path.join(HERE, "fonts", "Cinzel.ttf")
rng = random.Random(7)

BRONZE_DARK = np.array([22, 14, 8], np.float32)
BRONZE_MID = np.array([120, 74, 38], np.float32)
BRONZE_HI = np.array([255, 214, 150], np.float32)


def bronze_shade(height, light=(-0.6, -0.7, 0.45), rough=0.0, seed=0):
    """Turn a 0..1 heightmap into shaded bronze RGB via normal mapping."""
    h = height.astype(np.float32)
    gy, gx = np.gradient(h)
    nz = np.ones_like(h) * 0.04
    n = np.stack([-gx, -gy, nz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array(light, np.float32); L /= np.linalg.norm(L)
    diff = np.clip((n * L).sum(-1), 0, 1)
    H = L + np.array([0, 0, 1], np.float32); H /= np.linalg.norm(H)
    spec = np.clip((n * H).sum(-1), 0, 1) ** 28
    if rough:
        r = np.random.default_rng(seed).normal(0, 1, h.shape).astype(np.float32)
        r = np.array(Image.fromarray(((r * 0.5 + 0.5).clip(0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
        diff *= 0.75 + rough * r
    base = BRONZE_DARK + (BRONZE_MID - BRONZE_DARK) * (0.35 + 0.65 * h[..., None])
    col = base * (0.25 + 1.1 * diff[..., None]) + BRONZE_HI * spec[..., None] * 0.9
    return np.clip(col, 0, 255)


def polar_maze(size=2400, r0=0.10, r1=0.86, rings=11, seed=3):
    """Concentric maze: ring walls with gaps plus radial spokes."""
    R = random.Random(seed)
    im = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(im)
    c = size / 2
    radii = np.linspace(r0, r1, rings + 1) * c
    w = int(size * 0.010)
    for i, r in enumerate(radii):
        # ring wall with 1-3 gaps
        gaps = sorted(R.uniform(0, 360) for _ in range(R.randint(1, 3)))
        segs, start = [], 0
        for g in gaps:
            segs.append((start, g - 6)); start = g + 6
        segs.append((start, 360 + (gaps[0] - 6 if gaps else 0)))
        for a0, a1 in segs:
            if a1 > a0:
                d.arc([c - r, c - r, c + r, c + r], a0, a1, fill=255, width=w)
        if i < rings:
            n_sp = 4 + i * 2
            for k in range(n_sp):
                if R.random() < 0.55:
                    a = math.radians(R.uniform(0, 360))
                    ra, rb = radii[i], radii[i + 1]
                    d.line([(c + ra * math.cos(a), c + ra * math.sin(a)), (c + rb * math.cos(a), c + rb * math.sin(a))], fill=255, width=w)
    return im


def make_disc():
    S = 2400
    c = S / 2
    walls = polar_maze(S)
    h = np.array(walls.filter(ImageFilter.GaussianBlur(5)), np.float32) / 255
    # dish base: slight dome + outer rim
    yy, xx = np.mgrid[0:S, 0:S]
    rr = np.hypot(xx - c, yy - c) / c
    h = 0.15 * (1 - rr) + 0.85 * h
    rim = np.exp(-((rr - 0.93) / 0.025) ** 2)
    h = np.maximum(h, rim)
    # roman numerals embossed on the rim band
    txt = Image.new("L", (S, S), 0)
    td = ImageDraw.Draw(txt)
    f = ImageFont.truetype(FONT, int(S * 0.045)); f.set_variation_by_axes([800])
    for k, num in enumerate(["XII", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"]):
        a = math.radians(k * 30 - 90)
        tile = Image.new("L", (400, 200), 0)
        ImageDraw.Draw(tile).text((200, 100), num, font=f, fill=255, anchor="mm")
        tile = tile.rotate(-k * 30, expand=True, resample=Image.BICUBIC)
        r = c * 0.885
        x, y = c + r * math.cos(a), c + r * math.sin(a)
        txt.paste(255, (int(x - tile.width / 2), int(y - tile.height / 2)), tile)
    th = np.array(txt.filter(ImageFilter.GaussianBlur(2)), np.float32) / 255
    h = np.clip(h - 0.6 * th * (rr > 0.8), 0, 1)
    rgb = bronze_shade(h, rough=0.35, seed=1)
    # centre jewel/hub
    hub = np.exp(-(rr / 0.07) ** 2)[..., None]
    rgb = rgb * (1 - hub) + np.array([255, 196, 120]) * hub * 0.9
    alpha = (np.clip((0.985 - rr) * 120, 0, 1) * 255).astype(np.uint8)
    img = Image.fromarray(np.dstack([rgb.astype(np.uint8), alpha]), "RGBA").resize((1600, 1600), Image.LANCZOS)
    img.save(os.path.join(OUT, "disc.png"))

    # counter-rotating ornamental ring (ticks + dots)
    ring = Image.new("L", (S, S), 0)
    rd = ImageDraw.Draw(ring)
    for k in range(120):
        a = math.radians(k * 3)
        r_in = c * (0.955 if k % 5 else 0.94)
        rd.line([(c + r_in * math.cos(a), c + r_in * math.sin(a)), (c + c * 0.99 * math.cos(a), c + c * 0.99 * math.sin(a))], fill=255, width=int(S * (0.006 if k % 5 else 0.010)))
    hr = np.array(ring.filter(ImageFilter.GaussianBlur(3)), np.float32) / 255
    rgb = bronze_shade(hr, rough=0.2, seed=2)
    a = (np.clip(hr * 3, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(np.dstack([rgb.astype(np.uint8), a]), "RGBA").resize((1600, 1600), Image.LANCZOS).save(os.path.join(OUT, "disc_ring.png"))


def grid_maze(n=26, seed=11):
    R = random.Random(seed)
    W = 2 * n + 1
    g = np.ones((W, W), np.uint8)
    stack = [(0, 0)]; seen = {(0, 0)}; g[1, 1] = 0
    while stack:
        x, y = stack[-1]
        nb = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= x + dx < n and 0 <= y + dy < n and (x + dx, y + dy) not in seen]
        if not nb:
            stack.pop(); continue
        nx, ny = R.choice(nb)
        g[2 * ny + 1, 2 * nx + 1] = 0
        g[y + ny + 1, x + nx + 1] = 0
        seen.add((nx, ny)); stack.append((nx, ny))
    return g


def make_field():
    """Low-angle view over a bronze maze: shaded top-down, then perspective-warped."""
    g = grid_maze()
    S = 2600
    walls = Image.fromarray(g * 255).resize((S, S), Image.NEAREST)
    h = np.array(walls.filter(ImageFilter.GaussianBlur(6)), np.float32) / 255
    rgb = bronze_shade(h, light=(-0.4, -0.9, 0.35), rough=0.5, seed=4)
    # long cast shadows in the light direction (cheap: shifted blurred walls)
    sh = np.array(walls.transform(walls.size, Image.AFFINE, (1, 0, -10, 0, 1, -40)).filter(ImageFilter.GaussianBlur(18)), np.float32) / 255
    rgb *= (1 - 0.55 * sh * (1 - h))[..., None]
    top = Image.fromarray(rgb.astype(np.uint8))
    # perspective: map the square onto a trapezoid receding to a horizon
    W, Hh = 1920, 1080
    horizon = 300
    src = top
    # coefficients for PIL perspective (output->input mapping)
    def coeffs(pa, pb):
        m = []
        for p1, p2 in zip(pa, pb):
            m.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0] * p1[0], -p2[0] * p1[1]])
            m.append([0, 0, 0, p1[0], p1[1], 1, -p2[1] * p1[0], -p2[1] * p1[1]])
        A = np.array(m, np.float64); B = np.array(pb, np.float64).reshape(8)
        return np.linalg.solve(A, B).tolist()
    dst = [(-2600, Hh + 600), (W + 2600, Hh + 600), (W * 0.5 + 900, horizon), (W * 0.5 - 900, horizon)]
    srcq = [(0, S), (S, S), (S, 0), (0, 0)]
    field = src.transform((W, Hh), Image.PERSPECTIVE, coeffs(dst, srcq), Image.BICUBIC)
    f = np.array(field, np.float32)
    yy = np.mgrid[0:Hh, 0:W][0]
    # sky / haze
    sky = np.array([40, 26, 16], np.float32) + np.array([150, 100, 60], np.float32) * np.clip(1 - np.abs(yy - horizon) / 260, 0, 1)[..., None]
    mask = (yy > horizon)[..., None]
    haze = np.clip(1 - (yy - horizon) / 520, 0, 1)[..., None] ** 1.6
    f = np.where(mask, f * (1 - haze) + sky * haze, sky)
    # low sun on the horizon
    xx = np.mgrid[0:Hh, 0:W][1]
    sun = np.exp(-(((xx - W * 0.62) / 140) ** 2 + ((yy - horizon + 10) / 90) ** 2))[..., None]
    f = f + np.array([255, 190, 120]) * sun * 0.9
    Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).save(os.path.join(OUT, "field.png"))


if __name__ == "__main__":
    make_disc(); print("disc ok")
    make_field(); print("field ok")
