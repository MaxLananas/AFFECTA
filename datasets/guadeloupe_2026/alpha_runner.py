"""
AFFECTA REAL-DATA ALPHA
Real Guadeloupe 2026 posts + synthetic agents/wishes.
PRODUCT_POLICY variants — not regulatory truth.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.optimizer.fast_hybrid import fast_hybrid
from movement_engine.optimizer.counterexample import naive_sequential_no_release
from movement_engine.solver.engine import run_engine
from movement_engine.optimizer.satisfaction import satisfaction_report
from movement_engine.optimizer.objective import ObjectivePolicy, ObjectiveKind, quality_report

DATA = Path(__file__).parent
SEED = 20260811


def load_real_posts() -> Dict[str, Post]:
    raw = json.loads((DATA / "posts.json").read_text(encoding="utf-8"))
    posts: Dict[str, Post] = {}
    for p in raw:
        pid = str(p["id"])
        vacant = int(p.get("vacants") or 0) > 0
        cap = max(1, int(p.get("capacity") or 1))
        # expand multi-capacity posts into unit posts for engine (capacity=1 each)
        # DESIGN_DECISION: unit decomposition for matching simplicity
        if cap == 1:
            posts[pid] = Post(
                id=pid,
                commune=p.get("commune") or "",
                support=p.get("nature_code") or "ECEL",
                vacant=vacant,
                capacity=1,
                holder_id=None if vacant else f"HOLD_{pid}",
            )
        else:
            for k in range(cap):
                uid = f"{pid}#{k}"
                # first 'vacants' units are vacant
                unit_vacant = k < int(p.get("vacants") or 0)
                posts[uid] = Post(
                    id=uid,
                    commune=p.get("commune") or "",
                    support=p.get("nature_code") or "ECEL",
                    vacant=unit_vacant,
                    capacity=1,
                    holder_id=None if unit_vacant else f"HOLD_{uid}",
                )
    return posts


def post_meta() -> Dict[str, dict]:
    """Original post metadata for establishment metrics."""
    raw = json.loads((DATA / "posts.json").read_text(encoding="utf-8"))
    return {str(p["id"]): p for p in raw}


def generate_agents_wishes(
    posts: Dict[str, Post],
    n_agents: int,
    max_wishes: int,
    seed: int = SEED,
) -> Tuple[Dict[str, Agent], Dict[str, List[Wish]]]:
    """
    Synthetic agents on real posts.
    DESIGN_DECISION: wishes are synthetic — not real 2026 teacher wishes.
    """
    rng = random.Random(seed)
    post_ids = list(posts.keys())
    # index by commune and support for realistic wish locality
    by_commune: Dict[str, List[str]] = defaultdict(list)
    by_support: Dict[str, List[str]] = defaultdict(list)
    for pid, p in posts.items():
        by_commune[p.commune].append(pid)
        by_support[p.support].append(pid)
    communes = [c for c, v in by_commune.items() if v]

    agents: Dict[str, Agent] = {}
    wishes: Dict[str, List[Wish]] = {}

    # Occupied unit posts: agent IS the holder so liberation chains work
    occupied = [pid for pid, p in posts.items() if not p.vacant]
    rng.shuffle(occupied)
    # Cap agents to available occupied + some without post
    n_with_post = min(n_agents, len(occupied))
    # Rewrite post.holder_id to agent ids for chain resolution
    # (posts are frozen dataclasses — rebuild mapping via mutable side channel)
    holder_map: Dict[str, str] = {}

    for i in range(n_agents):
        aid = f"A{i:05d}"
        current = occupied[i] if i < n_with_post else None
        if current:
            holder_map[current] = aid
        home_commune = posts[current].commune if current else rng.choice(communes)
        agents[aid] = Agent(
            id=aid,
            echelon=(i % 11) + 1,
            children=i % 4,
            handicap_500=(i % 200 == 0),
            boe=(i % 500 == 0),
            current_post_id=current,
            aen_points=30 + (i % 9) * 10,
            fidelity_points=(i % 5) * 10,
            participation="obligatoire" if (current is None or i % 7 == 0) else "volontaire",
            spouse_commune=home_commune if i % 5 == 0 else None,
        )

    # Rebuild posts with correct holder_id pointing to agents
    rebuilt: Dict[str, Post] = {}
    for pid, p in posts.items():
        hid = holder_map.get(pid)
        rebuilt[pid] = Post(
            id=p.id,
            commune=p.commune,
            support=p.support,
            vacant=p.vacant if hid is None else False,
            capacity=1,
            holder_id=hid,
        )
    posts.clear()
    posts.update(rebuilt)

    for i in range(n_agents):
        aid = f"A{i:05d}"
        current = agents[aid].current_post_id
        home_commune = posts[current].commune if current and current in posts else rng.choice(communes)
        n_w = rng.randint(max(1, max_wishes // 3), max_wishes)
        preferred = list(by_commune.get(home_commune, []))
        rng.shuffle(preferred)
        pool = preferred + [p for p in post_ids if p not in preferred]
        seen = set()
        chosen = []
        for pid in pool:
            if pid in seen:
                continue
            seen.add(pid)
            chosen.append(pid)
            if len(chosen) >= n_w:
                break
        while len(chosen) < n_w and len(seen) < len(post_ids):
            pid = rng.choice(post_ids)
            if pid not in seen:
                seen.add(pid)
                chosen.append(pid)
        wishes[aid] = [
            Wish(rank=r + 1, post_ids=(pid,), precise=True, group=False)
            for r, pid in enumerate(chosen)
        ]

    return agents, wishes


def establishment_metrics(
    assignments: Dict[str, Assignment],
    posts: Dict[str, Post],
    meta: Dict[str, dict],
) -> dict:
    """
    PRODUCT metrics — not regulatory.
    Understaffing thresholds are DESIGN_DECISION / PRODUCT_POLICY.
    """
    # unit post -> base id
    def base_id(pid: str) -> str:
        return pid.split("#")[0]

    filled = Counter()
    for a in assignments.values():
        if a.kind == "ASSIGNED" and a.post_id:
            filled[base_id(a.post_id)] += 1

    # also count STAY as filled
    for a in assignments.values():
        if a.kind == "STAY" and a.post_id:
            filled[base_id(a.post_id)] += 1

    total_capacity = 0
    total_filled = 0
    total_vacant_remaining = 0
    etab_deficit = 0
    etab_critical = 0  # filled/capacity < 0.5 when capacity>=2
    communes_deficit = set()
    by_nature_deficit: Counter = Counter()

    etabs: Dict[str, dict] = {}
    for pid, m in meta.items():
        cap = max(1, int(m.get("capacity") or 1))
        fill = filled.get(pid, 0)
        # holders not in agent set still "occupy" non-vacant units not taken by our agents
        # conservative: remaining capacity = cap - fill - (non-participating holders)
        # For alpha: treat fill vs capacity only on posts we model
        total_capacity += cap
        total_filled += min(fill, cap)
        remaining = max(0, cap - fill)
        total_vacant_remaining += remaining
        etab = m.get("etablissement") or pid
        if etab not in etabs:
            etabs[etab] = {"cap": 0, "fill": 0, "commune": m.get("commune"), "nature": m.get("nature_code")}
        etabs[etab]["cap"] += cap
        etabs[etab]["fill"] += min(fill, cap)

    for etab, info in etabs.items():
        if info["cap"] <= 0:
            continue
        ratio = info["fill"] / info["cap"]
        if ratio < 1.0 and info["cap"] - info["fill"] >= 1:
            etab_deficit += 1
            if info["commune"]:
                communes_deficit.add(info["commune"])
            if info["nature"]:
                by_nature_deficit[info["nature"]] += 1
        if info["cap"] >= 2 and ratio < 0.5:
            etab_critical += 1

    return {
        "posts_modeled": len(meta),
        "capacity_total": total_capacity,
        "filled": total_filled,
        "remaining_vacant_units": total_vacant_remaining,
        "fill_rate_pct": round(100.0 * total_filled / total_capacity, 2) if total_capacity else 0,
        "etablissements": len(etabs),
        "etablissements_sous_effectif": etab_deficit,
        "etablissements_critiques": etab_critical,
        "communes_touchees": len(communes_deficit),
        "top_natures_deficit": by_nature_deficit.most_common(8),
        # thresholds are PRODUCT_POLICY
        "threshold_note": "PRODUCT_POLICY: sous-effectif = remaining>=1; critique = fill/cap < 0.5 if cap>=2",
    }


# --- PRODUCT_POLICY definitions (not regulatory) ---

POLICY_TEACHER = ObjectivePolicy(
    objectives=(
        ObjectiveKind.MAXIMIZE_ASSIGNED,
        ObjectiveKind.MAXIMIZE_FIRST_WISH,
        ObjectiveKind.MAXIMIZE_TOP_K_WISHES,
        ObjectiveKind.MINIMIZE_TOTAL_WISH_RANK,
        ObjectiveKind.MAXIMIZE_STABILITY,
    ),
    top_k=3,
    version="product-teacher-v1",
)

POLICY_BALANCED = ObjectivePolicy(
    objectives=(
        ObjectiveKind.MAXIMIZE_ASSIGNED,
        ObjectiveKind.MAXIMIZE_FIRST_WISH,
        ObjectiveKind.MAXIMIZE_TOP_K_WISHES,
        ObjectiveKind.MINIMIZE_TOTAL_WISH_RANK,
        ObjectiveKind.MAXIMIZE_STABILITY,
    ),
    top_k=3,
    version="product-balanced-v1",
)

POLICY_COVERAGE = ObjectivePolicy(
    objectives=(
        ObjectiveKind.MAXIMIZE_ASSIGNED,
        ObjectiveKind.MAXIMIZE_STABILITY,
        ObjectiveKind.MAXIMIZE_FIRST_WISH,
        ObjectiveKind.MAXIMIZE_TOP_K_WISHES,
        ObjectiveKind.MINIMIZE_TOTAL_WISH_RANK,
    ),
    top_k=3,
    version="product-coverage-v1",
)


def run_solver(name: str, agents, posts, wishes, policy=POLICY_TEACHER):
    t0 = time.perf_counter()
    if name == "NAIVE":
        asn = naive_sequential_no_release(agents, posts, wishes)
        elapsed = (time.perf_counter() - t0) * 1000
        method = "NAIVE"
        opt_status = "UNKNOWN"
    elif name == "LIBERATION":
        r = run_engine(agents, posts, wishes)
        asn = r.assignments
        elapsed = (time.perf_counter() - t0) * 1000
        method = "LIBERATION"
        opt_status = "UNKNOWN"
    else:
        r = fast_hybrid(agents, posts, wishes, policy=policy)
        asn = r["assignments"]
        elapsed = r["elapsed_ms"]
        method = r["method"]
        opt_status = r["optimality"]["status"]
    sat = satisfaction_report(asn)
    return {
        "name": name,
        "method": method,
        "assignments": asn,
        "satisfaction": sat,
        "elapsed_ms": elapsed,
        "optimality_status": opt_status,
        "policy_version": policy.version if name.startswith("AFFECTA") else None,
    }


def format_row(n_agents, max_w, result, est):
    s = result["satisfaction"]
    b = s["buckets"]
    top3 = b["voeu_1"] + b["voeu_2"] + b["voeu_3"]
    return {
        "agents": n_agents,
        "max_wishes": max_w,
        "solver": result["name"],
        "assigned": s["assigned"],
        "voeu1": b["voeu_1"],
        "top3": top3,
        "avg_rank": s["avg_rank"],
        "sat": s["avg_satisfaction"],
        "ms": round(result["elapsed_ms"], 1),
        "fill_pct": est["fill_rate_pct"],
        "sous_effectif": est["etablissements_sous_effectif"],
        "critiques": est["etablissements_critiques"],
        "opt": result["optimality_status"],
    }


def main():
    print("=" * 72)
    print("AFFECTA REAL-DATA ALPHA — Guadeloupe 2026")
    print("Posts/groups from official PDFs. Wishes = SYNTHETIC (DESIGN_DECISION).")
    print("Policies = PRODUCT_POLICY. Optimality = UNKNOWN unless proven.")
    print("=" * 72)

    posts = load_real_posts()
    meta = post_meta()
    print(f"\nReal posts loaded: {len(posts)} unit posts from {len(meta)} source lines")
    print(f"Capacity total (source): {sum(max(1,int(m.get('capacity') or 1)) for m in meta.values())}")

    # --- Experiment 1: effect of max wishes ---
    print("\n" + "-" * 72)
    print("EXPERIMENT 1 — Effect of max wishes (AFFECTA_HYBRID, n≈1200 agents)")
    print("-" * 72)
    n_agents = min(1200, len(posts))
    print(f"{'MAX_W':>6} {'ASSIGNED':>8} {'VŒU1':>6} {'TOP3':>6} {'AVG':>6} {'SAT':>6} {'ms':>8} {'FILL%':>6} {'SOUS':>5} {'CRIT':>5}")
    wish_rows = []
    for max_w in [5, 10, 20, 30, 50]:
        agents, wishes = generate_agents_wishes(posts, n_agents, max_w, seed=SEED + max_w)
        res = run_solver("AFFECTA_HYBRID", agents, posts, wishes, POLICY_TEACHER)
        est = establishment_metrics(res["assignments"], posts, meta)
        row = format_row(n_agents, max_w, res, est)
        wish_rows.append(row)
        print(f"{max_w:>6} {row['assigned']:>8,} {row['voeu1']:>6,} {row['top3']:>6,} "
              f"{row['avg_rank']:>6.2f} {row['sat']:>6.1f} {row['ms']:>8.0f} "
              f"{row['fill_pct']:>6.1f} {row['sous_effectif']:>5} {row['critiques']:>5}")

    # --- Experiment 2: 3 solvers comparison ---
    print("\n" + "-" * 72)
    print("EXPERIMENT 2 — NAIVE / LIBERATION / AFFECTA_HYBRID (max_wishes=20)")
    print("-" * 72)
    agents, wishes = generate_agents_wishes(posts, n_agents, 20, seed=SEED + 20)
    print(f"{'SOLVER':<16} {'ASSIGNED':>8} {'VŒU1':>6} {'TOP3':>6} {'AVG':>6} {'ms':>8} {'FILL%':>6} {'SOUS':>5}")
    solver_rows = []
    for sname in ["NAIVE", "LIBERATION", "AFFECTA_HYBRID"]:
        res = run_solver(sname, agents, posts, wishes, POLICY_TEACHER)
        est = establishment_metrics(res["assignments"], posts, meta)
        row = format_row(n_agents, 20, res, est)
        solver_rows.append(row)
        print(f"{sname:<16} {row['assigned']:>8,} {row['voeu1']:>6,} {row['top3']:>6,} "
              f"{row['avg_rank']:>6.2f} {row['ms']:>8.0f} {row['fill_pct']:>6.1f} {row['sous_effectif']:>5}")

    # --- Experiment 3: policy comparison (same data) ---
    print("\n" + "-" * 72)
    print("EXPERIMENT 3 — PRODUCT_POLICY comparison (same agents/wishes)")
    print("TEACHER_FIRST / BALANCED / COVERAGE_FIRST — all PRODUCT_POLICY")
    print("-" * 72)
    agents, wishes = generate_agents_wishes(posts, n_agents, 20, seed=SEED + 99)
    print(f"{'POLICY':<18} {'ASSIGNED':>8} {'VŒU1':>6} {'TOP3':>6} {'AVG':>6} {'FILL%':>6} {'SOUS':>5} {'CRIT':>5} {'ms':>7}")
    policy_rows = []
    for pname, pol in [
        ("TEACHER_FIRST", POLICY_TEACHER),
        ("BALANCED", POLICY_BALANCED),
        ("COVERAGE_FIRST", POLICY_COVERAGE),
    ]:
        res = run_solver("AFFECTA_HYBRID", agents, posts, wishes, pol)
        res["name"] = pname
        est = establishment_metrics(res["assignments"], posts, meta)
        row = format_row(n_agents, 20, res, est)
        policy_rows.append((row, est))
        print(f"{pname:<18} {row['assigned']:>8,} {row['voeu1']:>6,} {row['top3']:>6,} "
              f"{row['avg_rank']:>6.2f} {row['fill_pct']:>6.1f} {row['sous_effectif']:>5} "
              f"{row['critiques']:>5} {row['ms']:>7.0f}")

    # detailed establishment report for TEACHER
    print("\n" + "-" * 72)
    print("ÉTABLISSEMENTS (AFFECTA_HYBRID / TEACHER_FIRST, max_w=20)")
    print("-" * 72)
    res = run_solver("AFFECTA_HYBRID", agents, posts, wishes, POLICY_TEACHER)
    est = establishment_metrics(res["assignments"], posts, meta)
    print(f"  Postes source (lignes)              {est['posts_modeled']:,}")
    print(f"  Capacité totale                     {est['capacity_total']:,}")
    print(f"  Unités pourvues (modèle)            {est['filled']:,}")
    print(f"  Unités restantes                    {est['remaining_vacant_units']:,}")
    print(f"  Taux de remplissage                 {est['fill_rate_pct']} %")
    print(f"  Établissements                      {est['etablissements']:,}")
    print(f"  Établissements sous-effectif        {est['etablissements_sous_effectif']:,}")
    print(f"  Établissements critiques            {est['etablissements_critiques']:,}")
    print(f"  Communes touchées                   {est['communes_touchees']:,}")
    print(f"  Note: {est['threshold_note']}")

    # save report
    report = {
        "dataset": "guadeloupe-2026-alpha",
        "seed": SEED,
        "n_agents": n_agents,
        "notes": [
            "Wishes are SYNTHETIC — not real teacher preferences",
            "Policies are PRODUCT_POLICY — not official movement rules",
            "OPTIMALITY remains UNKNOWN",
            "Understaffing thresholds are DESIGN_DECISION",
        ],
        "wish_effect": wish_rows,
        "solver_comparison": solver_rows,
        "policy_comparison": [r for r, _ in policy_rows],
        "establishment_teacher": est,
    }
    out = DATA / "alpha_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport saved: {out}")
    print("\nAFFECTA REAL-DATA ALPHA complete.")


if __name__ == "__main__":
    main()
