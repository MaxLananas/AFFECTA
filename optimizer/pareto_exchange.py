"""
AFFECTA — Optimiseur d'efficacité de Pareto par cycles d'échange (post-traitement).

POURQUOI CE MODULE
------------------
L'acceptation différée (`solver/deferred_acceptance.py`) produit l'appariement STABLE
optimal-enseignant *pour l'ensemble de mouvements autorisé*. Par défaut, AFFECTA reste
CONSERVATEUR et interdit les échanges purs (permutations de postes sans poste vacant),
faute de règle réglementaire sourcée à ce sujet (voir la docstring de
`deferred_acceptance.py` §CYCLES). Conséquence mesurée sur données réelles Guadeloupe :
l'appariement laisse en moyenne ~4 (jusqu'à 7) *opportunités d'échange pur* inexploitées
— des groupes d'enseignants qui seraient TOUS strictement mieux servis en échangeant
leurs postes, sans léser personne.

Ce module transforme cette perte en gain, de façon AUDITABLE :

  1. il détecte les **cycles d'échange améliorant strictement Pareto** (chaque
     participant obtient un vœu strictement meilleur, personne n'est lésé) ;
  2. il attribue les **unités vacantes** libérées en cascade à leur meilleur candidat
     RÉGLEMENTAIRE (chaînes), exactement comme l'aurait fait l'acceptation différée si le
     poste s'était libéré à temps ;
  3. il applique ces mouvements par rotation (l'affectation reste une bijection
     agent→unité de poste : aucun poste n'est dédoublé) ;
  4. il RE-VÉRIFIE la stabilité de façon indépendante (`explain/stability.py`) et n'engage
     un lot d'échanges que s'il reste sans envie justifiée — la garantie d'équité de la
     phase principale n'est JAMAIS sacrifiée au profit du bien-être ;
  5. il émet un **certificat d'échange** listant chaque mouvement, chaque poste
     avant/après et le gain de rang de vœu de chaque enseignant, pour une traçabilité
     totale.

Réf. académique : Abdulkadiroğlu & Sönmez (1999), « House Allocation with Existing
Tenants » — allocation Pareto-efficace en présence d'agents titulaires (Top Trading
Cycles *and Chains*).

STATUT RÉGLEMENTAIRE
--------------------
Autoriser les échanges purs est une **PRODUCT_POLICY** explicite, jamais présentée comme
une règle réglementaire (aucune source ne confirme ni n'interdit les permutations pures
dans le MVT1D). Ce module ne s'exécute donc QUE lorsqu'il est demandé explicitement
(`run_movement(..., pareto_exchanges=True)`), et ses effets sont intégralement tracés.

PROPRIÉTÉS GARANTIES (vérifiées par les tests)
----------------------------------------------
* **Amélioration de Pareto stricte** : tout enseignant touché obtient un vœu strictement
  mieux classé ; aucun enseignant ne voit sa situation se dégrader.
* **Faisabilité** : l'affectation reste une injection agent→unité de poste.
* **Stabilité préservée** : re-contrôlée par le vérificateur indépendant après coup.
* **Déterminisme** : mouvements choisis par clés triées, résultat reproductible.
* **Terminaison / idempotence** : la somme des rangs de vœu décroît strictement à chaque
  tour et est bornée inférieurement — convergence en un nombre fini de tours.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.regulatory.registry import RuleRegistry, guadeloupe_registry
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.solver.engine import _tie_key
from movement_engine.explain.stability import check_stability

# Rang « pire que tout vœu » attribué à un agent resté sur poste (STAY) : n'importe quel
# vœu éligible constitue pour lui une amélioration stricte.
_WORST_RANK = 10 ** 9


@dataclass
class ExchangeStep:
    """Un mouvement appliqué : rotation (cycle) ou attribution d'une unité vacante."""
    agents: Tuple[str, ...]
    posts_before: Tuple[Optional[str], ...]
    posts_after: Tuple[str, ...]
    ranks_before: Tuple[int, ...]
    ranks_after: Tuple[int, ...]

    def to_dict(self) -> dict:
        return {
            "agents": list(self.agents),
            "posts_before": list(self.posts_before),
            "posts_after": list(self.posts_after),
            "ranks_before": [None if r >= _WORST_RANK else r for r in self.ranks_before],
            "ranks_after": list(self.ranks_after),
            "rank_gain": [
                (None if rb >= _WORST_RANK else rb - ra)
                for rb, ra in zip(self.ranks_before, self.ranks_after)
            ],
        }


