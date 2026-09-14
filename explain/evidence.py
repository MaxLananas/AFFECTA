"""
Decision evidence: for each assignment, list competitors and why they lost.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

from movement_engine.domain.models import Agent, Assignment, CandidateScore, Post, Wish
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import RuleRegistry, guadeloupe_registry


@dataclass
class CompetitorEvidence:
    agent: str
    eligible: bool
    priority: Optional[int] = None
    bareme: Optional[int] = None
    wish_rank: Optional[int] = None
    comparison: Optional[str] = None  # WINNER_HIGHER_PRIORITY | WINNER_HIGHER_BAREME | ...
    reason: Optional[str] = None      # if not eligible


@dataclass
class DecisionEvidence:
    agent: str
    post: str
    priority: int
    bareme: int
    wish_rank: int
    sous_rank: Optional[int]
    tie_break: Optional[str]
    bonuses: List[str]
    competitors: List[CompetitorEvidence]
    unknown: List[str]
    rules: List[str]


def build_evidence_for_assignment(
    winner: Assignment,
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    all_scores: Dict[Tuple[str, str], CandidateScore],
    registry: Optional[RuleRegistry] = None,
    max_competitors: int = 20,
) -> Optional[DecisionEvidence]:
    if winner.kind != "ASSIGNED" or not winner.post_id or not winner.score:
        return None

    post_id = winner.post_id
    wscore = winner.score
    competitors: List[CompetitorEvidence] = []

    # Find all agents who also wanted this post
    for aid, agent in agents.items():
        if aid == winner.agent_id:
            continue
        key = (aid, post_id)
        if key in all_scores:
            s = all_scores[key]
            if not s.eligible:
                competitors.append(CompetitorEvidence(
                    agent=aid, eligible=False, reason=s.rejection_reason or "NOT_ELIGIBLE",
                ))
            else:
                # compare regulatory keys
                wk = wscore.regulatory_key()
                ck = s.regulatory_key()
                if ck < wk:
                    # competitor would have been better — this is a problem
                    comparison = "COMPETITOR_SHOULD_HAVE_WON"
                elif ck == wk:
                    comparison = "TIE_BROKEN_BY_DISCRIMINANT"
                else:
                    # winner better
                    if wscore.priority_rank < s.priority_rank:
                        comparison = "WINNER_HIGHER_PRIORITY"
                    elif wscore.bareme > s.bareme:
                        comparison = "WINNER_HIGHER_BAREME"
                    elif wscore.wish_rank < s.wish_rank:
                        comparison = "WINNER_BETTER_WISH_RANK"
                    else:
                        comparison = "WINNER_TIEBREAK"
                competitors.append(CompetitorEvidence(
                    agent=aid, eligible=True,
                    priority=s.priority_rank, bareme=s.bareme, wish_rank=s.wish_rank,
                    comparison=comparison,
                ))

    # sort: show eligible competitors first, by how close they were
    competitors.sort(key=lambda c: (0 if c.eligible else 1, c.bareme or 0), reverse=False)
    competitors = competitors[:max_competitors]

    unknown = []
    if wscore.sous_rank is not None:
        # sous_rank is DESIGN_DECISION / convention
        unknown.append("SOUS_RANK_POLICY")

    return DecisionEvidence(
        agent=winner.agent_id,
        post=post_id,
        priority=wscore.priority_rank,
        bareme=wscore.bareme,
        wish_rank=wscore.wish_rank,
        sous_rank=wscore.sous_rank,
        tie_break=wscore.tie_key,
        bonuses=list(wscore.bonuses),
        competitors=competitors,
        unknown=unknown,
        rules=list(wscore.bonuses),
    )


def evidence_to_dict(ev: DecisionEvidence) -> dict:
    return {
        "agent": ev.agent,
        "post": ev.post,
        "decision": {
            "priority": ev.priority,
            "bareme": ev.bareme,
            "wish_rank": ev.wish_rank,
            "sous_rank": ev.sous_rank,
            "tie_break": ev.tie_break,
        },
        "evidence": {
            "eligible": True,
            "competitors": [asdict(c) for c in ev.competitors],
        },
        "rules": ev.rules,
        "unknown": ev.unknown,
    }
