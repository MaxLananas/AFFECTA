"""Rend toutes les frames de la vidéo AFFECTA dans frames/."""
import os
import sys
import time

import scenes as S
from render_lib import FPS

OUT = os.path.join(os.path.dirname(__file__), "frames")
os.makedirs(OUT, exist_ok=True)


def main():
    # clean old frames
    for f in os.listdir(OUT):
        if f.endswith(".jpg"):
            os.remove(os.path.join(OUT, f))

    gi = 0
    t0 = time.time()
    manifest = []
    for si, (fn, dur) in enumerate(zip(S.SCENES, S.DURATIONS)):
        nfr = int(round(dur * FPS))
        start = gi
        for f in range(nfr):
            t = f / FPS
            img = fn(t, dur, si)
            img.convert("RGB").save(os.path.join(OUT, f"f{gi:05d}.jpg"), quality=92)
            gi += 1
        manifest.append((si + 1, start, gi - 1, dur))
        print(f"scene {si+1}: {nfr} frames  ({dur}s)   total={gi}  "
              f"[{time.time()-t0:.0f}s]", flush=True)

    with open(os.path.join(os.path.dirname(__file__), "manifest.txt"), "w") as fh:
        for (s, a, b, d) in manifest:
            fh.write(f"{s} {a} {b} {d}\n")
    print(f"DONE {gi} frames in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
