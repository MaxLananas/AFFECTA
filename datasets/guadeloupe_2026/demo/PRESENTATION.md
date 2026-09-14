# AFFECTA — Support de présentation (7–10 min)

**CADRE VERROUILLÉ post-audit — lire `GLOSSAIRE_METRIQUES.md` avant toute présentation ou vidéo.**
Ne pas dire « établissements vides » pour la métrique v3. Ne pas comparer empty NAIVE et TEACHER. Affectés = 1 199/1 200. 10k agents = instance synthétique distincte.



**Version :** AFFECTA-DEMO-2026-08-11  
**Audience :** enseignants, syndicats, administration expérimentale  
**Ton :** institutionnel, sobre, factuel — aucune promesse marketing

Tous les chiffres ci-dessous proviennent exclusivement de la démo figée  
(`demo_report.json`, seed 20260811). Aucun chiffre n’a été ajusté pour la présentation.

---

# PLAN DES SLIDES (12 slides)

| # | Titre | Durée orale |
|---|--------|-------------|
| 1 | Titre | 20 s |
| 2 | Le problème | 60 s |
| 3 | Pourquoi un algorithme naïf ne suffit pas | 50 s |
| 4 | Ce qu’AFFECTA fait (3 couches) | 50 s |
| 5 | La démonstration — données | 30 s |
| 6 | Résultats comparés | 70 s |
| 7 | Le compromis professeurs / établissements | 70 s |
| 8 | Why-not : trois dossiers | 70 s |
| 9 | Les garanties | 40 s |
| 10 | Les limites (obligatoire) | 50 s |
| 11 | Conclusion | 40 s |
| 12 | Questions | — |

---

# CONTENU EXACT DES SLIDES

────────────────────────────────────────
## SLIDE 1 — Titre

**AFFECTA**  
Algorithme de Fiabilisation des Flux d’Effectifs,  
de Choix, de Transferts et d’Affectations

*Moteur expérimental d’optimisation des affectations enseignantes*

Démonstration — version figée 2026-08-11  
Périmètre : mouvement intra-départemental 1er degré · Guadeloupe

**Visuel :** fond clair, typographie institutionnelle, pas de logo d’État usurpée.  
Sous-titre discret : « Prototype expérimental — ne constitue pas un outil officiel »

────────────────────────────────────────
## SLIDE 2 — Le problème

**Chaque année, un mouvement d’affectation doit concilier :**

- des milliers de professeurs ;
- des postes aux natures différentes ;
- des vœux ordonnés et parfois larges ;
- des priorités et un barème ;
- des postes libérés seulement si le titulaire part ;
- **deux intérêts qui peuvent diverger :**
  - satisfaire au mieux les vœux des professeurs ;
  - ne pas laisser certaines écoles durablement sous-dotées.

**Le délai compte.** Une solution théoriquement meilleure mais trop lente  
n’est pas forcément utilisable dans une procédure réelle.

**Visuel :** schéma simple à deux flèches opposées  
`Préférences des professeurs` ←→ `Besoins des établissements`  
avec au centre : `Règles réglementaires + temps`

────────────────────────────────────────
## SLIDE 3 — Pourquoi un algorithme naïf ne suffit pas

**Décision locale ≠ meilleur résultat global**

Exemple de principe (chaîne de libération) :

```
Poste vacant V
Professeur A veut le poste de B
Professeur B veut le poste vacant V

NAIVE (sans libération) :
  B ne bouge pas → A ne peut pas prendre le poste de B
  → 0 ou 1 mutation utile

AVEC LIBÉRATION / CHAÎNE :
  B → V, puis A → poste de B
  → 2 mutations cohérentes
```

Dans la démo figée (1 200 professeurs simulés) :

| Méthode     | Affectés |
|-------------|----------|
| NAIVE       | **239**  |
| LIBERATION  | **1 089**|
| AFFECTA     | **1 199**|

Une approche purement séquentielle laisse des possibilités inutilisées.

**Visuel :** mini-diagramme A → B → V (chaîne) vs A bloqué / B immobile.

────────────────────────────────────────
## SLIDE 4 — Ce qu’AFFECTA fait

**Trois couches séparées**

```
1. REGULATORY     Ce qui est autorisé
                  (éligibilité, priorités connues, capacités)
                         ↓
2. OPTIMIZATION   Chercher une meilleure affectation
                  selon une politique d’objectifs explicite
                         ↓
3. VERIFICATION   Vérifier, expliquer, tracer
                  (Why-not, hashes, statut UNKNOWN)
```