@dataclass
class ExchangeCertificate:
    """Preuve auditable de l'ensemble des mouvements de Pareto appliqués."""
    applied: bool
    n_cycles: int
    n_agents_improved: int
    total_rank_gain: int
    stable_before: bool
    stable_after: bool
    steps: List[ExchangeStep] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "policy": "PRODUCT_POLICY:PARETO_IMPROVING_EXCHANGES",
            "applied": self.applied,
            "n_cycles": self.n_cycles,
            "n_agents_improved": self.n_agents_improved,
            "total_rank_gain": self.total_rank_gain,
            "stable_before": self.stable_before,
            "stable_after": self.stable_after,
            "note": self.note,
            "steps": [s.to_dict() for s in self.steps],
            "method": "PARETO_EXCHANGE_POSTPROCESSOR",
        }


def _eligible_wish_targets(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    registry: RuleRegistry,
    campaign_seed: str,
) -> Tuple[Dict[str, Dict[str, int]], Dict[Tuple[str, str], tuple]]:
    """Cibles éligibles par agent + clés réglementaires par (agent, poste).

    Renvoie `(targets, keys)` où :
      * `targets[aid][pid]` = meilleur rang de vœu de `aid` visant le poste `pid` ;
      * `keys[(aid, pid)]`  = clé de classement réglementaire de `aid` sur `pid`
        (sert à respecter l'ordre du poste lorsqu'une unité vacante est réattribuée —
        condition NÉCESSAIRE au maintien de la stabilité).

    Le vœu pour son propre poste est ignoré (MVT1D : STAY est le filet, pas un vœu).
    """
    out: Dict[str, Dict[str, int]] = {}
    keys: Dict[Tuple[str, str], tuple] = {}
    for aid, agent in agents.items():
        tie = _tie_key(aid, campaign_seed)
        best: Dict[str, int] = {}
        for wish in wishes.get(aid, []):
            for pid in wish.post_ids:
                if pid not in posts or pid == agent.current_post_id:
                    continue
                if pid in best and best[pid] <= wish.rank:
                    continue
                s = score_candidate(
                    agent, posts[pid], wish, registry,
                    sous_rank=None, tie_key=tie,
                )
                if s.eligible:
                    prev = best.get(pid)
                    if prev is None or wish.rank < prev:
                        best[pid] = wish.rank
                        keys[(aid, pid)] = s.regulatory_key()
        if best:
            out[aid] = best
    return out, keys


def _resolve_free_units(
    free_units: Dict[str, int],
    current_rank: Dict[str, int],
    targets: Dict[str, Dict[str, int]],
    keys: Dict[Tuple[str, str], tuple],
    wanters: Dict[str, List[str]],
) -> List[Tuple[str, str]]:
    """Attribue chaque unité vacante à son candidat le MIEUX classé réglementairement.

    Pour préserver la stabilité, une unité vacante d'un poste `pid` DOIT revenir au
    candidat éligible le mieux classé au sens de l'ordre du poste (priorité, barème, …)
    parmi TOUS ceux qui la préfèrent strictement — pas seulement ceux dont c'est le vœu
    de tête. C'est exactement le choix qu'aurait fait l'acceptation différée si le poste
    s'était libéré à temps ; il ne peut donc pas créer d'envie justifiée.

    Renvoie une liste déterministe de (agent, poste_vacant) sans conflit : un agent
    n'apparaît qu'une fois (sur le poste vacant qu'il préfère), une unité une fois.
    """
    best_for_post: Dict[str, Tuple[tuple, str]] = {}
    for pid in free_units:
        for aid in wanters.get(pid, ()):
            rank = targets[aid][pid]
            if rank >= current_rank.get(aid, _WORST_RANK):
                continue                       # pas une amélioration stricte pour aid
            k = keys.get((aid, pid))
            if k is None:
                continue
            prev = best_for_post.get(pid)
            if prev is None or (k, aid) < prev:
                best_for_post[pid] = (k, aid)
    # résoudre les conflits : un agent retenu pour plusieurs postes garde son préféré
    chosen: Dict[str, Tuple[int, str]] = {}    # agent -> (rang, poste)
    for pid, (_, aid) in best_for_post.items():
        rank = targets[aid][pid]
        prev = chosen.get(aid)
        if prev is None or (rank, pid) < prev:
            chosen[aid] = (rank, pid)
    return sorted((aid, pid) for aid, (_, pid) in chosen.items())


