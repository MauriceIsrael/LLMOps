# Plan d'implémentation — Dossier d'engagement scellé (« bundle ») et génération de documents, schémas et briques

Statut : plan, **à valider** (décisions D9 à D13 proposées). Complète
[`PLAN-IMPLEMENTATION-Gouvernance-KB-Archinex.md`](PLAN-IMPLEMENTATION-Gouvernance-KB-Archinex.md) et
[`PLAN-IMPLEMENTATION-Similarite-Reutilisation.md`](PLAN-IMPLEMENTATION-Similarite-Reutilisation.md).
Lots LLMOps **B1 à B4**, lots Archinex **A16 à A19**, porte **G9**. Le lot **B1** (schéma, vérificateur, exemple) est livré avec ce plan.

---

## 0. Pourquoi

Le bout en bout (réglementation → RFP → délibération → décision → capitalisation) produit de la connaissance validée, mais sa **sortie** n'est pas
encore un objet que l'on peut donner à un générateur. La partie « rendu » de LLMOps (`get_render_payload`, `get_diagram_graph`,
`get_engagement_export`) est dépréciée depuis la 1.13 : l'engagement vit dans Archinex.

Il faut donc un artefact unique, **lisible par machine, scellé et tracé**, dont tout le reste est **dérivé** : document de conception, schémas, fiches de décision,
exports de conformité. Sans lui, chaque générateur réinterprète l'état de l'engagement et risque de présenter comme acquis ce qui ne l'est pas, c'est-à-dire
le défaut que la règle de tolérance zéro (D8) cherche à supprimer, déplacé de la réutilisation vers le document livré.

## 1. Principes

