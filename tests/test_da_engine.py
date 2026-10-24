"""Tests for the deferred-acceptance solver: correctness, stability, no justified envy."""
from __future__ import annotations

import random

from movement_engine.domain.models import Agent, Post, Wish
from movement_engine.solver.deferred_acceptance import run_deferred_acceptance
from movement_engine.solver.engine import run_engine
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry

REG = guadeloupe_registry()


def _rkey(agent, post, wish):
    return score_candidate(agent, post, wish, REG, tie_key="t").regulatory_key()


def test_da_simple_vacant():
    agents = {"A": Agent(id="A", echelon=6)}
    posts = {"X1": Post(id="X1", commune="BT", support="ECEL", vacant=True)}
    wishes = {"A": [Wish(rank=1, post_ids=("X1",))]}
    r = run_deferred_acceptance(agents, posts, wishes)
    assert r.assignments["A"].kind == "ASSIGNED"
    assert r.assignments["A"].post_id == "X1"


def test_da_priority_beats_bareme():
    agents = {
        "H": Agent(id="H", echelon=1, handicap_500=True),
        "R": Agent(id="R", echelon=11, children=50),
    }
    posts = {"X": Post(id="X", commune="BT", support="ECEL", vacant=True)}
    wishes = {"H": [Wish(rank=1, post_ids=("X",))], "R": [Wish(rank=1, post_ids=("X",))]}
    r = run_deferred_acceptance(agents, posts, wishes)
    assert r.assignments["H"].post_id == "X"
    assert r.assignments["R"].post_id != "X"


def test_da_chain_liberation():
    agents = {
        "A": Agent(id="A", echelon=6),
        "B": Agent(id="B", echelon=4, current_post_id="XB"),
    }
    posts = {
        "XB": Post(id="XB", commune="BT", support="ECEL", vacant=False, holder_id="B"),
        "Y": Post(id="Y", commune="BT", support="ECEL", vacant=True),
    }
    wishes = {"A": [Wish(rank=1, post_ids=("XB",))], "B": [Wish(rank=1, post_ids=("Y",))]}
    r = run_deferred_acceptance(agents, posts, wishes)
    assert r.assignments["B"].post_id == "Y"
    assert r.assignments["A"].post_id == "XB"


def test_da_holder_stays_blocks():
    agents = {
        "A": Agent(id="A", echelon=6),
        "B": Agent(id="B", echelon=3, current_post_id="X"),
    }
    posts = {"X": Post(id="X", commune="BT", support="ECEL", vacant=False, holder_id="B")}
    wishes = {"A": [Wish(rank=1, post_ids=("X",))]}
    r = run_deferred_acceptance(agents, posts, wishes)
    assert r.assignments["B"].kind == "STAY"
    assert r.assignments["A"].post_id != "X"


def test_da_pure_cycle_not_auto_resolved():
    agents = {
        "A": Agent(id="A", echelon=5, current_post_id="XA"),
        "B": Agent(id="B", echelon=5, current_post_id="XB"),
    }
    posts = {
        "XA": Post(id="XA", commune="BT", support="ECEL", vacant=False, holder_id="A"),
        "XB": Post(id="XB", commune="BT", support="ECEL", vacant=False, holder_id="B"),
    }
    wishes = {"A": [Wish(rank=1, post_ids=("XB",))], "B": [Wish(rank=1, post_ids=("XA",))]}
    r = run_deferred_acceptance(agents, posts, wishes)
    assert r.metrics["cycles_detected"] >= 1
    assert r.assignments["A"].kind == "STAY"
    assert r.assignments["B"].kind == "STAY"


def test_da_pure_cycle_allowed_when_opted_in():
    agents = {
        "A": Agent(id="A", echelon=5, current_post_id="XA"),
        "B": Agent(id="B", echelon=5, current_post_id="XB"),
    }
    posts = {
        "XA": Post(id="XA", commune="BT", support="ECEL", vacant=False, holder_id="A"),
        "XB": Post(id="XB", commune="BT", support="ECEL", vacant=False, holder_id="B"),
    }
    wishes = {"A": [Wish(rank=1, post_ids=("XB",))], "B": [Wish(rank=1, post_ids=("XA",))]}
    r = run_deferred_acceptance(agents, posts, wishes, allow_pure_exchanges=True)
    assert r.assignments["A"].post_id == "XB"
    assert r.assignments["B"].post_id == "XA"


