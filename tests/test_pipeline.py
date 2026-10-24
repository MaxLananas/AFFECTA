"""
Tests de l'orchestration en deux temps (`solver/pipeline.py`) :
acceptation différée puis extension (affectation d'office des obligatoires).

Ces tests verrouillent le comportement confirmé de la procédure MVT1D complète :
  * un participant obligatoire non satisfait par ses vœux DOIT être affecté d'office
    sur un poste vacant compatible (jamais laissé UNASSIGNED s'il reste un poste) ;
  * l'extension ne travaille que sur les postes restés vacants, donc elle ne crée
    JAMAIS d'envie justifiée et ne modifie pas la phase principale ;
  * le résultat reste déterministe et les métriques sont cohérentes.
"""
from __future__ import annotations

import random

from movement_engine.domain.models import Agent, Post, Wish
from movement_engine.solver.pipeline import run_movement, count_mob_wishes
from movement_engine.solver.deferred_acceptance import run_deferred_acceptance
from movement_engine.explain.stability import check_stability


def _scarce_instance(seed: int = 3, n: int = 120):
    """Beaucoup d'entrants obligatoires, vœux précis étroits (fortes collisions),
    juste assez de postes vacants pour tous les loger."""
    rng = random.Random(seed)
    agents, posts, wishes = {}, {}, {}
    for i in range(n + 20):
        posts[f"X{i:04d}"] = Post(
            id=f"X{i:04d}", commune=f"C{i % 8}", support="ECEL", vacant=True,
            capacity=1, circonscription=f"K{i % 4}", nature_code="ECEL",
        )
    for i in range(n):
        agents[f"A{i:04d}"] = Agent(
            id=f"A{i:04d}", echelon=(i % 11) + 1, current_post_id=None,
            participation="obligatoire", aen_months=(i % 20) * 12,
            echelon_months=(i % 5) * 12,
        )
        tgt = [f"X{rng.randint(0, 10):04d}" for _ in range(2)]
        wishes[f"A{i:04d}"] = [
            Wish(rank=r + 1, post_ids=(p,), precise=True) for r, p in enumerate(tgt)
        ]
    return agents, posts, wishes


def test_pipeline_places_all_obligatory_when_posts_available():
    agents, posts, wishes = _scarce_instance()
    r = run_movement(agents, posts, wishes, campaign_seed="3")
    oblig_unassigned = [
        aid for aid, ag in agents.items()
        if ag.participation == "obligatoire" and r.assignments[aid].kind == "UNASSIGNED"
    ]
    assert oblig_unassigned == []            # aucun obligatoire laissé sans poste
    assert r.metrics["unassigned"] == 0
    assert r.metrics.get("office_assignments", 0) > 0
    assert r.metrics["method"] == "DEFERRED_ACCEPTANCE+EXTENSION"


def test_pipeline_strictly_improves_on_da_only():
    agents, posts, wishes = _scarce_instance()
    da = run_deferred_acceptance(agents, posts, wishes, campaign_seed="3")
    pipe = run_movement(agents, posts, wishes, campaign_seed="3")
    # La phase 1 seule laisse des obligatoires sans poste ; le pipeline les loge tous.
    assert da.metrics["unassigned"] > 0
    assert pipe.metrics["assigned"] > da.metrics["assigned"]


def test_extension_creates_no_justified_envy():
    agents, posts, wishes = _scarce_instance()
    pipe = run_movement(agents, posts, wishes, campaign_seed="3")
    stab = check_stability(pipe.assignments, agents, posts, wishes, campaign_seed="3")
    # L'extension ne remplit que des postes vacants -> aucune envie justifiée nouvelle.
    assert stab.witnesses == []


def test_pipeline_preserves_phase1_assignments():
    """Tout agent affecté par la phase principale garde EXACTEMENT le même poste."""
    agents, posts, wishes = _scarce_instance()
    da = run_deferred_acceptance(agents, posts, wishes, campaign_seed="3")
    pipe = run_movement(agents, posts, wishes, campaign_seed="3")
    for aid, a in da.assignments.items():
        if a.kind == "ASSIGNED":
            assert pipe.assignments[aid].post_id == a.post_id
            assert pipe.assignments[aid].kind == "ASSIGNED"


def test_volunteer_never_office_assigned():
    """Un titulaire volontaire sans vœu satisfait reste sur son poste (STAY),
    jamais affecté d'office."""
    agents = {
        "T": Agent(id="T", echelon=8, current_post_id="P1", participation="volontaire"),
        "O": Agent(id="O", echelon=6, participation="obligatoire"),
    }
    posts = {
        "P1": Post(id="P1", commune="LES ABYMES", support="ECEL", vacant=False,
                   holder_id="T", capacity=1, circonscription="C1", nature_code="ECEL"),
        "V1": Post(id="V1", commune="LE GOSIER", support="ECEL", vacant=True,
                   capacity=1, circonscription="C2", nature_code="ECEL"),
    }
    wishes = {"O": [Wish(rank=1, post_ids=("P1",), precise=True)]}  # O convoite P1 occupé
    r = run_movement(agents, posts, wishes, campaign_seed="1")
    assert r.assignments["T"].kind == "STAY"        # volontaire non délogé
    assert r.assignments["O"].kind == "ASSIGNED"    # obligatoire logé d'office
    assert r.assignments["O"].post_id == "V1"


def test_pipeline_deterministic():
    agents, posts, wishes = _scarce_instance()
    r1 = run_movement(agents, posts, wishes, campaign_seed="3")
    r2 = run_movement(agents, posts, wishes, campaign_seed="3")
    assert r1.result_hash == r2.result_hash


def test_with_extension_false_matches_da_only():
    agents, posts, wishes = _scarce_instance()
    da = run_deferred_acceptance(agents, posts, wishes, campaign_seed="3")
    off = run_movement(agents, posts, wishes, campaign_seed="3", with_extension=False)
    assert off.result_hash == da.result_hash


def test_count_mob_wishes_counts_only_groups():
    wishes = {
        "A": [
            Wish(rank=1, post_ids=("P1",), precise=True, group=False),
            Wish(rank=2, post_ids=("P2", "P3"), group=True),
            Wish(rank=3, post_ids=("P4", "P5"), group=True),
        ],
        "B": [Wish(rank=1, post_ids=("P1",), precise=True)],
    }
    counts = count_mob_wishes(wishes)
    assert counts["A"] == 2
    assert counts["B"] == 0
