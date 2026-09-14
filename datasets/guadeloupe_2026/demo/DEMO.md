# AFFECTA — Démonstration de bout en bout

**Version figée :** AFFECTA-DEMO-2026-08-11  
**Seed :** 20260811  
**Cadre verrouillé :** voir `GLOSSAIRE_METRIQUES.md`  
**Reproductible :** `demo_report.json` + hashes de résultat  

---

## 1. Le problème en une minute

Chaque année, des milliers de professeurs des écoles demandent une mutation
intra-départementale. Le système doit :

1. respecter les règles réglementaires connues ;
2. affecter le plus de professeurs possible ;
3. respecter au mieux leurs vœux ;
4. limiter les situations de sous-effectif dans le modèle ;
5. le faire **rapidement** ;
6. pouvoir **expliquer** chaque décision.

Ces objectifs peuvent entrer en conflit. Il n’existe pas une unique « bonne »
affectation magique.

---

## 2. Les données de cette démo

| Élément | Valeur |
|---------|--------|
| Périmètre | Intra-départemental 1D · Guadeloupe 2026 |
| Supports (PDF) | **1 310** |
| Groupes | **435** |
| Unités de capacité | **2 654** |
| Professeurs | **1 200 simulés** |
| Vœux | **entièrement synthétiques**, max 20 |
| Seed | **20260811** |

**Sources PDF (SHA-256) :**

| Document | Hash |
|----------|------|
| VOEUX PRECIS | `dc8163839d3ee21d…ba44448f` |
| ASSIMILES COMMUNES | `9dcf9a997b9b57d5…f3077bcc` |
| AUTRE MOB | `b41e27879d0e4fc3…d5b20428` |
| AUTRE ZONE | `ea961866487c3eff…baf2253b` |

> **Les vœux des professeurs de cette démo sont SYNTHÉTIQUES.**  
> Ce ne sont pas les vœux réels du mouvement 2026.  
> **AFFECTA n’est pas MVT1D.**

---

## 3. Comparaison des méthodes

Même dataset, mêmes vœux, même seed.

| Méthode | Affectés | Vœu 1 | Top 3 | Rang moy. | Bases vides (v3)* | Temps | Preuve |
|---------|----------|-------|-------|-----------|-------------------|-------|--------|
| **NAIVE** | 239 | 30 | 78 | 6,66 | *non comparable* | 4 ms | UNKNOWN |
| **LIBERATION** | 1 089 | 146 | 405 | 5,78 | *non comparable* | 268 ms | UNKNOWN |
| **AFFECTA TEACHER** | **1 199** | **405** | **831** | **3,12** | **346** | 519 ms | UNKNOWN |
| **AFFECTA BALANCED** | 1 199 | 307 | 720 | 3,81 | **286** | 967 ms | UNKNOWN |
| **AFFECTA COVERAGE** | 1 199 | 283 | 679 | 3,98 | **274** | 981 ms | UNKNOWN |

\* **Bases de support à remplissage nul** selon la métrique Coverage v3 —  
proxy interne de couverture. **Une base n’est pas nécessairement une école
au sens administratif.**  
Cette colonne n’est **pas définie de la même façon** pour NAIVE / LIBERATION :
aucune comparaison NAIVE↔TEACHER sur ce compteur n’est valide.

### Ce que montrent les chiffres

- **NAIVE** n’utilise presque que les postes déjà vacants → 239 affectés.
- **LIBERATION** active les chaînes → 1 089 affectés.
- **AFFECTA TEACHER** : 1 199 / 1 200 affectés, 405 vœux n°1, rang moyen 3,12.
- **AFFECTA COVERAGE** : même cardinalité, 283 vœux n°1, **274** bases vides (v3) vs **346** pour TEACHER.
- **BALANCED** se place entre les deux (cost/gain = **0,286**).

**1 agent sur 1 200 n’est pas affecté** (1 199 ASSIGNED).  
Ne pas affirmer que « tous les professeurs » sont affectés.

---

## 4. Le compromis (même métrique v3 uniquement)

| Politique | Intention | Vœu 1 | Bases vides (v3) | cost/gain |
|-----------|-----------|------:|-----------------:|----------:|
| **TEACHER** | Privilégier les vœux | **405** | 346 | 0 |
| **BALANCED** | Compromis | 307 | **286** | **0,286** |
| **COVERAGE** | Réduire les bases vides (v3) | 283 | **274** | **0,493** |

TEACHER → COVERAGE : **−122** vœux n°1, **−72** bases à remplissage nul (v3).

AFFECTA ne désigne pas la « bonne » politique.  
Il **mesure** un arbitrage expérimental (PRODUCT_POLICY).

---

## 5. Why-not : trois dossiers

### Dossier 1 — Vœu 1 obtenu (A00005)

Résultat : affecté en **vœu n°1** — motif `YOU_GOT_THIS_POST`.

### Dossier 2 — Classement prototype (A00014)

Résultat : affecté en **vœu n°3**.  
Vœu n°1 non obtenu : concurrent A00404 mieux ordonné selon le scorer du prototype  
(barème 146 vs 183). Catégorie **REGLEMENTAIRE** (du prototype, pas une décision officielle).

### Dossier 3 — Optimisation, preuve partielle (A00003)

Résultat : affecté en **vœu n°8**.

Formulation verrouillée :

> Dans l’état final, un autre agent occupe le poste demandé.  
> D’après le scorer réglementaire **du prototype**, A00003 serait mieux ordonné
> que le titulaire final sur ce poste.  
> L’état final résulte néanmoins d’une **optimisation**.  
> **Le journal exact de la décision n’est pas disponible dans cette démo.**  
> Catégorie : OPTIMISATION — preuve partielle.

---

## 6. Ce qu’AFFECTA ne prétend PAS faire

1. **Ce n’est pas MVT1D** et ne remplace aucun outil officiel.  
2. Les **vœux** de cette démo sont **synthétiques**.  
3. Certaines **règles réglementaires** restent **UNKNOWN**.  
4. L’**optimalité** n’est **pas prouvée** (status UNKNOWN).  
5. TEACHER / BALANCED / COVERAGE sont des **PRODUCT_POLICY**, pas des règles du BO/LDG.  
6. Le temps CPU du solveur n’est qu’une partie du délai administratif réel.  
7. La métrique « bases vides (v3) » n’est **pas** un recensement d’écoles.

---

## 7. Performance — formulations autorisées

- Démo figée (1 200 agents, postes Guadeloupe, vœux synthétiques) : TEACHER ≈ **519 ms**.  
- Instance **synthétique distincte** à 10 000 agents : TEACHER mesuré autour de **4 s**.  
- **Interdit** de fusionner les deux en « 10 000 enseignants Guadeloupe en 4 s ».

---

## 8. Message central

> Voici exactement ce que notre prototype produit, les objectifs que nous pouvons
> comparer, les compromis observés, les motifs que nous savons expliquer, et les
> choses que nous ne sommes pas capables de prouver.

Hashes : TEACHER `0ea2792c91fb88db` · BALANCED `d4d40f0e59c27ee5` · COVERAGE `60cda21892ee4e53`
