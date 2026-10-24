"""
AFFECTA — Certificat de stabilité (absence d'envie justifiée).

C'est LA garantie d'équité du moteur : une affectation est *stable* (sans envie
justifiée) si aucun enseignant ne peut légitimement réclamer un poste occupé par un
enseignant moins bien classé selon l'ordre réglementaire (priorité, barème, rang de
vœu, sous-rang, départage) — sauf droit du titulaire.

Ce vérificateur est INDÉPENDANT du solveur : il ne fait que relire le résultat et les
scores réglementaires. Il peut donc certifier n'importe quelle affectation, quelle que
soit la méthode qui l'a produite. Une violation = bug du solveur (à corriger), pas une
« décision d'optimisation ».

Voir docs/REGULATORY_SOURCES.md §Algorithme : « la priorité supplante le barème »,
traitement par poste.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.regulatory.registry import RuleRegistry, guadeloupe_registry
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.solver.engine import _tie_key


@dataclass
class EnvyWitness:
    agent_id: str
    post_id: str
    kind: str  # "FREE_UNIT" | "BEATS_OCCUPANT"
    beaten_agent: Optional[str] = None
    detail: str = ""


@dataclass
class StabilityCertificate:
    stable: bool
    n_agents: int
    n_checked_pairs: int
    witnesses: List[dict] = field(default_factory=list)
    pure_exchange_opportunities: List[dict] = field(default_factory=list)

    @property
    def stable_modulo_policy(self) -> bool:
        """Stable once we exclude blockings that only a pure exchange could resolve."""
        return len(self.witnesses) == 0

    def to_dict(self) -> dict:
        return {
            "stable": self.stable,
            "no_justified_envy": self.stable,
            "stable_modulo_no_pure_exchange_policy": self.stable_modulo_policy,
            "n_agents": self.n_agents,
            "n_checked_pairs": self.n_checked_pairs,
            "witnesses": self.witnesses,
            "pure_exchange_opportunities": self.pure_exchange_opportunities,
            "method": "INDEPENDENT_STABILITY_CHECK",
        }


def check_stability(
    assignments: Dict[str, Assignment],
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    registry: Optional[RuleRegistry] = None,
    *,
    campaign_seed: str = "20260810",
    max_witnesses: int = 50,
) -> StabilityCertificate:
    """Verify the assignment has no justified envy. Returns a certificate."""
    registry = registry or guadeloupe_registry()

    # Occupants (participating agents) per post, with their regulatory keys.
    occupants: Dict[str, List[Tuple[str, tuple]]] = {}
    assigned_rank: Dict[str, Optional[int]] = {}
    for aid, a in assignments.items():
        assigned_rank[aid] = a.wish_rank if a.kind == "ASSIGNED" else None
        if a.post_id and a.kind in ("ASSIGNED", "STAY"):
            key = _key_on_post(aid, a.post_id, agents, posts, wishes, registry, campaign_seed)
            occupants.setdefault(a.post_id, []).append((aid, key))

    # Realized "moved onto the post of another participating holder" graph, used to
    # tell apart TRUE justified envy from opportunities that only a (policy-forbidden)
    # pure exchange could satisfy.
    holder_of_post = {ag.current_post_id: aid for aid, ag in agents.items() if ag.current_post_id}
    move_edge: Dict[str, str] = {}   # agent -> agent whose current post it took
    for aid, a in assignments.items():
        if a.kind == "ASSIGNED" and a.post_id:
            h = holder_of_post.get(a.post_id)
            if h is not None and h != aid:
                move_edge[aid] = h

    def _is_pure_exchange_block(envier: str, wanted_post: str) -> bool:
        """True if `wanted_post` is empty only because a chain of moves would need to
        loop back to `envier`'s own post (a pure exchange), which policy forbids."""
        orig_holder = posts[wanted_post].holder_id
        if orig_holder is None or orig_holder not in agents:
            return False
        my_post = agents[envier].current_post_id
        if my_post is None:
            return False
        # Follow the move chain from the vacated post's holder; if it can only close by
        # taking `envier`'s own post, granting the wish requires a pure exchange.
        seen = set()
        cur = orig_holder
        for _ in range(len(agents) + 1):
            if cur is None or cur in seen:
                break
            seen.add(cur)
            dest = assignments[cur].post_id if cur in assignments else None
            if dest == my_post:
                return True
            cur = move_edge.get(cur)
        return False

    witnesses: List[EnvyWitness] = []
    opportunities: List[EnvyWitness] = []
    checked = 0

    for aid, agent in agents.items():
        a = assignments.get(aid)
        my_rank = assigned_rank.get(aid)
        for w in wishes.get(aid, []):
            for pid in w.post_ids:
                if pid not in posts:
                    continue
                # Confirmed MVT1D rule: a wish for one's OWN current post is ignored by
                # the algorithm (STAY is the fallback), so it cannot ground envy.
                if pid == agent.current_post_id:
                    continue
                s = score_candidate(agent, posts[pid], w, registry,
                                    sous_rank=None, tie_key=_tie_key(aid, campaign_seed))
                if not s.eligible:
                    continue
                # Does the agent strictly prefer this wish over their current lot?
                if a and a.kind == "ASSIGNED" and a.post_id == pid:
                    continue
                prefers = (my_rank is None) or (w.rank < my_rank)
                if not prefers:
                    continue
                checked += 1
                p = posts[pid]
                occ = occupants.get(pid, [])
                # Free unit? (capacity minus externally-locked units minus occupants)
                locked = 1 if (not p.vacant and p.holder_id and p.holder_id not in agents) else 0
                if len(occ) < p.capacity - locked:
                    wit = EnvyWitness(aid, pid, "FREE_UNIT",
                                      detail="poste avec unité libre non attribuée")
                    (opportunities if _is_pure_exchange_block(aid, pid) else witnesses).append(wit)
                    continue
                my_key = s.regulatory_key()
                # Incumbent right: cannot displace the post's own holder.
                for oid, okey in occ:
                    if oid == pid_holder(pid, agents, posts):
                        continue  # holder is untouchable
                    if my_key < okey:
                        wit = EnvyWitness(
                            aid, pid, "BEATS_OCCUPANT", beaten_agent=oid,
                            detail="candidat mieux classé que l'occupant (hors titulaire)",
                        )
                        (opportunities if _is_pure_exchange_block(aid, pid) else witnesses).append(wit)
                        break

    return StabilityCertificate(
        stable=len(witnesses) == 0 and len(opportunities) == 0,
        n_agents=len(agents),
        n_checked_pairs=checked,
        witnesses=[w.__dict__ for w in witnesses[:max_witnesses]],
        pure_exchange_opportunities=[w.__dict__ for w in opportunities[:max_witnesses]],
    )


def pid_holder(pid: str, agents: Dict[str, Agent], posts: Dict[str, Post]) -> Optional[str]:
    p = posts.get(pid)
    if p and p.holder_id and p.holder_id in agents:
        return p.holder_id
    return None


def _key_on_post(aid, pid, agents, posts, wishes, registry, seed) -> tuple:
    """Regulatory key of agent `aid` on post `pid` (incumbent gets absolute priority)."""
    agent = agents[aid]
    if agent.current_post_id == pid:
        return (-1,)  # incumbent right
    for w in wishes.get(aid, []):
        if pid in w.post_ids:
            s = score_candidate(agent, posts[pid], w, registry,
                                tie_key=_tie_key(aid, seed))
            if s.eligible:
                return s.regulatory_key()
    return (10**9,)