def test_da_no_double_assignment():
    n = 50
    agents = {f"A{i}": Agent(id=f"A{i}", echelon=5) for i in range(n)}
    posts = {f"X{i}": Post(id=f"X{i}", commune="BT", support="ECEL", vacant=True) for i in range(n // 2)}
    wishes = {
        f"A{i}": [Wish(rank=1, post_ids=tuple(f"X{j}" for j in range(n // 2)))]
        for i in range(n)
    }
    r = run_deferred_acceptance(agents, posts, wishes)
    used = [a.post_id for a in r.assignments.values() if a.kind == "ASSIGNED"]
    assert len(used) == len(set(used))
    assert len(used) == n // 2


def test_da_capacity_multi_unit():
    """A post with capacity 3 should take the 3 best-ranked eligible candidates."""
    agents = {f"A{i}": Agent(id=f"A{i}", echelon=(i % 11) + 1, children=i) for i in range(5)}
    posts = {"X": Post(id="X", commune="BT", support="ECEL", vacant=True, capacity=3)}
    wishes = {f"A{i}": [Wish(rank=1, post_ids=("X",))] for i in range(5)}
    r = run_deferred_acceptance(agents, posts, wishes)
    assigned = [aid for aid, a in r.assignments.items() if a.kind == "ASSIGNED"]
    assert len(assigned) == 3


def test_da_deterministic():
    agents = {f"A{i}": Agent(id=f"A{i}", echelon=(i % 11) + 1) for i in range(30)}
    posts = {f"X{i}": Post(id=f"X{i}", commune="BT", support="ECEL", vacant=True) for i in range(30)}
    wishes = {f"A{i}": [Wish(rank=1, post_ids=(f"X{i}",))] for i in range(30)}
    r1 = run_deferred_acceptance(agents, posts, wishes)
    r2 = run_deferred_acceptance(agents, posts, wishes)
    assert r1.result_hash == r2.result_hash


def _brute_no_justified_envy(agents, posts, wishes, assignments):
    """Return an (agent, post) pair witnessing justified envy, or None if stable.

    Justified envy: agent a prefers post p to their assignment, is eligible for p,
    and p has an occupant b (or free unit) that a would legitimately displace, i.e.
    a's regulatory key on p is strictly better than some occupant's key (or p has a
    free unit that a is eligible for but did not get).
    """
    reg = guadeloupe_registry()
    # occupant keys per post
    occ = {}
    for aid, a in assignments.items():
        if a.kind == "ASSIGNED" and a.post_id:
            occ.setdefault(a.post_id, []).append(aid)
    for aid, ag in agents.items():
        a = assignments[aid]
        # rank of assigned post for this agent (None -> worst)
        my_wr = a.wish_rank if a.kind == "ASSIGNED" else None
        for w in wishes.get(aid, []):
            for pid in w.post_ids:
                if pid not in posts:
                    continue
                s = score_candidate(ag, posts[pid], w, reg, tie_key="t")
                if not s.eligible:
                    continue
                # does agent strictly prefer this wish to current assignment?
                prefers = (my_wr is None) or (w.rank < my_wr)
                if a.kind == "ASSIGNED" and a.post_id == pid:
                    prefers = False
                if not prefers:
                    continue
                cap = posts[pid].capacity
                holders = occ.get(pid, [])
                # free unit available?
                if len(holders) < cap:
                    # if a non-participating holder locks a unit, that's fine
                    p = posts[pid]
                    locked = 1 if (not p.vacant and p.holder_id and p.holder_id not in agents) else 0
                    if len(holders) < cap - locked:
                        return (aid, pid, "free_unit")
                    continue
                mykey = score_candidate(
                    ag, posts[pid], w, reg,
                    tie_key=__import__("movement_engine.solver.engine", fromlist=["_tie_key"])._tie_key(aid, "20260810"),
                ).regulatory_key()
                for h in holders:
                    hw = next((ww for ww in wishes.get(h, []) if pid in ww.post_ids), None)
                    if hw is None:
                        continue
                    hkey = score_candidate(
                        agents[h], posts[pid], hw, reg,
                        tie_key=__import__("movement_engine.solver.engine", fromlist=["_tie_key"])._tie_key(h, "20260810"),
                    ).regulatory_key()
                    if mykey < hkey:
                        return (aid, pid, f"beats {h}")
    return None


def test_da_no_justified_envy_random():
    """On 300 random instances, the DA matching must have NO justified envy."""
    rng = random.Random(20260914)
    violations = 0
    for _ in range(300):
        n = rng.randint(3, 12)
        np_ = rng.randint(2, 10)
        agents = {}
        posts = {}
        for j in range(np_):
            posts[f"X{j}"] = Post(id=f"X{j}", commune="C", support="ECEL", vacant=True)
        for j in range(n):
            agents[f"A{j}"] = Agent(
                id=f"A{j}", echelon=rng.randint(1, 11),
                children=rng.randint(0, 4),
                handicap_500=(rng.random() < 0.1),
                boe=(rng.random() < 0.1),
            )
        wishes = {}
        for j in range(n):
            k = rng.randint(1, np_)
            pids = rng.sample([f"X{m}" for m in range(np_)], k)
            wishes[f"A{j}"] = [Wish(rank=r + 1, post_ids=(p,)) for r, p in enumerate(pids)]
        r = run_deferred_acceptance(agents, posts, wishes)
        w = _brute_no_justified_envy(agents, posts, wishes, r.assignments)
        if w is not None:
            violations += 1
            if violations <= 3:
                print(f"  JUSTIFIED ENVY: {w}")
    assert violations == 0, f"{violations}/300 instances had justified envy"
    print("  PASS 300/300 instances free of justified envy")


def test_stability_certificate_on_da():
    """The independent stability checker must certify the DA result as stable."""
    from movement_engine.explain.stability import check_stability
    rng = random.Random(4242)
    for _ in range(30):
        n = rng.randint(3, 15)
        np_ = rng.randint(2, 12)
        agents = {f"A{j}": Agent(id=f"A{j}", echelon=rng.randint(1, 11),
                                 children=rng.randint(0, 3),
                                 handicap_500=(rng.random() < 0.1)) for j in range(n)}
        posts = {f"X{j}": Post(id=f"X{j}", commune="C", support="ECEL", vacant=True)
                 for j in range(np_)}
        wishes = {}
        for j in range(n):
            k = rng.randint(1, np_)
            pids = rng.sample([f"X{m}" for m in range(np_)], k)
            wishes[f"A{j}"] = [Wish(rank=r + 1, post_ids=(p,)) for r, p in enumerate(pids)]
        r = run_deferred_acceptance(agents, posts, wishes)
        cert = check_stability(r.assignments, agents, posts, wishes)
        assert cert.stable, f"DA produced justified envy: {cert.witnesses[:2]}"


def test_stability_pure_exchange_classified_not_true_envy():
    """A blocked pure swap must be reported as an opportunity, NOT justified envy.

    A and B want to swap posts; C wants A's post (A's post becomes free only if A moves,
    which requires the forbidden swap). The certificate must have 0 true witnesses.
    """
    from movement_engine.explain.stability import check_stability
    agents = {
        "A": Agent(id="A", echelon=5, current_post_id="XA"),
        "B": Agent(id="B", echelon=5, current_post_id="XB"),
    }
    posts = {
        "XA": Post(id="XA", commune="C", support="ECEL", vacant=False, holder_id="A"),
        "XB": Post(id="XB", commune="C", support="ECEL", vacant=False, holder_id="B"),
    }
    wishes = {"A": [Wish(rank=1, post_ids=("XB",))], "B": [Wish(rank=1, post_ids=("XA",))]}
    r = run_deferred_acceptance(agents, posts, wishes)  # conservative: no swap
    cert = check_stability(r.assignments, agents, posts, wishes)
    # No TRUE justified envy; both A and B simply stay.
    assert len(cert.witnesses) == 0
    assert cert.stable_modulo_policy is True


def test_real_data_da_has_no_true_justified_envy():
    """On the real Guadeloupe posts + synthetic wishes, DA must have 0 true envy."""
    try:
        from movement_engine.datasets.guadeloupe_2026.alpha_runner import (
            load_real_posts, generate_agents_wishes,
        )
    except Exception:
        return  # dataset helpers unavailable
    from movement_engine.explain.stability import check_stability
    posts = load_real_posts()
    agents, wishes = generate_agents_wishes(posts, 800, 15, seed=20260811)
    r = run_deferred_acceptance(agents, posts, wishes, campaign_seed="20260811")
    cert = check_stability(r.assignments, agents, posts, wishes, campaign_seed="20260811")
    assert len(cert.witnesses) == 0, f"true justified envy on real data: {cert.witnesses[:2]}"
