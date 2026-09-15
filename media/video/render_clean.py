"""Rendu parallèle des frames AFFECTA v2 (thème corporate clair)."""
import os
import time
from multiprocessing import Pool

import clean_scenes as S
from clean_lib import FPS

OUT = os.path.join(os.path.dirname(__file__), "frames_v2")
os.makedirs(OUT, exist_ok=True)

PLAN = []
_gi = 0
_MAN = []
for si, (fn, dur) in enumerate(zip(S.SCENES, S.DURATIONS)):
    nfr = int(round(dur * FPS))
    start = _gi
    for f in range(nfr):
        PLAN.append((_gi, si, f / FPS, dur))
        _gi += 1
    _MAN.append((si + 1, start, _gi - 1, dur))
TOTAL = _gi


def render_one(job):
    gi, si, t, dur = job
    path = os.path.join(OUT, f"f{gi:05d}.jpg")
    img = S.SCENES[si](t, dur, si)
    img.convert("RGB").save(path, quality=92)
    return gi


def main():
    for f in os.listdir(OUT):
        if f.endswith(".jpg"):
            os.remove(os.path.join(OUT, f))
    with open(os.path.join(os.path.dirname(__file__), "manifest_v2.txt"), "w") as fh:
        for (s, a, b, d) in _MAN:
            fh.write(f"{s} {a} {b} {d}\n")

    nproc = min(os.cpu_count() or 2, 8)
    t0 = time.time()
    done = 0
    with Pool(nproc) as pool:
        for _ in pool.imap_unordered(render_one, PLAN, chunksize=8):
            done += 1
            if done % 200 == 0:
                el = time.time() - t0
                print(f"{done}/{TOTAL}  {el:.0f}s  ({done/el:.1f} fps)", flush=True)
    print(f"DONE {TOTAL} frames in {time.time()-t0:.0f}s using {nproc} procs")


if __name__ == "__main__":
    main()
