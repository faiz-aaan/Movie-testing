"""PDF step 7 (Finish): Real-ESRGAN (xinntao, BSD-3) x2 upscale 1080p -> 2160p (4K UHD).
Loaded with spandrel; tiled so it runs on a CPU without a graphics card."""
import sys, numpy as np, torch
from PIL import Image
from spandrel import ModelLoader
torch.set_grad_enabled(False)
model = ModelLoader().load_from_file(sys.argv[3] if len(sys.argv) > 3 else "models/RealESRGAN_x2plus.pth").eval()
img = np.asarray(Image.open(sys.argv[1]).convert("RGB"), np.float32) / 255
x = torch.from_numpy(img.transpose(2, 0, 1))[None]
s, T, P = model.scale, 360, 16
_, _, h, w = x.shape
out = torch.zeros(1, 3, h * s, w * s)
for y0 in range(0, h, T):
    for x0 in range(0, w, T):
        ya, xa = max(y0 - P, 0), max(x0 - P, 0)
        yb, xb = min(y0 + T + P, h), min(x0 + T + P, w)
        o = model(x[:, :, ya:yb, xa:xb])
        out[:, :, y0 * s:min(y0 + T, h) * s, x0 * s:min(x0 + T, w) * s] = \
            o[:, :, (y0 - ya) * s:(y0 - ya + min(T, h - y0)) * s, (x0 - xa) * s:(x0 - xa + min(T, w - x0)) * s]
Image.fromarray((out[0].clamp(0, 1).numpy().transpose(1, 2, 0) * 255).round().astype(np.uint8)).save(sys.argv[2])
print("esrgan ->", sys.argv[2], f"{w}x{h} -> {w*s}x{h*s}")
