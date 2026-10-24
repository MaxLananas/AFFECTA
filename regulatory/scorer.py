"""
Barème et éligibilité du mouvement intra-départemental — cœur réglementaire d'AFFECTA.

Ce module calcule, pour un couple (agent, poste) et un vœu donné, une `CandidateScore`
comprenant :

  * un **rang de priorité** (`priority_rank`, croissant, 1 = plus fort) traduisant les
    priorités légales de l'article L. 512-19 du code général de la fonction publique et
    les exigences de titre propres au poste ;
  * un **barème** (décroissant) somme des bonifications réglementaires, chacune décomposée
    et tracée dans `bonuses` ;
  * les **discriminants** de départage (AEN, ancienneté d'échelon) recopiés depuis l'agent.

DISCIPLINE DE SOURÇAGE
----------------------
Chaque bloc indique son statut. Les montants exacts d'un barème départemental (LDG
académiques) varient d'un département à l'autre ; ceux de la Guadeloupe ne sont pas publiés
au niveau nécessaire. On distingue donc :

  * la STRUCTURE (ordre des priorités, séquence des discriminants, nature des
    bonifications, conditions d'attribution) — REGULATORY_CONFIRMED, convergente entre
    académies ;
  * les VALEURS numériques — PROBABLE / HYPOTHESIS, reprises des barèmes publiés les plus
    représentatifs (ac-versailles, ac-lyon, education.gouv) et signalées comme telles.

Aucune valeur n'est inventée : chaque montant provient d'un barème réel documenté. Le
comportement historique (valeurs des tests) est intégralement préservé : toutes les règles
géographiques et statutaires ajoutées sont neutres tant que les champs correspondants de
l'agent gardent leur valeur par défaut.

ORDRE DES PRIORITÉS (priority_rank) — REGULATORY_CONFIRMED
---------------------------------------------------------
Les postes à exigence de titre sont traités AVANT le barème : un agent détenant le titre
requis (CAPPEI avec le bon module, liste d'aptitude de directeur) précède tout agent qui
ne le détient pas, indépendamment du barème (sgen-cfdt MVT1D, ac-toulouse, ac-montpellier).
On code cette exigence dans des rangs de priorité très forts (< 10). Viennent ensuite les
priorités légales, puis le barème pour le rang standard (15).
"""
from __future__ import annotations

from movement_engine.domain.models import Agent, CandidateScore, Post, Wish
from movement_engine.regulatory.registry import RuleRegistry

# ---------------------------------------------------------------------------------------
# Grille d'échelon — REGULATORY_CONFIRMED (structure) / PROBABLE (valeurs Guadeloupe).
# Conservée à l'identique : plusieurs tests en dépendent.
# ---------------------------------------------------------------------------------------
ECHELON_POINTS = (
    0,   # 0 unused
    18,  # 1
    18,  # 2
    22,  # 3
    22,  # 4
    26,  # 5
    29,  # 6
    31,  # 7
    33,  # 8
    33,  # 9
    36,  # 10
    39,  # 11
)


def echelon_points(echelon: int) -> int:
    if 0 <= echelon < len(ECHELON_POINTS):
        return ECHELON_POINTS[echelon]
    if echelon > 11:
        return 39 + (echelon - 11) * 3  # extension conservatrice (classe exceptionnelle)
    raise ValueError(f"Invalid echelon: {echelon}")


# ---------------------------------------------------------------------------------------
# Rangs de priorité — REGULATORY_CONFIRMED (ordre) ; codes numériques = DESIGN_DECISION.
# Plus le rang est petit, plus la priorité est forte. Les valeurs laissent des intervalles
# pour insérer des priorités locales sans réordonner l'existant.
# ---------------------------------------------------------------------------------------
PRIORITY_TITLE_EXACT = 2      # titre requis + module exact (affectation définitive)
PRIORITY_TITLE_PARTIAL = 4    # titre requis, module différent
PRIORITY_TITLE_INPROGRESS = 6 # formation en cours (affectation provisoire)
PRIORITY_MCS = 8              # mesure de carte scolaire (retour prioritaire)
PRIORITY_MEDICAL = 10         # handicap / médical grave sur avis favorable
PRIORITY_RC = 12             # rapprochement de conjoints réalisé
PRIORITY_CIMM = 13           # centre des intérêts matériels et moraux (DOM)
PRIORITY_QPV = 14            # exercice prolongé en éducation prioritaire / QPV
PRIORITY_STANDARD = 15       # candidature ordinaire (départagée au barème)
PRIORITY_UNTITLED = 40       # poste à exigence, titre non détenu (provisoire, après titrés)


