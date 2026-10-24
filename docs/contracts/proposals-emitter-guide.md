# Guide d'émetteur — canal de propositions suite → Hub (K7, contrat 1.33)

> Pour une application de la suite (Requirements Intake, Document Studio, Architecture Studio) qui voudrait **proposer** de la connaissance au Hub. Issue #157.
> Aucun émetteur n'existe aujourd'hui dans les dépôts de la suite lus (relevé du 2026-10-24, recherche par mots-clés, pas exhaustive) : ce guide est écrit **avant**
> le premier émetteur. Le canal est **un fichier**, jamais un appel : la suite n'appelle pas le Hub (ADR-SUITE-05, amendement du 2026-09-13, D1).

## Ce que l'émetteur produit

Une enveloppe de la suite `{schemaVersion, snapshotId, sourceSystem, createdAt, checksum, data}` :

| Champ | Règle |
|---|---|
| `schemaVersion` | `"1.0"` |
| `snapshotId` | unique, choisi par l'émetteur ; relire le même `snapshotId` ne crée rien deux fois (idempotence) |
| `sourceSystem` | **son propre nom** : `requirements-intake`, `document-studio` ou `architecture-studio`. Jamais celui d'un autre (ADR-DE-41, décision 2) ; le Hub n'est pas un émetteur de propositions |
| `createdAt` | ISO 8601, instant de production chez l'émetteur |
| `checksum` | `sha256:` + sha256 de `data` **seul**, au profil `canonical-json` v1 (`contracts/canonical-json.md`, vecteurs partagés) — jamais `JSON.stringify` |
| `data.candidates[]` | 1 à 500 candidates, identifiants uniques |

Pour sceller côté Python (outils internes, tests) : `pipelines.kb_candidates.proposals.seal`. Côté TypeScript, `computeSnapshotChecksum` du Document Engine ou le `canonicalJson` de `@architecture-suite/contracts`.

## Une candidate

Elle doit être **à la fois** une `ExtractedCandidate` de la suite et porter la proposition du Hub.

| Champ | Exigé par | Remarque |
|---|---|---|
| `id` | les deux | |
| `sourceFragment` `{id, documentId, documentVersion, originalText, hash, …un repère}` | la suite (obligatoire) ; le Hub (facultatif) | `hash` : empreinte du texte source |
| `originalText`, `normalizedText` | **la suite** (obligatoires, non vides) ; le Hub (facultatifs) | **L'exemple du Hub les omettait** : le schéma de la suite le refusait. Corrigé (`make verify-proposals`) |
| `candidateKind` | la suite (liste fermée de 8 valeurs) | `technical-requirement`, `functional-requirement`, `document-obligation`, `governance-obligation`, `planning-obligation`, `client-review`, `contractual-clause`, `acceptance-criterion` |
| `suggestedDestination` | les deux | **`"knowledge-hub-reference"`** (le Hub refuse toute autre valeur) |
| `proposal` | **le Hub seulement** | voir ci-dessous |

`proposal` : `kind` (`new_asset` / `amendment` / `rex`), `asset_type` (sauf `rex`), `title`, `proposed_content` (Markdown avec front matter), et facultativement `rationale`, `domain[]`,
`target_asset_id` (**obligatoire** pour `amendment`), `production_mode` (`llm-derived` par défaut : une proposition extraite n'est pas relue).

### Piège : `proposal` n'appartient pas au schéma de la suite

`extractedCandidateSchema` (zod, `requirements-intake/packages/contracts`) **retire les clés inconnues** à la lecture : mesuré, une candidate lue par ce schéma ressort sans `proposal`.
Un émetteur qui valide avec ce schéma puis sérialise le **résultat** envoie des candidates que le Hub refuse en bloc (`SCHEMA`, `proposal` manquant). Valider, puis **ajouter** `proposal` à
l'objet d'origine, ou lire en `passthrough`.

## Ce que le Hub fait de l'instantané

1. **Vérifie en entier** : schéma, sceau, identifiants uniques, amendement avec cible. Un seul problème : refus **en bloc** (`400`, `problems [{code, path, message}]`, aucune candidate créée ; `SEAL` si le contenu a été altéré).
2. Chaque proposition devient un **candidat du cycle ordinaire** : contrôles automatiques (dont l'**anonymisation K13** : identifiant d'engagement, e-mail, handle, IP, nom interdit refusés et nommés), revue par le propriétaire du domaine, double validation. **Rien ne devient actif sans revue humaine.**
3. Provenance conservée sur le candidat : `source.system`, `source.snapshot_id`, `source.snapshot_checksum`, `source.candidate_ref`.

## Comment il arrive jusqu'au Hub

Pas d'appel de la suite. Une personne ou un outil interne lit le fichier : `kb import-proposals <fichier> [--dry-run]` ou `POST /api/knowledge/proposals/import` (`?dry_run=1`). Commencer par `--dry-run`.

## Vérifier un émetteur

`make verify-proposals` rejoue l'exemple du Hub avec `extractedCandidateSchema` de Requirements Intake (dépôt voisin, `npm ci` fait ; code `3` = non vérifié). Contre-épreuve faite le 2026-10-24 : avant la correction de l'exemple,
la candidate était **refusée** (`originalText`, `normalizedText`) ; après, acceptée. Ce que cette vérification ne prouve pas : qu'un émetteur **existe**.

## À ne pas confondre

L'adaptateur `knowledge-hub` de Requirements Intake (`src/extraction/classifier/adapters/knowledgeHub.ts`) appelle `POST {INTAKE_KNOWLEDGE_HUB_URL}/classify` : c'est une **classification** de fragments par un service
qui reçoit une invite, pas ce canal. Le Hub n'expose pas cette route (issue #161).
