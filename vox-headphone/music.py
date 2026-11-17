"""Short punk-zine bed for the 20 s collage film: 132 bpm, E minor, kick/snare/hat + electric bass. Original, samples CC0 (FreePats / Versilian)."""
import os, sys, numpy as np, soundfile as sf
LIB = os.environ.get('LIB', '/root/lemo-opuscar'); sys.path.insert(0, LIB)
from core.audio import sampler as S
from core.audio.sfx import SR, limit
D = 20.2; BEAT = 60 / 132; ev = []
ROOT = {0: 40, 1: 40, 2: 43, 3: 38}                      # E2 E2 G2 D2 per bar
for bar in range(int(D / (4 * BEAT)) + 1):
    t0 = bar * 4 * BEAT; r = ROOT[bar % 4]
    for q in range(4):
        ev.append((t0 + q * BEAT, 'bass_drum', None, None, .75 if q % 2 == 0 else .5, 0, .8))
        if q % 2 == 1: ev.append((t0 + q * BEAT, 'snare', None, None, .7, 0, .7))
    for e in range(8): ev.append((t0 + e * BEAT / 2, 'hihat', None, None, .3 + .1 * (e % 2 == 0), .2, .4))
    for e in range(8): ev.append((t0 + e * BEAT / 2, 'electric_bass', r + (12 if e in (3, 6) else 0), .3, .55, 0, .7))
S.seed(3)
m = S.render(ev, dur=D, master=True)
m = m[:int(D * SR)]
n = int(.8 * SR); m[-n:] *= np.linspace(1, 0, n)[:, None]
sf.write('out_music.wav', m.astype(np.float32), SR)
print('music ok', m.shape)
