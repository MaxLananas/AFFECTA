"""
Full decision evidence with temporal context.
DESIGN_DECISION: decision_index is the ordinal of assignment in the deterministic pass.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple, Any
import hashlib
import json

from movement_engine.domain.models import Assignment, CandidateScore


@dataclass(frozen=True)
class CompetitorEvidence:
    agent_id: str
    post_id: str
    eligible: bool
    priority: Optional[int]
    bareme: Optional[float]
    wish_rank: Optional[int]
    comparison: str
    reason: str


@dataclass
class DecisionEvidence:
    agent_id: str
    post_id: str
    decision_index: int
    priority: int
    bareme: int
    wish_rank: int
    sous_rank: Optional[int]
    tie_break: Optional[str]
    bonuses: Tuple[str, ...]
    competitors: Tuple[CompetitorEvidence, ...]
    available_posts_snapshot_hash: str  # hash of free posts at decision time
    rules_applied: Tuple[str, ...]
    unknown_rules: Tuple[str, ...]
    dependency_chain: Tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "post_id": self.post_id,
            "decision_index": self.decision_index,
            "decision": {
                "priority": self.priority,
                "bareme": self.bareme,
                "wish_rank": self.wish_rank,
                "sous_rank": self.sous_rank,
                "tie_break": self.tie_break,
            },
            "competitors": [asdict(c) for c in self.competitors],
            "available_posts_snapshot_hash": self.available_posts_snapshot_hash,
            "rules_applied": list(self.rules_applied),
            "unknown_rules": list(self.unknown_rules),
            "dependency_chain": list(self.dependency_chain),
        }


def snapshot_hash(free_posts: set) -> str:
    return hashlib.sha256("|".join(sorted(free_posts)).encode()).hexdigest()[:16]


def compare_scores(winner: CandidateScore, other: CandidateScore) -> str:
    wk, ok = winner.regulatory_key(), other.regulatory_key()
    if ok < wk:
        return "COMPETITOR_SHOULD_HAVE_WON"
    if ok == wk:
        return "TIE_BROKEN_BY_DISCRIMINANT"
    if winner.priority_rank < other.priority_rank:
        return "WINNER_HIGHER_PRIORITY"
    if winner.bareme > other.bareme:
        return "WINNER_HIGHER_BAREME"
    if winner.wish_rank < other.wish_rank:
        return "WINNER_BETTER_WISH_RANK"
    return "WINNER_TIEBREAK"


def build_decision_evidence(
    winner: Assignment,
    decision_index: int,
    free_posts_at_time: set,
    scores_for_post: Dict[str, CandidateScore],  # agent_id -> score for this post
    max_competitors: int = 30,
) -> Optional[DecisionEvidence]:
    if winner.kind != "ASSIGNED" or not winner.post_id or not winner.score:
        return None

    comps: List[CompetitorEvidence] = []
    for aid, s in scores_for_post.items():
        if aid == winner.agent_id:
            continue
        if not s.eligible:
            comps.append(CompetitorEvidence(
                agent_id=aid, post_id=winner.post_id, eligible=False,
                priority=None, bareme=None, wish_rank=None,
                comparison="NOT_ELIGIBLE", reason=s.rejection_reason or "NOT_ELIGIBLE",
            ))
        else:
            comps.append(CompetitorEvidence(
                agent_id=aid, post_id=winner.post_id, eligible=True,
                priority=s.priority_rank, bareme=s.bareme, wish_rank=s.wish_rank,
                comparison=compare_scores(winner.score, s), reason="",
            ))

    # Sort: flag any COMPETITOR_SHOULD_HAVE_WON first
    comps.sort(key=lambda c: (0 if c.comparison == "COMPETITOR_SHOULD_HAVE_WON" else 1, c.agent_id))
    comps = comps[:max_competitors]

    unknown: List[str] = []
    if winner.score.sous_rank is not None:
        unknown.append("SOUS_RANK_POLICY")

    return DecisionEvidence(
        agent_id=winner.agent_id,
        post_id=winner.post_id,
        decision_index=decision_index,
        priority=winner.score.priority_rank,
        bareme=winner.score.bareme,
        wish_rank=winner.score.wish_rank,
        sous_rank=winner.score.sous_rank,
        tie_break=winner.score.tie_key,
        bonuses=winner.score.bonuses,
        competitors=tuple(comps),
        available_posts_snapshot_hash=snapshot_hash(free_posts_at_time),
        rules_applied=winner.score.bonuses,
        unknown_rules=tuple(unknown),
        dependency_chain=(),
    )


def evidence_bundle_hash(evidences: List[DecisionEvidence]) -> str:
    payload = json.dumps([e.to_dict() for e in evidences], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
