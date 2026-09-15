"""
Cross-validation of the native C core against the pure-Python deferred-acceptance
reference. The native engine must produce a BYTE-IDENTICAL matching to
`run_deferred_acceptance(..., allow_pure_exchanges=True)` on every instance.

If the native library is not compiled (`native/libaffecta.so` absent), these tests
skip cleanly so the dependency-free suite still passes everywhere.
"""
from __future__ import annotations

from movement_engine.datasets.guadeloupe_2026.alpha_runner import (
    load_real_posts,
    generate_agents_wishes,
)
from movement_engine.solver.deferred_acceptance import run_deferred_acceptance
from movement_engine.solver import engine_native


def _skip_if_unbuilt():
    if not engine_native.native_available():
        print("SKIP test_native: native/libaffecta.so not built (run `make -C native`)")
        return True
    return False


def test_native_matches_python_reference():
    if _skip_if_unbuilt():
        return
    posts = load_real_posts()
    for seed in (1, 42, 20260811):
        for n in (200, 1200):
            agents, wishes = generate_agents_wishes(posts, n, 8, seed=seed)
            py = run_deferred_acceptance(
                agents, posts, wishes,
                allow_pure_exchanges=True, campaign_seed=str(seed),
            )
            na = engine_native.run_deferred_acceptance_native(
                agents, posts, wishes, campaign_seed=str(seed),
            )
            assert py.result_hash == na.result_hash, (
                f"native/python mismatch at seed={seed} n={n}: "
                f"{py.result_hash} != {na.result_hash}"
            )
            assert py.metrics["assigned"] == na.metrics["assigned"]


def test_native_assignments_identical_per_agent():
    if _skip_if_unbuilt():
        return
    posts = load_real_posts()
    agents, wishes = generate_agents_wishes(posts, 1200, 8, seed=7)
    py = run_deferred_acceptance(
        agents, posts, wishes, allow_pure_exchanges=True, campaign_seed="7"
    )
    na = engine_native.run_deferred_acceptance_native(
        agents, posts, wishes, campaign_seed="7"
    )
    for aid in py.assignments:
        assert py.assignments[aid].post_id == na.assignments[aid].post_id
        assert py.assignments[aid].kind == na.assignments[aid].kind
