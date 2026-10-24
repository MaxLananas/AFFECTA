# AFFECTA

**Moteur d'affectation des enseignants du premier degré — mouvement intra-départemental.**

AFFECTA est un moteur expérimental d'aide à la décision pour les opérations de mobilité
intra-départementale des professeurs des écoles. Il vise à reproduire fidèlement les règles
du mouvement départemental (MVT1D) tout en apportant trois garanties formelles que le
traitement historique n'offre pas : l'**équité** (absence d'envie justifiée), l'**optimalité
pour les enseignants** parmi les affectations équitables, et la **traçabilité** intégrale de
chaque décision.

Le projet a une finalité claire : constituer une base technique crédible pour un système
d'affectation plus rapide, plus juste, plus transparent et pleinement auditable.

---

## 1. Statut et principes

AFFECTA est un prototype de recherche. Les données de postes utilisées sont réelles
(Guadeloupe, campagne 2026) ; les vœux des agents sont synthétiques, générés selon des
distributions réalistes.

Le projet applique une discipline stricte de sourçage réglementaire. Chaque règle mobilisée
par le moteur porte l'un des statuts suivants :

| Statut | Signification |
| --- | --- |
| `REGULATORY_CONFIRMED` | Règle établie par un texte officiel ou une circulaire académique vérifiable. |
| `PROBABLE` | Règle largement documentée mais dont la valeur exacte varie selon le département. |
| `HYPOTHESIS` | Modélisation raisonnée en l'absence de source départementale précise. |
| `PRODUCT_POLICY` | Choix de conception assumé, non imposé par la réglementation. |
| `UNKNOWN` | Valeur départementale non disponible publiquement. |

Aucune règle réglementaire n'est inventée. Les éléments non sourcés sont explicitement
marqués et isolés. L'inventaire complet figure dans `docs/REGULATORY_SOURCES.md` et peut
être audité par programme (`RuleRegistry.audit_table()`).

---

## 2. Garanties apportées

| Propriété | Fondement |
| --- | --- |
| Équité (aucune envie justifiée) | Solveur par acceptation différée (Gale–Shapley côté enseignants) produisant une affectation stable qui respecte exactement l'ordre réglementaire poste par poste. Vérifiée par un contrôleur indépendant (`explain/stability.py`). |
| Optimalité pour les enseignants | Parmi toutes les affectations stables, l'acceptation différée maximise la satisfaction des vœux des enseignants. |
| Non-manipulabilité | L'acceptation différée côté enseignants est *strategy-proof* : déclarer des vœux non sincères ne peut pas améliorer la situation d'un agent. |
| Performance | Cœur natif en C traitant plusieurs millions d'agents en quelques secondes ; démonstrateur parallèle tenant l'échelle de la centaine de millions d'agents (section 6). |
| Traçabilité | Certificats d'intégrité et de stabilité vérifiables indépendamment ; explications « pourquoi pas » ; barème décomposé et sourcé pour chaque candidature. |
| Reproductibilité | Résultat déterministe (départage réglementaire complet), donc empreinte de résultat stable. |
| Absence de dépendance | Bibliothèque standard Python uniquement ; cœur natif compilé avec la seule chaîne C standard. |

---

## 3. Modèle réglementaire

L'affectation MVT1D est un traitement **par poste**. Pour chaque poste, les candidatures
sont ordonnées selon la séquence réglementaire, confirmée de manière convergente par
plusieurs académies (Bordeaux, Toulouse, Poitiers) et les organisations professionnelles :

1. **Priorité croissante** — validité du titre exigé et priorités légales de l'article
   L. 512-19 du code général de la fonction publique.
2. **Barème décroissant** — somme des bonifications réglementaires.
3. **Rang du vœu croissant**.
4. **Sous-rang du vœu croissant** — ordre des postes au sein d'un vœu groupe.
5. **Discriminants**, dans l'ordre :
   1. ancienneté générale de fonction dans l'Éducation nationale (AEN), décroissante ;
   2. ancienneté dans l'échelon détenu, décroissante ;
   3. numéro aléatoire de campagne, attribué une fois pour toute la campagne.

AFFECTA implémente cette séquence intégralement. Le barème est décomposé en éléments
sourcés : ancienneté de service (échelon), ancienneté de poste, exercice en éducation
prioritaire, priorités familiales (rapprochement de conjoints, autorité parentale conjointe,
enfants à charge), situations de handicap et médicales, mesure de carte scolaire,
centre des intérêts matériels et moraux, réintégration, et priorités de titre pour les
postes spécialisés (ASH/CAPPEI) et de direction (liste d'aptitude).

Le rapprochement de conjoints s'appuie sur la distance réelle entre communes (seuil
réglementaire de 40 km) ; la mesure de carte scolaire mobilise la hiérarchie
école → commune → communes limitrophes. Ces mécanismes reposent sur un modèle
géographique des trente-deux communes de Guadeloupe (`regulatory/geography.py`).

### Procédure en deux temps

Le mouvement se déroule en deux temps enchaînés, confirmés par plusieurs académies
(Bordeaux, Toulouse, Strasbourg) et les organisations professionnelles :

1. **Phase principale** — tous les vœux (précis et groupes) sont traités par acceptation
   différée. Elle produit l'unique affectation stable, optimale pour les enseignants.
   Un titulaire sans vœu satisfait reste sur son poste actuel (maintien).
2. **Phase d'extension** — les **participants obligatoires** (entrants, stagiaires,
   réintégrations, mesures de carte scolaire non réaffectées) qui n'ont obtenu aucun vœu
   *doivent* recevoir un poste : ils sont affectés d'office sur un poste resté vacant,
   selon un ordre déterministe (demande valide d'abord, puis barème décroissant), à titre
   provisoire pour une demande valide, définitif pour une demande incomplète.

Les deux phases sont enchaînées par `solver/pipeline.py` (moteur `da` par défaut). La phase
d'extension ne remplit que des postes restés vacants : elle ne peut donc jamais déloger un
agent affecté par la phase principale et préserve intégralement sa stabilité (absence
d'envie justifiée vérifiée après enchaînement). Les affectations d'office sont tracées
(`chain_id = EXTENSION_PRO | EXTENSION_TPD`) et restent distinctes des affectations sur vœu.
Le moteur `da-only` exécute la phase principale seule, à fins de comparaison.

Le seuil de vœux groupe requis pour qu'une demande obligatoire soit *valide* varie selon
le département (de 2 à 5) : c'est un paramètre de politique produit
(`extension.DEFAULT_MOB_THRESHOLD`, défaut 2), explicitement distingué des règles
réglementaires.

---

## 4. Architecture

```
domain/            Modèles immuables : Agent, Post, Wish, CandidateScore, Assignment
regulatory/
  scorer.py             Barème complet et éligibilité, chaque élément sourcé et décomposé
  registry.py           Registre des règles avec statut et référence, outils d'audit
  geography.py          Modèle géographique des communes : distances, adjacences
solver/
  engine.py             Moteur historique (dictature sérielle) — conservé pour comparaison
  deferred_acceptance.py  Phase principale : solveur stable par acceptation différée
  extension.py          Phase d'extension : affectation d'office des participants obligatoires
  pipeline.py           Procédure MVT1D complète en deux temps (phase principale + extension)
  engine_native.py      Pont ctypes vers le cœur natif C (résultat identique)
native/            Cœur C haute performance (acceptation différée à l'échelle du million)
graph/             Graphe de dépendances, composantes fortement connexes, cycles
optimizer/         Couplage biparti pur-Python, objectifs, satisfaction, bornes
explain/           Certificat de stabilité, « pourquoi pas », traçabilité
verifier/          Vérificateur indépendant des invariants (n'importe pas le solveur)
datasets/          Données réelles Guadeloupe 2026 et générateurs de vœux synthétiques
docs/              Audit technique, sources réglementaires, journal des évolutions
tests/             Tests exécutés par run_tests.py, sans dépendance externe
```

---

## 5. Exécution

Le paquet s'importe sous le nom `movement_engine`. En développement, un lien symbolique
suffit :

```bash
cd /chemin/vers/parent
ln -s AFFECTA movement_engine
python3 -m movement_engine test
```

Commandes principales :

```bash
python3 -m movement_engine test                 # suite de tests (sans pytest)
python3 -m movement_engine run --agents 10000   # campagne (procédure MVT1D complète par défaut)
python3 -m movement_engine run --engine da-only # phase principale seule (sans extension)
python3 -m movement_engine run --engine native  # cœur natif C (résultat identique)
python3 -m movement_engine run --engine legacy  # moteur historique (comparaison)
python3 -m movement_engine compare              # acceptation différée contre moteur historique
python3 -m movement_engine benchmark --large    # mesure de performance
python3 -m movement_engine verify               # démonstration de détection d'altération
```

---

## 6. Passage à l'échelle

Le solveur pur-Python traite la campagne départementale réelle (1 310 postes, environ
1 200 agents) en quelques dizaines de millisecondes. Pour démontrer la tenue à l'échelle
nationale, un cœur natif en C (`native/`) implémente la même acceptation différée sur une
disposition mémoire compacte.

```bash
make -C native
./native/affecta_bench 1000000       # un million d'agents, chronométré
./native/affecta_verify 100000       # preuve exhaustive d'absence d'envie justifiée
```

| Agents | Propositions | Appariement | Débit | Affectés |
| ---: | ---: | ---: | ---: | ---: |
| 1 000 000 | 12,6 M | 0,58 s | 1,7 M agents/s | 92,7 % |
| 5 000 000 | 63,1 M | 3,89 s | 1,3 M agents/s | 92,6 % |
| 10 000 000 | 126,2 M | 8,28 s | 1,2 M agents/s | 92,7 % |

Le cœur natif produit une affectation identique, bit pour bit, à celle du solveur Python
de référence (contrôlé sur l'ensemble des instances par `tests/test_native.py`). Il s'agit
de la même décision, exécutée plus rapidement. En l'absence de bibliothèque compilée,
AFFECTA revient automatiquement au solveur Python.

### Démonstrateur de débit (100 millions d'agents)

Pour éprouver l'algorithme bien au-delà de tout besoin réel, `native/affecta_mega.c` exécute
la même acceptation différée en parallèle (pthreads, sans verrou) à l'échelle de la centaine
de millions d'agents. À ce volume, stocker une liste de vœux par agent est impossible (des
dizaines de gigaoctets) : chaque vœu et sa clé de classement sont donc reconstruits à la
demande par un oracle de hachage déterministe, sans jamais matérialiser la moindre
proposition. Chaque poste est une unique cellule atomique de 64 bits ; les propositions se
résolvent par maximum atomique et les agents évincés se re-proposent. L'ordre des propositions
n'affectant pas l'appariement stable optimal-enseignant, l'exécution parallèle rend le même
résultat qu'une exécution séquentielle, sans verrou par poste.

```bash
make -C native mega
./native/affecta_mega 100000000 42 2         # cent millions d'agents, chronométré
./native/affecta_mega 100000000 42 2 verify  # + audit exhaustif de stabilité
```

Mesures sur le bac à sable de développement (2 vCPU Xeon 2,60 GHz, 3,9 Go) :

| Agents | Appariement | Débit | Affectés | Stabilité |
| ---: | ---: | ---: | ---: | :---: |
| 1 000 000 | 0,19 s | 5,2 M agents/s | 100,0 % | 0 envie |
| 10 000 000 | 1,86 s | 5,4 M agents/s | 100,0 % | 0 envie |
| 50 000 000 | 9,71 s | 5,1 M agents/s | 100,0 % | 0 envie |
| 100 000 000 | ~20 s | ~5,0 M agents/s | 100,0 % | 0 envie |

Le débit est limité par la latence des accès mémoire aléatoires sur le tableau des postes
(environ 840 Mo à 100 M) : il progresse donc avec la bande passante mémoire et le nombre de
cœurs. Sur ces deux cœurs partagés, l'appariement se maintient à environ 5 millions d'agents
par seconde, avec une variabilité d'exécution notable liée à la charge de la machine. Chaque
mesure est confirmée par l'audit `verify` — aucune envie justifiée sur l'appariement produit.
Ce démonstrateur est autonome (aucune dépendance à `affecta_core.c`) et n'entre pas dans le
chemin de production : la campagne départementale réelle reste résolue en quelques dizaines de
millisecondes par le solveur Python.

Le détail des mesures et de la vérification figure dans `native/BENCHMARKS.md`.

---

## 7. Vérification de l'équité

```
python3 -m movement_engine run --agents 3000
...
ÉQUITÉ (preuve indépendante)
Sans envie justifiée    OUI
Paires vérifiées        1 721
```

Le certificat de stabilité est produit par un module qui ne fait pas confiance au solveur :
il relit uniquement le résultat et les barèmes réglementaires. Une violation signalerait un
défaut, non une décision d'optimisation. Sur les mêmes données, le moteur historique échoue
ce contrôle ; c'est l'argument central en faveur de son remplacement.

---

## 8. Documentation

- `docs/AUDIT.md` — audit technique, faiblesses identifiées, feuille de route.
- `docs/REGULATORY_SOURCES.md` — inventaire réglementaire sourcé, statut par règle.
- `docs/CHANGELOG_AFFECTA.md` — journal des évolutions, mesuré à chaque étape.
- `native/README.md`, `native/BENCHMARKS.md` — cœur natif et mesures de performance.
