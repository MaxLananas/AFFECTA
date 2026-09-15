# AFFECTA

**Moteur expérimental d'affectation des enseignants du premier degré** (mouvement
intra-départemental). Objectif de long terme : devenir un remplaçant crédible de
**MVT1D**, le système officiel de l'Éducation nationale — plus rapide, plus juste,
plus transparent, plus réaliste, et **auditable**.

> ⚠️ Statut : prototype de recherche. Les vœux d'agents sont **synthétiques**.
> Aucune règle réglementaire n'est inventée : tout ce qui n'est pas sourcé est marqué
> `UNKNOWN` / `PROBABLE` / `PRODUCT_POLICY`. Voir `docs/REGULATORY_SOURCES.md`.

## Ce qui rend AFFECTA crédible

| Propriété | Comment |
|---|---|
| **Juste (pas d'envie justifiée)** | Solveur par **acceptation différée** (Gale–Shapley côté enseignants) : appariement **stable**, respectant exactement l'ordre réglementaire poste par poste. Prouvé par un vérificateur indépendant (`explain/stability.py`). |
| **Optimal pour les enseignants** | Parmi tous les appariements stables, DA maximise la satisfaction des vœux des enseignants. |
| **Non manipulable** | DA côté enseignants est *strategy-proof* : mentir sur ses vœux ne peut pas aider. |
| **Rapide** | ~0,3 s pour 10 000 agents en pur Python ; le **cœur natif C** (`native/`) résout **1 000 000 d'agents en 0,58 s** et **10 000 000 en 8,3 s** sur un seul cœur (cf. `native/BENCHMARKS.md`). |
| **Transparent** | Certificats vérifiables indépendamment (intégrité + stabilité), explications *why-not*, traçabilité des sources réglementaires. |
| **Reproductible** | Résultat déterministe (départage par hash stable) → hash de résultat stable. |
| **Sans dépendance** | 100 % bibliothèque standard Python. `networkx` a été retiré (matching pur-Python). |

## Installation / exécution

Le paquet s'importe sous le nom `movement_engine` alors que le dossier s'appelle
`AFFECTA`. Deux options :

```bash
# option A — lien symbolique (recommandé pour le dev)
cd /chemin/vers/parent
ln -s AFFECTA movement_engine
python3 -m movement_engine test

# option B — depuis le parent en ajoutant un alias de module
PYTHONPATH=. python3 -c "import AFFECTA as movement_engine"
```

### Commandes

```bash
python3 -m movement_engine test                 # suite de tests (sans pytest)
python3 -m movement_engine run --agents 10000   # une campagne (solveur DA par défaut)
python3 -m movement_engine run --engine legacy  # ancien moteur glouton (comparaison)
python3 -m movement_engine compare              # DA vs legacy, côte à côte
python3 -m movement_engine benchmark --large    # perf jusqu'à 50 000 agents
python3 -m movement_engine verify               # démo de détection d'altération
```

## Architecture

```
domain/            Modèles immuables : Agent, Post, Wish, CandidateScore, Assignment
regulatory/        Barème + éligibilité (scorer) et registre honnête (registry)
solver/
  engine.py             Moteur historique (glouton multi-passes) — conservé
  deferred_acceptance.py  ⭐ Solveur stable par acceptation différée (défaut)
  engine_native.py      ⭐ Pont ctypes vers le cœur natif C (résultat identique)
native/            ⭐ Cœur C haute performance (DA à l'échelle du million d'agents)
  affecta_core.c        Acceptation différée sur disposition CSR compacte (int32)
  affecta_bench.c       Benchmark de passage à l'échelle
  affecta_verify.c      Vérificateur force brute d'absence d'envie justifiée
graph/             Graphe de dépendances, SCC (Tarjan), cycles/chaînes
optimizer/
  matching.py           ⭐ Matching pur-Python (Hopcroft–Karp + min-coût max-cardinalité)
  _nxcompat.py          Shim remplaçant networkx
  objective.py, satisfaction.py, policy_hybrid.py, coverage_v*.py, ...
explain/
  stability.py          ⭐ Certificat d'absence d'envie justifiée (vérif. indépendante)
  certificate.py, why_not.py, evidence.py
verifier/          Vérificateur indépendant des invariants (n'importe pas le solveur)
datasets/          Données réelles Guadeloupe 2026 (postes) + vœux synthétiques
docs/              AUDIT.md, REGULATORY_SOURCES.md, CHANGELOG_AFFECTA.md
tests/             Tests (exécutés par run_tests.py, sans dépendance)
```

## Le modèle d'affectation (pourquoi l'acceptation différée)

L'algorithme MVT1D est décrit publiquement comme un traitement **par poste** : pour
chaque poste, les candidats sont empilés par
`priorité ↑ → barème ↓ → rang de vœu ↑ → sous-rang ↑ → discriminants`, avec libération
en cascade. L'ancien moteur d'AFFECTA était une *dictature sérielle* qui ne garantissait
pas cette relation par poste et pouvait produire de l'**envie justifiée** (un agent
prioritaire privé d'un poste par un agent moins bien classé — contraire à « la priorité
supplante le barème »).