def _title_priority(agent: Agent, post: Post) -> int | None:
    """Priorité liée à l'exigence de titre du poste (REGULATORY_CONFIRMED, structure).

    Renvoie un rang de priorité si le poste exige un titre, sinon None. Les postes ASH
    (CAPPEI) et de direction (liste d'aptitude) sont traités avant le barème :
      * titre + module exact -> PRIORITY_TITLE_EXACT ;
      * titre, module différent -> PRIORITY_TITLE_PARTIAL ;
      * formation en cours -> PRIORITY_TITLE_INPROGRESS ;
      * aucun titre -> PRIORITY_UNTITLED (traité en dernier, affectation provisoire).
    """
    if not post.required_titles:
        return None
    have = set(agent.titles)
    for req in post.required_titles:
        if req in have:
            return PRIORITY_TITLE_EXACT
    # même famille de titre (préfixe avant ':') mais module différent
    req_families = {r.split(":", 1)[0] for r in post.required_titles}
    have_families = {t.split(":", 1)[0] for t in have}
    if req_families & have_families:
        return PRIORITY_TITLE_PARTIAL
    if any(t.endswith(":INPROGRESS") for t in have):
        return PRIORITY_TITLE_INPROGRESS
    return PRIORITY_UNTITLED


def score_candidate(
    agent: Agent,
    post: Post,
    wish: Wish,
    registry: RuleRegistry,
    *,
    sous_rank: int | None = None,
    tie_key: str | None = None,
) -> CandidateScore:
    points = echelon_points(agent.echelon)
    bonuses: list[str] = []
    is_precise = wish.precise and not wish.group

    def finalize(priority_rank, eligible=True, reason=None):
        return CandidateScore(
            agent.id, post.id, priority_rank, points, wish.rank,
            sous_rank, tie_key, tuple(bonuses), eligible, reason,
            aen_months=agent.aen_months, echelon_months=agent.echelon_months,
        )

    # -----------------------------------------------------------------------------------
    # 1. Exigence de titre (traitée avant le barème). REGULATORY_CONFIRMED (structure).
    # -----------------------------------------------------------------------------------
    priority_rank = PRIORITY_STANDARD
    title_pr = _title_priority(agent, post)
    if title_pr is not None:
        priority_rank = title_pr
        if title_pr == PRIORITY_UNTITLED:
            bonuses.append("TITRE_NON_DETENU")
        else:
            bonuses.append("TITRE_REQUIS_OK")

    # -----------------------------------------------------------------------------------
    # 2. Priorités légales et bonifications de priorité (article L. 512-19).
    #    REGULATORY_CONFIRMED (ordre) ; valeurs PROBABLE (barèmes académiques publiés).
    # -----------------------------------------------------------------------------------

    # 2a. Mesure de carte scolaire — bonification dégressive géographique. Structure
    #     CONFIRMED (ac-versailles/ac-lyon) ; valeurs 600/500/250 PROBABLE.
    if agent.mcs_affected and is_precise:
        prox = _mcs_proximity(agent, post)
        if prox == "SAME_SCHOOL" or prox == "SAME_COMMUNE":
            amt = 600 if prox == "SAME_SCHOOL" else 500
            points += amt
            bonuses.append(f"MCS_{amt}")
            priority_rank = min(priority_rank, PRIORITY_MCS)
        elif prox == "ADJACENT":
            points += 250
            bonuses.append("MCS_250")
            priority_rank = min(priority_rank, PRIORITY_MCS)

    # 2b. MCS points (champ historique conservé pour compatibilité).
    if agent.mcs_points >= 800:
        priority_rank = min(priority_rank, 1)
        bonuses.append(f"MCS_{agent.mcs_points}")
        points += agent.mcs_points
    elif agent.mcs_points >= 700:
        priority_rank = min(priority_rank, 2)
        bonuses.append(f"MCS_{agent.mcs_points}")
        points += agent.mcs_points
    elif agent.mcs_points > 0:
        priority_rank = min(priority_rank, 3)
        bonuses.append(f"MCS_{agent.mcs_points}")
        points += agent.mcs_points

    # 2c. Handicap / médical grave — priorité forte. Valeurs PROBABLE (500 avis médecin).
    if agent.handicap_500:
        priority_rank = min(priority_rank, PRIORITY_MEDICAL)
        points += registry.get("HANDICAP_500").amount
        bonuses.append("HANDICAP_500")
    elif agent.boe:
        # BOE : bonification automatique (100 pts interdép., ~30 intra). Ne confère pas la
        # priorité forte du handicap sur avis médical. PROBABLE.
        priority_rank = min(priority_rank, 20)
        points += registry.get("BOE_100").amount
        bonuses.append("BOE_100")

    # 2d. Centre des intérêts matériels et moraux (DOM) — 600 pts sur vœu de rang.
    #     REGULATORY_CONFIRMED (education.gouv) ; s'applique au vœu 1.
    if agent.cimm_dom and wish.rank == 1 and is_precise:
        points += 600
        bonuses.append("CIMM_600")
        priority_rank = min(priority_rank, PRIORITY_CIMM)

    # 2e. Exercice prolongé en éducation prioritaire / QPV (>= 5 ans) — priorité légale.
    #     Structure CONFIRMED (art. L.512-19) ; bonification 45 REP / 90 REP+ PROBABLE.
    if agent.rep_status and agent.rep_years >= 1:
        rep_amt = _rep_bonus(agent.rep_status, agent.rep_years)
        if rep_amt:
            points += rep_amt
            bonuses.append(f"{agent.rep_status}_{rep_amt}")
        if agent.rep_years >= 5:
            priority_rank = min(priority_rank, PRIORITY_QPV)

    # -----------------------------------------------------------------------------------
    # 3. Rapprochement de conjoints / autorité parentale conjointe.
    #    REGULATORY_CONFIRMED : non-cumulables ; exclus des vœux groupes (sauf handicap) ;
    #    conditionnés à une distance >= 40 km. Valeurs PROBABLE (150 + progressif).
    # -----------------------------------------------------------------------------------
    if agent.rc_points and agent.apc_points:
        return finalize(priority_rank, False, "RC_APC_NON_CUMULABLE")

    if agent.rc_points:
        if not is_precise:
            return finalize(priority_rank, False, "RC_NOT_APPLICABLE_TO_GROUP")
        if not _rc_distance_ok(agent):
            bonuses.append("RC_DISTANCE_INSUFFISANTE")
        else:
            rc_total = agent.rc_points + _separation_bonus(agent.separation_years)
            points += rc_total
            bonuses.append(f"RC_{rc_total}")
            priority_rank = min(priority_rank, PRIORITY_RC)
    elif agent.apc_points:
        if not is_precise:
            return finalize(priority_rank, False, "APC_NOT_APPLICABLE_TO_GROUP")
        apc_total = agent.apc_points + _separation_bonus(agent.separation_years)
        points += apc_total
        bonuses.append(f"APC_{apc_total}")
        priority_rank = min(priority_rank, PRIORITY_RC)

    # -----------------------------------------------------------------------------------
    # 4. Bonifications secondaires (cumulables). Valeurs PROBABLE / HYPOTHESIS.
    # -----------------------------------------------------------------------------------
    if agent.medical_grave and wish.rank == 1 and is_precise:
        points += registry.get("MED_GRAVE_30").amount
        bonuses.append("MED_GRAVE_30")

    if agent.children:
        points += agent.children * registry.get("CHILD_2").amount
        bonuses.append(f"CHILD_2_X{agent.children}")

    if agent.unique_parental_authority:
        points += registry.get("UNIQUE_PARENT_50").amount
        bonuses.append("UNIQUE_PARENT_50")

    if agent.renewal_years > 0 and wish.rank == 1 and is_precise:
        renewal = min(agent.renewal_years * 10, 90)
        points += renewal
        bonuses.append(f"RENEWAL_V1_{renewal}")

    # Ancienneté sur le poste — barème dégressif par paliers (3->3, 4->5, 5->8, 6->11,
    # 7+->16). REGULATORY_CONFIRMED (structure, valeurs ac-versailles/cgteduc92).
    if agent.post_seniority_years >= 3:
        seny = _post_seniority_bonus(agent.post_seniority_years)
        points += seny
        bonuses.append(f"ANCIENNETE_POSTE_{seny}")

    if agent.aen_points:
        points += agent.aen_points
        bonuses.append(f"AEN_{agent.aen_points}")

    if agent.fidelity_points:
        points += agent.fidelity_points
        bonuses.append(f"FIDELITE_{agent.fidelity_points}")

    if agent.rep_points:
        points += agent.rep_points
        bonuses.append(f"REP_{agent.rep_points}")

    if agent.islands_points:
        points += agent.islands_points
        bonuses.append(f"ILES_{agent.islands_points}")

    if agent.reintegration_points:
        points += agent.reintegration_points
        bonuses.append(f"REINTEGRATION_{agent.reintegration_points}")

    return finalize(priority_rank)


