# Alignement de LLMOps (rôle « Knowledge Hub ») sur les principes de Document Studio et de la suite

Date : 2 octobre 2026. Sources lues (dépôt `AM-padawan-coder/Document-studio`, commit `9555eaf`) : `CLAUDE.md`, `README.md`,
`docs/knowledge-hub/` (`README`, `ADR-KH-01-CONTRATS-EXPOSES`, `CONTRATS_KH`), `docs/DECISIONS.md` (KH-1 à KH-7),
`contracts/canonical-json.md` et ses vecteurs, `contracts/snapshot-ref.md`.
**Non lus** : `CONTRATS_KH.md` complet (607 lignes) et la revue, qui vivent dans `four-level-design`. Lu depuis : `document-engine` (README, `ADR-DE-02`, `src/types.ts`, PR #32 et ses commentaires). Les conclusions ci-dessous ne valent que pour ce qui a été lu.

Statut des textes : `ADR-KH-01` et la révision 2 de `ADR-SUITE-05` sont **proposés**, pas opposables ; l'amendement du 2026-09-13 est, lui, opposable : *la suite se connecte au Hub par canal à instantané scellé, jamais par port RPC (ni HTTP, ni MCP)*, sans que le Hub devienne un composant de la suite.

## 1. Ce que la suite attend du Knowledge Hub

1. **Un seul propriétaire par capacité.** Document Studio « orchestre, ne calcule jamais » ; la composition d'un document appartient au Document Engine. Le Hub « ne génère aucune prose destinée à un livrable d'homologation » et « ne détient ni décision de programme, ni exigence de programme, ni claim, ni preuve » (ADR-KH-01 D2).
2. **Canal = instantané scellé.** Enveloppe commune (`emitter`, empreinte SHA-256 du contenu, `rebuiltByEmitterTest`), empreinte selon le profil partagé **canonical-json v1**, `KnowledgeRef {sourceId: 'knowledge-hub', knowledgeKey, version}` « une référence partielle n'existe pas », résolution **depuis l'instantané scellé, jamais le disque vivant**.
3. **Qualification épistémique à deux étages** : confiance par élément (`verified / designed / vendor-stated / stated-by-client / assumed`, `vendor-stated` jamais perdue) **et** `is_provisional` par instantané (sujets < `L3_decided` ou conflits ouverts) ; « rien de ce qui sort du Hub n'entre dans la suite comme fait vérifié ».
4. **Élicitation déterministe, sans LLM** ; l'extraction LLM est confinée à l'ingestion.
5. **Toute contribution vers un référentiel est validée par un humain** avant de devenir canonique.
6. **Autorisation par appelant**, préalable à toute donnée de programme.
7. **Un bloc généré ne devient jamais un texte statique** : chaque bloc d'un document renvoie à sa source et se régénère.

## 2. Verdict

| # | Principe | État dans LLMOps | Action |
|---|---|---|---|
| 4 | Pas de modèle dans le chemin du Hub | **Aligné.** Vecteurs calculés par le client (D6), juge d'option par règles, contenu issu d'un modèle marqué `llm-derived`, termes d'ingestion proposés par le client | — |
| 5 | Validation humaine | **Aligné.** File de candidats, double revue, propositions de réutilisation toujours « à confirmer », hypothèse par hypothèse | — |
| 3 | Vocabulaire de confiance | **Aligné** pour la confiance (`verified`, `assumed`, `vendor-stated` présents dans la base). Maturité et conflits : vocabulaire identique côté plan d'engagement | — |
| 6 | Autorisation par appelant | **Largement aligné** : jetons à portées (`kb:review`, `kb:delegate`), identité de l'expert par e-mail contrôlée par le registre | surveiller |
| 1 | Pas de donnée de programme | **Direction juste, reste à finir.** Le plan d'engagement est déprécié depuis la 1.13 ; mais le journal de réutilisation conserve des jugements par sujet (empreinte, libellé anonymisé) | **Q1** ci-dessous |
| 1 | Pas de prose de livrable | **Deux cas distincts.** (a) Le générateur « zero-draft HLD » et ses gabarits produisent de la prose de livrable : *legacy* en 1.13, à geler puis retirer au profit du Document Engine. (b) `POST /api/prose/suggest-batch` est l'**assistance** que le Document Engine appelle déjà (PR `document-engine#32`, ADR-DE-02) ; le second amendement d'`ADR-SUITE-05` (2026-09-13) tranche que l'assistance n'est pas un canal. Mais la route **fabriquait** du texte (« Conception validée… ») : corrigée (PR LLMOps #39), elle cite la doctrine ou ne produit rien | **K4** (a), PR #39 (b) |
| 2 | Empreinte au profil canonical-json v1 | **Écart prouvé par exécution.** Contre les 48 vecteurs partagés, l'idiome `json.dumps(sort_keys…)` diverge sur 7 des 40 cas acceptés (`1.0`, `1e-07`, `-0.0`, ordre des clés hors BMP) et accepte les 8 cas à refuser (`NaN`, entiers au-delà de 2^53−1). Concerne l'instantané scellé (`scripts/export_sealed_snapshot.py`, qui n'est même pas compact) et l'instantané de conformité (`pipelines/compliance_mapper.py`). Le nouveau module `pipelines/canonical.py` est conforme (48/48) | **K1** |
| 2 | Enveloppe de canal | **Écart.** Enveloppe en snake_case (`snapshot_id`, `payload_sha256`), sans `emitter`, sans `rebuiltByEmitterTest`, sans `is_provisional` ni raisons | **K2** |
| 2 | Référence citable, résolution depuis l'instantané | **Écart.** Pas de coordonnée `version` par élément (`last_reviewed`, `superseded_by` seulement) ; `get_asset` relit la base vivante | **K3** |
| 7 | Bloc → source | Sans objet côté Hub ; côté sortie d'engagement, chaque élément du bundle porte un identifiant stable et un statut | A16 |

Ce qui n'est **pas** contredit : le canal REST entre Archinex et LLMOps. Archinex n'apparaît nulle part dans ces documents (aucune occurrence) ; les textes lus règlent la connexion de la **suite** au Hub, pas celle d'un autre client. Pour un composant de la suite (Document Studio, Document Engine), l'entrée est l'instantané scellé, pas l'API REST.

## 3. Conséquences sur le plan du bundle

- **D9 (rendus dans LLMOps) : retiré.** Rendre un HLD ou des fiches de décision depuis LLMOps contredit D2 et fait doublon avec le Document Engine. Les lots B2 (service de vérification) et B3 (rendus) disparaissent.
- **D10 : la prose est celle du Document Engine / de Document Studio**, hors LLMOps.
- **D13 (DOCX/PDF) : sans objet** : le Document Engine produit déjà les formats ; il n'y a rien à convertir côté LLMOps.
- **Le bundle n'appartient pas au Hub** : c'est une donnée de programme. Il est produit par Archinex (qui détient l'engagement) et publié comme **instantané scellé à enveloppe de la suite** ; son schéma est un contrat *proposé*, à valider avec le propriétaire du Document Engine, dont le contrat d'entrée n'a pas été lu. LLMOps en garde une copie de référence (schéma, exemple, vérificateur) tant que ce propriétaire n'est pas désigné.

## 4. Questions ouvertes (à trancher par vous, ou à poser à l'équipe de la suite)

- **Q1 — tranchée (mainteneur, 2026-10-02) : le journal de réutilisation relève de la connaissance sur la base** (mémoire d'usage des actifs : « cet actif a été retenu / rejeté pour un sujet de ce type, pour telle raison »), pas d'une décision de programme. Garde-fou à tenir (`ADR-SUITE-05` D3/D4 : la décision de programme appartient à l'application qui possède le graphe) : le journal ne conserve **aucune ancre de programme** : empreinte du sujet normalisé et libellé anonymisé seulement (le serveur refuse adresses IP et e-mails), jamais le texte de l'engagement ni son identifiant ; la décision d'un engagement vit dans son bundle.
- **Q2 — répondue** (lecture de `document-engine`) : le moteur prend `compile(ProjectedGraph, Blueprint, GenerationContext)`, où `ProjectedGraph` est le graphe projeté par la chaîne d'Architecture Studio (`items` avec `kind`, `layer` ∈ context/application/component/infrastructure/iaas, `c4Type`, `attributes`, `scope`…), plus des **snapshots externes demandés** (conformité, exigences par snapshot ADR-DE-05). Un bundle d'Archinex **n'est donc pas consommable tel quel** : il faut un **adaptateur** (`bundle.architecture` → `ProjectedGraph`, `bundle.compliance` → instantané de conformité, `bundle.requirements` → instantané d'exigences) dont le propriétaire reste à désigner (lot A20).
- **Q3 — tranchée (mainteneur, 2026-10-02) : « LLMOps = Knowledge Hub »**, c'est-à-dire que le schéma de référence du bundle est tenu dans ce dépôt. **Tension à lever** : `ADR-SUITE-05` D3 range les « décisions de programme » chez l'application qui possède le graphe et dit que le Hub « ne détient jamais un claim ». Tenir un **schéma** n'est pas détenir des **données** ; mais l'amendement d'`ADR-KH-01` (Q4) doit le dire : LLMOps tient le contrat de provenance et d'épistémique, le contenu d'un engagement reste chez son producteur, et LLMOps ne reçoit jamais de bundle (aucun service de vérification, lot B2 supprimé).
- **Q4** — `ADR-KH-01` est « à amender et adopter par le propriétaire du KH » : c'est vous. L'adopter (ou l'amender) donnerait un cadre opposable aux lots K1 à K4.