L'**acceptation différée côté enseignants** produit l'unique appariement **stable
optimal pour les enseignants** : chaque enseignant propose à ses vœux dans l'ordre, chaque
poste ne retient que les meilleurs candidats selon l'ordre réglementaire, les rejetés
re-proposent. Le titulaire d'un poste garde un **droit de priorité absolu** sur son propre
poste (jamais délogé), et son poste actuel sert de filet (STAY). Les **échanges purs**
(permutations sans poste vacant) restent, par prudence et faute de règle sourcée, **non
résolus par défaut** (`REGULATORY_UNKNOWN`), activables via `allow_pure_exchanges=True`
(PRODUCT_POLICY explicite).

## Passage à l'échelle (cœur natif)

Le solveur pur-Python suffit largement à une campagne départementale réelle (Guadeloupe :
1 310 postes, ~1 200 agents → quelques dizaines de ms). Pour démontrer que l'algorithme
tient à l'échelle **nationale** — voire à celle de simulations massives — un **cœur C**
(`native/`) implémente la même acceptation différée sur une disposition mémoire compacte.

```bash
make -C native                       # libaffecta.so + binaires
python3 -m movement_engine run --agents 5000 --engine native   # via ctypes
./native/affecta_bench 1000000       # 1 M d'agents, chronométré
./native/affecta_verify 100000       # preuve force brute : 0 envie justifiée
```

| Agents | Propositions | Appariement | Débit | Affectés |
|---:|---:|---:|---:|---:|
| 1 000 000 | 12,6 M | **0,58 s** | 1,7 M ag/s | 92,7 % |
| 5 000 000 | 63,1 M | **3,89 s** | 1,3 M ag/s | 92,6 % |
| 10 000 000 | 126,2 M | **8,28 s** | 1,2 M ag/s | 92,7 % |

Le cœur natif est **byte-à-byte identique** au solveur Python de référence (20/20
hachages égaux sur le jeu réel, gardé par `tests/test_native.py`) : c'est la **même
décision**, seulement plus rapide. S'il n'est pas compilé, AFFECTA retombe
automatiquement sur le solveur Python pur.

## Preuve d'équité, en pratique

```
python3 -m movement_engine run --agents 3000
...
ÉQUITÉ (preuve indépendante)
Sans envie justifiée    OUI (stable)
Paires vérifiées        1,721
```

Le certificat de stabilité est calculé par un module **qui ne fait pas confiance au
solveur** : il relit uniquement le résultat et les scores réglementaires. Une violation
signalerait un bug, pas une « décision d'optimisation ». Sur les mêmes données, l'ancien
moteur glouton **échoue** ce contrôle — c'est l'argument central pour le remplacement.

## Feuille de route

Voir `docs/AUDIT.md` (faiblesses + plan) et `docs/CHANGELOG_AFFECTA.md` (avancement).
