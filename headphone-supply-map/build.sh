#!/bin/sh
# One command: "Where a Headphone Comes From" (3D Map Explainer, 34 s, 24 fps, English narration + original score)
#   sh build.sh               data and voice if missing, cues, events, picture, mix, master, subtitles, readcheck, poster
#   FETCH=1 sh build.sh       re-download every map tile and rebuild the terrain assets first (several minutes, ~100 MB)
#   VOICE=1 sh build.sh       regenerate the narration before the speech check
#   WORKERS=3 SIZE=1920x1080 sh build.sh
# Needs the library (LIB), its voice tier (Kokoro, faster-whisper) and the VSCO 2 CE, VCSL and FreePats sample libraries.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LIB=${LIB:-/root/lemo-opuscar}
export LIB
[ -f "$LIB/core/render/video.mjs" ] || { echo "set LIB to the library folder"; exit 1; }
PY=${PY:-"$LIB/.venv/bin/python"}
NAME=headphone-supply-map
WORKERS=${WORKERS:-3}; SIZE=${SIZE:-1920x1080}
cd "$LIB"
mkdir -p "$HERE/out" "$HERE/stills" "$HERE/raw" "$HERE/assets"

# map data (public tiles, see CREDITS): delta z10/z11, east China z8/z9, wider region z6/z7, baked low-sun shadows; every download is logged in raw/manifest.jsonl
if [ "${FETCH:-0}" = "1" ] || [ ! -f "$HERE/assets/wide_shadow.png" ]; then
  "$PY" -I "$HERE/tools/data.py" "$HERE"; "$PY" -I "$HERE/tools/blend.py" "$HERE"
fi

# narration: Kokoro, one clip per line in voice/; every clip must pass the speech-to-text check
if [ "${VOICE:-0}" = "1" ] || [ ! -f "$HERE/voice/l1.wav" ]; then "$PY" core/tts/tts.py "$HERE/voice/lines.json" "$HERE/voice"; fi
"$PY" core/tts/asr_check.py "$HERE/voice/lines.json" "$HERE/voice" --lang en
python3 "$HERE/tools/cues.py"

node core/render/events.mjs "$HERE"
node core/render/video.mjs "$HERE" --fps 24 --workers "$WORKERS" --size "$SIZE" --out "$HERE/out/video.mp4"
"$PY" -I "$HERE/mix.py"
sh core/render/mux.sh "$HERE/out/video.mp4" "$HERE/out/mix.wav" "$HERE/$NAME.mp4" 24 1
"$PY" core/render/srt.py "$HERE/voice/cues.json" "$HERE/$NAME.srt"

node core/render/readcheck.mjs "$HERE" > "$HERE/out/readcheck.txt" && echo "readcheck ok" || { tail -20 "$HERE/out/readcheck.txt"; exit 1; }
node core/render/still.mjs "$HERE" 32.6 --size "$SIZE" --q nosubs=1 --out "$HERE/out/poster" > /dev/null
ffmpeg -v error -y -i "$HERE/out/poster/t_32.6.jpg" -q:v 3 "$HERE/poster.jpg"
echo "done: $HERE/$NAME.mp4"
