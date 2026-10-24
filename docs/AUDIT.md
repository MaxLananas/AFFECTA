# AFFECTA — Audit technique et feuille de route

> Objectif du projet : moteur d'affectation du mouvement intra-départemental 1er degré,
> candidat crédible au remplacement de **MVT1D**. Plus rapide, plus juste, plus
> transparent, plus réaliste — **sans jamais inventer de règle réglementaire**.

Ce document est le résultat d'un audit en profondeur du dépôt (état initial :
commit `5a9e5de`) et fixe la feuille de route des améliorations. Chaque affirmation
réglementaire est tracée dans `docs/REGULATORY_SOURCES.md`.

---

## 1. Cartographie du code (état initial)

| Couche | Modules | Rôle |
|---|---|---|
| Domaine | `domain/models.py` | `Agent`, `Post`, `Wish`, `CandidateScore`, `Assignment` (dataclasses immuables) |
| Réglementaire | `regulatory/registry.py`, `regulatory/scorer.py` | Barème + éligibilité + clé de tri lexicographique |
| Solveur cœur | `solver/engine.py` | Affectation gloutonne multi-passes avec libération de chaînes |
| Graphe | `graph/dependency.py` | Graphe de dépendances, SCC (Tarjan), chaînes, cycles |
| Optimiseurs | `optimizer/*.py` (18 fichiers) | Heuristiques concurrentes (matching, hybrides, politiques, couverture) |
| Explicabilité | `explain/*.py`, `evidence/decision.py` | Certificats, why-not, preuves de décision |
| Vérif. indépendante | `verifier/verifier.py` | Re-contrôle des invariants sans faire confiance au solveur |
| CLI / données | `__main__.py`, `cli_v03.py`, `datasets/` | Entrées, dataset Guadeloupe 2026 (réel : postes ; synthétique : vœux) |

**La clé de tri (`CandidateScore.regulatory_key`)** implémente
`(priorité ↑, barème ↓, rang de vœu ↑, sous-rang ↑, départage)`.
✅ **Confirmé conforme** à l'ordre de l'algorithme MVT1D par plusieurs sources
officielles/syndicales (voir REGULATORY_SOURCES §Algorithme).

---

## 2. Faiblesses identifiées (par gravité)

### 2.1 CRITIQUE — Le solveur cœur peut violer les priorités (justified envy)

`solver/engine.py` procède en **dictature sérielle par le meilleur vœu de chaque agent** :
on trie les agents par la clé réglementaire de leur *premier* vœu, puis chacun prend
son meilleur poste libre. Ce n'est **pas** un tri *par poste*.

Conséquence : un agent prioritaire peut se faire souffler un poste par un agent moins
bien classé, uniquement parce que ce poste n'était pas le meilleur vœu du prioritaire.
Reproduction (voir `tests/test_da_engine.py::test_no_justified_envy`) : un agent
HANDICAP (priorité 10) qui demande P (vœu 1, jamais libéré) puis Q (vœu 2) devrait
obtenir Q avant un agent standard qui demande Q en vœu 1 — l'ancien moteur donnait
malgré tout Q au prioritaire ici, mais la garantie n'existait pas *structurellement*.
La règle officielle est explicite : **« la priorité supplante le barème »** et l'algo
MVT1D empile *par poste* les candidats (voir REGULATORY_SOURCES §Algorithme). Il faut
donc une garantie *sans envie justifiée* (no justified envy), pas une heuristique.

