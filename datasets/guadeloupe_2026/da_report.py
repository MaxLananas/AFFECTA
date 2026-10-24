"""
AFFECTA — Rapport comparatif sur données réelles Guadeloupe 2026.

Postes RÉELS (extraits des PDF officiels du mouvement). Agents et vœux SYNTHÉTIQUES
(les vœux réels ne figurent pas dans les sources). Compare l'ancien moteur glouton
et le solveur par acceptation différée, avec la PREUVE d'équité (stabilité).

Usage:
    python3 -m movement_engine.datasets.guadeloupe_2026.da_report            # affichage
    python3 -m movement_engine.datasets.guadeloupe_2026.da_report --json out.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from movement_engine.solver.engine import run_engine
from movement_engine.solver.deferred_acceptance import run_deferred_acceptance
from movement_engine.solver.pipeline import run_movement
from movement_engine.optimizer.objective import quality_report
from movement_engine.optimizer.satisfaction import satisfaction_report
from movement_engine.explain.stability import check_stability
from movement_engine.datasets.guadeloupe_2026.alpha_runner import (
    load_real_posts, generate_agents_wishes,
)

SEED = 20260811


def _run_one(name, solver, agents, posts, wishes):
    t = time.perf_counter()
    r = solver(agents, posts, wishes, campaign_seed=str(SEED))
    ms = (time.perf_counter() - t) * 1000
    q = quality_report(r.assignments, agents)
    sat = satisfaction_report(r.assignments)
    stab = check_stability(r.assignments, agents, posts, wishes, campaign_seed=str(SEED))
    return {
        "solver": name,
        "elapsed_ms": round(ms, 1),
        "assigned": q["assigned"],
        "stayed": q["stayed"],
        "unassigned": q["unassigned"],
        "first_wish": q["first_wish"],
        "first_wish_pct": q["first_wish_pct"],
        "top3_rate": sat["top3_rate"],
        "avg_wish_rank": q["avg_wish_rank"],
        "stable_no_justified_envy": stab.stable_modulo_policy,
        "stability_pairs_checked": stab.n_checked_pairs,
        "true_justified_envy": len(stab.witnesses),
        "pure_exchange_opportunities": len(stab.pure_exchange_opportunities),
        "cycles_detected": r.metrics["cycles_detected"],
    }


def build_report(n_agents: int = 1200, max_wishes: int = 20, seed: int = SEED) -> dict:
    posts = load_real_posts()
    agents, wishes = generate_agents_wishes(posts, n_agents, max_wishes, seed=seed)
    # Neither solver mutates posts/agents/wishes, so both can share the same inputs.
    def _da_pareto(ag, po, wi, campaign_seed):
        return run_movement(ag, po, wi, campaign_seed=campaign_seed,
                            pareto_exchanges=True, with_extension=False)

    rows = [
        _run_one("LEGACY_GREEDY", run_engine, agents, posts, wishes),
        _run_one("DEFERRED_ACCEPTANCE", run_deferred_acceptance, agents, posts, wishes),
        _run_one("DA+PARETO_EXCHANGE", _da_pareto, agents, posts, wishes),
    ]
    return {
        "dataset": "guadeloupe-2026 (postes réels, vœux synthétiques)",
        "n_agents": n_agents,
        "n_posts": len(posts),
        "max_wishes": max_wishes,
        "seed": seed,
        "notes": [
            "Postes RÉELS extraits des PDF officiels du mouvement Guadeloupe 2026.",
            "Vœux SYNTHÉTIQUES — pas de vraies préférences enseignantes dans les sources.",
            "Stabilité vérifiée par un module indépendant du solveur.",
        ],
        "results": rows,
    }


def _fmt(rep: dict) -> str:
    L = [
        "AFFECTA — Guadeloupe 2026 (postes réels, vœux synthétiques)",
        "=" * 64,
        f"Agents {rep['n_agents']:,}   Postes {rep['n_posts']:,}   Vœux max {rep['max_wishes']}",
        "",
        f"{'Solveur':<22}{'ms':>7}{'affectés':>10}{'vœu1':>7}{'top3%':>7}{'rang':>7}{'stable':>8}",
        "-" * 68,
    ]
    for r in rep["results"]:
        L.append(
            f"{r['solver']:<22}{r['elapsed_ms']:>7.0f}{r['assigned']:>10}"
            f"{r['first_wish']:>7}{r['top3_rate']:>7}{r['avg_wish_rank']:>7}"
            f"{('OUI' if r['stable_no_justified_envy'] else 'NON'):>8}"
        )
    L += ["", "« stable » = aucune envie justifiée (preuve indépendante)."]
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agents", type=int, default=1200)
    p.add_argument("--max-wishes", type=int, default=20)
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--json", type=str, default="")
    args = p.parse_args()
    rep = build_report(args.agents, args.max_wishes, args.seed)
    print(_fmt(rep))
    if args.json:
        Path(args.json).write_text(json.dumps(rep, indent=2, ensure_ascii=False))
        print(f"\nÉcrit: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
