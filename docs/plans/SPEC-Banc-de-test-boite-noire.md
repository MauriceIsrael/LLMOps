# Spécification — Banc de test en boîte noire pour Archinex + LLMOps (ABE, version 2.1)

Statut : projet, 9 octobre 2026. **Version 2.1 : les critères de succès sont ceux du propriétaire du produit (vitesse, fiabilité et déterminisme, corrigibilité) ; voir §1.** Remplace la version 1 (« Archinex Benchmark Engine », comparaison à un LLM nu sur quatre axes). Destiné à un **dépôt séparé** (`archinex-benchmark`) qui n'importe ni le code d'Archinex ni celui de LLMOps.

Niveau de preuve : ce qui décrit l'interface de LLMOps est **[lu]** dans le contrat du Hub (v1.24). Ce qui décrit Archinex est **[à définir]** avec son équipe : je n'ai pas lu sa chaîne de délibération.

---

## 0. Ce qui change par rapport à la version 1

| Version 1 | Version 2 | Pourquoi |
|---|---|---|
| Deux systèmes : LLM nu contre chaîne complète | **Échelle de quatre systèmes** (S0 à S3) | sans elle, l'écart mesuré est celui de la connaissance, pas celui du système |
| Quatre axes de qualité de texte | **Trois dimensions de succès** posées par le propriétaire du produit (vitesse, fiabilité et déterminisme, corrigibilité), **cinq indicateurs primaires**, indicateurs secondaires pour expliquer | la valeur revendiquée n'est pas la qualité de la prose |
| Assertions « technologies obligatoires » | **Assertions de propriétés** | prescrire une pile récompense la conformité, pas la justesse |
| Vérité terrain dérivée du catalogue | **Vérité terrain indépendante**, issue d'un RFP réel, d'un extrait d'exploitation et d'annotations d'experts | la circularité rendait les axes 1 et 2 tautologiques |
| 4 cas, 5 itérations | **30 cas minimum**, plan apparié, intervalles de confiance, critères fixés avant mesure | 4 cas ne permettent aucune conclusion |
| Juge LLM comme mesure | Juge **secondaire**, calibré sur des étiquettes humaines, jamais dans une porte de décision | biais, instabilité |
| Un seul mode d'exécution | **Deux modes** : autonome et assisté (experts rejoués) | la chaîne suppose un humain qui décide |
| Promptfoo + Python | Python seul | un seul outil de plus à maintenir pour rien |
| Rapport « pourquoi Archinex a gagné » écrit par modèle | Explication **causale lue dans la traçabilité du système** | une narration générée n'est pas une preuve |

---

## 1. Objet, critères de succès et indicateurs

Le banc établit, sur des cas réels, si l'ensemble **Archinex + LLMOps** apporte quelque chose que ni un LLM seul, ni un LLM muni du même catalogue, n'apportent. Il peut conclure que **non**. Un résultat négatif est un résultat.

### 1.1 Les critères de succès (posés par le propriétaire du produit, 9 octobre 2026)

Le couple réussit s'il fait mieux sur au moins une de ces trois dimensions :

| Dimension | Ce que cela veut dire |
|---|---|
| **D1 — Aller plus vite** | (a) **choisir les bons sujets** : instruire d'abord ce qui bloque ; (b) **réemployer l'acquis antérieur** : ne pas refaire ce qui a déjà été établi |
| **D2 — Être fiable et déterministe** | ne rien affirmer sans fondement, et redonner le même résultat à entrées égales |
| **D3 — Pouvoir corriger sans tout remettre en cause** | une modification (exigence amendée, décision changée) n'ébranle que ce qui en dépend |

**Règle de succès : un premier indicateur qui démontre la supériorité sur une seule dimension suffit** pour dire que le couple apporte quelque chose. Cette règle est conservée telle quelle, avec trois garde-fous pour que « le premier indicateur » ne devienne pas « celui qui a bien marché » :

1. **Cinq indicateurs primaires** (deux pour D1 : P1a et P1b ; deux pour D2 : P2a et P2b ; un pour D3 : P3 ; définitions au §5.0), chacun **déclaré avant la première mesure**, avec son seuil et son sens.
2. La correction de **Holm** s'applique à l'ensemble de ces indicateurs primaires : « au moins un réussit » reste vrai après correction.
3. La conclusion **nomme** les dimensions atteintes et **liste** les autres (non atteintes ou non concluantes). On a le droit de dire « vitesse démontrée, corrigibilité non » ; on n'a pas le droit de taire le reste.

Tous les autres indicateurs (§5.2) sont **secondaires** : ils expliquent un résultat, ils ne le déclenchent pas.

### 1.2 Lien avec les indicateurs secondaires de la version 2.0

| Ancienne hypothèse | Rôle désormais |
|---|---|
| H1 détection des contradictions (M1) | explique D1a : un sujet bloquant bien choisi est souvent une contradiction repérée |
| H2 non-invention (M2), H4 traçabilité (M4) | composent D2 (fiabilité) |
| H3 cohérence doctrinale (M3) | indicateur secondaire de fiabilité |
| H5 reproductibilité (M5) | est l'indicateur P2b |
| H6 honnêteté sur l'état (M6) | indicateur secondaire de fiabilité |
| Effort (M7, M8) | mesures de coût de D1 |