Une règle réglementaire n’est pas mélangée avec un choix d’optimisation.  
Quand une règle manque, elle est marquée **UNKNOWN** — pas inventée.

**Visuel :** trois blocs empilés, flèches verticales, label UNKNOWN sur une branche.

────────────────────────────────────────
## SLIDE 5 — La démonstration — données

| Élément | Valeur |
|---------|--------|
| Périmètre | Intra-départemental 1D · Guadeloupe 2026 |
| Supports (PDF) | **1 310** |
| Groupes | **435** |
| Unités de capacité | **2 654** |
| Professeurs | **1 200 simulés** |
| Vœux | **synthétiques**, max 20 |
| Seed | **20260811** (reproductible) |

Sources : 4 documents officiels de postes/groupes,  
hashés dans le manifeste du dataset.

> Les vœux ne sont **pas** les vœux réels du mouvement 2026.

**Visuel :** encadré « Données postes = réelles · Vœux = synthétiques »

────────────────────────────────────────
## SLIDE 6 — Résultats comparés

**Même jeu de données · même seed · mêmes vœux**

| Méthode | Affectés | Vœu 1 | Top 3 | Rang moy. | Temps |
|---------|----------|-------|-------|-----------|-------|
| NAIVE | 239 | 30 | 78 | 6,66 | 4 ms |
| LIBERATION | 1 089 | 146 | 405 | 5,78 | 268 ms |
| **AFFECTA TEACHER** | **1 199** | **405** | **831** | **3,12** | 519 ms |
| **AFFECTA BALANCED** | 1 199 | 307 | 720 | 3,81 | 967 ms |
| **AFFECTA COVERAGE** | 1 199 | 283 | 679 | 3,98 | 981 ms |

Statut de preuve pour toutes les lignes : **UNKNOWN**

**Visuel :** tableau seul, chiffres gros, une ligne grisée pour NAIVE.

────────────────────────────────────────
## SLIDE 7 — Le compromis professeurs / établissements

| Politique | Intention | Vœu 1 | Établissements vides | Coût / gain |
|-----------|-----------|-------|----------------------|-------------|
| **TEACHER** | Privilégier les vœux | **405** | 346 | 0 |
| **BALANCED** | Compromis | 307 | **286** | 0,286 |
| **COVERAGE** | Réduire les vides | 283 | **274** | 0,493 |

- Passer de TEACHER à COVERAGE : **−122 vœux n°1**, **−72 bases à remplissage nul (v3)**.
- AFFECTA ne désigne pas la « bonne » politique.
- Il **mesure** le prix de chaque choix.

**Visuel :** deux barres côte à côte (vœux 1 vs bases vides (v3)) pour les 3 politiques.  
Phrase en bas : *« Il n’y a pas de solution parfaite universelle — il y a des arbitrages mesurables. »*

────────────────────────────────────────
## SLIDE 8 — Why-not : trois dossiers

**Dossier 1 — Vœu obtenu** (agent A00005)  
Résultat : affecté en **vœu n°1**  
Motif : vous avez obtenu ce poste.

**Dossier 2 — Raisonnement réglementaire** (agent A00014)  
Résultat : affecté en **vœu n°3**  
Vœu n°1 non obtenu car un concurrent était mieux classé  
Barème : **146** pts vs concurrent **183** pts  
Catégorie : **REGLEMENTAIRE**

**Dossier 3 — Arbitrage d’optimisation** (agent A00003)  
Résultat : affecté en **vœu n°8**  
Le classement réglementaire seul ne suffit pas à expliquer le refus  
Catégorie : **OPTIMISATION**  
Le moteur le dit explicitement — il n’invente pas une règle administrative.

**Visuel :** trois cartes verticales, pastilles de couleur  
vert = obtenu · bleu = réglementaire · orange = optimisation

────────────────────────────────────────
## SLIDE 9 — Les garanties

Ce que le prototype **vérifie** sur la démo figée :

- pas de double affectation d’un même professeur ;
- pas de poste attribué au-delà de sa capacité modélisée ;
- résultat **déterministe** (même seed → même hash) ;
- hashes des données sources et du résultat ;
- explications Why-not **catégorisées** ;
- statut **UNKNOWN** lorsque l’optimalité n’est pas prouvée ;
- séparation REGULATORY / PRODUCT_POLICY / UNKNOWN.

