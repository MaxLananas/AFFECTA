"""Tests for the pure-Python matching primitives (no networkx)."""
from movement_engine.optimizer.matching import hopcroft_karp, min_rank_matching


def test_hk_perfect():
    adj = {"a": ["x", "y"], "b": ["y"], "c": ["z"]}
    m = hopcroft_karp(adj)
    assert len(m) == 3
    assert len(set(m.values())) == 3  # no double post


def test_hk_maximum_cardinality():
    # a and b compete for x only; only one can match
    adj = {"a": ["x"], "b": ["x"], "c": ["y"]}
    m = hopcroft_karp(adj)
    assert len(m) == 2


def test_min_rank_prefers_low_rank():
    adj = {"a": [("x", 2), ("y", 1)], "b": [("x", 1)]}
    m = min_rank_matching(adj)
    # a should take y (rank1) leaving x for b, total rank = 1+1
    assert m["a"] == "y"
    assert m["b"] == "x"


def test_min_rank_capacity():
    adj = {"a": [("x", 1)], "b": [("x", 1)], "c": [("x", 1)]}
    m = min_rank_matching(adj, capacities={"x": 2})
    assert list(m.values()).count("x") == 2


def test_min_rank_cardinality_repair():
    # greedy-by-rank could strand an agent; repair must recover full cardinality
    adj = {"a": [("x", 1), ("y", 2)], "b": [("x", 1)]}
    m = min_rank_matching(adj)
    assert len(m) == 2
