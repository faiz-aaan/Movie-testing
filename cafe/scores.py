"""Two original 30 s scores for EMBER ROAST, synthesized from scratch (no samples, no licences).

  python3 scores.py  ->  build/score_energetic.wav, build/score_calm.wav

Energetic: 120 BPM, hits locked to the edit (cut list in post.py), SFX for beans,
portafilter clack, pour, whoosh, steam hiss; a stop on "WAKE UP." then the drop.
Calm: ~72 BPM lo-fi: rain bed, vinyl crackle, Rhodes-style 7th chords, brushed beat.
"""
import os, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(11)


def lp(x, f, o=2): return sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)
def bp(x, a, b, o=2): return sosfilt(butter(o, [a, b], "band", fs=SR, output="sos"), x)


class Track:
    def __init__(self, dur):
        self.N = int(SR * dur); self.mix = np.zeros((self.N, 2)); self.dur = dur

    def put(self, at, sig, gain=1.0, pan=0.0):
        i0 = int(at * SR)
        if i0 >= self.N: return
        sig = sig[: self.N - i0] * gain
        self.mix[i0:i0 + len(sig), 0] += sig * (1 - max(pan, 0))
        self.mix[i0:i0 + len(sig), 1] += sig * (1 + min(pan, 0))

    def reverb(self, amount, decay=0.6):
        L = int(2.2 * SR); t = np.arange(L) / SR
        for c in range(2):
            ir = lp(rng.normal(0, 1, L), 7000) * np.exp(-t / decay)
            wet = fftconvolve(self.mix[:, c], ir)[: self.N]
            self.mix[:, c] += wet / (np.abs(wet).max() + 1e-9) * amount * np.abs(self.mix[:, c]).max()

    def write(self, path, fade_out=0.6):
        m = self.mix / (np.abs(self.mix).max() + 1e-9)
        m = np.tanh(m * 1.3); m *= 0.9 / np.abs(m).max()
        t = np.arange(self.N) / SR
        m *= np.clip((self.dur - t) / fade_out, 0, 1)[:, None]
        wavfile.write(path, SR, (m * 32767).astype(np.int16)); print("->", path)


def env(L, a, d):
    t = np.arange(L) / SR
    return np.clip(t / max(a, 1e-4), 0, 1) * np.exp(-np.maximum(t - a, 0) / d)


def kick(g=1.0):
    L = int(0.5 * SR); t = np.arange(L) / SR
    f = 45 + 110 * np.exp(-t / 0.04)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22)
    return np.tanh((s + lp(rng.normal(0, 1, L), 3000) * np.exp(-t / 0.004) * 0.4) * 2) * g


def clap():
    L = int(0.3 * SR); n = rng.normal(0, 1, L); e = np.zeros(L)
    for k in range(3): e[int(k * 0.011 * SR):] += np.exp(-np.arange(L - int(k * 0.011 * SR)) / (0.008 * SR))
    e[int(0.033 * SR):] += np.exp(-np.arange(L - int(0.033 * SR)) / (0.08 * SR))
    return bp(n, 900, 5000) * e * 0.8


def hat(open_=False):
    L = int((0.25 if open_ else 0.05) * SR)
    return hp(rng.normal(0, 1, L), 7000) * env(L, 0.001, 0.08 if open_ else 0.012) * 0.5


def sub(freq, dur):
    L = int(dur * SR); t = np.arange(L) / SR
    return np.tanh(np.sin(2 * np.pi * freq * t) * 1.5) * env(L, 0.005, dur * 0.6) * 0.8


def whoosh(dur=0.5, up=True):
    L = int(dur * SR); x = np.linspace(0, 1, L)
    n = rng.normal(0, 1, L); lo, hi = bp(n, 300, 1200), bp(n, 2000, 8000)
    shape = np.sin(np.pi * x) ** 2
    return (lo * (1 - x) + hi * x if up else lo * x + hi * (1 - x)) * shape * 0.7


def riser(dur):
    L = int(dur * SR); x = np.linspace(0, 1, L)
    n = rng.normal(0, 1, L)
    return (hp(n, 500) * (1 - x) * 0.3 + hp(n, 4000) * x) * x ** 2 * 0.6


