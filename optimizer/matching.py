"""
Pure-Python bipartite matching — zero external dependency.

WHY
---
Five optimizer modules used to `import networkx as nx`. `networkx` is NOT available
in the target environment, so those modules raised ModuleNotFoundError on import and
were effectively dead code. This module provides the two primitives they need
(maximum-cardinality matching and rank-minimising assignment) in dependency-free
Python, so the whole optimizer layer becomes importable, testable and deployable
anywhere.

APIs are intentionally small and framework-free:
  * hopcroft_karp(adj)                 -> max cardinality matching (agent -> post)
  * min_rank_matching(adj_ranked, ...) -> cardinality-max, then rank-min assignment
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, Iterable, List, Optional, Tuple

INF = float("inf")


def hopcroft_karp(adj: Dict[str, List[str]]) -> Dict[str, str]:
    """Maximum-cardinality bipartite matching (left=agents, right=posts, capacity 1).

    `adj` maps each left node to the list of right nodes it can be matched to.
    Returns a dict agent -> post for matched agents only. O(E * sqrt(V)).
    """
    match_a: Dict[str, str] = {}
    match_p: Dict[str, str] = {}
    lefts = list(adj.keys())

    def bfs() -> bool:
        dist: Dict[str, float] = {}
        q: deque[str] = deque()
        for a in lefts:
            if a not in match_a:
                dist[a] = 0
                q.append(a)
            else:
                dist[a] = INF
        found = False
        while q:
            a = q.popleft()
            for p in adj[a]:
                nxt = match_p.get(p)
                if nxt is None:
                    found = True
                elif dist.get(nxt, INF) == INF:
                    dist[nxt] = dist[a] + 1
                    q.append(nxt)
        bfs.dist = dist  # type: ignore[attr-defined]
        return found

    def dfs(a: str) -> bool:
        dist = bfs.dist  # type: ignore[attr-defined]
        for p in adj[a]:
            nxt = match_p.get(p)
            if nxt is None or (dist.get(nxt, INF) == dist[a] + 1 and dfs(nxt)):
                match_a[a] = p
                match_p[p] = a
                return True
        dist[a] = INF
        return False

    import sys
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, len(lefts) * 2 + 1000))
    try:
        while bfs():
            for a in lefts:
                if a not in match_a:
                    dfs(a)
    finally:
        sys.setrecursionlimit(old_limit)
    return dict(match_a)


def min_rank_matching(
    adj_ranked: Dict[str, List[Tuple[str, int]]],
    *,
    capacities: Optional[Dict[str, int]] = None,
) -> Dict[str, str]:
    """Cardinality-maximal assignment that, among those, minimises total wish rank.

    `adj_ranked` maps agent -> list of (post_id, rank). Uses the successive-shortest-
    augmenting-path method on a small min-cost flow (unit capacities on the agent
    side, `capacities` per post, default 1). Deterministic given a stable input order.

    Returns agent -> post for assigned agents.
    """
    capacities = capacities or {}
    # Successive shortest augmenting paths (SSP) min-cost max-flow. Guarantees MAXIMUM
    # cardinality, and among all maximum matchings, MINIMUM total wish rank.
    # Shortest paths use SPFA (queue Bellman-Ford) which is correct with the negative
    # "refund" edges created when an occupant is bumped. AFFECTA residuals are small.
    remaining: Dict[str, int] = {}
    posts_seen: List[str] = []
    seen_set: set[str] = set()
    for a in adj_ranked:
        for pid, _ in adj_ranked[a]:
            if pid not in seen_set:
                seen_set.add(pid)
                posts_seen.append(pid)
    for pid in posts_seen:
        remaining[pid] = capacities.get(pid, 1)

    match_a: Dict[str, str] = {}            # agent -> post
    post_load: Dict[str, int] = defaultdict(int)
    post_agents: Dict[str, List[str]] = defaultdict(list)

    rank_on: Dict[Tuple[str, str], int] = {}
    all_agents = sorted(adj_ranked.keys())
    for a in all_agents:
        for pid, rank in adj_ranked[a]:
            rank_on[(a, pid)] = rank

    def augment() -> bool:
        # One SSP iteration: shortest alternating path from a virtual super-source
        # (connected to EVERY currently-unmatched agent at cost 0) to any post with
        # spare capacity. Guarantees min cost for the resulting flow value. SPFA
        # (queue Bellman-Ford) handles the negative "refund" edges from bumps.
        dist: Dict[str, float] = {}
        via: Dict[str, str] = {}
        prev_agent: Dict[str, Optional[str]] = {}
        q: deque[str] = deque()
        in_q: set[str] = set()
        for a in all_agents:
            if a not in match_a:
                dist[a] = 0.0
                prev_agent[a] = None
                q.append(a)
                in_q.add(a)
        best_end_post: Optional[str] = None
        best_end_agent: Optional[str] = None
        best_end_cost = INF
        while q:
            a = q.popleft()
            in_q.discard(a)
            da = dist[a]
            for pid, rank in adj_ranked.get(a, []):
                if post_load[pid] < remaining.get(pid, 0):
                    total = da + rank
                    if total < best_end_cost or (
                        total == best_end_cost
                        and (a, pid) < (best_end_agent or "", best_end_post or "")
                    ):
                        best_end_cost = total
                        best_end_post = pid
                        best_end_agent = a
                else:
                    for b in post_agents[pid]:
                        nd = da + rank - rank_on[(b, pid)]
                        if nd < dist.get(b, INF):
                            dist[b] = nd
                            via[b] = pid
                            prev_agent[b] = a
                            if b not in in_q:
                                in_q.add(b)
                                q.append(b)
        if best_end_post is None:
            return False
        # Flip the alternating path from the free endpoint back to the super-source.
        a, pid = best_end_agent, best_end_post
        while a is not None:
            old = match_a.get(a)
            if old is not None:
                post_load[old] -= 1
                post_agents[old].remove(a)
            match_a[a] = pid
            post_load[pid] += 1
            post_agents[pid].append(a)
            nxt = prev_agent[a]
            if nxt is None:
                break
            pid = via[a]          # post a was bumped from -> now free for predecessor
            a = nxt
        return True

    while augment():
        pass
    return match_a