**Visuel :** liste à puces courte, icônes sobres (coche / cadenas / point d’interrogation).

────────────────────────────────────────
## SLIDE 10 — Les limites

**À lire à voix haute, sans accélérer.**

1. AFFECTA **n’est pas MVT1D** et ne remplace pas un outil officiel.  
2. Les **vœux** de cette démo sont **synthétiques**.  
3. Certaines **règles réglementaires** restent **UNKNOWN**.  
4. L’**optimalité** à grande échelle n’est **pas prouvée**.  
5. TEACHER / BALANCED / COVERAGE sont des **choix de produit**,  
   pas des règles du Bulletin officiel ni des LDG.  
6. Le **délai administratif global** (saisie, validation, contentieux)  
   n’est pas réduit au seul temps de calcul du solveur.

**Visuel :** fond légèrement distinct (gris très clair), titre « Limites » sans fioriture.

────────────────────────────────────────
## SLIDE 11 — Conclusion

> AFFECTA ne cherche pas à prétendre remplacer l’administration.  
> Il cherche à montrer qu’une affectation peut être :
>
> - calculée **rapidement** ;
> - **comparée** selon plusieurs objectifs ;
> - **expliquée** individuellement ;
> - accompagnée de **preuves** sur ce qui est réellement connu —
>   et de silence explicite sur ce qui ne l’est pas.

**Problème humain au centre :**  
satisfaire les professeurs **sans** abandonner les établissements,  
dans un temps compatible avec une procédure réelle.

**Visuel :** reprise du schéma professeurs ↔ établissements,  
avec au centre le mot « compromis mesurable ».

────────────────────────────────────────
## SLIDE 12 — Questions

Titre seul : **Questions**

Sous-texte discret :  
« Les réponses ci-après distinguent ce qui est démontré, ce qui est expérimental, et ce qui reste inconnu. »

---

# SCRIPT ORAL (≈ 8 minutes)

### Ouverture — Slide 1 (20 s)

Bonjour.  
Je vais vous présenter AFFECTA, un **moteur expérimental** d’optimisation des affectations enseignantes.  
Ce n’est **pas** un outil officiel, et je commencerai par le problème concret avant les chiffres.

### Slide 2 — Le problème (60 s)

Le mouvement d’affectation, ce n’est pas seulement « mettre un nom sur un poste ».  
Il y a beaucoup de professeurs, beaucoup de postes, des vœux ordonnés, des priorités, un barème.  
Certains postes ne se libèrent que si le titulaire part ailleurs — ce sont des **chaînes**.

Et surtout, deux intérêts peuvent diverger :  
d’un côté, les professeurs veulent obtenir le meilleur vœu possible ;  
de l’autre, on ne veut pas laisser certaines écoles en grande difficulté.  
Le **délai** compte aussi : une solution trop lente n’est pas forcément utilisable.

### Slide 3 — Naïf insuffisant (50 s)

Si on affecte de façon purement séquentielle, sans gérer les libérations,  
on bloque des chaînes entières.  
Sur notre démo figée à 1 200 professeurs simulés :  
la méthode naïve en place **239** ;  
avec libération, **1 089** ;  
avec AFFECTA, **1 199**.  
Ce n’est pas de la magie : c’est le passage d’une vision locale à une vision un peu plus globale.

### Slide 4 — Trois couches (50 s)

AFFECTA sépare trois choses.  
D’abord le **réglementaire** : ce qui est autorisé.  
Ensuite l’**optimisation** : chercher une meilleure affectation selon une politique explicite.  
Enfin la **vérification** : expliquer et tracer.  
Quand une règle nous manque, on la marque UNKNOWN. On ne l’invente pas.

### Slide 5 — Données (30 s)

La démo utilise les **postes et groupes** du mouvement Guadeloupe 2026 — 1 310 supports, 435 groupes.  
En revanche, les **vœux des 1 200 professeurs sont synthétiques**.  
C’est important : on ne prétend pas rejouer le mouvement réel nominatif.

### Slide 6 — Résultats (70 s)

À dataset strictement identique :  
NAIVE 239 affectés, 30 vœux n°1.  
LIBERATION 1 089 affectés, 146 vœux n°1.  
AFFECTA TEACHER 1 199 affectés, **405** vœux n°1, rang moyen 3,12, en environ **une demi-seconde**.  
Les autres politiques AFFECTA gardent le même nombre d’affectés, mais arbitrent autrement entre vœux et couverture.  
Le statut de preuve reste **UNKNOWN** : on a trouvé une solution, on n’a pas prouvé qu’elle était la meilleure possible.

