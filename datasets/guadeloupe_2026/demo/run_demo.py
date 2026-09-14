"""Re-run frozen AFFECTA demo (seed=20260811). No algorithm changes."""
from __future__ import annotations

import json
import time
from pathlib import Path

from movement_engine.datasets.guadeloupe_2026 import policy_comparison as pc
from movement_engine.optimizer.coverage_v3 import ProductPolicy, coverage_v3
from movement_engine.optimizer.counterexample import naive_sequential_no_release
from movement_engine.solver.engine import run_engine
from movement_engine.optimizer.satisfaction import satisfaction_report

SEED = 20260811
N = 1200
MAX_W = 20
OUT = Path(__file__).parent


def main():
    manifest = json.loads((OUT.parent / "manifest.json").read_text(encoding="utf-8"))
    base_posts, meta = pc.load_unit_posts()
    agents, wishes, posts = pc.attach_agents_as_holders(base_posts, N, MAX_W, SEED)

    print("=" * 64)
    print("AFFECTA DEMO — Guadeloupe 2026")
    print(f"dataset={manifest['dataset_id']}  seed={SEED}  n={N}")
    print("Wishes: SYNTHETIC | Optimality: UNKNOWN | Policies: PRODUCT_POLICY")
    print("=" * 64)
    print(f"{'METHOD':<22} {'ASS':>5} {'V1':>5} {'TOP3':>5} {'AVG':>6} {'ms':>7}")

    rows = {}
    t0 = time.perf_counter()
    asn = naive_sequential_no_release(agents, posts, wishes)
    sat = satisfaction_report(asn)
    b = sat["buckets"]
    rows["NAIVE"] = sat
    print(f"{'NAIVE':<22} {sat['assigned']:>5} {b['voeu_1']:>5} "
          f"{b['voeu_1']+b['voeu_2']+b['voeu_3']:>5} {sat['avg_rank']:>6.2f} "
          f"{(time.perf_counter()-t0)*1000:>7.0f}")

    t0 = time.perf_counter()
    lib = run_engine(agents, posts, wishes)
    sat = satisfaction_report(lib.assignments)
    b = sat["buckets"]
    print(f"{'LIBERATION':<22} {sat['assigned']:>5} {b['voeu_1']:>5} "
          f"{b['voeu_1']+b['voeu_2']+b['voeu_3']:>5} {sat['avg_rank']:>6.2f} "
          f"{(time.perf_counter()-t0)*1000:>7.0f}")

    print("-" * 64)
    for pol in ProductPolicy:
        t0 = time.perf_counter()
        r = coverage_v3(agents, posts, wishes, pol)
        sat = r["satisfaction"]
        b = sat["buckets"]
        cov = r["coverage"]["after"]
        print(f"{'AFFECTA_'+pol.value:<22} {sat['assigned']:>5} {b['voeu_1']:>5} "
              f"{b['voeu_1']+b['voeu_2']+b['voeu_3']:>5} {sat['avg_rank']:>6.2f} "
              f"{(time.perf_counter()-t0)*1000:>7.0f}")
        print(f"  empty={cov['empty']}  <50%={cov['critical_50']}  "
              f"cost/gain={r['swaps']['cost_per_severity_gain']}  "
              f"hash={r['result_hash']}  OPT={r['optimality']['status']}")

    print("-" * 64)
    print("DISCLAIMER: not MVT1D · synthetic wishes · UNKNOWN rules · PRODUCT_POLICY")
    print(f"See {OUT / 'DEMO.md'}")


if __name__ == "__main__":
    main()
