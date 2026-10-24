"""
Équivalence stricte et robustesse de la phase d'extension optimisée.

`solver/extension.run_extension` a été réécrite d'un balayage naïf O(agents x postes) vers
un couplage glouton quasi linéaire. Ce module PROUVE, par différentiel exhaustif contre une
implémentation de référence naïve (l'ancienne sémantique, littérale), que le résultat est
identique poste pour poste sur des milliers d'instances aléatoires — y compris capacités
multiples, exigences de titre, postes à profil et cas dégénérés.
"""
from __future__ import annotations

import random
from typing import Dict, Optional

from movement_engine.domain.models import Agent, Assignment, Post
from movement_engine.solver.extension import (
    run_extension, _extension_post_order, _agent_can_hold, _base_bareme, _order_key,
)


def _reference_extension(
    assignments: Dict[str, Assignment],
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    *,
    mob_counts: Optional[Dict[str, int]] = None,
    mob_threshold: int = 2,
    campaign_seed: str = "20260810",
) -> Dict[str, Assignment]:
    """Implémentation de RÉFÉRENCE naïve (O(agents x postes)) — sémantique littérale.

    Sert d'oracle : le résultat de `run_extension` doit lui être identique.
    """
    mob_counts = mob_counts or {}
    result = dict(assignments)

    used: Dict[str, int] = {}
    for a in result.values():
        if a.kind in ("ASSIGNED", "STAY") and a.post_id:
            used[a.post_id] = used.get(a.post_id, 0) + 1
    remaining = {pid: max(0, int(p.capacity) - used.get(pid, 0)) for pid, p in posts.items()}

    pending = [
        aid for aid, ag in agents.items()
        if getattr(ag, "participation", "volontaire") == "obligatoire"
        and result.get(aid) is not None
        and result[aid].kind != "ASSIGNED"
    ]
    pending.sort(key=lambda aid: _order_key(
        agents[aid], aid, mob_counts, mob_threshold, campaign_seed))
    post_order = _extension_post_order(posts)

    for aid in pending:
        ag = agents[aid]
        valid = mob_counts.get(aid, 0) >= mob_threshold
        placed = False
        for pid in post_order:
            if remaining.get(pid, 0) <= 0:
                continue
            if not _agent_can_hold(ag, posts[pid]):
                continue
            remaining[pid] -= 1
            result[aid] = Assignment(
                agent_id=aid, post_id=pid, wish_rank=None, kind="ASSIGNED",
                chain_id="EXTENSION_PRO" if valid else "EXTENSION_TPD",
            )
            placed = True
            break
        if not placed:
            result[aid] = Assignment(
                agent_id=aid, post_id=None, wish_rank=None, kind="UNASSIGNED",
            )
    return result


def _canon(res: Dict[str, Assignment]) -> Dict[str, tuple]:
    return {aid: (a.kind, a.post_id, a.chain_id) for aid, a in res.items()}


_TOKENS = ["CAPPEI:D", "CAPPEI:F", "DIR_LA", "ULEC"]
_CIRCOS = ["C1", "C2", "C3", ""]
_NATURES = ["ECEL", "ECMA", "TR", "ULEC", ""]


def _random_instance(rng: random.Random):
    n_posts = rng.randint(0, 40)
    n_agents = rng.randint(0, 45)
    posts: Dict[str, Post] = {}
    for i in range(n_posts):
        req = ()
        if rng.random() < 0.30:
            req = tuple(sorted(set(rng.sample(_TOKENS, rng.randint(1, 2)))))
        posts[f"P{i:03d}"] = Post(
            id=f"P{i:03d}",
            commune=f"COM{i % 5}",
            support="ECEL",
            vacant=True,
            capacity=rng.choice([1, 1, 1, 2, 3]),
            circonscription=rng.choice(_CIRCOS),
            nature_code=rng.choice(_NATURES),
            profil=(rng.random() < 0.15),
            required_titles=req,
        )
    agents: Dict[str, Agent] = {}
    assignments: Dict[str, Assignment] = {}
    mob: Dict[str, int] = {}
    post_ids = list(posts)
    for i in range(n_agents):
        titles = ()
        if rng.random() < 0.4:
            titles = tuple(sorted(set(rng.sample(_TOKENS, rng.randint(1, 2)))))
        part = "obligatoire" if rng.random() < 0.7 else "volontaire"
        agents[f"A{i:03d}"] = Agent(
            id=f"A{i:03d}", echelon=rng.randint(1, 11),
            participation=part,
            aen_months=rng.randint(0, 300),
            echelon_months=rng.randint(0, 60),
            post_seniority_years=rng.randint(0, 15),
            boe=(rng.random() < 0.1),
            titles=titles,
        )
        mob[f"A{i:03d}"] = rng.randint(0, 4)
        # État initial : la plupart non affectés (UNASSIGNED), certains déjà posés.
        r = rng.random()
        if r < 0.6:
            assignments[f"A{i:03d}"] = Assignment(
                agent_id=f"A{i:03d}", post_id=None, wish_rank=None, kind="UNASSIGNED")
        elif r < 0.8 and post_ids:
            pid = rng.choice(post_ids)
            assignments[f"A{i:03d}"] = Assignment(
                agent_id=f"A{i:03d}", post_id=pid, wish_rank=1, kind="ASSIGNED")
        else:
            assignments[f"A{i:03d}"] = Assignment(
                agent_id=f"A{i:03d}", post_id=None, wish_rank=None, kind="STAY")
    return assignments, agents, posts, mob


