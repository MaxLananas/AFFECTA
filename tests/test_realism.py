"""
Tests des règles réglementaires enrichies : discriminants MVT1D, géographie
(rapprochement de conjoints, mesure de carte scolaire), priorités de titre, et phase
d'extension (affectation d'office des participants obligatoires).
"""
from __future__ import annotations

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.regulatory.registry import guadeloupe_registry
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory import geography as geo
from movement_engine.solver.extension import run_extension

REG = guadeloupe_registry()
POST = Post(id="P1", commune="LES ABYMES", support="ECEL")
W1 = Wish(rank=1, post_ids=("P1",), precise=True)


# --- Discriminants MVT1D ---------------------------------------------------------------
def test_aen_discriminant_breaks_tie():
    """À priorité, barème, rang et sous-rang égaux, l'AEN la plus élevée l'emporte."""
    senior = Agent(id="S", echelon=6, aen_months=300)
    junior = Agent(id="J", echelon=6, aen_months=100)
    ks = score_candidate(senior, POST, W1, REG, tie_key="z").regulatory_key()
    kj = score_candidate(junior, POST, W1, REG, tie_key="z").regulatory_key()
    assert ks < kj  # senior est un meilleur candidat


def test_echelon_seniority_after_aen():
    """À AEN égale, l'ancienneté dans l'échelon départage avant le tirage."""
    a = Agent(id="A", echelon=6, aen_months=200, echelon_months=40)
    b = Agent(id="B", echelon=6, aen_months=200, echelon_months=10)
    ka = score_candidate(a, POST, W1, REG, tie_key="z").regulatory_key()
    kb = score_candidate(b, POST, W1, REG, tie_key="z").regulatory_key()
    assert ka < kb


def test_random_only_after_all_discriminants():
    """Discriminants identiques -> départage par tirage (tie_key)."""
    a = Agent(id="A", echelon=6, aen_months=200, echelon_months=20)
    ka1 = score_candidate(a, POST, W1, REG, tie_key="aaa").regulatory_key()
    ka2 = score_candidate(a, POST, W1, REG, tie_key="bbb").regulatory_key()
    assert ka1 < ka2  # "aaa" < "bbb"


# --- Géographie ------------------------------------------------------------------------
def test_geography_adjacency_symmetric():
    for c, ns in geo.ADJACENCY.items():
        for n in ns:
            assert c in geo.ADJACENCY[n], f"{c}->{n} non symétrique"


def test_geography_islands_isolated():
    assert geo.ADJACENCY["LA DESIRADE"] == frozenset()
    assert geo.commune_proximity("GRAND BOURG", "LES ABYMES") == "FAR"


def test_rc_distance_threshold():
    """Le RC n'est bonifié qu'au-delà de 40 km entre résidences professionnelles."""
    near = Agent(id="N", echelon=6, rc_points=150, spouse_distance_km=10.0)
    far = Agent(id="F", echelon=6, rc_points=150, spouse_distance_km=60.0)
    rn = score_candidate(near, POST, W1, REG)
    rf = score_candidate(far, POST, W1, REG)
    assert "RC_DISTANCE_INSUFFISANTE" in rn.bonuses
    assert rn.bareme == 29  # pas de bonification
    assert any(b.startswith("RC_") and b != "RC_DISTANCE_INSUFFISANTE" for b in rf.bonuses)
    assert rf.bareme > 29


def test_separation_progressive_bonus():
    a1 = Agent(id="A", echelon=6, rc_points=150, spouse_distance_km=60.0, separation_years=1)
    a3 = Agent(id="B", echelon=6, rc_points=150, spouse_distance_km=60.0, separation_years=3)
    r1 = score_candidate(a1, POST, W1, REG)
    r3 = score_candidate(a3, POST, W1, REG)
    assert r3.bareme > r1.bareme  # 350 > 50 de bonif progressive


def test_mcs_degressive_geography():
    """MCS : même commune > commune limitrophe > lointaine."""
    same = Agent(id="S", echelon=6, mcs_affected=True, current_commune="LES ABYMES")
    p_same = Post(id="PS", commune="LES ABYMES", support="ECEL")
    p_adj = Post(id="PA", commune="POINTE A PITRE", support="ECEL")
    p_far = Post(id="PF", commune="BASSE TERRE", support="ECEL")
    rs = score_candidate(same, p_same, Wish(rank=1, post_ids=("PS",)), REG)
    ra = score_candidate(same, p_adj, Wish(rank=1, post_ids=("PA",)), REG)
    rf = score_candidate(same, p_far, Wish(rank=1, post_ids=("PF",)), REG)
    assert rs.bareme > ra.bareme > rf.bareme


