from __future__ import annotations

from typing import Dict, List, Optional
from movement_engine.domain.models import Assignment


def wish_satisfaction_points(rank: int, max_rank: int = 50) -> float:
    """Configurable decreasing satisfaction. Rank 1 = 100, then linear decay to 0 at max_rank+1."""
    if rank < 1:
        return 0.0
    if rank > max_rank:
        return 0.0
    return 100.0 * (1.0 - (rank - 1) / max_rank)


def satisfaction_report(assignments: Dict[str, Assignment], max_rank: int = 50) -> dict:
    assigned = [a for a in assignments.values() if a.kind == "ASSIGNED"]
    n_assigned = len(assigned)
    n_total = len(assignments)
    buckets = {
        "voeu_1": 0,
        "voeu_2": 0,
        "voeu_3": 0,
        "voeu_4_5": 0,
        "voeu_6_10": 0,
        "voeu_11_plus": 0,
    }
    total_sat = 0.0
    ranks = []
    for a in assigned:
        r = a.wish_rank or 99
        ranks.append(r)
        total_sat += wish_satisfaction_points(r, max_rank)
        if r == 1:
            buckets["voeu_1"] += 1
        elif r == 2:
            buckets["voeu_2"] += 1
        elif r == 3:
            buckets["voeu_3"] += 1
        elif r <= 5:
            buckets["voeu_4_5"] += 1
        elif r <= 10:
            buckets["voeu_6_10"] += 1
        else:
            buckets["voeu_11_plus"] += 1

    avg_rank = sum(ranks) / len(ranks) if ranks else 0.0
    median = sorted(ranks)[len(ranks) // 2] if ranks else 0
    return {
        "professors": n_total,
        "assigned": n_assigned,
        "unassigned": sum(1 for a in assignments.values() if a.kind == "UNASSIGNED"),
        "stayed": sum(1 for a in assignments.values() if a.kind == "STAY"),
        "buckets": buckets,
        "first_wish_rate": round(100.0 * buckets["voeu_1"] / n_assigned, 2) if n_assigned else 0,
        "top3_rate": round(100.0 * (buckets["voeu_1"] + buckets["voeu_2"] + buckets["voeu_3"]) / n_assigned, 2) if n_assigned else 0,
        "avg_rank": round(avg_rank, 3),
        "median_rank": median,
        "total_satisfaction": round(total_sat, 1),
        "avg_satisfaction": round(total_sat / n_assigned, 2) if n_assigned else 0,
        "outside_wishes": 0,
    }


def format_satisfaction(rep: dict) -> str:
    b = rep["buckets"]
    lines = [
        "AFFECTA — RÉSULTAT",
        "",
        f"Professeurs                         {rep['professors']:,}",
        f"Affectés                             {rep['assigned']:,}",
        f"Non affectés                         {rep['unassigned']:,}",
        f"Restés sur poste                     {rep['stayed']:,}",
        "",
        "Satisfaction des vœux",
        f"  Vœu 1                              {b['voeu_1']:,}",
        f"  Vœu 2                              {b['voeu_2']:,}",
        f"  Vœu 3                              {b['voeu_3']:,}",
        f"  Vœu 4–5                            {b['voeu_4_5']:,}",
        f"  Vœu 6–10                           {b['voeu_6_10']:,}",
        f"  Vœu 11+                            {b['voeu_11_plus']:,}",
        "",
        f"  Taux vœu 1                         {rep['first_wish_rate']} %",
        f"  Taux top 3                         {rep['top3_rate']} %",
        f"  Rang moyen                         {rep['avg_rank']}",
        f"  Rang médian                        {rep['median_rank']}",
        f"  Satisfaction moyenne               {rep['avg_satisfaction']}/100",
        "",
        f"Affectation hors vœux                {rep['outside_wishes']}",
    ]
    return "\n".join(lines)
