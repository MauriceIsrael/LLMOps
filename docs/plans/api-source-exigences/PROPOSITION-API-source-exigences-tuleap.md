# Proposition — API « source d'exigences » du socle Tuleap

> **Statut : proposition de conception, à discuter avec l'équipe Tuleap. Aucun code.** Elle remplace la piste « persister la ref Tuleap après coup » (appariement par texte), jugée insatisfaisante.
> Spécification machine : [`requirements-source.openapi.yaml`](requirements-source.openapi.yaml) (OpenAPI 3.1).
> Relevé du 2026-10-24 sur `tuleap` `e5766fd`, `requirements-intake` `cadafc8`, Archinex (branche de travail), LLMOps contrat 1.40. **Rien n'a été exécuté contre une instance Tuleap** ; ce qui dépend du comportement réel de Tuleap est marqué **« à recetter »**.

## 1. Ce qu'il faut reproduire

Aujourd'hui Archinex enregistre l'audit d'un appel d'offres par `POST /api/projects/{id}/requirements` : une **source** (`kind: rfp`, `sha256` du texte intégral, titre, langue, version) et des **clauses** (`clauseRef`, `title`, `text`, `criticality`, `category`, `position`, proposition de disposition par un modèle). L'opération est idempotente (même empreinte, mêmes lignes) et **la décision humaine n'est jamais écrasée** par un réimport.

Cible : **une seconde source d'import, « Tuleap »**. Les exigences viennent du registre (déjà extraites et curées par Requirements Intake), **avec leur référence** `RequirementRef {sourceId, requirementKey, version}`. La référence voyage ensuite d'Archinex au Hub (champ additif, voir §9) : **il n'y a plus d'appariement à faire**, donc plus de jointure par texte. Le problème d'identité (MauriceIsrael/LLMOps#150) disparaît pour les nouveaux projets. Il ne reste que la reprise des projets déjà ingérés par document (§8).

## 2. Principes (ceux de la suite, pas inventés ici)

1. **Lecture seule, derrière le port.** L'API est une **façade HTTP du `RequirementRegistryPort`** (et du lecteur de baselines), pas un accès à Tuleap : aucune clé d'accès Tuleap ne sort, aucun appelant ne parle à Tuleap (ADR-SUITE-02). Aucune écriture : la création reste le port de Requirements Intake seul.
2. **Ce qui doit être rejouable est scellé.** Enveloppe de la suite (`ExternalSnapshotEnvelope`), `canonical-json` v1, `sourceSystem: "tuleap"`, identifiant dérivé du contenu. Une donnée non scellée est un *aperçu*, dit comme tel.
3. **Identité par `RequirementRef`.** `sourceId` est **déclaré** par l'opérateur du registre (`tuleap:<registre>`), jamais construit par l'appelant ; `version` est le rang de changeset, **émis par Tuleap seul** : le contrat partagé n'est pas modifié (c'est la voie B).
4. **Pas d'état calculé.** Statut éditorial seulement (`proposed`, `approved`, `amended`, `obsolete`). `allocated`, `verified`, etc. appartiennent au moteur de conformité (ADR-TULEAP-03).
5. **La classification se plafonne côté serveur** (`assert_storable`) et l'API **dit ce qu'elle retient** : un manifeste qui annonce `withheld.count` ; jamais un silence qui se lirait « il n'y en a pas ».
6. **L'artifact id n'est pas exposé** : « détail de transport, la clé fait foi » (contrat `Requirement.artifact_id`). Le seul identifiant public est la clé.

## 3. « Faut-il streamer le document ? » — réponse

**Non au document comme un bloc, oui au flux d'enregistrements.**

- Ce qui s'échange est une **liste d'exigences** (et, plus tard, de fragments), pas un fichier Word. L'unité de transport est l'enregistrement, en **NDJSON** (une ligne = un objet), avec une première ligne `manifest` et une dernière ligne `end`.
- Pourquoi un flux : la taille d'un CCTP n'est **pas mesurée** ici, le plafond de pagination de Tuleap est un point ouvert de la recette T3 (« plafond réel de `limit` ? »), et l'adaptateur lit page par page. Le service lit Tuleap page par page et **n'accumule pas** en mémoire côté appelant.
- Pourquoi **scellé d'abord** : un flux sur des données vivantes n'est pas une vue cohérente (une exigence peut changer entre deux pages). L'extrait est donc **calculé en deux temps** : le service lit tout, calcule l'empreinte, écrit le résultat dans un fichier temporaire, puis **sert ce fichier** avec le manifeste (empreinte comprise) en tête. Le client reconstitue `data`, recalcule l'empreinte au profil `canonical-json` v1 et **refuse** si elle diffère ou si la ligne `end` manque (flux tronqué).
- Reprise : un extrait a un identifiant et une durée de vie (paramètre `after=<clé>`), pas de recalcul.
- **Le texte du document** (fragments) n'est pas dans Tuleap : il vit dans Requirements Intake (`SourceFragment`). Voir §7 : ce n'est pas nécessaire pour la première livraison.