# --- Priorités de titre ----------------------------------------------------------------
def test_title_holder_beats_untitled_regardless_of_bareme():
    ash = Post(id="U1", commune="LES ABYMES", support="ULEC", required_titles=("CAPPEI:D",))
    titled = Agent(id="T", echelon=1, titles=("CAPPEI:D",))
    untitled = Agent(id="U", echelon=11, children=100)
    kt = score_candidate(titled, ash, Wish(rank=1, post_ids=("U1",)), REG).regulatory_key()
    ku = score_candidate(untitled, ash, Wish(rank=1, post_ids=("U1",)), REG).regulatory_key()
    assert kt < ku  # le titulaire du titre passe avant, malgré un barème énorme


def test_partial_title_between_exact_and_none():
    ash = Post(id="U1", commune="LES ABYMES", support="ULEC", required_titles=("CAPPEI:D",))
    exact = Agent(id="E", echelon=6, titles=("CAPPEI:D",))
    partial = Agent(id="P", echelon=6, titles=("CAPPEI:F",))
    none = Agent(id="N", echelon=6)
    ke = score_candidate(exact, ash, Wish(rank=1, post_ids=("U1",)), REG).regulatory_key()
    kp = score_candidate(partial, ash, Wish(rank=1, post_ids=("U1",)), REG).regulatory_key()
    kn = score_candidate(none, ash, Wish(rank=1, post_ids=("U1",)), REG).regulatory_key()
    assert ke < kp < kn


# --- Extension -------------------------------------------------------------------------
def test_extension_places_obligatoire():
    agents = {
        "O": Agent(id="O", echelon=6, participation="obligatoire"),
    }
    posts = {
        "V1": Post(id="V1", commune="LES ABYMES", support="ECEL", vacant=True, capacity=1,
                   circonscription="C1", nature_code="ECEL"),
    }
    assignments = {"O": Assignment(agent_id="O", post_id=None, wish_rank=None, kind="UNASSIGNED")}
    out = run_extension(assignments, agents, posts, mob_counts={"O": 0})
    assert out["O"].kind == "ASSIGNED"
    assert out["O"].post_id == "V1"
    assert out["O"].chain_id == "EXTENSION_TPD"  # demande incomplète -> définitif


def test_extension_valid_request_is_provisional():
    agents = {"O": Agent(id="O", echelon=6, participation="obligatoire")}
    posts = {"V1": Post(id="V1", commune="LES ABYMES", support="ECEL", vacant=True, capacity=1)}
    assignments = {"O": Assignment(agent_id="O", post_id=None, wish_rank=None, kind="UNASSIGNED")}
    out = run_extension(assignments, agents, posts, mob_counts={"O": 2})
    assert out["O"].chain_id == "EXTENSION_PRO"  # >= seuil MOB -> provisoire


def test_extension_leaves_facultatif_untouched():
    agents = {"F": Agent(id="F", echelon=6, participation="volontaire", current_post_id="H")}
    posts = {"V1": Post(id="V1", commune="LES ABYMES", support="ECEL", vacant=True, capacity=1)}
    assignments = {"F": Assignment(agent_id="F", post_id="H", wish_rank=None, kind="STAY")}
    out = run_extension(assignments, agents, posts)
    assert out["F"].kind == "STAY"  # un facultatif n'est jamais affecté d'office


def test_extension_respects_title_requirement():
    agents = {"O": Agent(id="O", echelon=6, participation="obligatoire")}
    posts = {"V1": Post(id="V1", commune="LES ABYMES", support="ULEC", vacant=True,
                        capacity=1, required_titles=("CAPPEI:D",))}
    assignments = {"O": Assignment(agent_id="O", post_id=None, wish_rank=None, kind="UNASSIGNED")}
    out = run_extension(assignments, agents, posts, mob_counts={"O": 2})
    # aucun poste sans exigence de titre disponible -> reste non affecté
    assert out["O"].kind == "UNASSIGNED"