---

## 2. Les systèmes comparés

| Id | Système | Connaissance | Processus | Humain |
|---|---|---|---|---|
| **S0** | LLM nu | aucune | un appel | non |
| **S1** | LLM + catalogue | **le même instantané de base de connaissance** que S2, injecté dans le contexte (récupération simple) | un appel | non |
| **S2** | Archinex + LLMOps, **autonome** | instantané de base de connaissance **épinglé** | chaîne complète | aucun : l'engagement reste ce que le système peut établir seul |
| **S3** | Archinex + LLMOps, **assisté** | idem | idem | **réponses d'experts rejouées** depuis un enregistrement (§4.3) |
| **S1+** | LLM + catalogue + **dossier antérieur en contexte** | idem S1, plus le dossier du cas A | un appel | non |

**S1+ n'existe que pour D1b (réemploi)** : c'est la façon naïve de réemployer un acquis (« voici le dossier précédent »). **Pour D3 (corrigibilité)**, les systèmes sans mémoire structurée (S0, S1, S1+) sont évalués avec **deux stratégies de correction**, et c'est la meilleure des deux, cas par cas, qui sert de référence : **R**, régénération complète à partir du RFP modifié ; **P**, « patch » (on donne le dossier précédent et la modification, et on demande de ne changer que ce qui en dépend). Le comparateur n'est pas un homme de paille.

Lectures permises :

- **S1 − S0** : ce que vaut la connaissance seule. Ce n'est pas le système.
- **S2 − S1** : ce que vaut le processus (délibération, contraintes, scellement), à connaissance égale. **C'est la mesure principale.**
- **S3 − S2** : ce que l'expert ajoute, et ce que la chaîne en fait. Mesure de la valeur d'un humain bien outillé, non d'une automatisation.

**Figé et consigné pour chaque exécution** : identifiant et version de chaque modèle, paramètres, empreinte des invites, instantané de base de connaissance (identifiant et empreinte), version du contrat du Hub, version d'Archinex, empreinte du jeu de cas, graine, date. Aucune comparaison entre deux manifestes différents sans le dire dans le rapport.

---

## 3. Le jeu de cas