## 4. Ressources

| Méthode et chemin | Rôle | Scellé |
|---|---|---|
| `GET /v1/registries` | registres déclarés (`sourceId`), plafond de classification **de l'appelant**, version du contrat | non |
| `GET /v1/documents` | documents sources, **dérivés** de `source_ref.document` et `revision` ; compteurs | non |
| `GET /v1/requirements` | exploration paginée **en direct** (filtres : document, révision, section, statut éditorial, domaine, texte) ; en-tête `X-Registry-Watermark` | non (aperçu) |
| `GET /v1/requirements/{key}` (`?atVersion=`) · `GET /v1/requirements/{key}/versions` | une exigence, ses versions | non |
| `POST /v1/refs:check` | **lot** de références `{key, version}` → version courante et dérive | non |
| `POST /v1/extracts` | calcule un **extrait scellé** pour une portée (`document`, `revision`, `keys`…) ; `201` nouveau, `200` contenu identique déjà calculé | oui |
| `GET /v1/extracts/{id}` · `GET /v1/extracts/{id}/records` | manifeste ; flux NDJSON ou pages | oui |
| `GET /v1/baselines` · `GET /v1/baselines/{identifier}/records` | baselines **figées par la release** (lecture seule) | oui |

**Extrait ou baseline ?** Figer une baseline est « un acte de release, pas une opération de lecture » (`BaselineFreezerPort`, orchestrateur de release seulement) : Archinex **ne gèle pas**. L'extrait est un calcul à la demande, non conservé comme baseline ; la baseline est lue telle quelle. L'édition Community de Tuleap n'a pas le plugin Baseline (ADR-TULEAP-04) : les baselines sont des fichiers figés adressés par empreinte, et c'est ce que `GET /v1/baselines` sert.

Ce que **n'est pas** cette liste : un flux de changements (`GET /changes?after=`). Il demande de lister les artifacts modifiés depuis un instant, dont la faisabilité sur Tuleap est **à recetter** ; `POST /v1/refs:check` couvre le besoin réel (« mes références sont-elles à jour ? ») sans cela.

## 5. L'enregistrement d'exigence

```json
{
  "type": "requirement",
  "ref": { "sourceId": "tuleap:rrf", "requirementKey": "RRF-CORE-SEC-0042", "version": 3 },
  "title": "Journalisation des accès",
  "statement": "<p>Le titulaire doit journaliser …</p>",
  "statementText": "Le titulaire doit journaliser …",
  "domain": "SECURITY",
  "verificationModes": ["AUDIT"],
  "appliesTo": { "programRef": "RRF", "lotRefs": ["LOT-2"], "pbsRefs": [] },
  "service": null,
  "quality": null,
  "sourceRef": { "document": "CCTP-RRF-2026-03", "section": "§4.2.1", "revision": "B", "page": 17 },
  "editorialStatus": "approved",
  "classification": "DIFFUSION_RESTREINTE",
  "curatedDecision": null,
  "targetThreshold": null,
  "version": { "number": 3, "changesetId": 981, "submittedOn": "2026-10-01T09:12:00Z", "submittedBy": "…", "comment": "…" }
}
```

- `statement` est l'**énoncé tel que Tuleap le détient** (HTML restreint). `statementText` est une **projection déterministe** en texte brut (règle écrite, testée) pour les consommateurs qui n'affichent pas de HTML. Le contrat note que les transformations HTML du texte riche sont un risque de fidélité (recette T3) : à recetter sur des énoncés réels.
- `version.submittedBy` est un nom d'auteur Tuleap : **à décider** avec l'équipe s'il doit sortir (le Hub n'accepte que des handles, jamais une adresse).
- Ordre des enregistrements dans un extrait : par `sourceRef.section` en ordre naturel puis par clé (déterministe).

## 6. Le flux scellé, précisément