def clack():
    L = int(0.15 * SR); t = np.arange(L) / SR
    tone = sum(np.sin(2 * np.pi * f * t) for f in (1800, 2650, 4100)) * np.exp(-t / 0.02)
    return (tone * 0.3 + hp(rng.normal(0, 1, L), 2000) * np.exp(-t / 0.006)) * 0.8


def rattle(dur):  # beans
    L = int(dur * SR); s = np.zeros(L)
    for _ in range(int(dur * 260)):
        i = rng.integers(0, L - 600); s[i:i + 600] += hp(rng.normal(0, 1, 600), 3000) * np.exp(-np.arange(600) / 60) * rng.uniform(0.2, 1)
    return s * np.linspace(1, 0.3, L) * 0.5


def pour(dur):
    L = int(dur * SR); n = rng.normal(0, 1, L)
    gurgle = np.sin(2 * np.pi * np.cumsum(500 + 300 * lp(rng.normal(0, 1, L), 8) * 40) / SR)
    return (bp(n, 600, 2500) * 0.4 + gurgle * 0.08) * np.clip(np.linspace(0, 6, L), 0, 1) * np.clip(np.linspace(6, 0, L), 0, 1) * 0.6


def hiss(dur):
    L = int(dur * SR)
    return hp(rng.normal(0, 1, L), 3500) * env(L, 0.03, dur * 0.7) * 0.6


