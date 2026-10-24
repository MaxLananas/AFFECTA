"""
CLI entry point:
  python -m movement_engine test
  python -m movement_engine benchmark
  python -m movement_engine run --agents 10000
  python -m movement_engine verify
  python -m movement_engine whatif --extra-posts 500
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from typing import Dict, List

from movement_engine.domain.models import Agent, Post, Wish, Assignment
from movement_engine.solver.engine import run_engine
from movement_engine.solver.deferred_acceptance import run_deferred_acceptance
from movement_engine.explain.certificate import (
    build_certificate, verify_certificate, tamper_and_check,
)


def _resolve_engine(name: str):
    """Return the solver callable for a CLI engine name."""
    if name in ("da", "deferred", "deferred_acceptance", "movement", "mvt1d"):
        # Full confirmed MVT1D procedure: deferred acceptance then office-assignment
        # (extension) of obligatory participants. This is the production default.
        from movement_engine.solver.pipeline import run_movement
        return run_movement
    if name in ("da-only", "da-nostep", "phase1"):
        # Phase 1 in isolation (no extension) — useful for comparison/diagnostics.
        return run_deferred_acceptance
    if name in ("native", "da-native", "c"):
        from movement_engine.solver.engine_native import (
            run_deferred_acceptance_native,
            native_available,
        )
        if not native_available():
            raise SystemExit(
                "native core not built; run `make -C native` (falls back to 'da' otherwise)"
            )
        return run_deferred_acceptance_native
    if name in ("legacy", "greedy", "engine"):
        return run_engine
    raise SystemExit(f"unknown engine: {name!r} (use 'da', 'da-only', 'native' or 'legacy')")


def make_dataset(n_agents: int, n_posts: int, seed: int = 20260810):
    rng = random.Random(seed)
    agents: Dict[str, Agent] = {}
    posts: Dict[str, Post] = {}
    wishes: Dict[str, List[Wish]] = {}
    for i in range(n_posts):
        vacant = rng.random() > 0.25
        posts[f"X{i:05d}"] = Post(
            id=f"X{i:05d}",
            commune=f"C{i % 50}",
            support=rng.choice(["ECEL", "ECMA", "TRS", "DCOM"]),
            vacant=vacant,
            holder_id=f"A{i:05d}" if not vacant and i < n_agents else None,
        )
    for i in range(n_agents):
        current = f"X{i:05d}" if i < n_posts and not posts[f"X{i:05d}"].vacant else None
        agents[f"A{i:05d}"] = Agent(
            id=f"A{i:05d}",
            echelon=(i % 11) + 1,
            children=i % 4,
            handicap_500=(i % 200 == 0),
            boe=(i % 150 == 0),
            current_post_id=current,
            aen_points=30 + (i % 10) * 10,
            aen_months=(i % 25) * 12,
            echelon_months=(i % 5) * 12,
            medical_grave=(i % 300 == 0),
            # Un agent sans poste actuel est un entrant -> participant obligatoire
            # (doit recevoir une affectation). Les titulaires sont volontaires.
            participation="obligatoire" if current is None else "volontaire",
        )
        n_w = rng.randint(2, 6)
        pids = [f"X{rng.randint(0, n_posts - 1):05d}" for _ in range(n_w)]
        wishes[f"A{i:05d}"] = [
            Wish(rank=r + 1, post_ids=(pid,), precise=True) for r, pid in enumerate(pids)
        ]
    return agents, posts, wishes


def cmd_test(_args):
    # Delegate to the dependency-free discovery runner (covers all test modules).
    from movement_engine.run_tests import main as run_all
    return run_all()


def cmd_run(args):
    n = args.agents
    n_posts = int(n * 1.5)
    agents, posts, wishes = make_dataset(n, n_posts, seed=args.seed)
    solver = _resolve_engine(getattr(args, "engine", "da"))
    t0 = time.perf_counter()
    result = solver(agents, posts, wishes, campaign_seed=str(args.seed))
    total_ms = (time.perf_counter() - t0) * 1000

    cert = build_certificate(
        result.assignments, agents, posts,
        input_hash=result.input_hash,
        cycles_detected=result.metrics["cycles_detected"],
        run_id=f"run-{n}",
    )
    v = verify_certificate(cert, result.assignments, agents, posts)

    # Independent fairness proof (no justified envy). Only meaningful for stable solvers.
    from movement_engine.explain.stability import check_stability
    stab = check_stability(result.assignments, agents, posts, wishes,
                           campaign_seed=str(args.seed))

    n_wishes = sum(len(w) for w in wishes.values())
    print()
    print("MOUVEMENT ENGINE v0.2")
    print("━" * 50)
    print(f"Dataset                 SYNTH-{n}")
    print(f"Agents                  {n:,}")
    print(f"Postes                  {n_posts:,}")
    print(f"Vœux                    {n_wishes:,}")
    print()
    print("RÉSULTAT")
    print(f"Agents affectés         {cert.assigned:,}")
    print(f"Agents restés           {cert.stayed:,}")
    print(f"Agents non affectés     {cert.unassigned:,}")
    print(f"Double affectation      {cert.double_assignments}")
    print(f"Cycles détectés         {cert.cycles_detected}")
    print()
    print("PERFORMANCE")
    print(f"Total                   {total_ms:.0f} ms")
    print()
    print("CERTIFICATE")
    print(f"Input hash              {cert.input_hash}")
    print(f"Result hash             {cert.result_hash}")
    print(f"Ruleset                 {cert.ruleset}")
    print(f"Engine                  {cert.engine_version}")
    print(f"Solveur                 {result.metrics.get('method', 'LEGACY')}")
    print(f"Verification            {v['valid'] and 'PASS' or 'FAIL'}")
    if not v["valid"]:
        for r in v["reasons"]:
            print(f"  ! {r}")
    print()
    print("ÉQUITÉ (preuve indépendante)")
    print(f"Sans envie justifiée    {'OUI' if stab.stable_modulo_policy else 'NON'}")
    print(f"Paires vérifiées        {stab.n_checked_pairs:,}")
    if stab.witnesses:
        print(f"Violations réelles      {len(stab.witnesses)} (échantillon)")
    if stab.pure_exchange_opportunities:
        print(f"Échanges possibles      {len(stab.pure_exchange_opportunities)} "
              f"(bloqués par la politique anti-permutation)")
    print()
    return 0 if v["valid"] else 1


def cmd_benchmark(args):
    sizes = [100, 1000, 5000, 10000]
    if args.large:
        sizes += [25000, 50000]
    solver = _resolve_engine(getattr(args, "engine", "da"))
    print(f"engine = {getattr(args, 'engine', 'da')}")
    print(f"{'N':>8} {'Posts':>8} {'Med ms':>10} {'Assigned':>10} {'Hash':>18}")
    print("-" * 60)
    for n in sizes:
        agents, posts, wishes = make_dataset(n, int(n * 1.5))
        times = []
        last = None
        reps = 3 if n >= 10000 else 5
        solver(agents, posts, wishes)  # warmup
        for _ in range(reps):
            r = solver(agents, posts, wishes)
            times.append(r.elapsed_ms)
            last = r
        times.sort()
        med = times[len(times) // 2]
        print(f"{n:>8} {int(n*1.5):>8} {med:>10.1f} {last.metrics['assigned']:>10} {last.result_hash:>18}")
    return 0


def cmd_compare(args):
    """Compare the legacy greedy engine and the deferred-acceptance solver."""
    from movement_engine.optimizer.objective import quality_report
    sizes = [1000, 5000, 10000]
    if args.large:
        sizes += [25000, 50000]
    print("LEGACY (greedy serial dictatorship)  vs  DA (deferred acceptance, stable)")
    hdr = (f"{'N':>7} | {'legacy ms':>9} {'asg':>6} {'vœu1':>6} {'avg':>6}"
           f" | {'DA ms':>7} {'asg':>6} {'vœu1':>6} {'avg':>6}"
           f" | {'+asg':>5} {'+vœu1':>6}")
    print(hdr)
    print("-" * len(hdr))
    for n in sizes:
        agents, posts, wishes = make_dataset(n, int(n * 1.5), seed=args.seed)
        run_engine(agents, posts, wishes); run_deferred_acceptance(agents, posts, wishes)
        t = time.perf_counter(); r0 = run_engine(agents, posts, wishes); e0 = (time.perf_counter() - t) * 1000
        t = time.perf_counter(); r1 = run_deferred_acceptance(agents, posts, wishes); e1 = (time.perf_counter() - t) * 1000
        q0 = quality_report(r0.assignments, agents); q1 = quality_report(r1.assignments, agents)
        print(f"{n:>7} | {e0:>9.1f} {q0['assigned']:>6} {q0['first_wish']:>6} {q0['avg_wish_rank']:>6}"
              f" | {e1:>7.1f} {q1['assigned']:>6} {q1['first_wish']:>6} {q1['avg_wish_rank']:>6}"
              f" | {q1['assigned']-q0['assigned']:>+5} {q1['first_wish']-q0['first_wish']:>+6}")
    print("\nDA is a stable matching (no justified envy) and teacher-optimal.")
    return 0


def cmd_verify(args):
    agents, posts, wishes = make_dataset(500, 750)
    result = run_engine(agents, posts, wishes)
    cert = build_certificate(
        result.assignments, agents, posts,
        input_hash=result.input_hash,
        cycles_detected=result.metrics["cycles_detected"],
    )
    v = verify_certificate(cert, result.assignments, agents, posts)
    print("Original verification:", "PASS" if v["valid"] else "FAIL")

    tamper = tamper_and_check(result.assignments, agents, posts, result.input_hash)
    print("After tamper:")
    print(f"  original_valid = {tamper['original_valid']}")
    print(f"  tampered_valid = {tamper['tampered_valid']}")
    for r in tamper["tampered_reasons"]:
        print(f"  ! {r}")
    assert tamper["original_valid"] and not tamper["tampered_valid"]
    print("\nCERTIFICATE TAMPER DETECTION: OK")
    return 0


def cmd_whatif(args):
    n = args.agents
    base_posts = int(n * 1.5)
    agents, posts, wishes = make_dataset(n, base_posts, seed=args.seed)

    print(f"BASELINE  agents={n}  posts={base_posts}")
    r0 = run_engine(agents, posts, wishes, campaign_seed=str(args.seed))
    c0 = build_certificate(r0.assignments, agents, posts, input_hash=r0.input_hash)
    print(f"  affectés={c0.assigned}  restés={c0.stayed}  non-aff={c0.unassigned}")

    extra = args.extra_posts
    # add extra vacant posts
    new_posts = dict(posts)
    for i in range(extra):
        pid = f"Y{i:05d}"
        new_posts[pid] = Post(id=pid, commune="NEW", support="ECEL", vacant=True)
        # give some agents a wish toward new posts
        aid = f"A{(i % n):05d}"
        if aid in wishes:
            wishes[aid] = list(wishes[aid]) + [Wish(rank=1, post_ids=(pid,), precise=True)]

    print(f"\nSIMULATION  +{extra} postes")
    r1 = run_engine(agents, new_posts, wishes, campaign_seed=str(args.seed))
    c1 = build_certificate(r1.assignments, agents, new_posts, input_hash=r1.input_hash)
    print(f"  affectés={c1.assigned}  restés={c1.stayed}  non-aff={c1.unassigned}")

    changed = 0
    for aid in agents:
        a0 = r0.assignments[aid].post_id
        a1 = r1.assignments[aid].post_id
        if a0 != a1:
            changed += 1

    print("\nDIFF")
    print(f"  +{c1.assigned - c0.assigned} agents affectés")
    print(f"  {changed} agents changent de poste")
    print(f"  double affectation: {c1.double_assignments}")
    print(f"  verification: {c1.verification}")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="movement_engine", description="Moteur mouvement 1D v0.2")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("test")
    p_run = sub.add_parser("run")
    p_run.add_argument("--agents", type=int, default=10000)
    p_run.add_argument("--seed", type=int, default=20260810)
    p_run.add_argument("--engine", type=str, default="da", help="da (default, full MVT1D two-step) | da-only | native | legacy")

    p_bench = sub.add_parser("benchmark")
    p_bench.add_argument("--large", action="store_true")
    p_bench.add_argument("--engine", type=str, default="da", help="da (default, full MVT1D two-step) | da-only | native | legacy")

    p_cmp = sub.add_parser("compare")
    p_cmp.add_argument("--large", action="store_true")
    p_cmp.add_argument("--seed", type=int, default=20260810)

    sub.add_parser("verify")

    p_what = sub.add_parser("whatif")
    p_what.add_argument("--agents", type=int, default=2000)
    p_what.add_argument("--extra-posts", type=int, default=500)
    p_what.add_argument("--seed", type=int, default=20260810)

    args = parser.parse_args()
    if args.cmd == "test":
        sys.exit(cmd_test(args))
    elif args.cmd == "run":
        sys.exit(cmd_run(args))
    elif args.cmd == "benchmark":
        sys.exit(cmd_benchmark(args))
    elif args.cmd == "compare":
        sys.exit(cmd_compare(args))
    elif args.cmd == "verify":
        sys.exit(cmd_verify(args))
    elif args.cmd == "whatif":
        sys.exit(cmd_whatif(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
