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

COMPLEXITÉ
----------
L'affectation d'office est un couplage glouton « premier poste disponible compatible dans
un ordre fixe ». Une implémentation naïve rebalaye tous les postes pour chaque agent, soit
O(agents x postes) — quadratique et inutilisable à grande échelle. L'implémentation retenue
est quasi linéaire, O((agents + postes) log postes) :

  * les postes SANS exigence de titre sont compatibles avec tout le monde ; comme un poste
    rempli le reste, le « premier poste libre » dans cet ensemble n'avance que vers l'avant :
    un simple curseur monotone suffit ;
  * les postes AVEC exigence de titre (rares) sont indexés par jeton de titre dans des tas
    (heaps) ordonnés par position ; un agent ne consulte que les tas des titres qu'il détient.

Pour chaque agent, le poste choisi est celui de plus petite position parmi « premier poste
libre non restreint » et « premier poste restreint libre compatible ». C'est EXACTEMENT le
résultat de la version naïve (équivalence prouvée par différentiel exhaustif dans
`tests/test_extension_fast.py`), en temps quasi linéaire.
"""
from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Tuple

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


def _order_key(ag: Agent, aid: str, mob_counts: Dict[str, int],
               mob_threshold: int, campaign_seed: str) -> Tuple:
    """Ordre de traitement des obligatoires : demande valide d'abord, puis barème
    décroissant, puis discriminants MVT1D (AEN, échelon), puis tirage déterministe."""
    valid = mob_counts.get(aid, 0) >= mob_threshold
    base_bareme = _base_bareme(ag)
    return (
        0 if valid else 1,
        -base_bareme,
        -ag.aen_months,
        -ag.echelon_months,
        _tie_key(aid, campaign_seed),
    )


def run_extension(
    assignments: Dict[str, Assignment],
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    *,
    mob_counts: Optional[Dict[str, int]] = None,
    mob_threshold: int = DEFAULT_MOB_THRESHOLD,
    campaign_seed: str = "20260810",
) -> Dict[str, Assignment]:
    """Affecte d'office les participants obligatoires restés sans poste (quasi linéaire).

    `mob_counts` : nombre de vœux MOB saisis par agent (défaut 0). Ne modifie que les
    agents `participation == "obligatoire"` non affectés (kind != ASSIGNED). Renvoie un
    NOUVEAU dictionnaire d'affectations ; la phase principale n'est pas altérée.

    Robustesse : tolère les agents/postes manquants ou incohérents (capacité négative,
    identifiants inconnus dans `assignments`) sans lever d'exception ; un poste incompatible
    ou saturé est simplement ignoré, et un agent sans poste compatible reste UNASSIGNED.
    """
    mob_counts = mob_counts or {}
    result = dict(assignments)

    # Capacité résiduelle après la phase principale (jamais négative).
    used: Dict[str, int] = {}
    for a in result.values():
        if a.kind in ("ASSIGNED", "STAY") and a.post_id:
            used[a.post_id] = used.get(a.post_id, 0) + 1
    remaining: Dict[str, int] = {
        pid: max(0, int(p.capacity) - used.get(pid, 0)) for pid, p in posts.items()
    }

    # Population à traiter : obligatoires non encore affectés sur un vœu.
    pending = [
        aid for aid, ag in agents.items()
        if getattr(ag, "participation", "volontaire") == "obligatoire"
        and result.get(aid) is not None
        and result[aid].kind != "ASSIGNED"
    ]
    if not pending:
        return result

    pending.sort(key=lambda aid: _order_key(
        agents[aid], aid, mob_counts, mob_threshold, campaign_seed))

    post_order = _extension_post_order(posts)
    order_index: Dict[str, int] = {pid: i for i, pid in enumerate(post_order)}

    # Postes sans exigence de titre : compatibles avec tout le monde -> curseur monotone.
    unrestricted: List[str] = [pid for pid in post_order if not posts[pid].required_titles]
    u_ptr = 0

    # Postes à exigence de titre : indexés par jeton de titre, tas ordonnés par position.
    token_heaps: Dict[str, List[Tuple[int, str]]] = {}
    for pid in post_order:
        req = posts[pid].required_titles
        if not req:
            continue
        idx = order_index[pid]
        for tok in req:
            token_heaps.setdefault(tok, []).append((idx, pid))
    for h in token_heaps.values():
        heapq.heapify(h)

    for aid in pending:
        ag = agents[aid]
        valid = mob_counts.get(aid, 0) >= mob_threshold

        # Candidat non restreint : premier poste libre du curseur monotone.
        while u_ptr < len(unrestricted) and remaining.get(unrestricted[u_ptr], 0) <= 0:
            u_ptr += 1
        cand_u: Optional[Tuple[int, str]] = None
        if u_ptr < len(unrestricted):
            pid_u = unrestricted[u_ptr]
            cand_u = (order_index[pid_u], pid_u)

        # Candidat restreint : premier poste libre compatible parmi les titres de l'agent.
        cand_r: Optional[Tuple[int, str]] = None
        for tok in set(ag.titles):
            h = token_heaps.get(tok)
            if not h:
                continue
            while h and remaining.get(h[0][1], 0) <= 0:
                heapq.heappop(h)
            if h and (cand_r is None or h[0][0] < cand_r[0]):
                cand_r = h[0]

        # Le poste retenu est celui de plus petite position dans l'ordre fixe.
        chosen: Optional[Tuple[int, str]] = None
        if cand_u is not None and cand_r is not None:
            chosen = cand_u if cand_u[0] < cand_r[0] else cand_r
        else:
            chosen = cand_u if cand_u is not None else cand_r

        if chosen is None:
            # Aucun poste vacant compatible : reste non affecté (cas dégénéré).
            result[aid] = Assignment(
                agent_id=aid, post_id=None, wish_rank=None, kind="UNASSIGNED",
            )
            continue

        pid = chosen[1]
        remaining[pid] -= 1
        result[aid] = Assignment(
            agent_id=aid, post_id=pid, wish_rank=None, kind="ASSIGNED",
            # demande valide non satisfaite -> provisoire ; incomplète -> définitive.
            chain_id="EXTENSION_PRO" if valid else "EXTENSION_TPD",
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
