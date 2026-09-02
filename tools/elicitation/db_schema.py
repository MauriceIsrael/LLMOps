from pathlib import Path

from tools.adapters.kuzu_store import make_graph_store
from tools.ports.graph_store import GraphStore


class ElicitationSchemaInitializer:
    """Gestionnaire d'initialisation des tables d'élicitation dans le graphe."""

    def __init__(
        self,
        db_path: str | Path = "data/kuzu_db",
        graph_store: GraphStore | None = None,
    ) -> None:
        self.db_path = str(db_path)
        self.graph_store = graph_store or make_graph_store(db_path=self.db_path, read_only=False)
        self.init_schema(self.graph_store)

    def init_schema(self, graph_store: GraphStore) -> None:
        """Crée les tables de nœuds et de relations d'élicitation si elles n'existent pas."""
        tables_res = graph_store.execute_cypher("CALL show_tables() RETURN name;")
        table_names = [str(r["name"]) for r in tables_res if r and "name" in r]

        # 1. Table Subject
        if "Subject" not in table_names:
            self.graph_store.execute_cypher(
                """
                CREATE NODE TABLE Subject (
                    id STRING,
                    name STRING,
                    engagement STRING,
                    definition STRING,
                    level STRING,
                    origin STRING,
                    updated_at STRING,
                    PRIMARY KEY(id)
                );
                """
            )
        else:
            try:
                self.graph_store.execute_cypher("ALTER TABLE Subject ADD origin STRING DEFAULT 'declared';")
            except Exception:
                pass


        # 2. Table Statement
        if "Statement" not in table_names:
            self.graph_store.execute_cypher(
                """
                CREATE NODE TABLE Statement (
                    id STRING,
                    engagement STRING,
                    section STRING,
                    subject STRING,
                    predicate STRING,
                    value STRING,
                    unit STRING,
                    author STRING,
                    role STRING,
                    confidence STRING,
                    verbatim STRING,
                    created_at STRING,
                    status STRING,
                    based_on STRING,
                    PRIMARY KEY(id)
                );
                """
            )
        else:
            try:
                self.graph_store.execute_cypher("ALTER TABLE Statement ADD subject STRING DEFAULT '';")
            except Exception:
                pass
            try:
                self.graph_store.execute_cypher("ALTER TABLE Statement ADD based_on STRING DEFAULT '[]';")
            except Exception:
                pass

        # 3. Table Question
        if "Question" not in table_names:
            self.graph_store.execute_cypher(
                """
                CREATE NODE TABLE Question (
                    id STRING,
                    engagement STRING,
                    gap_type STRING,
                    section STRING,
                    question STRING,
                    why_it_matters STRING,
                    expected_shape STRING,
                    routed_to STRING,
                    status STRING,
                    level STRING DEFAULT '',
                    created_at STRING,
                    PRIMARY KEY(id)
                );
                """
            )
        else:
            try:
                self.graph_store.execute_cypher("ALTER TABLE Question ADD level STRING DEFAULT '';")
            except Exception:
                pass

        # 4. Table Conflict
        if "Conflict" not in table_names:
            self.graph_store.execute_cypher(
                """
                CREATE NODE TABLE Conflict (
                    id STRING,
                    kind STRING,
                    detail STRING,
                    status STRING,
                    origin STRING,
                    resolution STRING,
                    arbitrated_by STRING,
                    PRIMARY KEY(id)
                );
                """
            )
        else:
            try:
                self.graph_store.execute_cypher("ALTER TABLE Conflict ADD origin STRING DEFAULT 'declared';")
            except Exception:
                pass

        # 5. Table Uncertainty
        if "Uncertainty" not in table_names:
            self.graph_store.execute_cypher(
                """
                CREATE NODE TABLE Uncertainty (
                    id STRING,
                    engagement STRING,
                    subject STRING,
                    text STRING,
                    PRIMARY KEY(id)
                );
                """
            )

        # 6. Tables de Relations
        if "ABOUT" not in table_names:
            self.graph_store.execute_cypher("CREATE REL TABLE ABOUT (FROM Statement TO Subject);")

        if "ANSWERS" not in table_names:
            self.graph_store.execute_cypher("CREATE REL TABLE ANSWERS (FROM Statement TO Question);")

        if "TARGETS" not in table_names:
            self.graph_store.execute_cypher("CREATE REL TABLE TARGETS (FROM Question TO Subject);")

        if "INVOLVES" not in table_names:
            self.graph_store.execute_cypher("CREATE REL TABLE INVOLVES (FROM Conflict TO Statement);")