def _find_improving_cycles(
    holder_of_post: Dict[str, str],
    current_post: Dict[str, str],
    current_rank: Dict[str, int],
    targets: Dict[str, Dict[str, int]],
) -> List[List[str]]:
    """Cycles d'échange améliorant strictement Pareto (aucune unité vacante en jeu).

    Chaque agent pointe vers l'occupant du poste qu'il PRÉFÈRE le plus parmi ceux qui
    améliorent strictement sa situation. Un cycle dans ce graphe fonctionnel est une
    rotation où chacun obtient son poste le plus désiré du cycle : Pareto strict.
    """
    edge: Dict[str, str] = {}
    for aid, want in targets.items():
        cur = current_rank.get(aid, _WORST_RANK)
        cands = []
        for pid, rank in want.items():
            if rank >= cur:
                continue
            holder = holder_of_post.get(pid)
            if holder is not None and holder != aid:
                cands.append((rank, pid, holder))
        if not cands:
            continue
        cands.sort(key=lambda c: (c[0], c[1]))
        edge[aid] = cands[0][2]

    cycles: List[List[str]] = []
    used: set = set()
    done: set = set()
    for start in sorted(edge):
        if start in done or start in used:
            continue
        path: List[str] = []
        pos: Dict[str, int] = {}
        cur: Optional[str] = start
        while cur is not None and cur in edge and cur not in done and cur not in used:
            if cur in pos:
                cyc = path[pos[cur]:]
                if all(c not in used for c in cyc):
                    cycles.append(cyc)
                    used.update(cyc)
                break
            pos[cur] = len(path)
            path.append(cur)
            cur = edge[cur]
        for node in path:
            done.add(node)
    return cycles