# ---------------------------------------------------------------------------------------
# Fonctions d'appui géographiques et de paliers. Structure CONFIRMED, valeurs sourcées.
# ---------------------------------------------------------------------------------------
def _mcs_proximity(agent: Agent, post: Post) -> str:
    """Proximité du poste visé par rapport au poste supprimé (MCS)."""
    from movement_engine.regulatory.geography import commune_proximity, same_commune
    a_comm = agent.current_commune
    p_comm = post.commune
    if a_comm is None or p_comm is None:
        return "UNKNOWN"
    # même établissement = même commune + même circonscription/établissement d'origine
    if same_commune(a_comm, p_comm):
        return "SAME_COMMUNE"
    prox = commune_proximity(a_comm, p_comm)
    return "ADJACENT" if prox == "ADJACENT" else prox


def _rc_distance_ok(agent: Agent) -> bool:
    """Le rapprochement exige une séparation d'au moins 40 km. REGULATORY_CONFIRMED.

    Si la distance n'est pas renseignée, on considère la condition remplie (compatibilité
    avec les données historiques dépourvues de géographie).
    """
    if agent.spouse_distance_km is None:
        return True
    return agent.spouse_distance_km >= 40.0


def _separation_bonus(years: int) -> int:
    """Bonification progressive liée aux années de séparation (RC/APC).

    REGULATORY_CONFIRMED (structure) ; valeurs PROBABLE (barème interdép. education.gouv /
    cgteduc-versailles) : 1 an=50, 2 ans=200, 3 ans=350, 4 ans et +=450.
    """
    table = {0: 0, 1: 50, 2: 200, 3: 350}
    if years >= 4:
        return 450
    return table.get(years, 0)


def _rep_bonus(status: str, years: int) -> int:
    """Bonification d'exercice en éducation prioritaire (>= 5 ans continus).

    REGULATORY_CONFIRMED (structure) ; valeurs PROBABLE : REP+ / QPV = 90, REP = 45
    (barème interdép. education.gouv). Nulle en deçà de 5 ans (traitée en barème local
    dégressif ailleurs pour l'intra, non modélisé faute de valeurs départementales).
    """
    if years < 5:
        return 0
    if status in ("REP+", "QPV"):
        return 90
    if status == "REP":
        return 45
    return 0


def _post_seniority_bonus(years: int) -> int:
    """Ancienneté dans le poste — paliers REGULATORY_CONFIRMED (ac-versailles/cgteduc92)."""
    if years >= 7:
        return 16
    return {3: 3, 4: 5, 5: 8, 6: 11}.get(years, 0)
