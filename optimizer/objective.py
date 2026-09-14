"""
Lexicographic objective policy — versioned, explicit, testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from movement_engine.domain.models import Assignment


class ObjectiveKind(str, Enum):
    MAXIMIZE_ASSIGNED = "MAXIMIZE_ASSIGNED"
    MAXIMIZE_FIRST_WISH = "MAXIMIZE_FIRST_WISH"
    MAXIMIZE_TOP_K_WISHES = "MAXIMIZE_TOP_K_WISHES"
    MINIMIZE_TOTAL_WISH_RANK = "MINIMIZE_TOTAL_WISH_RANK"
    MINIMIZE_UNASSIGNED = "MINIMIZE_UNASSIGNED"
    MAXIMIZE_STABILITY = "MAXIMIZE_STABILITY"


@dataclass(frozen=True)
class ObjectivePolicy:
    """Order is strict: earlier objectives dominate later ones."""
    objectives: Tuple[ObjectiveKind, ...]
    top_k: int = 3
    version: str = "obj-v1"

    def score_vector(self, assignments: Dict[str, Assignment], agents: dict) -> Tuple:
        """Return a tuple to maximize (or minimize components negated)."""
        assigned = sum(1 for a in assignments.values() if a.kind == "ASSIGNED")
        first = sum(1 for a in assignments.values() if a.kind == "ASSIGNED" and a.wish_rank == 1)
        topk = sum(1 for a in assignments.values() if a.kind == "ASSIGNED" and a.wish_rank and a.wish_rank <= self.top_k)
        total_rank = sum(a.wish_rank or 0 for a in assignments.values() if a.kind == "ASSIGNED")
        unassigned = sum(1 for a in assignments.values() if a.kind == "UNASSIGNED")
        # stability: agents who stayed on current post
        stability = sum(
            1 for aid, a in assignments.items()
            if a.kind == "STAY" or (
                a.kind == "ASSIGNED" and agents.get(aid)
                and getattr(agents[aid], "current_post_id", None) == a.post_id
            )
        )
        vec = []
        for obj in self.objectives:
            if obj == ObjectiveKind.MAXIMIZE_ASSIGNED:
                vec.append(assigned)
            elif obj == ObjectiveKind.MAXIMIZE_FIRST_WISH:
                vec.append(first)
            elif obj == ObjectiveKind.MAXIMIZE_TOP_K_WISHES:
                vec.append(topk)
            elif obj == ObjectiveKind.MINIMIZE_TOTAL_WISH_RANK:
                vec.append(-total_rank)  # maximize negative = minimize
            elif obj == ObjectiveKind.MINIMIZE_UNASSIGNED:
                vec.append(-unassigned)
            elif obj == ObjectiveKind.MAXIMIZE_STABILITY:
                vec.append(stability)
        return tuple(vec)


DEFAULT_POLICY = ObjectivePolicy(
    objectives=(
        ObjectiveKind.MAXIMIZE_ASSIGNED,
        ObjectiveKind.MAXIMIZE_FIRST_WISH,
        ObjectiveKind.MAXIMIZE_TOP_K_WISHES,
        ObjectiveKind.MINIMIZE_TOTAL_WISH_RANK,
        ObjectiveKind.MINIMIZE_UNASSIGNED,
        ObjectiveKind.MAXIMIZE_STABILITY,
    )
)


def wish_distribution(assignments: Dict[str, Assignment]) -> Dict[str, int]:
    dist: Dict[str, int] = {}
    for a in assignments.values():
        if a.kind == "ASSIGNED" and a.wish_rank:
            key = f"voeu_{a.wish_rank}"
            dist[key] = dist.get(key, 0) + 1
    return dist


def quality_report(assignments: Dict[str, Assignment], agents: dict, policy: ObjectivePolicy = DEFAULT_POLICY) -> dict:
    assigned = sum(1 for a in assignments.values() if a.kind == "ASSIGNED")
    stayed = sum(1 for a in assignments.values() if a.kind == "STAY")
    unassigned = sum(1 for a in assignments.values() if a.kind == "UNASSIGNED")
    n = len(assignments)
    ranks = [a.wish_rank for a in assignments.values() if a.kind == "ASSIGNED" and a.wish_rank]
    avg_rank = sum(ranks) / len(ranks) if ranks else 0.0
    first = sum(1 for r in ranks if r == 1)
    return {
        "assigned": assigned,
        "stayed": stayed,
        "unassigned": unassigned,
        "rate": round(100.0 * assigned / n, 2) if n else 0,
        "first_wish": first,
        "first_wish_pct": round(100.0 * first / assigned, 2) if assigned else 0,
        "avg_wish_rank": round(avg_rank, 3),
        "distribution": wish_distribution(assignments),
        "objective_vector": policy.score_vector(assignments, agents),
        "policy_version": policy.version,
    }
