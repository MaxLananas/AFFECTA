"""
Phase d'extension — affectation d'office des participants obligatoires.

CONTEXTE RÉGLEMENTAIRE (REGULATORY_CONFIRMED — ac-bordeaux, ac-toulouse, ac-strasbourg,
ac-limoges, se-unsa)
--------------------------------------------------------------------------------------
Le mouvement distingue deux populations :

  * les **participants obligatoires** (stagiaires, sans affectation, réintégrations,
    affectés à titre provisoire, mesures de carte scolaire non réaffectées) : ils DOIVENT
    recevoir un poste. Ils doivent saisir au moins deux vœux groupe « mobilité obligatoire »
    (MOB) — le seuil exact varie de 2 (Paris, Strasbourg) à 5 (Bordeaux) selon le
    département ;
  * les **participants facultatifs** (titulaires d'un poste définitif) : s'ils n'obtiennent
    aucun vœu, ils restent sur leur poste actuel (STAY).

Lorsqu'un participant obligatoire n'obtient AUCUN de ses vœux (précis, groupe, MOB), il est
affecté d'office par un mécanisme dit « d'extension » sur un poste resté vacant, selon un
ordre déterministe :

  1. les candidats à demande valide (au moins un vœu MOB saisi) sont traités AVANT ceux à
     demande incomplète ;
  2. au sein de chaque population : barème de base décroissant, puis discriminant ;
  3. le poste est cherché dans un ordre fixe de circonscriptions puis de sous-catégories de
     postes (« vœu balayette »/B999), en excluant les postes à profil et les postes
     exigeant un titre que le candidat ne détient pas.

Le caractère de l'affectation d'office :
  * demande valide (>= seuil MOB) non satisfaite -> affectation **provisoire** (PRO) ;
  * demande incomplète / aucun vœu -> affectation **définitive** (TPD) sur poste vacant.

Cette phase s'exécute APRÈS l'acceptation différée, sur les seuls postes restés vacants ;
elle ne peut donc jamais déloger un agent affecté par la phase principale et préserve la
stabilité de celle-ci.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from movement_engine.domain.models import Agent, Assignment, Post
from movement_engine.solver.engine import _tie_key

# Seuil de vœux MOB pour une demande valide. PRODUCT_POLICY : valeur départementale
# variable (2 à 5 selon l'académie) ; 2 retenu par défaut (le plus fréquent, ac-strasbourg
# / ac-paris). Ajustable sans toucher à la logique.
DEFAULT_MOB_THRESHOLD = 2


def _extension_post_order(posts: Dict[str, Post]) -> List[str]:
    """Ordre fixe de balayage des postes vacants pour l'extension.

    REGULATORY_CONFIRMED (structure) : circonscription croissante, puis nature de poste,
    puis identifiant — déterministe et reproductible. Les postes à profil sont exclus
    (recrutement particulier hors extension).
    """
    def key(pid: str):
        p = posts[pid]
        return (p.circonscription or "", p.nature_code or "", pid)

    return sorted(
        (pid for pid, p in posts.items() if not p.profil),
        key=key,
    )


def _agent_can_hold(agent: Agent, post: Post) -> bool:
    """Un poste à exigence de titre ne peut être attribué en extension qu'au détenteur
    du titre (affectation définitive) ; sinon il est ignoré à ce stade. REGULATORY_CONFIRMED.
    """
    if not post.required_titles:
        return True
    return bool(set(agent.titles) & set(post.required_titles))


def run_extension(
    assignments: Dict[str, Assignment],
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    *,
    mob_counts: Optional[Dict[str, int]] = None,
    mob_threshold: int = DEFAULT_MOB_THRESHOLD,
    campaign_seed: str = "20260810",
) -> Dict[str, Assignment]:
    """Affecte d'office les participants obligatoires restés sans poste.

    `mob_counts` : nombre de vœux MOB saisis par agent (défaut 0). Ne modifie que les
    agents `participation == "obligatoire"` non affectés (kind != ASSIGNED). Renvoie un
    NOUVEAU dictionnaire d'affectations ; la phase principale n'est pas altérée.
    """
    mob_counts = mob_counts or {}
    result = dict(assignments)

    # Capacité résiduelle après la phase principale.
    used: Dict[str, int] = {}
    for a in result.values():
        if a.kind in ("ASSIGNED", "STAY") and a.post_id:
            used[a.post_id] = used.get(a.post_id, 0) + 1
    remaining = {pid: p.capacity - used.get(pid, 0) for pid, p in posts.items()}

    # Population à traiter : obligatoires non affectés.
    pending = [
        aid for aid, ag in agents.items()
        if getattr(ag, "participation", "volontaire") == "obligatoire"
        and result.get(aid) is not None
        and result[aid].kind != "ASSIGNED"
    ]
    if not pending:
        return result

    def order_key(aid: str):
        ag = agents[aid]
        valid = mob_counts.get(aid, 0) >= mob_threshold
        base_bareme = _base_bareme(ag)
        # demande valide d'abord (0 < 1), puis barème décroissant, puis discriminants.
        return (
            0 if valid else 1,
            -base_bareme,
            -ag.aen_months,
            -ag.echelon_months,
            _tie_key(aid, campaign_seed),
        )

    pending.sort(key=order_key)
    post_order = _extension_post_order(posts)

    for aid in pending:
        ag = agents[aid]
        valid = mob_counts.get(aid, 0) >= mob_threshold
        placed = False
        for pid in post_order:
            if remaining.get(pid, 0) <= 0:
                continue
            if not _agent_can_hold(ag, posts[pid]):
                continue
            remaining[pid] -= 1
            # demande valide non satisfaite -> provisoire ; incomplète -> définitive.
            kind = "ASSIGNED"
            result[aid] = Assignment(
                agent_id=aid, post_id=pid, wish_rank=None, kind=kind,
                chain_id="EXTENSION_PRO" if valid else "EXTENSION_TPD",
            )
            placed = True
            break
        if not placed:
            # aucun poste vacant compatible : reste non affecté (cas dégénéré).
            result[aid] = Assignment(
                agent_id=aid, post_id=None, wish_rank=None, kind="UNASSIGNED",
            )
    return result


def _base_bareme(agent: Agent) -> int:
    """Barème de base pour l'extension : ancienneté de service + ancienneté de poste +
    handicap automatique + éducation prioritaire. REGULATORY_CONFIRMED (glossaire mutation
    education.gouv, ac-guadeloupe FAQ) : l'extension ne conserve pas les bonifications
    attachées à un vœu spécifique. Valeurs en points (approximation mensuelle de l'AEN).
    """
    from movement_engine.regulatory.scorer import echelon_points, _post_seniority_bonus, _rep_bonus

    b = echelon_points(agent.echelon)
    b += agent.aen_months // 12 * 2                       # ancienneté de service ~2 pts/an
    b += _post_seniority_bonus(agent.post_seniority_years)
    if agent.boe:
        b += 100
    if agent.rep_status:
        b += _rep_bonus(agent.rep_status, agent.rep_years)
    return b
