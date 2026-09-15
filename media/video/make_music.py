"""Génère une nappe d'ambiance discrète (pad synthétique) pour la vidéo AFFECTA.
Aucune dépendance externe : synthèse additive + enveloppes, écrit un WAV 48kHz stéréo.
"""
import math
import struct
import wave

SR = 48000
DUR = 138.0
N = int(SR * DUR)

# Progression d'accords douce (fréquences en Hz), une par section, ambiance cinématique.
# Dm9 - Bb(add9) - F - C  (transposé grave), notes choisies pour un rendu apaisé/institutionnel.
CHORDS = [
    [146.83, 220.00, 261.63, 329.63],   # D minor 9-ish
    [116.54, 174.61, 233.08, 293.66],   # Bb add9
    [130.81, 196.00, 261.63, 329.63],   # F/C
    [130.81, 164.81, 196.00, 246.94],   # C
]
SECT = DUR / len(CHORDS)


def env_global(t):
    # fade in 3s, fade out 4s
    a = min(1.0, t / 3.0)
    b = min(1.0, (DUR - t) / 4.0)
    return max(0.0, a * b)


def sample(t):
    # crossfade between chords
    pos = t / SECT
    i = int(pos) % len(CHORDS)
    j = (i + 1) % len(CHORDS)
    frac = pos - int(pos)
    xf = 0.5 - 0.5 * math.cos(math.pi * min(1.0, frac / 1.0))  # smooth
    ch_a = CHORDS[i]
    ch_b = CHORDS[j]
    s = 0.0
    for k in range(4):
        fa, fb = ch_a[k], ch_b[k]
        # gentle detune for width
        amp = 0.16 * (1.0 - 0.12 * k)
        va = math.sin(2 * math.pi * fa * t) + 0.3 * math.sin(2 * math.pi * fa * 2 * t)
        vb = math.sin(2 * math.pi * fb * t) + 0.3 * math.sin(2 * math.pi * fb * 2 * t)
        s += amp * ((1 - xf) * va + xf * vb)
    # slow shimmer
    s *= 0.9 + 0.1 * math.sin(2 * math.pi * 0.08 * t)
    return s * 0.5


def main():
    frames = bytearray()
    for n in range(N):
        t = n / SR
        g = env_global(t) * 0.5
        base = sample(t) * g
        # slight stereo: phase offset
        left = base
        right = sample(t + 0.004) * g
        # soft clip
        left = max(-1.0, min(1.0, left))
        right = max(-1.0, min(1.0, right))
        frames += struct.pack("<hh", int(left * 20000), int(right * 20000))
    with wave.open("audio/music.wav", "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(frames))
    print("music.wav written", DUR, "s")


if __name__ == "__main__":
    main()
