# Vidéo de présentation AFFECTA

Sources de production de `../AFFECTA_presentation.mp4` (1920×1080, 30 fps, ~1 min 48 s,
H.264 High + AAC 192 k).

## Contenu versionné

| Fichier | Rôle |
|---|---|
| `render_lib.py` | Boîte à outils de rendu (palette, polices, easing, panneaux, glow, fond réseau). |
| `scenes.py` | Les 8 scènes (`SCENES`, `DURATIONS`) : intro, DA, garanties, deux-temps, perf, robustesse, outro. |
| `render_par.py` | Rendu parallèle des frames → `frames/fNNNNN.jpg`. |
| `render_all.py` | Rendu série (lent, pour debug). |
| `make_music.py` | Synthèse de la nappe musicale ambiante → `audio/music.wav` (sans dépendance externe). |
| `assemble_audio.sh` | Reconstruit `audio/mix.wav` (voix + musique) à partir de `audio/s1..s8.mp3`. |
| `audio/s1..s8.mp3` | Narration par scène (voix off). |

## Artefacts dérivés (non versionnés, cf. `.gitignore`)

`frames/`, `manifest.txt`, `audio/seg/`, `audio/voice.wav`, `audio/music.wav`, `audio/mix.wav`.

## Reproduire la vidéo

Prérequis : `python3`, `pip install pillow numpy imageio imageio-ffmpeg`.

```bash
cd media/video
python3 render_par.py          # ~2 min : rend toutes les frames dans frames/
./assemble_audio.sh            # reconstruit audio/mix.wav
FF=$(python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
"$FF" -y -framerate 30 -i frames/f%05d.jpg -i audio/mix.wav \
  -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 192k -shortest ../AFFECTA_presentation.mp4
```
