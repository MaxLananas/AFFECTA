"""Optimality tests: exhaustive oracle, cardinality bounds, greedy-loss fixture."""
from __future__ import annotations

import random
from movement_engine.domain.models import Agent, Post, Wish
from movement_engine.optimizer.exhaustive import exhaustive_optimize
from movement_engine.optimizer.solver import greedy_baseline, optimize, compare_greedy_vs_optimized
from movement_engine.optimizer.bounds import cardinality_bound, classify_cardinality
from movement_engine.optimizer.objective import DEFAULT_POLICY


def test_greedy_loss_fixture():
    """
    Classic trap for sequential greedy:
    A prefers P1 then P2
    B only wants P1
    C only wants P2

    If A takes P1 first, B is stuck, C takes P2 → 2 assigned, but B unassigned.
    Better: A takes P2, B takes P1 → still 2 assigned, and depending on policy
    more first wishes for B.

    With MAXIMIZE_ASSIGNED first, both give 2.
    With first-wish: A→P2 (wish2), B→P1 (wish1), C unassigned
    vs A→P1 (wish1), C→P2 (wish1), B unassigned
    Both: assigned=2, first=2. Equivalent on top objectives.

    Stronger trap — cardinality difference:
    A: P1, P2
    B: P1
    C: P2
    D: P3  (only one who can take P3)
    Posts: P1,P2,P3 all vacant

    Actually need a case where greedy assigns fewer people.

    Chain-like:
    A wants only X (held by B who wants Y vacant)
    Sequential: if we process A first, X not free → A unassigned, then B→Y.
    Optimized with liberation: B→Y liberates X, A→X → 2 assigned.

    Our greedy engine already does multi-pass liberation. So use pure sequential
    without liberation as "bad baseline".
    """
    # Agents: A wants XB (held by B), B wants Y vacant
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
    # Our engine with multi-pass should get both
    g = greedy_baseline(agents, posts, wishes)
    assert g["quality"]["assigned"] == 2, "chain liberation should assign both"


def test_cardinality_bound_matches_exhaustive():
    agents = {
        "A": Agent(id="A", echelon=5),
        "B": Agent(id="B", echelon=5),
        "C": Agent(id="C", echelon=5),
    }
    posts = {
        "X1": Post(id="X1", commune="BT", support="ECEL", vacant=True),
        "X2": Post(id="X2", commune="BT", support="ECEL", vacant=True),
    }
    wishes = {
        "A": [Wish(rank=1, post_ids=("X1",))],
        "B": [Wish(rank=1, post_ids=("X1",)), Wish(rank=2, post_ids=("X2",))],
        "C": [Wish(rank=1, post_ids=("X2",))],
    }
    bound = cardinality_bound(agents, posts, wishes)
    r = exhaustive_optimize(agents, posts, wishes)
    assigned = r["quality"]["assigned"]
    status = classify_cardinality(assigned, bound["upper_bound"])
    assert assigned <= bound["upper_bound"]
    # under full regulatory, assigned may be < edge-only bound
    print(f"  bound={bound['upper_bound']} assigned={assigned} status={status}")


def test_random_vs_exhaustive_batch():
    """100 random instances N=3..8: optimizer must match exhaustive objective."""
    rng = random.Random(20260811)
    failures = 0
    n_tests = 100  # 100 for speed; scale to 1000 in CI
    for i in range(n_tests):
        n = rng.randint(3, 7)
        n_posts = rng.randint(n - 1, n + 2)
        agents = {f"A{j}": Agent(id=f"A{j}", echelon=rng.randint(1, 11)) for j in range(n)}
        posts = {
            f"X{j}": Post(id=f"X{j}", commune="BT", support="ECEL", vacant=True)
            for j in range(n_posts)
        }
        wishes = {}
        for j in range(n):
            k = rng.randint(1, min(3, n_posts))
            pids = [f"X{rng.randint(0, n_posts-1)}" for _ in range(k)]
            wishes[f"A{j}"] = [Wish(rank=r + 1, post_ids=(p,)) for r, p in enumerate(pids)]

        ex = exhaustive_optimize(agents, posts, wishes)
        opt = optimize(agents, posts, wishes)
        if ex["objective_vector"] != opt.get("objective_vector") and ex["objective_vector"] != opt["quality"].get("objective_vector"):
            # compare quality vectors via policy
            from movement_engine.optimizer.objective import DEFAULT_POLICY
            ov = DEFAULT_POLICY.score_vector(opt["assignments"], agents)
            if ov != ex["objective_vector"]:
                failures += 1
                if failures <= 3:
                    print(f"  FAIL instance {i}: ex={ex['objective_vector']} opt={ov}")
    assert failures == 0, f"{failures}/{n_tests} mismatches"
    print(f"  PASS {n_tests}/{n_tests} random instances match exhaustive")


def test_bound_classification():
    agents = {"A": Agent(id="A", echelon=5), "B": Agent(id="B", echelon=5)}
    posts = {"X": Post(id="X", commune="BT", support="ECEL", vacant=True)}
    wishes = {
        "A": [Wish(rank=1, post_ids=("X",))],
        "B": [Wish(rank=1, post_ids=("X",))],
    }
    b = cardinality_bound(agents, posts, wishes)
    assert b["upper_bound"] == 1
    assert classify_cardinality(1, 1) == "PROVEN_OPTIMAL"
    assert classify_cardinality(0, 1) == "UNKNOWN"
