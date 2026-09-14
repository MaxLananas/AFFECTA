"""
Exhaustive optimal solver for small instances (N <= 12 agents).
Proves optimality by enumerating all feasible assignments.
"""
from __future__ import annotations

from itertools import permutations, product
from typing import Dict, List, Optional, Tuple

from movement_engine.domain.models import Agent, Assignment, CandidateScore, Post, Wish
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import RuleRegistry, guadeloupe_registry
from movement_engine.optimizer.objective import ObjectivePolicy, DEFAULT_POLICY, quality_report


def _eligible_pairs(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    registry: RuleRegistry,
) -> Dict[str, List[Tuple[str, int, CandidateScore]]]:
    """agent -> [(post_id, wish_rank, score), ...] eligible only."""
    out: Dict[str, List[Tuple[str, int, CandidateScore]]] = {}
    for aid, agent in agents.items():
        opts = []
        for wish in wishes.get(aid, []):
            for pid in wish.post_ids:
                if pid not in posts:
                    continue
                s = score_candidate(agent, posts[pid], wish, registry)
                if s.eligible:
                    opts.append((pid, wish.rank, s))
        out[aid] = opts
    return out


def exhaustive_optimize(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    policy: ObjectivePolicy = DEFAULT_POLICY,
    registry: Optional[RuleRegistry] = None,
) -> dict:
    """
    Enumerate all injective assignments of agents to posts (respecting eligibility).
    Return best under lexicographic policy + proof of optimality.
    """
    registry = registry or guadeloupe_registry()
    assert len(agents) <= 12, "Exhaustive only for N<=12"

    pairs = _eligible_pairs(agents, posts, wishes, registry)
    agent_ids = sorted(agents.keys())
    post_ids = sorted(posts.keys())
    # capacity 1 assumed for exhaustive
    capacities = {pid: posts[pid].capacity for pid in post_ids}

    best_vec = None
    best_assign: Optional[Dict[str, Assignment]] = None
    n_feasible = 0

    # For each agent, choices = list of (post, rank, score) or None (unassigned/stay)
    choice_lists = []
    for aid in agent_ids:
        opts = pairs.get(aid, [])
        # include STAY option
        stay_post = agents[aid].current_post_id
        choices = [(None, None, None)]  # unassigned/stay marker
        for pid, rank, sc in opts:
            choices.append((pid, rank, sc))
        choice_lists.append(choices)

    # cartesian product — may be large; prune by capacity
    for combo in product(*choice_lists):
        used: Dict[str, int] = {}
        conflict = False
        for (pid, rank, sc) in combo:
            if pid is None:
                continue
            used[pid] = used.get(pid, 0) + 1
            if used[pid] > capacities.get(pid, 1):
                conflict = True
                break
        if conflict:
            continue

        assignments: Dict[str, Assignment] = {}
        for aid, (pid, rank, sc) in zip(agent_ids, combo):
            if pid is not None:
                assignments[aid] = Assignment(
                    agent_id=aid, post_id=pid, wish_rank=rank, kind="ASSIGNED", score=sc,
                )
            else:
                cur = agents[aid].current_post_id
                assignments[aid] = Assignment(
                    agent_id=aid, post_id=cur, wish_rank=None,
                    kind="STAY" if cur else "UNASSIGNED",
                )

        # REGULATORY: higher-priority eligible agent must not be left
        # unassigned while a lower-priority agent takes the post.
        regulatory_ok = True
        for aid, a in assignments.items():
            if a.kind != "ASSIGNED" or not a.post_id:
                continue
            holder_score = None
            for (p2, rank, sc) in pairs.get(aid, []):
                if p2 == a.post_id:
                    holder_score = sc
                    break
            if holder_score is None:
                continue
            for other, opts in pairs.items():
                if other == aid:
                    continue
                if assignments[other].kind == "ASSIGNED":
                    continue
                for (p2, rank, sc) in opts:
                    if p2 == a.post_id and sc.eligible:
                        if sc.regulatory_key() < holder_score.regulatory_key():
                            regulatory_ok = False
                            break
                if not regulatory_ok:
                    break
            if not regulatory_ok:
                break
        if not regulatory_ok:
            continue

        n_feasible += 1
        vec = policy.score_vector(assignments, agents)
        if best_vec is None or vec > best_vec:
            best_vec = vec
            best_assign = assignments

    assert best_assign is not None
    report = quality_report(best_assign, agents, policy)
    return {
        "assignments": best_assign,
        "objective_vector": best_vec,
        "quality": report,
        "optimality": {
            "proven": True,
            "method": "EXHAUSTIVE",
            "feasible_solutions_examined": n_feasible,
            "n_agents": len(agents),
        },
        "policy_version": policy.version,
    }
