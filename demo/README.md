# KRONOS: 15-second demo brand film

A proof of what the Launch Film Kit pipeline can do with **zero paid credits**. Every graphic, the music and the type are generated from code. The look is borrowed from the graphical (non-human) parts of two lyric videos: *Jailer 2 – One Sun One Moon* and *Vidaamuyarchi – Pathikichu*.

Final film: `output/kronos_demo_1080p60.mp4`  (1920×1080, 60 fps, original score)

## Pipeline (in order)

| Step | Script | Tool | What it does |
|---|---|---|---|
| 1 Plan | (this README / shot list below) | Claude | script + shot list |
| 2 Visuals | `assets.py` | Python + NumPy | builds the bronze maze dial and 3D maze field |
| 3 Depth | `depth.py` | **Depth Anything V2 Small** | depth map → parallax camera move + rack focus |
| — Score | `score.py` | NumPy/SciPy synth | original 96 BPM trailer score locked to the cuts |
| 4 Edit/Animate | `render.py` | OpenCV + Pillow + ffmpeg | 5 shots, kinetic type, particles, grain |
| 5 Color | `gen_lut.py` → `kronos_bronze.cube` | color-grade-ai method | .cube LUT (also loads in Resolve/Premiere) |
| 6 Smooth | `rife60.py` | **RIFE (ECCV2022, HD v3)** | 24 → 96 → 60 fps |
| 7 Finish | `esrgan4k.py` | **Real-ESRGAN x2plus** | 1080p → 4K (shown on the end-card frame) |

## Shot list

| Time | Shot | Borrowed technique |
|---|---|---|
| 0.0–2.5 | Credits resolve letter by letter in dust | wide-tracked serif credits (both refs) |
| 2.5–6.0 | Bronze maze dial push-in, **TIME** drops on the beat | CG hero object + maze motif (ref 2), dropping letters (ref 1) |
| 6.0–9.0 | Depth push over 3D maze at sunset, **BENDS** warps | depth/parallax and rack focus, type placed in the scene (ref 2) |
| 9.0–11.5 | Red/yellow halftone chapter, **FOR NO ONE** in brush type, ink wipe | red chapter (ref 1) + comic halftone interlude (ref 2) |
| 11.5–15 | **KRONOS** assembles from scattered letters, sparks, tagline | title assembly + end card on the motif (both refs) |

## Rebuild

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install transformers spandrel opencv-python-headless scipy gdown
# models (not committed): Real-ESRGAN weights from xinntao/Real-ESRGAN releases,
# RIFE HD weights per hzwer/ECCV2022-RIFE README -> demo/models/RIFE/train_log
python3 assets.py && python3 depth.py build/field.png build/field_depth.png
python3 score.py && python3 render.py
python3 gen_lut.py && ffmpeg -i build/master_24.mp4 -vf lut3d=kronos_bronze.cube build/graded_24.mp4
python3 rife60.py build/graded_24.mp4 build/graded_60.mp4
ffmpeg -i build/graded_60.mp4 -i build/score.wav -c:v copy -c:a aac -shortest output/kronos_demo_1080p60.mp4
```

Licences: Depth Anything V2 Small – Apache-2.0; RIFE – MIT; Real-ESRGAN – BSD-3; fonts – SIL OFL / Apache. KRONOS is a fictional brand.
