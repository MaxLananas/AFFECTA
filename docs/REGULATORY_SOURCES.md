# AFFECTA — Sources réglementaires (traçabilité)

Ce fichier ancre le moteur dans des textes réels. **Règle d'or : rien n'est marqué
`CONFIRMED` sans source vérifiable.** Tout le reste est `PROBABLE`, `UNKNOWN` ou
`PRODUCT_POLICY`.

Statuts utilisés (voir `domain/models.RuleStatus`) :
- `REGULATORY_CONFIRMED` — valeur/règle explicitement écrite dans une source citée ci-dessous.
- `REGULATORY_PROBABLE` — attesté par plusieurs sources concordantes mais variable selon département/année.
- `UNKNOWN` — non déterminable à partir des sources disponibles.
- `PRODUCT_POLICY` — choix produit AFFECTA (ex. politiques de couverture), **jamais** présenté comme réglementaire.

> ⚠️ Le barème du mouvement **intra-départemental** est fixé par les **LDG académiques**
> et **varie d'un département/académie à l'autre et d'une année à l'autre**. Les valeurs
> ci-dessous sont des ordres de grandeur documentés (campagne 2025/2026) servant de
> *barème de référence* ; elles ne remplacent pas la LDG du département cible.

---

## Algorithme d'affectation MVT1D — ordre de tri des candidats sur un poste ✅ CONFIRMED

Ordre lexicographique d'examen des vœux, concordant sur toutes les sources :