### 3.1 Sources
1. **Le RFP réel** : base des cas de contradiction et de sous-spécification.
2. **L'extrait d'exploitation (centre d'exploitation)** : base des cas de **non-régression**. L'incident arrivé dit ce qu'un bon design aurait dû prévoir ; cette vérité terrain ne dépend pas du catalogue.
3. **Cas construits à la main** à partir de pièges connus (technologie à la mode, hébergement hors périmètre, sous-dimensionnement).

Toute source est **anonymisée avant d'entrer dans le dépôt** (noms de clients et de sites, adresses, personnes), avec la liste noire du Hub (`data/kb/anonymization_denylist.txt`) comme point de départ.

### 3.2 Format d'un cas

Un cas contient le texte soumis, la **vérité terrain annotée** et des **propriétés** à vérifier. Il ne contient **aucune liste de produits obligatoires**.

```python
class Provenance(BaseModel):            # d'où vient la vérité terrain
    source: Literal["rfp-reel", "incident-exploitation", "construit"]
    annotator_ids: list[str]            # au moins deux pour les cas annotés
    agreement: float | None             # accord entre annotateurs (κ), si deux annotations

class GroundContradiction(BaseModel):
    id: str
    statement_ids: list[str]            # les passages du RFP en tension (extraits par offset)
    kind: Literal["contradiction", "incoherence-reglementaire", "incoherence-technique"]
    why: str

class GroundGap(BaseModel):
    id: str
    about: str                          # ce que le RFP ne dit pas et qu'il faut savoir
    blocking: bool                      # empêche de décider sans réponse

class Property(BaseModel):              # propriété d'architecture, pas un produit
    id: str
    kind: Literal["interdit", "obligatoire"]
    text: str                           # « aucun magasin non durable pour des commandes critiques »
    check: Literal["structure", "extracteur", "relecture"]   # comment elle se vérifie (§5)
    refs: list[str]                     # identifiants réels de la base (contrôles, principes) ou de l'incident

class Amendment(BaseModel):             # une correction appliquée à un dossier (D3)
    id: str
    kind: Literal["exigence-amendee", "decision-changee", "hypothese-retiree"]
    description: str                    # « passer de deux sites actif/actif à trois sites »
    impacted: list[str]                 # éléments du dossier qui DOIVENT changer (annoté par deux experts)
    not_impacted: list[str]             # éléments qui NE DOIVENT PAS changer (le reste du dossier de référence)

class ReuseLink(BaseModel):             # un élément de B qui a son équivalent établi dans A (D1b)
    element_b: str
    element_a: str
    holds_under_b: bool                 # les hypothèses de validité de l'acquis tiennent-elles pour B ?

class RFPCase(BaseModel):
    id: str
    title: str
    category: Literal["contradiction", "mode-technologique", "sous-specifie", "post-mortem"]
    rfp_text: str
    contradictions: list[GroundContradiction]
    gaps: list[GroundGap]
    properties: list[Property]
    expected_provisional: bool          # le dossier doit-il rester provisoire sans réponse d'expert ?
    expert_script: list[ScriptedAnswer] # réponses rejouées en mode assisté (§4.3), vide sinon
    prior_case_id: str | None           # cas A déjà traité, dont B peut réemployer l'acquis (D1b)
    reuse_links: list[ReuseLink]        # annoté par deux experts ; vide si prior_case_id est vide
    amendments: list[Amendment]         # corrections à appliquer, une à la fois (D3)
    reference_dossier: list[str]        # éléments du dossier de référence (vérité terrain pour D3)
    split: Literal["dev", "held-out"]
    provenance: Provenance
```

Les identifiants de règles et de contrôles de `properties[].refs` sont ceux de la **base de connaissance réelle** (par exemple `SNC-REQ-01`), vérifiés par un test du jeu de cas. Une propriété issue d'un incident cite l'incident.

### 3.3 Protocole d'annotation
- Deux annotateurs indépendants par cas ; désaccords arbitrés par un troisième ; accord (κ de Cohen) consigné. Un cas dont l'accord est inférieur à 0,6 est réécrit ou retiré.
- Un annotateur ne voit **ni** les sorties des systèmes **ni** le catalogue pendant l'annotation.
- Les **propriétés** sont écrites avant toute exécution et ne sont plus modifiées après la première mesure (sinon : nouvelle version du jeu).

### 3.4 Taille et séparation
- **Tailles minimales pour conclure**, par indicateur primaire : P1a et P2 : 20 cas ; **P1b : 8 paires de cas** (A puis B, du même domaine) ; **P3 : 20 corrections** réparties sur au moins 10 cas. 10 à 15 cas suffisent pour le pilote (§12, J1).
- `dev` (environ 60 %) sert à construire les extracteurs et les métriques ; `held-out` (environ 40 %) n'est exécuté que pour les rapports qui concluent. Aucun cas du jeu, ni sa réponse, n'entre dans la base de connaissance ni dans les invites d'un système.
- Répartition cible par catégorie : contradictions, mode technologique, sous-spécification, post-mortems, chacune au moins 6 cas.

---

## 4. Interface boîte noire des systèmes

Chaque système est un adaptateur qui prend un cas et rend un **artefact d'exécution normalisé**. Le banc ne connaît ni les agents, ni les invites, ni le graphe interne.

### 4.1 Contrat d'adaptateur

```python
class Claim(BaseModel):                 # une affirmation atomique du système
    id: str
    kind: Literal["choix", "hypothese", "fait", "question", "conflit"]
    text: str
    entities: list[str]                 # technologies, composants, normes, normalisés (§5.1)
    assertion: Literal["affirme", "propose", "inconnu"]
    evidence: list[EvidenceRef]         # références rendues par le système lui-même

class EvidenceRef(BaseModel):
    kind: Literal["rfp", "base-connaissance", "decision", "autre"]
    ref: str                            # passage du RFP (offset) ou clé de connaissance + version

class RunArtifact(BaseModel):
    system: Literal["S0", "S1", "S2", "S3"]
    case_id: str
    iteration: int
    raw_text: str                       # tout ce que le système a produit, en texte
    claims: list[Claim] | None          # structure native si le système en fournit une
    graph: dict | None                  # éléments et relations, si fournis
    declared_provisional: bool | None
    questions: list[str]
    conflicts: list[str]
    expert_interactions: int            # nombre de sollicitations d'un expert
    expert_seconds: float               # temps humain consommé (réel ou simulé)
    tokens_in: int
    tokens_out: int
    wall_seconds: float
    manifest_id: str                    # renvoie au manifeste de l'exécution (§2)

class SystemUnderTest(Protocol):
    def run(self, case: RFPCase, iteration: int, mode: Literal["autonome", "assiste"]) -> RunArtifact: ...
```

### 4.2 Normalisation commune
Les systèmes S0 et S1 ne rendent que du texte ; S2 et S3 rendent aussi de la structure. Pour qu'aucun système ne soit avantagé par son format :
1. **Un extracteur unique** transforme le texte de **tous** les systèmes en `claims` (§5.1) ; il est versionné et validé (§7).
2. Pour S2 et S3, le banc calcule les métriques **deux fois** : sur la structure native, et sur le texte passé dans l'extracteur commun. Le rapport affiche les deux. Un écart important signale un problème d'extraction, pas un résultat.

### 4.3 Les deux modes de S2/S3
- **Autonome (S2)** : aucun humain. Le bon comportement n'est pas de produire un HLD complet, c'est d'**ouvrir des questions, lever des conflits et rester provisoire** quand le RFP n'établit pas assez.
- **Assisté (S3)** : les sollicitations d'expert reçoivent les `expert_script` du cas, rejoués dans l'ordre d'apparition. Si le système pose une question que le script ne couvre pas, la réponse est « sans réponse » et l'événement est compté (`expert_unanswered`). Le script est annoté avant toute exécution (§3.3), jamais ajusté après une sortie.
- Le mode assisté **ne mesure pas la qualité des décisions d'expert** (elles sont dictées) : il mesure ce que la chaîne en fait. Le rapport le dit.

### 4.4 Adaptateur du Hub (LLMOps) — [lu]
Le Hub est utilisable en boîte noire par son API (contrat v1.24) ; un jeton de service porte les portées de création et de délégation. Pour un cas :

1. `POST /api/engagements` crée un engagement **géré** dont l'identifiant est dérivé du cas et de l'itération ; `PUT …/members` déclare un contributeur, un décideur et un administrateur.
2. L'écriture passe par `POST …/{subjects, statements, questions, requirements, decisions}`, avec une clé d'idempotence ; `…/decisions/{id}/assert` par un décideur **distinct de l'auteur** (mode assisté).
3. Le système expose son état par `GET …/facts`, `GET …/lineage` et `POST …/exports` puis `GET …/exports/{id}` : l'**instantané scellé** contient les conflits, les manques, les décisions, les références à la base (`kb_references`, `unresolved_references`), la lignée et l'indicateur `is_provisional`.
4. L'instantané de base de connaissance est **épinglé** (`PUT …/kb-pin`) pour que S2 et S3 lisent la même connaissance que S1.

La normalisation de l'instantané en `RunArtifact` est déterministe (aucun modèle).

**Décision (9 octobre 2026) : le banc compare les propriétés de l'instantané, pas un HLD en prose.** L'instantané est plus facile à comparer et contient tout ce qui permettra de générer ensuite une prose fiable (décisions, faits, conflits, manques, références, lignée, indicateur provisoire). Le Hub ne rend d'ailleurs pas de prose (pas de modèle sur ses routes). Évaluer une prose générée à partir de l'instantané est une étape **ultérieure et distincte** : elle mesurerait le générateur, pas le système. Pour S0 et S1, qui ne produisent que du texte, la comparaison passe par l'extracteur commun (§4.2).

### 4.5 Adaptateur d'Archinex — [à définir]
Archinex doit fournir un point d'entrée **par lot** (cas en entrée, artefact en sortie, sans interface graphique) et un mode d'exécution où les sollicitations d'expert sont servies par le banc (§4.3). Sans cela, S2 et S3 ne sont pas automatisables.

---

## 5. Métriques

Toutes les métriques sont calculées **par cas et par itération**, puis agrégées (§6). Les métriques de §5.2 (M1 à M8) sont **secondaires**, sauf M2 et M5 qui servent d'indicateurs primaires (P2a, P2b). Une métrique qui dépend d'un modèle est marquée **(M)** et n'entre jamais dans une porte de décision.

### 5.0 Les indicateurs primaires

Un par dimension (deux pour D1 et pour D2) ; leurs seuils sont signés avant la première mesure (§6, §14).

**P1a — Focalisation (D1a) : R-précision des sujets.**
Soit *R* le nombre de manques **bloquants** annotés pour le cas. On prend les *R* premières questions ou sujets que le système propose d'instruire (ordre du système). `P1a = |manques bloquants couverts par ces R premiers| / R`. Sa valeur est entre 0 et 1 ; plus c'est haut, moins on instruit de sujets sans importance avant d'arriver à l'essentiel. Comparateur S1 : on lui demande « liste, par ordre d'importance, les questions à poser avant de concevoir ». Une question couvre un manque si elle porte sur le même passage du RFP ou le même sujet annoté.

**P1b — Réemploi (D1b) : sollicitations d'expert évitées.**
Sur une paire (A, B) avec `reuse_links` : `P1b = 1 − I(B | A) / I(B | sans A)`, où *I* est le nombre de sollicitations d'expert pour atteindre les **mêmes décisions finales** sur B (mode assisté, scripts annotés). La valeur est entre 0 et 1 (plus c'est haut, plus on a économisé). **Condition de validité** : `réemplois abusifs = 0`, c'est-à-dire aucun élément repris de A pour B alors que `holds_under_b` est faux, et aucun élément repris **sans confirmation** d'une personne (le Hub ne réemploie jamais automatiquement : un acquis est proposé, puis confirmé hypothèse par hypothèse). Une paire avec un réemploi abusif est invalide pour P1b et signalée. Comparateur S1+ : le dossier A en contexte, mêmes scripts.

