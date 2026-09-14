"""
AFFECTA COVERAGE v3 — multi-level severity + net pairwise impact.

PRODUCT_POLICY / DESIGN_DECISION. Not regulatory.
OPTIMALITY = UNKNOWN.

Severity levels (by fill/cap ratio):
  EMPTY      ratio == 0
  CRITICAL   0 < ratio <= 0.50
  STRAINED   0.50 < ratio <= 0.75
  UNDER      0.75 < ratio < 1.0
  FULL       ratio >= 1.0

A swap is evaluated on BOTH bases (leave + take).
Net coverage gain must be strictly positive when sacrificing satisfaction,
and leaving a worse-or-equal base to fill a better-off base is rejected.
"""
from __future__ import annotations

import hashlib
import time
from collections import Counter, defaultdict
from enum import Enum
from typing import Dict, List, Tuple

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


# Higher = worse situation. DESIGN_DECISION.
SEVERITY = {
    "EMPTY": 4,
    "CRITICAL": 3,
    "STRAINED": 2,
    "UNDER": 1,
    "FULL": 0,
}


def _base(pid: str) -> str:
    return pid.split("#")[0]


def level(fill: int, cap: int) -> str:
    if cap <= 0:
        return "FULL"
    if fill <= 0:
        return "EMPTY"
    r = fill / cap
    if r <= 0.50:
        return "CRITICAL"
    if r <= 0.75:
        return "STRAINED"
    if r < 1.0:
        return "UNDER"
    return "FULL"


def level_score(fill: int, cap: int) -> int:
    return SEVERITY[level(fill, cap)]


def stats(fill: Dict[str, int], cap: Dict[str, int]) -> dict:
    empty = critical = strained = under = 0
    total_def = 0
    worst_ratio = 1.0
    worst_bid = None
    worst_def = 0
    for b, c in cap.items():
        if c <= 0:
            continue
        f = fill.get(b, 0)
        d = max(0, c - f)
        total_def += d
        lv = level(f, c)
        if lv == "EMPTY":
            empty += 1
        elif lv == "CRITICAL":
            critical += 1
        elif lv == "STRAINED":
            strained += 1
        elif lv == "UNDER":
            under += 1
        if d > worst_def:
            worst_def = d
            worst_bid = b
        ratio = f / c
        if ratio < worst_ratio:
            worst_ratio = ratio
    return {
        "empty": empty,
        "critical_50": critical,
        "strained_75": strained,
        "under_100": under,
        "total_deficit": total_def,
        "worst_deficit": worst_def,
        "worst_ratio": round(worst_ratio, 3),
        "worst_base": worst_bid,
    }


def pairwise_impact(
    fill: Dict[str, int],
    cap: Dict[str, int],
    leave_pid: str,
    take_pid: str,
) -> dict:
    """
    Impact of moving one unit from leave_pid to take_pid.
    Returns severity scores before/after for both bases and net gain.
    Positive net_severity_reduction = improvement.
    """
    lb, tb = _base(leave_pid), _base(take_pid)
    same = lb == tb
    lf, lc = fill.get(lb, 0), cap.get(lb, 0)
    tf, tc = fill.get(tb, 0), cap.get(tb, 0)

    sev_leave_before = level_score(lf, lc)
    sev_take_before = level_score(tf, tc)

    if same:
        # internal move within same base: no coverage change
        return {
            "net_severity_reduction": 0,
            "leave_before": level(lf, lc),
            "leave_after": level(lf, lc),
            "take_before": level(tf, tc),
            "take_after": level(tf, tc),
            "leave_worsened": False,
            "take_improved": False,
            "forbidden_rob_peter": False,
        }

    lf2, tf2 = lf - 1, tf + 1
    sev_leave_after = level_score(lf2, lc)
    sev_take_after = level_score(tf2, tc)

    # net: reduction in total severity (before - after), positive = better
    net = (sev_leave_before + sev_take_before) - (sev_leave_after + sev_take_after)

    leave_worsened = sev_leave_after > sev_leave_before
    take_improved = sev_take_after < sev_take_before

    # Forbidden: worsen an already bad base (CRITICAL/EMPTY) to improve another
    # when the leave base ends up worse or equal severity than take after
    forbidden = False
    if leave_worsened and sev_leave_before >= SEVERITY["CRITICAL"]:
        # robbing a critical/empty-ish establishment
        if sev_leave_after >= sev_take_after:
            forbidden = True
    if leave_worsened and sev_leave_after >= SEVERITY["CRITICAL"] and not take_improved:
        forbidden = True

    return {
        "net_severity_reduction": net,
        "leave_before": level(lf, lc),
        "leave_after": level(lf2, lc),
        "take_before": level(tf, tc),
        "take_after": level(tf2, tc),
        "leave_worsened": leave_worsened,
        "take_improved": take_improved,
        "forbidden_rob_peter": forbidden,
    }


def policy_accept(
    policy: ProductPolicy,
    net_sev: int,
    forbidden: bool,
    sat_delta: float,
    rank_delta: int,
) -> bool:
    if forbidden:
        return False
    # Non-regression: no coverage gain + sat loss => reject
    if net_sev <= 0 and sat_delta < 0:
        return False

    if policy == ProductPolicy.TEACHER_FIRST:
        # Pure wish improvement: allow even if coverage neutral.
        # Reject only if it significantly worsens coverage (net_sev <= -2).
        return sat_delta > 0 and rank_delta < 0 and net_sev >= -1

    if policy == ProductPolicy.BALANCED:
        if sat_delta > 0 and rank_delta < 0 and net_sev >= 0:
            return True
        # allow mild rank sacrifice only with real net severity improvement
        if net_sev > 0 and rank_delta <= 1 and sat_delta >= -20:
            return True
        if net_sev >= 2 and rank_delta <= 2:
            return True
        return False

    if policy == ProductPolicy.COVERAGE_FIRST:
        if net_sev > 0 and rank_delta <= 3:
            return True
        if sat_delta > 0 and rank_delta < 0 and net_sev >= 0:
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


