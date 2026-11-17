"""Original 15s trailer score, synthesized from scratch (no samples, no licences).

96 BPM. Hits are placed on the film's cut points so picture and sound lock together.
Writes build/score.wav (48 kHz stereo).
"""
import os, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
DUR = 15.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(5)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "score.wav")

# Cut points shared with render.py
HITS = {"s2": 2.5, "time": 3.75, "s3": 6.0, "s4": 9.0, "noone": 9.6, "s5": 11.5, "title": 12.05}


def lp(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)


def env(start, attack, decay, length=None):
    e = np.zeros(N)
    i0 = int(start * SR)
    L = int((length or (attack + decay * 6)) * SR)
    tt = np.arange(min(L, N - i0)) / SR
    a = np.clip(tt / max(attack, 1e-4), 0, 1)
    e[i0:i0 + len(tt)] = a * np.exp(-np.maximum(tt - attack, 0) / decay)
    return e


def saw(f, ph=0.0):
    return 2 * ((t * f + ph) % 1) - 1


mix = np.zeros((N, 2))

# 1) Drone: detuned low saws, slow swell, filtered dark
drone = sum(saw(55 * d, rng.random()) for d in (1.0, 1.004, 0.996, 2.002))
drone = lp(drone, 220) * 0.18
swell = np.clip(t / 2.5, 0, 1) * (1 - 0.6 * ((t > 9.0) & (t < 11.5)))
swell *= np.clip((15.0 - t) / 0.8, 0, 1)
mix += (drone * swell)[:, None]

# 2) Clock tick on 8ths (watch brand motif) during shots 2-3
beat = 60 / 96
tick = np.zeros(N)
for k in range(64):
    s = HITS["s2"] + k * beat / 2
    if s >= HITS["s4"]:
        break
    i = int(s * SR)
    L = int(0.03 * SR)
    burst = rng.normal(0, 1, L) * np.exp(-np.arange(L) / (0.004 * SR))
    tick[i:i + L] += burst * (0.5 if k % 2 else 0.8)
tick = hp(tick, 3000) * 0.22
mix[:, 0] += tick * 0.8
mix[:, 1] += tick


# 3) Taiko / sub hits (pitch-drop sine + noise)
def boom(at, gain=1.0, f0=110, f1=38):
    i0 = int(at * SR)
    L = int(1.6 * SR)
    tt = np.arange(L) / SR
    f = f1 + (f0 - f1) * np.exp(-tt / 0.06)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-tt / 0.45)
    click = lp(rng.normal(0, 1, L), 1800) * np.exp(-tt / 0.02) * 0.6
    sig = np.tanh((body + click) * 1.6) * gain
    seg = slice(i0, min(N, i0 + L))
    mix[seg] += sig[: seg.stop - seg.start, None] * 0.55


for k, g in (("s2", 0.8), ("time", 1.0), ("s3", 0.9), ("s4", 1.0), ("noone", 0.8), ("s5", 0.7), ("title", 1.25)):
    boom(HITS[k], g)
boom(0.15, 0.35, 70, 30)

# 4) Risers before s4 and before s5 (filtered noise sweeps)
for a, b in ((7.6, 9.0), (10.4, 11.5)):
    m = (t >= a) & (t < b)
    x = (t - a) / (b - a)
    noise = rng.normal(0, 1, N)
    r = np.zeros(N)
    # time-varying highpass approximation: crossfade bands
    lo, hi = hp(noise, 400), hp(noise, 3000)
    r[m] = (lo[m] * (1 - x[m]) + hi[m] * x[m]) * x[m] ** 2
    mix[:, 0] += r * 0.12
    mix[:, 1] += np.roll(r, 300) * 0.12

# 5) Red-chapter bass pulse: distorted 8ths 9.0-11.4
pulse = np.zeros(N)
for k in range(16):
    s = HITS["s4"] + k * beat / 2
    if s > 11.35:
        break
    pulse += env(s, 0.004, 0.09) * saw(41.2)
pulse = np.tanh(lp(pulse, 400) * 3) * 0.16
mix += pulse[:, None]

# 6) Braam on the end card
braam = sum(saw(f * d) for f in (36.7, 73.4, 110.0) for d in (1.0, 1.006))
braam = np.tanh(lp(braam, 900) * 2.2) * env(HITS["title"] - 0.02, 0.03, 0.9, 3.0) * 0.20
mix += braam[:, None]

# 7) Shimmer pad on the logo
pad = sum(np.sin(2 * np.pi * f * t + rng.random() * 6) for f in (440, 554.4, 659.3, 880))
pad = pad * np.clip((t - 12.3) / 0.8, 0, 1) * np.clip((15.0 - t) / 1.2, 0, 1) * 0.025
mix[:, 0] += pad
mix[:, 1] += np.roll(pad, 600)

# Reverb: convolve with decaying stereo noise IR
L = int(1.8 * SR)
ir_t = np.arange(L) / SR
irs = [lp(rng.normal(0, 1, L), 6000) * np.exp(-ir_t / 0.45) for _ in range(2)]
wet = np.stack([fftconvolve(mix[:, c], irs[c])[:N] for c in range(2)], 1)
wet /= np.abs(wet).max() + 1e-9
out = mix + wet * 0.18 * np.abs(mix).max()
out = np.tanh(out / (np.abs(out).max() + 1e-9) * 1.4)
out *= 0.89 / np.abs(out).max()
fade = np.clip((15.0 - t) / 0.4, 0, 1)[:, None]
out *= fade
os.makedirs(os.path.dirname(OUT), exist_ok=True)
wavfile.write(OUT, SR, (out * 32767).astype(np.int16))
print("score ->", OUT)