```
{"type":"manifest","schemaVersion":"1.0","extractId":"tuleap-rrf-3f2a9c1b04de","sourceSystem":"tuleap","sourceId":"tuleap:rrf",
 "createdAt":"…","checksum":"sha256:…","counts":{"requirements":412},"withheld":{"count":3,"aboveClassification":"DIFFUSION_RESTREINTE"},
 "scope":{"document":"CCTP-RRF-2026-03","revision":"B"}}
{"type":"requirement", …}
… (une ligne par exigence, ordre déterministe)
{"type":"end","count":412}
```

- `checksum` = sha256 au profil `canonical-json` v1 de **`data` seul** : `{"scope":…, "requirements":[…]}` (tableau trié comme ci-dessus). `createdAt` et la provenance restent **hors sceau** (même contenu à deux instants, même empreinte) ; `extractId` = `tuleap-<registre>-<12 premiers hex>`.
- Le client **ne fait pas confiance au manifeste** : il recalcule. Un `end` absent, un compte différent, une empreinte différente : **refus entier**, rien n'est importé.
- Même enveloppe que la baseline figée (`FrozenBaselineData`, `BASELINE_SCHEMA_VERSION` 1.0) pour `GET /v1/baselines/{identifier}/records` : un seul vocabulaire, deux sources.

## 7. Le texte du document — pas pour la première livraison

Archinex n'a besoin du texte du document que pour **son audit par un modèle** (détecter les clauses que l'extraction a manquées, montrer le contexte). Avec une source Tuleap, les exigences existent déjà ; l'audit d'omissions est le travail de Requirements Intake (curation des candidates).

