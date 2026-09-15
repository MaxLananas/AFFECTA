# Journal des améliorations AFFECTA

Suivi des vagues de la feuille de route (`docs/AUDIT.md`). Chaque entrée est mesurée.

## Vague 1 — Traçabilité & documentation ✅
- `docs/AUDIT.md` : audit technique complet (cartographie, faiblesses par gravité, plan).
- `docs/REGULATORY_SOURCES.md` : ancrage réglementaire, chaque affirmation sourcée avec statut.
- `README.md` : présentation, exécution, architecture, argument de remplacement de MVT1D.
- `run_tests.py` : runner de tests sans dépendance (pytest indisponible dans l'env).

## Vague 2 — Solveur correct par acceptation différée ✅
- `solver/deferred_acceptance.py` : Gale–Shapley côté enseignants.
  - **Garantie : 0 envie justifiée** (vérifié sur 300 instances aléatoires + 30 via
    certificat de stabilité indépendant).
  - Gère nativement : chaînes de libération, capacités multi-postes, droit du titulaire,
    filet STAY, vœu sur son propre poste ignoré (règle MVT1D confirmée).
  - Cycles/échanges purs : conservateur par défaut (REGULATORY_UNKNOWN), activables.
  - **Qualité vs ancien moteur (10 000 agents, données synthétiques)** :
    - affectés 9 059 → **9 406** (+347)
    - vœu n°1 : 5 166 → **6 678** (+1 512)
    - rang moyen 1,68 → **1,43**
- `tests/test_da_engine.py` : 11 tests (correction, stabilité, capacité, déterminisme).

## Vague 3 — Purge de la dépendance networkx ✅
- Constat : 5 modules optimiseurs faisaient `import networkx` → **crash à l'import**
  (networkx absent de l'environnement cible). Couche « matching » entièrement morte.
- `optimizer/matching.py` : Hopcroft–Karp + **min-coût max-cardinalité** (SSP/SPFA),
  pur Python. Optimalité vérifiée contre force brute : **0 écart / 3 000 instances**.
- `optimizer/_nxcompat.py` : shim minimal reproduisant l'API networkx utilisée.
- Les 5 modules (`fast_matching`, `fast_hybrid`, `policy_hybrid`, `coverage_v2/v3`)
  s'importent et s'exécutent désormais avec **zéro dépendance externe**.
- `tests/test_matching.py` : 5 tests.

## Vague 4 — Performance ✅
- DA en pur Python : **10 000 agents ≈ 0,30 s**, 25 000 ≈ 1,0 s, 50 000 ≈ 2,2 s
  (objectif « milliers d'agents en secondes » atteint, avec marge).
- Déterminisme préservé (hash de résultat stable entre exécutions).
- `movement_engine compare` : comparaison DA vs legacy intégrée à la CLI.

## Vague 5 — Registre réglementaire honnête ✅
- `regulatory/registry.py` réécrit :
  - Chaque bonus historique porte un **statut réel** (CONFIRMED/PROBABLE/UNKNOWN) au
    lieu de « CONFIRMED » systématique non sourcé.
  - `reference_registry()` : barème de référence **entièrement sourcé** (LDG 2025/2026)
    fourni à côté, sans casser le comportement historique.
  - Helpers d'audit : `unsourced()`, `audit_table()`.

## Vague 6 — Explicabilité : certificat de stabilité ✅
- `explain/stability.py` : vérificateur **indépendant** d'absence d'envie justifiée
  (relit uniquement résultat + scores). Intégré à `movement_engine run`.
- Démonstration : sur 2 000 agents, DA **stable**, ancien moteur **non stable**.

## Vague 7 — Cœur natif haute performance (passage au million d'agents) ✅
- `native/affecta_core.c` : acceptation différée côté enseignants en C sur disposition
  **CSR compacte** (int32), file à anneau + pile par poste avec éviction du plus faible.
  Compilé en `libaffecta.so` (`-O3 -march=native`).
- `solver/engine_native.py` : pont **ctypes**. Réutilise `_build_preferences` /
  `_effective_capacity` du solveur de référence → **sémantique réglementaire identique**
  (clé par poste, droit du titulaire, vœu propre poste ignoré, capacités multi-postes).
  Repli automatique sur le solveur Python si la lib n'est pas compilée.
- **Équivalence stricte** : résultat **byte-à-byte identique** à
  `run_deferred_acceptance(..., allow_pure_exchanges=True)` — 20/20 hachages égaux
  (seeds × tailles, jeu réel Guadeloupe). Gardé par `tests/test_native.py`.
- **Correction** : `native/affecta_verify.c` vérifie en force brute l'absence d'envie
  justifiée jusqu'à 500 000 agents (0 violation).
- **Performance mesurée** (2 vCPU, mono-thread, cf. `native/BENCHMARKS.md`) :
  - 1 000 000 agents (12,6 M propositions) : appariement en **0,58 s** (1,7 M ag/s)
  - 5 000 000 agents (63,1 M propositions) : **3,89 s**
  - 10 000 000 agents (126,2 M propositions) : **8,28 s**, pic mémoire < 2,5 Gio
  - Objectif « milliers d'agents en secondes » **dépassé de plusieurs ordres de grandeur**.
- CLI : `--engine native` disponible sur `run` / `benchmark`.

---

## Reste à faire (pistes priorisées)

- Intégrer DA au runner de données réelles (`datasets/guadeloupe_2026/alpha_runner.py`)
  et régénérer `alpha_report.json` avec les métriques de stabilité.
- Vœux groupes : modéliser le sous-rang dans DA de bout en bout (données de composition
  de groupe restent UNKNOWN dans les sources).
- Barème de référence : brancher `reference_registry()` derrière un flag pour des
  simulations « réalistes » (sans jamais l'imposer comme réglementaire).
- Politiques de couverture (TEACHER/BALANCED/COVERAGE) : réécrire au-dessus de DA pour
  garder la garantie de stabilité tout en couvrant les postes critiques.
- Résolution optionnelle des cycles d'échange (TTC — Top Trading Cycles) en PRODUCT_POLICY.
