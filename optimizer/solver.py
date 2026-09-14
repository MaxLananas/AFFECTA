"""
Optimizer: greedy baseline + improved multi-pass + exhaustive for small N.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import hashlib

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.solver.engine import run_engine
from movement_engine.optimizer.objective import (
    ObjectivePolicy, DEFAULT_POLICY, quality_report, ObjectiveKind,
)
from movement_engine.optimizer.exhaustive import exhaustive_optimize
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry


def greedy_baseline(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
) -> dict:
    """Sequential greedy = current engine (first-come by regulatory order)."""
    r = run_engine(agents, posts, wishes)
    q = quality_report(r.assignments, agents)
    return {
        "assignments": r.assignments,
        "quality": q,
        "method": "GREEDY_LEXICOGRAPHIC",
        "result_hash": r.result_hash,
        "elapsed_ms": r.elapsed_ms,
        "optimality": {"proven": False, "method": "GREEDY"},
    }


def cardinality_first_optimize(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    policy: ObjectivePolicy = DEFAULT_POLICY,
) -> dict:
    """
    Multi-pass improvement over greedy:
    1. Run greedy
    2. Try reassignments that increase cardinality or improve wish ranks
       without decreasing higher objectives.
    Not proven optimal for large N, but better than pure greedy.
    """
    base = greedy_baseline(agents, posts, wishes)
    best = dict(base["assignments"])
    best_vec = policy.score_vector(best, agents)
    registry = guadeloupe_registry()

    # Build eligible options
    options: Dict[str, List[Tuple[str, int]]] = {}
    for aid, agent in agents.items():
        opts = []
        for wish in wishes.get(aid, []):
            for pid in wish.post_ids:
                if pid not in posts:
                    continue
                s = score_candidate(agent, posts[pid], wish, registry)
                if s.eligible:
                    opts.append((pid, wish.rank))
        options[aid] = opts

    # Free posts
    used = {a.post_id for a in best.values() if a.kind == "ASSIGNED" and a.post_id}
    free = {pid for pid, p in posts.items() if p.vacant or pid not in used}
    # also posts held by agents who could move
    improved = True
    passes = 0
    while improved and passes < 20:
        improved = False
        passes += 1
        for aid in sorted(agents.keys()):
            cur = best[aid]
            for pid, rank in options.get(aid, []):
                if pid in used and (cur.kind != "ASSIGNED" or cur.post_id != pid):
                    # occupied — skip unless we can swap (simplified: only free)
                    if pid not in free:
                        continue
                if cur.kind == "ASSIGNED" and cur.post_id == pid:
                    continue
                # try assign
                trial = dict(best)
                old_post = cur.post_id if cur.kind == "ASSIGNED" else None
                trial[aid] = Assignment(
                    agent_id=aid, post_id=pid, wish_rank=rank, kind="ASSIGNED",
                )
                # update free/used
                trial_used = {a.post_id for a in trial.values() if a.kind == "ASSIGNED" and a.post_id}
                # capacity check
                from collections import Counter
                counts = Counter(a.post_id for a in trial.values() if a.kind == "ASSIGNED" and a.post_id)
                if any(counts[p] > posts[p].capacity for p in counts if p in posts):
                    continue
                vec = policy.score_vector(trial, agents)
                if vec > best_vec:
                    best = trial
                    best_vec = vec
                    used = trial_used
                    free = {pid2 for pid2 in posts if pid2 not in used}
                    improved = True
                    break

    q = quality_report(best, agents, policy)
    canon = "|".join(f"{a}:{best[a].post_id}:{best[a].kind}" for a in sorted(best))
    return {
        "assignments": best,
        "quality": q,
        "method": "CARDINALITY_FIRST_LOCAL",
        "result_hash": hashlib.sha256(canon.encode()).hexdigest()[:16],
        "optimality": {"proven": False, "method": "LOCAL_SEARCH"},
        "objective_vector": best_vec,
        "policy_version": policy.version,
    }


def optimize(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    policy: ObjectivePolicy = DEFAULT_POLICY,
) -> dict:
    """Dispatch: exhaustive if N<=10, else cardinality-first local."""
    if len(agents) <= 10:
        return exhaustive_optimize(agents, posts, wishes, policy)
    return cardinality_first_optimize(agents, posts, wishes, policy)


def compare_greedy_vs_optimized(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    policy: ObjectivePolicy = DEFAULT_POLICY,
) -> dict:
    g = greedy_baseline(agents, posts, wishes)
    o = optimize(agents, posts, wishes, policy)
    gq, oq = g["quality"], o["quality"]
    return {
        "greedy": gq,
        "optimized": oq,
        "gain": {
            "assigned": oq["assigned"] - gq["assigned"],
            "first_wish": oq["first_wish"] - gq["first_wish"],
            "avg_wish_rank": round(oq["avg_wish_rank"] - gq["avg_wish_rank"], 3),
            "unassigned": oq["unassigned"] - gq["unassigned"],
        },
        "optimality": o.get("optimality", {}),
        "method_optimized": o.get("method"),
    }
