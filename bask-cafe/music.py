"""Original 30 s bright groove for the Bask intro: 100 bpm, D major, piano chords + electric bass + kit + claps + chimes.
Arc: 0-2.5 swell (pour), 2.5 kick on BASK, 6.0 groove in, 13-17 snare hits POUR/SIP/REPEAT, 21-26 opens up, 26 drop to one chime, silence at end.
Samples CC0 (FreePats / Versilian). usage: LIB=/root/lemo-opuscar $LIB/.venv/bin/python -I music.py"""
import os, sys, numpy as np, soundfile as sf
LIB = os.environ.get('LIB', '/root/lemo-opuscar'); sys.path.insert(0, LIB)
from core.audio import sampler as S
from core.audio.sfx import SR, bp, whoosh, lp
D = 30.0; BEAT = 0.6; BAR = 2.4; ev = []
CH = [[50, 62, 66, 69], [47, 59, 62, 66], [43, 55, 59, 62], [45, 57, 61, 64]]   # D  Bm  G  A
# intro pad 0-2.5
ev += [(0.0, 'piano', 74, 2.4, .35, -.2, .5), (0.6, 'piano', 78, 2.0, .3, .2, .45), (1.2, 'piano', 81, 1.6, .3, 0, .4), (2.5, 'bass_drum', None, None, .9, 0, 1.0), (2.5, 'crash', None, None, .5, .2, .35)]
t = 2.5; b = 0
while t < 26.0:
    c = CH[b % 4]; groove = t >= 6.0
    for i, p in enumerate(c[1:]): ev.append((t + i * .02, 'piano', p, BAR * .9, .42, -.2 + .2 * i, .5))
    for q in range(8):
        tt = t + q * BEAT / 2
        if tt >= 26.0: break
        ev.append((tt, 'electric_bass', c[0] - 12 + (7 if q in (3, 6) else 0), .28, .6, 0, .75))
        if groove:
            ev.append((tt, 'hihat', None, None, .25 + .1 * (q % 2 == 0), .25, .35))
            if q in (0, 4): ev.append((tt, 'bass_drum', None, None, .8, 0, .9))
            if q in (2, 6): ev.append((tt, 'claps', None, None, .6, 0, .6))
    t += BAR; b += 1
for tt in (13.0, 14.33, 15.67): ev.append((tt, 'snare', None, None, .9, 0, .8))          # POUR / SIP / REPEAT
for k, tt in enumerate((10.2, 10.6, 11.0, 11.4, 11.8)): ev.append((tt, 'glockenspiel', [86, 88, 90, 93, 95][k], .8, .35, -.4 + .2 * k, .35))   # globes pop
ev += [(26.0, 'hand_chimes', 81, 3.0, .55, 0, .6), (26.0, 'piano', 62, 3.5, .4, 0, .45), (26.0, 'piano', 69, 3.5, .35, 0, .4)]
S.seed(9)
m = S.render(ev, dur=D, master=True)[:int(D * SR)]
n = len(m); tt = np.arange(n) / SR
rng = np.random.default_rng(1)
sw = bp(rng.standard_normal(n), 400, 5000, 1) * np.clip((tt - .2) / 2.3, 0, 1) ** 3 * (tt < 2.5) * .08     # pour swell
for a in (17.0, 18.0, 19.0, 20.0):                                                                          # food whooshes
    w = lp(whoosh(.6, 1.0), 4000) * .08; i = int(a * SR); m[i:i + len(w)] += w[:, None]
m[:, 0] += sw; m[:, 1] += sw
f = int(1.2 * SR); m[-f:] *= np.linspace(1, 0, f)[:, None] ** 2
sf.write('build/music.wav', (m / max(1e-9, np.abs(m).max()) * .9).astype(np.float32), SR); print('music ok')
