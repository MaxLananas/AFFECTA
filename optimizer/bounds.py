"""
Maximum cardinality bound via bipartite matching on eligible edges only.
Does NOT encode full priority constraints — that requires the regulatory filter.
Returns an upper bound; equality with solution ⇒ PROVEN cardinality (under edge set).
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional

from movement_engine.domain.models import Agent, Post, Wish
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry


def eligible_edges(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
) -> List[Tuple[str, str]]:
    """List of (agent, post) pairs that are regulatory-eligible."""
    reg = guadeloupe_registry()
    edges = []
    for aid, agent in agents.items():
        for wish in wishes.get(aid, []):
            for pid in wish.post_ids:
                if pid not in posts:
                    continue
                s = score_candidate(agent, posts[pid], wish, reg)
                if s.eligible:
                    edges.append((aid, pid))
    return edges


def max_cardinality_matching(edges: List[Tuple[str, str]], capacities: Optional[Dict[str, int]] = None) -> int:
    """
    Maximum number of agent-post assignments with capacity 1 per post (default)
    and at most 1 post per agent. Hopcroft-style BFS/DFS bipartite matching.
    """
    if not edges:
        return 0
    adj: Dict[str, List[str]] = defaultdict(list)
    for a, p in edges:
        adj[a].append(p)

    match_p: Dict[str, str] = {}  # post -> agent
    match_a: Dict[str, str] = {}  # agent -> post

    def bfs() -> bool:
        queue = deque()
        dist: Dict[str, int] = {}
        for a in adj:
            if a not in match_a:
                dist[a] = 0
                queue.append(a)
            else:
                dist[a] = float("inf")
        found = False
        while queue:
            a = queue.popleft()
            for p in adj[a]:
                # capacity 1
                if p not in match_p:
                    found = True
                else:
                    a2 = match_p[p]
                    if dist.get(a2, float("inf")) == float("inf"):
                        dist[a2] = dist[a] + 1
                        queue.append(a2)
        return found

    def dfs(a: str, dist: Dict[str, int], visited_p: Set[str]) -> bool:
        for p in adj[a]:
            if p in visited_p:
                continue
            visited_p.add(p)
            if p not in match_p:
                match_a[a] = p
                match_p[p] = a
                return True
            a2 = match_p[p]
            if dist.get(a2, float("inf")) == dist[a] + 1:
                if dfs(a2, dist, visited_p):
                    match_a[a] = p
                    match_p[p] = a
                    return True
        return False

    matching = 0
    while bfs():
        # rebuild dist for this phase
        dist: Dict[str, int] = {}
        queue = deque()
        for a in adj:
            if a not in match_a:
                dist[a] = 0
                queue.append(a)
            else:
                dist[a] = float("inf")
        while queue:
            a = queue.popleft()
            for p in adj[a]:
                if p in match_p:
                    a2 = match_p[p]
                    if dist.get(a2, float("inf")) == float("inf"):
                        dist[a2] = dist[a] + 1
                        queue.append(a2)
        for a in list(adj.keys()):
            if a not in match_a:
                if dfs(a, dist, set()):
                    matching += 1
    return matching


def cardinality_bound(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
) -> dict:
    edges = eligible_edges(agents, posts, wishes)
    # unique edges
    edges = list(set(edges))
    bound = max_cardinality_matching(edges)
    # also limited by number of vacant-ish posts and agents
    n_posts = len(posts)
    n_agents = len(agents)
    bound = min(bound, n_posts, n_agents)
    return {
        "upper_bound": bound,
        "n_edges": len(edges),
        "n_agents": n_agents,
        "n_posts": n_posts,
        "method": "BIPARTITE_MAX_MATCHING_ELIGIBLE_EDGES",
        "note": "Upper bound under eligibility only; priority constraints may lower feasible max",
    }


def classify_cardinality(assigned: int, upper_bound: int) -> str:
    if assigned == upper_bound:
        return "PROVEN_OPTIMAL"
    if assigned < upper_bound:
        return "UNKNOWN"  # may or may not be optimal under full regulatory constraints
    return "INVALID"  # assigned > bound impossible