1. **Priorité** croissante (priorité 1 = la plus forte ; supplante le barème)
2. **Barème** décroissant
3. **Rang du vœu** croissant
4. **Sous-rang du vœu** croissant (au sein d'un vœu groupe)
5. **Discriminants** départementaux : AEN (ancienneté Éducation nationale) / AGS
   (ancienneté générale de service), puis échelon/ancienneté d'échelon, puis
   **tirage au sort** (numéro aléatoire attribué au participant).

Sources :
- Vade-mecum MVT1D Landes (FSU-SNUipp 40) — « 1-Vœu commun ; 2-Priorité ; 3-Barème ;
  4-Rang de vœu ; 5-Sous rang de vœu ; 6-Discriminants : 1-L'AEN, 2-L'AGS, 3-Le tirage
  au sort ». https://40-site.fsu-snuipp.fr/IMG/pdf/MVT1D_2022_-_Vade-mecum.pdf
- Guide intra 2026 CGT Éduc Versailles — « 1. Priorité croissante 2. Barème décroissant
  3. Rang du vœu croissant 4. Rang du sous-vœu croissant 5. Ancienneté de fonction
  6. Discriminant aléatoire ». https://www.cgteduc-versailles.fr/guide-sur-le-mouvement-intra-departemental/
- SNALC intra 2026 — « priorités légales, barème, rang de vœux, sous-rang de vœux,
  critères de départage propres à chaque département ». https://snalc.fr/mouvement-intradep-2026/
- Vade-mecum Nord 2026 (FSU-SNUipp 59) — mêmes critères + discriminants AGS / ancienneté
  fonction / ancienneté échelon / tirage au sort.
  https://59-site.fsu-snuipp.fr/IMG/pdf/vademecum_2026.pdf

**Implication AFFECTA** : `CandidateScore.regulatory_key()` respecte exactement cet ordre.
✅ Le primitive de tri du moteur est réglementairement correct.

> ⚠️ **Précision importante sur la nature de l'algorithme officiel.** L'algorithme MVT1D
> est décrit publiquement comme un traitement **par poste** (« une pile de vœux sera
> établie pour chaque poste ») en une passe barème/priorité, avec libération en cascade.
> Le modèle *deferred acceptance côté enseignants* d'AFFECTA produit un appariement
> **stable et sans envie justifiée** qui **respecte cette relation d'ordre par poste**,
> tout en étant *strategy-proof* et optimal pour les enseignants. Toute divergence
> exacte avec l'implémentation ministérielle (non publiée) reste `UNKNOWN`.

---

## Barème de référence (campagne 2025/2026) — ordres de grandeur documentés

| Élément | Valeur documentée | Statut | Source |
|---|---|---|---|
| Situation médicale grave / handicap (agent, conjoint, enfant), **sur vœu 1** | **800 pts** | PROBABLE | LDG interdép. + intra (voir ci-dessous) |
| BOE / RQTH (bonification handicap générale) | **100 pts** (interdép.) / **30 pts** (certaines LDG intra) | PROBABLE | CGT 92 (100) ; CGT Versailles (30) |
| Enfant à charge (< 18 ans) | **50 pts / enfant** | PROBABLE | CGT 92 |
| Rapprochement de conjoint (RC) — bonification de base | **150 pts** | PROBABLE | CGT 92 |
| RC/APC progressif par années de séparation | 1 an : 50 ; 2 ans : 200 ; 3 ans : 350 ; 4 ans + : 450 | PROBABLE | CGT 92 |
| APC (autorité parentale conjointe) — base | **150 pts** (interdép.) ; **5–70 pts** (intra selon dépt) | UNKNOWN (varie) | CGT 92 ; DSDEN 57 |
| Ancienneté de fonction (1er degré) | 2 pts/an (+3 forfait dans certains dépts) + tranches | PROBABLE | ac-Versailles, Guide Versailles |
| Renouvellement du vœu 1 (vœu précis école, rang 1) | 2 à 5 pts/an, souvent plafonné | PROBABLE | Guide Versailles (2 pts/an), CGT 92 (5 pts/an) |
| Éducation prioritaire (REP / REP+) | REP 45 ; REP+ 90 (interdép.) ; 40 pts (certaines LDG intra) | PROBABLE | CGT 92 ; Guide Versailles |
| Mesure de carte scolaire (poste supprimé) | 500 pts (école) / 300 (circ.) / 100 (dépt) + majorations | PROBABLE | SE-UNSA 67 (Strasbourg) |
| CIMM (DOM) — interdépartemental | 600 pts | CONFIRMED (interdép.) | CGT 92 |

Sources détaillées :
- CGT Éduc 92 — mouvement **interdépartemental** 2026, tableau de barème complet.
  https://www.92.cgteduc.fr/le-mouvement-interdepartemental-du-1er-degre/
- Circulaire intra 2026 ac-Versailles. https://www.ac-versailles.fr/media/56216/download
- Circulaire mvt intra 2025 ac-Strasbourg (SE-UNSA 67) — mesures de carte 500/300/100.
  https://se-unsa67.net/wp-content/uploads/2025/03/circulaire-MVT-annexes-repagineesommaire-interactifcompressee.pdf
- Guide intra 2026 CGT Versailles — enfant 50, handicap 30, REP/REP+, carte scolaire.
  https://www.cgteduc-versailles.fr/guide-sur-le-mouvement-intra-departemental/
- DSDEN 57 (FSU-SNUipp 57) annexe priorités/barème 2026 — APC 70 pts, priorités.
  https://57-site.fsu-snuipp.fr/IMG/pdf/annexe1_priorite-bareme-algorithme_26_1_.pdf
- Note départementale Rhône (ac-Lyon 2024/2025) — système de **priorités 1–99**,
  « la priorité supplante le barème ». https://www.ac-lyon.fr/media/57778/download

---

## Règles structurantes (hors montants)

### Les priorités ne s'appliquent PAS aux vœux groupes ✅ CONFIRMED
« Les priorités présentées [...] ne peuvent pas s'appliquer sur les vœux groupes. Si
vous pensez être dans une situation vous permettant de bénéficier d'une priorité, il est
préconisé de demander ce poste en vœu précis. » — Note intra ac-Lyon 2024.
https://www.ac-lyon.fr/media/50385/download
➡️ **Déjà implémenté** : `scorer.score_candidate` rejette RC/APC sur `wish.group`.

### RC et parent isolé / APC non cumulables ✅ CONFIRMED
« Les bonifications de rapprochement de conjoint et parents isolés ne sont pas
cumulables. » — Note intra ac-Lyon 2025. https://www.ac-lyon.fr/media/57778/download
➡️ **Déjà implémenté** : rejet `RC_APC_NON_CUMULABLE`.

### Participants obligatoires affectés d'office si aucun vœu satisfait ✅ CONFIRMED
« Si aucun des vœux formulés n'est satisfait, l'algorithme affectera le participant
obligatoire à titre définitif sur tout poste resté vacant dans le département. »
— Vade-mecum Landes. https://40-site.fsu-snuipp.fr/IMG/pdf/MVT1D_2022_-_Vade-mecum.pdf
➡️ Modélisé via `Agent.participation == "obligatoire"` : phase 2 « affectation d'office »
sur postes vacants par barème décroissant (statut `PROBABLE` sur les détails).

### Deux modalités d'affectation : TPD (définitif) vs PRO (provisoire) ✅ CONFIRMED
Note SE-UNSA 60 (codifications de vœux). https://sections.se-unsa.org/60/IMG/pdf/20230516_ia_fonctionnement_des_codifications_de_voeux_sur_l_accuse_de_reception_-_mouvement_intra-departemental_2023.pdf

### Vœu sur son propre poste (agent TPD) : ignoré par l'algorithme ✅ CONFIRMED
Guide ac-Paris 2023 : « l'algorithme ne prendra pas en considération ce premier vœu ».
https://www.ac-paris.fr/media/36731/download

### Priorités = échelle 1 à 99 (1 = plus forte), avec priorités techniques ✅ CONFIRMED
Priorité 15 = standard ; 95 = absence de poste ; 97 = incompatibilité quotité ;
priorité 1 = réintégrations, etc. — Note intra ac-Lyon.
➡️ AFFECTA utilise des rangs numériques *provisoires* ; le mapping exact vers les
codes 1–99 départementaux reste **UNKNOWN** (dépend du département).

---

## Enrichissements réglementaires (recherche croisée, septembre 2026)

### Chaîne de discriminants MVT1D — ordre exact ✅ CONFIRMED
Convergence de sources indépendantes sur la séquence de départage **après** priorité,
barème, rang et sous-rang :
1. **AEN** — ancienneté de fonction dans l'Éducation nationale, décroissante ;
2. **ancienneté dans l'échelon** détenu, décroissante ;
3. **numéro aléatoire** de campagne, attribué une fois pour toute la campagne.

Sources :
- Guide intra ac-Bordeaux — « discriminant 1 : AEN décroissant ; discriminant 2 :
  ancienneté dans l'échelon détenu décroissant ; discriminant 3 : numéro aléatoire
  décroissant ». https://www.ac-bordeaux.fr/media/78717/download
- Circulaire ac-Toulouse (MVT1D) — « barème de base décroissant ; discriminant
  décroissant ». https://www.ac-toulouse.fr/media/87344/download
- LDG ac-Poitiers — « 1 le rang de vœu ; 2 l'échelon ; 3 l'ancienneté dans l'échelon ;
  4 l'ancienneté générale de services ; 5 le numéro attribué à chaque participant ».
  https://www.ac-poitiers.fr/media/19931/download
- FSU-SNUipp 76 — « en cas d'égalité : l'ancienneté de fonctions (≠ AGS) … ».
  https://e-mouvement.snuipp.fr/76/regles/comment-ca-marche-402

➡️ AFFECTA implémente la chaîne complète (`CandidateScore.regulatory_key`, champs
`aen_months` / `echelon_months`). Les valeurs exactes en Guadeloupe restent à renseigner
par agent (par défaut neutres).

### Rapprochement de conjoints — seuil de distance ✅ CONFIRMED (structure)
La bonification RC exige une distance d'au moins **40 km** entre la résidence
professionnelle de l'agent et celle du conjoint (calcul routier Mappy/Maps).
- Circulaire SNUipp 69 — « une distance de 40 km ou plus sépare son lieu d'affectation
  actuelle de la résidence professionnelle de son conjoint ». https://69.snuipp.fr/IMG/pdf/circulaire.pdf
- Mémento ac-Aix-Marseille 2026 ; annexe ac-Limoges (« au-delà de 40 kilomètres »).

➡️ AFFECTA : `regulatory/geography.py` (distance orthodromique, HYPOTHESIS
d'approximation du calcul routier) + seuil 40 km dans le barème.

### Bonification progressive de séparation (RC/APC) ✅ CONFIRMED (structure)
Barème dégressif selon les années de séparation. Valeurs **PROBABLE** (interdép.
education.gouv / cgteduc-versailles) : 1 an = 50, 2 ans = 200, 3 ans = 350, 4 ans+ = 450.
Non-cumul RC/APC confirmé ; exclusion des vœux groupes (sauf handicap) confirmée.

### Mesure de carte scolaire — bonification dégressive géographique ✅ CONFIRMED (structure)
Hiérarchie école → commune d'exercice → communes limitrophes. Valeurs **PROBABLE**
(ac-versailles 2026 : 600 école / 500 commune / 250 limitrophe ; le vœu de maintien
déclenche les bonifications dégressives).
- Circulaire ac-Versailles n°2026-10. http://www.snalc-versailles.fr/uploads/circulaire-mouvement-intra-2026.pdf
- Circulaire ac-Lyon / SNUipp 69 (niveaux 300/200/100 selon les départements).

➡️ AFFECTA : `_mcs_proximity` s'appuie sur l'adjacence communale de `geography.py`.

### Priorités de titre (ASH/CAPPEI, direction) — traitées avant le barème ✅ CONFIRMED
Un agent détenteur du titre requis passe avant tout agent non titré, indépendamment du
barème ; hiérarchie CAPPEI (module exact > module différent > formation en cours > sans
titre → affectation provisoire).
- sgen-cfdt « Fonctionnement de l'algorithme MVT1D » (exigence 31 vs 40).
  https://sgen-cfdt.fr/contenu/uploads/sites/3/2024/03/FONCTIONNEMENT-ALGO-MVT1D-1.pdf
- ac-Montpellier, ac-Toulouse (annexe ASH), Somme 2025 (priorités 1 à 6 CAPPEI).

➡️ AFFECTA : `Post.required_titles`, `Agent.titles`, `_title_priority` (rangs < 10).

### Participants obligatoires et phase d'extension ✅ CONFIRMED
Les participants obligatoires doivent saisir au moins 2 vœux MOB (jusqu'à 5 selon le
département). Sans satisfaction : affectation d'office par « extension » sur poste vacant,
demandes valides avant demandes incomplètes, barème de base décroissant puis discriminant,
balayage à ordre fixe des circonscriptions/natures de postes (« vœu balayette » B/999).
Caractère : provisoire (PRO) si demande valide non satisfaite, définitif (TPD) si demande
incomplète.
- ac-Bordeaux (« a minima 5 vœux groupe MOB »), ac-Strasbourg / ac-Paris (« au moins 2 »),
  ac-Toulouse, ac-Limoges. Barème d'extension = ancienneté service + poste + handicap
  automatique + éducation prioritaire (glossaire mutation education.gouv, FAQ ac-Guadeloupe).

➡️ AFFECTA : `solver/extension.py` (exécuté après l'acceptation différée, sur postes
vacants uniquement, ne peut pas déloger une affectation principale).

---

## Ce qui reste UNKNOWN (à ne pas inventer)

- Composition exacte des vœux groupes (postes membres) — absente des PDF source Guadeloupe.
- Règle de sélection *interne* à un vœu groupe (au-delà du sous-rang = ordre départemental).
- Mapping exact des codes priorité 1–99 pour la Guadeloupe 2026.
- Barème **exact** Guadeloupe 2026 (le lien LDG dans le registre historique n'a pas pu
  être vérifié dans cet environnement — marqué en conséquence).
- Détails de la résolution des cycles/échanges purs (permutations) : traités en
  `PRODUCT_POLICY` optionnelle, jamais comme règle.
