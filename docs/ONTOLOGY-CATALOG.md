# Catalogue d'ontologie servi aux clients

Référence : issues #189 (une seule forme d'export), #190 (pureté d'intention), #191 (cohérence interne et contrat d'export).

## Une seule forme servie

`GET /api/knowledge/ontology/export` et l'outil MCP `export_ontology_catalog` servent **le catalogue** :

```json
{ "catalog_version": "1.0", "generated_at": "…", "entities": { "<urn>": { … } }, "triplets": [ … ], "clause_index": { … } }
```

Schéma : `schemas/ontology_catalog.schema.json`. Fichier : `data/snapshots/ontology_export.json`. Chargeur unique : `pipelines/ontology/catalog_file.py`.

| Situation | Réponse |
|---|---|
| fichier présent, forme catalogue | 200, catalogue (enveloppe `payload` dépliée, `clause_index` garanti) |
| fichier absent | **404** `{"code": "ontology_export_not_found"}` ; rien n'est régénéré |
| fichier d'une autre forme (sans `entities`, par exemple `payload.entries`) | **503** `{"code": "ontology_export_wrong_shape"}` ; jamais servi |

Le producteur « entries » (`pipelines.ontology.export`, commande `kb ontology export`) écrit une **autre forme** (`payload.entries`) dans `data/snapshots/ontology_entries_export.json`. Les deux ne partagent plus de chemin.

## Contrôles

`python -m pipelines.kb_cli ontology catalog-check [--catalog <fichier>] [--strict]`

1. **Cohérence interne d'une feuille** : `oracle_rules` sans `projections` est une **erreur** (les règles n'ont pas de paramètres : elles seraient sans objet) ; `projections` sans `governed_by_clauses` est un **avertissement**.
2. **Pureté d'intention** : aucune adresse IPv4/IPv6, CIDR ou MAC dans les `projections` ni dans `hydration_template.reconciliation_graph`. L'ontologie est une doctrine commune à tous les projets ; les **instances** (identifiants, tenants, sous-réseaux) sont des données du projet. Les autres gabarits d'hydratation génèrent par nature des valeurs par défaut et ne sont pas contrôlés.

Limite connue : seules les adresses sont détectées ; un identifiant concret (nom d'hôte, identifiant de tenant) n'est pas reconnaissable mécaniquement.

## Contrat d'export

Les consommateurs peuvent compter sur : `catalog_version`, `generated_at`, `entities`, `triplets`, `clause_index`, et pour chaque entité `urn`, `revision`, `kind`, `title` (testé par `tests/unit/test_ontology_catalog_checks.py`).
