"""
AFFECTA fast optimizer: warm-start from liberation multi-pass,
then limited improving swaps only where gain is possible.
DESIGN_DECISION: not proven optimal; status remains FEASIBLE/UNKNOWN.
"""
from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.solver.engine import run_engine
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry
from movement_engine.optimizer.objective import DEFAULT_POLICY, quality_report, ObjectivePolicy
from movement_engine.optimizer.satisfaction import satisfaction_report


def _build_options(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
) -> Dict[str, List[Tuple[str, int]]]:
    reg = guadeloupe_registry()
    options: Dict[str, List[Tuple[str, int]]] = {}
    for aid, agent in agents.items():
        opts = []
        for wish in wishes.get(aid, []):
            for pid in wish.post_ids:
                if pid not in posts:
                    continue
                s = score_candidate(agent, posts[pid], wish, reg)
                if s.eligible:
                    opts.append((pid, wish.rank))
        options[aid] = opts
    return options


def fast_optimize(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    policy: ObjectivePolicy = DEFAULT_POLICY,
    max_improve_passes: int = 3,
) -> dict:
    t0 = time.perf_counter()
    # Warm start = liberation greedy (already good + fast)
    base = run_engine(agents, posts, wishes)
    assignments = dict(base.assignments)
    best_vec = policy.score_vector(assignments, agents)
    options = _build_options(agents, posts, wishes)

    used = {a.post_id for a in assignments.values() if a.kind == "ASSIGNED" and a.post_id}
    free = {pid for pid, p in posts.items() if (p.vacant or pid not in used) and pid not in used}

    # Limited improvement: only unassigned/stay agents grabbing free posts
    # then 2-opt between agents if objective improves
    for _ in range(max_improve_passes):
        improved = False
        # Phase 1: place unassigned onto free posts (best rank)
        for aid in sorted(agents.keys()):
            cur = assignments[aid]
            if cur.kind == "ASSIGNED":
                continue
            best_choice = None
            for pid, rank in options.get(aid, []):
                if pid not in free:
                    continue
                if best_choice is None or rank < best_choice[1]:
                    best_choice = (pid, rank)
            if best_choice:
                pid, rank = best_choice
                trial = dict(assignments)
                trial[aid] = Assignment(agent_id=aid, post_id=pid, wish_rank=rank, kind="ASSIGNED")
                vec = policy.score_vector(trial, agents)
                if vec > best_vec:
                    assignments = trial
                    best_vec = vec
                    used.add(pid)
                    free.discard(pid)
                    improved = True

        # Phase 2: rank-improving reassignment to free posts for already assigned
        for aid in sorted(agents.keys()):
            cur = assignments[aid]
            if cur.kind != "ASSIGNED":
                continue
            cur_rank = cur.wish_rank or 99
            for pid, rank in options.get(aid, []):
                if pid not in free or rank >= cur_rank:
                    continue
                trial = dict(assignments)
                old = cur.post_id
                trial[aid] = Assignment(agent_id=aid, post_id=pid, wish_rank=rank, kind="ASSIGNED")
                vec = policy.score_vector(trial, agents)
                if vec > best_vec:
                    assignments = trial
                    best_vec = vec
                    free.discard(pid)
                    if old:
                        free.add(old)
                    improved = True
                    break
        if not improved:
            break

    elapsed = (time.perf_counter() - t0) * 1000
    q = quality_report(assignments, agents, policy)
    sat = satisfaction_report(assignments)
    canon = "|".join(f"{a}:{assignments[a].post_id}:{assignments[a].kind}" for a in sorted(assignments))
    return {
        "assignments": assignments,
        "quality": q,
        "satisfaction": sat,
        "method": "FAST_WARMSTART_LOCAL",
        "result_hash": hashlib.sha256(canon.encode()).hexdigest()[:16],
        "elapsed_ms": elapsed,
        "optimality": {"proven": False, "method": "HEURISTIC", "status": "UNKNOWN"},
        "objective_vector": best_vec,
        "policy_version": policy.version,
    }
