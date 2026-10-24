# Projection « décision du Hub → `governanceStatements` du Document Engine »

> **Projection de référence** (issue #153, ADR-DE-44 du Document Engine). Le propriétaire de l'adaptateur reste à désigner (A20, #40) : ce document
> fixe la **correspondance**, pas qui la porte. Implémentation de référence : `pipelines/engagement/governance_projection.py` ; témoin reconstruit par
> son test : `tests/fixtures/suite/governance-statements.golden.json` ; essai de bout en bout : `make e2e-suite`.
> Relevé fait contre `document-engine` `4a9361b` ; Architecture Studio, qui produit aujourd'hui ces énoncés dans la suite, n'a pas été lu.

## Ce que le Document Engine lit

Les décisions n'entrent pas par `items[]` (dont `layer` est obligatoire : un item sans couche est écarté). Elles voyagent dans
`ProjectedGraph.governanceStatements`, une collection de :

```ts
{ id: string; name: string; governanceKind: string; description?: string; attributes?: Record<string, string> }
```

Un bloc `table` les interroge par `query: { select: governance-statements, filters: { governanceKind: decision } }` et choisit ses `columns` parmi `label`
(= `name`), `description` et les **clés d'`attributes`, sous les noms du producteur**, jamais renommées (ADR-DE-44 §3). Absent et `[]` ne disent pas la
même chose : un graphe sans `governanceStatements` produit l'avertissement `incomplete-graph`.

## Correspondance

| Champ de la décision du Hub (instantané d'engagement, schéma `1.8`) | Champ projeté |
|---|---|
| `<engagement>` + `id` | `id` = `<engagement>:<id>` (comme les identifiants de sujets du Hub) |
| `decision` | `name` |
| — | `governanceKind` = `decision` |
| `rationale` | `description` |
| `status` `active` / `proposed` | `attributes["decision-status"]` = `accepted` / `proposed` |
| `assertion_level`, `origin`, `subject`, `reversibility` | `attributes["assertion-level"]`, `["origin"]`, `["subject"]`, `["reversibility"]` |
| `validated_by`, `validated_at` (décision affirmée seulement) | `attributes["validated-by"]`, `["validated-at"]` (un handle, jamais une adresse) |
| `rejected[]` `{option, reason}` | `attributes["rejected-options"]` = `option — raison; …` |
| `consequences[]` | `attributes["consequences"]` = `…; …` |
| `accepted_violations[]` `{typed_id, justification}` | `attributes["accepted-violations"]` = `typed_id — justification; …` |
| `based_on[].id` | `attributes["based-on"]` = `id, id` |
| `facts[]` `{key, value}` | `attributes["facts"]` = `clé=valeur; …` |
| (enveloppe) `snapshotId` | `attributes["source-snapshot"]`, avec `attributes["source"]` = `knowledge-hub` : la provenance se lit dans le livrable (ADR-DE-41 §5) |
| `governance-kind` | `attributes["governance-kind"]` = `decision` (l'usage du catalogue d'Architecture Studio lu par le Document Engine) |

Une propriété sans valeur n'est pas émise (cellule vide : « cette décision ne porte pas cette propriété »). Toutes les valeurs sont des chaînes.

## Règles

1. **Seul un instantané vérifié est projeté** (`verify` du canal K11) ; sinon `ProjectionRefusedError`, rien n'est produit.
2. **Une décision proposée ne sort jamais comme un fait.** Par défaut elle n'est pas publiée ; avec `include_proposed=True` elle l'est, marquée `decision-status: proposed`
   et sans validateur. **Choix confirmé par le mainteneur le 2026-10-24** : l'exclusion par défaut.
3. Une décision **remplacée** ou **retirée** n'engage plus personne : jamais publiée.
4. Un statut inconnu **lève** : on ne devine pas. `accepted` et `proposed` sont les seules valeurs de `decision-status` constatées dans le catalogue lu par le
   Document Engine ; le Hub n'en invente pas d'autres.
5. **Le Hub ne détient ni hypothèses ni risques** : la projection n'en publie aucun et le dit (`not_published_by_the_hub`). Un plan alimenté par le Hub ne doit
   donc **pas** porter de registre de risques ni de liste d'hypothèses : le Document Engine les rendrait vides, sans avertissement dès qu'une décision est publiée,
   et un registre de risques vide se lit « aucun risque ». (Les hypothèses attachées aux décisions sont l'objet de l'issue #135.)

## Limites connues

- **L'instantané provisoire** (`is_provisional`, `provisional_reasons`) est dans le rapport de la projection, **pas** dans le document : `ProjectedGraph` n'a aucun champ
  pour le porter et le Document Engine n'a pas de notion d'instantané provisoire. Le HLD ne dit donc pas qu'il repose sur une connaissance provisoire. À demander au
  propriétaire du Document Engine.
- **Maturité** : la projection ne publie pas les sujets. La projection de `L5_archived` vers `L4_specified` (SUITE-MAP §5.5) reste à faire quand les sujets seront publiés.
- Les **composants, couches et flux** du HLD ne viennent pas du Hub (#138) : l'essai de bout en bout les emprunte à un graphe de démonstration.
- Le vocabulaire de `decision-status` (`accepted`, `proposed`) est relevé dans un jeu de test du Document Engine, pas dans le métamodèle d'Architecture Studio.

## À décider

- ~~Décision proposée : exclue ou publiée marquée~~ **Tranché le 2026-10-24 : exclue par défaut** ; `include_proposed=True` reste disponible pour une relecture, jamais comme défaut d'un livrable.
- Où vit l'adaptateur (A20) : chez le consommateur, qui connaît `ProjectedGraph`, ou au Hub.
