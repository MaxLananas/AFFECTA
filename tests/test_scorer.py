from movement_engine.domain.models import Agent, Post, Wish
from movement_engine.regulatory.registry import guadeloupe_registry
from movement_engine.regulatory.scorer import echelon_points, score_candidate

REGISTRY = guadeloupe_registry()
POST = Post(id="P001", commune="Basse-Terre", support="TPD")
WISH_1 = Wish(rank=1, post_ids=("P001",), precise=True)


def test_echelon_table():
    assert echelon_points(1) == 18
    assert echelon_points(2) == 18
    assert echelon_points(3) == 22
    assert echelon_points(6) == 29
    assert echelon_points(11) == 39


def test_medical_bonus_only_wish_one():
    agent = Agent(id="A", echelon=6, medical_grave=True)
    result = score_candidate(agent, POST, WISH_1, REGISTRY)
    assert result.bareme == 29 + 30
    assert "MED_GRAVE_30" in result.bonuses


def test_medical_bonus_not_on_wish_two():
    agent = Agent(id="A", echelon=6, medical_grave=True)
    wish = Wish(rank=2, post_ids=("P001",), precise=True)
    result = score_candidate(agent, POST, wish, REGISTRY)
    assert result.bareme == 29
    assert "MED_GRAVE_30" not in result.bonuses


def test_children():
    agent = Agent(id="A", echelon=6, children=3)
    result = score_candidate(agent, POST, WISH_1, REGISTRY)
    assert result.bareme == 29 + 6


def test_unique_parental_authority():
    agent = Agent(id="A", echelon=6, unique_parental_authority=True)
    result = score_candidate(agent, POST, WISH_1, REGISTRY)
    assert result.bareme == 29 + 50


def test_renewal_is_capped_at_90():
    agent = Agent(id="A", echelon=6, renewal_years=20)
    result = score_candidate(agent, POST, WISH_1, REGISTRY)
    assert result.bareme == 29 + 90
    assert "RENEWAL_V1_90" in result.bonuses


def test_rc_apc_cannot_be_combined():
    agent = Agent(id="A", echelon=6, rc_points=250, apc_points=250)
    result = score_candidate(agent, POST, WISH_1, REGISTRY)
    assert not result.eligible
    assert result.rejection_reason == "RC_APC_NON_CUMULABLE"


def test_rc_does_not_apply_to_group_wish():
    agent = Agent(id="A", echelon=6, rc_points=250)
    wish = Wish(rank=1, post_ids=("P001",), precise=False, group=True)
    result = score_candidate(agent, POST, wish, REGISTRY)
    assert not result.eligible


def test_priority_beats_huge_bareme():
    priority_agent = Agent(id="A", echelon=6, handicap_500=True)
    points_agent = Agent(id="B", echelon=11, children=100)
    a = score_candidate(priority_agent, POST, WISH_1, REGISTRY)
    b = score_candidate(points_agent, POST, WISH_1, REGISTRY)
    assert a.regulatory_key() < b.regulatory_key()


def test_deterministic():
    agent = Agent(id="A", echelon=6, children=2)
    a = score_candidate(agent, POST, WISH_1, REGISTRY)
    b = score_candidate(agent, POST, WISH_1, REGISTRY)
    assert a == b
