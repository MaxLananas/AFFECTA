"""Adversarial tests for the core engine."""
from movement_engine.domain.models import Agent, Post, Wish
from movement_engine.solver.engine import run_engine
from movement_engine.graph.dependency import tarjan_scc, build_dependency_graph


def test_simple_vacant_assignment():
    agents = {"A": Agent(id="A", echelon=6)}
    posts = {"X1": Post(id="X1", commune="BT", support="ECEL", vacant=True)}
    wishes = {"A": [Wish(rank=1, post_ids=("X1",))]}
    r = run_engine(agents, posts, wishes)
    assert r.assignments["A"].kind == "ASSIGNED"
    assert r.assignments["A"].post_id == "X1"
    assert r.metrics["assigned"] == 1


def test_holder_stays_post_not_taken():
    """Regression: occupied post must not be given away if holder stays."""
    agents = {
        "A": Agent(id="A", echelon=6),
        "B": Agent(id="B", echelon=3, current_post_id="X"),
    }
    posts = {
        "X": Post(id="X", commune="BT", support="ECEL", vacant=False, holder_id="B"),
        "Y": Post(id="Y", commune="BT", support="ECEL", vacant=True),
    }
    wishes = {
        "A": [Wish(rank=1, post_ids=("X",))],
        "B": [Wish(rank=1, post_ids=("Y",))],  # B moves to Y
    }
    r = run_engine(agents, posts, wishes)
    # B takes Y, liberates X, A can take X
    assert r.assignments["B"].post_id == "Y"
    assert r.assignments["A"].post_id == "X"


def test_holder_stays_blocks():
    agents = {
        "A": Agent(id="A", echelon=6),
        "B": Agent(id="B", echelon=3, current_post_id="X"),
    }
    posts = {
        "X": Post(id="X", commune="BT", support="ECEL", vacant=False, holder_id="B"),
    }
    wishes = {
        "A": [Wish(rank=1, post_ids=("X",))],
        # B has no wish → stays
    }
    r = run_engine(agents, posts, wishes)
    assert r.assignments["A"].kind != "ASSIGNED" or r.assignments["A"].post_id != "X"
    assert r.assignments["B"].kind == "STAY"


def test_priority_beats_bareme():
    agents = {
        "H": Agent(id="H", echelon=1, handicap_500=True),
        "R": Agent(id="R", echelon=11, children=50),
    }
    posts = {"X": Post(id="X", commune="BT", support="ECEL", vacant=True)}
    wishes = {
        "H": [Wish(rank=1, post_ids=("X",))],
        "R": [Wish(rank=1, post_ids=("X",))],
    }
    r = run_engine(agents, posts, wishes)
    assert r.assignments["H"].post_id == "X"
    assert r.assignments["R"].post_id != "X"


def test_cycle_detected_not_auto_resolved():
    agents = {
        "A": Agent(id="A", echelon=5, current_post_id="XA"),
        "B": Agent(id="B", echelon=5, current_post_id="XB"),
    }
    posts = {
        "XA": Post(id="XA", commune="BT", support="ECEL", vacant=False, holder_id="A"),
        "XB": Post(id="XB", commune="BT", support="ECEL", vacant=False, holder_id="B"),
    }
    wishes = {
        "A": [Wish(rank=1, post_ids=("XB",))],
        "B": [Wish(rank=1, post_ids=("XA",))],
    }
    r = run_engine(agents, posts, wishes)
    assert r.metrics["cycles_detected"] >= 1
    # REGULATORY_UNKNOWN → no auto swap
    assert r.assignments["A"].kind == "STAY"
    assert r.assignments["B"].kind == "STAY"


def test_no_double_assignment():
    n = 50
    agents = {f"A{i}": Agent(id=f"A{i}", echelon=5) for i in range(n)}
    posts = {f"X{i}": Post(id=f"X{i}", commune="BT", support="ECEL", vacant=True) for i in range(n // 2)}
    wishes = {
        f"A{i}": [Wish(rank=1, post_ids=tuple(f"X{j}" for j in range(n // 2)))]
        for i in range(n)
    }
    r = run_engine(agents, posts, wishes)
    used = [a.post_id for a in r.assignments.values() if a.kind == "ASSIGNED"]
    assert len(used) == len(set(used))
    assert len(used) == n // 2


def test_deterministic_hash():
    agents = {f"A{i}": Agent(id=f"A{i}", echelon=(i % 11) + 1) for i in range(20)}
    posts = {f"X{i}": Post(id=f"X{i}", commune="BT", support="ECEL", vacant=True) for i in range(20)}
    wishes = {f"A{i}": [Wish(rank=1, post_ids=(f"X{i}",))] for i in range(20)}
    r1 = run_engine(agents, posts, wishes)
    r2 = run_engine(agents, posts, wishes)
    assert r1.result_hash == r2.result_hash


def test_chain_liberation():
    """A wants XB, B wants Y vacant → both get posts."""
    agents = {
        "A": Agent(id="A", echelon=6),
        "B": Agent(id="B", echelon=4, current_post_id="XB"),
    }
    posts = {
        "XB": Post(id="XB", commune="BT", support="ECEL", vacant=False, holder_id="B"),
        "Y": Post(id="Y", commune="BT", support="ECEL", vacant=True),
    }
    wishes = {
        "A": [Wish(rank=1, post_ids=("XB",))],
        "B": [Wish(rank=1, post_ids=("Y",))],
    }
    r = run_engine(agents, posts, wishes)
    assert r.assignments["B"].post_id == "Y"
    assert r.assignments["A"].post_id == "XB"


def test_rc_group_rejected():
    from movement_engine.regulatory.scorer import score_candidate
    from movement_engine.regulatory.registry import guadeloupe_registry
    agent = Agent(id="A", echelon=6, rc_points=250)
    post = Post(id="X", commune="BT", support="ECEL")
    wish = Wish(rank=1, post_ids=("X",), precise=False, group=True)
    s = score_candidate(agent, post, wish, guadeloupe_registry())
    assert not s.eligible
