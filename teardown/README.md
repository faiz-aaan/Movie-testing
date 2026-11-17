# Teardown film: Nothing Headphone (1) + Vu TV (30 s, 9:16)

A vertical "exploded view" teardown made from the user's own phone footage plus a procedural 3D model.

## Pipeline

| Step | Script | What it does |
|---|---|---|
| Real shots | `ffmpeg` (vidstab) | Stabilises 3.4-6.6 s (headphones) and 12.1-14.3 s (TV) of the raw footage |
| Exploded views | `teardown_scene.py` (Blender, Eevee, CPU) | Headphone cup stands up and explodes into a vertical stack; TV lies flat and fans into layers. Writes `track.json` with each labelled part's screen position per frame |
| Smoothing | `rife_seq.py` (RIFE) | 12 fps render -> 24 fps |
| Edit + labels | `compose_teardown.py` | Joins real and CGI, pins labels to moving parts, titles, grade, grain, end card |
| Sound | `td_score.py` | Original synthesised sound design locked to the cuts |

## Honesty notes

* The exploded geometry is an **illustrative model**, not a scan of the user's units. Nobody physically opened these products.
* No public teardown of the Headphone (1) gives its Bluetooth chip or battery capacity, so those are **not** claimed. The Vu TV's model and chips are unknown, so its layout is labelled "typical LED TV".

## Spec sources used for the headphone labels

* 40 mm dynamic drivers, 20 Hz-40 kHz, four microphones, Bluetooth 5.3, LDAC, USB-C + 3.5 mm: iFixit device page https://www.ifixit.com/Device/Nothing_Headphone_%281%29
* KEF acoustic tuning, memory-foam cushions: KEF product page https://us.kef.com/products/nothing-headphone-1 and retailer listings
* Adaptive ANC up to 42 dB, up to 80 h playback (ANC off), roller / paddle / custom button: Android Authority https://www.androidauthority.com/nothing-headphone-1-3572665/ and retailer listings
