#!/usr/bin/env bash
# Reconstruit audio/mix.wav (voix narration + nappe musicale) à partir des
# sources versionnées : audio/s1..s8.mp3 (narration) et make_music.py (musique).
# Dépendances : python3 + imageio-ffmpeg (fournit le binaire ffmpeg).
set -euo pipefail
cd "$(dirname "$0")"

FF=$(python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
FPS=30
# Durées de chaque scène (secondes) — doivent correspondre à scenes.DURATIONS
DUR=(10.6 15.9 19.7 13.9 13.4 12.5 13.4 9.2)

mkdir -p audio/seg
: > audio/concat.txt
for i in "${!DUR[@]}"; do
  n=$((i+1)); d=${DUR[$i]}
  # 0.5 s de silence en tête, puis pad/atrim à la durée exacte de la scène
  "$FF" -y -i "audio/s${n}.mp3" \
    -af "adelay=500|500,apad,atrim=0:${d},asetpts=N/SR/TB" \
    -ar 48000 -ac 2 "audio/seg/seg${n}.wav" >/dev/null 2>&1
  echo "file 'seg/seg${n}.wav'" >> audio/concat.txt
done

# Voix concaténée
"$FF" -y -f concat -safe 0 -i audio/concat.txt -c copy audio/voice.wav >/dev/null 2>&1
# Nappe musicale ambiante
python3 make_music.py
# Mixage voix (1.0) + musique (0.14)
"$FF" -y -i audio/voice.wav -i audio/music.wav \
  -filter_complex "[0:a]volume=1.0[v];[1:a]volume=0.14[m];[v][m]amix=inputs=2:duration=first:dropout_transition=0[a]" \
  -map "[a]" -ar 48000 -ac 2 audio/mix.wav >/dev/null 2>&1

echo "audio/mix.wav reconstruit."
