"""Map data for "Where a Headphone Comes From": download public tiles, build terrain assets.

Levels
  delta : the Pearl River Delta (detail the camera flies over)   terrain z10, imagery z11
  wide  : East Asia backdrop (Baotou ... Shenzhen ... Taiwan)    terrain z6,  imagery z7
  world : whole Earth for the globe shots                         imagery z4 (equirectangular)

Sources (no Google/Bing/Esri/Mapbox imagery):
  elevation + bathymetry : AWS Terrain Tiles ("terrarium" PNG), free with attribution
  imagery                : EOX Sentinel-2 cloudless 2016 (s2cloudless_3857), CC BY 4.0
  No border data is downloaded or drawn.

usage (library root):  .venv/bin/python -I <project>/tools/data.py <project>
Writes <project>/raw/*, <project>/assets/{delta,wide}_{height.bin,albedo.jpg,water.png,shadow.png,meta.json}, assets/world.jpg
"""
import sys, os, io, json, math, time, datetime, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
from scipy import ndimage

P = sys.argv[1]
RAW = os.path.join(P, 'raw'); OUT = os.path.join(P, 'assets')
os.makedirs(RAW, exist_ok=True); os.makedirs(OUT, exist_ok=True)
Image.MAX_IMAGE_PIXELS = None
UA = {'User-Agent': 'headphone-supply-map/1.0 (film research)'}
LOG = open(os.path.join(RAW, 'manifest.jsonl'), 'a')
TERRAIN = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
BM = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg'   # NASA Blue Marble Next Generation (clean colour base)
S2 = 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg'   # 2016 release only


def get(url):
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                b = r.read()
            LOG.write(json.dumps({'url': url, 'bytes': len(b), 'date': datetime.date.today().isoformat()}) + '\n')
            return b
        except Exception:
            if k == 4: raise
            time.sleep(2 + 3 * k)


