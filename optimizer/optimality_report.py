"""
Strict separation of feasibility, cardinality optimality, and lexicographic optimality.
Never claim OPTIMAL without proof.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.optimizer.bounds import cardinality_bound, classify_cardinality
from movement_engine.optimizer.objective import ObjectivePolicy, DEFAULT_POLICY, quality_report
from movement_engine.optimizer.solver import optimize, greedy_baseline
from movement_engine.optimizer.counterexample import naive_sequential_no_release


@dataclass
class OptimalityReport:
    project: str
    version: str
    feasible: bool
    assigned: int
    eligibility_upper_bound: int
    cardinality_status: str  # PROVEN | UNKNOWN | INVALID
    first_wish: int
    first_wish_status: str   # PROVEN | UNKNOWN | NOT_COMPUTED
    avg_wish_rank: float
    lexicographic_status: str  # PROVEN | UNKNOWN | NOT_COMPUTED
    global_status: str
    method: str
    unknown_rules_note: str
    quality: dict
    bound_note: str

    def to_dict(self) -> dict:
        return asdict(self)


PROJECT_NAME = "AFFECTA"
ENGINE_VERSION = "0.9.0"


def build_optimality_report(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    *,
    policy: ObjectivePolicy = DEFAULT_POLICY,
    use_exhaustive_if_small: bool = True,
) -> OptimalityReport:
    bound_info = cardinality_bound(agents, posts, wishes)
    upper = bound_info["upper_bound"]

    sol = optimize(agents, posts, wishes, policy)
    assignments = sol["assignments"]
    q = quality_report(assignments, agents, policy)
    assigned = q["assigned"]

    # Feasibility: no double posts
    used = [a.post_id for a in assignments.values() if a.kind == "ASSIGNED" and a.post_id]
    feasible = len(used) == len(set(used)) and assigned <= upper

    card_status = classify_cardinality(assigned, upper)
    if card_status == "PROVEN_OPTIMAL":
        card_status = "PROVEN"
    elif card_status == "UNKNOWN":
        card_status = "UNKNOWN"

    # Lexicographic proof only when exhaustive
    method = sol.get("method") or sol.get("optimality", {}).get("method", "UNKNOWN")
    proven_opt = sol.get("optimality", {}).get("proven", False)

    if proven_opt and card_status == "PROVEN":
        # Exhaustive examined all feasible regulatory solutions
        first_status = "PROVEN"
        lex_status = "PROVEN"
        global_status = "LEXICOGRAPHIC_OPTIMAL"
    elif card_status == "PROVEN":
        first_status = "UNKNOWN"
        lex_status = "UNKNOWN"
        global_status = "CARDINALITY_OPTIMAL"
    else:
        first_status = "UNKNOWN"
        lex_status = "UNKNOWN"
        global_status = "FEASIBLE" if feasible else "INFEASIBLE"

    return OptimalityReport(
        project=PROJECT_NAME,
        version=ENGINE_VERSION,
        feasible=feasible,
        assigned=assigned,
        eligibility_upper_bound=upper,
        cardinality_status=card_status,
        first_wish=q["first_wish"],
        first_wish_status=first_status,
        avg_wish_rank=q["avg_wish_rank"],
        lexicographic_status=lex_status,
        global_status=global_status,
        method=method,
        unknown_rules_note="Eligibility bound only; full regulatory bound may be lower",
        quality=q,
        bound_note=bound_info.get("note", ""),
    )


def format_report(r: OptimalityReport) -> str:
    lines = [
        f"{r.project} v{r.version}",
        "",
        "CONTRACT",
        "  Maximize teachers assigned under hard regulatory constraints,",
        "  then maximize wish satisfaction lexicographically.",
        "",
        "OPTIMALITY REPORT",
        f"  Feasible                 {r.feasible}",
        "",
        "  Cardinality",
        f"    achieved               {r.assigned}",
        f"    eligibility_bound      {r.eligibility_upper_bound}",
        f"    status                 {r.cardinality_status}",
        "",
        "  First wishes",
        f"    achieved               {r.first_wish}",
        f"    status                 {r.first_wish_status}",
        "",
        f"  Average wish rank        {r.avg_wish_rank}",
        f"  Lexicographic status     {r.lexicographic_status}",
        "",
        f"  GLOBAL STATUS            {r.global_status}",
        f"  Method                   {r.method}",
        "",
        f"  Note: {r.bound_note}",
    ]
    return "\n".join(lines)
