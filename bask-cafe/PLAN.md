# Bask by Coffee, Palavakkam: 30 s intro film (plan)

## Context
The user wants a 30 s, 9:16 "product-launch style" intro for Bask by Coffee (D4, MGR Salai, Palavakkam, Chennai) to bring people in. It has music only, with no voiceover. The reference lyric videos (Coolie "Powerhouse", Leo "Badass", plus the two other links) are used for **graphic grammar only**: no people, no colours, no frames are copied. The base images are photos the user provides (the user's choice). Google Maps photos are not used: I can't fetch them (429 / redirect), and many are customer uploads the café doesn't own.

## What we borrow from the references (grammar, not look)
1. **Giant kinetic type living in 3D space.** Words stand in the room behind or between objects, as in "PODUSUNGALUKUM".
2. **One-accent graphic grade.** The world is pushed to near-monochrome texture, with one loud accent colour (Leo: yellow + blood red).
3. **Hero objects on a textured surface.** Props are lit like product shots, with stencil/ink/grain textures.
4. **Hard cuts on beats, slow pushes between them, and the wordmark as the final hit.**

## Design direction: "Espresso Noir × Terracotta"
- **Palette, taken from the café itself:** charcoal and espresso black, cream paper, and **terracotta/cognac** (the leather booths) as the only accent. Warm bulb-gold is used for light glows only.
- **Texture:** ink/stencil grain on walls and floor, and latte-art swirls as a recurring graphic motif.
- **Type:** a heavy condensed display font (open licence, e.g. Anton or Bebas Neue, OFL) in cream, with a terracotta underline. All text is rendered in code, not by AI, so it stays crisp.
- **Sound:** original 90–100 bpm groove (bass, brushed kit, Rhodes) built with the library sampler (CC0). Silence on the logo hit.

## Storyboard (9:16, 30 s, 8 shots)
| # | s | Picture | Type on screen |
|---|---|---|---|
| 1 | 0–2.5 | Black. A drop of espresso falls in slow motion; a crema swirl blooms | — |
| 2 | 2.5–6 | Stylised façade/bungalow from the user's photo; push in through the black steel windows | **BASK** builds letter by letter behind the window frames |
| 3 | 6–10 | Terracotta booth row, monochrome except the leather; the camera glides along | **SINK IN.** |
| 4 | 10–13 | Industrial hall, string bulbs ignite one by one on the beat | **STAY A WHILE** |
| 5 | 13–17 | Hero product: latte art on a textured table, ink splash radiates (Leo grammar) | **POUR / SIP / REPEAT** (3 hard cuts) |
| 6 | 17–21 | Food hero: pizza, churros, pasta, three quick 3D-feel orbits | dish names, small caps |
| 7 | 21–26 | Courtyard/greenery seating at dusk, slow pull-out | **YOUR TABLE IS WAITING** |
| 8 | 26–30 | Logo card: cup silhouette, crema swirl forms the wordmark | **BASK BY COFFEE · PALAVAKKAM · Open till 11 pm** |

## Production pipeline
1. **Inputs:** 6–10 user photos (façade, booths, hall, coffee, 2–3 dishes, courtyard, the logo if available) via Drive link.
2. **Look samples (gate 1):** 3 sample frames with Higgsfield `nano_banana_2_1`, using the user's photos as `image_references` and the prompt from the design direction above. Cost about 1 credit. The user approves the look.
3. **Keyframes:** one per shot (about 8 images, ~2 credits); review the sheet (gate 2).
4. **Motion:** `seedance_2_0_mini` image-to-video, 5 s, 720p, `generate_audio:false`. That is 6 clips ≈ 30 credits. Shot 1 and the logo card are made in code. Submit 2–3 at a time (429 rate limit seen before).
5. **Type and compositing:** a lemo-opuscar page (`window.render(t)` contract, `/root/lemo-opuscar/core/render/video.mjs`). It layers the clips plus kinetic type plus grain at 24 fps, 1080×1920.
6. **Music:** an original track with `core/audio/sampler.py` (pattern from `vox-headphone/music.py`), mastered with `core/render/mux.sh` to −14 LUFS.
7. **Deliver:** mp4, poster, storyboard sheet, CREDITS (photo source = user/café; fonts OFL; samples CC0). Commit to `ccr-0dcd4ec4-f1ovk9` under `bask-cafe/`, with media gitignored.

**Budget:** about 33 credits for the whole film. Check the balance first.

## Verification
- A contact sheet every 2 s, and a check that the type is readable at phone size.
- `ffprobe`: 1080×1920, 24 fps, 30 s. ebur128 −14 LUFS; no black frames except the intended opening.
- No faces or other brands; the café name and hours match the listing.

## Needed from the user before step 2
Photos (Drive link), and the café's logo or the exact spelling "Bask by Coffee".
