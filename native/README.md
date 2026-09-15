# AFFECTA — cœur natif (deferred acceptance haute performance)

Noyau C de l'algorithme d'acceptation différée côté enseignants (Gale–Shapley), conçu
pour passer à l'échelle de **plusieurs millions d'agents** sur un seul cœur. Il produit
l'**unique appariement stable optimal-enseignant** respectant exactement l'ordre MVT1D
par poste (priorité ↑, barème ↓, rang de vœu ↑, sous-rang ↑, puis la chaîne complète de
discriminants AEN ↓, ancienneté d'échelon ↓, tirage aléatoire), avec droit absolu du
titulaire sur son poste. La clé de classement est repliée sans perte dans deux mots de
64 bits pour minimiser l'empreinte mémoire par créneau (voir `BENCHMARKS.md`).

## Composants

| Fichier | Rôle |
|---|---|
| `affecta_core.c` / `.h` | Noyau DA sur disposition CSR compacte (int32). File d'attente à anneau, pile par poste avec éviction du candidat le plus faible. |
| `affecta_bench.c` | Générateur synthétique (forme statistique calquée sur le jeu réel) + chronométrage. |
| `affecta_verify.c` | Vérificateur force brute de la stabilité (aucune envie justifiée) + capacités. |
| `affecta_mega.c` | Démonstrateur parallèle (pthreads, sans verrou) tenant l'échelle de 100 M d'agents via un oracle de préférences par hachage ; audit de stabilité intégré. Autonome. |
| `Makefile` | `make` (lib + binaires), `make bench`, `make verify`, `make mega`, `make mega-bench`, `make clean`. |

## Build

```sh
make -C native            # libaffecta.so + affecta_bench + affecta_verify
```

La bibliothèque `libaffecta.so` est chargée par `solver/engine_native.py` (ctypes). Si
elle n'est pas compilée, AFFECTA retombe automatiquement sur le solveur Python pur.

## Correction (équivalence stricte)

Le cœur natif est **byte-à-byte identique** au solveur Python de référence
`run_deferred_acceptance(..., allow_pure_exchanges=True)` : vérifié sur 20 instances
(seeds × tailles) du jeu réel Guadeloupe, hash de résultat égal à chaque fois
(`tests/test_native.py`). Le vérificateur force brute confirme l'absence d'envie
justifiée jusqu'à 500 000 agents.

```sh
make -C native verify && ./native/affecta_verify 100000
# verify: agents=100000 assigned=92660 envy_violations=0 -> STABLE (no justified envy)
```

## Performance mesurée

Machine de mesure : 2 vCPU, 3,8 Gio RAM, gcc 12 `-O3 -march=native`, mono-thread.
Campagne synthétique (≈0,6 poste/agent, capacités 1–5, 12 vœux précis/agent, mix de
priorités légales art. 60). Voir `BENCHMARKS.md` pour le tableau complet.

| Agents | Propositions | Build | Solve | Débit | Affectés |
|---:|---:|---:|---:|---:|---:|
| 100 000 | 1,26 M | 24 ms | 29 ms | 3,5 M/s | 92,6 % |
| 1 000 000 | 12,6 M | 245 ms | 555 ms | 1,8 M/s | 92,7 % |
| 5 000 000 | 63,1 M | 1,12 s | 3,71 s | 1,4 M/s | 92,6 % |
| 10 000 000 | 86,2 M | 1,79 s | 6,86 s | 1,5 M/s | 90,6 % |

À titre de comparaison, la campagne réelle Guadeloupe (1 310 postes, ~1 200 agents) est
résolue en **quelques dizaines de millisecondes** ; l'objectif « milliers d'agents en
secondes » est dépassé de plusieurs ordres de grandeur.

### Démonstrateur parallèle (100 M d'agents)

Le même algorithme, poussé bien au-delà de tout besoin réel, en parallèle et à l'échelle
de la centaine de millions d'agents (préférences reconstruites à la demande par un oracle
de hachage — aucune proposition matérialisée) :

```sh
make -C native mega
./native/affecta_mega 100000000 42 2 verify   # cent millions d'agents + audit de stabilité
```

Sur ces deux cœurs : 1 M en ~0,2 s, 10 M en ~1,9 s, 50 M en moins de 10 s, 100 M en ~20 s,
toujours **100 % affectés** et **stables (0 envie justifiée)**, résultat déterministe et
indépendant du nombre de fils. Débit borné par la latence mémoire (voir `BENCHMARKS.md`).
Ce binaire est autonome et n'entre pas dans le chemin de production.
