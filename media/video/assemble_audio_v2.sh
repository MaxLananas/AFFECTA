#!/usr/bin/env bash
# Assemble la piste audio de la vidéo v2 : narration voix off (seg/s1..s11) posée au
# début de chaque scène + nappe musicale discrète en fond. Sortie : audio/mix.wav.
set -euo pipefail
cd "$(dirname "$0")"

FF="$(python3 -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')"

# Décalage (s) du début de chaque scène = somme cumulée des durées.
DUR=(9.5 11.0 12.0 12.5 17.5 13.0 13.5 13.0 12.5 13.5 10.0)
TOTAL=138.0

# Retards de chaque scène.
OFFS=(); acc=0
for d in "${DUR[@]}"; do
  OFFS+=("$acc")
  acc=$(python3 -c "print($acc + $d)")
done

# 1) nappe musicale (régénérée à 138 s)
python3 make_music.py

# 2) chaque voix : delay au début de scène + petit padding, normalisée douce
inputs=(-i audio/music.wav)
filters=""
idx=1
n_voice=0
for i in "${!DUR[@]}"; do
  seg="audio/seg/s$((i+1)).mp3"
  [ -f "$seg" ] || { echo "manque $seg — narration incomplète"; continue; }
  inputs+=(-i "$seg")
  ms=$(python3 -c "print(int(${OFFS[$i]}*1000)+250)")
  filters+="[$idx:a]adelay=${ms}|${ms},volume=1.35[v$idx];"
  idx=$((idx+1)); n_voice=$((n_voice+1))
done

# musique atténuée pendant la voix (ducking simple par baisse globale)
filters+="[0:a]volume=0.16[m];"
mixins="[m]"
for k in $(seq 1 $n_voice); do mixins+="[v$k]"; done
filters+="${mixins}amix=inputs=$((n_voice+1)):duration=longest:normalize=0[mixraw];"
filters+="[mixraw]alimiter=limit=0.95,aresample=48000[out]"

"$FF" -y "${inputs[@]}" \
  -filter_complex "$filters" -map "[out]" -t "$TOTAL" \
  -c:a pcm_s16le audio/mix.wav

echo "audio/mix.wav écrit ($n_voice segments de voix, $TOTAL s)"
