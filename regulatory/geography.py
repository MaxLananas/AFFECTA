"""
Modèle géographique des communes de Guadeloupe.

Plusieurs règles réglementaires du mouvement dépendent de la géographie réelle :

  * rapprochement de conjoints (RC) : bonification conditionnée à une distance d'au moins
    40 km entre la résidence professionnelle de l'agent et celle du conjoint
    (REGULATORY_CONFIRMED — circulaires ac-lyon, ac-limoges, mémento ac-aix-marseille) ;
  * mesure de carte scolaire (MCS) : bonifications dégressives école -> commune
    d'exercice -> communes limitrophes (REGULATORY_CONFIRMED — circulaires ac-versailles,
    ac-lyon) ;
  * autorité parentale conjointe (APC) : rapprochement de la commune de résidence de
    l'enfant, mêmes mécanismes de proximité.

Ce module fournit :
  * `COMMUNES` : les 32 communes du département (source : datasets posts.json) ;
  * `ADJACENCY` : les communes limitrophes (frontière terrestre), HYPOTHESIS géographique
    documentée, dérivée de la carte administrative de la Guadeloupe ;
  * des coordonnées approximatives (centroïdes communaux, degrés décimaux) permettant un
    calcul de distance à vol d'oiseau (haversine) — HYPOTHESIS ; la réglementation impose
    un calcul routier (Mappy/Maps) que l'on ne peut reproduire hors ligne, la distance
    orthodromique en est une approximation conservatrice et déterministe.

Les valeurs géographiques sont des DONNÉES DE MODÉLISATION, jamais des règles : elles
alimentent le barème mais n'en fixent pas les montants. Les îles (Marie-Galante, La
Désirade, Les Saintes) n'ont aucune commune limitrophe terrestre — un fait, pas une
approximation.
"""
from __future__ import annotations

import math
from typing import Dict, FrozenSet, Tuple

# Centroïdes approximatifs (latitude, longitude) en degrés décimaux. HYPOTHESIS :
# positions issues des coordonnées publiques des chefs-lieux communaux, arrondies.
_COORDS: Dict[str, Tuple[float, float]] = {
    "ANSE BERTRAND": (16.475, -61.505),
    "BAIE MAHAULT": (16.267, -61.588),
    "BAILLIF": (16.020, -61.750),
    "BASSE TERRE": (15.998, -61.727),
    "BOUILLANTE": (16.132, -61.769),
    "CAPESTERRE BELLE EAU": (16.045, -61.565),
    "CAPESTERRE MARIE GALANTE": (15.900, -61.222),
    "DESHAIES": (16.303, -61.795),
    "GOURBEYRE": (15.985, -61.688),
    "GOYAVE": (16.130, -61.573),
    "GRAND BOURG": (15.883, -61.315),
    "LA DESIRADE": (16.303, -61.085),
    "LAMENTIN": (16.270, -61.635),
    "LE GOSIER": (16.207, -61.492),
    "LE MOULE": (16.333, -61.348),
    "LES ABYMES": (16.271, -61.505),
    "MORNE A L EAU": (16.335, -61.512),
    "PETIT BOURG": (16.190, -61.593),
    "PETIT CANAL": (16.378, -61.485),
    "POINTE A PITRE": (16.241, -61.533),
    "POINTE NOIRE": (16.235, -61.790),
    "PORT LOUIS": (16.420, -61.532),
    "ST CLAUDE": (16.023, -61.702),
    "ST FRANCOIS": (16.252, -61.270),
    "ST LOUIS": (15.960, -61.310),
    "STE ANNE": (16.227, -61.380),
    "STE ROSE": (16.330, -61.697),
    "TERRE DE BAS": (15.855, -61.638),
    "TERRE DE HAUT": (15.867, -61.583),
    "TROIS RIVIERES": (15.973, -61.640),
    "VIEUX FORT": (15.948, -61.700),
    "VIEUX HABITANTS": (16.058, -61.767),
}

COMMUNES: FrozenSet[str] = frozenset(_COORDS)

