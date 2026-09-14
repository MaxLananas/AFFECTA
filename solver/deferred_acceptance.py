"""
AFFECTA — Solveur par acceptation différée (Gale–Shapley côté enseignants).

POURQUOI CE SOLVEUR
-------------------
Le moteur historique (`solver/engine.py`) est une *dictature sérielle* : il trie les
agents par la clé réglementaire de leur meilleur vœu, puis chacun se sert. Ce n'est pas
un traitement *par poste* et cela n'offre AUCUNE garantie contre « l'envie justifiée »
(un agent prioritaire privé d'un poste par un agent moins bien classé).

L'algorithme MVT1D est décrit publiquement comme un traitement **par poste** : pour
chaque poste, une pile de candidats est triée par (priorité ↑, barème ↓, rang de vœu ↑,
sous-rang ↑, discriminants), et l'affectation se fait en cascade avec libération des
postes des agents qui bougent. Voir docs/REGULATORY_SOURCES.md §Algorithme.

L'acceptation différée côté enseignants (deferred acceptance) produit l'unique
appariement **stable** qui :
  * respecte EXACTEMENT la relation d'ordre par poste (aucune envie justifiée) ;
  * est **optimal pour les enseignants** parmi tous les appariements stables ;
  * est *strategy-proof* (un enseignant n'a jamais intérêt à mentir sur ses vœux) ;
  * modélise nativement les chaînes de libération et les capacités multi-postes.

DROIT DU TITULAIRE (incumbent right)
------------------------------------
Un agent titulaire d'un poste ne peut jamais en être délogé de force : dans la pile de
son poste actuel, il possède la priorité absolue. Son poste actuel est aussi son
« filet » (fallback) : s'il n'obtient aucun vœu, il y reste (STAY). Un poste occupé par
un titulaire participant n'est libéré que lorsque ce titulaire obtient un vœu — c'est la
libération de chaîne, gérée automatiquement par la convergence de l'algorithme.

CYCLES / ÉCHANGES PURS
----------------------
L'acceptation différée résoudrait spontanément les permutations pures (deux agents qui
échangent leurs postes sans qu'aucun poste vacant n'entre en jeu). Or, faute de règle
réglementaire sourcée sur les échanges purs, la politique par défaut d'AFFECTA reste
CONSERVATRICE : ces cycles sont détectés puis annulés (retour STAY), exactement comme le
moteur historique (classification REGULATORY_UNKNOWN). On peut les autoriser via
`allow_pure_exchanges=True` (PRODUCT_POLICY explicite, jamais réglementaire).

DÉTERMINISME
------------
Les clés réglementaires sont strictes (le départage `tie_key` déterministe brise toute
égalité), donc l'appariement stable est unique et le résultat est reproductible.
"""
from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

from movement_engine.domain.models import Agent, Assignment, CandidateScore, Post, Wish
from movement_engine.regulatory.registry import RuleRegistry, guadeloupe_registry
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.solver.engine import EngineResult, _tie_key
from movement_engine.graph.dependency import Cycle, classify_cycle


# Sentinel key strictly smaller than any real regulatory key (priority_rank >= 1).
# Guarantees the incumbent holder wins the pile of their own post.
_INCUMBENT_KEY: Tuple = (-1,)


def _effective_capacity(posts: Dict[str, Post], agents: Dict[str, Agent]) -> Dict[str, int]:
    """Number of units a post can offer to the matching.

    = total capacity - units locked by NON-participating holders.
    Participating holders keep their unit via the incumbent fallback (they count
    against capacity but may release it by moving). Reproduces the historical
    single-holder engine exactly (capacity 1):
      * vacant post                     -> cap = capacity
      * occupied, holder participates   -> cap = capacity   (freeable via chain)
      * occupied, holder absent (extern)-> cap = capacity-1 (never freed)
    """
    cap: Dict[str, int] = {}
    for pid, p in posts.items():
        locked = 0
        if not p.vacant and p.holder_id is not None and p.holder_id not in agents:
            locked = 1
        cap[pid] = max(0, p.capacity - locked)
    return cap


