"""Sound for 'Where a Headphone Comes From': English narration + original score + foley on one 34 s timeline.

A minor, 90 bpm: one beat = 0.667 s, one bar = 2.667 s. Cues come from events.json (exported from the page) and voice/cues.json.
Voice: compressed, music about 10 dB under it (RMS over the spoken parts), music carved at 300 Hz-4 kHz and ducked under each line.
Silences on purpose: 0-0.7 s (air only), 21.1-22.0 s (the breath before the three lines ignite), and the last 0.6 s.

usage:  LIB=/root/lemo-opuscar $LIB/.venv/bin/python mix.py        writes out/mix.wav and out/instruments.txt
"""
import json, os, sys
import numpy as np, soundfile as sf, soxr
LIB = os.environ.get('LIB', '/root/lemo-opuscar')
sys.path.insert(0, LIB)
from core.audio import sampler as S
from core.audio.sfx import SR, bp, lp, hp, add, compress, limit, click, whoosh, thump, ding, ignite as ignite_fx

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, 'events.json')))
FULL = float(D['dur']); EV = D['ev']
CUES = json.load(open(os.path.join(HERE, 'voice', 'cues.json')))
N = int(FULL * SR) + SR
tt = np.arange(N) / SR
rng = np.random.default_rng(5)
BEAT = 60 / 90; BAR = 4 * BEAT
evs = lambda k: [e for e in EV if e['type'] == k]


def env(points):
    ts, vs = zip(*points); return np.interp(tt, ts, vs)


def st(x): return np.stack([x, np.roll(x, 1511)], 1)


mix = np.zeros((N, 2)); music = np.zeros((N, 2))

# ---------------- beds ----------------
air = bp(rng.standard_normal(N), 220, 4200, 2) * env([(0, .012), (.7, .014), (4.4, .014), (6.5, .004), (22, .004), (24, .01), (26.2, .006), (31, .006), (33.4, .004), (FULL, 0)])
low = lp(rng.standard_normal(N), 180, 2) * env([(0, 0), (1.2, .02), (21.1, .02), (21.6, .03), (22.0, 0), (FULL, 0)])
for x in (air, low): mix += st(x)

# ---------------- score ----------------
ev = []
CH = {'Am': [45, 52, 57, 60, 64], 'F': [41, 48, 53, 57, 60], 'C': [36, 43, 48, 52, 55], 'G': [43, 50, 55, 59, 62]}
PROG = ['Am', 'F', 'C', 'G']
PENTA = [69, 72, 74, 76, 79, 81, 84, 86, 88, 91]            # A minor pentatonic, A4 upward
breath0, breath1 = 21.1, 22.0
bar_start = lambda b: (b - 1) * BAR
for b in range(3, 13):                                       # bars 3-12 carry the pulse (5.33 s to 32 s)
    t0 = bar_start(b); c = CH[PROG[(b - 3) % 4]]
    for q in range(4):
        t = t0 + q * BEAT
        if breath0 <= t < breath1: continue
        ev.append((t, 'contrabass_pizz', c[0] if q % 2 == 0 else c[1], .5, .5 if q == 0 else .38, -.05, .55))
    if b >= 5:                                               # harp arpeggio from the lithium pillar on
        pat = [1, 2, 3, 2, 1, 3, 2, 4] if b % 2 else [1, 3, 2, 3, 1, 2, 4, 3]
        for i, k in enumerate(pat):
            t = t0 + i * BEAT / 2
            if breath0 <= t < breath1: continue
            ev.append((t, 'harp', c[k] + 12, 1.0, .3 + .07 * (i % 4 == 0), -.25 + .07 * i, .4))
    if b >= 7:
        for q in (1, 3):
            t = t0 + q * BEAT
            if not (breath0 <= t < breath1): ev.append((t, 'violins_pizz', c[3] + 12, .3, .3, .35, .28))
    if not (breath0 <= t0 < breath1): ev.append((t0, 'frame_drum', 'large_muted', None, .4, 0, .45))
