"""
AFFECTA COVERAGE v2 — delta-based coverage tradeoffs (fast incremental).

PRODUCT_POLICY / DESIGN_DECISION. Not regulatory.
OPTIMALITY = UNKNOWN.

Rules:
  1. Never decrease assigned count.
  2. Swap accepted only with real coverage gain or pure satisfaction gain.
  3. Non-regression: coverage_delta==0 → satisfaction_delta >= 0.
"""
from __future__ import annotations

import hashlib
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Set, Tuple

from movement_engine.optimizer import _nxcompat as nx  # pure-Python drop-in (no networkx dependency)

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry
from movement_engine.optimizer.objective import DEFAULT_POLICY, quality_report
from movement_engine.optimizer.satisfaction import satisfaction_report, wish_satisfaction_points
from movement_engine.solver.engine import run_engine


class ProductPolicy(str, Enum):
    TEACHER_FIRST = "TEACHER_FIRST"
    BALANCED = "BALANCED"
    COVERAGE_FIRST = "COVERAGE_FIRST"


def _base(pid: str) -> str:
    return pid.split("#")[0]


def _severity(fill: int, cap: int) -> int:
    """0=full, 1=understaffed, 2=critical, 3=empty. DESIGN_DECISION."""
    if cap <= 0 or fill >= cap:
        return 0
    if fill == 0:
        return 3
    if cap >= 2 and fill / cap <= 0.5:
        return 2
    return 1


def _stats(fill: Dict[str, int], cap: Dict[str, int]) -> dict:
    total_def = empty = critical = under = 0
    worst = 0
    for b, c in cap.items():
        f = fill.get(b, 0)
        d = max(0, c - f)
        total_def += d
        if d > worst:
            worst = d
        if c >= 1 and f == 0:
            empty += 1
        if c >= 2 and f / c <= 0.5:
            critical += 1
        if f < c:
            under += 1
    return {
        "total_deficit": total_def,
        "empty": empty,
        "critical": critical,
        "understaffed": under,
        "worst": worst,
    }


def composite_gain(before: dict, after: dict) -> float:
    return (
        (before["empty"] - after["empty"]) * 10
        + (before["critical"] - after["critical"]) * 5
        + (before["total_deficit"] - after["total_deficit"]) * 2
        + (before["understaffed"] - after["understaffed"]) * 1
        + (before["worst"] - after["worst"]) * 1
    )


def unit_value(fill: Dict[str, int], cap: Dict[str, int], pid: str) -> int:
    bid = _base(pid)
    return _severity(fill.get(bid, 0), cap.get(bid, 0))


def policy_accept(policy: ProductPolicy, cov_gain: float, sat_delta: float, rank_delta: int) -> bool:
    if cov_gain == 0 and sat_delta < 0:
        return False
    if policy == ProductPolicy.TEACHER_FIRST:
        return sat_delta > 0 and rank_delta < 0
    if policy == ProductPolicy.BALANCED:
        if sat_delta > 0 and rank_delta < 0:
            return True
        if cov_gain > 0 and rank_delta <= 1:
            return True
        if cov_gain > 0 and sat_delta >= -15:
            return True
        return False
    if policy == ProductPolicy.COVERAGE_FIRST:
        if cov_gain > 0 and rank_delta <= 3:
            return True
        if sat_delta > 0 and rank_delta < 0 and cov_gain >= 0:
            return True
        return False
    return False


def build_options(agents, posts, wishes):
    reg = guadeloupe_registry()
    options: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for aid, agent in agents.items():
        for wish in wishes.get(aid, []):
            for pid in wish.post_ids:
                if pid not in posts:
                    continue
                s = score_candidate(agent, posts[pid], wish, reg)
                if s.eligible:
                    options[aid].append((pid, wish.rank))
        options[aid].sort(key=lambda x: x[1])
    return options


