"""
AFFECTA — real differentiation of PRODUCT policies + controlled divergence fixture.
"""
from __future__ import annotations

import json
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.optimizer.policy_hybrid import ProductPolicy, policy_hybrid
from movement_engine.optimizer.satisfaction import satisfaction_report
from movement_engine.solver.engine import run_engine
from movement_engine.optimizer.counterexample import naive_sequential_no_release
from movement_engine.explain.why_not import why_not_wish

DATA = Path(__file__).parent
SEED = 20260811


def load_unit_posts() -> Tuple[Dict[str, Post], Dict[str, dict]]:
    raw = json.loads((DATA / "posts.json").read_text(encoding="utf-8"))
    posts: Dict[str, Post] = {}
    meta = {}
    for p in raw:
        pid = str(p["id"])
        meta[pid] = p
        cap = max(1, int(p.get("capacity") or 1))
        vac = int(p.get("vacants") or 0)
        for k in range(cap):
            uid = f"{pid}#{k}" if cap > 1 else pid
            unit_vacant = k < vac
            posts[uid] = Post(
                id=uid,
                commune=p.get("commune") or "",
                support=p.get("nature_code") or "ECEL",
                vacant=unit_vacant,
                capacity=1,
                holder_id=None if unit_vacant else f"HOLD_{uid}",
            )
    return posts, meta


