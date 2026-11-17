"""PDF step 6 (Smooth): RIFE (ECCV2022-RIFE, HD v3 weights) 24fps -> 96fps (2 recursive
midpoint passes, = the repo's --exp 2) -> ffmpeg resample to 60fps."""
import os, subprocess, sys, time
import cv2, numpy as np, torch
from torch.nn import functional as F
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "models", "RIFE"))
from train_log.RIFE_HDv3 import Model
torch.set_grad_enabled(False); torch.set_num_threads(os.cpu_count())
m = Model(); m.load_model(os.path.join(HERE, "models", "RIFE", "train_log"), -1); m.eval(); m.device()
src, dst = sys.argv[1], sys.argv[2]
SCALE = float(os.environ.get("RIFE_SCALE", "0.5"))
limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
cap = cv2.VideoCapture(src)
frames = []
while True:
    ok, f = cap.read()
    if not ok: break
    frames.append(f)
if limit: frames = frames[:limit]
H, W = frames[0].shape[:2]
ph, pw = ((H - 1) // 32 + 1) * 32, ((W - 1) // 32 + 1) * 32
def T(f): return F.pad(torch.from_numpy(f.transpose(2, 0, 1)).float()[None] / 255, (0, pw - W, 0, ph - H))
def N(t): return (t[0, :, :H, :W].clamp(0, 1).numpy().transpose(1, 2, 0) * 255).round().astype(np.uint8)
ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", "96", "-i", "-",
                       "-vf", "fps=60", "-c:v", "libx264", "-crf", "12", "-preset", "medium", "-pix_fmt", "yuv420p", dst], stdin=subprocess.PIPE)
t0 = time.time()
for i in range(len(frames) - 1):
    a, b = T(frames[i]), T(frames[i + 1])
    mid = m.inference(a, b, SCALE)
    q1, q3 = m.inference(a, mid, SCALE), m.inference(mid, b, SCALE)
    for x in (frames[i], N(q1), N(mid), N(q3)):
        ff.stdin.write(np.ascontiguousarray(x).tobytes())
    if i % 20 == 0: print(f"pair {i}/{len(frames)-1}  {time.time()-t0:.0f}s", flush=True)
ff.stdin.write(frames[-1].tobytes()); ff.stdin.close(); ff.wait()
print("rife ->", dst, f"{time.time()-t0:.0f}s")
