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
from movement_engine.explain.certificate import (
    build_certificate, verify_certificate, tamper_and_check,
)


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
        agents[f"A{i:05d}"] = Agent(
            id=f"A{i:05d}",
            echelon=(i % 11) + 1,
            children=i % 4,
            handicap_500=(i % 200 == 0),
            boe=(i % 150 == 0),
            current_post_id=f"X{i:05d}" if i < n_posts and not posts[f"X{i:05d}"].vacant else None,
            aen_points=30 + (i % 10) * 10,
            medical_grave=(i % 300 == 0),
        )
        n_w = rng.randint(2, 6)
        pids = [f"X{rng.randint(0, n_posts - 1):05d}" for _ in range(n_w)]
        wishes[f"A{i:05d}"] = [
            Wish(rank=r + 1, post_ids=(pid,), precise=True) for r, pid in enumerate(pids)
        ]
    return agents, posts, wishes


def cmd_test(_args):
    import movement_engine.tests.test_scorer as ts
    import movement_engine.tests.test_engine as te

    tests = [
        ts.test_echelon_table, ts.test_medical_bonus_only_wish_one,
        ts.test_medical_bonus_not_on_wish_two, ts.test_children,
        ts.test_unique_parental_authority, ts.test_renewal_is_capped_at_90,
        ts.test_rc_apc_cannot_be_combined, ts.test_rc_does_not_apply_to_group_wish,
        ts.test_priority_beats_huge_bareme, ts.test_deterministic,
        te.test_simple_vacant_assignment, te.test_holder_stays_post_not_taken,
        te.test_holder_stays_blocks, te.test_priority_beats_bareme,
        te.test_cycle_detected_not_auto_resolved, te.test_no_double_assignment,
        te.test_deterministic_hash, te.test_chain_liberation, te.test_rc_group_rejected,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 0 if failed == 0 else 1


def cmd_run(args):
    n = args.agents
    n_posts = int(n * 1.5)
    agents, posts, wishes = make_dataset(n, n_posts, seed=args.seed)
    t0 = time.perf_counter()
    result = run_engine(agents, posts, wishes, campaign_seed=str(args.seed))
    total_ms = (time.perf_counter() - t0) * 1000

    cert = build_certificate(
        result.assignments, agents, posts,
        input_hash=result.input_hash,
        cycles_detected=result.metrics["cycles_detected"],
        run_id=f"run-{n}",
    )
    v = verify_certificate(cert, result.assignments, agents, posts)

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
    print(f"Verification            {v['valid'] and 'PASS' or 'FAIL'}")
    if not v["valid"]:
        for r in v["reasons"]:
            print(f"  ! {r}")
    print()
    return 0 if v["valid"] else 1


def cmd_benchmark(args):
    sizes = [100, 1000, 5000, 10000]
    if args.large:
        sizes += [25000, 50000]
    print(f"{'N':>8} {'Posts':>8} {'Med ms':>10} {'Assigned':>10} {'Hash':>18}")
    print("-" * 60)
    for n in sizes:
        agents, posts, wishes = make_dataset(n, int(n * 1.5))
        times = []
        last = None
        reps = 3 if n >= 10000 else 5
        run_engine(agents, posts, wishes)  # warmup
        for _ in range(reps):
            r = run_engine(agents, posts, wishes)
            times.append(r.elapsed_ms)
            last = r
        times.sort()
        med = times[len(times) // 2]
        print(f"{n:>8} {int(n*1.5):>8} {med:>10.1f} {last.metrics['assigned']:>10} {last.result_hash:>18}")
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

    p_bench = sub.add_parser("benchmark")
    p_bench.add_argument("--large", action="store_true")

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
    elif args.cmd == "verify":
        sys.exit(cmd_verify(args))
    elif args.cmd == "whatif":
        sys.exit(cmd_whatif(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
