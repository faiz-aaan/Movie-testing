#!/bin/sh
# Bask by Coffee 30 s intro: 7 Seedance clips + end card + code-set type + original music -> 1080x1920, 24 fps, -14 LUFS
set -e; cd "$(dirname "$0")"
PATH=$(ls -d /home/user/tools/ffmpeg-*-amd64-static | head -1):$PATH
FB=/home/user/Movie-testing/headphone-supply-map/fonts/BarlowCondensed-SemiBold.ttf
V="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24,setsar=1"
# shot: input, start-in-clip, duration
ffmpeg -v error -y \
 -i clips/s1.mp4 -i clips/s2.mp4 -i clips/s3.mp4 -i clips/s4.mp4 -i clips/s5.mp4 -i clips/s6.mp4 -i clips/s7.mp4 \
 -loop 1 -t 4 -i build/endcard.png -i build/music.wav -filter_complex "
[0:v]trim=0.3:2.8,setpts=PTS-STARTPTS,$V[a];
[1:v]trim=0.5:4.0,setpts=PTS-STARTPTS,$V[b];
[2:v]trim=0.5:4.5,setpts=PTS-STARTPTS,$V[c];
[3:v]trim=1.0:4.0,setpts=PTS-STARTPTS,$V[d];
[4:v]trim=0:4,setpts=PTS-STARTPTS,$V,zoompan=z='if(lt(on,32),1.0,if(lt(on,64),1.18,1.36))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=24[e];
[5:v]trim=0.5:4.5,setpts=PTS-STARTPTS,$V[f];
[6:v]trim=0:5,setpts=PTS-STARTPTS,$V[g];
[7:v]$V,zoompan=z='1+0.0008*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=24,trim=0:4,setpts=PTS-STARTPTS[h];
[a][b][c][d][e][f][g][h]concat=n=8:v=1:a=0,format=yuv420p[cat];
[cat]subtitles=type.ass:fontsdir=/home/user/Movie-testing/headphone-supply-map/fonts,fade=t=in:st=0:d=0.4:color=white,fade=t=out:st=29.3:d=0.7[v]" \
 -map "[v]" -map 8:a -t 30 -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -c:a aac -b:a 192k build/raw.mp4
ffmpeg -v error -y -i build/raw.mp4 -af loudnorm=I=-14:TP=-1.2:LRA=9 -c:v copy -c:a aac -b:a 192k bask-by-coffee-intro.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 bask-by-coffee-intro.mp4