1. **Une source, des projections.** Le bundle est la seule source ; HLD, schémas, fiches ADR, exports sont des **fonctions pures et déterministes** du bundle (mêmes entrées, mêmes octets).
2. **Chaque affirmation porte son statut.** `epistemic_status` (validé, réutilisé confirmé, proposé par IA, hypothèse, contesté) dont découle, **de façon déterministe**, un `assertion_level` (`asserted`, `proposed`, `assumption`, `open`). Un générateur n'écrit comme un fait que ce qui est `asserted` ; tout le reste est rendu **avec son marquage**.
3. **Seul un humain valide.** Un élément `asserted` exige une personne (handle propriétaire) et une base `human_validation` ou `reuse_confirmation`. Une correspondance trouvée par un lexique, un texte légal ou un vecteur reste **proposée** tant qu'une personne ne l'a pas confirmée.
4. **La réutilisation est prouvée.** Une décision reprise de la base renvoie à une entrée du journal de réutilisation dont **chaque hypothèse** a été jugée ; `reused` exige que toutes tiennent, `reused_with_exception` un commentaire.
5. **Épinglé et reproductible.** Le bundle fixe la version de la base de connaissances (empreinte de l'instantané), les référentiels (version, empreinte du texte source) et le modèle d'embeddings ayant proposé des rapprochements.
6. **Échec bruyant.** Un export ou un rendu refuse un bundle qui ne passe pas la vérification ; il ne « répare » jamais en silence.
7. **Pas de donnée personnelle.** Des handles de propriétaires, jamais d'adresses e-mail ; un libellé client anonymisé ; un niveau de confidentialité obligatoire.

## 2. Le bundle (schéma `schemas/engagement_bundle.schema.json`, version `1.0`)

Enveloppe scellée comme l'instantané de la base : `schema_version`, `bundle_id`, `source_system` (producteur), `created_at`, `canonicalization: canonical-json-v1`,
`payload_sha256` (`sha256:<hex>` sur la sérialisation canonique de `data` : clés triées, séparateurs `,` `:`, UTF-8), `engagement`, `data`.

| Section de `data` | Contenu | Sert à |
|---|---|---|
| `pins` | version du contrat LLMOps, instantané de la base (id + empreinte), référentiels (version, couverture, empreinte du texte), modèle d'embeddings | reproductibilité, citation |
| `source_documents`, `requirements` | documents sources (empreinte seulement) et exigences (texte, clause) | traçabilité amont |
| `subjects` | sujets, maturité L0 à L4, statut, questions ouvertes (bloquantes ou non) | plan du document, écarts |
| `decisions` | décision, justification, alternatives, **hypothèses jugées**, conséquences, `derived_from` (actif de la base + entrée du journal), date de réexamen | fiches ADR, HLD |
| `statements` | énoncés (texte, prédicat, valeur, unité) | HLD |
| `compliance` | matrice exigence → contrôle (relation, `matched_by`, statut) | annexe de conformité |
| `gaps` | écarts (exigence non couverte, hypothèse manquante, conflit, proposition non revue), bloquants ou non | liste de réserves |
| `architecture` | éléments et relations (composants, flux, frontières), chacun tracé à des décisions | **schémas** |
| `kb_references`, `glossary` | actifs de la base cités (titre, statut), glossaire | citations sans appel serveur |
| `reuse_log` | confirmations de réutilisation de l'engagement | preuve des reprises |

Invariants vérifiés par `pipelines/bundle/verify.py` (en plus du schéma) : sceau exact ; identifiants uniques et tous résolus ; niveau d'affirmation dérivé du statut ;
élément affirmé = personne + base humaine ; décision réutilisée = entrée du journal cohérente (même actif, issue de réutilisation, hypothèses jugées et valides, commentaire si exception) ;
actifs de la base cités = listés ; sujet « décidé » = au moins une décision affirmée ; aucune adresse e-mail.

## 3. Décisions à prendre (proposées)

| # | Question | Proposition | Alternative |
|---|---|---|---|
| **D9** | Où vivent les rendus ? | **LLMOps**, comme bibliothèque et service sans état (`kb bundle render`, `POST /api/bundles/render`) : tout client tiers en profite, Archinex n'a rien à dupliquer | dans Archinex seul |
| **D10** | Un LLM écrit-il la prose ? | **Non en v1** : gabarits déterministes. Une aide rédactionnelle ultérieure ne reçoit que les éléments `asserted` et ne peut rien ajouter | prose générée dès la v1 |
| **D11** | Que peut contenir le bundle ? | Le texte des exigences du client est **légitime** (c'est le dossier de l'engagement) mais jamais son nom ; `confidentiality` obligatoire ; export refusé sans elle | anonymiser aussi les exigences |
| **D12** | OSCAL ? | Reporté : un export de la matrice de conformité au format OSCAL si un client l'exige | dès B3 |
| **D13** | DOCX / PDF ? | Reportés : le rendu produit du Markdown et du Mermaid ; la conversion passe par un outil externe (Pandoc, moteur de documents existant) | rendu natif |

## 4. Lots

| Lot | Dépôt | Objet | Prérequis |
|---|---|---|---|
| **B1** | LLMOps | Schéma, vérificateur, exemple scellé, tests (**livré avec ce plan**) | — |
| **B2** | LLMOps | `kb bundle verify`, `POST /api/bundles/verify` (sans état), contrat 1.14, types TypeScript, vecteur d'essai partagé (sceau) pour les implémentations TypeScript | B1 |
| **B3** | LLMOps | Rendus de référence : HLD (EN/FR), fiches ADR (une par décision, format MADR), diagrammes Mermaid depuis `architecture`, annexe de conformité ; `kb bundle render`, `POST /api/bundles/render` ; règles de marquage par niveau | B2, D9, D10 |
| **B4** | LLMOps | Facilités pour les clients : OpenAPI généré depuis le catalogue gelé, `GET /api/knowledge/assets/{id}`, schéma du bundle publié dans `docs/CLIENTS.md` | B2 |
| **A16** | Archinex | Export du bundle : construire depuis l'état de l'engagement, les décisions (hypothèses, journal de réutilisation lu dans LLMOps) et les pins ; sceller ; **vérifier via LLMOps avant d'offrir le téléchargement** ; bouton « Exporter le dossier » avec la liste des écarts bloquants | B2 |
| **A17** | Archinex | Vues de génération : aperçu HLD, fiches ADR, diagrammes (appel B3), marquage visible des éléments non affirmés, archive (`bundle.json`, fichiers générés, manifeste d'empreintes) | A16, B3 |
| **A18** | Archinex | E2E « acte 7 », API et navigateur, sur le vrai LLMOps | A17 |
| **A19** | Archinex | Ré-export et différence entre deux bundles, signature, retour vers la capitalisation (décisions du bundle → candidats de la base) | A18 |

### B1 — livré
`schemas/engagement_bundle.schema.json`, `schemas/examples/engagement_bundle.example.json` (scénario illustratif, scellé), `pipelines/bundle/verify.py`
(`canonical_json`, `payload_sha256`, `seal`, `verify_bundle`), `tests/unit/test_engagement_bundle.py` (un test par règle, par mutation).

### B2 — vérification publique
1. `kb bundle verify <fichier>` : code de sortie 0 si aucun problème, liste lisible sinon.
2. `POST /api/bundles/verify` : corps = le bundle, réponse = `{valid, problems:[{code,path,message}]}` ; aucune écriture, aucun état ; limite de taille.
3. Contrat 1.14 (additif), `schemas/types.ts`, `docs/contracts/knowledge-hub-api-v1.md` §5.14, `docs/CLIENTS.md`.
4. Vecteur d'essai (`schemas/examples/`) : un bundle et son sceau attendu, pour que les implémentations TypeScript prouvent qu'elles calculent le même sceau.
**Critères** : l'exemple est vérifié ; chaque mutation du test unitaire est refusée par l'API avec le même code ; tests gelés inchangés.

### B3 — rendus de référence
1. Fonctions pures `render_hld(bundle, lang)`, `render_adr_cards(bundle)`, `render_diagrams(bundle)`, `render_compliance_annex(bundle)` ; refus si le bundle ne passe pas `verify_bundle`.
2. **Règles de marquage** : `asserted` écrit tel quel avec sa référence (`DEC-001`, valideur, date) ; `proposed` précédé de « Proposition non validée » ; `assumption` listée comme hypothèse à confirmer ; `open` comme point ouvert ; jamais d'affirmation sans identifiant source.
3. Chaque fichier généré se termine par `bundle_id` et `payload_sha256`.
4. Diagrammes Mermaid : éléments non affirmés en pointillés avec leur niveau dans la légende.
**Critères** : mêmes octets pour le même bundle (test) ; aucun élément non affirmé n'apparaît sans marquage (test par mutation : on abaisse le niveau d'un élément, le texte change) ; chaque phrase du HLD porte un identifiant du bundle ; la sortie Mermaid se parse.

### B4 — clients tiers
OpenAPI depuis `scripts/freeze_interfaces.py` (chemins, méthodes, formes gelées) publié dans `schemas/openapi.json` et testé contre le serveur ; route `GET /api/knowledge/assets/{id}` ; mise à jour de `docs/CLIENTS.md`.

### A16 à A19 (Archinex, issues à créer après validation de ce plan)
- **A16** : le jeu des éléments est construit **sans rien inventer** : tout élément dont l'origine n'est pas une validation humaine ou une réutilisation confirmée est exporté `ai_proposed` ou `assumption`. Un export est refusé (message précis) si `verify` échoue ou si `confidentiality` manque.
- **A18 — acte 7** : à partir du scénario du bout en bout, exporter le bundle, le vérifier, générer HLD, fiches ADR, diagrammes ; asserter que (i) le bundle est valide, (ii) la décision réutilisée renvoie à son entrée du journal et à ses hypothèses, (iii) la proposition non revue apparaît marquée comme telle dans chaque rendu, (iv) deux générations donnent les mêmes octets, (v) l'export est refusé quand on retire une confirmation de réutilisation.

## 5. Porte G9

Sur le scénario de bout en bout, un dossier est exporté, **vérifié par LLMOps** puis rendu en document, schémas et fiches ; aucun élément non validé n'y figure sans marquage ; les rendus sont reproductibles à l'octet près ; un bundle altéré (sceau, niveau, réutilisation sans confirmation) est refusé ; aucune adresse e-mail n'y figure.

## 6. Risques et limites

- **Le schéma est le contrat** : toute évolution est additive en `1.x` ; un changement de sens exige une version majeure et l'accord des producteurs.
- **Qualité des diagrammes** : ils ne sont aussi bons que le modèle `architecture` que le producteur renseigne ; B3 ne l'invente pas.
- **Un bundle prouve la provenance, pas la vérité** : un validateur peut se tromper ; le bundle dit qui a validé et sur quelles hypothèses.
- **Deuxième humain** : la double revue n'est une garantie que si les validateurs sont des personnes distinctes.
