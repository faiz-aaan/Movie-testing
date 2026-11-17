"""Original score for the City Symphony test: kick on every cut, 8th-note hats, low drone. Synthesised, no samples."""
import sys, numpy as np
from scipy.io import wavfile
sys.path.insert(0, "/home/user/Movie-testing/cafe")
import scores as S
T = S.Track(20.0)
t = np.arange(T.N) / S.SR
drone = S.lp(sum(2 * ((t * 55 * d) % 1) - 1 for d in (1, 1.004, 2.003)), 240) * 0.10
T.mix += (drone * np.clip(t / 1.5, 0, 1) * np.clip((20 - t) / 0.6, 0, 1))[:, None]
for at in (2.6, 5.8, 9.0, 12.8, 17.0, 19.5):          # cut points from TREATMENT.md
    T.put(at, S.kick(0.6), 0.6)
for k in range(int(19.5 / 0.25)):                       # 120 BPM 8ths
    at = k * 0.25
    if at > 19.4: break
    T.put(at, S.hat(open_=(k % 4 == 2)), 0.35 if k % 2 else 0.5, 0.25)
T.reverb(0.08, 0.35)
T.write("mix.wav", 0.5)
