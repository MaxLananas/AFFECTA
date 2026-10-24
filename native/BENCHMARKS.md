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

## Démonstrateur parallèle à 100 millions d'agents (`affecta_mega`)

`native/affecta_mega.c` pousse le même algorithme d'acceptation différée bien au-delà de
tout besoin opérationnel, en parallèle (pthreads, sans verrou par poste), jusqu'à la
centaine de millions d'agents. À ce volume, stocker une liste de vœux par agent
représenterait des dizaines de gigaoctets : chaque vœu et sa clé de classement sont donc
reconstruits à la demande par un oracle de hachage déterministe (splitmix64), sans jamais
matérialiser la moindre proposition. L'empreinte mémoire reste ainsi d'environ 2,1 Gio à
100 M d'agents. Chaque poste est une unique cellule atomique 64 bits (clé de classement
37 bits au-dessus d'un identifiant d'agent 27 bits) ; les propositions se résolvent par
maximum atomique et les évincés se re-proposent via une liste de travail (frontière) — le
coût total est proportionnel au nombre de propositions, jamais un balayage O(n) par tour.

Reproduire :

```sh
make -C native mega
for n in 1000000 10000000 50000000 100000000; do
  ./native/affecta_mega $n 42 2 verify
done
```

| Agents | Postes | Appariement (ms) | Débit (M ag/s) | Tours | Affectés | Stabilité |
| ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| 1 000 000 | 1 050 016 | 191 | 5,2 | 12 | 100,000 % | 0 envie |
| 10 000 000 | 10 500 016 | 1 861 | 5,4 | 13 | 100,000 % | 0 envie |
| 50 000 000 | 52 500 016 | 9 706 | 5,1 | 14 | 100,000 % | 0 envie |
| 100 000 000 | 105 000 016 | ~20 000 | ~5,0 | 15 | 100,000 % | 0 envie |

100 % d'affectation est atteint par une passe de comblement (`backfill`) stable : les
créneaux restés vides ne sont, par construction, convoités par personne, donc les y placer
ne crée aucune envie justifiée. La colonne stabilité provient de l'audit `verify` intégré
(option `verify` en 4ᵉ argument), qui vérifie l'absence d'envie justifiée sur
l'appariement produit *avant* comblement. Le résultat est déterministe et indépendant du
nombre de fils (1, 2 ou 4 fils donnent le même appariement).

Le débit est borné par la latence des accès mémoire aléatoires sur le tableau des postes
(environ 840 Mo à 100 M) ; il progresse donc avec la bande passante mémoire et le nombre de
cœurs, et présente une variabilité d'exécution notable sur une machine partagée (l'étape
d'appariement à 100 M a été mesurée entre 19 et 24 s selon la charge). Ce démonstrateur est
autonome (aucune dépendance à `affecta_core.c`) et n'entre pas dans le chemin de
production.

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
