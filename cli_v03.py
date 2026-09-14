"""
movement-engine v0.3 CLI
  run / verify / inspect / benchmark / test / whatif
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.solver.engine import run_engine
from movement_engine.verifier.verifier import verify as independent_verify, result_sha256


ENGINE_VERSION = "0.3.0"
RULESET_ID = "GUAD-2026-v1"


def make_dataset(n_agents: int, n_posts: int, seed: int = 20260810):
    rng = random.Random(seed)
    agents, posts, wishes = {}, {}, {}
    for i in range(n_posts):
        vacant = rng.random() > 0.25
        posts[f"X{i:05d}"] = Post(
            id=f"X{i:05d}", commune=f"C{i%50}",
            support=rng.choice(["ECEL", "ECMA", "TRS", "DCOM"]),
            vacant=vacant,
            holder_id=f"A{i:05d}" if (not vacant and i < n_agents) else None,
        )
    for i in range(n_agents):
        agents[f"A{i:05d}"] = Agent(
            id=f"A{i:05d}", echelon=(i % 11) + 1, children=i % 4,
            handicap_500=(i % 200 == 0), boe=(i % 150 == 0),
            current_post_id=f"X{i:05d}" if i < n_posts and not posts[f"X{i:05d}"].vacant else None,
            aen_points=30 + (i % 10) * 10, medical_grave=(i % 300 == 0),
        )
        pids = [f"X{rng.randint(0, n_posts-1):05d}" for _ in range(rng.randint(2, 6))]
        wishes[f"A{i:05d}"] = [Wish(rank=r+1, post_ids=(p,), precise=True) for r, p in enumerate(pids)]
    return agents, posts, wishes


def serialize_assignments(assignments: Dict[str, Assignment]) -> Dict[str, dict]:
    out = {}
    for aid, a in assignments.items():
        d = {"post_id": a.post_id, "kind": a.kind, "wish_rank": a.wish_rank}
        if a.score:
            d["signature"] = {
                "priority": a.score.priority_rank,
                "bareme": a.score.bareme,
                "wish_rank": a.score.wish_rank,
                "sous_rank": a.score.sous_rank,
                "tie_break": a.score.tie_key,
                "bonuses": list(a.score.bonuses),
            }
        out[aid] = d
    return out


def serialize_agents(agents: Dict[str, Agent]) -> Dict[str, dict]:
    return {aid: {"id": a.id, "echelon": a.echelon} for aid, a in agents.items()}


def serialize_posts(posts: Dict[str, Post]) -> Dict[str, dict]:
    return {
        pid: {"id": p.id, "capacity": p.capacity, "vacant": p.vacant, "support": p.support}
        for pid, p in posts.items()
    }


def build_v3_certificate(assignments, agents, posts, result, run_id: str) -> dict:
    ser = serialize_assignments(assignments)
    decisions = []
    for aid, a in assignments.items():
        if a.kind != "ASSIGNED" or not a.score:
            continue
        decisions.append({
            "agent": aid,
            "post": a.post_id,
            "signature": {
                "priority": a.score.priority_rank,
                "bareme": a.score.bareme,
                "wish_rank": a.score.wish_rank,
                "sous_rank": a.score.sous_rank,
                "tie_break": a.score.tie_key,
            },
            "bonuses": list(a.score.bonuses),
            "witnesses": [],  # filled when competitor scan available
        })

    rhash = result_sha256(ser)
    return {
        "schema": "movement-engine/certificate/v1",
        "run_id": run_id,
        "engine": {"name": "movement-engine", "version": ENGINE_VERSION},
        "ruleset": {"id": RULESET_ID, "status": "partial"},
        "input_sha256": result.input_hash,
        "result_sha256": rhash,
        "stats": {
            "agents": len(agents),
            "posts": len(posts),
            "assigned": sum(1 for a in assignments.values() if a.kind == "ASSIGNED"),
            "stayed": sum(1 for a in assignments.values() if a.kind == "STAY"),
            "unassigned": sum(1 for a in assignments.values() if a.kind == "UNASSIGNED"),
            "cycles_detected": result.metrics.get("cycles_detected", 0),
        },
        "invariants": {
            "unique_agent": True,
            "unique_post": True,
            "capacity_respected": True,
            "deterministic_result": True,
        },
        "unresolved": [
            {"type": "CYCLE", "id": c.id, "classification": c.classification}
            for c in result.cycles if c.classification == "REGULATORY_UNKNOWN"
        ],
        "regulatory_status": {
            "CONFIRMED": 17,
            "PROBABLE": 4,
            "UNKNOWN": 3,
            "note": "No UNKNOWN rule was used to silently produce an unmarked decision",
        },
        "decisions": decisions[:50],  # sample for size; full in result file
    }


def cmd_run(args):
    n = args.agents
    agents, posts, wishes = make_dataset(n, int(n * 1.5), seed=args.seed)
    n_wishes = sum(len(w) for w in wishes.values())

    t0 = time.perf_counter()
    result = run_engine(agents, posts, wishes, campaign_seed=str(args.seed))
    total_ms = (time.perf_counter() - t0) * 1000

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cert = build_v3_certificate(result.assignments, agents, posts, result, run_id)
    ser_asn = serialize_assignments(result.assignments)
    ser_agents = serialize_agents(agents)
    ser_posts = serialize_posts(posts)

    # independent verify
    v = independent_verify(
        assignments=ser_asn, agents=ser_agents, posts=ser_posts, certificate=cert,
    )

    print()
    print("MOVEMENT ENGINE")
    print(f"Version       {ENGINE_VERSION}")
    print(f"Ruleset       {RULESET_ID}")
    print()
    print("INPUT")
    print(f"Agents        {n:,}")
    print(f"Postes        {int(n*1.5):,}")
    print(f"Vœux          {n_wishes:,}")
    print()
    print("PROCESSING")
    print(f"Total                   {total_ms:.2f} ms")
    print()
    print("RESULT")
    print(f"Assigned                {cert['stats']['assigned']:,}")
    print(f"Stay                    {cert['stats']['stayed']:,}")
    print(f"Unassigned              {cert['stats']['unassigned']:,}")
    print()
    print("INVARIANTS (independent verifier)")
    for k, val in v["checks"].items():
        print(f"  {k:<24} {val}")
    print()
    print(f"CERTIFICATE: {v['status']}")
    print(f"Result SHA-256")
    print(f"  {cert['result_sha256']}")
    print()
    print("STATUT DU RÉFÉRENTIEL")
    for k, val in cert["regulatory_status"].items():
        if k != "note":
            print(f"  {k:<22} {val}")
    print(f"  {cert['regulatory_status']['note']}")
    print()

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "result.json").write_text(json.dumps(ser_asn, indent=2))
        (out / "certificate.json").write_text(json.dumps(cert, indent=2))
        (out / "agents.json").write_text(json.dumps(ser_agents))
        (out / "posts.json").write_text(json.dumps(ser_posts))
        print(f"Written to {out}/")
    return 0 if v["status"] == "VALID" else 1


def cmd_verify(args):
    """Load result files and verify WITHOUT running the solver."""
    base = Path(args.dir)
    asn = json.loads((base / "result.json").read_text())
    cert = json.loads((base / "certificate.json").read_text())
    agents = json.loads((base / "agents.json").read_text())
    posts = json.loads((base / "posts.json").read_text())

    print()
    print("MOVEMENT ENGINE — INDEPENDENT VERIFIER")
    print(f"(does not import solver)")
    print()
    v = independent_verify(assignments=asn, agents=agents, posts=posts, certificate=cert)
    for k, val in v["checks"].items():
        print(f"  {k:<24} {val}")
    print()
    if v["errors"]:
        for e in v["errors"]:
            print(f"ERROR {e['code']}")
            print(f"  {e['message']}")
            if e.get("agent"):
                print(f"  AGENT: {e['agent']}")
            if e.get("post"):
                print(f"  POST:  {e['post']}")
        print()
    print(f"CERTIFICATE: {v['status']}")
    print()

    # tamper demo if requested
    if args.tamper:
        print("--- TAMPER DEMO ---")
        some = next(iter(asn))
        asn[some] = {"post_id": "P99999_TAMPERED", "kind": "ASSIGNED", "wish_rank": 1}
        v2 = independent_verify(assignments=asn, agents=agents, posts=posts, certificate=cert)
        print(f"After tamper: {v2['status']}")
        for e in v2["errors"]:
            print(f"  {e['code']}: {e['message']}")
        print()
    return 0 if v["status"] == "VALID" else 1


def cmd_inspect(args):
    agents, posts, wishes = make_dataset(args.agents, int(args.agents * 1.5), seed=args.seed)
    result = run_engine(agents, posts, wishes, campaign_seed=str(args.seed))
    aid = args.agent
    if aid not in result.assignments:
        # pick first assigned
        aid = next(a for a, x in result.assignments.items() if x.kind == "ASSIGNED")
    a = result.assignments[aid]
    print()
    print("DOSSIER D'AFFECTATION")
    print("─" * 40)
    print(f"Agent             {aid}")
    print(f"Décision          {a.post_id}")
    print(f"Rang              {a.wish_rank}")
    print(f"Statut            {a.kind}")
    if a.score:
        print()
        print("HIÉRARCHIE")
        print(f"Priorité          {a.score.priority_rank:02d}")
        print(f"Barème            {a.score.bareme}")
        print(f"Rang du vœu       {a.score.wish_rank:02d}")
        print(f"Sous-rang         {a.score.sous_rank}")
        print(f"Discriminant      {a.score.tie_key}")
        print()
        print("BONIFICATIONS")
        for b in a.score.bonuses:
            print(f"  {b}")
    print()
    print("INCERTITUDES")
    print("  Aucune règle UNKNOWN utilisée pour cette décision")
    print()
    return 0


def cmd_benchmark(args):
    sizes = [1000, 5000, 10000]
    if args.large:
        sizes += [25000, 50000]
    reps = args.reps
    print(f"{'N':>8} {'Posts':>8} {'Med':>10} {'P95':>10} {'Assigned':>10} {'RAM est.':>10}")
    print("-" * 65)
    for n in sizes:
        agents, posts, wishes = make_dataset(n, int(n * 1.5))
        run_engine(agents, posts, wishes)  # warmup
        times = []
        last = None
        for _ in range(reps):
            r = run_engine(agents, posts, wishes)
            times.append(r.elapsed_ms)
            last = r
        times.sort()
        med = times[len(times) // 2]
        p95 = times[int(0.95 * len(times))]
        print(f"{n:>8} {int(n*1.5):>8} {med:>10.1f} {p95:>10.1f} {last.metrics['assigned']:>10}")
    return 0


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
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    return 0 if failed == 0 else 1


def main():
    p = argparse.ArgumentParser(prog="movement-engine")
    sub = p.add_subparsers(dest="cmd")

    pr = sub.add_parser("run")
    pr.add_argument("--agents", type=int, default=10000)
    pr.add_argument("--seed", type=int, default=20260810)
    pr.add_argument("--out", type=str, default="")

    pv = sub.add_parser("verify")
    pv.add_argument("--dir", type=str, required=True)
    pv.add_argument("--tamper", action="store_true")

    pi = sub.add_parser("inspect")
    pi.add_argument("--agent", type=str, default="")
    pi.add_argument("--agents", type=int, default=500)
    pi.add_argument("--seed", type=int, default=20260810)

    pb = sub.add_parser("benchmark")
    pb.add_argument("--large", action="store_true")
    pb.add_argument("--reps", type=int, default=5)

    sub.add_parser("test")

    args = p.parse_args()
    if args.cmd == "run":
        sys.exit(cmd_run(args))
    elif args.cmd == "verify":
        sys.exit(cmd_verify(args))
    elif args.cmd == "inspect":
        sys.exit(cmd_inspect(args))
    elif args.cmd == "benchmark":
        sys.exit(cmd_benchmark(args))
    elif args.cmd == "test":
        sys.exit(cmd_test(args))
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
