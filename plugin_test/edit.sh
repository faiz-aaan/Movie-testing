#!/bin/bash
# City Symphony cut list from TREATMENT.md (edit time, src in-out, speed). Stabilized picture only.
export PATH=$(ls -d /home/user/tools/ffmpeg-*-amd64-static | head -1):$PATH
set -e; cd "$(dirname "$0")"; mkdir -p parts
# name     src_start src_end speed
cuts="
s1 0.0 6.0 2.3
s2 2.0 5.2 1.0
s3 4.6 6.2 0.5
s4 10.0 17.6 2.0
s5 16.4 18.5 0.5
s6 18.5 23.5 2.0
"
i=0
while read n a b s; do
  [ -z "$n" ] && continue
  ffmpeg -v error -y -ss $a -to $b -i stab.mp4 -vf "setpts=(PTS-STARTPTS)/$s,fps=24" -an -c:v libx264 -crf 16 -preset fast -pix_fmt yuv420p parts/$n.mp4
done <<< "$cuts"
# hard cut to black for the last 0.5 s
ffmpeg -v error -y -f lavfi -i color=c=black:s=1080x1920:r=24:d=0.5 -c:v libx264 -crf 16 -pix_fmt yuv420p parts/black.mp4
: > list.txt
for n in s1 s2 s3 s4 s5 s6 black; do echo "file 'parts/$n.mp4'" >> list.txt; done
ffmpeg -v error -y -f concat -safe 0 -i list.txt -c copy picture.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 picture.mp4