**P2a — Fiabilité (D2) : taux d'affirmations sans fondement.**
C'est M2 (`taux_invention`) : part des affirmations qui n'ont aucune preuve se résolvant vers le RFP ou la base de connaissance au bon numéro de version (§5.2). **Plus bas c'est mieux.**

**P2b — Déterminisme (D2) : taux de reproduction.**
C'est M5 (`jaccard_moyen` sur les éléments normalisés) sur *k* ≥ 5 exécutions du même cas au même manifeste. Il est rapporté **deux fois** : sur la **partie déterministe seule** (le Hub rejouant un dossier enregistré) et sur le **pipeline complet** (avec la part de modèle d'Archinex). La première démontre une propriété du Hub, déterministe par construction (importante pour l'exploitation, mais acquise d'avance) ; la seconde est la seule qui mesure la chaîne réelle. Le seuil de succès porte sur la seconde.

**P3 — Corrigibilité (D3) : dérive collatérale.**
Pour chaque `Amendment`, le banc applique la correction par la stratégie du système (S2/S3 : l'API du Hub, par remplacement de la décision ou amendement de l'exigence, puis nouvel export ; S0, S1, S1+ : R et P, §2) et compare le dossier avant et après :
`P3 = |éléments non impactés qui ont changé| / |not_impacted|`.
**Plus bas c'est mieux** : zéro signifie que la correction n'a touché que ce qui en dépendait. Valeurs secondaires associées : rappel et précision de l'**ensemble impacté signalé** par le système (pour S2/S3, il vient de la lignée : sujets passés en « fondation contestée » ; pour les autres, d'une demande explicite « liste ce qui change »), et coût de la correction (jetons, temps, sollicitations d'expert) rapporté au coût d'une régénération complète.

**Lecture honnête de P2b et P3** : le Hub est déterministe et incrémental par construction. Mesurer ces deux propriétés sur lui seul est un contrôle de bon fonctionnement, pas une démonstration de supériorité. Ce qui compte est ce qu'elles deviennent dans la chaîne complète avec Archinex. Le rapport affiche les deux niveaux (composante / chaîne).

### 5.1 Extraction commune
`extract(raw_text) -> list[Claim]` : extraction typée par un modèle **figé** (autre famille que les systèmes évalués), sortie JSON contrainte par schéma, entités normalisées par un dictionnaire (`approved_stack.json` du banc, **indépendant** du catalogue de LLMOps : maintenu par les annotateurs, pas par l'équipe du système). L'extracteur est validé avant usage (§7).

### 5.2 Définitions

**M1 — Détection des contradictions (H1)**
`rappel = |contradictions du cas reconnues| / |contradictions du cas|` ; `précision = |signalements justes| / |signalements|`.
Un signalement est reconnu s'il porte sur les mêmes passages du RFP (recouvrement d'offsets ≥ 50 %) **sous forme de conflit ou de question**, pas de simple mention. Une contradiction **corrigée en silence** (le design évite la mauvaise option sans la nommer) compte comme **non détectée** et est relevée à part (`silent_fix`).
Calcul : S2/S3 par la structure (`conflicts`, `questions`) ; tous par l'extracteur (`kind ∈ {conflit, question}`).

**M2 — Non-invention (H2)**
- `taux_invention = |claims affirmés sans preuve| / |claims affirmés|`. Un claim est **sans preuve** si aucune `evidence` ne se résout vers un passage du RFP ou une clé de la base de connaissance au bon numéro de version. La résolution est **déterministe** pour S2/S3 (références de l'instantané) ; pour S0/S1, un claim n'a de preuve que s'il cite un passage retrouvé par recherche exacte dans le RFP.
- `rappel_manques = |manques du cas qui donnent lieu à une question| / |manques du cas|`.
- `affirmations_sur_manque` : nombre de claims `affirme` qui tranchent un manque **bloquant** du cas sans réponse d'expert. Doit être nul.

**M3 — Cohérence doctrinale (H3)**
Pour chaque `Property` : vérifiée selon `check` :
- `structure` : test déterministe sur le graphe ou l'instantané (S2/S3) ;
- `extracteur` : test déterministe sur les `entities` (tous systèmes) ;
- `relecture` : jugée par deux relecteurs humains en aveugle (§5.3).

`violations` (propriétés « interdit » enfreintes), `obligations_satisfaites / obligations`, et `violations_reglementaires` (sous-ensemble citant un contrôle réglementaire). Aucune liste de produits n'est exigée : une propriété qui nomme un produit n'est acceptée que si l'incident ou la norme le nomme.

**M4 — Traçabilité (H4)**
- `part_tracee = |claims affirmés avec au moins une preuve qui se résout| / |claims affirmés|`.
- `références_mortes` : preuves qui ne se résolvent pas (clé absente, version inexistante).
- (M) `ancrage` : jugement d'un modèle de la fidélité de chaque claim à ses preuves — **indicatif seulement**, voir §5.4.

**M5 — Reproductibilité (H5)**
Sur *k* exécutions d'un même cas (même manifeste) :
- `jaccard_moyen` des **ensembles de claims normalisés** (entité + type + assertion), non des mots : `2/(k(k−1)) Σ |A_i ∩ A_j| / |A_i ∪ A_j|`.
- `identité_decisions` : part des décisions identiques d'une exécution à l'autre.
- `identité_scellé` : part des exécutions qui donnent la même empreinte d'instantané (S2/S3 seulement ; attendue forte pour la partie déterministe).
- Distance d'édition de graphe : **seulement** pour les graphes de moins de 30 éléments (calcul exponentiel) ; sinon distance d'ensemble sur éléments et relations normalisés.

**M6 — Honnêteté sur l'état (H6)**
Confusion entre `declared_provisional` et `expected_provisional` du cas : précision, rappel et taux de faux « final » (un système qui se déclare final alors que le cas ne l'est pas — l'erreur grave). S0 et S1 n'ont pas de déclaration : le banc applique à leur texte la détection de réserves (« sous réserve », « à confirmer ») par l'extracteur, et le dit.

**M7 — Coût**
Jetons, durée, appels de modèle, coût en monnaie calculé au tarif consigné dans le manifeste. En mode assisté : `expert_interactions` et `expert_seconds` (temps du script, étalonné sur un échantillon réel).

**M8 — Relecture humaine en aveugle (étalon)**
Sur un échantillon fixe de cas, deux ou trois architectes classent les sorties de S0 à S3, **sans savoir quel système est quel**, et relèvent les défauts (contradiction non vue, invention, violation). Ordre aléatoire, sorties rendues dans un format identique. Accord entre relecteurs consigné. **C'est l'étalon** : si les métriques automatiques ne classent pas comme les relecteurs, ce sont elles qu'on corrige.

### 5.3 Relecture humaine des propriétés
Les propriétés `check: relecture` et M8 utilisent la même procédure : outil de relecture local, sortie anonymisée et mélangée, deux relecteurs, arbitrage par un troisième.

### 5.4 Le juge LLM (M)
Autorisé comme indicateur, sous conditions : modèle figé d'une famille différente de tous les systèmes ; ne voit ni l'identité du système ni l'ordre ; **trois jugements** par sortie, médiane ; invite versionnée. **Calibrage obligatoire** : κ ≥ 0,6 contre les étiquettes humaines d'un échantillon d'au moins 50 jugements, sinon la métrique est affichée comme *non fiable* et exclue des conclusions. Il n'entre dans aucun critère de succès.

---

## 6. Plan d'expérience et statistiques

- **Plan apparié** : chaque cas est exécuté par chaque système, *k* ≥ 5 itérations. L'unité statistique est le **cas** (la moyenne de ses itérations), non l'itération.
- **Indicateurs primaires et seuils fixés avant mesure** (fichier `hypotheses.yaml`, daté et haché) : pour chacun des cinq (P1a, P1b, P2a, P2b, P3), le sens, la comparaison, le seuil de succès et le niveau de confiance. Exemples de forme : « P1a : la R-précision de S2 dépasse celle de S1 d'au moins 0,20, borne basse de l'intervalle à 95 % > 0 » ; « P3 : la dérive collatérale de S2 est inférieure d'au moins 50 % à celle de la meilleure stratégie de S1, borne haute de l'intervalle < 0 ». **Règle de succès : au moins un des cinq atteint son seuil après correction de Holm** (§1.1). Les seuils chiffrés sont proposés par les annotateurs et signés par le mainteneur du Hub et le responsable produit d'Archinex (§14, question 3), pas décidés par l'équipe qui construit le banc.
- **Inférence** : intervalle de confiance par *bootstrap* sur les cas (10 000 rééchantillonnages) ; test de permutation apparié ou de Wilcoxon sur les différences par cas ; taille d'effet rapportée avec chaque valeur de *p* ; correction de Holm sur les cinq indicateurs primaires.
- **Puissance** : le banc calcule, pour l'effet visé, le nombre de cas nécessaire et **refuse de conclure** en dessous (rapport « non concluant »).
- **Hors échantillon** : les conclusions ne s'appuient que sur `held-out` ; `dev` sert à la mise au point.
- **Résultats négatifs ou mitigés** : affichés avec la même visibilité que les positifs.

---

## 7. Validité de l'instrument

Avant de croire un chiffre :

| Contrôle | Critère |
|---|---|
| L'extracteur est fidèle | F1 ≥ 0,85 sur 30 sorties étiquetées à la main, par catégorie de claim |
| Une sortie parfaite fabriquée à la main obtient le maximum | exigé pour chaque métrique |
| Une sortie vide obtient le minimum | exigé pour chaque métrique |
| Le bourrage de mots-clés ne gagne pas | une sortie qui cite tous les produits attendus sans cohérence ne dépasse pas la médiane |
| Mutation des évaluateurs | retirer une règle d'une métrique fait échouer au moins un test |
| Le jeu n'a pas fuité | aucune phrase d'un cas dans la base de connaissance épinglée ni dans les invites (test de recherche exacte) |
| Les références de propriétés existent | tout `refs` se résout dans la base ou dans l'incident cité |
| L'accord humain est suffisant | κ ≥ 0,6 pour les annotations et pour M8 |

Ces contrôles sont des tests automatisés du banc lui-même (`tests/instrument/`).

---

## 8. Reproductibilité et traçabilité

- **Manifeste** par exécution (§2), enregistré avec les artefacts.
- **Stockage adressé par le contenu** des sorties brutes et des artefacts normalisés ; aucune sortie n'est écrasée.
- **Rejeu** : les réponses de modèle sont enregistrées (cassettes) ; le banc peut recalculer toutes les métriques et tout le rapport **sans appeler un modèle**. Un changement de métrique se vérifie sur les mêmes sorties.
- **Plafonds de coût** par exécution et par jour ; arrêt propre au dépassement.
- Les temps et les coûts sont mesurés, jamais estimés.

---

## 9. Architecture logicielle

Python 3.11+, `uv` ou Poetry, Pydantic v2, Typer et Rich, `httpx` (adaptateurs), Jinja2 (rapports), `pytest`. NetworkX seulement pour les petits graphes (M5). Pas de Promptfoo.

```
archinex-benchmark/
├── README.md
├── pyproject.toml
├── hypotheses.yaml            # hypothèses, métriques, seuils (daté, haché)
├── data/
│   ├── cases/                 # un fichier par cas (RFPCase), dev/ et held-out/
│   ├── annotations/           # annotations brutes et accords
│   ├── scripts_expert/        # réponses rejouées (mode assisté)
│   ├── normalisation/         # dictionnaire d'entités (indépendant du catalogue)
│   └── anonymisation/         # liste noire
├── src/abe/
│   ├── models/                # RFPCase, Claim, RunArtifact, Manifest, Report
│   ├── systems/               # base, s0_nu, s1_catalogue, s2_s3_hub_archinex
│   ├── extraction/            # extracteur commun, validation
│   ├── metrics/               # m1_detection … m7_cout
│   ├── judge/                 # juge LLM, calibrage
│   ├── review/                # relecture humaine en aveugle (M8)
│   ├── stats/                 # bootstrap, permutation, Holm, puissance
│   ├── store/                 # manifestes, cassettes, stockage par contenu
│   ├── reporting/             # modèles Jinja2 (Markdown, HTML)
│   └── cli.py                 # abe run | replay | metrics | review | report | check-instrument
└── tests/
    ├── instrument/            # validité de l'instrument (§7)
    └── unit/
```

Commandes :
`abe run --systems S0,S1,S2,S3 --split dev --iterations 5` ; `abe replay` (recalcul sans modèle) ; `abe metrics` ; `abe review export|import` ; `abe report --split held-out --format md,html` ; `abe check-instrument`.

---

## 10. Rapport

1. **Verdict par dimension (D1, D2, D3)** : critère, valeur, intervalle, taille d'effet, **atteint / non atteint / non concluant** (puissance).
2. **Échelle S0 → S3** : un tableau par métrique, avec la décomposition connaissance (S1 − S0), processus (S2 − S1), expert (S3 − S2).
3. **Détail par cas** : contradictions réelles, ce que chaque système en a fait (détectée, corrigée en silence, ignorée), inventions relevées, violations, avec les passages concernés.
4. **Explication causale lue, pas racontée** : pour S2/S3, la raison d'un blocage est celle de la traçabilité du système (règle, version, faits, décision dans la lignée). Aucune narration générée par un modèle.
5. **Relecture humaine** (M8) face aux métriques : concordance des classements.
6. **Limites** générées : métriques non fiables, cas sous le seuil d'accord, écarts structure/texte, mode assisté.
7. **Manifeste** complet.

---

## 11. CI et exploitation

| Niveau | Déclencheur | Contenu | Durée visée |
|---|---|---|---|
| Déterministe | chaque PR du banc ou d'un système | tests d'instrument, métriques recalculées sur cassettes, adaptateur du Hub contre un Hub local | < 5 min |
| Régression | planifié (nuit / semaine) et à la montée de version d'Archinex ou du Hub | exécution réelle de S2 et S3 sur `dev`, plafond de coût | selon plafond |
| Conclusion | à la demande, avant une communication | S0 à S3 sur `held-out`, relecture humaine | — |

**Porte de décision** : aucune régression de S2/S3 sur les cinq indicateurs primaires, ni sur M1, M2, M4 et M6, par rapport à la dernière exécution de référence (comparaison au système lui-même, non au LLM nu). Les métriques (M) ne participent jamais à la porte.

---

## 12. Plan d'implémentation par jalons

| Jalon | Contenu | Livrable / critère d'acceptation | Dépendances externes |
|---|---|---|---|
| **J0 — Protocole** | hypothèses, seuils, protocole d'annotation, règles d'anonymisation | `hypotheses.yaml` signé par le propriétaire du produit | — |
| **J1 — Jeu pilote et premier signal** | 10 à 15 cas issus du RFP et de l'extrait d'exploitation, annotés à deux, dont **3 paires (A, B)** et **au moins 10 corrections annotées** ; S0, S1, S1+ et S2/S3 lancés à la main ; relecture en aveugle par 2 à 3 architectes. **Voie rapide** : mesurer d'abord P3 et P2b (aucune relecture humaine nécessaire, automatisables sur un dossier enregistré importé dans le Hub), pour obtenir un premier signal avant que P1a et P1b (qui demandent des experts et Archinex) soient prêts | tableau des cinq indicateurs primaires par système ; **décision de continuer ou non** | Archinex utilisable sur ces cas |
| **J2 — Squelette** | modèles, adaptateurs S0 et S1, stockage, manifestes, cassettes, `abe run` et `replay` | un cas rejouable de bout en bout sans modèle | — |
| **J3 — Adaptateurs S2/S3** | adaptateur du Hub (§4.4), adaptateur d'Archinex (§4.5), mode assisté | un cas complet en S2 et en S3, instantané normalisé | **Archinex : point d'entrée par lot**, avec sollicitations d'expert servies par le banc |
| **J4 — Métriques et instrument** | extracteur, M1 à M7, tests d'instrument | tous les contrôles du §7 verts ; extracteur à F1 ≥ 0,85 | — |
| **J5 — Statistiques et rapport** | bootstrap, permutation, Holm, puissance ; gabarits Markdown et HTML ; M8 | rapport sur le pilote, avec « non concluant » correctement émis | — |
| **J6 — Extension et CI** | 30 cas ou plus, répartition par catégorie, trois niveaux de CI | première exécution sur `held-out` avec verdict par dimension | — |

**J1 avant tout code** : si l'effet n'est pas visible à la main, il ne le sera pas dans un rapport automatisé.

---

## 13. Menaces à la validité et réponses

| Menace | Réponse |
|---|---|
| Circularité (le système est jugé sur sa propre connaissance) | vérité terrain indépendante (RFP, incidents, annotateurs) ; S1 donne la même connaissance au concurrent |
| Réglage au jeu de test | séparation `dev` / `held-out`, propriétés figées avant mesure |
| Fuite du jeu dans la base ou les invites | test de recherche exacte (§7) |
| Extracteur inégal selon le système | extracteur unique, métriques doubles structure / texte |
| Juge biaisé | juge secondaire, calibré, hors portes |
| Humain simulé qui « souffle » la réponse | scripts annotés avant exécution, interactions non couvertes comptées |
| Température 0 supposée déterministe | *k* itérations, M5 mesuré, manifeste |
| Cas trop peu nombreux | puissance calculée, rapport « non concluant » |
| Modèles hébergés qui changent | versions consignées, cassettes, comparaison seulement à manifeste égal |
| Annotateurs d'accord par hasard | κ, double annotation, tiers |
| Données confidentielles dans le dépôt | anonymisation, liste noire, revue avant chaque ajout |

---

## 14. Questions ouvertes

1. **Archinex** *(question posée à son équipe par la PR de cette spécification)* : existe-t-il un **mode par lot** (un cas en entrée, un artefact en sortie, sans interface graphique) et un **mode où les sollicitations d'expert sont servies par un script** plutôt que par une personne ? Sans les deux, S2 et S3 ne sont pas automatisables (J3 en dépend). Si l'un manque, quelle est la plus petite modification qui le fournirait ?
2. ~~**Texte ou propriétés**~~ **Tranché le 9 octobre 2026 : les propriétés de l'instantané** (§4.4).
3. **Seuils chiffrés (J0)** : les **critères** sont posés (§1.1). Il reste les **chiffres** : de combien la focalisation doit-elle gagner, quelle dérive collatérale est acceptable, quelle économie de sollicitations compte ? Ils sont écrits avant la première mesure et signés par le mainteneur du Hub et le responsable produit d'Archinex, sur proposition des annotateurs.
4. **Annotateurs** : qui, combien d'heures, quelle indépendance par rapport à l'équipe qui construit les systèmes ?
5. **Étalonnage du temps d'expert** (M7) : mesure sur un échantillon réel ou valeur de référence ?
6. **Matrice de conformité** : sans K17 (exigence → contrôle dans l'instantané), la partie « obligations réglementaires » de M3 repose sur l'extracteur pour S2/S3 ; avec K17, elle devient structurelle.
7. **Hébergement du dépôt, du stockage des sorties et des secrets** des appels de modèle.

---

## Annexe A — Le cas TC-SEC-001 réécrit

Version 1 : « interdit : AWS us-east-1 ; obligatoire : SecNumCloud Provider, Région UE souveraine ; règles RULE-SOV-01, RGPD-ART-44 » (identifiants inexistants, produits imposés).

Version 2 (extrait) :

```json
{
  "id": "TC-CONTRA-001",
  "title": "Données biométriques et calcul hors UE",
  "category": "contradiction",
  "rfp_text": "…workers de calcul instanciés sur la région AWS us-east-1 avec réplication passive sur site en France…",
  "contradictions": [{
    "id": "K1",
    "statement_ids": ["rfp:412-486", "rfp:131-190"],
    "kind": "incoherence-reglementaire",
    "why": "Traitement de données biométriques de personnes de l'UE hors UE, alors que le RFP exige l'immunité aux lois extraterritoriales."
  }],
  "gaps": [{"id": "G1", "about": "Qualification du fournisseur d'hébergement exigée ?", "blocking": true}],
  "properties": [
    {"id": "P1", "kind": "interdit", "text": "Aucun traitement de données biométriques hors du périmètre juridique exigé par le RFP, sans exception justifiée et tracée",
     "check": "extracteur", "refs": ["SNC-REQ-01"]},
    {"id": "P2", "kind": "obligatoire", "text": "La contradiction entre le lieu de calcul et l'exigence de souveraineté est nommée et soumise à décision",
     "check": "structure", "refs": []}
  ],
  "expected_provisional": true,
  "split": "dev"
}
```

Le bon comportement attendu n'est pas un design qui évite discrètement us-east-1 : c'est un **conflit nommé**, une **question ouverte** et un dossier **provisoire** tant qu'aucun décideur n'a tranché.
