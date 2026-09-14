"""
AFFECTA policy-aware hybrid solver.

PRODUCT_POLICY / DESIGN_DECISION — not regulatory rules.

Hierarchy (hard order):
  0. Regulatory eligibility (never violated)
  1. Maximize number of assigned professors
  2. Policy-specific tradeoff: wish satisfaction vs establishment coverage
  3. Stability

OPTIMALITY = UNKNOWN
"""
from __future__ import annotations

import hashlib
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry
from movement_engine.optimizer.objective import ObjectivePolicy, DEFAULT_POLICY, quality_report
from movement_engine.optimizer.satisfaction import satisfaction_report
from movement_engine.solver.engine import run_engine


class ProductPolicy(str, Enum):
    TEACHER_FIRST = "TEACHER_FIRST"
    BALANCED = "BALANCED"
    COVERAGE_FIRST = "COVERAGE_FIRST"


@dataclass(frozen=True)
class PolicyConfig:
    """PRODUCT_POLICY parameters — explicit, versioned, not regulatory."""
    name: ProductPolicy
    version: str
    # how much rank worsening we accept to fill a critical post
    # TEACHER: 0 (never worsen rank for coverage)
    # BALANCED: allow +1 rank step to fill critical
    # COVERAGE: allow +3 rank steps to fill critical
    max_rank_sacrifice_for_critical: int
    # weight when sorting free posts for residual fill
    coverage_weight: float
    # prefer filling completely empty establishments
    prefer_empty_etab: bool


POLICIES = {
    ProductPolicy.TEACHER_FIRST: PolicyConfig(
        name=ProductPolicy.TEACHER_FIRST,
        version="product-teacher-v2",
        max_rank_sacrifice_for_critical=0,
        coverage_weight=0.0,
        prefer_empty_etab=False,
    ),
    ProductPolicy.BALANCED: PolicyConfig(
        name=ProductPolicy.BALANCED,
        version="product-balanced-v2",
        max_rank_sacrifice_for_critical=1,
        coverage_weight=1.0,
        prefer_empty_etab=True,
    ),
    ProductPolicy.COVERAGE_FIRST: PolicyConfig(
        name=ProductPolicy.COVERAGE_FIRST,
        version="product-coverage-v2",
        max_rank_sacrifice_for_critical=3,
        coverage_weight=5.0,
        prefer_empty_etab=True,
    ),
}


def _base_id(pid: str) -> str:
    return pid.split("#")[0]


def _etab_key(posts: Dict[str, Post], pid: str) -> str:
    p = posts[pid]
    return f"{p.commune}|{p.support}|{_base_id(pid)}"


def _coverage_state(
    assignments: Dict[str, Assignment],
    posts: Dict[str, Post],
) -> Tuple[Dict[str, int], Dict[str, int], Set[str]]:
    """Return fill count per base post, capacity per base, set of critical unit posts."""
    fill: Counter = Counter()
    cap: Counter = Counter()
    for pid, p in posts.items():
        bid = _base_id(pid)
        cap[bid] += 1
    for a in assignments.values():
        if a.kind in ("ASSIGNED", "STAY") and a.post_id:
            fill[_base_id(a.post_id)] += 1
    # PRODUCT_POLICY thresholds (DESIGN_DECISION):
    # - any remaining unit on a base with fill/cap <= 0.5 (cap>=2) is critical
    # - any unit on a completely empty base is critical
    critical_units: Set[str] = set()
    for pid in posts:
        bid = _base_id(pid)
        c, f = cap[bid], fill[bid]
        if c >= 2 and f / c <= 0.5:
            critical_units.add(pid)
        if f == 0:
            critical_units.add(pid)
    return dict(fill), dict(cap), critical_units


