from __future__ import annotations

from dataclasses import dataclass

from movement_engine.domain.models import RuleLevel, RuleStatus, SourceRef


@dataclass(frozen=True, slots=True)
class Bonus:
    id: str
    label: str
    amount: int
    level: RuleLevel
    source: SourceRef
    status: RuleStatus


class RuleRegistry:
    def __init__(self, version: str):
        self.version = version
        self._bonuses: dict[str, Bonus] = {}

    def register(self, bonus: Bonus) -> None:
        if bonus.id in self._bonuses:
            raise ValueError(f"Duplicate rule: {bonus.id}")
        self._bonuses[bonus.id] = bonus

    def get(self, rule_id: str) -> Bonus:
        return self._bonuses[rule_id]

    def all(self) -> tuple[Bonus, ...]:
        return tuple(self._bonuses.values())

    # ---- Auditing helpers ------------------------------------------------
    def unsourced(self) -> tuple[Bonus, ...]:
        """Bonuses whose status is not REGULATORY_CONFIRMED (audit surface)."""
        return tuple(b for b in self._bonuses.values() if b.status != RuleStatus.CONFIRMED)

    def audit_table(self) -> list[dict]:
        rows = []
        for b in self._bonuses.values():
            rows.append({
                "id": b.id,
                "label": b.label,
                "amount": b.amount,
                "level": b.level.value,
                "status": b.status.value,
                "source_url": b.source.url,
                "source_year": b.source.year,
            })
        return rows


# ---------------------------------------------------------------------------
# HISTORICAL registry (guadeloupe-2026-v1).
#
# IMPORTANT (see docs/REGULATORY_SOURCES.md): the numeric amounts below are the
# project's original provisional values. Several were previously tagged CONFIRMED
# without a verifiable source. They are kept here for backward compatibility and
# test stability, but each bonus now carries an HONEST status:
#   * CONFIRMED  only where a structural rule is textually sourced;
#   * PROBABLE   where the mechanism is attested but the exact amount varies by
#                département/année;
#   * UNKNOWN    where neither amount nor mechanism could be verified.
# A separately documented, source-anchored reference barème is available via
# `reference_registry()` for realism work — WITHOUT changing legacy behaviour.
# ---------------------------------------------------------------------------
def guadeloupe_registry() -> RuleRegistry:
    registry = RuleRegistry(version="guadeloupe-2026-v1")

    # Generic (unverified in this environment) source placeholder for the historical
    # academic scale. The exact Guadeloupe 2026 LDG could not be fetched/verified here.
    unverified = SourceRef(
        url="https://www.ac-guadeloupe.fr/media/20436/download",
        passage="LDG / barème académique Guadeloupe (lien NON vérifié dans cet environnement)",
        year=2026,
        status=RuleStatus.UNKNOWN,
    )
    # Structural rules (mechanisms) that ARE textually confirmed by multiple sources.
    confirmed_struct = SourceRef(
        url="https://www.ac-lyon.fr/media/57778/download",
        passage="Note intra 1D ac-Lyon : priorité supplante barème ; RC/parent isolé non cumulables ; "
                "priorités inapplicables aux vœux groupes",
        year=2025,
        status=RuleStatus.CONFIRMED,
    )

    def add(rule_id, label, amount, level, status=RuleStatus.PROBABLE, source=unverified):
        registry.register(Bonus(rule_id, label, amount, level, source, status))

    # Amounts: PROBABLE/UNKNOWN (values are provisional, mechanisms attested).
    add("MED_GRAVE_30", "Situation médicale grave", 30, RuleLevel.SECONDARY, RuleStatus.PROBABLE)
    add("CHILD_2", "Enfant à charge", 2, RuleLevel.SECONDARY, RuleStatus.PROBABLE)
    add("UNIQUE_PARENT_50", "Autorité parentale unique", 50, RuleLevel.SECONDARY, RuleStatus.UNKNOWN)
    add("RENEWAL_V1_10", "Renouvellement du premier vœu", 10, RuleLevel.SECONDARY, RuleStatus.PROBABLE)
    add("REINTEGRATION_50", "Réintégration", 50, RuleLevel.SECONDARY, RuleStatus.PROBABLE)
    add("RC_150", "Rapprochement de conjoint", 150, RuleLevel.PRIORITY, RuleStatus.PROBABLE)
    add("RC_250", "Rapprochement de conjoint", 250, RuleLevel.PRIORITY, RuleStatus.UNKNOWN)
    add("APC_150", "Autorité parentale conjointe", 150, RuleLevel.PRIORITY, RuleStatus.PROBABLE)
    add("APC_250", "Autorité parentale conjointe", 250, RuleLevel.PRIORITY, RuleStatus.UNKNOWN)
    add("BOE_100", "Bénéficiaire obligation d'emploi", 100, RuleLevel.PRIORITY, RuleStatus.PROBABLE)
    add("HANDICAP_500", "Handicap (avis favorable)", 500, RuleLevel.PRIORITY, RuleStatus.PROBABLE)
    return registry


