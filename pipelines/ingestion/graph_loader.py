"""Graph data loader for ingesting architecture entities and relations into LadybugDB."""

from pathlib import Path
from typing import Any

from tools.adapters.ladybug_store import LadybugGraphStore
from tools.ports.graph_store import GraphStore


class LadybugGraphLoader:
    """Manager for inserting and updating entities and relations in the graph database."""

    def __init__(
        self,
        db_path: str | Path = "data/knowledge.lbug",
        graph_store: GraphStore | None = None,
    ) -> None:
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.store = graph_store or LadybugGraphStore(db_path=self.db_path, read_only=False)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initializes or updates the graph database schema."""
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
                    version STRING,
                    markdown_content STRING,
                    sha256 STRING,
                    external_ref STRING,
                    PRIMARY KEY (id)
                );
                """
            )
        else:
            for col in ("phase", "domain", "version", "markdown_content", "sha256", "external_ref"):
                try:
                    self.store.execute_cypher(f"ALTER TABLE Asset ADD {col} STRING;")
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
        """Inserts nodes and relations into the graph database using parameterized Cypher."""
        for node in nodes:
            props = node.properties
            label = node.label

            if label == "GLOSSARY_TERM":
                term = str(props.get("term", ""))
                definition = str(props.get("definition", ""))
                query = "MERGE (g:GlossaryTerm {term: $term}) SET g.definition = $definition;"
                self.store.execute_cypher(query, {"term": term, "definition": definition})
            else:
                doc_id = str(props.get("id", ""))
                title = str(props.get("title", ""))
                doc_type = str(props.get("type", ""))
                status = str(props.get("status", ""))
                confidence = str(props.get("confidence", ""))
                phase = str(props.get("phase", ""))
                domain = str(props.get("domain", ""))
                last_reviewed = str(props.get("last_reviewed", ""))
                owner = str(props.get("owner", ""))
                source_path = str(props.get("source_path", ""))
                version = str(props.get("version", "1.0.0"))
                markdown_content = str(props.get("markdown_content", ""))
                sha256 = str(props.get("sha256", ""))
                external_ref = str(props.get("external_ref", f"KH:{doc_id}@v{version}"))

                query = """
                MERGE (a:Asset {id: $id})
                SET a.title = $title,
                    a.type = $type,
                    a.status = $status,
                    a.confidence = $confidence,
                    a.phase = $phase,
                    a.domain = $domain,
                    a.last_reviewed = $last_reviewed,
                    a.owner = $owner,
                    a.source_path = $source_path,
                    a.version = $version,
                    a.markdown_content = $markdown_content,
                    a.sha256 = $sha256,
                    a.external_ref = $external_ref;
                """
                self.store.execute_cypher(
                    query,
                    {
                        "id": doc_id,
                        "title": title,
                        "type": doc_type,
                        "status": status,
                        "confidence": confidence,
                        "phase": phase,
                        "domain": domain,
                        "last_reviewed": last_reviewed,
                        "owner": owner,
                        "source_path": source_path,
                        "version": version,
                        "markdown_content": markdown_content,
                        "sha256": sha256,
                        "external_ref": external_ref,
                    },
                )

        for rel in relations:
            src = str(rel.source_id)
            tgt = str(rel.target_id)
            lbl = rel.label

            if lbl == "SUPERSEDES":
                query = "MATCH (a1:Asset {id: $src}), (a2:Asset {id: $tgt}) MERGE (a1)-[:SUPERSEDES]->(a2);"
                self.store.execute_cypher(query, {"src": src, "tgt": tgt})
            elif lbl == "REQUIRES":
                query = "MATCH (a1:Asset {id: $src}), (a2:Asset {id: $tgt}) MERGE (a1)-[:REQUIRES]->(a2);"
                self.store.execute_cypher(query, {"src": src, "tgt": tgt})
            elif lbl == "DEFINES":
                query = "MATCH (a:Asset {id: $src}), (g:GlossaryTerm {term: $tgt}) MERGE (a)-[:DEFINES]->(g);"
                self.store.execute_cypher(query, {"src": src, "tgt": tgt})


# Backward compatibility alias
KuzuGraphLoader = LadybugGraphLoader