def buzz(dur):
    L = int(dur * SR); t = np.arange(L) / SR
    b = np.sign(np.sin(2 * np.pi * 100 * t)) * 0.2 + np.sin(2 * np.pi * 50 * t) * 0.3
    gate = (rng.random(L // 2000 + 1) > 0.4).repeat(2000)[:L]
    return lp(b, 1500) * gate * 0.4


def braam(dur, f=41.2):
    L = int(dur * SR); t = np.arange(L) / SR
    s = sum(2 * ((t * f * m * d) % 1) - 1 for m in (1, 2, 3) for d in (1, 1.007))
    return np.tanh(lp(s, 700) * 2) * env(L, 0.02, dur * 0.4) * 0.5


def energetic():
    T = Track(30.0); beat = 0.5
    # SFX locked to picture
    T.put(0.0, buzz(1.0), 0.8)
    T.put(1.0, rattle(2.0), 0.9, 0.2)
    T.put(3.0, clack(), 1.2)
    T.put(4.05, pour(1.4), 0.9)
    T.put(5.45, whoosh(0.6), 1.0)
    T.put(6.0, hiss(1.0), 0.7, -0.3)
    T.put(7.0, whoosh(0.8, up=False), 0.6)
    T.put(8.5, riser(1.0), 1.0)
    T.put(9.5, kick(1.3), 1.0); T.put(9.5, braam(1.0), 0.9)          # WAKE UP. (stop)
    T.put(14.5, whoosh(0.4), 0.6); T.put(16.4, whoosh(0.5), 0.8)
    T.put(17.5, rattle(1.5), 0.6, -0.2)
    for k, at in enumerate((19.0, 19.5, 20.0)):                        # SIP. SMILE. REPEAT.
        T.put(at, kick(1.1), 1.0); T.put(at, clap(), 0.8)
    T.put(25.5, riser(0.0001), 0)
    T.put(28.5, kick(1.4), 1.0); T.put(28.5, braam(1.5, 36.7), 0.9)
    # groove: intro 0-9.5 (light), drop 10.5-19 (full), 20.5-28.5 (full), stops on cards
    bass_notes = [41.2, 41.2, 49.0, 36.7]
    t = 0.0
    while t < 28.5:
        bar = int(t / 2.0); pos = round((t % 2.0) / 0.125)
        full = (10.5 <= t < 19.0) or (20.5 <= t < 28.5)
        intro = t < 9.5
        stop = (9.5 <= t < 10.5) or (19.0 <= t < 20.5)
        if not stop:
            if pos in (0, 8) or (full and pos in (6, 11)):
                T.put(t, kick(), 0.9 if full else 0.6)
            if pos in (4, 12) and (full or t > 3):
                T.put(t, clap(), 0.7)
            if full or (intro and t > 1):
                T.put(t, hat(open_=(pos % 4 == 2)), 0.35 if pos % 2 else 0.5, 0.3)
            if full and pos in (0, 6, 8, 11):
                T.put(t, sub(bass_notes[bar % 4], 0.3), 0.7)
        t += 0.125
    # stab chords on the drop
    for at in (10.5, 14.5, 20.5, 24.5):
        L = int(0.4 * SR); tt = np.arange(L) / SR
        ch = sum(2 * ((tt * f) % 1) - 1 for f in (220, 261.6, 329.6, 392))
        T.put(at, lp(ch, 2500) * env(L, 0.005, 0.15) * 0.25, 1.0)
    T.reverb(0.12, 0.4)
    T.write(os.path.join(HERE, "build", "score_energetic.wav"), 0.3)


def rhodes(freqs, dur):
    L = int(dur * SR); t = np.arange(L) / SR; s = np.zeros(L)
    for f in freqs:
        for h, a in ((1, 1.0), (2, 0.35), (3, 0.12), (4, 0.06)):
            s += a * np.sin(2 * np.pi * f * h * t + 0.3 * np.sin(2 * np.pi * 5.5 * t)) * np.exp(-t * (0.6 + h * 0.5))
    trem = 1 + 0.12 * np.sin(2 * np.pi * 4.2 * t)
    return lp(s * trem, 3000) * env(L, 0.01, dur) / len(freqs) * 0.6


def calm():
    T = Track(30.0)
    N = T.N; t = np.arange(N) / SR
    # rain bed + drops on glass + vinyl crackle
    rain = bp(rng.normal(0, 1, N), 800, 6000) * 0.10 + lp(rng.normal(0, 1, N), 400) * 0.05
    drops = np.zeros(N)
    for _ in range(900):
        i = rng.integers(0, N - 400); drops[i:i + 400] += hp(rng.normal(0, 1, 400), 2500) * np.exp(-np.arange(400) / 40) * rng.uniform(0.05, 0.3)
    crackle = np.zeros(N)
    for _ in range(2200):
        i = rng.integers(0, N - 60); crackle[i:i + 60] += rng.normal(0, 1, 60) * np.exp(-np.arange(60) / 8) * rng.uniform(0.02, 0.15)
    bed = (rain + drops) * np.clip(t / 2.0, 0, 1)
    T.mix[:, 0] += bed + crackle; T.mix[:, 1] += np.roll(bed, 500) + crackle
    # chords: Fmaj7 Em7 Dm7 Cmaj7 (one per bar, bar = 4 beats at 72 BPM = 3.333 s)
    bar = 60 / 72 * 4
    chords = [(174.6, 220.0, 261.6, 329.6), (164.8, 196.0, 246.9, 293.7), (146.8, 174.6, 220.0, 261.6), (130.8, 164.8, 196.0, 246.9)]
    for k in range(9):
        at = 0.8 + k * bar
        T.put(at, rhodes(chords[k % 4], bar + 1.5), 1.0, (-0.2, 0.2)[k % 2])
        T.put(at, sub(chords[k % 4][0] / 2, bar * 0.8) * 0.5, 0.5)
    # soft lo-fi beat from 5 s to 27 s
    b = 60 / 72
    for k in range(int(22 / (b / 2))):
        at = 5.0 + k * b / 2
        if at > 27: break
        pos = k % 8
        if pos in (0, 5): T.put(at, lp(kick(0.5), 900), 0.5)
        if pos in (2, 6): T.put(at, lp(clap(), 2500), 0.25)
        T.put(at, lp(hat(), 6000), 0.12, 0.3)
    # cup clink on the steam shot, door-bell-ish chime on the sign
    L = int(1.2 * SR); tt = np.arange(L) / SR
    clink = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt / d) for f, d in ((2350, 0.25), (3720, 0.15), (5200, 0.08))) * 0.15
    T.put(10.4, clink, 1.0, 0.3)
    chime = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.6) for f in (1046.5, 1318.5, 1568.0)) * 0.08
    T.put(27.1, chime, 1.0); T.put(27.4, chime, 0.7)
    T.reverb(0.35, 0.9)
    T.write(os.path.join(HERE, "build", "score_calm.wav"), 2.5)


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    energetic(); calm()
