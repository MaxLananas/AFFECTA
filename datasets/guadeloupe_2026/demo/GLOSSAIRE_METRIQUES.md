# AFFECTA-DEMO-2026-08-11 — Glossaire et métriques (cadre verrouillé)

Ce document fixe le vocabulaire public de la démo.  
**Aucun chiffre n’est recalculé.** Les valeurs chiffrées restent celles de `demo_report.json`.

---

## Ce qui est factuel (ne pas modifier)

| Élément | Valeur |
|---------|--------|
| Version | AFFECTA-DEMO-2026-08-11 |
| Seed | 20260811 |
| Agents simulés | 1 200 |
| Supports (lignes PDF) | 1 310 |
| Groupes | 435 |
| Unités de capacité | 2 654 |
| Vœux | **entièrement synthétiques** |
| Postes / groupes | issus des 4 PDF hashés |
| optimality | **UNKNOWN** pour toutes les méthodes |
| Nature du projet | prototype expérimental, **pas MVT1D** |
| TEACHER / BALANCED / COVERAGE | **PRODUCT_POLICY** (choix expérimentaux) |

---

## Vocabulaire obligatoire

| Terme | Sens dans la démo | Ne pas dire |
|-------|-------------------|-------------|
| **Support** | Ligne de `posts.json` (1 310) | « école » par défaut |
| **Unité de capacité** | Poste unitaire après éventuel découpage `#k` (2 654) | « établissement » |
| **Base (Coverage v3)** | Agrégat des unités d’un même id support | « établissement administratif » |
| **Établissement (libellé PDF)** | Champ texte `etablissement` du document source | confondu avec *base* |
| **Groupe** | Entrée de `groups.json` ; composition interne souvent UNKNOWN | ensemble libre de postes sans réserve |
| **Affectation** | Agent → unité avec `kind=ASSIGNED` | |

**Règle :** ne plus écrire « établissements vides » pour la métrique Coverage v3.

**Formulation correcte :**  
« **346 bases de support à remplissage nul** selon la métrique Coverage v3. »  

**Formulation pédagogique :**  
« Cette métrique est un **proxy interne de couverture**. Une *base* AFFECTA n’est **pas** nécessairement une école au sens administratif. »

---

## Définitions des métriques publiables

| Métrique | Définition figée | Notes |
|----------|------------------|-------|
| `assigned` | Nombre d’agents avec `kind=ASSIGNED` | Démo : **1 199 / 1 200** (1 non affecté) |
| `voeu1` | Affectés avec `wish_rank=1` | |
| `top3` | Affectés avec `wish_rank ∈ {1,2,3}` | |
| `avg_rank` | Moyenne des `wish_rank` des seuls ASSIGNED | |
| `empty` (AFFECTA v3) | Nombre de **bases** avec fill=0 | **Pas** comparable à NAIVE/LIBERATION |
| `under_50` (AFFECTA v3) | Bases cap≥2 et fill/cap ≤ 0,5 | Proxy CRITICAL |
| `cost_per_severity_gain` | Coût satisfaction / gain de sévérité (DESIGN_DECISION) | 0,286 BALANCED · 0,493 COVERAGE |
| `optimality` | Toujours UNKNOWN ici | Ne jamais écrire OPTIMAL |
| `result_hash` | Empreinte de reproductibilité de la solution | Pas une preuve réglementaire |

### Interdiction publique

Ne **jamais** présenter côte à côte :

- NAIVE `empty=32` et TEACHER `empty=346`

Ces deux nombres **ne mesurent pas la même chose** (définition et code de calcul différents).

Pour NAIVE et LIBERATION, **ne pas publier** de colonne « vides » issue de Coverage v3.

---

## Résultats figés (seed 20260811) — tableau autorisé

| Méthode | Affectés | Vœu 1 | Top 3 | Rang moy. | Bases vides (v3) | under_50 (v3) | Temps | Preuve |
|---------|----------|-------|-------|-----------|------------------|---------------|-------|--------|
| NAIVE | 239 | 30 | 78 | 6,66 | *non comparable* | *non comparable* | 4 ms | UNKNOWN |
| LIBERATION | 1 089 | 146 | 405 | 5,78 | *non comparable* | *non comparable* | 268 ms | UNKNOWN |
| AFFECTA TEACHER | **1 199** | **405** | **831** | **3,12** | **346** | 278 | 519 ms | UNKNOWN |
| AFFECTA BALANCED | 1 199 | 307 | 720 | 3,81 | **286** | 299 | 967 ms | UNKNOWN |
| AFFECTA COVERAGE | 1 199 | 283 | 679 | 3,98 | **274** | 299 | 981 ms | UNKNOWN |

Compromis TEACHER → COVERAGE (même métrique v3 uniquement) :

- **−122** vœux n°1  
- **−72** bases à remplissage nul (proxy v3)  
- cost/gain COVERAGE = **0,493**

---

## Performance — formulations autorisées

**Autorisé :**  
« Sur la démo figée (1 200 agents, postes Guadeloupe 2026, vœux synthétiques), AFFECTA TEACHER s’exécute en environ **519 ms**. »

**Autorisé :**  
« Sur une **instance synthétique distincte** de 10 000 agents, le chemin TEACHER a été mesuré autour de **4 secondes**. »

**Interdit :**  
« AFFECTA traite 10 000 enseignants du mouvement Guadeloupe en 4 secondes. »

---

## Dossier D3 — formulation verrouillée

**Ne pas présenter comme preuve complète de causalité.**

Formulation rigoureuse :

> Dans l’état final, un autre agent occupe le poste demandé.  
> D’après le scorer réglementaire **du prototype**, le dossier A00003 serait mieux ordonné que le titulaire final sur ce poste.  
> L’état final résulte néanmoins d’une **optimisation** (chaînes et/ou PRODUCT_POLICY).  
> **Le journal exact de la décision n’est pas disponible dans cette démo.**  
> Catégorie : OPTIMISATION — preuve partielle (reconstruction a posteriori, pas trace d’exécution).

---

## Message central autorisé

> Voici exactement ce que notre prototype produit, les objectifs que nous pouvons comparer, les compromis observés, les motifs que nous savons expliquer, et les choses que nous ne sommes pas capables de prouver.

**Pas :** « AFFECTA est meilleur / officiel / optimal / conforme MVT1D. »
