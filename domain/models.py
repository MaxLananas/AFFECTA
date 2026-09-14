from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RuleStatus(str, Enum):
    CONFIRMED = "REGULATORY_CONFIRMED"
    PROBABLE = "REGULATORY_PROBABLE"
    UNKNOWN = "UNKNOWN"


class RuleLevel(str, Enum):
    PRIORITY = "LEGAL_PRIORITY"
    SECONDARY = "SECONDARY"


@dataclass(frozen=True, slots=True)
class SourceRef:
    url: str
    passage: str
    year: int
    status: RuleStatus


@dataclass(frozen=True, slots=True)
class Agent:
    id: str
    echelon: int
    children: int = 0
    unique_parental_authority: bool = False
    medical_grave: bool = False
    boe: bool = False
    handicap_500: bool = False
    rc_points: int = 0
    apc_points: int = 0
    renewal_years: int = 0
    spouse_commune: Optional[str] = None
    child_commune: Optional[str] = None
    current_post_id: Optional[str] = None
    aen_points: int = 0
    fidelity_points: int = 0
    mcs_points: int = 0
    rep_points: int = 0
    islands_points: int = 0
    reintegration_points: int = 0
    participation: str = "volontaire"  # obligatoire | volontaire


@dataclass(frozen=True, slots=True)
class Post:
    id: str
    commune: str
    support: str
    vacant: bool = True
    capacity: int = 1
    holder_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Wish:
    rank: int
    post_ids: tuple[str, ...]
    precise: bool = True
    group: bool = False


@dataclass(frozen=True, slots=True)
class CandidateScore:
    agent_id: str
    post_id: str
    priority_rank: int
    bareme: int
    wish_rank: int
    sous_rank: Optional[int]
    tie_key: Optional[str]
    bonuses: tuple[str, ...] = ()
    eligible: bool = True
    rejection_reason: Optional[str] = None

    def regulatory_key(self) -> tuple:
        return (
            self.priority_rank,
            -self.bareme,
            self.wish_rank,
            self.sous_rank if self.sous_rank is not None else 2**63,
            self.tie_key if self.tie_key is not None else "",
        )


@dataclass(frozen=True, slots=True)
class Assignment:
    agent_id: str
    post_id: Optional[str]
    wish_rank: Optional[int]
    kind: str  # ASSIGNED | STAY | UNASSIGNED
    score: Optional[CandidateScore] = None
    chain_id: Optional[str] = None
