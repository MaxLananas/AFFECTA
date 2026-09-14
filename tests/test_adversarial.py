"""Load JSON fixtures and run adversarial checks."""
from __future__ import annotations

import json
from pathlib import Path

from movement_engine.domain.models import Agent, Post, Wish
from movement_engine.solver.engine import run_engine
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry

FIX = Path(__file__).resolve().parent.parent / "datasets" / "adversarial"
REG = guadeloupe_registry()


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


def _agents(data):
    return {a["id"]: Agent(**{k: v for k, v in a.items() if k in Agent.__dataclass_fields__}) for a in data["agents"]}


def _posts(data):
    return {p["id"]: Post(**{k: v for k, v in p.items() if k in Post.__dataclass_fields__}) for p in data["posts"]}


def _wishes(data):
    out = {}
    for aid, wlist in data["wishes"].items():
        out[aid] = [Wish(rank=w["rank"], post_ids=tuple(w["post_ids"]), precise=w.get("precise", True), group=w.get("group", False)) for w in wlist]
    return out


def test_001_priority_vs_bareme():
    d = _load("001_priority_vs_bareme.json")
    r = run_engine(_agents(d), _posts(d), _wishes(d))
    assert r.assignments["H"].post_id == "X"
    assert r.assignments["R"].post_id != "X"


def test_002_rc_apc_non_cumul():
    d = _load("002_rc_apc_non_cumul.json")
    agents = _agents(d)
    posts = _posts(d)
    wishes = _wishes(d)
    s = score_candidate(agents["A"], posts["X"], wishes["A"][0], REG)
    assert not s.eligible
    assert s.rejection_reason == "RC_APC_NON_CUMULABLE"


def test_003_cycle_no_auto():
    d = _load("003_cycle_no_auto.json")
    r = run_engine(_agents(d), _posts(d), _wishes(d))
    assert r.assignments["A"].kind == "STAY"
    assert r.assignments["B"].kind == "STAY"
    assert r.metrics["cycles_detected"] >= 1


def test_evidence_no_competitor_should_have_won():
    """If evidence says COMPETITOR_SHOULD_HAVE_WON, the solver has a bug."""
    from movement_engine.evidence.decision import build_decision_evidence, compare_scores
    from movement_engine.domain.models import CandidateScore

    agents = {
        "H": Agent(id="H", echelon=1, handicap_500=True),
        "R": Agent(id="R", echelon=11, children=50),
    }
    posts = {"X": Post(id="X", commune="BT", support="ECEL", vacant=True)}
    wishes = {k: [Wish(rank=1, post_ids=("X",))] for k in agents}
    r = run_engine(agents, posts, wishes)
    scores = {}
    for aid, ag in agents.items():
        s = score_candidate(ag, posts["X"], wishes[aid][0], REG, tie_key="t")
        scores[aid] = s
    winner = r.assignments["H"]
    ev = build_decision_evidence(winner, 0, {"X"}, scores)
    assert ev is not None
    for c in ev.competitors:
        assert c.comparison != "COMPETITOR_SHOULD_HAVE_WON", f"bug: {c}"