# ---------------------------------------------------------------------------
# REFERENCE registry (documented 2025/2026 orders of magnitude).
#
# Every amount here is traceable to a public source in docs/REGULATORY_SOURCES.md.
# These are ORDERS OF MAGNITUDE — the real intra barème is set by each académie's
# LDG and varies. Use for realism experiments; NOT a substitute for the target
# département's LDG. Kept separate so it never silently changes legacy results.
# ---------------------------------------------------------------------------
def reference_registry() -> RuleRegistry:
    registry = RuleRegistry(version="reference-ldg-2026")

    src_cgt92 = SourceRef(
        url="https://www.92.cgteduc.fr/le-mouvement-interdepartemental-du-1er-degre/",
        passage="Barème mouvement interdép. 2026 : enfant 50 pts ; handicap/médical grave 800 pts ; "
                "BOE 100 pts ; RC 150 pts ; RC/APC progressif 50/200/350/450 ; CIMM 600 pts",
        year=2026,
        status=RuleStatus.CONFIRMED,
    )
    src_versailles = SourceRef(
        url="https://www.cgteduc-versailles.fr/guide-sur-le-mouvement-intra-departemental/",
        passage="Guide intra 2026 : BOE/RQTH 30 pts ; REP+ 90 / REP 45 ; renouvellement vœu1 2 pts/an",
        year=2026,
        status=RuleStatus.CONFIRMED,
    )
    src_strasbourg = SourceRef(
        url="https://se-unsa67.net/wp-content/uploads/2025/03/circulaire-MVT-annexes-repagineesommaire-interactifcompressee.pdf",
        passage="Circulaire intra 2025 ac-Strasbourg : mesure de carte scolaire 500/300/100 pts",
        year=2025,
        status=RuleStatus.CONFIRMED,
    )

    def add(rule_id, label, amount, level, status=RuleStatus.CONFIRMED, source=src_cgt92):
        registry.register(Bonus(rule_id, label, amount, level, source, status))

    # Priority-level bonuses (legal priorities that supplant barème are handled in the
    # scorer's priority_rank; these amounts feed the barème tie-break within a priority).
    add("MED_GRAVE_800", "Situation médicale grave / handicap (vœu 1)", 800, RuleLevel.PRIORITY, source=src_cgt92)
    add("BOE_RQTH_30", "BOE / RQTH (intra, plusieurs LDG)", 30, RuleLevel.PRIORITY, source=src_versailles)
    add("BOE_100", "BOE (interdép.)", 100, RuleLevel.PRIORITY, source=src_cgt92)
    add("RC_150", "Rapprochement de conjoint (base)", 150, RuleLevel.PRIORITY, source=src_cgt92)
    add("RC_SEP_1", "RC/APC séparation 1 an", 50, RuleLevel.PRIORITY, source=src_cgt92)
    add("RC_SEP_2", "RC/APC séparation 2 ans", 200, RuleLevel.PRIORITY, source=src_cgt92)
    add("RC_SEP_3", "RC/APC séparation 3 ans", 350, RuleLevel.PRIORITY, source=src_cgt92)
    add("RC_SEP_4", "RC/APC séparation 4 ans et +", 450, RuleLevel.PRIORITY, source=src_cgt92)
    add("APC_150", "Autorité parentale conjointe (base)", 150, RuleLevel.PRIORITY, source=src_cgt92)
    add("CIMM_600", "Centre des intérêts matériels et moraux (DOM, interdép.)", 600, RuleLevel.PRIORITY, source=src_cgt92)

    # Secondary bonuses (pure barème points).
    add("CHILD_50", "Enfant à charge (< 18 ans)", 50, RuleLevel.SECONDARY, source=src_cgt92)
    add("REP_45", "Éducation prioritaire REP", 45, RuleLevel.SECONDARY, source=src_versailles)
    add("REP_PLUS_90", "Éducation prioritaire REP+", 90, RuleLevel.SECONDARY, source=src_versailles)
    add("RENEWAL_V1_2PY", "Renouvellement vœu 1 (2 pts/an)", 2, RuleLevel.SECONDARY, source=src_versailles)
    add("CARTE_ECOLE_500", "Mesure de carte scolaire — même école", 500, RuleLevel.SECONDARY, source=src_strasbourg)
    add("CARTE_CIRCO_300", "Mesure de carte scolaire — circonscription", 300, RuleLevel.SECONDARY, source=src_strasbourg)
    add("CARTE_DEPT_100", "Mesure de carte scolaire — département", 100, RuleLevel.SECONDARY, source=src_strasbourg)
    return registry
