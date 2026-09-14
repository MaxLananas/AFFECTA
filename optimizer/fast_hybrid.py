"""
AFFECTA_OPT hybrid: LIBERATION warm-start + residual matching improvement.
DESIGN_DECISION: heuristic. OPTIMALITY = UNKNOWN.
Preserves regulatory eligibility; does not invent rules.
"""
from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from typing import Dict, List, Tuple

from movement_engine.optimizer import _nxcompat as nx  # pure-Python drop-in (no networkx dependency)

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry
from movement_engine.optimizer.objective import DEFAULT_POLICY, quality_report, ObjectivePolicy
from movement_engine.optimizer.satisfaction import satisfaction_report
from movement_engine.solver.engine import run_engine


def fast_hybrid(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    policy: ObjectivePolicy = DEFAULT_POLICY,
) -> dict:
    t0 = time.perf_counter()
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
        if pid not in used and (posts[pid].vacant or posts[pid].holder_id is None)
    }

    unassigned = [aid for aid, a in assignments.items() if a.kind != "ASSIGNED"]
    if unassigned and free:
        G = nx.Graph()
        left = [f"A:{a}" for a in unassigned]
        right = [f"P:{p}" for p in free]
        G.add_nodes_from(left, bipartite=0)
        G.add_nodes_from(right, bipartite=1)
        edge_rank = {}
        for aid in unassigned:
            for pid, rank in options.get(aid, []):
                if pid in free:
                    G.add_edge(f"A:{aid}", f"P:{pid}")
                    edge_rank[(aid, pid)] = rank
        if G.number_of_edges() > 0:
            matching = nx.bipartite.hopcroft_karp_matching(G, top_nodes=left)
            pairs = []
            for node, mate in matching.items():
                if node.startswith("A:") and mate.startswith("P:"):
                    aid, pid = node[2:], mate[2:]
                    pairs.append((edge_rank.get((aid, pid), 99), aid, pid))
            pairs.sort()
            claimed = set()
            for rank, aid, pid in pairs:
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
            for pid, rank in options.get(aid, []):
                if pid in free:
                    assignments[aid] = Assignment(
                        agent_id=aid, post_id=pid, wish_rank=rank, kind="ASSIGNED",
                    )
                    free.discard(pid)
                    used.add(pid)
                    break

    # Rank improvement swaps onto free posts
    improved = True
    passes = 0
    while improved and passes < 5:
        improved = False
        passes += 1
        for aid in sorted(agents.keys()):
            cur = assignments[aid]
            if cur.kind != "ASSIGNED":
                continue
            cur_rank = cur.wish_rank or 99
            for pid, rank in options.get(aid, []):
                if pid not in free or rank >= cur_rank:
                    continue
                old = cur.post_id
                assignments[aid] = Assignment(
                    agent_id=aid, post_id=pid, wish_rank=rank, kind="ASSIGNED",
                )
                free.discard(pid)
                if old:
                    free.add(old)
                improved = True
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
        "method": "FAST_HYBRID_LIBERATION_MATCHING",
        "result_hash": hashlib.sha256(canon.encode()).hexdigest()[:16],
        "elapsed_ms": (t_end - t0) * 1000,
        "timing": {
            "liberation_ms": (t_lib - t0) * 1000,
            "improve_ms": (t_end - t_lib) * 1000,
        },
        "optimality": {
            "proven": False,
            "method": "HYBRID_HEURISTIC",
            "status": "UNKNOWN",
        },
        "objective_vector": policy.score_vector(assignments, agents),
        "policy_version": policy.version,
    }
