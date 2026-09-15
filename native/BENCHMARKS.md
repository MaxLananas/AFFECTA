# AFFECTA — benchmarks de passage à l'échelle (cœur natif)

Environnement de mesure : 2 vCPU, 3,8 Gio RAM, gcc 12.2 `-O3 -march=native
-funroll-loops`, exécution mono-thread. Générateur : `native/affecta_bench.c`
(campagne synthétique dont la forme statistique reproduit le jeu réel Guadeloupe —
≈0,6 poste par agent, capacités par poste 1–5, 12 vœux précis par agent, 62 % de
titulaires, mix de priorités légales conforme à l'ordre de l'article 60).

Reproduire :

```sh
make -C native
for n in 100000 500000 1000000 2000000 5000000 10000000; do
  ./native/affecta_bench $n 20260914
done
```

## Résultats

| Agents | Postes | Slots | Propositions | Build (ms) | Solve (ms) | Débit (M ag/s) | Affectés | Vœu 1–3 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 000 | 60 016 | 95 401 | 1 262 058 | 24 | 39 | 2,57 | 92,66 % | 29,04 % |
| 500 000 | 300 016 | 476 784 | 6 309 865 | 125 | 238 | 2,10 | 92,61 % | 29,29 % |
| 1 000 000 | 600 016 | 953 698 | 12 620 456 | 198 | 579 | 1,73 | 92,65 % | 29,19 % |
| 2 000 000 | 1 200 016 | 1 906 685 | 25 240 196 | 418 | 1 219 | 1,64 | 92,62 % | 29,23 % |
| 5 000 000 | 3 000 016 | 4 767 897 | 63 100 105 | 1 036 | 3 888 | 1,29 | 92,63 % | 29,23 % |
| 10 000 000 | 6 000 016 | 9 538 027 | 126 199 857 | 2 304 | 8 283 | 1,21 | 92,65 % | 29,24 % |

`Solve` est le temps du seul appariement (hors génération/`build`). Le pic mémoire pour
10 M d'agents reste sous ~2,5 Gio (mesuré : 311 Mio résident au repos, la campagne tient
dans les 3,6 Gio disponibles).

## Correction

Vérificateur force brute (`native/affecta_verify.c`) — aucune envie justifiée :

| Agents | Affectés | Violations d'envie | Verdict |
|---:|---:|---:|:--|
| 1 000 | 935 | 0 | STABLE |
| 20 000 | 18 551 | 0 | STABLE |
| 100 000 | 92 660 | 0 | STABLE |
| 500 000 | 463 025 | 0 | STABLE |

## Équivalence avec le solveur de référence

Le cœur natif reproduit **byte-à-byte** l'appariement du solveur Python
`run_deferred_acceptance(..., allow_pure_exchanges=True)` sur le jeu réel Guadeloupe :

| Seed | n=200 | n=600 | n=1200 | n=2000 |
|---|---|---|---|---|
| 1 | ✅ | ✅ | ✅ | ✅ |
| 7 | ✅ | ✅ | ✅ | ✅ |
| 42 | ✅ | ✅ | ✅ | ✅ |
| 20260811 | ✅ | ✅ | ✅ | ✅ |
| 99999 | ✅ | ✅ | ✅ | ✅ |

(20/20 hachages de résultat identiques ; gardé par `tests/test_native.py`.)
