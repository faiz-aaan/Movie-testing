"""PDF tool #2: Depth Anything V2 (Small, Apache-2.0) -> depth map for parallax."""
import sys, numpy as np, torch
from PIL import Image
from transformers import pipeline
src, out = sys.argv[1], sys.argv[2]
pipe = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device=-1)
img = Image.open(src).convert("RGB")
d = np.array(pipe(img)["predicted_depth"].squeeze(), np.float32)  # relative inverse depth (near = high)
d = (d - d.min()) / (d.max() - d.min() + 1e-6)
Image.fromarray((d * 255).astype(np.uint8)).resize(img.size, Image.BICUBIC).save(out)
print("depth saved", out, img.size)