# Communes limitrophes par frontière terrestre. HYPOTHESIS géographique dérivée de la
# carte administrative (Grande-Terre, Basse-Terre). Les communes insulaires détachées
# (Marie-Galante, La Désirade, Les Saintes) n'ont aucune limitrophe terrestre.
_ADJACENCY_RAW: Dict[str, Tuple[str, ...]] = {
    # Grande-Terre
    "ANSE BERTRAND": ("PORT LOUIS", "PETIT CANAL"),
    "PORT LOUIS": ("ANSE BERTRAND", "PETIT CANAL"),
    "PETIT CANAL": ("ANSE BERTRAND", "PORT LOUIS", "MORNE A L EAU", "LE MOULE"),
    "MORNE A L EAU": ("PETIT CANAL", "LES ABYMES", "LE MOULE"),
    "LE MOULE": ("PETIT CANAL", "MORNE A L EAU", "STE ANNE", "LES ABYMES"),
    "LES ABYMES": ("MORNE A L EAU", "LE MOULE", "STE ANNE", "LE GOSIER", "POINTE A PITRE", "BAIE MAHAULT"),
    "POINTE A PITRE": ("LES ABYMES", "LE GOSIER", "BAIE MAHAULT"),
    "LE GOSIER": ("LES ABYMES", "POINTE A PITRE", "STE ANNE"),
    "STE ANNE": ("LE GOSIER", "LES ABYMES", "LE MOULE", "ST FRANCOIS"),
    "ST FRANCOIS": ("STE ANNE",),
    # jonction Grande-Terre / Basse-Terre par le pont de la Gabarre
    "BAIE MAHAULT": ("LES ABYMES", "POINTE A PITRE", "LAMENTIN", "PETIT BOURG"),
    "LAMENTIN": ("BAIE MAHAULT", "STE ROSE", "PETIT BOURG"),
    "STE ROSE": ("LAMENTIN", "DESHAIES", "PETIT BOURG", "POINTE NOIRE"),
    "DESHAIES": ("STE ROSE", "POINTE NOIRE"),
    "POINTE NOIRE": ("DESHAIES", "STE ROSE", "BOUILLANTE"),
    "BOUILLANTE": ("POINTE NOIRE", "VIEUX HABITANTS"),
    "VIEUX HABITANTS": ("BOUILLANTE", "BAILLIF"),
    "BAILLIF": ("VIEUX HABITANTS", "BASSE TERRE", "ST CLAUDE"),
    "BASSE TERRE": ("BAILLIF", "ST CLAUDE", "GOURBEYRE"),
    "ST CLAUDE": ("BASSE TERRE", "BAILLIF", "GOURBEYRE"),
    "GOURBEYRE": ("BASSE TERRE", "ST CLAUDE", "TROIS RIVIERES", "CAPESTERRE BELLE EAU"),
    "TROIS RIVIERES": ("GOURBEYRE", "CAPESTERRE BELLE EAU", "VIEUX FORT"),
    "VIEUX FORT": ("TROIS RIVIERES",),
    "CAPESTERRE BELLE EAU": ("TROIS RIVIERES", "GOURBEYRE", "GOYAVE"),
    "GOYAVE": ("CAPESTERRE BELLE EAU", "PETIT BOURG"),
    "PETIT BOURG": ("GOYAVE", "BAIE MAHAULT", "LAMENTIN", "STE ROSE"),
    # Marie-Galante
    "GRAND BOURG": ("CAPESTERRE MARIE GALANTE", "ST LOUIS"),
    "CAPESTERRE MARIE GALANTE": ("GRAND BOURG", "ST LOUIS"),
    "ST LOUIS": ("GRAND BOURG", "CAPESTERRE MARIE GALANTE"),
    # Les Saintes
    "TERRE DE HAUT": ("TERRE DE BAS",),
    "TERRE DE BAS": ("TERRE DE HAUT",),
    # La Désirade : isolée
    "LA DESIRADE": (),
}

ADJACENCY: Dict[str, FrozenSet[str]] = {
    c: frozenset(_ADJACENCY_RAW.get(c, ())) for c in COMMUNES
}


def _norm(name: str | None) -> str | None:
    if not name:
        return None
    return name.strip().upper()


def haversine_km(a: str, b: str) -> float:
    """Distance orthodromique approximative (km) entre deux communes.

    HYPOTHESIS : approximation à vol d'oiseau de la distance routière exigée par les
    textes. Renvoie 0.0 pour une commune vers elle-même, +inf si l'une est inconnue.
    """
    a, b = _norm(a), _norm(b)
    if a is None or b is None or a not in _COORDS or b not in _COORDS:
        return float("inf")
    if a == b:
        return 0.0
    lat1, lon1 = _COORDS[a]
    lat2, lon2 = _COORDS[b]
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def are_adjacent(a: str, b: str) -> bool:
    """True si b est limitrophe de a (frontière terrestre)."""
    a, b = _norm(a), _norm(b)
    if a is None or b is None:
        return False
    return b in ADJACENCY.get(a, frozenset())


def same_commune(a: str, b: str) -> bool:
    a, b = _norm(a), _norm(b)
    return a is not None and a == b


def commune_proximity(a: str, b: str) -> str:
    """Classe la proximité de b relativement à a.

    Renvoie 'SAME' | 'ADJACENT' | 'FAR' | 'UNKNOWN'. Sert de base commune aux
    mécanismes MCS (dégressif) et RC/APC (seuil de distance).
    """
    a, b = _norm(a), _norm(b)
    if a is None or b is None or a not in COMMUNES or b not in COMMUNES:
        return "UNKNOWN"
    if a == b:
        return "SAME"
    if b in ADJACENCY.get(a, frozenset()):
        return "ADJACENT"
    return "FAR"
