"""RIFE (PDF tool 3): 12 fps Blender frames -> 24 fps by inserting one in-between frame.

  python3 rife_seq.py renders/hp build/hp24
Output frames: 0001.png ... (2 x N). Run on CPU, flow computed at half size for speed.
"""
import os, sys
import cv2, numpy as np, torch
from torch.nn import functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "demo", "models", "RIFE"))
from train_log.RIFE_HDv3 import Model
torch.set_grad_enabled(False); torch.set_num_threads(os.cpu_count())
m = Model(); m.load_model(os.path.join(HERE, "..", "demo", "models", "RIFE", "train_log"), -1); m.eval(); m.device()

src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
files = sorted(f for f in os.listdir(src) if f.endswith(".png"))
frames = [cv2.imread(os.path.join(src, f)) for f in files]
H, W = frames[0].shape[:2]
ph, pw = ((H - 1) // 32 + 1) * 32, ((W - 1) // 32 + 1) * 32
T = lambda f: F.pad(torch.from_numpy(f.transpose(2, 0, 1).copy()).float()[None] / 255, (0, pw - W, 0, ph - H))
N = lambda t: (t[0, :, :H, :W].clamp(0, 1).numpy().transpose(1, 2, 0) * 255).round().astype(np.uint8)
k = 1
for i, f in enumerate(frames):
    cv2.imwrite(os.path.join(dst, f"{k:04d}.png"), f); k += 1
    nxt = frames[i + 1] if i + 1 < len(frames) else f
    mid = N(m.inference(T(f), T(nxt), 0.5)) if nxt is not f else f
    cv2.imwrite(os.path.join(dst, f"{k:04d}.png"), mid); k += 1
    if i % 20 == 0:
        print(f"{i}/{len(frames)}", flush=True)
print("rife ->", dst, k - 1, "frames")
