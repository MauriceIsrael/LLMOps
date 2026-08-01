# Phase 0: Kùzu → LadybugDB Migration Notes

### Section 0.1 — Audit de couplage

`import kuzu` appears in the following production files (excluding `.venv/` and `tests/`):

| Module | Fichier | Sites d'appel | Nature de l'usage |
|--------|---------|--------------|-------------------|
| `mcp_server` | `mcp_server/db/kuzu_client.py` | 3 | `kuzu.Database()`, `kuzu.Connection()`, cache singleton, `execute_cypher()` |
| `mcp_server` | `mcp_server/core/db.py` | 5 | `ReadOnlyKuzuClient`, `kuzu.Database(read_only=True/False)`, `kuzu.Connection()`, `.kuzu` file discovery |
| `pipelines` | `pipelines/ingestion/graph_loader.py` | 3 | `kuzu.Database()`, `kuzu.Connection()`, DDL + DML Cypher via `conn.execute()` |
| `pipelines` | `pipelines/ingestion/migrate_adr0015.py` | 4 | `kuzu.Database()`, `kuzu.Connection()`, `CALL show_tables()`, schema validation assertions |
| `pipelines` | `pipelines/ingestion/generate_schema_doc.py` | 2 | `kuzu.Database()`, `kuzu.Connection()`, table introspection |
| `pipelines` | `pipelines/visualization/graph_visualizer.py` | 2 | `kuzu.Database(read_only=True)`, `kuzu.Connection()` |

**Total : 6 fichiers, 19 sites d'appel, 3 modules distincts** (`mcp_server`, `pipelines`, `tools/elicitation` via `KuzuClient`).

⚠️ Exactement au seuil de la condition STOP §0.1 (3 modules). Le couplage est contenu : `tools/elicitation/repository.py` et `db_schema.py` n'importent pas `kuzu` directement mais passent par `KuzuClient`. Tous les accès Kùzu convergent vers `KuzuClient.execute_cypher()`.

### Section 0.2 — Audit de la chaîne d'ingestion LlamaIndex

Résultat : **Cas 1 — couplage faible, pas de `KuzuPropertyGraphStore` en production**.

Le pipeline d'ingestion utilise LlamaIndex pour l'extraction (`SchemaLLMPathExtractor` dans `llama_extractor.py`) mais **l'insertion en base passe par du Cypher brut** dans `graph_loader.py`, pas par `KuzuPropertyGraphStore`.

`llama-index-graph-stores-kuzu` est déclarée dans `pyproject.toml` mais n'est importée nulle part en production. C'est une dépendance fantôme.

Conséquences :
- Un `LadybugPropertyGraphStore` custom n'est **PAS** nécessaire
- Il suffit de remplacer `import kuzu` par `import ladybug as lb` dans `graph_loader.py`
- Remplacer `llama-index-graph-stores-kuzu` par `llama-index-graph-stores-ladybug` dans `pyproject.toml`

### Section — Améliorations repérées mais non faites (Règle 3)



### Section — Divergences de dialecte rencontrées

