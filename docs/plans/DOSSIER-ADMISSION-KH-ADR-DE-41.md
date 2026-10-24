# Dossier d'admission de `knowledge-hub` comme source du canal de conformité du Document Engine (ADR-DE-41)

> Préparation côté Hub, issue #152. Le Hub **prépare** ; l'admission est un amendement daté d'ADR-DE-41, dans le dépôt du Document Engine, par son propriétaire. Ce dossier ne décide rien et n'a pas
> la valeur d'une preuve d'acceptation. Relevé du 2026-10-24 : `document-engine` `4a9361b`, LLMOps contrat 1.40.

## Les trois conditions d'ADR-DE-41 (décision 4), dans l'ordre

| # | Condition | État | Preuve (ou ce qui manque) |
|---|---|---|---|
| 1 | Un **contrat versionné** côté Hub (une API ou un canal à instantané scellé, sans préjuger de la forme) | **Partiel** | Contrat `docs/contracts/knowledge-hub-api-v1.md` (§5.18 engagement, §5.30 et §5.40 conformité) ; schéma `schemas/engagement_snapshot.schema.json`. **La forme de la conformité n'est pas alignée** (voir « Ce que le lecteur refuse »), et la majeure 4 dépend de #150 |
| 2 | **Vecteurs partagés** : le Hub émet une `ConformityData` conforme et un `checksum` que le Document Engine recalcule à l'identique | **Partiel** | **Fait** : vecteurs `canonical-json` identiques octet pour octet (SHA-256 `3f629da8…`) ; le `checksum` du témoin de conformité et de l'exemple d'engagement est recalculé à l'identique par `computeSnapshotChecksum` du Document Engine (`make verify-suite`). **Manque** : `ConformityData` **conforme** (le lecteur refuse), et un test rejoué **chez** le Document Engine |
| 3 | **Décision de suite** sur le rôle du Hub comme source de conformité | **Non prise** | N'appartient pas au Document Engine (ADR-DE-01) ; à poser aux propriétaires (SUITE-MAP §6) |

## Ce que le lecteur du Document Engine refuse aujourd'hui (mesuré avec son code)

Dans l'ordre où il refuse ; seul le premier est mesuré directement, les suivants l'ont été en posant à la main la provenance et la `ref` dans une expérience locale hors dépôt.

1. **Provenance** : `'sourceSystem' attendu 'tuleap', reçu 'knowledge-hub'` — `CONFORMITY_SOURCE_SYSTEM` est encore un scalaire (`src/conformity/types.ts`) ; le premier lot d'exécution d'ADR-DE-41 (un ensemble déclaré) n'est pas fait.
2. **Version** : le lecteur oppose la majeure `4` ; le Hub émet `2.0`.
3. **`ref`** : `RequirementRef {sourceId, requirementKey, version}` est requise sur chaque exigence en majeure 4 ; le Hub n'en émet aucune (#150).
4. **Source de preuve** : `evidence[].source` est un vocabulaire fermé (`VALID_EVIDENCE_SOURCES` : `architecture-studio`, `ip-flow-manager`, `document-engine`, `edm`, `tuleap`, `external-registry`) ; `knowledge-hub` n'en fait pas partie.

## Ce que l'admission exigera du livrable (ADR-DE-41, décision 5)

Publier sans juger a pour contrepartie que le **lecteur** voie *qui affirme quoi*, dans le **même lot** que l'ajout du nom. Côté Hub, deux éléments existent déjà pour l'alimenter : la section `compliance` de
l'instantané d'engagement porte `origin: "knowledge-hub"` et ne dit jamais `verified` ; la projection des décisions (`docs/contracts/suite-governance-projection.md`, sur sa propre branche) pose `source` et `source-snapshot` sur chaque énoncé.
Le rendu de la provenance dans les blocs de matrice d'exigences est une demande au Document Engine.

Admettre un nom n'endosse pas une qualité (ADR-DE-41, conséquences) : un statut `allocated` du Hub traverse comme celui de Tuleap ; c'est le lecteur, provenance sous les yeux, qui en pèse la valeur.

## Proposition à soumettre pour la condition 3

Le Hub n'émet que `allocated` (couverture **déclarée** par une décision ou un actif), `identified` (rien ne la déclare), jamais `verified` ni `accepted` ; il le dit dans chaque ligne ; sa source de preuve est `knowledge-hub`. Aucune exigence n'est émise sans `ref`
(#150). Il ne se substitue pas à Tuleap : qui fait foi pour les exigences d'un appel d'offres reste à trancher (SUITE-MAP §5.3).

## Annexe — trois demandes à ouvrir chez le propriétaire du Document Engine

À déposer par la personne qui en a la charge ; rien n'a été ouvert dans ce dépôt.

**A. Ensemble de sources de conformité (premier lot d'ADR-DE-41).** `CONFORMITY_SOURCE_SYSTEM: 'tuleap'` → `CONFORMITY_SOURCE_SYSTEMS: ['tuleap']`, opposé par le validateur, message d'erreur nommant l'ensemble ; mêmes changements pour les canaux EDM, Confluence, IP Flow Manager ; témoin de parité inchangé tant que la liste n'a qu'un nom.

**B. Amendement daté d'ADR-DE-41 admettant `knowledge-hub`** quand les trois conditions ci-dessus sont remplies, **y compris** l'admission de `knowledge-hub` dans le vocabulaire fermé `evidence[].source`, que l'ADR ne mentionne pas aujourd'hui.

**C. Provenance lisible dans le livrable** (décision 5), dans le même lot que B : les blocs `requirement-matrix` et `requirement-section-matrix` montrent le système source de chaque exigence quand deux systèmes peuvent affirmer dans un même dossier.

Question complémentaire, hors ADR-DE-41 : le `ProjectedGraph` n'a aucun champ pour dire qu'il repose sur une connaissance **provisoire** (`is_provisional` de l'instantané d'engagement) ; le HLD ne peut donc pas le dire.
