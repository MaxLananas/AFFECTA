"""
Tests de l'optimiseur d'efficacité de Pareto (`optimizer/pareto_exchange.py`).

Invariants vérifiés :
  * amélioration de Pareto STRICTE (personne lésé, au moins un gagnant si des échanges
    sont appliqués) ;
  * faisabilité (aucun poste dédoublé au-delà de sa capacité) ;
  * stabilité préservée (aucune envie justifiée introduite) — sur de nombreuses
    instances aléatoires ;
  * déterminisme (deux exécutions identiques donnent le même résultat) ;
  * idempotence (ré-appliquer l'optimiseur ne change plus rien).

Style « fonctions test_* + assert » pour le runner maison (`run_tests.py`).
"""
from __future__ import annotations

import random

from movement_engine.domain.models import Agent, Post, Wish
from movement_engine.solver.deferred_acceptance import run_deferred_acceptance
from movement_engine.solver.pipeline import run_movement
from movement_engine.optimizer.pareto_exchange import improve_pareto
from movement_engine.explain.stability import check_stability


def _rank_of(assign, aid):
    a = assign[aid]
    if a.kind == "ASSIGNED" and a.wish_rank:
        return a.wish_rank
    return 10 ** 9


def _no_overcapacity(assign, posts):
    occ = {}
    for a in assign.values():
        if a.post_id and a.kind in ("ASSIGNED", "STAY"):
            occ[a.post_id] = occ.get(a.post_id, 0) + 1
    return all(occ[p] <= posts[p].capacity for p in occ)


def _random_instance(seed):
    rng = random.Random(seed)
    n_agents = rng.randint(6, 16)
    n_posts = rng.randint(n_agents, n_agents + 8)
    posts = {}
    for j in range(n_posts):
        pid = f"P{j}"
        posts[pid] = Post(id=pid, commune=f"C{j % 4}", support="ADJOINT", vacant=True)
    agents = {}
    wishes = {}
    post_ids = list(posts)
    for i in range(n_agents):
        aid = f"A{i}"
        cur = None
        if rng.random() < 0.6:
            cur = post_ids[i % n_posts]
        agents[aid] = Agent(id=aid, echelon=rng.randint(1, 11),
                            aen_months=rng.randint(0, 300),
                            current_post_id=cur)
        if cur:
            posts[cur] = Post(id=cur, commune=posts[cur].commune, support="ADJOINT",
                              vacant=False, holder_id=aid)
        k = rng.randint(1, 6)
        picks = rng.sample(post_ids, k)
        wishes[aid] = tuple(Wish(rank=r + 1, post_ids=(p,)) for r, p in enumerate(picks))
    return agents, posts, wishes


def test_pareto_and_stability_random():
    """Sur 200 instances aléatoires : Pareto strict, faisabilité, stabilité."""
    improved_count = 0
    for seed in range(200):
        agents, posts, wishes = _random_instance(seed)
        base = run_deferred_acceptance(agents, posts, wishes, campaign_seed=str(seed))
        new, cert = improve_pareto(base.assignments, agents, posts, wishes,
                                   campaign_seed=str(seed))
        assert _no_overcapacity(new, posts), f"overcapacity seed={seed}"
        if cert.applied:
            improved_count += 1
            worse = better = 0
            for aid in agents:
                rb, ra = _rank_of(base.assignments, aid), _rank_of(new, aid)
                if ra > rb:
                    worse += 1
                if ra < rb:
                    better += 1
            assert worse == 0, f"agent lésé seed={seed}"
            assert better > 0, f"aucun gain seed={seed}"
            stab = check_stability(new, agents, posts, wishes, campaign_seed=str(seed))
            assert len(stab.witnesses) == 0, f"envie justifiée introduite seed={seed}"
    assert improved_count > 5, "l'optimiseur devrait trouver des gains sur ces instances"


def test_never_creates_justified_envy():
    """La garantie d'équité prime : jamais d'envie justifiée après optimisation."""
    for seed in range(50):
        agents, posts, wishes = _random_instance(seed + 1000)
        base = run_deferred_acceptance(agents, posts, wishes, campaign_seed=str(seed))
        new, _ = improve_pareto(base.assignments, agents, posts, wishes,
                                campaign_seed=str(seed))
        stab = check_stability(new, agents, posts, wishes, campaign_seed=str(seed))
        assert len(stab.witnesses) == 0


def test_deterministic():
    agents, posts, wishes = _random_instance(42)
    base = run_deferred_acceptance(agents, posts, wishes, campaign_seed="42")
    n1, c1 = improve_pareto(base.assignments, agents, posts, wishes, campaign_seed="42")
    n2, c2 = improve_pareto(base.assignments, agents, posts, wishes, campaign_seed="42")
    assert {a: n1[a].post_id for a in n1} == {a: n2[a].post_id for a in n2}
    assert c1.total_rank_gain == c2.total_rank_gain


def test_idempotent():
    """Ré-appliquer l'optimiseur au résultat déjà optimisé ne change plus rien."""
    agents, posts, wishes = _random_instance(7)
    base = run_deferred_acceptance(agents, posts, wishes, campaign_seed="7")
    once, _ = improve_pareto(base.assignments, agents, posts, wishes, campaign_seed="7")
    twice, cert2 = improve_pareto(once, agents, posts, wishes, campaign_seed="7")
    assert cert2.applied is False
    assert {a: once[a].post_id for a in once} == {a: twice[a].post_id for a in twice}


def test_pipeline_flag_off_by_default():
    """Sans le flag, le résultat est identique à l'acceptation différée pure."""
    agents, posts, wishes = _random_instance(99)
    off = run_movement(agents, posts, wishes, campaign_seed="99", with_extension=False)
    base = run_deferred_acceptance(agents, posts, wishes, campaign_seed="99")
    assert {a: off.assignments[a].post_id for a in off.assignments} == \
           {a: base.assignments[a].post_id for a in base.assignments}
    assert "pareto_exchange" not in off.metrics


def test_pipeline_flag_on_attaches_certificate():
    agents, posts, wishes = _random_instance(3)
    on = run_movement(agents, posts, wishes, campaign_seed="3",
                      pareto_exchanges=True, with_extension=False)
    assert "pareto_exchange" in on.metrics
    cert = on.metrics["pareto_exchange"]
    assert "applied" in cert
    assert cert["method"] == "PARETO_EXCHANGE_POSTPROCESSOR"


def test_no_wish_no_change():
    """Un agent sans vœu satisfait ne subit aucun échange."""
    agents = {"A": Agent(id="A", echelon=6, current_post_id="P0")}
    posts = {"P0": Post(id="P0", commune="C", support="ADJOINT", vacant=False, holder_id="A"),
             "P1": Post(id="P1", commune="C", support="ADJOINT", vacant=True)}
    wishes = {"A": [Wish(rank=1, post_ids=("P0",))]}  # vœu = poste actuel -> ignoré
    base = run_deferred_acceptance(agents, posts, wishes, campaign_seed="1")
    new, cert = improve_pareto(base.assignments, agents, posts, wishes, campaign_seed="1")
    assert cert.applied is False
    assert new["A"].post_id == "P0"
