"""
Why-not explanations for professors.

Never invent a reason. If the engine cannot prove why a candidate lost,
emit EXPLICATION_INSUFFISANTE.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry


def why_not_wish(
    agent_id: str,
    wish_rank: int,
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    assignments: Dict[str, Assignment],
    *,
    decision_log: Optional[List[dict]] = None,
) -> dict:
    agent = agents[agent_id]
    my_wishes = wishes.get(agent_id, [])
    target = next((w for w in my_wishes if w.rank == wish_rank), None)
    result = {
        "agent": agent_id,
        "asked_wish_rank": wish_rank,
        "assigned_post": assignments[agent_id].post_id if agent_id in assignments else None,
        "assigned_kind": assignments[agent_id].kind if agent_id in assignments else None,
        "assigned_wish_rank": assignments[agent_id].wish_rank if agent_id in assignments else None,
        "explanations": [],
    }
    if target is None:
        result["explanations"].append({
            "reason": "WISH_NOT_IN_LIST",
            "category": "FAIT",
        })
        return result

    reg = guadeloupe_registry()
    for pid in target.post_ids:
        if pid not in posts:
            result["explanations"].append({
                "post": pid,
                "reason": "UNKNOWN_POST",
                "category": "FAIT",
            })
            continue
        post = posts[pid]
        my_score = score_candidate(agent, post, target, reg)
        if not my_score.eligible:
            result["explanations"].append({
                "post": pid,
                "eligible": False,
                "reason": my_score.rejection_reason or "NOT_ELIGIBLE",
                "category": "REGLEMENTAIRE",
            })
            continue

        holder = None
        for aid, asn in assignments.items():
            if asn.kind == "ASSIGNED" and asn.post_id == pid:
                holder = aid
                break

        if holder is None:
            if not post.vacant and post.holder_id:
                result["explanations"].append({
                    "post": pid,
                    "eligible": True,
                    "reason": "POST_NOT_LIBERATED",
                    "holder_stayed": post.holder_id,
                    "category": "DISPONIBILITE",
                })
            else:
                result["explanations"].append({
                    "post": pid,
                    "eligible": True,
                    "reason": "EXPLICATION_INSUFFISANTE",
                    "detail": "Poste disponible non attribue; motif non reconstructible sans journal de decision.",
                    "category": "INSUFFISANT",
                })
            continue

        if holder == agent_id:
            result["explanations"].append({
                "post": pid,
                "reason": "YOU_GOT_THIS_POST",
                "category": "FAIT",
            })
            continue

        holder_agent = agents[holder]
        holder_wishes = wishes.get(holder, [])
        holder_wish = None
        for w in holder_wishes:
            if pid in w.post_ids:
                holder_wish = w
                break
        if holder_wish is None:
            result["explanations"].append({
                "post": pid,
                "eligible": True,
                "reason": "EXPLICATION_INSUFFISANTE",
                "detail": "Titulaire sans voeu trace sur ce poste; comparaison reglementaire impossible.",
                "concurrent": holder,
                "category": "INSUFFISANT",
            })
            continue

        h_score = score_candidate(holder_agent, post, holder_wish, reg)
        my_key = my_score.regulatory_key()
        h_key = h_score.regulatory_key()

        if h_key < my_key:
            result["explanations"].append({
                "post": pid,
                "eligible": True,
                "reason": "CONCURRENT_MIEUX_CLASSE",
                "category": "REGLEMENTAIRE",
                "concurrent": holder,
                "votre_priorite": my_score.priority_rank,
                "votre_bareme": my_score.bareme,
                "votre_rang_voeu": my_score.wish_rank,
                "concurrent_priorite": h_score.priority_rank,
                "concurrent_bareme": h_score.bareme,
                "concurrent_rang_voeu": h_score.wish_rank,
            })
        elif h_key == my_key:
            result["explanations"].append({
                "post": pid,
                "eligible": True,
                "reason": "DEPARTAGE_EGALITE",
                "category": "REGLEMENTAIRE",
                "concurrent": holder,
                "votre_priorite": my_score.priority_rank,
                "votre_bareme": my_score.bareme,
                "concurrent_priorite": h_score.priority_rank,
                "concurrent_bareme": h_score.bareme,
                "detail": "Scores reglementaires identiques; departage deterministe ou regle UNKNOWN.",
            })
        else:
            result["explanations"].append({
                "post": pid,
                "eligible": True,
                "reason": "DECISION_OPTIMISATION",
                "category": "OPTIMISATION",
                "concurrent": holder,
                "votre_priorite": my_score.priority_rank,
                "votre_bareme": my_score.bareme,
                "votre_rang_voeu": my_score.wish_rank,
                "concurrent_priorite": h_score.priority_rank,
                "concurrent_bareme": h_score.bareme,
                "concurrent_rang_voeu": h_score.wish_rank,
                "detail": (
                    "Selon le classement reglementaire seul, votre dossier etait mieux place. "
                    "Le poste a neanmoins ete attribue dans le cadre d'une optimisation "
                    "(chaine de liberation ou politique de couverture)."
                ),
            })
    return result


def format_why_not(info: dict) -> str:
    lines = [
        "MON AFFECTATION",
        f"  Agent              {info['agent']}",
        f"  Affecte a          {info['assigned_post']}",
        f"  Rang obtenu        {info['assigned_wish_rank']}",
        f"  Statut             {info['assigned_kind']}",
        "",
        f"Pourquoi pas le voeu n°{info['asked_wish_rank']} ?",
        "",
    ]
    for e in info["explanations"]:
        if "post" in e:
            lines.append(f"  Poste {e['post']}")
        reason = e.get("reason")
        cat = e.get("category", "")
        if reason == "CONCURRENT_MIEUX_CLASSE":
            lines.append(f"    Motif     : un autre candidat a ete mieux classe")
            lines.append(f"    Categorie : {cat}")
            lines.append(f"    Concurrent: {e.get('concurrent')}")
            lines.append(f"    Votre priorite / bareme     : {e.get('votre_priorite')} / {e.get('votre_bareme')}")
            lines.append(f"    Concurrent priorite / bareme: {e.get('concurrent_priorite')} / {e.get('concurrent_bareme')}")
        elif reason == "POST_NOT_LIBERATED":
            lines.append(f"    Motif     : le poste n'a pas ete libere par son titulaire")
            lines.append(f"    Categorie : {cat}")
        elif reason == "DECISION_OPTIMISATION":
            lines.append(f"    Motif     : decision d'optimisation (pas un classement purement reglementaire)")
            lines.append(f"    Categorie : {cat}")
            if e.get("detail"):
                lines.append(f"    Detail    : {e['detail']}")
        elif reason == "EXPLICATION_INSUFFISANTE":
            lines.append(f"    Motif     : EXPLICATION_INSUFFISANTE")
            lines.append(f"    Categorie : {cat}")
            if e.get("detail"):
                lines.append(f"    Detail    : {e['detail']}")
        elif reason == "DEPARTAGE_EGALITE":
            lines.append(f"    Motif     : egalite de score — departage")
            lines.append(f"    Categorie : {cat}")
        elif e.get("eligible") is False:
            lines.append(f"    Eligible  : NON")
            lines.append(f"    Motif     : {reason}")
        else:
            lines.append(f"    Motif     : {reason}")
            if e.get("detail"):
                lines.append(f"    Detail    : {e['detail']}")
        lines.append("")
    return "\n".join(lines)
