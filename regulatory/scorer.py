from __future__ import annotations

from movement_engine.domain.models import Agent, CandidateScore, Post, Wish
from movement_engine.regulatory.registry import RuleRegistry

# REGULATORY_CONFIRMED — grille d'échelon Guadeloupe
ECHELON_POINTS = (
    0,   # 0 unused
    18,  # 1
    18,  # 2
    22,  # 3
    22,  # 4
    26,  # 5
    29,  # 6
    31,  # 7
    33,  # 8
    33,  # 9
    36,  # 10
    39,  # 11
)


def echelon_points(echelon: int) -> int:
    if 0 <= echelon < len(ECHELON_POINTS):
        return ECHELON_POINTS[echelon]
    if echelon > 11:
        return 39 + (echelon - 11) * 3  # conservative extension
    raise ValueError(f"Invalid echelon: {echelon}")


def score_candidate(
    agent: Agent,
    post: Post,
    wish: Wish,
    registry: RuleRegistry,
    *,
    sous_rank: int | None = None,
    tie_key: str | None = None,
) -> CandidateScore:
    points = echelon_points(agent.echelon)
    bonuses: list[str] = []

    # Priority rank (lower = better). Exact Guadeloupe codes still UNKNOWN;
    # we use a provisional ordering based on documented legal priorities.
    # DESIGN_DECISION: provisional numeric ranks pending official codes.
    priority_rank = 99

    if agent.mcs_points >= 800:
        priority_rank = 1
        bonuses.append(f"MCS_{agent.mcs_points}")
        points += agent.mcs_points
    elif agent.mcs_points >= 700:
        priority_rank = 2
        bonuses.append(f"MCS_{agent.mcs_points}")
        points += agent.mcs_points
    elif agent.mcs_points > 0:
        priority_rank = 3
        bonuses.append(f"MCS_{agent.mcs_points}")
        points += agent.mcs_points

    if agent.handicap_500:
        priority_rank = min(priority_rank, 10)
        points += registry.get("HANDICAP_500").amount
        bonuses.append("HANDICAP_500")
    elif agent.boe:
        priority_rank = min(priority_rank, 20)
        points += registry.get("BOE_100").amount
        bonuses.append("BOE_100")

    # RC / APC — non-cumulable, not on group wishes
    if agent.rc_points and agent.apc_points:
        return CandidateScore(
            agent.id, post.id, priority_rank, points, wish.rank,
            sous_rank, tie_key, tuple(bonuses), False, "RC_APC_NON_CUMULABLE",
        )

    if agent.rc_points:
        if wish.group or not wish.precise:
            return CandidateScore(
                agent.id, post.id, priority_rank, points, wish.rank,
                sous_rank, tie_key, tuple(bonuses), False, "RC_NOT_APPLICABLE_TO_GROUP",
            )
        points += agent.rc_points
        bonuses.append(f"RC_{agent.rc_points}")
        priority_rank = min(priority_rank, 30)

    elif agent.apc_points:
        if wish.group or not wish.precise:
            return CandidateScore(
                agent.id, post.id, priority_rank, points, wish.rank,
                sous_rank, tie_key, tuple(bonuses), False, "APC_NOT_APPLICABLE_TO_GROUP",
            )
        points += agent.apc_points
        bonuses.append(f"APC_{agent.apc_points}")
        priority_rank = min(priority_rank, 30)

    # Secondary bonuses
    if agent.medical_grave and wish.rank == 1 and wish.precise:
        points += registry.get("MED_GRAVE_30").amount
        bonuses.append("MED_GRAVE_30")

    if agent.children:
        pts = agent.children * registry.get("CHILD_2").amount
        points += pts
        bonuses.append(f"CHILD_2_X{agent.children}")

    if agent.unique_parental_authority:
        points += registry.get("UNIQUE_PARENT_50").amount
        bonuses.append("UNIQUE_PARENT_50")

    if agent.renewal_years > 0 and wish.rank == 1 and wish.precise:
        renewal = min(agent.renewal_years * 10, 90)
        points += renewal
        bonuses.append(f"RENEWAL_V1_{renewal}")

    if agent.aen_points:
        points += agent.aen_points
        bonuses.append(f"AEN_{agent.aen_points}")

    if agent.fidelity_points:
        points += agent.fidelity_points
        bonuses.append(f"FIDELITE_{agent.fidelity_points}")

    if agent.rep_points:
        points += agent.rep_points
        bonuses.append(f"REP_{agent.rep_points}")

    if agent.islands_points:
        points += agent.islands_points
        bonuses.append(f"ILES_{agent.islands_points}")

    if agent.reintegration_points:
        points += agent.reintegration_points
        bonuses.append(f"REINTEGRATION_{agent.reintegration_points}")

    return CandidateScore(
        agent.id, post.id, priority_rank, points, wish.rank,
        sous_rank, tie_key, tuple(bonuses), True, None,
    )