def attach_agents_as_holders(
    posts: Dict[str, Post],
    n_agents: int,
    max_wishes: int,
    seed: int,
) -> Tuple[Dict[str, Agent], Dict[str, List[Wish]], Dict[str, Post]]:
    rng = random.Random(seed)
    occupied = [pid for pid, p in posts.items() if not p.vacant]
    rng.shuffle(occupied)
    n_with = min(n_agents, len(occupied))
    by_commune: Dict[str, List[str]] = defaultdict(list)
    for pid, p in posts.items():
        by_commune[p.commune].append(pid)
    communes = [c for c, v in by_commune.items() if v]
    post_ids = list(posts.keys())

    agents: Dict[str, Agent] = {}
    wishes: Dict[str, List[Wish]] = {}
    holder_map: Dict[str, str] = {}

    for i in range(n_agents):
        aid = f"A{i:05d}"
        current = occupied[i] if i < n_with else None
        if current:
            holder_map[current] = aid
        home = posts[current].commune if current else rng.choice(communes)
        agents[aid] = Agent(
            id=aid,
            echelon=(i % 11) + 1,
            children=i % 4,
            handicap_500=(i % 200 == 0),
            current_post_id=current,
            aen_points=30 + (i % 9) * 10,
            fidelity_points=(i % 5) * 10,
            participation="obligatoire" if (current is None or i % 7 == 0) else "volontaire",
            spouse_commune=home if i % 5 == 0 else None,
        )

    rebuilt = {}
    for pid, p in posts.items():
        hid = holder_map.get(pid)
        rebuilt[pid] = Post(
            id=p.id, commune=p.commune, support=p.support,
            vacant=False if hid else p.vacant,
            capacity=1, holder_id=hid,
        )
    posts = rebuilt

    for i in range(n_agents):
        aid = f"A{i:05d}"
        current = agents[aid].current_post_id
        home = posts[current].commune if current and current in posts else rng.choice(communes)
        n_w = rng.randint(max(1, max_wishes // 3), max_wishes)
        preferred = list(by_commune.get(home, []))
        rng.shuffle(preferred)
        pool = preferred + [p for p in post_ids if p not in preferred]
        seen, chosen = set(), []
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
            Wish(rank=r + 1, post_ids=(pid,), precise=True)
            for r, pid in enumerate(chosen)
        ]
    return agents, wishes, posts


def establishment_report(
    assignments: Dict[str, Assignment],
    posts: Dict[str, Post],
    meta: Dict[str, dict],
) -> dict:
    def base(pid: str) -> str:
        return pid.split("#")[0]

    filled = Counter()
    for a in assignments.values():
        if a.kind in ("ASSIGNED", "STAY") and a.post_id:
            filled[base(a.post_id)] += 1

    etabs: Dict[str, dict] = {}
    for pid, m in meta.items():
        cap = max(1, int(m.get("capacity") or 1))
        fill = filled.get(pid, 0)
        etab = m.get("etablissement") or pid
        if etab not in etabs:
            etabs[etab] = {
                "cap": 0, "fill": 0,
                "commune": m.get("commune") or "?",
                "nature": m.get("nature_code") or "?",
            }
        etabs[etab]["cap"] += cap
        etabs[etab]["fill"] += min(fill, cap)

    sous = crit = empty = 0
    worst_deficit = 0
    by_commune: Counter = Counter()
    for e, info in etabs.items():
        deficit = info["cap"] - info["fill"]
        if deficit > worst_deficit:
            worst_deficit = deficit
        if deficit >= 1:
            sous += 1
            by_commune[info["commune"]] += 1
        if info["fill"] == 0 and info["cap"] >= 1:
            empty += 1
        if info["cap"] >= 2 and info["fill"] / info["cap"] < 0.5:
            crit += 1

    total_cap = sum(i["cap"] for i in etabs.values())
    total_fill = sum(i["fill"] for i in etabs.values())
    return {
        "capacity": total_cap,
        "filled": total_fill,
        "remaining_vacant": total_cap - total_fill,
        "fill_pct": round(100.0 * total_fill / total_cap, 2) if total_cap else 0,
        "etablissements": len(etabs),
        "sous_effectif": sous,
        "critiques": crit,
        "completement_vides": empty,
        "pire_deficit": worst_deficit,
        "communes_sous_effectif": dict(by_commune.most_common(10)),
        "nb_communes_touchees": len(by_commune),
    }


def controlled_divergence_fixture():
    """
    DESIGN_DECISION fixture: TEACHER vs COVERAGE must diverge.

    Etablissement critique « Désirade Unique » = 2 postes (CRIT#0, CRIT#1).
    Tant qu'ils ne sont pas tous deux pourvus, ils restent critiques.

    A1 : vœu1 = POPULAIRE (PAP), vœu2 = CRIT#0
    A2 : vœu1 = POPULAIRE seulement
    A3 : vœu1 = CRIT#1, vœu2 = AUTRE

    TEACHER_FIRST  → maximise vœux 1 : A1 ou A2 sur POPULAIRE, risque de laisser un CRIT vide.
    COVERAGE_FIRST → accepte qu'A1 prenne CRIT#0 (rang 2) pour couvrir le critique.
    """
    posts = {
        "POP": Post("POP", "Pointe-à-Pitre", "ECEL", vacant=True),
        "CRIT#0": Post("CRIT#0", "Désirade", "ECEL", vacant=True),
        "CRIT#1": Post("CRIT#1", "Désirade", "ECEL", vacant=True),
        "AUTRE": Post("AUTRE", "Basse-Terre", "ECEL", vacant=True),
    }
    agents = {
        "A1": Agent("A1", echelon=8, aen_points=80),   # better bareme → wins POP under teacher
        "A2": Agent("A2", echelon=3, aen_points=20),
        "A3": Agent("A3", echelon=5, aen_points=40),
    }
    wishes = {
        "A1": [Wish(1, ("POP",)), Wish(2, ("CRIT#0",)), Wish(3, ("AUTRE",))],
        "A2": [Wish(1, ("POP",)), Wish(2, ("AUTRE",))],
        "A3": [Wish(1, ("CRIT#1",)), Wish(2, ("AUTRE",))],
    }
    meta = {
        "POP": {"capacity": 1, "etablissement": "Ecole Centrale PAP", "commune": "Pointe-à-Pitre", "nature_code": "ECEL"},
        "CRIT": {"capacity": 2, "etablissement": "Ecole Désirade Unique", "commune": "Désirade", "nature_code": "ECEL"},
        "AUTRE": {"capacity": 1, "etablissement": "Ecole BT", "commune": "Basse-Terre", "nature_code": "ECEL"},
    }
    return agents, posts, wishes, meta


def fmt_policy_row(name, sat, est, ms, hash_):
    b = sat["buckets"]
    ranks = []
    return {
        "policy": name,
        "assigned": sat["assigned"],
        "unassigned": sat["unassigned"],
        "voeu1": b["voeu_1"],
        "top3": b["voeu_1"] + b["voeu_2"] + b["voeu_3"],
        "avg_rank": sat["avg_rank"],
        "median_rank": sat["median_rank"],
        "sat": sat["avg_satisfaction"],
        "remaining_vacant": est["remaining_vacant"],
        "sous_effectif": est["sous_effectif"],
        "critiques": est["critiques"],
        "vides": est["completement_vides"],
        "pire_deficit": est["pire_deficit"],
        "ms": round(ms, 1),
        "hash": hash_,
    }


def teacher_dossier(
    agent_id: str,
    agents, posts, wishes, assignments,
    post_labels: Dict[str, str],
) -> str:
    asn = assignments[agent_id]
    my_wishes = wishes.get(agent_id, [])
    lines = []
    lines.append("=" * 56)
    lines.append(f"DOSSIER D'AFFECTATION — {agent_id}")
    lines.append("=" * 56)
    if asn.kind == "ASSIGNED":
        label = post_labels.get(asn.post_id, asn.post_id)
        lines.append(f"Résultat          : affecté(e)")
        lines.append(f"Poste obtenu      : {label}")
        lines.append(f"Rang de vœu       : n°{asn.wish_rank}")
    elif asn.kind == "STAY":
        lines.append(f"Résultat          : maintenu(e) sur votre poste actuel")
        lines.append(f"Poste             : {asn.post_id}")
    else:
        lines.append(f"Résultat          : non affecté(e) dans ce mouvement")

    lines.append("")
    lines.append("Vos vœux et ce qu'il en est devenu :")
    for w in sorted(my_wishes, key=lambda x: x.rank)[:8]:
        pid = w.post_ids[0] if w.post_ids else "?"
        label = post_labels.get(pid, pid)
        if asn.kind == "ASSIGNED" and asn.post_id == pid:
            status = "→ OBTENU"
        elif asn.kind == "ASSIGNED" and asn.wish_rank and w.rank < asn.wish_rank:
            status = "→ non obtenu (voir motif)"
        elif asn.kind == "ASSIGNED" and asn.wish_rank and w.rank > asn.wish_rank:
            status = "→ non examiné (vœu mieux classé déjà obtenu)"
        else:
            status = "→ non obtenu"
        lines.append(f"  Vœu n°{w.rank:<3}  {label[:42]:<42} {status}")

    # explain first unsatisfied better wish
    if asn.kind == "ASSIGNED" and asn.wish_rank and asn.wish_rank > 1:
        target_rank = 1
        info = why_not_wish(agent_id, target_rank, agents, posts, wishes, assignments)
        lines.append("")
        lines.append(f"Pourquoi pas votre vœu n°{target_rank} ?")
        for e in info["explanations"][:3]:
            if e.get("reason") == "CONCURRENT_PRIORITE_OU_BAREME_SUPERIEUR":
                lines.append(f"  Le poste demandé a été attribué à un autre candidat.")
                lines.append(f"  Concurrent          : {e.get('concurrent')}")
                lines.append(f"  Votre priorité      : {e.get('votre_priorite')}")
                lines.append(f"  Priorité concurrent : {e.get('concurrent_priorite')}")
                lines.append(f"  Votre barème        : {e.get('votre_bareme')} pts")
                lines.append(f"  Barème concurrent   : {e.get('concurrent_bareme')} pts")
            elif e.get("reason") == "POST_NOT_LIBERATED":
                lines.append(f"  Le poste n'a pas été libéré par son titulaire.")
            elif e.get("reason") == "POST_AVAILABLE_BUT_NOT_ASSIGNED":
                lines.append(f"  Le poste était disponible mais une autre combinaison")
                lines.append(f"  d'affectations a été retenue (ordre des vœux / couverture).")
            else:
                lines.append(f"  Motif : {e.get('reason')}")
    lines.append("")
    return "\n".join(lines)


def main():
    print("=" * 72)
    print("AFFECTA — POLITIQUES RÉELLEMENT DISTINCTES + FIXTURE DE DIVERGENCE")
    print("PRODUCT_POLICY only. OPTIMALITY = UNKNOWN.")
    print("=" * 72)

    # --- Controlled fixture ---
    print("\n--- FIXTURE CONTRÔLÉE (divergence obligatoire) ---")
    agents_f, posts_f, wishes_f, meta_f = controlled_divergence_fixture()
    print(f"{'POLICY':<16} {'ASSIGNED':>8} {'VŒU1':>5} {'AVG':>5}  Affectations")
    fixture_results = {}
    for pol in ProductPolicy:
        r = policy_hybrid(agents_f, posts_f, wishes_f, pol)
        sat = r["satisfaction"]
        asn = r["assignments"]
        detail = ", ".join(
            f"{a}→{asn[a].post_id}(r{asn[a].wish_rank})"
            for a in sorted(asn) if asn[a].kind == "ASSIGNED"
        )
        fixture_results[pol.value] = {
            "assigned": sat["assigned"],
            "voeu1": sat["buckets"]["voeu_1"],
            "avg": sat["avg_rank"],
            "detail": detail,
            "hash": r["result_hash"],
        }
        print(f"{pol.value:<16} {sat['assigned']:>8} {sat['buckets']['voeu_1']:>5} "
              f"{sat['avg_rank']:>5.2f}  {detail}")

    diverged = len({fixture_results[p]["hash"] for p in fixture_results}) > 1
    print(f"\nDivergence entre politiques : {'OUI' if diverged else 'NON'}")

    # --- Real data policy comparison ---
    print("\n--- COMPARAISON SUR DONNÉES RÉELLES Guadeloupe 2026 ---")
    base_posts, meta = load_unit_posts()
    n_agents = 1200
    max_w = 20
    agents, wishes, posts = attach_agents_as_holders(base_posts, n_agents, max_w, SEED + 20)

    rows = []
    print(f"{'POLICY':<16} {'ASS':>5} {'UNASS':>5} {'V1':>5} {'TOP3':>5} {'AVG':>5} "
          f"{'SOUS':>5} {'CRIT':>5} {'VIDE':>5} {'PIR':>4} {'ms':>6}")
    prev_asn = None
    for pol in ProductPolicy:
        r = policy_hybrid(agents, posts, wishes, pol)
        sat = r["satisfaction"]
        est = establishment_report(r["assignments"], posts, meta)
        row = fmt_policy_row(pol.value, sat, est, r["elapsed_ms"], r["result_hash"])
        # stability vs previous policy result
        if prev_asn is not None:
            same = sum(
                1 for a in agents
                if prev_asn[a].post_id == r["assignments"][a].post_id
                and prev_asn[a].kind == r["assignments"][a].kind
            )
            row["stability_vs_prev_pct"] = round(100.0 * same / len(agents), 1)
        else:
            row["stability_vs_prev_pct"] = 100.0
        prev_asn = r["assignments"]
        rows.append(row)
        print(f"{pol.value:<16} {row['assigned']:>5} {row['unassigned']:>5} {row['voeu1']:>5} "
              f"{row['top3']:>5} {row['avg_rank']:>5.2f} {row['sous_effectif']:>5} "
              f"{row['critiques']:>5} {row['vides']:>5} {row['pire_deficit']:>4} {row['ms']:>6.0f}")

    # Diffs
    print("\nDifférences vs TEACHER_FIRST :")
    base = rows[0]
    for row in rows[1:]:
        print(f"  {row['policy']}:")
        print(f"    Δ assigned={row['assigned']-base['assigned']:+d}  "
              f"Δ voeu1={row['voeu1']-base['voeu1']:+d}  "
              f"Δ top3={row['top3']-base['top3']:+d}  "
              f"Δ avg_rank={row['avg_rank']-base['avg_rank']:+.2f}")
        print(f"    Δ sous_effectif={row['sous_effectif']-base['sous_effectif']:+d}  "
              f"Δ critiques={row['critiques']-base['critiques']:+d}  "
              f"Δ vides={row['vides']-base['vides']:+d}")

    # --- Wish curve 5..100 ---
    print("\n--- COURBE DU NOMBRE DE VŒUX (TEACHER_FIRST) ---")
    print(f"{'MAX_W':>6} {'ASS':>5} {'RATE':>6} {'V1':>5} {'TOP3':>5} {'AVG':>5} {'MED':>4} {'WORST':>5} {'ms':>6}")
    wish_curve = []
    for max_w in [5, 10, 20, 30, 50, 75, 100]:
        ag, wi, po = attach_agents_as_holders(
            {k: v for k, v in load_unit_posts()[0].items()},
            n_agents, max_w, SEED + max_w,
        )
        r = policy_hybrid(ag, po, wi, ProductPolicy.TEACHER_FIRST)
        sat = r["satisfaction"]
        ranks = [
            a.wish_rank for a in r["assignments"].values()
            if a.kind == "ASSIGNED" and a.wish_rank
        ]
        worst = max(ranks) if ranks else 0
        rate = round(100.0 * sat["assigned"] / n_agents, 1)
        wish_curve.append({
            "max_w": max_w, "assigned": sat["assigned"], "rate": rate,
            "voeu1": sat["buckets"]["voeu_1"],
            "top3": sat["buckets"]["voeu_1"] + sat["buckets"]["voeu_2"] + sat["buckets"]["voeu_3"],
            "avg": sat["avg_rank"], "median": sat["median_rank"],
            "worst": worst, "ms": round(r["elapsed_ms"], 1),
        })
        print(f"{max_w:>6} {sat['assigned']:>5} {rate:>5.1f}% {sat['buckets']['voeu_1']:>5} "
              f"{sat['buckets']['voeu_1']+sat['buckets']['voeu_2']+sat['buckets']['voeu_3']:>5} "
              f"{sat['avg_rank']:>5.2f} {sat['median_rank']:>4} {worst:>5} {r['elapsed_ms']:>6.0f}")

    # --- Scale benchmark ---
    print("\n--- SCALABILITÉ (TEACHER_FIRST, max_w=12) ---")
    print(f"{'N':>6} {'ASS':>6} {'V1':>6} {'ms':>8}")
    scale_rows = []
    for n in [500, 1500, 5000, 10000]:
        # synthetic scale on unit posts sampled
        ag, wi, po = attach_agents_as_holders(
            {k: v for k, v in load_unit_posts()[0].items()},
            min(n, 2400), 12, SEED + n,
        )
        # if n > available holders, generator caps — for large N use pure synthetic
        if n > 2500:
            from movement_engine.domain.models import Agent as Ag, Post as Po, Wish as Wi
            rng = random.Random(SEED + n)
            po, ag, wi = {}, {}, {}
            for i in range(int(n * 1.5)):
                po[f"X{i:05d}"] = Po(f"X{i:05d}", f"C{i%40}", "ECEL", vacant=rng.random() > 0.35)
            for i in range(n):
                ag[f"A{i:05d}"] = Ag(f"A{i:05d}", echelon=(i % 11) + 1, aen_points=40)
                pids = [f"X{rng.randint(0, int(n*1.5)-1):05d}" for _ in range(12)]
                pids = list(dict.fromkeys(pids))
                wi[f"A{i:05d}"] = [Wi(r + 1, (p,)) for r, p in enumerate(pids)]
        t0 = time.perf_counter()
        r = policy_hybrid(ag, po, wi, ProductPolicy.TEACHER_FIRST)
        ms = (time.perf_counter() - t0) * 1000
        sat = r["satisfaction"]
        scale_rows.append({"n": n, "assigned": sat["assigned"], "voeu1": sat["buckets"]["voeu_1"], "ms": round(ms, 1)})
        print(f"{n:>6} {sat['assigned']:>6} {sat['buckets']['voeu_1']:>6} {ms:>8.0f}")

    # --- 10 Why-not dossiers ---
    print("\n--- 10 DOSSIERS WHY-NOT (lisibles professeur) ---")
    ag, wi, po = attach_agents_as_holders(
        {k: v for k, v in load_unit_posts()[0].items()},
        1200, 20, SEED + 20,
    )
    r = policy_hybrid(ag, po, wi, ProductPolicy.TEACHER_FIRST)
    asn = r["assignments"]
    # pick interesting cases: got rank>1, or unassigned
    interesting = []
    for aid, a in asn.items():
        if a.kind == "ASSIGNED" and a.wish_rank and a.wish_rank > 1:
            interesting.append(aid)
        elif a.kind == "UNASSIGNED":
            interesting.append(aid)
    interesting = sorted(interesting)[:10]
    post_labels = {}
    for pid, p in po.items():
        post_labels[pid] = f"{p.commune} / {p.support} ({pid})"

    dossiers = []
    for aid in interesting:
        text = teacher_dossier(aid, ag, po, wi, asn, post_labels)
        dossiers.append(text)
        print(text)

    report = {
        "fixture_divergence": fixture_results,
        "fixture_diverged": diverged,
        "policy_comparison": rows,
        "wish_curve": wish_curve,
        "scale": scale_rows,
        "notes": [
            "All policies are PRODUCT_POLICY / DESIGN_DECISION",
            "OPTIMALITY remains UNKNOWN",
            "Wishes are synthetic",
            "Coverage thresholds are design decisions",
        ],
    }
    out = DATA / "policy_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "dossiers_why_not.txt").write_text("\n".join(dossiers), encoding="utf-8")
    print(f"\nReports: {out}")
    print(f"Dossiers: {DATA / 'dossiers_why_not.txt'}")


if __name__ == "__main__":
    main()
