#!/bin/sh
# Assemble the 20 s punk-zine collage film: 4 Seedance clips (clips/c1-c4.mp4) + local Kokoro narration (voice/v*.wav) + music bed + burned captions
set -e
cd "$(dirname "$0")"
PATH=$(ls -d /home/user/tools/ffmpeg-*-amd64-static | head -1):$PATH
F=/home/user/Movie-testing/headphone-supply-map/fonts
ffmpeg -v error -y -i clips/c1.mp4 -i clips/c2.mp4 -i clips/c3.mp4 -i clips/c4.mp4 \
  -i voice/v1.wav -i voice/v2.wav -i voice/v3.wav -i voice/v4.wav -i out_music.wav -filter_complex "
[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0,fps=24,subtitles=captions.srt:fontsdir=$F:force_style='FontName=Barlow Condensed,FontSize=20,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,BackColour=&H99000000,Outline=2,MarginV=14,Alignment=2'[v];
[4:a]adelay=400|400[a1];[5:a]adelay=5440|5440[a2];[6:a]adelay=10480|10480[a3];[7:a]adelay=15520|15520[a4];
[a1][a2][a3][a4]amix=inputs=4:normalize=0,aformat=channel_layouts=stereo,asplit=2[vo][vk];
[8:a]volume=0.55[mu];[mu][vk]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[md];
[vo][md]amix=inputs=2:normalize=0,alimiter=limit=0.9[a]" -map "[v]" -map "[a]" -t 20.17 -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k raw.mp4
ffmpeg -y -i raw.mp4 -af loudnorm=I=-14:TP=-1.2:LRA=9 -c:v copy -c:a aac -b:a 192k vox-headphone-supply-chain.mp4 2>&1 | tail -1
ffprobe -v error -show_entries format=duration -of csv=p=0 vox-headphone-supply-chain.mp4