Si on le veut quand même (phase 2), il faut voir que **les fragments ne sont pas dans Tuleap** : Requirements Intake détient `SourceFragment {id, documentId, documentVersion, sectionPath, originalText, hash}` et le reçu d'injection (`sourceFragmentId`, `sourceFragmentHash`, artifact). Deux conditions :
1. Requirements Intake **inscrit dans Tuleap** le pointeur `fragment {id, hash}` dans `SourceRef` (champ additif du contrat et du tracker), pour que le lien fragment ↔ exigence soit natif et non reconstruit ;
2. un flux `GET /v1/documents/{id}/fragments` (NDJSON, ordre du document), **tenu par Requirements Intake** (c'est lui le propriétaire des fragments), exposé par la même façade ou par la sienne.

Le `sha256` de la source côté Archinex deviendrait alors l'empreinte de la **liste ordonnée des empreintes de fragments**, pas celle d'un texte brut.

## 8. Côté Archinex : la source « Tuleap »

| Archinex (`RequirementSource` / `Requirement`) | Depuis l'extrait |
|---|---|
| `kind` | `tuleap` (aujourd'hui `z.literal('rfp')` : **à étendre**) |
| `sha256` | `checksum` de l'extrait : même idempotence (même empreinte, mêmes lignes) |
| `title`, `version` | `scope.document`, `scope.revision` |
| `language` | **absente de Tuleap** : valeur par défaut déclarée, à confirmer |
| `clauseRef` | `requirementKey` (unique par source ; la section peut se répéter) |
| `title`, `text` | `title`, `statementText` |
| `category` | `domain` |
| `criticality` | **aucun équivalent dans Tuleap** (`bloquant`/`majeur`/`info` est requis par Archinex) : **à décider**, voir ci-dessous |
| `position` | ordre de l'extrait |
| `proposedDisposition`, `proposedBy` | `to_qualify`, `import:tuleap` : aucun modèle n'intervient |
| **nouveau** : `ref` (`sourceId`, `requirementKey`, `version`), `classification`, `editorialStatus` | de l'enregistrement |

- **Réimport avec une version plus récente** : même `requirementKey`, `version` plus haute → les propositions sont rafraîchies, **la décision humaine est conservée mais marquée « prise sur la version N »** (le texte a pu changer). Règle actuelle d'Archinex (« jamais écrasée ») maintenue.
- **`criticality`** : trois options : (a) Tuleap ajoute un champ d'obligation (`mandatory`/`recommended`/`informative`) — le plus propre, une modification du contrat ; (b) Archinex rend `criticality` nullable (« non qualifiée ») ; (c) valeur par défaut déclarée (je ne la recommande pas : elle inventerait une qualification).
- **Projets déjà ingérés par document** : une reprise peut proposer l'appariement par `sourceRef.document` + section et par texte, **confirmé par une personne**. C'est le seul endroit où la jointure subsiste ; elle n'est plus la voie nominale.

## 9. Côté Hub

Champ additif sur les exigences de l'engagement : `external_ref {sourceId, requirementKey, version}`, posé à la création (Archinex l'envoie avec l'exigence) ou par un geste séparé. Le Hub **valide** le motif de `sourceId` (`^[a-z0-9-]+:[a-z0-9-]+$`) et **n'invente jamais** de version. Il l'émet dans l'instantané d'engagement et dans la conformité de majeure 4 (MauriceIsrael/LLMOps#148, #150). Une nouvelle version de l'exigence côté Tuleap : à traiter (`requirement_changed` aujourd'hui refuse un texte différent sur un même identifiant ; il faudra une règle de remplacement par version). Contrat 1.41, à rédiger après accord.

## 10. Sécurité et exploitation

- **Appelants nommés** (Archinex, Hub), jeton de service portant un **plafond de classification** et une portée (registres, programmes). Archinex appelle de serveur à serveur, jamais depuis le navigateur ; l'utilisateur n'a pas de jeton Tuleap. Correspondance entre `Classification` de Tuleap (`NON_PROTEGE` … `TRES_SECRET`) et la confidentialité d'un projet Archinex : **à définir** (un plafond mal posé serait une fuite).
- Journal d'accès : appelant, registre, portée, empreinte servie. Pas d'énoncé dans les journaux.
- Erreurs au format `application/problem+json` : `registry_unavailable` (503, avec `Retry-After`, réessayable), `classification_ceiling` (403), `extract_expired` (410), `key_not_found` (404), `version_not_found` (404), `invalid_cursor` (400), `scope_too_broad` (422).
- Limites de débit et plafond de `limit` de Tuleap : **à recetter** (le service doit les absorber, pas les exposer).

## 11. Ce qui est à décider avec l'équipe Tuleap

1. **Où vit la façade** : service dans le dépôt `tuleap` (aujourd'hui sans dépendance web : `pydantic`, `httpx`, `PyYAML` seulement) ou dans Requirements Intake ? La suite ne connaît pas Archinex (SUITE-MAP) : le registre de canaux doit accepter un **consommateur qui n'est pas un composant de la suite**, la même question que pour le Hub (MauriceIsrael/LLMOps#154).
2. **Identité des documents** : `source_ref.document` est un texte libre (`CCTP-RRF-2026-03`) : sans liste de codes de documents, `GET /v1/documents` expose des variantes. Une liste tenue par Requirements Intake règlerait le problème.
3. **Champ d'obligation** dans le contrat (§8) et **pointeur de fragment** dans `SourceRef` (§7).
4. **Faisabilité** : plafond de pagination, coût de `values=all`, filtre par date de modification, fidélité du HTML.
5. **Qui peut demander un extrait** et selon quels plafonds.
6. `version.submittedBy` : sort-il ?

## 12. Livraison par étapes

| Étape | Contenu | Suffit pour |
|---|---|---|
| **P0** | `registries`, `documents`, `requirements` (aperçu), `requirements/{key}`, `refs:check`, `extracts` + flux NDJSON | l'import Archinex et la boucle vers le Hub |
| **P1** | `baselines` en lecture | rejouer une release |
| **P2** | pointeur de fragment dans Tuleap + flux de fragments (Requirements Intake) | audit d'omissions, reprise des projets existants |
| **P3** | flux de changements | synchronisation sans interrogation par lot |

## 13. Comment on saura que ça marche

- **Contrat** : le même jeu de tests contre le double en mémoire (`InMemoryRequirementRegistry`) et contre un faux Tuleap en processus, comme pour les ports existants ; un comportement qui diverge est un bug.
- **Sceau** : même état, même `extractId` ; modifier une exigence change l'empreinte (mutation) ; vecteurs `canonical-json` partagés ; le client reconstitue `data` à partir du flux et retrouve l'empreinte.
- **Flux** : tronqué (sans `end`), compte faux, empreinte fausse : refus entier. Reprise par `after`. Un extrait de 10 000 exigences sans croissance de mémoire du service.
- **Honnêteté** : au-dessus du plafond, `withheld.count` est exact et aucun énoncé fuit ; un registre injoignable est un 503, jamais une liste vide.
- **Boucle** : un projet Archinex importé depuis Tuleap, ses exigences envoyées au Hub avec `external_ref`, l'instantané d'engagement qui les porte, la conformité de majeure 4 acceptée par le lecteur du Document Engine (preuve de bout en bout de MauriceIsrael/LLMOps#148 et #150).

## 14. Correction à ma réponse précédente

J'avais cité `GET /baselines/{id}/artifacts` parmi les routes REST utilisées. C'est la voie du **plugin Baseline**, **absent de l'édition Community** (routes en 404, ADR-TULEAP-04) : sur Community, les baselines sont des fichiers figés adressés par empreinte.
