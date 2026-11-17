"""Original 30 s sound design for the teardown film (synthesised, no samples).

Cut list (seconds, global): real HP 0-3.2 | CGI HP 3.2-18.1 | real TV 18.1-20.3 | CGI TV 20.3-28.5 | end card 28.5-30
Writes build/td_score.wav
"""
import os, sys, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "cafe"))
import scores as S
from scipy.signal import butter, sosfilt

SR = S.SR
T = S.Track(30.0)
rng = np.random.default_rng(21)

HP0, TV0 = 3.2, 20.3
HP_LABELS = [6.6, 7.4, 8.2, 9.0, 9.8, 10.6]
TV_LABELS = [2.9, 3.5, 4.1, 4.7, 5.3, 5.9]


def blip(f=1760, d=0.14, g=0.5):
    L = int(d * SR); t = np.arange(L) / SR
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2 * t)) * np.exp(-t / 0.05) * g


def tick():
    L = int(0.03 * SR)
    return S.hp(rng.normal(0, 1, L), 4000) * np.exp(-np.arange(L) / (0.005 * SR)) * 0.5


def pluck(f, d=0.5):
    L = int(d * SR); t = np.arange(L) / SR
    s = sum(2 * ((t * f * k) % 1) - 1 for k in (1, 1.005)) * np.exp(-t / 0.18)
    return S.lp(s, 2800) * 0.22


def sweep_down(dur=0.9):
    L = int(dur * SR); x = np.linspace(0, 1, L)
    n = rng.normal(0, 1, L)
    return (S.bp(n, 400, 2500) * x + S.hp(n, 3000) * (1 - x) * 0.3) * (x ** 2) * 0.5


# --- drone bed (whole film) ---
t = np.arange(T.N) / SR
drone = S.lp(sum(2 * ((t * 55 * d) % 1) - 1 for d in (1, 1.004, 2.003)), 260) * 0.12
drone *= np.clip(t / 2.0, 0, 1) * np.clip((30 - t) / 1.2, 0, 1)
T.mix += drone[:, None]

# --- opening: real headphones shot ---
T.put(1.4, S.riser(1.8), 0.9)
T.put(3.0, S.whoosh(0.4), 0.9)
T.put(HP0, S.kick(1.3), 1.0); T.put(HP0, S.braam(1.2, 41.2), 0.8)

# --- sparse arpeggio + ticks under the CGI sections ---
notes = [220.0, 261.6, 329.6, 392.0, 329.6, 261.6, 440.0, 392.0]
for base, end in ((HP0 + 1.0, 17.8), (TV0 + 0.8, 28.2)):
    s_, k = base, 0
    while s_ < end:
        T.put(s_, pluck(notes[k % 8]), 0.5 if k % 2 == 0 else 0.35, (-0.3, 0.3)[k % 2])
        T.put(s_, tick(), 0.3)
        s_ += 0.27272; k += 1          # 110 BPM 8ths
T.put(HP0 + 2.0, S.sub(55, 0.6), 0.5)

# --- headphones CGI ---
T.put(HP0 + 3.0 - 0.1, S.whoosh(0.7), 0.9)                  # band + left cup fly off
T.put(HP0 + 4.6, S.whoosh(0.5, up=False), 0.7)              # cup stands up
for i in range(8):                                          # explode: clack per part
    T.put(HP0 + 4.7 + 0.06 * i + 0.2, S.clack(), 0.6, (-0.4, 0.4)[i % 2])
T.put(HP0 + 4.5, sweep_down(1.0), 0.8)
for k, lt in enumerate(HP_LABELS):
    T.put(HP0 + lt, blip(1760 if k % 2 == 0 else 1320), 0.7, (0.4, -0.4)[k % 2])
T.put(HP0 + 12.3, S.riser(0.5), 0.8)
for i in range(8):
    T.put(HP0 + 12.65 + 0.04 * i, S.clack(), 0.5)
T.put(HP0 + 13.7, S.kick(1.1), 0.9)
T.put(HP0 + 13.4, S.whoosh(0.9), 0.8)

# --- real TV shot ---
T.put(17.6, S.whoosh(0.5), 0.9)
T.put(18.1, S.hat(True), 0.8); T.put(18.1, S.sub(55, 0.5), 0.6)
T.put(19.0, S.riser(1.3), 0.9)
T.put(TV0, S.kick(1.3), 1.0); T.put(TV0, S.braam(1.2, 36.7), 0.8)

# --- TV CGI ---
T.put(TV0 + 0.9, sweep_down(0.9), 0.8)
for i in range(6):
    T.put(TV0 + 1.0 + 0.09 * i + 0.15, S.clack(), 0.6, (-0.4, 0.4)[i % 2])
for k, lt in enumerate(TV_LABELS):
    T.put(TV0 + lt, blip(1568 if k % 2 == 0 else 1175), 0.7, (0.4, -0.4)[k % 2])
T.put(TV0 + 6.6, S.riser(0.5), 0.8)
for i in range(6):
    T.put(TV0 + 6.85 + 0.05 * i, S.clack(), 0.5)

# --- end card ---
T.put(28.5, S.kick(1.4), 1.0); T.put(28.5, S.braam(1.6, 36.7), 0.9)
L = int(1.5 * SR); tt = np.arange(L) / SR
chime = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.7) for f in (880, 1318.5, 1760)) * 0.07
T.put(28.7, chime, 1.0)

T.reverb(0.16, 0.5)
os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
T.write(os.path.join(HERE, "build", "td_score.wav"), 0.5)
