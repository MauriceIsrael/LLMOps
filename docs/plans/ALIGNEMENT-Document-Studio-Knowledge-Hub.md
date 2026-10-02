# Alignement de LLMOps (rôle « Knowledge Hub ») sur les principes de Document Studio et de la suite

Date : 2 octobre 2026. Sources lues (dépôt `AM-padawan-coder/Document-studio`, commit `9555eaf`) : `CLAUDE.md`, `README.md`,
`docs/knowledge-hub/` (`README`, `ADR-KH-01-CONTRATS-EXPOSES`, `CONTRATS_KH`), `docs/DECISIONS.md` (KH-1 à KH-7),
`contracts/canonical-json.md` et ses vecteurs, `contracts/snapshot-ref.md`.
**Non lus** : `CONTRATS_KH.md` complet (607 lignes) et la revue, qui vivent dans `four-level-design` ; le dépôt `document-engine` (contrat d'entrée d'un document). Les conclusions ci-dessous ne valent que pour ce qui a été lu.

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
| 1 | Pas de prose de livrable | **Écart.** Le générateur « zero-draft HLD » et ses gabarits produisent de la prose de livrable ; marqués *legacy* en 1.13, ils doivent être gelés puis retirés au profit du Document Engine | **K4** |
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

- **Q1** — Le journal de réutilisation (sujet anonymisé → actif de la base, avec jugements) est-il de la *connaissance sur la base* (mémoire d'usage) ou une *décision de programme* (donc hors du Hub selon D2) ? Si c'est la seconde, il doit migrer vers Archinex, LLMOps ne gardant que des compteurs agrégés.
- **Q2** — Le contrat d'entrée du Document Engine : graphe + Blueprint (EDM) ou instantané scellé ? Le bundle doit s'y brancher ; il faut lire `document-engine` (non lu ici) avant de figer le schéma.
- **Q3** — Qui est le propriétaire du schéma du bundle, et dans quel dépôt il vit (producteur, ou contrat partagé de la suite copié octet pour octet).
- **Q4** — `ADR-KH-01` est « à amender et adopter par le propriétaire du KH » : c'est vous. L'adopter (ou l'amender) donnerait un cadre opposable aux lots K1 à K4.