➡️ **Correctif : solveur par acceptation différée (deferred acceptance) côté enseignants**
(`solver/deferred_acceptance.py`). Produit l'appariement **stable optimal pour les
enseignants**, respecte exactement les priorités poste par poste, est *strategy-proof*
(un enseignant n'a jamais intérêt à mentir sur ses vœux), et modélise fidèlement la
libération de postes par chaînes. C'est le modèle théorique correct des mouvements
d'affectation à la française.

### 2.2 CRITIQUE — Modules optimiseurs morts (dépendance `networkx` absente)

`fast_matching.py`, `fast_hybrid.py`, `policy_hybrid.py`, `coverage_v2.py`,
`coverage_v3.py` font `import networkx as nx`. `networkx` **n'est pas installable**
dans l'environnement cible → ces modules lèvent `ModuleNotFoundError` à l'import.
Toute la couche « matching rapide » est donc inutilisable en l'état.

➡️ **Correctif : matching pur-Python** (`optimizer/matching.py`, Hopcroft–Karp +
flot min-coût sans dépendance) et bascule des optimiseurs dessus. Zéro dépendance
externe = déployable partout, auditable, reproductible.

### 2.3 MAJEUR — Barème « CONFIRMED » mais non sourcé / irréaliste

`regulatory/registry.py` affecte le statut `REGULATORY_CONFIRMED` à des montants
inventés (RC 150/250, enfant ×2, médical 30, autorité parentale unique 50…).
Or les LDG académiques 2026 réelles donnent des ordres de grandeur différents
(enfant **50 pts**, situation médicale grave/handicap **jusqu'à 800 pts** sur vœu 1,
BOE/RQTH **30 pts**, RC progressif 50/200/350/450). Marquer « CONFIRMED » une valeur
non sourcée est le pire cas pour un moteur qui vise l'audit réglementaire.

➡️ **Correctif : registre honnête** — chaque bonus porte un statut réel
(`CONFIRMED` seulement si sourcé, sinon `PROBABLE`/`UNKNOWN`/`PRODUCT_POLICY`),
avec la source exacte. Un « barème de référence documenté » (basé sur les LDG 2026
publiques) est fourni **à côté** du barème historique, sans écraser les tests.

### 2.4 MAJEUR — Performance non conforme à l'objectif (« milliers d'agents en secondes »)

- Tie-break = `sha256` recalculé ~1 par (agent, poste) éligible (40k hash pour 10k agents).
- L'ordre des agents est **re-trié à chaque passe** (`sorted(agents.keys(), key=…)`).
- Recomputation répétée de `regulatory_key()`.

➡️ **Correctifs** : tie-key entier déterministe (hash 64 bits mis en cache par agent),
scoring calculé une seule fois, ordre stable pré-calculé, structures indexées.
Le solveur DA est en O(Σ longueurs de listes de vœux) et scale linéairement.

### 2.5 MOYEN — Cycles/échanges (mutations croisées) systématiquement non résolus

`graph/dependency.py` classe tout cycle en `REGULATORY_UNKNOWN` et ne l'exécute jamais.
Deux enseignants qui veulent échanger leurs postes restent bloqués. C'est prudent, mais
irréaliste : dans la vraie vie ces échanges se font. Le statut reste `UNKNOWN` faute de
règle sourcée sur les permutations pures, mais on peut **exposer** ces cycles comme
opportunités et, en `PRODUCT_POLICY` explicite et désactivable, proposer leur résolution.

➡️ **Correctif** : détection enrichie + rapport d'opportunités d'échange, résolution
optionnelle marquée `PRODUCT_POLICY` (jamais par défaut, jamais « réglementaire »).

### 2.6 MOYEN — Capacité multi-postes et vœux groupes approximatifs

- L'`engine` historique ne gère que `vacant: bool` (capacité 1 de fait).
- Les vœux groupes ont un `sous_rank`, mais la règle de sélection *interne* au groupe
  est marquée `UNKNOWN` dans les données source — hypothèse : ordre du département.
- Rappel réglementaire sourcé : **les priorités ne s'appliquent pas aux vœux groupes**
  (déjà correctement implémenté dans le scorer ✅).

➡️ **Correctif** : le solveur DA gère nativement `capacity > 1` (postes multi-unités)
et le sous-rang des groupes.

### 2.7 MINEUR — Dettes diverses

- Le paquet s'importe sous `movement_engine` mais le dossier est `AFFECTA` → nécessite
  un lien/chemin. Documenté dans le README + `conftest`/`run_tests.py`.
- `pytest` absent de l'environnement → `run_tests.py` (runner sans dépendance) ajouté.
- `__main__.py` et `cli_v03.py` dupliquent `make_dataset`.

---

## 3. Feuille de route (par vagues, mesurable)

| Vague | Livrable | Métrique de succès |
|---|---|---|
| 1 | Docs d'audit + sources réglementaires + README | Traçabilité : 0 règle « CONFIRMED » non sourcée |
| 2 | Solveur **acceptation différée** correct | 0 envie justifiée sur 10 000 instances aléatoires |
| 3 | Purge `networkx` → matching pur-Python | Tous les optimiseurs importables/exécutables |
| 4 | Perf | ≥ 10 000 agents < 1 s ; profil linéaire |
| 5 | Registre honnête + barème de référence sourcé | Chaque montant a un statut + source |
| 6 | Explicabilité (no-justified-envy certificate) | Certificat « stabilité » vérifiable indépendamment |

L'état d'avancement est suivi dans `docs/CHANGELOG_AFFECTA.md`.
