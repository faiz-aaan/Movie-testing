"""PDF step 5 (Color): write a 33^3 .cube LUT, the same output color-grade-ai produces.
Diagnosis of the raw frames: blacks a touch milky, highlights clip to hard white,
mid-tone orange too saturated (reads 'digital'). Fix: warm-bronze split tone,
filmic highlight roll-off, -12% saturation, deeper toe. Loadable in Resolve / Premiere too."""
import numpy as np, os
N = 33
g = np.linspace(0, 1, N)
b, gg, r = np.meshgrid(g, g, g, indexing="ij")  # .cube order: r fastest
rgb = np.stack([r, gg, b], -1)
lum = (rgb * [0.2126, 0.7152, 0.0722]).sum(-1, keepdims=True)
rgb = lum + (rgb - lum) * 0.88                               # desaturate 12%
rgb = np.clip(rgb, 0, 1) ** 1.08                              # deeper toe
rgb = np.where(rgb < 0.7, rgb, 0.7 + 0.3 * np.tanh((rgb - 0.7) / 0.3))  # roll-off above 70% only
sh = np.clip(1 - lum * 2.2, 0, 1); hi = np.clip(lum * 1.6 - 0.6, 0, 1)
rgb += sh * np.array([0.012, 0.004, -0.006]) + hi * np.array([0.02, 0.008, -0.03])  # split tone
rgb = np.clip(rgb, 0, 1)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kronos_bronze.cube")
with open(out, "w") as f:
    f.write('TITLE "KRONOS bronze"\nLUT_3D_SIZE 33\n')
    for v in rgb.reshape(-1, 3):
        f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
print("lut ->", out)