### Slide 7 — Compromis (70 s)

C’est le cœur du sujet pour beaucoup d’enseignants et d’établissements.  
Si on privilégie les vœux — politique TEACHER — on obtient 405 vœux n°1, mais 346 bases à remplissage nul (proxy Coverage v3, pas un recensement d'écoles).  
Si on privilégie la couverture — COVERAGE — on descend à 274 bases de support à remplissage nul (métrique Coverage v3), mais on perd 122 vœux n°1.  
BALANCED se place entre les deux.  
AFFECTA ne dit pas quelle politique est « la bonne ».  
Il dit : **voici le prix de chaque choix**.

### Slide 8 — Why-not (70 s)

Pour un professeur, le résultat brut ne suffit pas.  
Premier dossier : la personne obtient son vœu 1 — c’est transparent.  
Deuxième : elle ne l’obtient pas parce qu’un concurrent a un barème plus élevé — 183 points contre 146 — catégorie réglementaire.  
Troisième : le refus ne s’explique pas par le seul barème ; il vient d’un **arbitrage d’optimisation**, et le moteur le **écrit noir sur blanc**.  
On préfère une explication inconfortable mais vraie à une justification administrative inventée.

### Slide 9 — Garanties (40 s)

Sur cette démo : pas de double affectation, résultat reproductible à seed et hash identiques,  
données sources hashées, explications catégorisées, et UNKNOWN lorsque la preuve d’optimalité manque.

### Slide 10 — Limites (50 s)

Je insiste sur les limites.  
Ce n’est pas MVT1D.  
Les vœux sont synthétiques.  
Des règles restent inconnues.  
L’optimalité n’est pas prouvée à grande échelle.  
Les politiques TEACHER, BALANCED et COVERAGE sont des choix de **produit**, pas des textes officiels.  
Et le temps de calcul du solveur n’est qu’une partie du délai vécu par les personnels.

### Slide 11 — Conclusion (40 s)

AFFECTA ne prétend pas remplacer l’administration.  
Il montre qu’on peut calculer vite, comparer plusieurs objectifs, expliquer individuellement,  
et être honnête sur ce qu’on sait et ce qu’on ne sait pas.  
Le problème humain reste central : **satisfaire les professeurs sans abandonner les établissements**,  
dans un temps réaliste.

Je vous remercie. Je réponds à vos questions.

---

# ÉLÉMENTS VISUELS PAR SLIDE (brief designer)

| Slide | Élément |
|-------|---------|
| 1 | Titre centré, sous-titre « prototype expérimental », aucune Marianne officielle usurpée |
| 2 | Schéma 2 pôles + contraintes au centre |
| 3 | Animation simple ou schéma statique de chaîne A→B→V |
| 4 | 3 blocs REGULATORY / OPTIMIZATION / VERIFICATION |
| 5 | Tableau données + bandeau « vœux synthétiques » |
| 6 | Tableau comparatif, une ligne par méthode |
| 7 | Double graphique barres (vœu 1 vs bases vides (v3)) |
| 8 | 3 cartes dossier |
| 9 | Liste garanties avec pictogrammes sobres |
| 10 | Fond légèrement gris, texte intégral des limites |
| 11 | Phrase de conclusion seule, grande lisibilité |
| 12 | Fond neutre « Questions » |

Palette suggérée (style institutionnel, **sans** copier un kit officiel non autorisé) :  
bleu nuit `#1e3a5f`, gris texte `#333`, fond `#f7f7f5`, accent mesure `#c45c26`.  
Police : système type **Marianne** *si licence disponible*, sinon **Inter** ou **Source Sans 3**.

---

# QUESTIONS DIFFICILES — RÉPONSES HONNÊTES

### Q1. « Vous allez remplacer MVT1D ? »
**Non.** AFFECTA est un prototype expérimental. Il ne remplace aucun outil officiel et n’a pas vocation à publier des affectations opposables.

### Q2. « Vos 405 vœux n°1, c’est sur le vrai mouvement Guadeloupe ? »
**Non.** Les postes et groupes viennent de documents 2026 ; les **vœux sont synthétiques**. On ne peut pas affirmer ce que donnerait le moteur sur les vœux réels sans ces données.

### Q3. « Pourquoi je n’ai pas eu mon vœu alors que j’ai plus de points qu’un collègue ? »
Deux cas dans AFFECTA :  
- soit un concurrent est réellement mieux classé (priorité / barème) → catégorie REGULATORY ;  
- soit la décision vient d’une optimisation (chaîne, politique de couverture) → catégorie OPTIMISATION, **explicitement signalée**.  
Si on ne peut pas prouver le motif : on dit EXPLICATION_INSUFFISANTE, on n’invente pas.

### Q4. « Vous optimisez contre les professeurs au profit des établissements ? »
On propose **trois politiques**. TEACHER maximise les vœux ; COVERAGE réduit les bases à remplissage nul (v3) ; BALANCED est entre les deux.  
Le choix de politique est un **choix de produit / de pilotage**, pas une vérité réglementaire.  
Les chiffres de la démo montrent le **coût** de chaque option.

### Q5. « C’est optimal ? »
À cette échelle, le statut est **UNKNOWN**.  
On a des solutions réalisables, des gains mesurés par rapport à des baselines,  
mais pas une preuve mathématique d’optimalité globale pour 1 200 ou 10 000 agents.

### Q6. « En combien de temps sur un vrai volume académique ? »
Sur des instances synthétiques d’environ **10 000** agents, le chemin TEACHER tourne en **quelques secondes** dans nos mesures.  
Cela ne préjuge pas du temps global d’une campagne administrative (saisie, pièces, validation humaine).

### Q7. « Que faites-vous des règles que vous ne connaissez pas ? »
On les marque **UNKNOWN**.  
On refuse de les remplir par déduction pour « faire joli ».  
C’est une limitation du prototype, pas une fonctionnalité cachée.

### Q8. « Un syndicat peut-il faire confiance à vos priorités ? »
Les priorités **documentées** sont isolées dans la couche réglementaire.  
Les arbitrages TEACHER/BALANCED/COVERAGE sont déclarés comme PRODUCT_POLICY.  
La confiance se construit sur la **transparence de cette séparation**, pas sur une promesse de conformité totale.

### Q9. « Que se passe-t-il si on autorise 50 vœux au lieu de 5 ? »
Dans nos tests synthétiques, passer de 5 à environ **50** vœux améliore fortement l’affectation et la satisfaction, puis la courbe **plafonne**.  
Au-delà, le gain devient faible alors que le temps de calcul augmente.  
Ce n’est pas une recommandation réglementaire ; c’est un résultat expérimental.

### Q10. « Pouvez-vous garantir qu’aucune école ne sera sacrifiée ? »
**Non.** Aucune politique ne garantit zéro établissement sous tension.  
COVERAGE **réduit** le nombre d’bases de support à remplissage nul (v3) dans notre modèle  
(274 vs 346 **bases** v3 pour TEACHER sur la démo figée), au prix de vœux n°1 en moins — proxy interne, pas un comptage d'écoles.  
Garantir l’absence totale de tension supposerait plus de moyens humains ou de postes — ce n’est pas un résultat algorithmique seul.

### Q11. « Où sont les preuves ? »
- Hashes des PDF sources dans le manifeste ;  
- hash de résultat par politique (`0ea2792c…`, `d4d40f0e…`, `60cda218…`) ;  
- seed public 20260811 ;  
- script `run_demo.py` pour rejouer ;  
- dossiers Why-not catégorisés.  
La preuve porte sur la **reproductibilité et la traçabilité**, pas sur la conformité légale totale.

### Q12. « Pourquoi ne pas maximiser uniquement le nombre d’affectés ? »
Parce que 1 199 affectés avec de mauvais vœux et des écoles vides n’est pas le même résultat  
que 1 199 affectés avec 405 vœux n°1 ou avec moins de bases à remplissage nul (v3).  
La cardinalité est prioritaire dans AFFECTA, mais elle ne dit pas tout sur la **qualité** du mouvement.

---

# CHECKLIST AVANT LA PRÉSENTATION

- [ ] Ouvrir `DEMO.md` + `demo_report.json` sous les yeux  
- [ ] Ne citer que les chiffres de la version figée  
- [ ] Prononcer la slide Limites en entier  
- [ ] Ne jamais dire « on remplace MVT1D »  
- [ ] Ne jamais dire « optimal » sans « UNKNOWN »  
- [ ] Avoir `run_demo.py` prêt en secours si on demande une rejouabilité  

FIN DU SUPPORT
