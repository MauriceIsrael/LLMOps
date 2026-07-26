"""Chargeur de données Kùzu DB pour insérer les entités et relations du graphe."""

from pathlib import Path
from typing import Any

import kuzu


class KuzuGraphLoader:
    """Gestionnaire d'insertion et de mise à jour des entités dans Kùzu DB."""

    def __init__(self, db_path: str | Path = "data/kuzu_db") -> None:
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(self.db_path)
        self.conn = kuzu.Connection(self.db)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialise les tables de nœuds et de relations dans Kùzu DB si elles n'existent pas."""
        tables_res = self.conn.execute("CALL show_tables() RETURN *;")
        table_names = []
        while tables_res.has_next():
            row = tables_res.get_next()
            if row:
                table_names.append(str(row[0]))

        if "Asset" not in table_names:
            self.conn.execute(
                """
                CREATE NODE TABLE Asset (
                    id STRING,
                    title STRING,
                    type STRING,
                    status STRING,
                    confidence STRING,
                    last_reviewed STRING,
                    owner STRING,
                    source_path STRING,
                    PRIMARY KEY (id)
                );
                """
            )

        if "GlossaryTerm" not in table_names:
            self.conn.execute(
                """
                CREATE NODE TABLE GlossaryTerm (
                    term STRING,
                    definition STRING,
                    PRIMARY KEY (term)
                );
                """
            )

        if "SUPERSEDES" not in table_names:
            self.conn.execute("CREATE REL TABLE SUPERSEDES (FROM Asset TO Asset);")

        if "REQUIRES" not in table_names:
            self.conn.execute("CREATE REL TABLE REQUIRES (FROM Asset TO Asset);")

        if "DEFINES" not in table_names:
            self.conn.execute("CREATE REL TABLE DEFINES (FROM Asset TO GlossaryTerm);")

    def load_doc_nodes_and_rels(self, nodes: list[Any], relations: list[Any]) -> None:
        """Insère les nœuds et relations dans Kùzu DB."""
        for node in nodes:
            props = node.properties
            label = node.label

            if label == "GLOSSARY_TERM":
                term = props.get("term", "").replace("'", "''")
                definition = props.get("definition", "").replace("'", "''")
                query = f"""
                MERGE (g:GlossaryTerm {{term: '{term}'}})
                SET g.definition = '{definition}';
                """
                self.conn.execute(query)
            else:
                doc_id = props.get("id", "").replace("'", "''")
                title = props.get("title", "").replace("'", "''")
                doc_type = props.get("type", "").replace("'", "''")
                status = props.get("status", "").replace("'", "''")
                confidence = props.get("confidence", "").replace("'", "''")
                last_reviewed = props.get("last_reviewed", "").replace("'", "''")
                owner = props.get("owner", "").replace("'", "''")
                source_path = props.get("source_path", "").replace("'", "''")

                query = f"""
                MERGE (a:Asset {{id: '{doc_id}'}})
                SET a.title = '{title}',
                    a.type = '{doc_type}',
                    a.status = '{status}',
                    a.confidence = '{confidence}',
                    a.last_reviewed = '{last_reviewed}',
                    a.owner = '{owner}',
                    a.source_path = '{source_path}';
                """
                self.conn.execute(query)

        for rel in relations:
            src = rel.source_id.replace("'", "''")
            tgt = rel.target_id.replace("'", "''")
            lbl = rel.label

            if lbl == "SUPERSEDES":
                query = f"""
                MATCH (a1:Asset {{id: '{src}'}}), (a2:Asset {{id: '{tgt}'}})
                MERGE (a1)-[:SUPERSEDES]->(a2);
                """
                self.conn.execute(query)
            elif lbl == "REQUIRES":
                query = f"""
                MATCH (a1:Asset {{id: '{src}'}}), (a2:Asset {{id: '{tgt}'}})
                MERGE (a1)-[:REQUIRES]->(a2);
                """
                self.conn.execute(query)
            elif lbl == "DEFINES":
                query = f"""
                MATCH (a:Asset {{id: '{src}'}}), (g:GlossaryTerm {{term: '{tgt}'}})
                MERGE (a)-[:DEFINES]->(g);
                """
                self.conn.execute(query)