def coverage_v2(agents, posts, wishes, product_policy=ProductPolicy.TEACHER_FIRST) -> dict:
    t0 = time.perf_counter()
    base = run_engine(agents, posts, wishes)
    t_lib = time.perf_counter()
    assignments = dict(base.assignments)
    options = build_options(agents, posts, wishes)

    used = {a.post_id for a in assignments.values() if a.kind == "ASSIGNED" and a.post_id}
    free = {
        pid for pid in posts
        if pid not in used and (
            posts[pid].vacant
            or posts[pid].holder_id is None
            or posts[pid].holder_id not in agents
        )
    }

    # Residual cardinality
    unassigned = [aid for aid, a in assignments.items() if a.kind != "ASSIGNED"]
    if unassigned and free:
        G = nx.Graph()
        left = [f"A:{a}" for a in unassigned]
        G.add_nodes_from(left, bipartite=0)
        G.add_nodes_from([f"P:{p}" for p in free], bipartite=1)
        edge_rank = {}
        for aid in unassigned:
            for pid, rank in options.get(aid, []):
                if pid in free:
                    G.add_edge(f"A:{aid}", f"P:{pid}")
                    edge_rank[(aid, pid)] = rank
        if G.number_of_edges():
            matching = nx.bipartite.hopcroft_karp_matching(G, top_nodes=left)
            pairs = sorted(
                (edge_rank.get((n[2:], m[2:]), 99), n[2:], m[2:])
                for n, m in matching.items()
                if n.startswith("A:") and m.startswith("P:")
            )
            claimed = set()
            for rank, aid, pid in pairs:
                if pid in claimed or assignments[aid].kind == "ASSIGNED":
                    continue
                assignments[aid] = Assignment(aid, pid, rank, "ASSIGNED")
                claimed.add(pid)
                free.discard(pid)
                used.add(pid)
        for aid in sorted(unassigned):
            if assignments[aid].kind == "ASSIGNED":
                continue
            for pid, rank in options.get(aid, []):
                if pid in free:
                    assignments[aid] = Assignment(aid, pid, rank, "ASSIGNED")
                    free.discard(pid)
                    used.add(pid)
                    break

    # Incremental fill/cap maps
    cap: Dict[str, int] = Counter()
    for pid in posts:
        cap[_base(pid)] += 1
    fill: Dict[str, int] = Counter()
    for a in assignments.values():
        if a.kind in ("ASSIGNED", "STAY") and a.post_id:
            fill[_base(a.post_id)] += 1

    before_stats = _stats(fill, cap)
    sat_before = sum(
        wish_satisfaction_points(a.wish_rank)
        for a in assignments.values()
        if a.kind == "ASSIGNED" and a.wish_rank
    )

    swaps_done = 0
    swaps_rejected = 0
    total_cov_gain = 0.0
    total_sat_cost = 0.0

    improved = True
    passes = 0
    while improved and passes < 8:
        improved = False
        passes += 1
        stats_now = _stats(fill, cap)
        candidates = []

        for aid in agents:
            cur = assignments[aid]
            if cur.kind != "ASSIGNED" or not cur.post_id:
                continue
            cur_rank = cur.wish_rank or 99
            cur_pid = cur.post_id
            old_bid = _base(cur_pid)
            old_sev = _severity(fill.get(old_bid, 0), cap.get(old_bid, 0))

            for pid, rank in options.get(aid, []):
                if pid not in free:
                    continue
                new_bid = _base(pid)
                # incremental: leave old, take new
                fill_old_after = fill.get(old_bid, 0) - 1
                fill_new_after = fill.get(new_bid, 0) + 1
                # local stats delta for the two bases only
                # recompute severity contribution
                def local_contrib(bid, f):
                    c = cap.get(bid, 0)
                    sev = _severity(f, c)
                    d = max(0, c - f)
                    empty = 1 if c >= 1 and f == 0 else 0
                    crit = 1 if c >= 2 and f / c <= 0.5 else 0 if c else 0
                    under = 1 if f < c else 0
                    return sev, d, empty, crit, under

                so, do, eo, co, uo = local_contrib(old_bid, fill.get(old_bid, 0))
                sn, dn, en, cn, un = local_contrib(new_bid, fill.get(new_bid, 0))
                so2, do2, eo2, co2, uo2 = local_contrib(old_bid, fill_old_after)
                sn2, dn2, en2, cn2, un2 = local_contrib(new_bid, fill_new_after)

                # delta = before - after for each metric (positive = improvement)
                d_empty = (eo + en) - (eo2 + en2)
                d_crit = (co + cn) - (co2 + cn2)
                d_def = (do + dn) - (do2 + dn2)
                d_under = (uo + un) - (uo2 + un2)
                # worst is global — approximate: ignore for speed, use 0
                cg = d_empty * 10 + d_crit * 5 + d_def * 2 + d_under * 1

                # also require target unit has positive coverage value if sacrificing rank
                target_val = _severity(fill.get(new_bid, 0), cap.get(new_bid, 0))

                old_sat = wish_satisfaction_points(cur_rank)
                new_sat = wish_satisfaction_points(rank)
                sd = new_sat - old_sat
                rd = rank - cur_rank

                if not policy_accept(product_policy, float(cg), sd, rd):
                    if cg <= 0 and sd < 0:
                        swaps_rejected += 1
                    continue
                # extra guard: if sacrificing rank, target must actually need coverage
                if rd > 0 and target_val == 0:
                    continue

                candidates.append((-cg, -sd, rd, aid, pid, rank, float(cg), sd))

        candidates.sort()
        touched_a, touched_p = set(), set()
        for _, _, _, aid, pid, rank, cg, sd in candidates:
            if aid in touched_a or pid in touched_p:
                continue
            if pid not in free:
                continue
            cur = assignments[aid]
            if cur.kind != "ASSIGNED":
                continue
            old = cur.post_id
            # apply
            fill[_base(old)] = fill.get(_base(old), 0) - 1
            fill[_base(pid)] = fill.get(_base(pid), 0) + 1
            assignments[aid] = Assignment(aid, pid, rank, "ASSIGNED")
            free.discard(pid)
            free.add(old)
            touched_a.add(aid)
            touched_p.add(pid)
            touched_p.add(old)
            swaps_done += 1
            total_cov_gain += cg
            if sd < 0:
                total_sat_cost += -sd
            improved = True

    t_end = time.perf_counter()
    after_stats = _stats(fill, cap)
    sat_after = sum(
        wish_satisfaction_points(a.wish_rank)
        for a in assignments.values()
        if a.kind == "ASSIGNED" and a.wish_rank
    )
    sat = satisfaction_report(assignments)
    d = {k: before_stats[k] - after_stats[k] for k in before_stats}
    cg_total = composite_gain(before_stats, after_stats)
    sat_delta = sat_after - sat_before
    cpg = None
    if total_cov_gain > 0 and total_sat_cost > 0:
        cpg = round(total_sat_cost / total_cov_gain, 3)
    elif total_cov_gain > 0:
        cpg = 0.0
    non_reg = not (cg_total == 0 and sat_delta < -0.01)

    canon = "|".join(
        f"{a}:{assignments[a].post_id}:{assignments[a].kind}"
        for a in sorted(assignments)
    )
    return {
        "assignments": assignments,
        "satisfaction": sat,
        "quality": quality_report(assignments, agents, DEFAULT_POLICY),
        "method": f"COVERAGE_V2_{product_policy.value}",
        "product_policy": product_policy.value,
        "policy_version": "coverage-v2.1",
        "result_hash": hashlib.sha256(canon.encode()).hexdigest()[:16],
        "elapsed_ms": (t_end - t0) * 1000,
        "timing": {"liberation_ms": (t_lib - t0) * 1000, "policy_ms": (t_end - t_lib) * 1000},
        "optimality": {"proven": False, "status": "UNKNOWN"},
        "coverage": {
            "before_swaps": before_stats,
            "after": after_stats,
            "delta": d,
            "composite_gain": cg_total,
        },
        "swaps": {
            "done": swaps_done,
            "rejected_no_gain": swaps_rejected,
            "total_cov_gain": round(total_cov_gain, 2),
            "total_sat_cost": round(total_sat_cost, 2),
            "cost_per_coverage_gain": cpg,
            "sat_delta_total": round(sat_delta, 2),
        },
        "non_regression_ok": non_reg,
    }
