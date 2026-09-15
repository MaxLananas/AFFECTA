"""
AFFECTA — Orchestration du mouvement en deux temps (procédure MVT1D complète).

POURQUOI CE MODULE
------------------
Le mouvement intra-départemental confirmé (REGULATORY_CONFIRMED — se-unsa13, ac-bordeaux,
ac-toulouse, ac-strasbourg) se déroule en DEUX temps enchaînés :

  1. **Phase principale** — traitement de tous les vœux (précis et groupes) par
     acceptation différée côté enseignants (`solver/deferred_acceptance.py`). Elle produit
     l'unique appariement stable optimal-enseignant respectant l'ordre réglementaire par
     poste. Les titulaires sans vœu satisfait restent sur leur poste (STAY).

  2. **Phase d'extension** — les **participants obligatoires** (stagiaires, entrants,
     réintégrations, mesures de carte scolaire, affectés à titre provisoire) qui n'ont
     obtenu AUCUN vœu DOIVENT recevoir un poste : ils sont affectés d'office sur un poste
     resté vacant (`solver/extension.py`), sur demande valide (>= seuil MOB, affectation
     provisoire) puis sur demande incomplète (affectation définitive).

Jusqu'ici les deux phases existaient séparément mais n'étaient JAMAIS enchaînées dans un
run standard : un participant obligatoire non satisfait ressortait donc `UNASSIGNED`, ce
qui ne correspond PAS à la procédure réelle (aucun obligatoire ne reste sans poste tant
qu'un poste vacant compatible existe). Ce module joint les deux temps en une seule
exécution auditable et renvoie un `EngineResult` cohérent (mêmes hachages, mêmes
certificats, même vérificateur de stabilité).

GARANTIES PRÉSERVÉES
--------------------
* La phase d'extension ne travaille QUE sur les postes restés vacants après la phase
  principale : elle ne peut jamais déloger un agent déjà affecté, donc la stabilité
  (absence d'envie justifiée) de la phase principale est intégralement conservée.
* Le résultat reste déterministe et reproductible (mêmes clés de départage).
* Les affectations d'office sont tracées (`chain_id = EXTENSION_PRO | EXTENSION_TPD`) et
  restent distinguables des affectations sur vœu dans les certificats et explications.

Ce module n'invente aucune règle : le seuil MOB est un PRODUCT_POLICY explicite
(`extension.DEFAULT_MOB_THRESHOLD`), le reste est REGULATORY_CONFIRMED (voir les docstrings
de `deferred_acceptance.py` et `extension.py`).
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional

from movement_engine.domain.models import Agent, Post, Wish
from movement_engine.regulatory.registry import RuleRegistry
from movement_engine.solver.engine import EngineResult
from movement_engine.solver.deferred_acceptance import run_deferred_acceptance
from movement_engine.solver.extension import run_extension, DEFAULT_MOB_THRESHOLD


def count_mob_wishes(wishes: Dict[str, List[Wish]]) -> Dict[str, int]:
    """Nombre de vœux groupe « mobilité obligatoire » (MOB) saisis par agent.

    REGULATORY_CONFIRMED : la validité d'une demande obligatoire repose sur le nombre de
    vœux GROUPE saisis (et non de vœux précis). On assimile ici « vœu MOB » à « vœu de
    type groupe » (`Wish.group is True`), la seule information de type disponible dans le
    modèle. C'est une approximation fidèle tant que les vœux groupes du jeu de données
    représentent les vœux MOB — DESIGN_DECISION documentée.
    """
    return {
        aid: sum(1 for w in wl if getattr(w, "group", False))
        for aid, wl in wishes.items()
    }


def run_movement(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    registry: Optional[RuleRegistry] = None,
    *,
    campaign_seed: str = "20260810",
    allow_pure_exchanges: bool = False,
    with_extension: bool = True,
    mob_counts: Optional[Dict[str, int]] = None,
    mob_threshold: int = DEFAULT_MOB_THRESHOLD,
) -> EngineResult:
    """Exécute la procédure MVT1D complète : acceptation différée puis extension.

    Renvoie un `EngineResult` unique et cohérent. Lorsque `with_extension=False`, se
    comporte exactement comme `run_deferred_acceptance` (utile pour isoler la phase
    principale). `mob_counts` est dérivé des vœux groupes si non fourni.

    Le résultat de la phase principale — donc sa stabilité — n'est jamais modifié par
    l'extension : celle-ci ne remplit que des postes restés vacants.
    """
    base = run_deferred_acceptance(
        agents, posts, wishes, registry,
        campaign_seed=campaign_seed,
        allow_pure_exchanges=allow_pure_exchanges,
    )

    if not with_extension:
        return base

    # Y a-t-il seulement des obligatoires non affectés ? Sinon, court-circuit (aucun coût).
    has_pending = any(
        getattr(ag, "participation", "volontaire") == "obligatoire"
        and base.assignments.get(aid) is not None
        and base.assignments[aid].kind != "ASSIGNED"
        for aid, ag in agents.items()
    )
    if not has_pending:
        return base

    if mob_counts is None:
        mob_counts = count_mob_wishes(wishes)

    extended = run_extension(
        base.assignments, agents, posts,
        mob_counts=mob_counts,
        mob_threshold=mob_threshold,
        campaign_seed=campaign_seed,
    )

    # Recompose un EngineResult cohérent : métriques recalculées, hachage de résultat
    # recalculé sur les affectations finales (le hachage d'entrée est inchangé).
    n_office = sum(
        1 for aid, a in extended.items()
        if a.kind == "ASSIGNED"
        and base.assignments.get(aid) is not None
        and base.assignments[aid].kind != "ASSIGNED"
    )

    metrics = dict(base.metrics)
    metrics["assigned"] = sum(1 for a in extended.values() if a.kind == "ASSIGNED")
    metrics["stayed"] = sum(1 for a in extended.values() if a.kind == "STAY")
    metrics["unassigned"] = sum(1 for a in extended.values() if a.kind == "UNASSIGNED")
    metrics["office_assignments"] = n_office
    metrics["method"] = "DEFERRED_ACCEPTANCE+EXTENSION"

    canon = "|".join(
        f"{a}:{extended[a].post_id}:{extended[a].kind}" for a in sorted(extended)
    )
    result_hash = hashlib.sha256(canon.encode()).hexdigest()[:16]

    return EngineResult(
        assignments=extended,
        cycles=base.cycles,
        metrics=metrics,
        elapsed_ms=base.elapsed_ms,
        input_hash=base.input_hash,
        result_hash=result_hash,
    )
