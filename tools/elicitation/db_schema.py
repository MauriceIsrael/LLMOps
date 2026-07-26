"""Module d'initialisation et de migration du schéma Kùzu DB pour l'élicitation."""

from pathlib import Path

from mcp_server.db.kuzu_client import KuzuClient


class ElicitationSchemaInitializer:
    """Gestionnaire d'initialisation des tables d'élicitation dans Kùzu DB."""

    def __init__(self, db_path: str | Path = "data/kuzu_db") -> None:
        self.db_path = str(db_path)
        self.client = KuzuClient(db_path=self.db_path, read_only=False)
        self.db = self.client.db
        self.conn = self.client.conn
        self.init_schema()

    def init_schema(self) -> None:
        """Crée les tables de nœuds et de relations d'élicitation si elles n'existent pas."""
        tables_res = self.conn.execute("CALL show_tables() RETURN *;")
        table_names = []
        while tables_res.has_next():
            row = tables_res.get_next()
            if row:
                table_names.append(str(row[0]))

        # 1. Table Subject
        if "Subject" not in table_names:
            self.conn.execute(
                """
                CREATE NODE TABLE Subject (
                    name STRING,
                    definition STRING,
                    level STRING,
                    updated_at STRING,
                    PRIMARY KEY(name)
                );
                """
            )


        # 2. Table Statement
        if "Statement" not in table_names:
            self.conn.execute(
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
                    PRIMARY KEY(id)
                );
                """
            )
        else:
            try:
                self.conn.execute("ALTER TABLE Statement ADD subject STRING DEFAULT '';")
            except Exception:
                pass

        # 3. Table Question
        if "Question" not in table_names:
            self.conn.execute(
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
                    created_at STRING,
                    PRIMARY KEY(id)
                );
                """
            )

        # 4. Table Conflict
        if "Conflict" not in table_names:
            self.conn.execute(
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
                self.conn.execute("ALTER TABLE Conflict ADD origin STRING DEFAULT 'declared';")
            except Exception:
                pass

        # 5. Table Uncertainty
        if "Uncertainty" not in table_names:
            self.conn.execute(
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

        # 6. Table Asset (si elle n'existe pas)
        if "Asset" not in table_names:
            self.conn.execute(
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

        # 6. Tables de Relations
        if "ABOUT" not in table_names:
            self.conn.execute("CREATE REL TABLE ABOUT (FROM Statement TO Subject);")

        if "ANSWERS" not in table_names:
            self.conn.execute("CREATE REL TABLE ANSWERS (FROM Statement TO Question);")

        if "BASED_ON" not in table_names:
            self.conn.execute("CREATE REL TABLE BASED_ON (FROM Statement TO Asset);")

        if "TARGETS" not in table_names:
            self.conn.execute("CREATE REL TABLE TARGETS (FROM Question TO Subject);")

        if "INVOLVES" not in table_names:
            self.conn.execute("CREATE REL TABLE INVOLVES (FROM Conflict TO Statement);")