def _build_preferences(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    registry: RuleRegistry,
    campaign_seed: str,
) -> Tuple[
    Dict[str, List[Tuple[str, Optional[int], Optional[int], Tuple, bool]]],
    Dict[Tuple[str, str], CandidateScore],
]:
    """Return per-agent ordered preference lists and the score cache.

    Each preference entry: (post_id, wish_rank, sous_rank, regulatory_key, is_fallback).
    Sorted by the agent's OWN preference order (wish_rank, sous_rank). A holder's own
    post is appended as an always-available fallback (STAY) with an incumbent key.
    A wish equal to the agent's current post is ignored (confirmed MVT1D behaviour).
    """
    prefs: Dict[str, List[Tuple[str, Optional[int], Optional[int], Tuple, bool]]] = {}
    scores: Dict[Tuple[str, str], CandidateScore] = {}
    for aid, agent in agents.items():
        tie = _tie_key(aid, campaign_seed)
        seen: set[str] = set()
        entries: List[Tuple[str, Optional[int], Optional[int], Tuple, bool]] = []
        for wish in wishes.get(aid, []):
            for sr, pid in enumerate(wish.post_ids):
                if pid not in posts or pid in seen:
                    continue
                if pid == agent.current_post_id:
                    # Ranking one's own post is ignored by MVT1D; STAY handled by fallback.
                    seen.add(pid)
                    continue
                s = score_candidate(
                    agent, posts[pid], wish, registry,
                    sous_rank=sr if wish.group else None,
                    tie_key=tie,
                )
                if not s.eligible:
                    continue
                seen.add(pid)
                scores[(aid, pid)] = s
                sous = sr if wish.group else 0
                entries.append((pid, wish.rank, sous, s.regulatory_key(), False))
        # Stable sort by the agent's declared preference order.
        entries.sort(key=lambda e: (e[1], e[2]))
        # Fallback: own post (STAY) — always last, incumbent priority.
        cur = agent.current_post_id
        if cur and cur in posts:
            entries.append((cur, None, None, _INCUMBENT_KEY, True))
        prefs[aid] = entries
    return prefs, scores


def _post_key(pid: str, aid: str, is_fallback: bool, entry_key: Tuple,
              posts: Dict[str, Post]) -> Tuple:
    """Comparison key used inside a post's pile (smaller = better candidate)."""
    if is_fallback and posts[pid].holder_id == aid:
        return _INCUMBENT_KEY
    if is_fallback:
        # STAY on own post but not recorded as holder_id: still an incumbent right.
        return _INCUMBENT_KEY
    return entry_key


def _match_once(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    prefs: Dict[str, List[Tuple[str, Optional[int], Optional[int], Tuple, bool]]],
    cap: Dict[str, int],
    forbidden: set,
) -> Dict[str, str]:
    """One teacher-proposing deferred-acceptance run, skipping forbidden (agent, post)."""
    occupants: Dict[str, Dict[str, Tuple[Tuple, bool]]] = defaultdict(dict)
    match: Dict[str, str] = {}
    next_choice: Dict[str, int] = {aid: 0 for aid in agents}
    queue: deque[str] = deque(aid for aid in agents if prefs.get(aid))

    while queue:
        aid = queue.popleft()
        plist = prefs[aid]
        i = next_choice[aid]
        if i >= len(plist):
            continue
        pid, wr, sr, ekey, is_fb = plist[i]
        next_choice[aid] = i + 1

        if (aid, pid) in forbidden:
            queue.append(aid)
            continue

        pkey = _post_key(pid, aid, is_fb, ekey, posts)
        pile = occupants[pid]
        c = cap.get(pid, 0)
        if c <= 0:
            queue.append(aid)
            continue

        if len(pile) < c:
            pile[aid] = (pkey, is_fb)
            match[aid] = pid
        else:
            worst_aid = max(pile, key=lambda x: pile[x][0])
            if pkey < pile[worst_aid][0]:
                del pile[worst_aid]
                del match[worst_aid]
                pile[aid] = (pkey, is_fb)
                match[aid] = pid
                queue.append(worst_aid)
            else:
                queue.append(aid)
    return match


def _assemble(match, agents, posts, scores):
    raw: Dict[str, Assignment] = {}
    for aid, agent in agents.items():
        pid = match.get(aid)
        if pid is None:
            raw[aid] = Assignment(
                agent_id=aid, post_id=agent.current_post_id, wish_rank=None,
                kind="STAY" if agent.current_post_id else "UNASSIGNED",
            )
        elif pid == agent.current_post_id:
            raw[aid] = Assignment(agent_id=aid, post_id=pid, wish_rank=None, kind="STAY")
        else:
            sc = scores.get((aid, pid))
            raw[aid] = Assignment(
                agent_id=aid, post_id=pid,
                wish_rank=sc.wish_rank if sc else None,
                kind="ASSIGNED", score=sc,
            )
    return raw


