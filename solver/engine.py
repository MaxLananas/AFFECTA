"""
Core lexicographic assignment engine with chains and cycle detection.
DESIGN_DECISION: multi-pass on free posts; cycles marked UNKNOWN not auto-resolved.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import hashlib

from movement_engine.domain.models import Agent, Assignment, CandidateScore, Post, Wish
from movement_engine.regulatory.registry import RuleRegistry, guadeloupe_registry
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.graph.dependency import (
    build_dependency_graph, tarjan_scc, classify_cycle, DependencyGraph, Cycle,
)


@dataclass
class EngineResult:
    assignments: Dict[str, Assignment]
    cycles: List[Cycle]
    metrics: Dict[str, int]
    elapsed_ms: float
    input_hash: str
    result_hash: str


def _tie_key(agent_id: str, seed: str = "20260810") -> str:
    """DESIGN_DECISION: deterministic tie-break from agent_id + campaign seed."""
    h = hashlib.sha256(f"{seed}:{agent_id}".encode()).hexdigest()
    return h[:16]


def run_engine(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    registry: Optional[RuleRegistry] = None,
    *,
    campaign_seed: str = "20260810",
    max_passes: int = 30,
) -> EngineResult:
    import time
    t0 = time.perf_counter()
    registry = registry or guadeloupe_registry()

    # --- score all eligible pairs ---
    scores: Dict[Tuple[str, str], CandidateScore] = {}
    wishes_flat: Dict[str, List[Tuple[Wish, str, int]]] = defaultdict(list)
    # agent -> list of (wish, post_id, sous_rank)

    for agent_id, wish_list in wishes.items():
        for wish in wish_list:
            for sr, post_id in enumerate(wish.post_ids):
                if post_id not in posts:
                    continue
                post = posts[post_id]
                agent = agents[agent_id]
                s = score_candidate(
                    agent, post, wish, registry,
                    sous_rank=sr if wish.group else None,
                    tie_key=_tie_key(agent_id, campaign_seed),
                )
                if s.eligible:
                    scores[(agent_id, post_id)] = s
                    wishes_flat[agent_id].append((wish, post_id, sr if wish.group else 0))

    # sort each agent's wishes by regulatory key
    for aid in wishes_flat:
        wishes_flat[aid].sort(
            key=lambda x: scores[(aid, x[1])].regulatory_key()
            if (aid, x[1]) in scores else (99, 0, 999, 0, "")
        )

    # free posts = vacant
    free: Set[str] = {pid for pid, p in posts.items() if p.vacant}
    assigned_agent: Dict[str, str] = {}  # agent -> post
    assigned_post: Dict[str, str] = {}   # post -> agent

    # desired first choice for dependency graph
    desired: Dict[str, str] = {}
    for aid, opts in wishes_flat.items():
        if opts:
            desired[aid] = opts[0][1]

    post_holder = {pid: p.holder_id for pid, p in posts.items()}
    graph = build_dependency_graph(desired, post_holder)
    sccs = tarjan_scc(graph.edges)
    cycles = [classify_cycle(c, "REGULATORY_UNKNOWN") for c in sccs]

    # multi-pass assignment: only free (vacant or liberated) posts
    changed = True
    passes = 0
    while changed and passes < max_passes:
        changed = False
        passes += 1
        # process agents in deterministic order by best score
        order = sorted(
            agents.keys(),
            key=lambda aid: (
                scores[aid, wishes_flat[aid][0][1]].regulatory_key()
                if aid in wishes_flat and wishes_flat[aid] and (aid, wishes_flat[aid][0][1]) in scores
                else (99, 0, 999, 0, aid)
            ),
        )
        for aid in order:
            if aid in assigned_agent:
                continue
            for wish, post_id, sr in wishes_flat.get(aid, []):
                if post_id not in free:
                    continue
                if post_id in assigned_post:
                    continue
                # assign
                assigned_agent[aid] = post_id
                assigned_post[post_id] = aid
                free.discard(post_id)
                # liberate previous post if any
                cur = agents[aid].current_post_id
                if cur and cur in posts and posts[cur].holder_id == aid:
                    free.add(cur)
                    # mark liberated
                changed = True
                break

    # build assignments
    result_assign: Dict[str, Assignment] = {}
    for aid, agent in agents.items():
        if aid in assigned_agent:
            pid = assigned_agent[aid]
            sc = scores.get((aid, pid))
            wr = sc.wish_rank if sc else None
            result_assign[aid] = Assignment(
                agent_id=aid, post_id=pid, wish_rank=wr,
                kind="ASSIGNED", score=sc,
            )
        else:
            result_assign[aid] = Assignment(
                agent_id=aid, post_id=agent.current_post_id,
                wish_rank=None, kind="STAY" if agent.current_post_id else "UNASSIGNED",
            )

    # hashes
    canon = "|".join(
        f"{a}:{result_assign[a].post_id}:{result_assign[a].kind}"
        for a in sorted(result_assign)
    )
    result_hash = hashlib.sha256(canon.encode()).hexdigest()[:16]
    input_hash = hashlib.sha256(
        f"{len(agents)}:{len(posts)}:{campaign_seed}".encode()
    ).hexdigest()[:16]

    elapsed = (time.perf_counter() - t0) * 1000
    metrics = {
        "agents": len(agents),
        "posts": len(posts),
        "assigned": sum(1 for a in result_assign.values() if a.kind == "ASSIGNED"),
        "stayed": sum(1 for a in result_assign.values() if a.kind == "STAY"),
        "unassigned": sum(1 for a in result_assign.values() if a.kind == "UNASSIGNED"),
        "cycles_detected": len(cycles),
        "passes": passes,
        "scores_computed": len(scores),
    }
    return EngineResult(
        assignments=result_assign,
        cycles=cycles,
        metrics=metrics,
        elapsed_ms=elapsed,
        input_hash=input_hash,
        result_hash=result_hash,
    )