def coverage_v3(agents, posts, wishes, product_policy=ProductPolicy.TEACHER_FIRST) -> dict:
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

    cap: Dict[str, int] = Counter()
    for pid in posts:
        cap[_base(pid)] += 1
    fill: Dict[str, int] = Counter()
    for a in assignments.values():
        if a.kind in ("ASSIGNED", "STAY") and a.post_id:
            fill[_base(a.post_id)] += 1

    before = stats(fill, cap)
    sat_before = sum(
        wish_satisfaction_points(a.wish_rank)
        for a in assignments.values()
        if a.kind == "ASSIGNED" and a.wish_rank
    )

    swaps_done = 0
    rejected_forbidden = 0
    rejected_no_gain = 0
    total_net_sev = 0
    total_sat_cost = 0.0

    improved = True
    passes = 0
    while improved and passes < 8:
        improved = False
        passes += 1
        candidates = []

        for aid in agents:
            cur = assignments[aid]
            if cur.kind != "ASSIGNED" or not cur.post_id:
                continue
            cur_rank = cur.wish_rank or 99
            cur_pid = cur.post_id

            for pid, rank in options.get(aid, []):
                if pid not in free:
                    continue
                impact = pairwise_impact(fill, cap, cur_pid, pid)
                if impact["forbidden_rob_peter"]:
                    rejected_forbidden += 1
                    continue

                old_sat = wish_satisfaction_points(cur_rank)
                new_sat = wish_satisfaction_points(rank)
                sd = new_sat - old_sat
                rd = rank - cur_rank
                net = impact["net_severity_reduction"]

                if not policy_accept(product_policy, net, False, sd, rd):
                    if net <= 0 and sd < 0:
                        rejected_no_gain += 1
                    continue

                # sort: prefer higher net severity reduction, then better sat
                candidates.append((-net, -sd, rd, aid, pid, rank, net, sd))

        candidates.sort()
        touched_a, touched_p = set(), set()
        for _, _, _, aid, pid, rank, net, sd in candidates:
            if aid in touched_a or pid in touched_p:
                continue
            if pid not in free:
                continue
            cur = assignments[aid]
            if cur.kind != "ASSIGNED":
                continue
            old = cur.post_id
            # re-check impact with current fill (may have changed this pass)
            impact = pairwise_impact(fill, cap, old, pid)
            if impact["forbidden_rob_peter"]:
                continue
            if not policy_accept(product_policy, impact["net_severity_reduction"], False,
                                 wish_satisfaction_points(rank) - wish_satisfaction_points(cur.wish_rank or 99),
                                 rank - (cur.wish_rank or 99)):
                continue

            fill[_base(old)] = fill.get(_base(old), 0) - 1
            fill[_base(pid)] = fill.get(_base(pid), 0) + 1
            assignments[aid] = Assignment(aid, pid, rank, "ASSIGNED")
            free.discard(pid)
            free.add(old)
            touched_a.add(aid)
            touched_p.add(pid)
            touched_p.add(old)
            swaps_done += 1
            total_net_sev += impact["net_severity_reduction"]
            if sd < 0:
                total_sat_cost += -sd
            improved = True

    t_end = time.perf_counter()
    after = stats(fill, cap)
    sat_after = sum(
        wish_satisfaction_points(a.wish_rank)
        for a in assignments.values()
        if a.kind == "ASSIGNED" and a.wish_rank
    )
    sat = satisfaction_report(assignments)
    sat_delta = sat_after - sat_before
    # global severity proxy: weighted count
    def sev_total(s):
        return s["empty"] * 4 + s["critical_50"] * 3 + s["strained_75"] * 2 + s["under_100"] * 1
    sev_gain = sev_total(before) - sev_total(after)
    non_reg = not (sev_gain <= 0 and sat_delta < -0.01)
    cpg = None
    if sev_gain > 0 and total_sat_cost > 0:
        cpg = round(total_sat_cost / sev_gain, 3)
    elif sev_gain > 0:
        cpg = 0.0

    canon = "|".join(
        f"{a}:{assignments[a].post_id}:{assignments[a].kind}"
        for a in sorted(assignments)
    )
    return {
        "assignments": assignments,
        "satisfaction": sat,
        "quality": quality_report(assignments, agents, DEFAULT_POLICY),
        "method": f"COVERAGE_V3_{product_policy.value}",
        "product_policy": product_policy.value,
        "policy_version": "coverage-v3",
        "result_hash": hashlib.sha256(canon.encode()).hexdigest()[:16],
        "elapsed_ms": (t_end - t0) * 1000,
        "timing": {"liberation_ms": (t_lib - t0) * 1000, "policy_ms": (t_end - t_lib) * 1000},
        "optimality": {"proven": False, "status": "UNKNOWN"},
        "coverage": {
            "before_swaps": before,
            "after": after,
            "severity_gain": sev_gain,
        },
        "swaps": {
            "done": swaps_done,
            "rejected_forbidden": rejected_forbidden,
            "rejected_no_gain": rejected_no_gain,
            "total_net_severity": total_net_sev,
            "total_sat_cost": round(total_sat_cost, 2),
            "cost_per_severity_gain": cpg,
            "sat_delta_total": round(sat_delta, 2),
        },
        "non_regression_ok": non_reg,
    }
