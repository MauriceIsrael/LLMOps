"""Module de stockage (Repository) — Seul composant autorisé à écrire dans Kùzu DB."""

from datetime import datetime
from pathlib import Path
from typing import Any

from mcp_server.db.kuzu_client import KuzuClient
from tools.elicitation.config import ALLOWED_PREDICATES
from tools.elicitation.db_schema import ElicitationSchemaInitializer


class ElicitationRepository:
    """Repository d'accès aux données pour l'élicitation avec validation stricte."""

    def __init__(self, db_path: str | Path = "data/kuzu_db") -> None:
        self.db_path = str(db_path)
        # Initialise le schéma au besoin
        ElicitationSchemaInitializer(db_path=self.db_path)
        self.db_client = KuzuClient(db_path=self.db_path, read_only=False)


    def save_subject(self, name: str, definition: str = "") -> None:
        """Enregistre ou met à jour un sujet canonique dans Kùzu DB."""
        name_esc = name.replace("'", "''")
        def_esc = definition.replace("'", "''")
        query = f"""
        MERGE (s:Subject {{name: '{name_esc}'}})
        SET s.definition = '{def_esc}';
        """
        self.db_client.execute_cypher(query)

    def save_question(self, question: dict[str, Any]) -> str:
        """Enregistre une question élicitée dans Kùzu DB."""
        q_id = question.get("id") or f"Q-{int(datetime.now().timestamp() * 1000)}"
        engagement = str(question.get("engagement", "demo-2026")).replace("'", "''")
        gap_type = str(question.get("gap_type", "G1_empty_section")).replace("'", "''")
        section = str(question.get("section", "general")).replace("'", "''")
        question_text = str(question.get("question", "")).replace("'", "''")
        why_it_matters = str(question.get("why_it_matters", "")).replace("'", "''")
        expected_shape = str(question.get("expected_shape", "free_text")).replace("'", "''")
        routed_to = str(question.get("routed_to", "architect")).replace("'", "''")
        status = str(question.get("status", "open")).replace("'", "''")
        created_at = str(question.get("created_at", datetime.now().isoformat())).replace("'", "''")

        query = f"""
        MERGE (q:Question {{id: '{q_id}'}})
        SET q.engagement = '{engagement}',
            q.gap_type = '{gap_type}',
            q.section = '{section}',
            q.question = '{question_text}',
            q.why_it_matters = '{why_it_matters}',
            q.expected_shape = '{expected_shape}',
            q.routed_to = '{routed_to}',
            q.status = '{status}',
            q.created_at = '{created_at}';
        """
        self.db_client.execute_cypher(query)

        # Lier au sujet cible si présent
        subject_name = question.get("subject")
        if subject_name:
            self.save_subject(subject_name)
            sub_esc = subject_name.replace("'", "''")
            rel_query = f"""
            MATCH (q:Question {{id: '{q_id}'}}), (s:Subject {{name: '{sub_esc}'}})
            MERGE (q)-[:TARGETS]->(s);
            """
            self.db_client.execute_cypher(rel_query)

        return q_id

    def update_question_status(self, question_id: str, status: str) -> None:
        """Met à jour le statut d'une question (sent, confirmed, declined, etc.)."""
        query = f"""
        MATCH (q:Question {{id: '{question_id}'}})
        SET q.status = '{status}';
        """
        self.db_client.execute_cypher(query)

    def save_statement(self, statement: dict[str, Any]) -> str:
        """Enregistre un énoncé d'architecture avec validation stricte du prédicat."""
        predicate = statement.get("predicate", "")
        if predicate not in ALLOWED_PREDICATES:
            raise ValueError(
                f"Prédicat non autorisé '{predicate}'. La liste contrôlée autorise uniquement: {ALLOWED_PREDICATES}"
            )

        s_id = statement.get("id") or f"S-{int(datetime.now().timestamp() * 1000)}"
        engagement = str(statement.get("engagement", "demo-2026")).replace("'", "''")
        section = str(statement.get("section", "general")).replace("'", "''")
        pred_esc = predicate.replace("'", "''")
        value_esc = str(statement.get("value", "")).replace("'", "''")
        unit_esc = str(statement.get("unit", "")).replace("'", "''")
        author_esc = str(statement.get("author", "unknown")).replace("'", "''")
        role_esc = str(statement.get("role", "architect")).replace("'", "''")
        confidence_esc = str(statement.get("confidence", "verified")).replace("'", "''")
        verbatim_esc = str(statement.get("verbatim", "")).replace("'", "''")
        created_at = str(statement.get("created_at", datetime.now().isoformat())).replace("'", "''")
        status = str(statement.get("status", "active")).replace("'", "''")

        query = f"""
        MERGE (s:Statement {{id: '{s_id}'}})
        SET s.engagement = '{engagement}',
            s.section = '{section}',
            s.predicate = '{pred_esc}',
            s.value = '{value_esc}',
            s.unit = '{unit_esc}',
            s.author = '{author_esc}',
            s.role = '{role_esc}',
            s.confidence = '{confidence_esc}',
            s.verbatim = '{verbatim_esc}',
            s.created_at = '{created_at}',
            s.status = '{status}';
        """
        self.db_client.execute_cypher(query)

        # Relations ABOUT, ANSWERS, BASED_ON
        subject_name = statement.get("subject")
        if subject_name:
            self.save_subject(subject_name)
            sub_esc = subject_name.replace("'", "''")
            self.db_client.execute_cypher(
                f"MATCH (st:Statement {{id: '{s_id}'}}), (sub:Subject {{name: '{sub_esc}'}}) MERGE (st)-[:ABOUT]->(sub);"
            )

        question_id = statement.get("question_id")
        if question_id:
            self.db_client.execute_cypher(
                f"MATCH (st:Statement {{id: '{s_id}'}}), (q:Question {{id: '{question_id}'}}) MERGE (st)-[:ANSWERS]->(q);"
            )

        based_on_asset = statement.get("based_on")
        if based_on_asset:
            asset_esc = based_on_asset.replace("'", "''")
            self.db_client.execute_cypher(
                f"MATCH (st:Statement {{id: '{s_id}'}}), (a:Asset {{id: '{asset_esc}'}}) MERGE (st)-[:BASED_ON]->(a);"
            )

        return s_id

    def save_conflict(self, conflict: dict[str, Any], statement_ids: list[str]) -> str:
        """Crée un nœud de conflit opposant plusieurs énoncés sans les écraser."""
        c_id = conflict.get("id") or f"C-{int(datetime.now().timestamp() * 1000)}"
        kind = str(conflict.get("kind", "contradiction")).replace("'", "''")
        detail = str(conflict.get("detail", "")).replace("'", "''")
        status = str(conflict.get("status", "open")).replace("'", "''")

        query = f"""
        MERGE (c:Conflict {{id: '{c_id}'}})
        SET c.kind = '{kind}',
            c.detail = '{detail}',
            c.status = '{status}',
            c.resolution = '',
            c.arbitrated_by = '';
        """
        self.db_client.execute_cypher(query)

        for s_id in statement_ids:
            s_esc = s_id.replace("'", "''")
            self.db_client.execute_cypher(
                f"MATCH (c:Conflict {{id: '{c_id}'}}), (st:Statement {{id: '{s_esc}'}}) MERGE (c)-[:INVOLVES]->(st);"
            )

        return c_id

    def arbitrate_conflict(
        self, conflict_id: str, keep_statement_id: str, reason: str, arbitrated_by: str
    ) -> None:
        """Arbitre un conflit (réservé à l'architecte en chef). Passe les énoncés perdants à 'superseded'."""
        reason_esc = reason.replace("'", "''")
        by_esc = arbitrated_by.replace("'", "''")

        # 1. Marquer le conflit comme arbitré
        self.db_client.execute_cypher(
            f"MATCH (c:Conflict {{id: '{conflict_id}'}}) SET c.status = 'arbitrated', c.resolution = '{reason_esc}', c.arbitrated_by = '{by_esc}';"
        )

        # 2. Récupérer tous les énoncés impliqués
        inv_query = f"MATCH (c:Conflict {{id: '{conflict_id}'}})-[:INVOLVES]->(st:Statement) RETURN st.id as id;"
        rows = self.db_client.execute_cypher(inv_query)

        # 3. Passer à 'superseded' les énoncés perdants
        for r in rows:
            s_id = r.get("id")
            if s_id and s_id != keep_statement_id:
                self.db_client.execute_cypher(
                    f"MATCH (st:Statement {{id: '{s_id}'}}) SET st.status = 'superseded';"
                )

    def get_question(self, question_id: str) -> dict[str, Any] | None:
        """Récupère une question par son identifiant."""
        query = f"MATCH (q:Question {{id: '{question_id}'}}) RETURN q.id as id, q.engagement as engagement, q.section as section, q.question as question, q.why_it_matters as why_it_matters, q.expected_shape as expected_shape, q.routed_to as routed_to, q.status as status;"
        res = self.db_client.execute_cypher(query)
        return res[0] if res and "error" not in res[0] else None

    def get_active_statements(self, engagement: str) -> list[dict[str, Any]]:
        """Récupère tous les énoncés actifs d'un engagement."""
        query = f"MATCH (s:Statement {{engagement: '{engagement}', status: 'active'}}) RETURN s.id as id, s.section as section, s.predicate as predicate, s.value as value, s.unit as unit, s.author as author, s.role as role, s.confidence as confidence, s.verbatim as verbatim;"
        return self.db_client.execute_cypher(query)

    def get_conflicts(self, engagement: str, status: str = "open") -> list[dict[str, Any]]:
        """Récupère les conflits ouverts pour un engagement."""
        query = f"MATCH (c:Conflict {{status: '{status}'}}) RETURN c.id as id, c.kind as kind, c.detail as detail, c.status as status, c.resolution as resolution, c.arbitrated_by as arbitrated_by;"
        return self.db_client.execute_cypher(query)
