"""ADR-0015 Migration Script (F3).

Migrates single kuzu_db layout to physical two-plane layout:
  - data/knowledge.kuzu                   (Asset, GlossaryTerm, SUPERSEDES)
  - data/engagements/nordwave-mcx-2027.kuzu (Subject, Statement, Question, Conflict, Uncertainty)
"""

import shutil
from pathlib import Path

from tools.adapters.kuzu_store import make_graph_store
from tools.elicitation.db_schema import ElicitationSchemaInitializer


def migrate_to_adr0015(data_dir: Path | str = "data") -> dict[str, str]:
    base = Path(data_dir)
    knowledge_db = base / "knowledge.lbug"
    engagements_dir = base / "engagements"
    ref_engagement_db = engagements_dir / "nordwave-mcx-2027.lbug"

    engagements_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initialize clean knowledge.lbug
    if knowledge_db.exists():
        if knowledge_db.is_dir():
            shutil.rmtree(knowledge_db)
        else:
            knowledge_db.unlink()

    from pipelines.cli import ingest
    try:
        ingest(kb_dir=Path("data/kb"), db_path=knowledge_db)
    except SystemExit:
        pass

    # 2. Initialize reference engagement database
    if not ref_engagement_db.exists():
        schema_init = ElicitationSchemaInitializer(db_path=ref_engagement_db)
        del schema_init

    # Assert physical plane separation
    forbidden_in_knowledge = ["Subject", "Statement", "Question", "Conflict", "Uncertainty"]
    store_k = make_graph_store(str(knowledge_db))
    res_k = store_k.execute_cypher("CALL show_tables() RETURN name;")
    final_tables_k = {str(row["name"]) for row in res_k if row and "name" in row}
    store_k.close()

    store_e = make_graph_store(str(ref_engagement_db))
    res_e = store_e.execute_cypher("CALL show_tables() RETURN name;")
    final_tables_e = {str(row["name"]) for row in res_e if row and "name" in row}
    store_e.close()

    assert not (set(forbidden_in_knowledge) & final_tables_k), (
        f"Migration failed: knowledge database contains engagement tables: {set(forbidden_in_knowledge) & final_tables_k}"
    )
    assert "Asset" not in final_tables_e, (
        "Migration failed: engagement database contains copied Asset table!"
    )

    return {
        "knowledge_db": str(knowledge_db),
        "ref_engagement_db": str(ref_engagement_db),
        "status": "success",
    }


def main() -> None:
    res = migrate_to_adr0015()
    print(f"✅ ADR-0015 Migration completed successfully! Output: {res}")


if __name__ == "__main__":
    import os
    main()
    os._exit(0)
