"""Chargeur de données graphe pour insérer les entités et relations d'architecture."""

from pathlib import Path
from typing import Any

from tools.adapters.kuzu_store import make_graph_store
from tools.ports.graph_store import GraphStore


class KuzuGraphLoader:
    """Gestionnaire d'insertion et de mise à jour des entités dans la base graphe."""

    def __init__(
        self,
        db_path: str | Path = "data/kuzu_db",
        graph_store: GraphStore | None = None,
    ) -> None:
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.store = graph_store or make_graph_store(db_path=self.db_path, read_only=False)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialise ou met à jour le schéma de la base graphe."""
        tables_res = self.store.execute_cypher("CALL show_tables() RETURN name;")
        table_names = [str(r["name"]) for r in tables_res if r and "name" in r]

        if "Asset" not in table_names:
            self.store.execute_cypher(
                """
                CREATE NODE TABLE Asset (
                    id STRING,
                    title STRING,
                    type STRING,
                    status STRING,
                    confidence STRING,
                    phase STRING,
                    domain STRING,
                    last_reviewed STRING,
                    owner STRING,
                    source_path STRING,
                    PRIMARY KEY (id)
                );
                """
            )
        else:
            # Migration douce du schéma si phase / domain manquent
            try:
                self.store.execute_cypher("ALTER TABLE Asset ADD phase STRING;")
            except Exception:
                pass
            try:
                self.store.execute_cypher("ALTER TABLE Asset ADD domain STRING;")
            except Exception:
                pass

        if "GlossaryTerm" not in table_names:
            self.store.execute_cypher(
                """
                CREATE NODE TABLE GlossaryTerm (
                    term STRING,
                    definition STRING,
                    PRIMARY KEY (term)
                );
                """
            )

        if "SUPERSEDES" not in table_names:
            self.store.execute_cypher("CREATE REL TABLE SUPERSEDES (FROM Asset TO Asset);")

        if "REQUIRES" not in table_names:
            self.store.execute_cypher("CREATE REL TABLE REQUIRES (FROM Asset TO Asset);")

        if "DEFINES" not in table_names:
            self.store.execute_cypher("CREATE REL TABLE DEFINES (FROM Asset TO GlossaryTerm);")

    def load_doc_nodes_and_rels(self, nodes: list[Any], relations: list[Any]) -> None:
        """Insère les nœuds et relations dans la base graphe."""
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
                self.store.execute_cypher(query)
            else:
                doc_id = props.get("id", "").replace("'", "''")
                title = props.get("title", "").replace("'", "''")
                doc_type = props.get("type", "").replace("'", "''")
                status = props.get("status", "").replace("'", "''")
                confidence = props.get("confidence", "").replace("'", "''")
                phase = props.get("phase", "").replace("'", "''")
                domain = props.get("domain", "").replace("'", "''")
                last_reviewed = props.get("last_reviewed", "").replace("'", "''")
                owner = props.get("owner", "").replace("'", "''")
                source_path = props.get("source_path", "").replace("'", "''")

                query = f"""
                MERGE (a:Asset {{id: '{doc_id}'}})
                SET a.title = '{title}',
                    a.type = '{doc_type}',
                    a.status = '{status}',
                    a.confidence = '{confidence}',
                    a.phase = '{phase}',
                    a.domain = '{domain}',
                    a.last_reviewed = '{last_reviewed}',
                    a.owner = '{owner}',
                    a.source_path = '{source_path}';
                """
                self.store.execute_cypher(query)

        for rel in relations:
            src = rel.source_id.replace("'", "''")
            tgt = rel.target_id.replace("'", "''")
            lbl = rel.label

            if lbl == "SUPERSEDES":
                query = f"""
                MATCH (a1:Asset {{id: '{src}'}}), (a2:Asset {{id: '{tgt}'}})
                MERGE (a1)-[:SUPERSEDES]->(a2);
                """
                self.store.execute_cypher(query)
            elif lbl == "REQUIRES":
                query = f"""
                MATCH (a1:Asset {{id: '{src}'}}), (a2:Asset {{id: '{tgt}'}})
                MERGE (a1)-[:REQUIRES]->(a2);
                """
                self.store.execute_cypher(query)
            elif lbl == "DEFINES":
                query = f"""
                MATCH (a:Asset {{id: '{src}'}}), (g:GlossaryTerm {{term: '{tgt}'}})
                MERGE (a)-[:DEFINES]->(g);
                """
                self.store.execute_cypher(query)
