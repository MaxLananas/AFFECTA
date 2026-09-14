from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.optimizer.objective import DEFAULT_POLICY, ObjectivePolicy, quality_report
from movement_engine.optimizer.exhaustive import exhaustive_optimize
from movement_engine.optimizer.solver import greedy_baseline, optimize
from movement_engine.optimizer.counterexample import naive_sequential_no_release
from movement_engine.optimizer.bounds import cardinality_bound, classify_cardinality
from movement_engine.solver.engine import run_engine


@dataclass
class SolverResult:
    name: str
    assigned: int
    first_wish: int
    avg_rank: float
    objective_vector: tuple
    status: str
    method: str


def _from_assignments(name: str, assignments: Dict[str, Assignment], agents: dict, method: str, status: str) -> SolverResult:
    q = quality_report(assignments, agents)
    return SolverResult(
        name=name,
        assigned=q["assigned"],
        first_wish=q["first_wish"],
        avg_rank=q["avg_wish_rank"],
        objective_vector=q["objective_vector"],
        status=status,
        method=method,
    )


def run_naive_greedy(agents, posts, wishes) -> SolverResult:
    asn = naive_sequential_no_release(agents, posts, wishes)
    return _from_assignments("NAIVE_GREEDY", asn, agents, "SEQUENTIAL_NO_RELEASE", "FEASIBLE")


def run_liberation_greedy(agents, posts, wishes) -> SolverResult:
    g = greedy_baseline(agents, posts, wishes)
    return _from_assignments("LIBERATION_GREEDY", g["assignments"], agents, "MULTI_PASS_RELEASE", "FEASIBLE")


def run_affecta(agents, posts, wishes, policy: ObjectivePolicy = DEFAULT_POLICY) -> SolverResult:
    sol = optimize(agents, posts, wishes, policy)
    proven = sol.get("optimality", {}).get("proven", False)
    status = "LEXICOGRAPHIC_OPTIMAL" if proven else "FEASIBLE"
    return _from_assignments("AFFECTA_OPTIMIZER", sol["assignments"], agents, sol.get("method", "OPT"), status)


def run_oracle(agents, posts, wishes, policy: ObjectivePolicy = DEFAULT_POLICY) -> SolverResult:
    sol = exhaustive_optimize(agents, posts, wishes, policy)
    return _from_assignments("EXHAUSTIVE_ORACLE", sol["assignments"], agents, "EXHAUSTIVE", "ORACLE")


def compare_all(agents, posts, wishes, policy: ObjectivePolicy = DEFAULT_POLICY) -> dict:
    results = [
        run_naive_greedy(agents, posts, wishes),
        run_liberation_greedy(agents, posts, wishes),
        run_affecta(agents, posts, wishes, policy),
    ]
    oracle = None
    if len(agents) <= 10:
        oracle = run_oracle(agents, posts, wishes, policy)
        results.append(oracle)

    bound = cardinality_bound(agents, posts, wishes)
    affecta = results[2]
    card_status = classify_cardinality(affecta.assigned, bound["upper_bound"])

    match_oracle = None
    if oracle is not None:
        match_oracle = affecta.objective_vector == oracle.objective_vector

    return {
        "solvers": [
            {
                "name": r.name,
                "assigned": r.assigned,
                "first_wish": r.first_wish,
                "avg_rank": r.avg_rank,
                "objective_vector": list(r.objective_vector),
                "status": r.status,
                "method": r.method,
            }
            for r in results
        ],
        "eligibility_bound": bound["upper_bound"],
        "cardinality_status": card_status,
        "affecta_matches_oracle": match_oracle,
        "policy_version": policy.version,
        "policy_note": "DESIGN_DECISION: cardinality dominates wish satisfaction; not a regulatory mandate",
    }


def random_instance(rng: random.Random, n_min: int = 3, n_max: int = 7) -> Tuple[dict, dict, dict]:
    n = rng.randint(n_min, n_max)
    np_ = rng.randint(max(2, n - 1), n + 3)
    agents = {f"A{i}": Agent(id=f"A{i}", echelon=rng.randint(1, 11)) for i in range(n)}
    posts = {f"X{i}": Post(id=f"X{i}", commune="BT", support="ECEL", vacant=True) for i in range(np_)}
    wishes = {}
    for i in range(n):
        k = rng.randint(1, min(4, np_))
        pids = []
        seen = set()
        for _ in range(k):
            p = f"X{rng.randint(0, np_ - 1)}"
            if p not in seen:
                seen.add(p)
                pids.append(p)
        wishes[f"A{i}"] = [Wish(rank=r + 1, post_ids=(p,)) for r, p in enumerate(pids)]
    return agents, posts, wishes


def oracle_batch(n_instances: int = 1000, seed: int = 20260811) -> dict:
    rng = random.Random(seed)
    matches = 0
    mismatches = []
    for i in range(n_instances):
        agents, posts, wishes = random_instance(rng)
        cmp = compare_all(agents, posts, wishes)
        if cmp["affecta_matches_oracle"] is True:
            matches += 1
        elif cmp["affecta_matches_oracle"] is False:
            mismatches.append({
                "instance": i,
                "seed": seed,
                "solvers": cmp["solvers"],
            })
            if len(mismatches) >= 5:
                break
    return {
        "total": n_instances if not mismatches else (mismatches[-1]["instance"] + 1),
        "matches": matches,
        "mismatches": len(mismatches),
        "first_mismatches": mismatches[:3],
        "pass": len(mismatches) == 0,
    }


def format_comparison(cmp: dict) -> str:
    lines = [
        "AFFECTA — SOLVER COMPARISON",
        f"Policy: {cmp['policy_version']}  ({cmp['policy_note']})",
        "",
        f"{'SOLVER':<22} {'ASSIGNED':>8} {'FIRST':>6} {'AVG':>6}  STATUS",
        "-" * 60,
    ]
    for s in cmp["solvers"]:
        lines.append(
            f"{s['name']:<22} {s['assigned']:>8} {s['first_wish']:>6} {s['avg_rank']:>6.2f}  {s['status']}"
        )
    lines.append("")
    lines.append(f"Eligibility bound     {cmp['eligibility_bound']}")
    lines.append(f"Cardinality status    {cmp['cardinality_status']}")
    if cmp["affecta_matches_oracle"] is not None:
        lines.append(f"AFFECTA == ORACLE     {cmp['affecta_matches_oracle']}")
    return "\n".join(lines)
