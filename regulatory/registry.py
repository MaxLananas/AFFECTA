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


def guadeloupe_registry() -> RuleRegistry:
    registry = RuleRegistry(version="guadeloupe-2026-v1")
    source = SourceRef(
        url="https://www.ac-guadeloupe.fr/media/20436/download",
        passage="LDG / barème académique Guadeloupe",
        year=2026,
        status=RuleStatus.CONFIRMED,
    )

    def add(rule_id: str, label: str, amount: int, level: RuleLevel) -> None:
        registry.register(
            Bonus(
                id=rule_id,
                label=label,
                amount=amount,
                level=level,
                source=source,
                status=RuleStatus.CONFIRMED,
            )
        )

    add("MED_GRAVE_30", "Situation médicale grave", 30, RuleLevel.SECONDARY)
    add("CHILD_2", "Enfant à charge", 2, RuleLevel.SECONDARY)
    add("UNIQUE_PARENT_50", "Autorité parentale unique", 50, RuleLevel.SECONDARY)
    add("RENEWAL_V1_10", "Renouvellement du premier vœu", 10, RuleLevel.SECONDARY)
    add("REINTEGRATION_50", "Réintégration", 50, RuleLevel.SECONDARY)
    add("RC_150", "Rapprochement de conjoint", 150, RuleLevel.PRIORITY)
    add("RC_250", "Rapprochement de conjoint", 250, RuleLevel.PRIORITY)
    add("APC_150", "Autorité parentale conjointe", 150, RuleLevel.PRIORITY)
    add("APC_250", "Autorité parentale conjointe", 250, RuleLevel.PRIORITY)
    add("BOE_100", "Bénéficiaire obligation d'emploi", 100, RuleLevel.PRIORITY)
    add("HANDICAP_500", "Handicap (avis favorable)", 500, RuleLevel.PRIORITY)
    return registry
