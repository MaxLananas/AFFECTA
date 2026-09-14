from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class Chain:
    agents: Tuple[str, ...]
    posts: Tuple[str, ...]
    ends_on_vacant: bool
    depth: int
    id: str = ""


@dataclass
class Cycle:
    agents: Tuple[str, ...]
    classification: str  # RESOLVABLE | CONSTRAINED | IMPOSSIBLE | REGULATORY_UNKNOWN
    id: str = ""


@dataclass
class DependencyGraph:
    """Agent desires post held by another agent → edge agent → holder."""
    edges: Dict[str, str] = field(default_factory=dict)  # agent -> holder
    desired_post: Dict[str, str] = field(default_factory=dict)  # agent -> post
    holders: Dict[str, str] = field(default_factory=dict)  # post -> holder


def build_dependency_graph(
    desired: Dict[str, str],
    post_holder: Dict[str, Optional[str]],
) -> DependencyGraph:
    g = DependencyGraph()
    g.desired_post = dict(desired)
    for agent, post_id in desired.items():
        holder = post_holder.get(post_id)
        if holder and holder != agent:
            g.edges[agent] = holder
            g.holders[post_id] = holder
    return g


def tarjan_scc(edges: Dict[str, str]) -> List[List[str]]:
    """Return list of strongly connected components with size >= 1 that are cycles."""
    index = 0
    stack: List[str] = []
    on_stack: Set[str] = set()
    indices: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    result: List[List[str]] = []

    nodes = set(edges.keys()) | set(edges.values())

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        w = edges.get(v)
        if w is not None:
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])

        if lowlink[v] == indices[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or (len(comp) == 1 and edges.get(comp[0]) == comp[0]):
                result.append(comp)

    for node in nodes:
        if node not in indices:
            strongconnect(node)
    return result


def extract_chains(edges: Dict[str, str], desired: Dict[str, str],
                   vacant_posts: Set[str]) -> List[Chain]:
    """Linear chains ending on a vacant post."""
    # reverse: who points to me
    incoming: Dict[str, List[str]] = defaultdict(list)
    for a, h in edges.items():
        incoming[h].append(a)

    chains = []
    cid = 0
    # agents who desire a vacant post
    for agent, post in desired.items():
        if post not in vacant_posts:
            continue
        # walk upstream
        path_agents = [agent]
        path_posts = [post]
        seen = {agent}
        cur = agent
        # upstream: who wants this agent's current situation? simplified: just record terminal
        chains.append(Chain(
            agents=tuple(path_agents),
            posts=tuple(path_posts),
            ends_on_vacant=True,
            depth=1,
            id=f"CH{cid}",
        ))
        cid += 1
    return chains


def classify_cycle(agents: List[str], policy: str = "REGULATORY_UNKNOWN") -> Cycle:
    """Default: REGULATORY_UNKNOWN — do not invent resolution."""
    return Cycle(
        agents=tuple(agents),
        classification=policy,
        id="CY" + "_".join(sorted(agents)[:3]),
    )
