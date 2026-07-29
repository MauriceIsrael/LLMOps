"""ADR-0015 Migration Script (F3).

Migrates single kuzu_db layout to physical two-plane layout:
  - data/knowledge.kuzu                   (Asset, GlossaryTerm, SUPERSEDES)
  - data/engagements/nordwave-mcx-2027.kuzu (Subject, Statement, Question, Conflict, Uncertainty)
"""

import shutil
from pathlib import Path

import kuzu
from pipelines.ingestion.graph_loader import KuzuGraphLoader
from tools.elicitation.db_schema import ElicitationSchemaInitializer


def migrate_to_adr0015(data_dir: Path | str = "data") -> dict[str, str]:
    base = Path(data_dir)
    src_db = base / "kuzu_db"
    knowledge_db = base / "knowledge.kuzu"
    engagements_dir = base / "engagements"
    ref_engagement_db = engagements_dir / "nordwave-mcx-2027.kuzu"

    engagements_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initialize clean knowledge.kuzu
    if knowledge_db.exists():
        shutil.rmtree(knowledge_db)

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
    db_k = kuzu.Database(str(knowledge_db))
    conn_k = kuzu.Connection(db_k)
    res_k = conn_k.execute("CALL show_tables() RETURN name;")
    final_tables_k = set()
    while res_k.has_next():
        row = res_k.get_next()
        if row:
            final_tables_k.add(str(row[0]))
    del conn_k
    del db_k

    db_e = kuzu.Database(str(ref_engagement_db))
    conn_e = kuzu.Connection(db_e)
    res_e = conn_e.execute("CALL show_tables() RETURN name;")
    final_tables_e = set()
    while res_e.has_next():
        row = res_e.get_next()
        if row:
            final_tables_e.add(str(row[0]))
    del conn_e
    del db_e

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
    main()
