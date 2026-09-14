"""
Minimal drop-in shim for the tiny slice of the `networkx` API that AFFECTA's
optimizer modules used. `networkx` is not available in the target environment;
this shim is backed by `optimizer.matching` (pure Python), so the optimizer layer
becomes importable and runnable with ZERO external dependencies.

Only what AFFECTA actually calls is implemented:
  * Graph()  with add_nodes_from / add_edge / number_of_edges
  * DiGraph() with add_edge(capacity=, weight=)
  * bipartite.hopcroft_karp_matching(G, top_nodes=...)  -> both-direction dict
  * min_cost_flow(DiGraph)                              -> flow dict
  * NetworkXUnfeasible
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from movement_engine.optimizer.matching import hopcroft_karp, min_rank_matching


class NetworkXUnfeasible(Exception):
    pass


class Graph:
    def __init__(self) -> None:
        self._adj: Dict[str, set] = defaultdict(set)
        self._nodes: set = set()
        self._bip: Dict[str, int] = {}

    def add_nodes_from(self, nodes: Iterable[str], bipartite: Optional[int] = None) -> None:
        for n in nodes:
            self._nodes.add(n)
            if bipartite is not None:
                self._bip[n] = bipartite

    def add_edge(self, u: str, v: str, **_: object) -> None:
        self._nodes.add(u)
        self._nodes.add(v)
        self._adj[u].add(v)
        self._adj[v].add(u)

    def number_of_edges(self) -> int:
        return sum(len(vs) for vs in self._adj.values()) // 2


class DiGraph:
    def __init__(self) -> None:
        self.edges_data: Dict[Tuple[str, str], Dict[str, object]] = {}
        self.out: Dict[str, List[str]] = defaultdict(list)
        self.nodes: set = set()

    def add_edge(self, u: str, v: str, capacity: int = 1, weight: int = 0, **_: object) -> None:
        self.nodes.add(u)
        self.nodes.add(v)
        self.edges_data[(u, v)] = {"capacity": capacity, "weight": weight}
        self.out[u].append(v)


class _Bipartite:
    @staticmethod
    def hopcroft_karp_matching(G: Graph, top_nodes: Optional[Iterable[str]] = None) -> Dict[str, str]:
        """Return a both-direction matching dict, like networkx."""
        if top_nodes is not None:
            lefts = list(top_nodes)
        else:
            lefts = [n for n, b in G._bip.items() if b == 0]
        adj = {a: [p for p in G._adj.get(a, ())] for a in lefts}
        m = hopcroft_karp(adj)
        both: Dict[str, str] = {}
        for a, p in m.items():
            both[a] = p
            both[p] = a
        return both


bipartite = _Bipartite()


def min_cost_flow(G: DiGraph) -> Dict[str, Dict[str, int]]:
    """Solve the AFFECTA agent->post transportation structure.

    Expects the exact network shape built by fast_matching:
        SRC -> A:<agent> (cap 1) -> P:<post> (cap w) -> SNK
    Returns a flow dict {node: {neighbor: amount}} where the A->P edges carry the
    chosen assignment. Minimises total weight (rank/priority-encoded) among maximum
    matchings, mirroring networkx min_cost_flow closely enough for the caller, which
    only reads the A:->P: edges.
    """
    # Extract agent -> [(post, weight)] and post capacities.
    adj_ranked: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    capacities: Dict[str, int] = {}
    for (u, v), data in G.edges_data.items():
        if u.startswith("A:") and v.startswith("P:"):
            adj_ranked[u].append((v, int(data["weight"])))
        elif u.startswith("P:") and v == "SNK":
            capacities[u] = int(data["capacity"])
    if not adj_ranked:
        return {}
    match = min_rank_matching(adj_ranked, capacities=capacities)
    flow: Dict[str, Dict[str, int]] = defaultdict(dict)
    for a, p in match.items():
        flow[a][p] = 1
    return flow
