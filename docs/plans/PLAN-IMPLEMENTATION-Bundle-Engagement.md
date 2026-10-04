# Plan d'implémentation — Dossier d'engagement scellé (« bundle ») et alignement sur la suite Document Studio

Statut : plan **révisé le 2 octobre 2026** après lecture des principes de Document Studio
([`ALIGNEMENT-Document-Studio-Knowledge-Hub.md`](ALIGNEMENT-Document-Studio-Knowledge-Hub.md)). Complète
[`PLAN-IMPLEMENTATION-Gouvernance-KB-Archinex.md`](PLAN-IMPLEMENTATION-Gouvernance-KB-Archinex.md) et
[`PLAN-IMPLEMENTATION-Similarite-Reutilisation.md`](PLAN-IMPLEMENTATION-Similarite-Reutilisation.md).
Lots LLMOps **K1 à K4** et **C1**, lots Archinex **A16 à A19**, porte **G9**. Le lot **B1** (schéma de référence, vérificateur, module `canonical`) est livré avec ce plan.

> **Ce qui a changé par rapport à la première version** : le rôle de LLMOps est celui du **Knowledge Hub** de la suite. Il ne génère aucune prose de livrable
> et ne détient aucune donnée de programme. Les anciens lots B2 (service de vérification) et B3 (rendus HLD, fiches, diagrammes dans LLMOps) sont **supprimés** : la composition d'un
> document appartient au Document Engine, la rédaction au Document Studio. Le bundle est un produit d'**Archinex**, publié comme instantané scellé. *(Remplacé le 3 octobre : émis par le Hub, voir la révision ci-dessus.)*

