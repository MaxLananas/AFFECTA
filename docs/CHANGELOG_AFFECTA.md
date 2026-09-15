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

## Vague 8 — Réalisme réglementaire, géographie et optimisation du cœur ✅
- **Recherche croisée approfondie** (circulaires ac-Bordeaux, ac-Toulouse, ac-Poitiers,
  ac-Versailles, ac-Lyon, ac-Strasbourg, ac-Limoges, education.gouv, SNUipp, SGEN-CFDT).
  Consignée dans `docs/REGULATORY_SOURCES.md` (statut par règle).
- **Chaîne complète des discriminants MVT1D** (REGULATORY_CONFIRMED) : AEN décroissant →
  ancienneté d'échelon décroissant → tirage aléatoire. `regulatory_key` passe de 5 à
  7 composantes ; champs `Agent.aen_months` / `echelon_months`.
- **Modèle géographique** `regulatory/geography.py` : 32 communes de Guadeloupe,
  adjacences terrestres (symétriques, îles isolées), distances orthodromiques.
- **Barème enrichi et décomposé** (`regulatory/scorer.py`, réécrit) :
  - rapprochement de conjoints conditionné à la distance ≥ 40 km ;
  - bonification progressive de séparation (50/200/350/450) ;
  - mesure de carte scolaire dégressive école/commune/limitrophe (600/500/250) ;
  - CIMM (600), éducation prioritaire (REP 45 / REP+ 90), ancienneté de poste par paliers ;
  - priorités de titre (ASH/CAPPEI, direction) traitées avant le barème.
  - Comportement historique STRICTEMENT préservé (68 tests, valeurs des tests inchangées).
- **Phase d'extension** `solver/extension.py` : affectation d'office des participants
  obligatoires (demandes valides avant incomplètes, barème de base décroissant + discriminant,
  balayage à ordre fixe, PRO/TPD), exécutée sur les seuls postes vacants — n'altère pas
  la stabilité de la phase principale.
- **Métadonnées réelles** propagées depuis `posts.json` (nature, circonscription, profil,
  exigence de titre) via `alpha_runner.load_real_posts`.
- **Cœur natif** : clé de classement compactée sans perte en deux mots 64 bits
  (struct 40 → 24 octets, comparateur à 3 branches). Solve 1 M : 555 ms ; 5 M : 3,71 s ;
  10 M : 6,86 s. Toujours **byte-à-byte identique** au solveur Python (15/15 empreintes)
  et **0 envie justifiée** jusqu'à 500 000 agents.
- **README** réécrit au registre institutionnel (sans emojis, sans ornements).
- Tests : **68 passed / 0 failed** (ajout de `tests/test_realism.py`, 14 tests).

---

## Vague 9 — Cœur parallèle 100 M et enchaînement de la procédure en deux temps ✅
- **Démonstrateur natif parallèle** `native/affecta_mega.c` : acceptation différée
  sans verrou (pthreads) à l'échelle de **100 millions d'agents**, préférences
  reconstruites à la demande par oracle de hachage (aucune proposition matérialisée,
  ~2,1 Gio à 100 M). ~5 M agents/s sur 2 cœurs : 1 M ~0,2 s, 10 M ~1,9 s, 50 M < 10 s,
  100 M ~20 s ; **100 % affectés** (comblement stable) et **0 envie justifiée** (audit
  `verify` intégré). Déterministe (1/2/4 fils → même appariement). Câblé au Makefile
  (`make mega`, `make mega-bench`) ; autonome, hors chemin de production.
- **Enchaînement de la procédure MVT1D en deux temps** `solver/pipeline.py` (`run_movement`) :
  jusqu'ici la phase d'extension existait mais n'était JAMAIS enchaînée à la phase
  principale dans un run standard — un participant obligatoire non satisfait ressortait
  donc `UNASSIGNED`, ce qui ne correspond PAS à la procédure réelle. `run_movement` joint
  les deux temps en une exécution auditable :
  - dérive le nombre de vœux MOB (vœux groupes) par agent ;
  - n'affecte d'office que les obligatoires non satisfaits, sur postes vacants ;
  - recompose un `EngineResult` cohérent (hachage recalculé, `office_assignments`,
    `method = DEFERRED_ACCEPTANCE+EXTENSION`).
  - **Effet mesuré** (instance rare, 300 entrants en forte collision) :
    DA seule 21 affectés / 279 non affectés → pipeline **300 affectés / 0 non affecté**
    (279 affectations d'office), **0 envie justifiée** — la phase principale est préservée
    à l'identique.
- **Moteur par défaut** de la CLI (`run`) : `da` = procédure complète (`run_movement`).
  Nouveau moteur `da-only` pour la phase principale seule (diagnostic/comparaison). Le jeu
  synthétique de démonstration marque désormais les agents sans poste comme obligatoires
  (entrants), rendant l'enchaînement visible.
- Tests : **76 passed / 0 failed** (ajout `tests/test_pipeline.py`, 8 tests : placement
  des obligatoires, préservation de la phase 1, absence d'envie, déterminisme, comptage MOB).

---

## Reste à faire (pistes priorisées)

- Régénérer `alpha_report.json` avec les métriques de la procédure complète en deux temps
  (`run_movement`) et les taux de satisfaction/stabilité associés.
- Vœux groupes : modéliser le sous-rang dans DA de bout en bout (données de composition
  de groupe restent UNKNOWN dans les sources).
- Barème de référence : brancher `reference_registry()` derrière un flag pour des
  simulations « réalistes » (sans jamais l'imposer comme réglementaire).
- Politiques de couverture (TEACHER/BALANCED/COVERAGE) : réécrire au-dessus de DA pour
  garder la garantie de stabilité tout en couvrant les postes critiques.
- Résolution optionnelle des cycles d'échange (TTC — Top Trading Cycles) en PRODUCT_POLICY.