def run_deferred_acceptance(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    registry: Optional[RuleRegistry] = None,
    *,
    campaign_seed: str = "20260810",
    allow_pure_exchanges: bool = False,
    max_cycle_breaks: int = 200,
) -> EngineResult:
    """Teacher-proposing deferred acceptance. Drop-in replacement for `run_engine`.

    Guarantees: no justified envy (given the allowed move set), teacher-optimal stable
    matching, deterministic.

    When `allow_pure_exchanges=False` (default, conservative), realised pure-exchange
    cycles (mutual swaps with no vacant post) are forbidden edge-by-edge and the match
    is RE-SOLVED, so those agents still fall back to their next-best non-cyclic option
    (e.g. a genuinely liberated post) instead of being stranded on STAY. This keeps the
    result stable w.r.t. the allowed moves — verified by explain/stability.py.
    """
    t0 = time.perf_counter()
    registry = registry or guadeloupe_registry()

    prefs, scores = _build_preferences(agents, posts, wishes, registry, campaign_seed)
    cap = _effective_capacity(posts, agents)

    forbidden: set = set()
    match = _match_once(agents, posts, prefs, cap, forbidden)
    raw = _assemble(match, agents, posts, scores)
    cycles = _detect_realized_cycles(raw, agents, posts)
    n_cycles_seen = len(cycles)
    cycles_report = list(cycles)

    if not allow_pure_exchanges:
        breaks = 0
        while cycles and breaks < max_cycle_breaks:
            breaks += 1
            # Break each realised pure-exchange cycle MINIMALLY: forbid a single edge
            # per cycle (the lowest-priority participant taking a co-member's post).
            # Forbidding only one edge lets the rest of the chain still resolve, and if
            # a co-member vacates for a genuinely free post the remaining agents can
            # legitimately follow. Deterministic choice = max regulatory key.
            holder_of_post = {ag.current_post_id: aid for aid, ag in agents.items()
                              if ag.current_post_id}
            added = False
            for cy in cycles:
                cy_set = set(cy.agents)
                edge_candidates = []
                for aid in cy.agents:
                    took = raw[aid].post_id
                    if took and holder_of_post.get(took) in cy_set and (aid, took) not in forbidden:
                        sc = scores.get((aid, took))
                        key = sc.regulatory_key() if sc else (10**9,)
                        edge_candidates.append((key, aid, took))
                if edge_candidates:
                    # Forbid the weakest-claim edge (largest regulatory key = lowest
                    # priority). Deterministic tie-break by agent then post id.
                    _, aid, took = max(edge_candidates, key=lambda e: (e[0], e[1], e[2]))
                    forbidden.add((aid, took))
                    added = True
            if not added:
                break
            match = _match_once(agents, posts, prefs, cap, forbidden)
            raw = _assemble(match, agents, posts, scores)
            cycles = _detect_realized_cycles(raw, agents, posts)
            n_cycles_seen = max(n_cycles_seen, len(cycles))

    result_assign = raw
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
        "cycles_detected": n_cycles_seen,
        "passes": 1,
        "scores_computed": len(scores),
        "method": "DEFERRED_ACCEPTANCE",
    }
    return EngineResult(
        assignments=result_assign,
        cycles=cycles_report,
        metrics=metrics,
        elapsed_ms=elapsed,
        input_hash=input_hash,
        result_hash=result_hash,
    )


def _detect_realized_cycles(
    assignments: Dict[str, Assignment],
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
) -> List[Cycle]:
    """Cycles in the 'took the post of another participating holder' graph.

    A closed cycle means a pure permutation with no external vacancy (mutual swap).
    A chain ends on an agent who took a genuinely vacant post (no outgoing edge).
    """
    # post -> current participating holder
    holder_of_post: Dict[str, str] = {}
    for aid, ag in agents.items():
        if ag.current_post_id:
            holder_of_post[ag.current_post_id] = aid

    edges: Dict[str, str] = {}
    for aid, a in assignments.items():
        if a.kind == "ASSIGNED" and a.post_id:
            h = holder_of_post.get(a.post_id)
            if h is not None and h != aid:
                edges[aid] = h

    from movement_engine.graph.dependency import tarjan_scc
    sccs = tarjan_scc(edges)
    return [classify_cycle(c, "REGULATORY_UNKNOWN") for c in sccs]
