# ADR-KH-01 — Knowledge Hub : contrats exposés et engagements envers la suite (amendé par le propriétaire du KH)

**Statut** : **projet d'amendement — adoption par le propriétaire du Knowledge Hub requise** (voir « Décision d'adoption » en fin de fichier).
Rien de ce qui suit n'est opposable tant que cette décision n'est pas inscrite.

**Domicile** : ce dépôt (LLMOps, rôle de Knowledge Hub), `docs/adr/`. Le préfixe `ADR-KH-nnn` y est adopté (le texte d'origine le propose pour lever la collision `ADR-0014` côté KH contre `ADR-017` côté Architecture Studio).
La suite interdit chez elle ce préfixe, pour qu'ouvrir un canal vers un système ne revienne pas à le faire entrer dans la suite (`docs/DECISIONS.md` de Document Studio, KH-1 et KH-2) : cet ADR est donc **un texte du Hub**, sans attestation à propager dans la suite.

**Provenance du texte d'origine** : fichier `docs/knowledge-hub/ADR-KH-01-CONTRATS-EXPOSES.md` du dépôt `AM-padawan-coder/Document-studio` (commit `9555eaf`, versé le 2026-09-12 « verbatim, avec son empreinte »).
SHA-256 : `7a82efca0105f33b4ca4e37a77d373b8653243e91ea6b4c6ae3f5ee760483c2c`. Statut d'origine : *proposé, révision 2*, « rédigé par la suite, à amender et adopter par le propriétaire du KH ».

**Règle de forme** (celle de la suite, `ADR-SUITE-00` règle 4, telle que rapportée par Document Studio) : **aucun mot du texte d'origine n'est réécrit**. Il est reproduit ci-dessous à l'identique (en citation), puis amendé par des paragraphes additifs datés.

Textes liés : [`../plans/ALIGNEMENT-Document-Studio-Knowledge-Hub.md`](../plans/ALIGNEMENT-Document-Studio-Knowledge-Hub.md) (confrontation au code), [`../plans/PLAN-IMPLEMENTATION-Bundle-Engagement.md`](../plans/PLAN-IMPLEMENTATION-Bundle-Engagement.md) (lots), [`../contracts/knowledge-hub-api-v1.md`](../contracts/knowledge-hub-api-v1.md).

---

## Partie I — Texte d'origine (inchangé)

> # ADR-KH-01 — Knowledge Hub : contrats exposés et engagements envers la suite
>
> **Statut** : proposé, révision 2 (intègre REVUE-CONTRATS-KH-2026-08-31 ;
> rédigé par la suite, à amender et adopter par le propriétaire du KH).
> **Miroir de** : ADR-SUITE-05 rév. 2.
> **Numérotation** : le KH adopte le préfixe **ADR-KH-nnn** (collision
> constatée : ADR-0014 côté KH vs ADR-017 côté AS — une citation croisée
> non préfixée est ambiguë).
>
> ## Décision 1 — Les surfaces, telles qu'elles sont
>
> Quatre surfaces constatées, deux au contrat :
>
> 1. **Contrat hors-ligne (fixtures scellées)** — `fixtures/*.json` sous
>    `schema_version`, guide d'intégration tiers, client de référence.
>    **C'est la surface d'intégration applicative de la suite** : un
>    consommateur développe et tourne sans démarrer le KH. Elle entre au
>    registre de canaux de la suite moyennant trois champs d'enveloppe
>    (CONTRATS_KH §enveloppe).
> 2. **Serveur(s) MCP** — 23 outils sur deux serveurs (11 plan
>    Connaissance, 12 plan Engagement), SSE/STDIO, jeton Bearer.
>    **Réservé aux agents** — jamais un transport d'appel applicatif
>    synchrone (protocole de session).
> 3. *Hors contrat* : accès direct au graphe et Cypher (`query_graph`) —
>    exploration humaine uniquement (d'autant que le plan Connaissance
>    n'est pas paramétré, voir D3.5).
> 4. *Hors contrat, déclarée* : la **boîte aux lettres GitHub**
>    (`github_adapter` : création d'issues pour router les questions
>    d'élicitation, relecture des commentaires). Surface assumée du
>    workflow d'élicitation, sans contact avec la suite.
>
> Les « API HTTP de suggestion et d'élicitation » de la révision 1
> n'existent pas et ne sont plus des surfaces déclarées ; le besoin est
> couvert par la surface 1.
>
> ## Décision 2 — Ce que le KH ne fait pas (portée exacte)
>
> - **Le KH n'appelle aucune API de la suite.** (Reformulation à portée
>   exacte : la rév. 1 disait « le KH n'appelle pas », ce que la boîte
>   aux lettres GitHub rendait littéralement faux — un invariant énoncé
>   plus large que sa portée réelle coûte la confiance dans tous les
>   autres.) L'indexation des objets de la suite se fait en lisant les
>   instantanés qu'elle PUBLIE (canal), jamais en l'appelant.
> - Il ne détient ni décision de programme, ni exigence de programme, ni
>   claim, ni résultat de vérification, ni preuve.
> - Il ne génère aucune prose destinée à un livrable d'homologation.
> - Il ne se substitue à aucun calcul d'une application spécialisée.
>
> ## Décision 3 — Garanties de service (constatées vs engagées)
>
> **Constatées — à préserver comme engagements :**
> 1. **Élicitation déterministe sans LLM** — aucune inférence de modèle
>    dans le chemin d'élicitation ; détection de conflits en Cypher
>    paramétré ; l'extraction LLM est confinée au pipeline d'ingestion.
>    **C'est la propriété la plus forte du KH** : une élicitation
>    déterministe se rejoue, donc s'audite, donc se cite. Toute évolution
>    qui introduirait un appel de modèle dans ce chemin est une rupture
>    de contrat.
> 2. **Fraîcheur fermée à la source** — le test de l'émetteur régénère
>    les fixtures et compare à l'octet près. À étendre à la spécification
>    d'interface elle-même (constat : INTERFACE.md documente 20 outils
>    sur 23 — le témoin s'est périmé sans le dire ; même vérification CI
>    que pour les fixtures).
> 3. **Isolation physique des plans** (bases Kùzu séparées).
>
> **Engagées — travail nommé côté KH, préalable aux contrats concernés :**
> 4. **Coordonnée de version citable et résolution scellée** — constat
>    (revue §C1) : pas de colonne version (supersession = un ordre, pas
>    une coordonnée) et `get_asset` relit le disque local (même id ⇒
>    contenus possiblement différents ; `source_path` fuit). Tant que ces
>    deux points tiennent, « un même identifiant résout toujours le même
>    contenu » n'est PAS tenu, et citer le KH dans un document gelé
>    revient à citer une adresse. Levée : version citable par élément +
>    résolution depuis l'instantané scellé, jamais le disque vivant.
> 5. **Paramétrage du plan Connaissance** — les requêtes y sont
>    construites par interpolation (injection possible, et casse
>    fonctionnelle certaine à la première apostrophe française :
>    « l'AMF »). Le plan Engagement, paramétré, montre la cible.
> 6. **Autorisation par appelant** — aujourd'hui : jeton unique partagé,
>    `authorise()` ne filtre rien, énumération des engagements sur
>    disque. Préalable absolu à toute donnée de programme ; le jeton de
>    démonstration public reste cantonné à la démo.
> 7. **Hygiène de production** — retirer les sentinelles de test des
>    chemins de production (`zzz-does-not-exist-9999` court-circuite dix
>    outils) ; rendre la génération de `schemas/types.ts` réelle (le
>    fichier est étiqueté « généré » mais la fonction retourne une chaîne
>    écrite à la main — l'étiquette interdit l'édition manuelle tout en
>    garantissant que la dérive passe inaperçue) ou retirer l'étiquette.
> 8. **Provenance sur tout élément retourné** ; identifiants stables
>    jamais recyclés.
>
> ## Décision 4 — Qualification de la connaissance (vocabulaires réels, convergence)
>
> - Maturité : `L0_named / L1_framed / L2_decomposed / L3_decided /
>   L4_specified` — `L3_decided` est le seuil COMPLETE d'une section.
> - Confiance : convergence des TROIS variantes internes constatées
>   (garde d'écriture : 5 valeurs ; Asset : 3 ; Statement : 4) vers
>   l'énumération complète `verified / designed / vendor-stated /
>   stated-by-client / assumed` — **`vendor-stated` ne doit jamais être
>   perdue** (cas le plus fréquent en phase d'offre, ligne la plus
>   stricte de la table de correspondance).
> - Conflits : `contradiction / principle_violation / stale_basis` —
>   les deux derniers sont précisément consommables par la suite
>   (principle_violation → Conformity Engine ; stale_basis → le
>   REQUIREMENT_VERSION_DRIFT de la connaissance).
> - Manques : `G1_empty_section / G2_unanswered_blocking /
>   G3_principle_unaddressed` — le manque est ce que Requirements Intake
>   attend en premier.
> - **Épistémique à deux étages** : confiance par élément ET
>   `is_provisional` par instantané (sujets < L3_decided, conflits
>   ouverts) — exposés tous les deux ; la suite traite un instantané
>   provisoire comme provisoire en bloc.
> - Rien de ce qui sort du KH n'entre dans la suite comme fait vérifié
>   (table de correspondance : CONTRATS_KH).
>
> ## Décision 5 — Gouvernance
> - Préfixe ADR-KH-nnn ; discipline de la suite (ADR, CI, rétrocompat
>   des surfaces testée, ≥ 2 mainteneurs) ; évolutions additives ou
>   versionnées ; PI/licence tranchées avant mise en dépendance d'une
>   chaîne d'homologation.
> - La CI du KH vérifie la fraîcheur de : fixtures (existant),
>   spécification d'interface (à ajouter), types publiés (à rendre réel).
>
> ## Hors périmètre
> - Intégration bidirectionnelle, webhooks, synchronisation (le flux vers
>   la suite est : la suite publie, le KH lit ; le KH publie, la suite
>   lit).
> - Donnée de programme classifiée avant la garantie 6.

---

## Partie II — Amendements du propriétaire du Knowledge Hub (2026-10-02, projet)

Les amendements s'appuient sur la lecture du code et des tests de ce dépôt à la date ci-dessus, et sur la lecture de `CLAUDE.md`, `docs/knowledge-hub/` et `contracts/` de Document Studio, d'`ADR-DE-02` et de la PR `document-engine#32`. Ce qui n'a **pas** été réexaminé est dit tel quel.

### A1 — Position
Le Hub est la **mémoire d'ingénierie transverse** de la suite (`ADR-SUITE-05` D1), pas un composant de la suite : il lui offre de la connaissance et en reçoit des contributions validées par un humain. Il est consommé par **canal à instantané scellé** (amendement KH-1 de `ADR-SUITE-05`, 2026-09-13), jamais par un port RPC synchrone depuis un composant de la suite.

### A2 — D1 (surfaces) actualisée
1. **Instantané scellé** : surface d'intégration des composants de la suite (Document Studio, Document Engine, Architecture Studio) ; inchangée dans son principe, complétée par les lots K1 à K3.
2. **Serveurs MCP** : agents uniquement. Inchangé.
3. **REST** (`/api/…`, contrat `1.0` à `1.13`, formes gelées par `tests/contract/frozen/`) : n'existait pas comme surface déclarée à la révision 2. Elle existe : **clients interactifs et outils** (Archinex : gouvernance de la base, juge d'option, similarité et réutilisation, ingestion de référentiels). Ce n'est **pas** le mécanisme d'intégration applicative d'un composant de la suite.
4. **Accès direct au graphe (`query_graph`)** : hors contrat, exploration humaine. Inchangé.
5. **« API HTTP de suggestion et d'élicitation »** : la révision 2 notait qu'elles n'existaient pas. Aujourd'hui : l'enrichissement passe par `/api/knowledge/candidates…` (soumission, contrôles, revue, promotion) ; l'assistance à la rédaction par `POST /api/prose/suggest-batch` (A3-a) ; les routes `/api/elicitation/*` et `/api/arbitration/*` existent mais sont **dépréciées depuis la 1.13** (A3-d).

### A3 — D2 (ce que le Hub ne fait pas) précisée
**a. Assistance à la rédaction.** Le Hub peut être **fournisseur d'assistance** du Document Engine (`ADR-DE-02`, second amendement d'`ADR-SUITE-05` du 2026-09-13 : l'assistance n'est pas un canal). Ce n'est pas de la « prose destinée à un livrable d'homologation » à trois conditions, qui sont des **engagements du Hub** : (1) la réponse est une **citation de la doctrine** de la base (identifiant, type, confiance telle que publiée, extrait), jamais un récit ; (2) elle **n'énonce rien sur le projet** (ni conformité, ni validation) ; (3) quand rien ne s'applique, **elle ne produit rien** et renvoie un avertissement. Le brouillon reste un `suggestion` que seul un geste humain bloc par bloc fait entrer dans le document (`ADR-DE-02`). *Constat à la date de l'amendement* : la route fabriquait du texte (« Conception validée… ») ; corrigée par la PR `LLMOps#39`.
**b. Mémoire d'usage (décision du mainteneur, 2026-10-02).** Le **journal de réutilisation** (quel actif a été retenu ou rejeté pour un sujet de ce type, pour quelle raison, sous quelles hypothèses jugées) est de la **connaissance sur la base**. Il ne conserve **aucune ancre de programme** : empreinte du sujet normalisé et libellé anonymisé seulement (adresses IP et e-mails refusés par le serveur), jamais le texte ni l'identifiant d'un engagement. La décision d'un engagement vit chez son producteur (`ADR-SUITE-05` D4).
**c. Schéma du dossier d'engagement (décision du mainteneur, 2026-10-02).** Le Hub **tient le contrat de provenance et d'épistémique** d'un dossier d'engagement scellé (`schemas/engagement_bundle.schema.json`, proposé). Tenir un schéma n'est pas détenir des données : le Hub **ne reçoit jamais** le contenu d'un engagement (aucun service de vérification ni de rendu), et ne détient « ni décision de programme, ni exigence de programme, ni claim, ni preuve ».
**d. Plan d'engagement.** Déprécié depuis la 1.13 (en-tête `Deprecation`, guide `docs/migration-archinex.md`) : conforme à D2 ; retrait en version majeure avec l'accord écrit des consommateurs.
**e. Générateur de document.** `generate_zero_draft_hld`, `POST /api/documents/zero-draft-blueprint` et les gabarits `templates/` produisent de la prose de livrable : **legacy**, à retirer au profit du Document Engine (lot K4), après accord des consommateurs.

### A4 — D3 (garanties) : état constaté au 2026-10-02
| # | Garantie | État | Suite |
|---|---|---|---|
| 1 | Élicitation déterministe, sans LLM | **Tenu et étendu** : aucun appel de modèle dans les chemins du Hub (vecteurs de similarité calculés par le **client**, juge d'option par règles, contenu issu d'un modèle du client marqué `llm-derived` et jamais décidant) | — |
| 2 | Fraîcheur fermée à la source | Fixtures : test existant. Instantané scellé et spécification d'interface : **non couverts** | K2 |
| 3 | Isolation physique des plans | Non réexaminée | à vérifier |
| 4 | Version citable, résolution scellée | **Non tenue** : pas de coordonnée de version par élément ; la lecture d'un actif relit la base vivante | K3 |
| 5 | Paramétrage du plan Connaissance | Non réexaminé à cette date | à vérifier avant adoption |
| 6 | Autorisation par appelant | **Partielle** : jetons à portées (`kb:review`, `kb:delegate`), identité de l'expert par e-mail contrôlée par le registre des propriétaires (403 sinon), jeton de démonstration sans portée de gouvernance. Le prérequis « aucune donnée de programme classifiée » est tenu **par construction** (A3-c) ; le cloisonnement des engagements n'a pas été réexaminé | à vérifier |
| 7 | Hygiène de production | Non réexaminée ; d'après la lecture de `scripts/generate_schemas.py` (non rejoué), `schemas/types.ts` contient encore du TypeScript écrit à la main sous l'étiquette « généré » | C1 |
| 8 | Provenance sur tout élément, identifiants stables | Partielle : provenance des actifs dans l'instantané, valideur et date des amendements ; identifiants jamais recyclés **non testé** | K3 |

### A5 — D4 (vocabulaires) : état
- **Confiance** : le schéma des actifs de la base n'accepte que `verified`, `vendor-stated` et `assumed` (**3 valeurs sur 5**) ; `designed` et `stated-by-client` ne sont pas exprimables. La convergence vers l'énumération complète est à faire (lot **K5**, issue `#42`). `vendor-stated` n'est jamais perdue.
- **Maturité, conflits, manques** : vocabulaires du plan d'engagement (déprécié) ; le dossier d'engagement les reprend tels que publiés par la suite.
- **`is_provisional`** par instantané : à publier (K2).

### A6 — D5 (gouvernance) : état
- Préfixe `ADR-KH-nnn` : adopté ici (A1).
- Évolutions additives ou versionnées : en place (`docs/VERSIONING.md`, `docs/DEPRECATION.md`, formes gelées).
- **« ≥ 2 mainteneurs » : non tenue** (un mainteneur). Risque assumé, à lever avant toute dépendance d'une chaîne d'homologation.
- **PI et licence** : MIT, © 2026 Maurice Israel ; à **confirmer** avant mise en dépendance d'une chaîne d'homologation (D5).
- CI : fraîcheur des fixtures (existant) ; de la spécification d'interface et des types publiés (à ajouter, C1).

### A7 — Décisions nouvelles
- **D6 — Sceaux.** Tout sceau calculé par le Hub suit le profil **canonical-json v1** de la suite (module `pipelines/canonical.py`, vecteurs partagés de la suite). *Constat* : l'idiome `json.dumps(sort_keys…)` diverge sur 7 des 40 vecteurs acceptés et accepte les 8 à refuser ; l'instantané scellé et l'instantané de conformité y sont encore. Lot **K1**.
- **D7 — Enveloppe de canal.** Les instantanés publiés portent `emitter`, `rebuiltByEmitterTest`, `checksum` canonique et `is_provisional` avec ses raisons (additif : les champs actuels sont conservés). Lot **K2**.
- **D8 — Référence citable.** `KnowledgeRef {sourceId: 'knowledge-hub', knowledgeKey, version}` ; la `version` est une coordonnée **publiée dans l'instantané** et résolue depuis lui, jamais depuis la base vivante ; une référence sans version n'est pas citable dans un document figé. Lot **K3**.
- **D9 — Aucune réutilisation automatique.** Toute proposition de réutilisation d'une connaissance est « à confirmer » par une personne, hypothèse par hypothèse ; les zones de score ne décident jamais. Cohérent avec « rien de ce qui sort du KH n'entre dans la suite comme fait vérifié ».
- **D10 — Pas de service sur du contenu d'engagement.** Le Hub ne vérifie, ne rend et ne stocke aucun dossier d'engagement (A3-c).

### A8 — Rejets (inchangés, confirmés)
Le Hub comme socle sémantique ; Cypher libre comme contrat ; **prose de livrable générée** (précisée par A3-a et A3-e) ; absorption d'objets possédés par la suite ; dépendance dure ; **RPC synchrone comme mécanisme d'intégration applicative de la suite**.

### A9 — Conséquences et suivi
- Lots **K1** (sceaux), **K2** (enveloppe), **K3** (version citable), **K4** (retrait planifié du générateur de document), **K5** (confiance à 5 valeurs, `#42`), **C1** (OpenAPI, types réels) : issues `LLMOps#33` à `#37`, suivi `#38`, adaptateur `#40`.
- PR `LLMOps#39` (assistance honnête).
- Chaque engagement de la Partie II est **testable** : K1 par les vecteurs partagés, K2 par le test de fraîcheur à l'octet, K3 par la résolution depuis l'instantané. Un engagement sans test reste une intention.
- À vérifier avant adoption : A4 lignes 3, 5, 6 (cloisonnement), 7.

---

## Décision d'adoption (à renseigner par le propriétaire du Knowledge Hub)

- [ ] Adopter tel quel
- [ ] Adopter avec les modifications suivantes : …
- [ ] Ne pas adopter : motif : …

Date : …  Décideur : …

Tant que cette décision n'est pas inscrite, ce texte est un **projet** : seuls l'amendement KH-1 d'`ADR-SUITE-05` (canal scellé, jamais RPC) et le profil canonical-json de la suite sont opposables.