def policy_hybrid(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    product_policy: ProductPolicy = ProductPolicy.TEACHER_FIRST,
) -> dict:
    cfg = POLICIES[product_policy]
    t0 = time.perf_counter()

    # 1. Liberation warm-start — maximizes assigned via chains
    base = run_engine(agents, posts, wishes)
    t_lib = time.perf_counter()
    assignments = dict(base.assignments)

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

    used = {a.post_id for a in assignments.values() if a.kind == "ASSIGNED" and a.post_id}
    free = {
        pid for pid in posts
        if pid not in used and (posts[pid].vacant or posts[pid].holder_id is None
                                 or posts[pid].holder_id not in agents)
    }

    # 2. Residual fill for unassigned — always maximize cardinality first
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
        if G.number_of_edges() > 0:
            matching = nx.bipartite.hopcroft_karp_matching(G, top_nodes=left)
            pairs = []
            fill, cap, critical = _coverage_state(assignments, posts)
            for node, mate in matching.items():
                if node.startswith("A:") and mate.startswith("P:"):
                    aid, pid = node[2:], mate[2:]
                    rank = edge_rank.get((aid, pid), 99)
                    # lower sort key = preferred
                    # TEACHER: rank only; COVERAGE: critical first then rank
                    crit_pen = 0 if pid in critical else 1
                    score = (
                        crit_pen * cfg.coverage_weight * 1000 + rank
                        if cfg.coverage_weight > 0
                        else rank
                    )
                    pairs.append((score, rank, aid, pid))
            pairs.sort()
            claimed = set()
            for _, rank, aid, pid in pairs:
                if pid in claimed or assignments[aid].kind == "ASSIGNED":
                    continue
                assignments[aid] = Assignment(
                    agent_id=aid, post_id=pid, wish_rank=rank, kind="ASSIGNED",
                )
                claimed.add(pid)
                free.discard(pid)
                used.add(pid)
        for aid in sorted(unassigned):
            if assignments[aid].kind == "ASSIGNED":
                continue
            fill, cap, critical = _coverage_state(assignments, posts)
            candidates = []
            for pid, rank in options.get(aid, []):
                if pid not in free:
                    continue
                crit = 1 if pid in critical else 0
                # prefer critical when coverage_weight > 0
                key = (-crit * cfg.coverage_weight, rank)
                candidates.append((key, pid, rank))
            candidates.sort()
            if candidates:
                _, pid, rank = candidates[0]
                assignments[aid] = Assignment(
                    agent_id=aid, post_id=pid, wish_rank=rank, kind="ASSIGNED",
                )
                free.discard(pid)
                used.add(pid)

    # 3. Rank improvement + coverage-aware swaps
    #    Never decrease assigned count.
    improved = True
    passes = 0
    while improved and passes < 8:
        improved = False
        passes += 1
        fill, cap, critical = _coverage_state(assignments, posts)

        for aid in sorted(agents.keys()):
            cur = assignments[aid]
            if cur.kind != "ASSIGNED":
                continue
            cur_rank = cur.wish_rank or 99
            cur_pid = cur.post_id
            cur_critical = cur_pid in critical if cur_pid else False

            best = None  # (sort_key, new_pid, new_rank)
            for pid, rank in options.get(aid, []):
                if pid not in free:
                    continue
                # TEACHER: only improve rank
                if cfg.max_rank_sacrifice_for_critical == 0:
                    if rank >= cur_rank:
                        continue
                    key = (rank,)
                    if best is None or key < best[0]:
                        best = (key, pid, rank)
                    continue

                # BALANCED / COVERAGE: may accept worse rank to leave a non-critical
                # post and take a critical free post
                pid_critical = pid in critical
                rank_delta = rank - cur_rank
                if rank_delta < 0:
                    # pure improvement — always good
                    # prefer critical target if equal rank improvement
                    key = (0, -int(pid_critical), rank)
                    if best is None or key < best[0]:
                        best = (key, pid, rank)
                elif rank_delta <= cfg.max_rank_sacrifice_for_critical and pid_critical and not cur_critical:
                    # sacrifice rank to cover critical post
                    key = (1, rank_delta, rank)
                    if best is None or key < best[0]:
                        best = (key, pid, rank)

            if best is not None:
                _, pid, rank = best
                old = cur_pid
                assignments[aid] = Assignment(
                    agent_id=aid, post_id=pid, wish_rank=rank, kind="ASSIGNED",
                )
                free.discard(pid)
                if old:
                    free.add(old)
                improved = True

    t_end = time.perf_counter()
    q = quality_report(assignments, agents, DEFAULT_POLICY)
    sat = satisfaction_report(assignments)
    fill, cap, critical = _coverage_state(assignments, posts)
    canon = "|".join(
        f"{a}:{assignments[a].post_id}:{assignments[a].kind}"
        for a in sorted(assignments)
    )
    return {
        "assignments": assignments,
        "quality": q,
        "satisfaction": sat,
        "method": f"POLICY_HYBRID_{cfg.name.value}",
        "product_policy": cfg.name.value,
        "policy_version": cfg.version,
        "result_hash": hashlib.sha256(canon.encode()).hexdigest()[:16],
        "elapsed_ms": (t_end - t0) * 1000,
        "timing": {
            "liberation_ms": (t_lib - t0) * 1000,
            "policy_ms": (t_end - t_lib) * 1000,
        },
        "optimality": {
            "proven": False,
            "method": "POLICY_HEURISTIC",
            "status": "UNKNOWN",
        },
        "coverage_snapshot": {
            "critical_units_remaining": len([p for p in free if p in critical]),
            "policy": cfg.name.value,
            "max_rank_sacrifice": cfg.max_rank_sacrifice_for_critical,
        },
    }
