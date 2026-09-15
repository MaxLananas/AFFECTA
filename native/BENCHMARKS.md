# AFFECTA — benchmarks de passage à l'échelle (cœur natif)

Environnement de mesure : 2 vCPU, 3,8 Gio RAM, gcc 12.2 `-O3 -march=native
-funroll-loops`, exécution mono-thread. Générateur : `native/affecta_bench.c`
(campagne synthétique dont la forme statistique reproduit le jeu réel Guadeloupe —
environ 0,6 poste par agent, capacités par poste de 1 à 5, 12 vœux précis par agent,
62 % de titulaires, mix de priorités légales conforme à l'ordre de l'article L. 512-19,
discriminants AEN et ancienneté d'échelon renseignés).

Reproduire :

```sh
make -C native
for n in 100000 500000 1000000 2000000 5000000 10000000; do
  ./native/affecta_bench $n 20260914
done
```

## Résultats

| Agents | Postes | Propositions | Build (ms) | Solve (ms) | Débit (M ag/s) | Affectés |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 000 | 60 016 | 1,26 M | 24 | 29 | 3,49 | 92,64 % |
| 500 000 | 300 016 | 6,31 M | 108 | 200 | 2,50 | 92,64 % |
| 1 000 000 | 600 016 | 12,62 M | 245 | 555 | 1,80 | 92,67 % |
| 2 000 000 | 1 200 016 | 25,24 M | 520 | 1 173 | 1,70 | 92,62 % |
| 5 000 000 | 3 000 016 | 63,10 M | 1 124 | 3 712 | 1,35 | 92,64 % |
| 10 000 000 | 6 000 016 | 86,20 M | 1 788 | 6 864 | 1,46 | 90,63 % |

`Solve` est le temps du seul appariement (hors génération/`build`). Pour dix millions
d'agents le générateur réduit le nombre de vœux à 8 afin de tenir dans les 3,8 Gio de la
machine de mesure ; le solveur, lui, reste linéaire en nombre de propositions.

### Note d'optimisation — clé de comparaison compactée

La clé de classement réglementaire (priorité, barème, rang, sous-rang, puis les trois
discriminants MVT1D) est repliée sans perte dans deux mots de 64 bits « de force » plus
le tirage aléatoire 64 bits. Cela ramène la structure par créneau de 40 à 24 octets et le
comparateur à trois branches, réduisant la pression sur la bande passante mémoire — le
facteur limitant à l'échelle du million de créneaux. L'ordre lexicographique reste
strictement identique à `CandidateScore.regulatory_key()` (équivalence vérifiée bit à bit
contre le solveur Python de référence).

## Correction

Vérificateur force brute (`native/affecta_verify.c`) — aucune envie justifiée, en tenant
compte de la chaîne complète des discriminants :

| Agents | Affectés | Violations d'envie | Verdict |
| ---: | ---: | ---: | :-- |
| 1 000 | 944 | 0 | STABLE |
| 20 000 | 18 487 | 0 | STABLE |
| 100 000 | 92 635 | 0 | STABLE |
| 500 000 | 463 178 | 0 | STABLE |

## Équivalence avec le solveur de référence

Le cœur natif reproduit bit à bit l'appariement du solveur Python
`run_deferred_acceptance(..., allow_pure_exchanges=True)` sur le jeu réel Guadeloupe,
discriminants AEN/échelon activés :

| Seed | n=200 | n=1200 | n=2000 |
| --- | --- | --- | --- |
| 1 | oui | oui | oui |
| 7 | oui | oui | oui |
| 42 | oui | oui | oui |
| 20260811 | oui | oui | oui |
| 99999 | oui | oui | oui |

(15/15 empreintes de résultat identiques ; gardé par `tests/test_native.py`.)