def improve_pareto(
    assignments: Dict[str, Assignment],
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    registry: Optional[RuleRegistry] = None,
    *,
    campaign_seed: str = "20260810",
    max_rounds: int = 100,
    verify_stability: bool = True,
) -> Tuple[Dict[str, Assignment], ExchangeCertificate]:
    """Applique les mouvements d'amélioration de Pareto au résultat d'un appariement.

    Renvoie `(nouvelles_affectations, certificat)`. Les affectations d'origine ne sont
    pas mutées. Si `verify_stability=True`, l'état final est recontrôlé par le
    vérificateur indépendant ; en cas d'apparition (théorique) d'une envie justifiée, le
    lot est ANNULÉ et l'appariement d'origine est renvoyé intact (garantie d'équité
    prioritaire sur le bien-être).
    """
    registry = registry or guadeloupe_registry()

    stable_before = True
    if verify_stability:
        cert0 = check_stability(assignments, agents, posts, wishes, registry,
                                campaign_seed=campaign_seed)
        stable_before = cert0.stable_modulo_policy

    work: Dict[str, Assignment] = dict(assignments)
    targets, keys = _eligible_wish_targets(agents, posts, wishes, registry, campaign_seed)

    # Postes échangeables : occupant unique (capacité 1) tenu par un agent participant.
    single_cap = {pid for pid, p in posts.items() if p.capacity == 1}

    # Index inverse : pour chaque poste, la liste des agents qui le convoitent.
    wanters: Dict[str, List[str]] = {}
    for aid, want in targets.items():
        for pid in want:
            wanters.setdefault(pid, []).append(aid)

    steps: List[ExchangeStep] = []

    for _ in range(max_rounds):
        # État courant : poste et rang de chaque agent doté d'un poste, occupation.
        current_post: Dict[str, str] = {}
        current_rank: Dict[str, int] = {}
        holder_of_post: Dict[str, str] = {}
        occupancy: Dict[str, int] = {}
        for aid, a in work.items():
            if a.post_id and a.kind in ("ASSIGNED", "STAY"):
                current_post[aid] = a.post_id
                current_rank[aid] = a.wish_rank if (a.kind == "ASSIGNED" and a.wish_rank) else _WORST_RANK
                occupancy[a.post_id] = occupancy.get(a.post_id, 0) + 1
                if a.post_id in single_cap:
                    holder_of_post[a.post_id] = aid
        # Unités vacantes = capacité - unités verrouillées (occupant externe) - occupants.
        free_units: Dict[str, int] = {}
        for pid, p in posts.items():
            locked = 1 if (not p.vacant and p.holder_id and p.holder_id not in agents) else 0
            fu = p.capacity - locked - occupancy.get(pid, 0)
            if fu > 0:
                free_units[pid] = fu

        # (a) D'abord, écouler les unités vacantes vers leur meilleur candidat
        #     réglementaire (chaînes/cascades) — c'est ce qui préserve la stabilité.
        chains = _resolve_free_units(free_units, current_rank, targets, keys, wanters)
        cycles: List[List[str]] = []
        if not chains:
            # (b) Plus aucune unité vacante réattribuable : chercher des cycles d'échange
            #     purs entre occupants (rotation).
            cycles = _find_improving_cycles(
                holder_of_post, current_post, current_rank, targets)
        if not cycles and not chains:
            break

        # Appliquer les chaînes : chaque agent prend un poste vacant strictement préféré ;
        # son ancien poste est rouvert au tour suivant (cascade).
        for aid, new_pid in chains:
            new_rank = targets[aid][new_pid]
            posts_before = (current_post.get(aid),)
            ranks_before = (current_rank.get(aid, _WORST_RANK),)
            sc = work[aid].score
            work[aid] = Assignment(
                agent_id=aid, post_id=new_pid, wish_rank=new_rank,
                kind="ASSIGNED", score=sc, chain_id="PARETO_CHAIN",
            )
            steps.append(ExchangeStep(
                agents=(aid,), posts_before=posts_before,
                posts_after=(new_pid,), ranks_before=ranks_before,
                ranks_after=(new_rank,),
            ))

        # Appliquer les cycles : rotation ; agent i prend le poste de l'agent suivant.
        for cyc in cycles:
            n = len(cyc)
            posts_before = tuple(current_post.get(a) for a in cyc)
            ranks_before = tuple(current_rank.get(a, _WORST_RANK) for a in cyc)
            posts_after: List[str] = []
            ranks_after: List[int] = []
            for i, aid in enumerate(cyc):
                nxt = cyc[(i + 1) % n]
                new_pid = current_post[nxt]
                new_rank = targets[aid][new_pid]
                posts_after.append(new_pid)
                ranks_after.append(new_rank)
                sc = work[aid].score
                work[aid] = Assignment(
                    agent_id=aid, post_id=new_pid, wish_rank=new_rank,
                    kind="ASSIGNED", score=sc, chain_id="PARETO_EXCHANGE",
                )
            steps.append(ExchangeStep(
                agents=tuple(cyc),
                posts_before=posts_before,
                posts_after=tuple(posts_after),
                ranks_before=ranks_before,
                ranks_after=tuple(ranks_after),
            ))

    if not steps:
        return dict(assignments), ExchangeCertificate(
            applied=False, n_cycles=0, n_agents_improved=0, total_rank_gain=0,
            stable_before=stable_before, stable_after=stable_before,
            note="Aucun mouvement améliorant : l'appariement est déjà Pareto-efficace.",
        )

    stable_after = stable_before
    if verify_stability:
        cert1 = check_stability(work, agents, posts, wishes, registry,
                                campaign_seed=campaign_seed)
        stable_after = cert1.stable_modulo_policy
        if not stable_after:
            # Garde-fou : ne jamais dégrader l'équité. On annule tout.
            return dict(assignments), ExchangeCertificate(
                applied=False, n_cycles=len(steps),
                n_agents_improved=0, total_rank_gain=0,
                stable_before=stable_before, stable_after=stable_before,
                note="Mouvements annulés : une envie justifiée serait apparue (garantie "
                     "d'équité prioritaire).",
            )

    n_improved = sum(len(s.agents) for s in steps)
    total_gain = sum(
        (rb - ra)
        for s in steps
        for rb, ra in zip(s.ranks_before, s.ranks_after)
        if rb < _WORST_RANK
    )
    return work, ExchangeCertificate(
        applied=True, n_cycles=len(steps), n_agents_improved=n_improved,
        total_rank_gain=total_gain,
        stable_before=stable_before, stable_after=stable_after,
        steps=steps,
        note="Mouvements d'amélioration stricte de Pareto, stabilité re-vérifiée.",
    )
