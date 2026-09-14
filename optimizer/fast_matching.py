"""
AFFECTA_OPT_FAST — matching-based optimizer.

DESIGN_DECISION: heuristic with max-cardinality + min-cost refinement.
OPTIMALITY status remains UNKNOWN unless exhaustive (N small).
No regulatory rule is invented or relaxed.
"""
from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import networkx as nx

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry
from movement_engine.optimizer.objective import DEFAULT_POLICY, quality_report, ObjectivePolicy
from movement_engine.optimizer.satisfaction import satisfaction_report
from movement_engine.solver.engine import run_engine


def _eligible_edges(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
) -> List[Tuple[str, str, int, tuple]]:
    """Return list of (agent_id, post_id, wish_rank, regulatory_key)."""
    reg = guadeloupe_registry()
    edges = []
    for aid, agent in agents.items():
        for wish in wishes.get(aid, []):
            for sr, pid in enumerate(wish.post_ids):
                if pid not in posts:
                    continue
                s = score_candidate(
                    agent, posts[pid], wish, reg,
                    sous_rank=sr if wish.group else None,
                )
                if s.eligible:
                    edges.append((aid, pid, wish.rank, s.regulatory_key()))
    return edges


def _max_cardinality_matching(
    edges: List[Tuple[str, str, int, tuple]],
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
) -> Dict[str, str]:
    """Hopcroft-Karp style max cardinality via networkx."""
    G = nx.Graph()
    left = [f"A:{a}" for a in agents]
    right = [f"P:{p}" for p in posts]
    G.add_nodes_from(left, bipartite=0)
    G.add_nodes_from(right, bipartite=1)
    for aid, pid, rank, _ in edges:
        # capacity: only capacity-1 posts for now (multi-capacity later)
        G.add_edge(f"A:{aid}", f"P:{pid}")
    matching = nx.bipartite.hopcroft_karp_matching(G, top_nodes=left)
    result = {}
    for node, mate in matching.items():
        if node.startswith("A:") and mate.startswith("P:"):
            result[node[2:]] = mate[2:]
    return result


def _min_cost_max_matching(
    edges: List[Tuple[str, str, int, tuple]],
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    target_cardinality: Optional[int] = None,
) -> Dict[str, str]:
    """
    Prefer lower wish ranks among high-cardinality solutions.
    Cost = wish_rank * 1_000_000 + secondary from regulatory key components.
    Uses successive shortest path via networkx min_cost_flow on a flow network.
    """
    # Build directed flow network: source -> agents -> posts -> sink
    G = nx.DiGraph()
    source, sink = "SRC", "SNK"
    agent_ids = list(agents.keys())
    post_ids = list(posts.keys())

    for aid in agent_ids:
        G.add_edge(source, f"A:{aid}", capacity=1, weight=0)
    for pid in post_ids:
        cap = max(1, getattr(posts[pid], "capacity", 1))
        G.add_edge(f"P:{pid}", sink, capacity=cap, weight=0)

    # edge costs: lower wish_rank is better (lower weight)
    for aid, pid, rank, rkey in edges:
        # encode rank + priority components into integer weight
        # rkey = (priority_rank, -bareme, wish_rank, sous_rank, tie)
        pri = rkey[0] if rkey else 99
        bareme_neg = rkey[1] if len(rkey) > 1 else 0
        cost = rank * 1_000_000 + pri * 10_000 + (bareme_neg + 5000)
        G.add_edge(f"A:{aid}", f"P:{pid}", capacity=1, weight=int(cost))

    try:
        flow = nx.min_cost_flow(G)
    except nx.NetworkXUnfeasible:
        return _max_cardinality_matching(edges, agents, posts)

    result = {}
    for aid in agent_ids:
        a_node = f"A:{aid}"
        if a_node not in flow:
            continue
        for p_node, amount in flow[a_node].items():
            if amount > 0 and p_node.startswith("P:"):
                result[aid] = p_node[2:]
                break
    return result


def fast_optimize_v2(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    policy: ObjectivePolicy = DEFAULT_POLICY,
) -> dict:
    """
    Fast optimizer:
    1. Score eligible edges once
    2. Min-cost max-flow preferring low wish ranks
    3. Fill remaining via liberation-style free posts
    4. Report UNKNOWN optimality
    """
    t0 = time.perf_counter()
    edges = _eligible_edges(agents, posts, wishes)
    t_score = time.perf_counter()

    matching = _min_cost_max_matching(edges, agents, posts)
    t_match = time.perf_counter()

    # Build rank lookup
    rank_lookup: Dict[Tuple[str, str], int] = {}
    for aid, pid, rank, _ in edges:
        key = (aid, pid)
        if key not in rank_lookup or rank < rank_lookup[key]:
            rank_lookup[key] = rank

    assignments: Dict[str, Assignment] = {}
    used_posts = set(matching.values())

    for aid in agents:
        if aid in matching:
            pid = matching[aid]
            rank = rank_lookup.get((aid, pid), 99)
            assignments[aid] = Assignment(
                agent_id=aid, post_id=pid, wish_rank=rank, kind="ASSIGNED",
            )
        else:
            agent = agents[aid]
            if agent.current_post_id and agent.current_post_id not in used_posts:
                # stay if current post free
                assignments[aid] = Assignment(
                    agent_id=aid, post_id=agent.current_post_id,
                    wish_rank=None, kind="STAY",
                )
                used_posts.add(agent.current_post_id)
            else:
                assignments[aid] = Assignment(
                    agent_id=aid, post_id=None, wish_rank=None, kind="UNASSIGNED",
                )

    # Liberate chains: if someone stayed on a post that another matched agent needed...
    # Simple second pass: unassigned agents take free vacant posts from their options
    free = {
        pid for pid, p in posts.items()
        if pid not in used_posts and (p.vacant or p.holder_id is None)
    }
    options_by_agent: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for aid, pid, rank, _ in edges:
        options_by_agent[aid].append((pid, rank))
    for aid in options_by_agent:
        options_by_agent[aid].sort(key=lambda x: x[1])

    for aid in sorted(agents.keys()):
        if assignments[aid].kind == "ASSIGNED":
            continue
        for pid, rank in options_by_agent.get(aid, []):
            if pid in free:
                assignments[aid] = Assignment(
                    agent_id=aid, post_id=pid, wish_rank=rank, kind="ASSIGNED",
                )
                free.discard(pid)
                used_posts.add(pid)
                break

    t_end = time.perf_counter()
    q = quality_report(assignments, agents, policy)
    sat = satisfaction_report(assignments)
    canon = "|".join(
        f"{a}:{assignments[a].post_id}:{assignments[a].kind}"
        for a in sorted(assignments)
    )
    return {
        "assignments": assignments,
        "quality": q,
        "satisfaction": sat,
        "method": "FAST_MINCOST_MATCHING",
        "result_hash": hashlib.sha256(canon.encode()).hexdigest()[:16],
        "elapsed_ms": (t_end - t0) * 1000,
        "timing": {
            "score_ms": (t_score - t0) * 1000,
            "match_ms": (t_match - t_score) * 1000,
            "assemble_ms": (t_end - t_match) * 1000,
        },
        "edges": len(edges),
        "optimality": {
            "proven": False,
            "method": "MIN_COST_MAX_FLOW",
            "status": "UNKNOWN",
        },
        "objective_vector": policy.score_vector(assignments, agents),
        "policy_version": policy.version,
    }
