"""Feather the sharp delta imagery into the mid level so no rectangular seam shows, and match brightness."""
import json, sys, numpy as np
from PIL import Image
from scipy import ndimage
P = sys.argv[1]
dm = json.load(open(f'{P}/assets/delta_meta.json')); mm = json.load(open(f'{P}/assets/mid_meta.json'))
d = np.asarray(Image.open(f'{P}/assets/delta_albedo.jpg.orig' if __import__('os').path.exists(f'{P}/assets/delta_albedo.jpg.orig') else f'{P}/assets/delta_albedo.jpg').convert('RGB'), np.float32) / 255
m = np.asarray(Image.open(f'{P}/assets/mid_albedo.jpg').convert('RGB'), np.float32) / 255
IH, IW = d.shape[:2]
# delta pixel -> mid pixel (z11 -> z9 is /4)
ys, xs = np.mgrid[0:IH, 0:IW].astype(np.float32)
mx = (dm['merc'][0] + xs) / 4 - mm['merc'][0]; my = (dm['merc'][1] + ys) / 4 - mm['merc'][1]
mr = np.stack([ndimage.map_coordinates(m[..., c], [my, mx], order=1, mode='nearest') for c in range(3)], -1)
# tone the delta down toward the mid grade (its roads and roofs stay brighter), then feather at the border
d = np.clip(d * .86, 0, 1)
edge = np.minimum.reduce([xs, ys, IW - 1 - xs, IH - 1 - ys]) / (0.16 * min(IW, IH))
w = np.clip(edge, 0, 1) ** 1.6
out = d * w[..., None] + mr * (1 - w[..., None])
import shutil, os
src = f'{P}/assets/delta_albedo.jpg'
if not os.path.exists(src + '.orig'): shutil.copy(src, src + '.orig')
Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(src, quality=93)
print('delta feathered')