def tile_xy(lon, lat, z):
    n = 2 ** z
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def merc(lon, lat, z):
    n = 2 ** z * 256
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def mosaic(name, tmpl, z, box):
    W, S, E, N = box
    ext = 'png' if 'terrarium' in tmpl else 'jpg'
    dst = os.path.join(RAW, f'{name}_z{z}.{ext}')
    x0, y0 = tile_xy(W, N, z); x1, y1 = tile_xy(E, S, z)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    if not os.path.exists(dst):
        jobs = [(x, y) for y in range(ty0, ty1 + 1) for x in range(tx0, tx1 + 1)]
        im = Image.new('RGB', ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
        with ThreadPoolExecutor(8) as ex:
            for (x, y), b in ex.map(lambda j: (j, get(tmpl.format(z=z, x=j[0], y=j[1]))), jobs):
                im.paste(Image.open(io.BytesIO(b)).convert('RGB'), ((x - tx0) * 256, (y - ty0) * 256))
        im.save(dst, quality=95) if ext == 'jpg' else im.save(dst)
        print('downloaded', name, z, len(jobs), 'tiles', flush=True)
    return dst, {'z': z, 'tx0': tx0, 'ty0': ty0}


def build(level, box, zt, zi, ex_ds=4, sea_depth_scale=90.0):
    """terrain + imagery -> height grid, graded albedo, water mask, meta"""
    W, S, E, N = box
    tpath, tm = mosaic(level + '_terrain', TERRAIN, zt, box)
    ipath, im_ = mosaic(level + '_s2', S2, zi, box)
    x0, y0 = merc(W, N, zi); x1, y1 = merc(E, S, zi)
    ox, oy = im_['tx0'] * 256, im_['ty0'] * 256
    img = Image.open(ipath).convert('RGB').crop((int(x0 - ox), int(y0 - oy), int(x1 - ox), int(y1 - oy)))
    IW, IH = img.size
    tx0, ty0 = merc(W, N, zt); tx1, ty1 = merc(E, S, zt)
    t = np.asarray(Image.open(tpath).convert('RGB'), np.float64)
    h = t[..., 0] * 256 + t[..., 1] + t[..., 2] / 256 - 32768
    ys = (np.arange(IH) + .5) / IH * (ty1 - ty0) + ty0 - tm['ty0'] * 256 - .5
    xs = (np.arange(IW) + .5) / IW * (tx1 - tx0) + tx0 - tm['tx0'] * 256 - .5
    X, Y = np.meshgrid(xs, ys)
    hi = ndimage.map_coordinates(h, [Y, X], order=3, mode='nearest').astype(np.float32)

    a = np.asarray(img, np.float32) / 255
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = .3 * r + .59 * g + .11 * b
    watery = (b > r + .015) & (lum < .42)
    # sea = below sea level, or clearly water-coloured and low. (hi <= 1 alone swallowed the delta's flat lowlands)
    water = (hi < -0.5) | (watery & (hi < 6)) | ((hi <= 0.5) & (lum < .30))
    water = ndimage.binary_opening(water, iterations=2)
    water = ndimage.binary_closing(water, iterations=2)
    lab, n = ndimage.label(water)
    sizes = ndimage.sum(water, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool); keep[1:] = sizes > {'delta': 4000, 'mid': 1500, 'wide': 600}[level]
    water = keep[lab]
    land = ~water
    hl = np.where(land, np.maximum(hi, 2.0), np.minimum(hi, -1.0))
    dist_land = ndimage.distance_transform_edt(water)

    lin = a ** 2.2
    L = lin.copy()
    l = (L * [.2126, .7152, .0722]).sum(-1, keepdims=True)
    L = l + (L - l) * .82
    L = L * np.array([1.06, 1.0, .88])
    L = np.clip(L * .9, 0, 1)
    L = L ** 1.12 * 1.08
    if level in ('mid', 'wide'):
        # clean colour from NASA Blue Marble (no swath/cloud patchwork); the Sentinel-2 imagery only contributes fine detail (brightness ratio)
        zbm = 8 if level == 'mid' else 7
        bpath, bt = mosaic(level + '_bm', BM, zbm, box)
        bx0, by0 = merc(W, N, zbm); bx1, by1 = merc(E, S, zbm)
        bimg = Image.open(bpath).convert('RGB').crop((int(bx0 - bt['tx0'] * 256), int(by0 - bt['ty0'] * 256), int(bx1 - bt['tx0'] * 256), int(by1 - bt['ty0'] * 256)))
        B = (np.asarray(bimg.resize((IW, IH), Image.LANCZOS), np.float32) / 255) ** 2.2
        lb = (B * [.2126, .7152, .0722]).sum(-1, keepdims=True)
        B = lb + (B - lb) * .95
        B = np.clip(B * np.array([1.08, 1.0, .9]) * 1.05, 0, 1)
        sig = 12 if level == 'mid' else 5
        ratio = np.clip(lum / (ndimage.gaussian_filter(lum, sig) + 1e-3), .66, 1.5)[..., None]
        L = np.clip(B * ratio, 0, 1) ** 1.05
    depth = np.clip(-hl, 0, 120 if level == 'delta' else 4000)
    sh = np.exp(-depth / 9.0)
    sh = np.maximum(sh, np.exp(-dist_land / {'delta': 5.0, 'mid': 3.0, 'wide': 2.0}[level]) * .6)
    deep = np.array([.008, .030, .066]); mid = np.array([.014, .055, .095]); teal = np.array([.03, .17, .19])
    dd = np.clip(depth / (90 if level == 'delta' else 3000), 0, 1)[..., None]
    sea = mid * (1 - dd) + deep * dd
    s2sea = lin * np.array([.55, .95, 1.0])
    shallow = .55 * teal + .45 * s2sea
    sea = sea * (1 - sh[..., None] * .85) + shallow * (sh[..., None] * .85)
    wm = ndimage.gaussian_filter(water.astype(np.float32), 1.2)[..., None]
    alb = L * (1 - wm) + sea * wm
    Image.fromarray((np.clip(alb, 0, 1) ** (1 / 2.2) * 255 + .5).astype(np.uint8)).save(os.path.join(OUT, f'{level}_albedo.jpg'), quality=93)
    Image.fromarray((wm[..., 0] * 255).astype(np.uint8)).resize((IW // 2, IH // 2), Image.LANCZOS).save(os.path.join(OUT, f'{level}_water.png'))

    GW, GH = IW // ex_ds, IH // ex_ds
    hg = np.asarray(Image.fromarray(hl).resize((GW, GH), Image.BILINEAR), np.float32)
    hg.astype('<f4').tofile(os.path.join(OUT, f'{level}_height.bin'))
    latc = (S + N) / 2
    km_px = 40075.016 * math.cos(math.radians(latc)) / (2 ** zi * 256)
    meta = {'GW': GW, 'GH': GH, 'IW': IW, 'IH': IH, 'bbox': [W, S, E, N], 'z': zi, 'merc': [x0, y0, x1, y1], 'km_px': km_px,
            'width_km': IW * km_px, 'height_km': IH * km_px, 'hmax': float(hl.max()), 'hmin': float(hl.min())}
    json.dump(meta, open(os.path.join(OUT, f'{level}_meta.json'), 'w'), indent=1)
    print(level, meta, flush=True)
    return meta


def bake(level, EX=3.2, reach=40.0, up=2):
    """low-sun shadows baked into a texture (no shadow maps at render time)"""
    SUN = np.array([-150.0, 62.0, -70.0])
    hor = math.hypot(SUN[0], SUN[2]); TAN = SUN[1] / hor
    dx, dz = SUN[0] / hor, SUN[2] / hor
    m = json.load(open(os.path.join(OUT, f'{level}_meta.json')))
    GW, GH = m['GW'], m['GH']
    h = np.fromfile(os.path.join(OUT, f'{level}_height.bin'), '<f4').reshape(GH, GW)
    y = np.maximum(h, 0) / 1000 * EX
    if up > 1: y = ndimage.zoom(y, up, order=1)
    H, Wd = y.shape
    kx = m['width_km'] / (Wd - 1); kz = m['height_km'] / (H - 1)
    step = min(kx, kz) * 0.75
    R, C = np.mgrid[0:H, 0:Wd].astype(np.float32)
    occ = np.zeros_like(y); d = step
    while d < reach:
        rr = R + dz * d / kz; cc = C + dx * d / kx
        hs = ndimage.map_coordinates(y, [rr, cc], order=1, mode='nearest')
        occ = np.maximum(occ, (hs - (y + d * TAN)) / (0.02 + d * 0.04))
        d += step * (1 + d / 25)
    lit = np.clip(1 - occ, 0, 1); lit = lit * lit * (3 - 2 * lit)
    Image.fromarray((lit * 255 + .5).astype(np.uint8)).save(os.path.join(OUT, f'{level}_shadow.png'))
    print(level, 'shadow', Wd, H, flush=True)


def world(Z=4):
    n = 2 ** Z
    src = os.path.join(RAW, f'world_s2_z{Z}.jpg')
    if not os.path.exists(src):
        im = Image.new('RGB', (n * 256, n * 256))
        jobs = [(x, y) for y in range(n) for x in range(n)]
        with ThreadPoolExecutor(8) as ex:
            for (x, y), b in ex.map(lambda j: (j, get(S2.format(z=Z, x=j[0], y=j[1]))), jobs):
                im.paste(Image.open(io.BytesIO(b)).convert('RGB'), (x * 256, y * 256))
        im.save(src, quality=94)
    m = np.asarray(Image.open(src).convert('RGB'), np.float32)
    H = Wd = n * 256; OW, OH = 4096, 2048
    lon = (np.arange(OW) + .5) / OW * 360 - 180
    lat = 90 - (np.arange(OH) + .5) / OH * 180
    latc = np.clip(lat, -85.05, 85.05)
    Xs = (lon + 180) / 360 * Wd - .5
    Ys = (1 - np.log(np.tan(np.radians(latc)) + 1 / np.cos(np.radians(latc))) / math.pi) / 2 * H - .5
    XX, YY = np.meshgrid(Xs, Ys)
    out = np.stack([ndimage.map_coordinates(m[..., c], [YY, XX], order=1, mode='nearest') for c in range(3)], -1)
    a = (out / 255) ** 2.2
    l = (a * [.2126, .7152, .0722]).sum(-1, keepdims=True)
    water = (a[..., 2:3] > a[..., 0:1] + .01) & (l < .08)
    a = l + (a - l) * .85
    a = a * np.array([1.05, 1.0, .9])
    a = np.where(water, a * .55 + np.array([.004, .014, .03]), a)
    polar = np.abs(lat)[:, None, None] > 84
    a = np.where(polar, np.array([.55, .58, .62]), a)
    Image.fromarray((np.clip(a, 0, 1) ** (1 / 2.2) * 255 + .5).astype(np.uint8)).save(os.path.join(OUT, 'world.jpg'), quality=92)
    print('world.jpg', OW, OH, flush=True)


if __name__ == '__main__':
    # lon/lat boxes: west, south, east, north
    build('delta', (112.9, 21.9, 115.2, 23.7), zt=10, zi=11)
    build('mid', (109.5, 18.0, 119.5, 27.5), zt=8, zi=9, ex_ds=6)
    build('wide', (100.0, 14.0, 128.0, 44.0), zt=6, zi=7)
    for lv in ('delta', 'mid', 'wide'):
        bake(lv, reach={'delta': 40, 'mid': 50, 'wide': 60}[lv])
    world()


def fix_mid():
    """The 2016 mosaic has swath and cloud patchwork. For the mid level, keep the colour of the already-flattened wide
    imagery (low frequency) and the mid imagery's own fine detail (high frequency), on land only."""
    mm = json.load(open(os.path.join(OUT, 'mid_meta.json'))); wmx = json.load(open(os.path.join(OUT, 'wide_meta.json')))
    mid = np.asarray(Image.open(os.path.join(OUT, 'mid_albedo.jpg')).convert('RGB'), np.float32) / 255
    wide = Image.open(os.path.join(OUT, 'wide_albedo.jpg')).convert('RGB')
    water = np.asarray(Image.open(os.path.join(OUT, 'mid_water.png')).resize((mid.shape[1], mid.shape[0]), Image.BILINEAR), np.float32) / 255
    W, S, E, N = mm['bbox']; zw = wmx['z']
    x0, y0 = merc(W, N, zw); x1, y1 = merc(E, S, zw)
    wx0, wy0, _, _ = wmx['merc']
    crop = wide.crop((int(x0 - wx0), int(y0 - wy0), int(x1 - wx0), int(y1 - wy0))).resize((mid.shape[1], mid.shape[0]), Image.BICUBIC)
    lp = np.asarray(crop, np.float32) / 255
    lum = (mid * [.3, .59, .11]).sum(-1)
    ratio = np.clip(lum / (ndimage.gaussian_filter(lum, 14) + 1e-3), .66, 1.5)[..., None]
    fixed = np.clip(lp * ratio, 0, 1)
    wm_ = ndimage.gaussian_filter(water, 3)[..., None]
    out = mid * wm_ + fixed * (1 - wm_)                 # sea keeps its own depth shading
    Image.fromarray((out * 255 + .5).astype(np.uint8)).save(os.path.join(OUT, 'mid_albedo.jpg'), quality=93)
    print('mid albedo fixed', out.shape, flush=True)