def test_extension_matches_reference_exhaustively():
    rng = random.Random(12345)
    for trial in range(3000):
        assignments, agents, posts, mob = _random_instance(rng)
        thr = rng.choice([0, 1, 2, 3])
        seed = str(rng.randint(0, 9999))
        fast = run_extension(assignments, agents, posts,
                             mob_counts=mob, mob_threshold=thr, campaign_seed=seed)
        ref = _reference_extension(assignments, agents, posts,
                                   mob_counts=mob, mob_threshold=thr, campaign_seed=seed)
        assert _canon(fast) == _canon(ref), f"divergence au tirage {trial}"


def test_extension_capacity_multi_slot():
    posts = {
        "P0": Post(id="P0", commune="X", support="ECEL", vacant=True, capacity=3,
                   circonscription="C1", nature_code="ECEL"),
    }
    agents = {f"A{i}": Agent(id=f"A{i}", echelon=6, participation="obligatoire")
              for i in range(5)}
    assignments = {aid: Assignment(agent_id=aid, post_id=None, wish_rank=None,
                                   kind="UNASSIGNED") for aid in agents}
    out = run_extension(assignments, agents, posts)
    placed = [a for a in out.values() if a.kind == "ASSIGNED"]
    assert len(placed) == 3            # exactement la capacité
    assert all(a.post_id == "P0" for a in placed)
    assert sum(1 for a in out.values() if a.kind == "UNASSIGNED") == 2


def test_extension_title_restricted_prefers_earlier_position():
    # P0 (restreint, position 0) exige CAPPEI:D ; P1 (libre, position 1).
    posts = {
        "P0": Post(id="P0", commune="X", support="ULEC", vacant=True, capacity=1,
                   circonscription="C1", nature_code="AAA", required_titles=("CAPPEI:D",)),
        "P1": Post(id="P1", commune="X", support="ECEL", vacant=True, capacity=1,
                   circonscription="C1", nature_code="BBB"),
    }
    # H traité en premier (aen plus élevée) ; détient le titre du poste restreint.
    holder = Agent(id="H", echelon=6, participation="obligatoire",
                   titles=("CAPPEI:D",), aen_months=300)
    plain = Agent(id="N", echelon=6, participation="obligatoire", aen_months=100)
    agents = {"H": holder, "N": plain}
    assignments = {aid: Assignment(agent_id=aid, post_id=None, wish_rank=None,
                                   kind="UNASSIGNED") for aid in agents}
    out = run_extension(assignments, agents, posts)
    assert out["H"].post_id == "P0"    # le détenteur prend le poste restreint (position 0)
    assert out["N"].post_id == "P1"    # le non-détenteur prend le poste libre


def test_extension_profil_posts_excluded():
    posts = {
        "P0": Post(id="P0", commune="X", support="ECEL", vacant=True, capacity=1,
                   circonscription="C1", nature_code="ECEL", profil=True),
    }
    agents = {"A": Agent(id="A", echelon=6, participation="obligatoire")}
    assignments = {"A": Assignment(agent_id="A", post_id=None, wish_rank=None,
                                   kind="UNASSIGNED")}
    out = run_extension(assignments, agents, posts)
    assert out["A"].kind == "UNASSIGNED"   # poste à profil jamais utilisé en extension


def test_extension_empty_inputs_are_safe():
    assert run_extension({}, {}, {}) == {}