# opening: low bowed pedal, one chime on the pin, a held fifth
ev += [(0.9, 'cellos', 'A2', 4.4, .3, 0, .3), (1.0, 'hang', 'E4', 2.5, .3, -.3, .35), (2.6, 'hang', 'A4', 2.5, .28, .3, .3)]
for e in evs('pin'): ev.append((e['t'], 'hand_chimes', 'A5', 2.5, .5, .3, .5))
# rise 4.4: a horn swell into the first pillar, drum on the pillar
ev += [(4.4, 'horn', 'A2', 2.4, .35, -.1, .28), (4.4, 'horn', 'E3', 2.4, .3, .1, .22)]
for e in evs('pillar'): ev.append((e['t'], 'frame_drum', 'large', None, .55, 0, .6))
# slabs: one plucked note per slab, rising up the scale
for e in evs('slab'):
    n = len([x for x in evs('slab') if x['pillar'] == e['pillar']])
    ev.append((e['t'], 'harp', PENTA[min(9, e['i'] * 10 // max(1, n))], .6, .36 + .02 * e['i'], -.3 + .6 * e['i'] / max(1, n - 1), .5))
# breath: the music thins to a low pedal at 21.1; the three lines ignite on 22.0
ev += [(breath0 - .1, 'contrabass', 'A1', 2.2, .4, 0, .35)]
ig = evs('ignite')
for k, e in enumerate(ig):
    ev.append((e['t'], 'glockenspiel', [81, 84, 88][k], 1.2, .34, -.4 + .4 * k, .34))
    ev.append((e['t'], 'hand_chimes', [76, 79, 83][k], 1.8, .3, .4 - .4 * k, .3))
ev += [(ig[0]['t'], 'frame_drum', 'large', None, .62, 0, .7), (ig[0]['t'], 'cellos', 'A2', 2.4, .42, -.2, .34), (ig[0]['t'], 'timpani', 'A2', 1.6, .42, 0, .4)]
# dive into the hub 24.0: horn chord climbs; hub 26.2: one low hit and one chime
ev += [(24.0, 'horn', 'F3', 2.2, .36, -.1, .26), (24.0, 'horn', 'C4', 2.2, .32, .1, .22)]
hub = evs('hub')[0]['t']
ev += [(hub, 'contrabass', 'C2', 2.4, .5, 0, .45), (hub, 'hand_chimes', 'E6', 2.4, .42, .3, .4), (hub, 'timpani', 'C3', 1.5, .4, 0, .4)]
for k, e in enumerate(evs('lane')): ev.append((e['t'], 'harp', [88, 84][k], 1.6, .42, [.5, -.5][k], .45))
# pull-out: strings rise to the Am add9; the chord lands on the bar line at 32.0 with a harp run leading in at 31.8
fin = evs('final')[0]['t']
for i, p in enumerate([33, 45, 52, 57, 59, 64, 69]): ev.append((fin + i * .03, 'harp', p, 3.0, .5, -.3 + i * .1, .5))
ev += [(32.0, 'cellos', 'A2', 2.0, .38, 0, .3), (32.0, 'violas', 'E4', 2.0, .3, 0, .22), (32.0, 'glockenspiel', 'B6', 2.0, .3, .3, .26)]
for e in evs('close'): ev += [(e['t'], 'hang', 'A4', 1.2, .3, -.2, .28), (e['t'], 'hand_chimes', 'E6', 1.2, .3, .3, .25)]
S.seed(13)
sc = S.render(ev, dur=FULL + 1, master=False)[:N]
f0 = 55.0
drone = np.sin(2 * np.pi * f0 * tt) + .4 * np.sin(4 * np.pi * f0 * tt) + .15 * np.sin(6 * np.pi * f0 * tt)
drone *= env([(0, 0), (.9, .02), (5, .026), (21.0, .03), (21.1, .04), (21.9, .04), (22.0, .05), (31, .035), (33.0, .03), (33.6, 0), (FULL, 0)])
sc += st(drone)
sw = bp(rng.standard_normal(N), 300, 3000, 1)
swell = np.zeros(N)
for a, b in [(3.7, 4.4), (21.1, 22.0), (25.3, 26.2), (29.9, 30.6)]:    # four risers; the last two lead the picture by about a second
    swell += np.clip((tt - a) / (b - a), 0, 1) ** 3 * (tt < b)
sc += st(sw * swell * .05)
sc = np.stack([hp(sc[:, c], 32, 2) for c in range(2)], 1)
sc = S.room(sc, size=.5, mix=.2)
music += sc

# ---------------- foley driven by the picture ----------------
for e in EV:
    k, t = e['type'], e['t']
    if k == 'rise': add(mix, lp(whoosh(1.8, 1.0), 2200) * .08, t - .1, 1, 0)
    elif k == 'slab': add(mix, hp(click(pitch=1.3 + .05 * e['i'], v=1.0), 1800) * .035, t, 1, -.2 + .4 * (e['i'] % 3) / 2)
    elif k == 'pillar': add(mix, thump(1.0, 60) * .12, t, 1, 0)
    elif k == 'ignite':
        add(mix, thump(1.0, 52) * .18, t, 1, 0); add(mix, ignite_fx(.6) * .08, t, 1, [-.4, 0, .4][e['i']])
    elif k == 'dive': add(mix, lp(whoosh(1.6, 1.0), 2400) * .1, t - .2, 1, 0)
    elif k == 'hub': add(mix, thump(1.0, 46) * .2, t, 1, 0)
    elif k == 'lane': add(mix, lp(whoosh(1.4, 1.0), 2000) * .07, t, 1, [.4, -.4][e['i']])
    elif k == 'pull': add(mix, lp(whoosh(2.0, 1.0), 1500) * .08, t - .1, 1, 0)
    elif k == 'final': add(mix, ding(1.0) * .03, t + .2, 1, .3)

# carve the voice band out of the music
mid = np.stack([bp(music[:, c], 300, 4000, 2) for c in range(2)], 1)
music = music - mid * (1 - 10 ** (-4 / 20))

# ---------------- narration ----------------
voice = np.zeros(N); active = np.zeros(N)
for c in CUES:
    x, sr = sf.read(os.path.join(HERE, 'voice', c['id'] + '.wav'), dtype='float64')
    if x.ndim > 1: x = x.mean(1)
    if sr != SR: x = soxr.resample(x, sr, SR)
    i = int(c['t0'] * SR); j = min(N, i + len(x)); voice[i:j] += x[:j - i]; active[i:j] = 1
voice = hp(voice, 80, 2)
voice = compress(voice, thr=.18, ratio=3.0)
duck = np.convolve(active, np.ones(int(.25 * SR)) / int(.25 * SR), 'same')
duck = 1 - .45 * np.clip(duck * 1.4, 0, 1)
music = music * duck[:, None]
vr = np.sqrt((voice[active > 0] ** 2).mean()); voice *= .16 / vr
mr = np.sqrt((music[active > 0] ** 2).mean()); music *= (.16 * 10 ** (-10 / 20)) / mr
fr = np.sqrt((mix[active > 0] ** 2).mean()); mix *= min(1.0, (.16 * 10 ** (-12 / 20)) / max(fr, 1e-9))
mix += music + np.stack([voice, voice], 1)

out = mix[:int(FULL * SR)].copy()
nf = int(.6 * SR); out[-nf:] *= np.linspace(1, 0, nf)[:, None] ** 1.5       # the last 0.6 s fades to silence
out = np.stack([compress(out[:, 0], thr=.35, ratio=2.0), compress(out[:, 1], thr=.35, ratio=2.0)], 1)
out = np.stack([limit(out[:, 0]), limit(out[:, 1])], 1)
os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
sf.write(os.path.join(HERE, 'out', 'mix.wav'), out.astype(np.float32), SR)
used = ['harp', 'cellos', 'contrabass', 'contrabass_pizz', 'frame_drum', 'hang', 'hand_chimes', 'horn', 'glockenspiel', 'violins_pizz', 'violas', 'timpani']
cr = S.credits(used)
open(os.path.join(HERE, 'out', 'instruments.txt'), 'w').write('\n'.join(cr) if isinstance(cr, list) else str(cr))
vo = 20 * np.log10(np.sqrt((voice[active > 0] ** 2).mean())); mu = 20 * np.log10(np.sqrt((music[active > 0] ** 2).mean()))
print(f'mix {FULL}s peak {np.abs(out).max():.3f}  voice {vo:.1f} dB  music under voice {mu:.1f} dB  (gap {vo - mu:.1f} dB)')
