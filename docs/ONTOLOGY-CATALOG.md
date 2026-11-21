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

## Migration depuis la fixture d'un consommateur (issue #192)

`scripts/migrate_ontology_from_fixture.py` reprend, **une fois et à la main**, le contenu d'une fixture de consommateur (Archinex) dans le catalogue, de façon additive et déterministe :

- entité absente du Hub : **ajoutée** ; champ absent d'une entité commune : **complété** (la `revision` de l'entité est incrémentée) ;
- champ présent des deux côtés et différent : **conflit**, la valeur du Hub est **conservée** et le conflit est listé ; une source qui ne fait qu'**ajouter** des clés ou des éléments à la valeur du Hub est un enrichissement, pas un conflit ;
- `oracle_rules` et `projections` forment un **lot** : jamais mélangés ;
- les **données de projet** ne migrent pas (identifiants d'exigences `REQ-…`, numéros de lot, noms de projet, identifiants de tenant ou de nœud d'un scénario) ; un garde-fou final échoue si une marque subsiste ;
- chaque `governed_by_clauses` reçoit son triplet `satisfies_clause` (exigé par `validate_clause_leaf_integrity`) avec une justification qui dit sa provenance : **à rédiger par le relecteur**.

Le rapport de relecture (`docs/ONTOLOGY-MIGRATION-REPORT.md`) liste les ajouts, les enrichissements, les données de projet retirées et chaque conflit en regard des deux valeurs.

### Prédicats et champs ajoutés au schéma

Les prédicats `requires_prerequisite_axis` (fermeture transitive des prérequis) et `instantiates_component` (feuille → composant logique) rejoignent l'énumération des triplets ; `togaf_domain`, `document_engine_layer`, `default_decision_type` (`type1_deliberate` / `type2_default_ratify`) et `instantiated_component` sont des champs d'entité optionnels. Ajouts seulement.

### Limites connues

- Le Hub **ne valide pas** l'existence d'une URN de clause (aucun registre de clauses dans `data/kb`) : seule la forme de l'URN est contrôlée.
- Trois identifiants de triplets du Hub sont dupliqués (`tr-014` à `tr-016`) depuis avant la migration : signalés par `catalog-check` (avertissement), non renumérotés (des consommateurs citent ces identifiants).
- Quatre règles d'oracle déclarées dans le catalogue ne sont pas implémentées dans le Rego d'Archinex (`deny_shared_oob_network`, `deny_insecure_security_zone`, `deny_single_point_of_power_failure`, `deny_divergent_preprod_topology`) : elles sont d'origine Hub.
- La règle `deny_unmediated_s6a_direct_flow` de la feuille IPsec perd son paramètre `required_mediation_hops` (identifiants de nœuds de scénario) : sans modèle de graphe (issue #196), elle est inerte tant que le consommateur ne fournit pas les instances.