> **Révision du 3 octobre 2026 (ADR-KH-01 A10, projet)** — le Hub contient **deux bases** : connaissance (agnostique de programme) et **engagement** (exigences, décisions, énoncés, conflits, manques). Le « bundle » ci-dessous
> devient **l'instantané scellé de la base d'engagement, émis par le Hub** (lot **K11**), non plus un produit d'Archinex. Archinex est l'outil d'aide à la décision et de sollicitation des experts : un client qui écrit
> dans le Hub. La suite n'a pas à le connaître. Conséquences : la phrase « ne détient aucune donnée de programme » ci-dessus est **remplacée** (la base de connaissance n'en détient aucune ; la base d'engagement
> en détient sous les préalables d'A10-d) ; les lots Archinex **A16 à A19** sont à reformuler par l'équipe Archinex (l'export n'est plus construit chez eux) ; **A22 est caduque** ; D14 est tranchée (le Hub porte le contrat).
> Nouveaux lots LLMOps : **K9** (#46, préalable bloquant), **K10** (#48), **K11** (#49), **K12** (#50), **K13** (#51). Voir [`../SUITE-MAP.md`](../SUITE-MAP.md).
> Les exigences de l'appel d'offres restent **côté Hub** en attendant la clarification avec la suite (A10-h).
> **État au 4 octobre (contrat 1.24 ; K16 décisions, K12 import, K18 faits d'architecture, K19 règles de déclenchement, K20 moteur de cascade et K21 ajustements par engagement livrés)** : livrés dans `main` ou en PR : K1 à K3 et K5 (1.15), K9, K10 (1.14), **K14** (rôles et engagements gérés, 1.16, issue #58), **K15** (API d'écriture, 1.17, #59), **K11** (instantané d'engagement, 1.18). Restent : K12 (#50), K13 (#51), K4, K6 à K8, C1. Deux écarts à ce plan : le canal d'engagement n'émet **pas** le « bundle » tel que décrit plus bas (le plan d'engagement du Hub ne détient ni décisions avec alternatives, ni architecture, ni conformité, ni journal de réutilisation) mais un instantané plus restreint, schéma `engagement_snapshot` ; les rôles et l'identité des personnes (K14) sont venus s'intercaler avant K11. Le « bundle » ci-dessous reste le modèle cible de ces compléments.

---

## 0. Pourquoi

Le bout en bout (réglementation → RFP → délibération → décision → capitalisation) produit de la connaissance validée, mais sa **sortie** n'est pas encore un objet qu'un générateur
(Document Engine, Document Studio) peut consommer sans risque. Sans lui, chaque générateur réinterprète l'état de l'engagement et peut présenter comme acquis ce qui ne l'est pas : le défaut
que la règle de tolérance zéro (D8) supprime côté réutilisation, déplacé vers le document livré.

## 1. Principes

1. **Une source, des projections.** Le bundle est la seule source ; documents, schémas, fiches en sont dérivés **par les composants dont c'est le métier** (Document Engine / Studio), jamais par le Hub.
2. **Chaque affirmation porte son statut.** `epistemic_status` (validé, réutilisé confirmé, proposé par IA, hypothèse, contesté) dont découle, **de façon déterministe**, un `assertion_level` (`asserted`, `proposed`, `assumption`, `open`). Un générateur n'écrit comme un fait que ce qui est `asserted`.
3. **Seul un humain valide.** `asserted` exige une personne (handle) et une base `human_validation` ou `reuse_confirmation`. Une correspondance lexicale, par texte légal ou vectorielle reste **proposée** tant qu'une personne ne l'a pas confirmée.
4. **La réutilisation est prouvée** : renvoi à une entrée du journal dont **chaque hypothèse** est jugée.
5. **Deux étages épistémiques** (suite) : `is_provisional` pour le bundle entier (un sujet sous `L3_decided` ou un conflit ouvert) **en plus** du statut de chaque élément ; vocabulaires de la suite (maturité `L0_named`…`L4_specified`, confiance `verified / designed / vendor-stated / stated-by-client / assumed`, conflits `contradiction / principle_violation / stale_basis`).
6. **Scellé selon la suite** : enveloppe `ExternalSnapshotEnvelope` (`snapshotId`, `sourceSystem`, `schemaVersion`, `createdAt`, `sourceRevision`, `checksum`), empreinte `sha256:<hex>` de `data` au profil **canonical-json v1** de la suite.
7. **Épinglé** : version de la base de connaissances et `KnowledgeRef` `{source_id: 'knowledge-hub', knowledge_key, version}` ; une référence sans version n'est **pas citable** dans un document figé.
8. **Échec bruyant** : un export est refusé s'il ne passe pas la vérification.
9. **Pas de donnée personnelle** : handles de propriétaires, libellé client anonymisé, `confidentiality` obligatoire.

## 2. Le bundle (schéma `schemas/engagement_bundle.schema.json`, version `1.0`, contrat **proposé**)

| Section de `data` | Contenu |
|---|---|
| `engagement`, `pins` | identité (libellé anonymisé, confidentialité), version du contrat LLMOps, instantané de la base (id + empreinte), référentiels, modèle d'embeddings |
| `source_documents`, `requirements` | documents sources (empreinte seulement), exigences |
| `subjects` | sujets, maturité (`L0_named`…`L4_specified`), statut, questions ouvertes |
| `decisions` | décision, justification, alternatives, **hypothèses jugées**, conséquences, `derived_from` (actif de la base + entrée du journal) |
| `statements`, `conflicts` | énoncés ; conflits (`contradiction`, `principle_violation`, `stale_basis`) |
| `compliance`, `gaps` | matrice exigence → contrôle ; écarts (`G1_empty_section`, `G2_unanswered_blocking`, `G3_principle_unaddressed`, …) |
| `architecture` | éléments et relations (composants, flux, frontières) tracés à des décisions |
| `is_provisional`, `provisional_reasons` | dérivés (vérifiés) : sujets sous `L3_decided`, conflits ouverts |
| `kb_references`, `glossary`, `reuse_log` | actifs de la base cités (`knowledge_ref`, confiance), glossaire, confirmations de réutilisation |

Invariants vérifiés par `pipelines/bundle/verify.py` en plus du schéma : sceau exact au profil de la suite ; identifiants uniques et résolus ; niveau dérivé du statut ; élément affirmé = personne +
base humaine ; décision réutilisée = entrée du journal cohérente (même actif, issue de réutilisation, hypothèses jugées et valides, commentaire si exception) ; actifs cités listés ; sujet « décidé » =
décision affirmée ; `is_provisional` et ses raisons **dérivés, jamais déclarés** ; aucune adresse e-mail.

## 3. Décisions

| # | Question | Décision |
|---|---|---|
| **D9** | Où vivent les rendus ? | **Révisée : ni dans LLMOps ni dans Archinex.** Document Engine / Document Studio (alignement). LLMOps = Knowledge Hub : aucune prose de livrable |
| **D10** | Qui écrit la prose ? | **Document Studio / Document Engine** (module de rédaction), à partir du bundle : seuls les éléments `asserted` sont écrits comme des faits |
| **D11** | Que contient le bundle ? | Le texte des exigences du client est légitime, jamais son nom ; `confidentiality` obligatoire. **Validé.** |
| **D12** | OSCAL | **Validé en principe** : export de la matrice de conformité au format OSCAL, produit par Archinex ; lot A19 |
| **D13** | DOCX / PDF | **Sans objet** : le Document Engine produit déjà les formats ; il n'y a rien à convertir ici |
| **D14** | Qui possède le schéma du bundle ? | **Tranchée le 3 octobre** : le Hub, émetteur du canal « engagement » (A10-b). Reste à faire valider par la suite (registre de canaux) |
| **D16** | Où vivent les exigences de l'appel d'offres ? | **Dans la base d'engagement du Hub** pour l'instant (A10-h) ; à clarifier avec Requirements Intake / Tuleap |
| **D17** | Ingestion de l'appel d'offres | Faite côté Archinex (extraction par modèle, marquée `llm-derived`, **proposée** seulement) ; le Hub reste déterministe |

## 4. Lots

| Lot | Dépôt | Objet | Prérequis |
|---|---|---|---|
| **B1** | LLMOps | Schéma de référence, vérificateur, exemple scellé, **module `pipelines/canonical.py` conforme au profil de la suite**, vecteurs partagés (**livré**) | — |
| **K1** | LLMOps | Tous les sceaux au profil canonical-json v1 (instantané scellé, instantané de conformité) ; régénération des fixtures ; contrat 1.15 | B1 |
| **K2** | LLMOps | Enveloppe de canal : `emitter`, `rebuiltByEmitterTest`, `is_provisional` + raisons, `checksum` canonique (additif : champs actuels conservés) ; test de fraîcheur à l'octet | K1 |
| **K3** | LLMOps | `version` citable par élément, résolution **depuis l'instantané scellé**, `GET /api/knowledge/assets/{id}`, `KnowledgeRef` documenté | K2 |
| **K4** | LLMOps | Hub sans prose de livrable : gel puis retrait planifié du générateur « zero-draft HLD » et des gabarits (guide de migration vers le Document Engine). **Hors périmètre : `POST /api/prose/suggest-batch`**, assistance consommée par le Document Engine, corrigée par la PR #39 (citations de la doctrine ou aucun brouillon) | — |
| **C1** | LLMOps | OpenAPI généré depuis le catalogue gelé, `docs/CLIENTS.md` à jour (instantané d'abord pour les composants de la suite) | K3 |
| **K9** | LLMOps | Autorisation par appelant : 403 et non 500, énumération filtrée, identifiants validés — **livré** (#46) ; la fermeture par défaut est réalisée par K14 | — |
| **K14** | LLMOps | Engagements gérés : rôles, membres, journal d'accès, fermés dans tous les environnements — **livré** (#58) | K9 |
| **K15** | LLMOps | API d'écriture de l'engagement pour Archinex — **livré** (#59) | K14 |
| **K10** | LLMOps | Lever la dépréciation du plan d'engagement (contrat 1.14) — #48 | — |
| **K11** | LLMOps | Émission de l'instantané d'engagement par le Hub — **livré** (#49), schéma `engagement_snapshot` plus restreint que ce bundle | K1, K2, K3, K5, K14, K15 |
| **K12** | LLMOps | Mode import et simulation pour la reprise des projets d'Archinex — **livré** (#50) ; l'import lui-même est fait par Archinex (archinex#34) | K15 |
| **K18** | LLMOps | Vocabulaire des faits d'architecture et faits portés par les décisions affirmées (contrat 1.21) — **livré** (#67) ; premier lot de la cascade de questions (K18 → K19 → K20 → K21 → K22, #67 à #71) | K16 |
| **K19** | LLMOps | Règles de déclenchement de questions attachées aux actifs (contrat 1.22) — **livré** (#68) | K18 |
| **K20** | LLMOps | Moteur de cascade déterministe (contrat 1.23) — **livré** (#69) | K18, K19, K16 |
| **K21** | LLMOps | Ajustements des règles par engagement (contrat 1.24) — **livré** sauf la capitalisation (étape 4, dépend de K7 #44 et K13 #51) (#70) | K19, K20 |
| **K13** | LLMOps | Étanchéité de la capitalisation : aucune ancre de programme dans la base de connaissance — #51 | — |
| **A16** *(à reformuler, équipe Archinex)* | Archinex | Export du bundle comme instantané scellé de la suite (TypeScript, vecteurs partagés), construit **sans rien inventer** ; refus si la vérification échoue ou si `confidentiality` manque | B1, K1 |
| **A17** | Archinex | Publication : fichier et référence `SnapshotRef` (`sourceSystem`, `snapshotId`, `checksum`, `producedAt`) pour les consommateurs ; bouton « Exporter le dossier », bandeau « provisoire » et liste des écarts bloquants | A16 |
| **A18** | Archinex | E2E « acte 7 » (API et navigateur) sur le vrai LLMOps | A17, K3 |
| **A19** | Archinex | Export OSCAL de la matrice de conformité (D12), ré-export et différence entre deux bundles, retour vers la capitalisation | A18 |
| **A20** (LLMOps#40) | à désigner | **Adaptateur vers le Document Engine** : `bundle.architecture` → `ProjectedGraph`, `bundle.compliance` → instantané de conformité, `bundle.requirements` → instantané d'exigences (ADR-DE-05) ; correspondance des types d'éléments (`actor/system/component/datastore/network…`) vers `layer` et `c4Type` ; propriétaire à décider avec les équipes du moteur (Q2, D15) | A18 |

Aucun lot ne rend de document. Le **consommateur** (Document Engine) prend `compile(ProjectedGraph, Blueprint, GenerationContext)` et des snapshots externes demandés : le bundle ne s'y branche donc pas tel quel, d'où le lot **A20** (adaptateur, propriétaire à désigner, question **Q2** répondue dans le rapport d'alignement).

### B1 — livré
`schemas/engagement_bundle.schema.json`, `schemas/examples/engagement_bundle.example.json` (scénario illustratif, scellé), `pipelines/bundle/verify.py`, `pipelines/canonical.py`
(profil canonical-json v1 de la suite, **48 vecteurs partagés** acceptés/refusés comme prévu), `tests/fixtures/canonical-json.vectors.json`, `tests/unit/test_engagement_bundle.py` (un test par règle, par mutation),
`tests/unit/test_canonical_json_profile.py`.

### K1 — sceaux conformes
1. Remplacer `json.dumps(…)` par `pipelines.canonical` dans `scripts/export_sealed_snapshot.py` et `pipelines/compliance_mapper.py` ; refuser (erreur de construction de l'instantané) ce que le profil refuse.
2. Régénérer `fixtures/`, `data/snapshots/latest.json` et le vecteur de conformité ; pour les données actuelles (chaînes, entiers) les empreintes ne changent que si l'instantané scellé passait de `indent=2` au compact : **annoncer le changement de checksum** dans `VERSIONING.md`.
3. **Critères** : les 48 vecteurs passent sur le code de production ; un test échoue si un nouveau sceau est calculé hors du module ; tests gelés inchangés.

### K2 — enveloppe de canal
Champs additifs sur l'instantané scellé et sur `GET /snapshot/*` : `emitter`, `rebuiltByEmitterTest: true` (le test de CI régénère et compare), `is_provisional` + `provisional_reasons` (sujets sous `L3_decided`, conflits ouverts dans la base), `checksum` au profil. **Critères** : un consommateur de la suite valide l'enveloppe sans connaître LLMOps ; la CI échoue si l'instantané publié n'est pas celui que le code régénère.

### K3 — référence citable
`version` par élément (incrémentée à chaque amendement accepté, stockée dans l'en-tête), `content_sha256`, présentes dans l'instantané ; `get_asset` et la nouvelle route REST résolvent **depuis l'instantané désigné**, jamais la base vivante ; `source_path` n'est plus exposé. **Critères** : le même `{knowledge_key, version}` résout toujours les mêmes octets ; un amendement change la version.

### K4 — Hub sans prose
Constat : le générateur « zero-draft HLD » (`generate_zero_draft_hld`, `/api/documents/zero-draft-blueprint`, gabarits `templates/`) produit de la prose de livrable. Gel (déjà *legacy*), guide de migration, calendrier de retrait en version majeure avec l'accord des consommateurs (`DEPRECATION.md`).

## 5. Porte G9

Sur le scénario de bout en bout, **le Hub** (ex-Archinex, voir la révision) exporte un bundle **scellé au profil de la suite** ; il passe la vérification (TypeScript et référence Python, mêmes cas de conformité) ; ses références à la base sont citables (version) et
résolvent depuis l'instantané épinglé ; `is_provisional` est juste ; un bundle altéré (sceau, niveau, réutilisation sans confirmation) est refusé ; aucune adresse e-mail ; deux exports du même état ont le même `checksum`.
Le rendu d'un document relève du Document Engine / Studio et se démontre avec leurs propriétaires, via l'adaptateur A20.

## 6. Risques et limites

- **Contrat non validé par son consommateur** : le schéma est une proposition ; le Document Engine consomme un `ProjectedGraph` et des snapshots, pas ce dossier : sa valeur directe est la provenance et le contrôle (statuts, `is_provisional`), l'entrée du moteur passe par l'adaptateur A20.
- **Textes de la suite non opposables** : `ADR-KH-01` est « proposé » ; K1 à K4 s'y réfèrent, mais seuls l'amendement KH-1 et le profil canonical-json sont opposables. L'adopter est une décision du propriétaire du Hub (Q4).
- **Un bundle prouve la provenance, pas la vérité** ; la double revue n'est une garantie que si les validateurs sont des personnes distinctes.
- **Q1** (le journal de réutilisation est-il une donnée de programme ?) : tranchée, c'est de la connaissance sur la base (ADR-KH-01 A3-b), anonymisée ; K13 en fait un test.
- **Le Hub détient désormais des données de programme** : il hérite de leurs obligations (confidentialité, classification) ; K9 est bloquant (A10-i).
- **Deux sources de vérité pendant la transition** (Prisma d'Archinex et base d'engagement du Hub) : la durée est à borner dans K12.
