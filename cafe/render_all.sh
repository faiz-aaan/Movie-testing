#!/bin/bash
# Render both films (energetic then calm) with Blender in background mode.
B=${BLENDER:-/opt/blender/blender-5.2.4-linux-x64/blender}
cd "$(dirname "$0")"
for film in energetic calm; do
  $B -b -P cafe_scene.py -- $film 2>&1 | grep --line-buffered -E "SHOT|ALL DONE|Traceback|Error:"
done
