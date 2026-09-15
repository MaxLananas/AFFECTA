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
    # Discriminants réglementaires de départage (REGULATORY_CONFIRMED, ordre officiel) :
    # à priorité, barème, rang et sous-rang égaux, on départage par ancienneté générale
    # de fonction EN (AEN) décroissante, puis ancienneté dans l'échelon décroissante,
    # puis numéro aléatoire. Exprimés en mois pour un ordre total fin.
    aen_months: int = 0            # ancienneté générale de fonction Éducation nationale
    echelon_months: int = 0        # ancienneté dans l'échelon détenu
    # Contexte géographique et statutaire (alimente le barème, ne le fixe pas).
    current_commune: Optional[str] = None
    spouse_distance_km: Optional[float] = None      # distance résidence pro. conjoint
    separation_years: int = 0                        # années de séparation (RC/APC)
    rep_status: Optional[str] = None                 # None | "REP" | "REP+" | "QPV"
    rep_years: int = 0
    post_seniority_years: int = 0                    # ancienneté sur le poste actuel
    mcs_affected: bool = False                       # touché par une mesure de carte scolaire
    cimm_dom: bool = False                            # centre des intérêts matériels et moraux
    titles: tuple[str, ...] = ()                      # ex. ("CAPPEI:D", "DIR_LA")


@dataclass(frozen=True, slots=True)
class Post:
    id: str
    commune: str
    support: str
    vacant: bool = True
    capacity: int = 1
    holder_id: Optional[str] = None
    # Métadonnées réelles (datasets/guadeloupe_2026/posts.json) alimentant les règles.
    nature_code: Optional[str] = None      # DE, ECEL, ECMA, TR, RASE, ULEC, UEE, ...
    circonscription: Optional[str] = None
    profil: bool = False                    # poste à profil (recrutement particulier)
    rep_status: Optional[str] = None        # None | "REP" | "REP+" | "QPV"
    required_titles: tuple[str, ...] = ()   # exigences (ex. ("CAPPEI:D",) ou ("DIR_LA",))
    nb_classes: int = 0


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
    # Discriminants réglementaires (décroissants) — voir Agent.aen_months / echelon_months.
    aen_months: int = 0
    echelon_months: int = 0

    def regulatory_key(self) -> tuple:
        """Clé de classement par poste (ordre croissant = meilleur candidat).

        Reproduit exactement la séquence MVT1D (REGULATORY_CONFIRMED, convergence
        ac-bordeaux / ac-toulouse / ac-poitiers) :
          1. priorité croissante ;
          2. barème décroissant ;
          3. rang de vœu croissant ;
          4. sous-rang croissant ;
          5. discriminant 1 : ancienneté de fonction EN (AEN) décroissante ;
          6. discriminant 2 : ancienneté dans l'échelon décroissante ;
          7. discriminant 3 : numéro aléatoire (tie_key).
        Les anciennetés sont niées pour transformer « décroissant » en ordre croissant.
        """
        return (
            self.priority_rank,
            -self.bareme,
            self.wish_rank,
            self.sous_rank if self.sous_rank is not None else 2**63,
            -self.aen_months,
            -self.echelon_months,
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
