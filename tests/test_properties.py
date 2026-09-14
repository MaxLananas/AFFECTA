"""Property-based / monotonicity tests — try to break the engine."""
from movement_engine.domain.models import Agent, Post, Wish
from movement_engine.solver.engine import run_engine
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry


REG = guadeloupe_registry()
POST = Post(id="X", commune="BT", support="ECEL", vacant=True)
W1 = Wish(rank=1, post_ids=("X",), precise=True)


def test_higher_priority_always_beats_lower_regardless_of_bareme():
    """Monotonicity: priority dominates bareme."""
    high = Agent(id="H", echelon=1, handicap_500=True)  # priority ~10
    for children in [0, 10, 50, 100, 500]:
        low = Agent(id="L", echelon=11, children=children)  # huge bareme possible
        agents = {"H": high, "L": low}
        posts = {"X": POST}
        wishes = {"H": [W1], "L": [W1]}
        r = run_engine(agents, posts, wishes)
        assert r.assignments["H"].post_id == "X", f"failed at children={children}"
        assert r.assignments["L"].post_id != "X"


def test_higher_bareme_wins_at_same_priority():
    a = Agent(id="A", echelon=11, children=5)   # more points
    b = Agent(id="B", echelon=3, children=0)
    r = run_engine(
        {"A": a, "B": b},
        {"X": POST},
        {"A": [W1], "B": [W1]},
    )
    assert r.assignments["A"].post_id == "X"


def test_increasing_winner_bareme_keeps_win():
    """If A already wins, increasing A's points must keep A winning."""
    a = Agent(id="A", echelon=8, children=2)
    b = Agent(id="B", echelon=5, children=0)
    r1 = run_engine({"A": a, "B": b}, {"X": POST}, {"A": [W1], "B": [W1]})
    assert r1.assignments["A"].post_id == "X"
    a2 = Agent(id="A", echelon=11, children=10)
    r2 = run_engine({"A": a2, "B": b}, {"X": POST}, {"A": [W1], "B": [W1]})
    assert r2.assignments["A"].post_id == "X"


def test_no_double_assignment_property():
    n = 80
    agents = {f"A{i}": Agent(id=f"A{i}", echelon=5) for i in range(n)}
    posts = {f"X{i}": Post(id=f"X{i}", commune="BT", support="ECEL", vacant=True) for i in range(n // 2)}
    wishes = {
        f"A{i}": [Wish(rank=1, post_ids=tuple(f"X{j}" for j in range(n // 2)))]
        for i in range(n)
    }
    r = run_engine(agents, posts, wishes)
    used = [a.post_id for a in r.assignments.values() if a.kind == "ASSIGNED"]
    assert len(used) == len(set(used))


def test_determinism_property():
    agents = {f"A{i}": Agent(id=f"A{i}", echelon=(i % 11) + 1) for i in range(30)}
    posts = {f"X{i}": Post(id=f"X{i}", commune="BT", support="ECEL", vacant=True) for i in range(30)}
    wishes = {f"A{i}": [Wish(rank=1, post_ids=(f"X{i}",))] for i in range(30)}
    r1 = run_engine(agents, posts, wishes)
    r2 = run_engine(agents, posts, wishes)
    assert r1.result_hash == r2.result_hash
    for aid in agents:
        assert r1.assignments[aid].post_id == r2.assignments[aid].post_id


def test_unknown_cycle_does_not_mutate():
    """Cycle REGULATORY_UNKNOWN → no automatic swap."""
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
    assert r.assignments["A"].kind == "STAY"
    assert r.assignments["B"].kind == "STAY"


def test_rc_never_on_group():
    from movement_engine.regulatory.scorer import score_candidate
    agent = Agent(id="A", echelon=6, rc_points=250)
    post = Post(id="X", commune="BT", support="ECEL")
    wish = Wish(rank=1, post_ids=("X",), precise=False, group=True)
    s = score_candidate(agent, post, wish, REG)
    assert not s.eligible
    assert s.rejection_reason == "RC_NOT_APPLICABLE_TO_GROUP"
