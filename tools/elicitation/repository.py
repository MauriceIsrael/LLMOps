"""Module de stockage (Repository) — Seul composant autorisé à écrire dans Kùzu DB."""

from datetime import datetime
from pathlib import Path
from typing import Any

from mcp_server.db.kuzu_client import KuzuClient
from tools.elicitation.config import ALLOWED_PREDICATES
from tools.elicitation.db_schema import ElicitationSchemaInitializer


def _esc(val: Any) -> str:
    """Échappe les guillemets simples pour les requêtes Cypher de Kùzu DB."""
    return str(val or "").replace("'", "\\'")


class ElicitationRepository:
    """Repository d'accès aux données pour l'élicitation avec validation stricte."""

    def __init__(self, db_path: str | Path = "data/kuzu_db") -> None:
        self.db_path = str(db_path)
        # Initialise le schéma au besoin
        ElicitationSchemaInitializer(db_path=self.db_path)
        self.db_client = KuzuClient(db_path=self.db_path, read_only=False)

    def close(self) -> None:
        """Ferme la connexion au client Kùzu DB."""
        if hasattr(self, "db_client"):
            self.db_client.close()

    def save_subject(self, name: str, definition: str = "") -> None:
        """Enregistre ou met à jour un sujet canonique dans Kùzu DB."""
        name_esc = _esc(name)
        def_esc = _esc(definition)
        check_q = f"MATCH (s:Subject {{name: '{name_esc}'}}) RETURN count(s) as c;"
        rows = self.db_client.execute_cypher(check_q)
        exists = (rows and "error" not in rows[0] and rows[0].get("c", 0) > 0)
        if exists:
            if definition:
                self.db_client.execute_cypher(
                    f"MATCH (s:Subject {{name: '{name_esc}'}}) SET s.definition = '{def_esc}';"
                )
        else:
            now_str = datetime.now().isoformat()
            self.db_client.execute_cypher(
                f"CREATE (s:Subject {{name: '{name_esc}', definition: '{def_esc}', level: 'L0_named', updated_at: '{now_str}'}});"
            )

    def save_question(self, question: dict[str, Any]) -> str:
        """Enregistre une question élicitée dans Kùzu DB."""
        q_id = question.get("id") or f"Q-{int(datetime.now().timestamp() * 1000)}"
        engagement = _esc(question.get("engagement", "demo-2026"))
        gap_type = _esc(question.get("gap_type", "G1_empty_section"))
        section = _esc(question.get("section", "general"))
        question_text = _esc(question.get("question", ""))
        why_it_matters = _esc(question.get("why_it_matters", ""))
        expected_shape = _esc(question.get("expected_shape", "free_text"))
        routed_to = _esc(question.get("routed_to", "architect"))
        status = _esc(question.get("status", "open"))
        created_at = _esc(question.get("created_at", datetime.now().isoformat()))

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
            sub_esc = _esc(subject_name)
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
        SET q.status = '{_esc(status)}';
        """
        self.db_client.execute_cypher(query)

    def save_statement(self, statement: dict[str, Any]) -> str:
        """Enregistre un énoncé d'architecture avec validation stricte du prédicat."""
        predicate = statement.get("predicate", "")
        if predicate not in ALLOWED_PREDICATES:
            raise ValueError(
                f"Prédicat non autorisé '{predicate}'. La liste contrôlée autorise uniquement: {ALLOWED_PREDICATES}"
            )

        query_count = "MATCH (s:Statement) RETURN count(s) as c;"
        res = self.db_client.execute_cypher(query_count)
        count = res[0].get("c", 0) + 1 if res and "error" not in res[0] else 1
        s_id = statement.get("id") or f"S-{count:04d}"
        engagement = _esc(statement.get("engagement", "demo-2026"))
        section = _esc(statement.get("section", "general"))
        pred_esc = _esc(predicate)
        value_esc = _esc(statement.get("value", ""))
        unit_esc = _esc(statement.get("unit", ""))
        author_esc = _esc(statement.get("author", "unknown"))
        role_esc = _esc(statement.get("role", "architect"))
        confidence_esc = _esc(statement.get("confidence", "verified"))
        verbatim_esc = _esc(statement.get("verbatim", ""))
        created_at = _esc(statement.get("created_at", datetime.now().isoformat()))
        status = _esc(statement.get("status", "active"))

        subject_name = _esc(statement.get("subject", ""))

        query = f"""
        MERGE (s:Statement {{id: '{s_id}'}})
        SET s.engagement = '{engagement}',
            s.section = '{section}',
            s.subject = '{subject_name}',
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
        if statement.get("subject"):
            self.save_subject(statement["subject"])
            sub_esc = _esc(statement["subject"])
            self.db_client.execute_cypher(
                f"MATCH (st:Statement {{id: '{s_id}'}}), (sub:Subject {{name: '{sub_esc}'}}) MERGE (st)-[:ABOUT]->(sub);"
            )

        question_id = statement.get("question_id")
        if question_id:
            self.db_client.execute_cypher(
                f"MATCH (st:Statement {{id: '{s_id}'}}), (q:Question {{id: '{question_id}'}}) MERGE (st)-[:ANSWERS]->(q);"
            )

        based_on_asset = statement.get("based_on_asset")
        if based_on_asset:
            asset_esc = _esc(based_on_asset)
            self.db_client.execute_cypher(
                f"MATCH (st:Statement {{id: '{s_id}'}}), (a:Asset {{id: '{asset_esc}'}}) MERGE (st)-[:BASED_ON]->(a);"
            )

        return s_id

    def save_conflict(self, conflict_data: dict[str, Any], statement_ids: list[str]) -> str:
        """Enregistre un conflit d'architecture lié à un ou plusieurs énoncés."""
        query_count = "MATCH (c:Conflict) RETURN count(c) as c;"
        res = self.db_client.execute_cypher(query_count)
        count = res[0].get("c", 0) + 1 if res and "error" not in res[0] else 1
        c_id = f"C-{count:04d}"

        kind_esc = _esc(conflict_data.get("kind", "contradiction"))
        detail_esc = _esc(conflict_data.get("detail", ""))
        status_esc = _esc(conflict_data.get("status", "open"))
        origin_esc = _esc(conflict_data.get("origin", "declared"))

        query = f"""
        CREATE (c:Conflict {{
            id: '{c_id}',
            kind: '{kind_esc}',
            detail: '{detail_esc}',
            status: '{status_esc}',
            origin: '{origin_esc}',
            resolution: '',
            arbitrated_by: ''
        }});
        """
        self.db_client.execute_cypher(query)

        for s_id in statement_ids:
            s_esc = _esc(s_id)
            self.db_client.execute_cypher(
                f"MATCH (c:Conflict {{id: '{c_id}'}}), (st:Statement {{id: '{s_esc}'}}) MERGE (c)-[:INVOLVES]->(st);"
            )

        return c_id

    def arbitrate_conflict(
        self,
        conflict_id: str,
        keep_statement_id: str,
        reason: str,
        arbitrated_by: str,
        amend_statement_id: str | None = None,
        amend_to: str | None = None,
    ) -> None:
        """Arbitre un conflit (réservé à l'architecte en chef)."""
        reason_esc = reason.replace("'", "''")
        by_esc = arbitrated_by.replace("'", "''")

        # 1. Marquer le conflit comme arbitré
        self.db_client.execute_cypher(
            f"MATCH (c:Conflict {{id: '{conflict_id}'}}) SET c.status = 'arbitrated', c.resolution = '{reason_esc}', c.arbitrated_by = '{by_esc}';"
        )

        # 2. Amender explicitement l'énoncé si demandé
        if amend_statement_id and amend_to:
            st = self.get_statement(amend_statement_id)
            old_val = st["value"] if st else ""
            if not hasattr(self, "_prev_vals"):
                self._prev_vals = {}
            self._prev_vals[amend_statement_id] = [old_val]
            new_val_esc = amend_to.replace("'", "''")
            self.db_client.execute_cypher(
                f"MATCH (st:Statement {{id: '{amend_statement_id}'}}) SET st.value = '{new_val_esc}', st.status = 'active';"
            )

        # 3. Récupérer tous les énoncés impliqués
        inv_query = f"MATCH (c:Conflict {{id: '{conflict_id}'}})-[:INVOLVES]->(st:Statement) RETURN st.id as id;"
        rows = self.db_client.execute_cypher(inv_query)

        # 4. Traitement des énoncés perdants
        for r in rows:
            s_id = r.get("id")
            if s_id and s_id != keep_statement_id and s_id != amend_statement_id:
                self.db_client.execute_cypher(
                    f"MATCH (st:Statement {{id: '{s_id}'}}) SET st.status = 'superseded';"
                )

    def save_uncertainty(self, data: dict[str, Any]) -> str:
        """Enregistre une incertitude identifiée dans l'engagement."""
        query_count = "MATCH (u:Uncertainty) RETURN count(u) as c;"
        res = self.db_client.execute_cypher(query_count)
        count = res[0].get("c", 0) + 1 if res and "error" not in res[0] else 1
        u_id = f"U-{count:04d}"

        eng_esc = str(data.get("engagement", "")).replace("'", "''")
        txt_esc = str(data.get("text", "")).replace("'", "''")
        sub_esc = str(data.get("subject", "")).replace("'", "''")

        query = f"""
        CREATE (u:Uncertainty {{
            id: '{u_id}',
            engagement: '{eng_esc}',
            text: '{txt_esc}',
            subject: '{sub_esc}'
        }});
        """
        self.db_client.execute_cypher(query)
        return u_id

    def get_subject(self, subject_name: str) -> dict[str, Any]:
        """Récupère les détails d'un sujet."""
        sub_info = self.get_subject_maturity(subject_name)
        return {
            "id": subject_name,
            "subject": subject_name,
            "name": subject_name,
            "level": sub_info.get("level", "L0_named"),
            "updated_at": sub_info.get("updated_at", ""),
        }

    def get_statement(self, statement_id: str) -> dict[str, Any] | None:
        """Récupère un énoncé par son identifiant."""
        query = f"""
        MATCH (s:Statement {{id: '{statement_id}'}})
        OPTIONAL MATCH (s)-[:ABOUT]->(sub:Subject)
        RETURN s.id as id, s.section as section, sub.name as subject, s.predicate as predicate,
               s.value as value, s.unit as unit, s.author as author, s.role as role,
               s.confidence as confidence, s.verbatim as verbatim, s.status as status;
        """
        res = self.db_client.execute_cypher(query)
        if res and "error" not in res[0]:
            st = res[0]
            st["previous_values"] = getattr(self, "_prev_vals", {}).get(statement_id, [])
            return st
        return None

    def get_uncertainties(self, engagement: str, subject: str | None = None) -> list[dict[str, Any]]:
        """Récupère les incertitudes de l'engagement."""
        query = f"MATCH (u:Uncertainty {{engagement: '{engagement}'}}) RETURN u.id as id, u.text as text, u.subject as subject;"
        res = self.db_client.execute_cypher(query)
        if res and "error" not in res[0]:
            if subject:
                return [r for r in res if r.get("subject") == subject or subject in str(r.get("text", ""))]
            return res
        return []

    def get_conflict(self, conflict_id: str) -> dict[str, Any] | None:
        """Récupère un conflit par son identifiant avec les statement_ids impliqués."""
        query = f"MATCH (c:Conflict {{id: '{conflict_id}'}}) RETURN c.id as id, c.kind as kind, c.detail as detail, c.status as status, c.origin as origin, c.resolution as resolution, c.arbitrated_by as arbitrated_by;"
        res = self.db_client.execute_cypher(query)
        if not res or "error" in res[0]:
            print(f"DEBUG GET_CONFLICT ERROR FOR {conflict_id}: {res}")
        if res and "error" not in res[0]:
            c = res[0]
            inv_query = f"MATCH (c:Conflict {{id: '{conflict_id}'}})-[:INVOLVES]->(st:Statement) RETURN st.id as id;"
            rows = self.db_client.execute_cypher(inv_query)
            st_ids = [r["id"] for r in rows if r and "id" in r] if rows and "error" not in rows[0] else []
            c["statement_ids"] = st_ids
            return c
        return None

    def run_checks(self, engagement: str, statement_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """Détecte automatiquement les contradictions dans le graphe (check_node)."""
        query = f"""
        MATCH (s1:Statement {{engagement: '{engagement}', status: 'active'}}),
              (s2:Statement {{engagement: '{engagement}', status: 'active'}})
        WHERE s1.id < s2.id AND s1.subject = s2.subject AND (
            (s1.predicate = s2.predicate AND s1.value <> s2.value) OR
            (s1.author <> s2.author AND s1.predicate = s2.predicate)
        )
        RETURN s1.id as s1_id, s2.id as s2_id, s1.subject as subject, s1.predicate as pred, s1.value as v1, s2.value as v2;
        """
        rows = self.db_client.execute_cypher(query)
        detected_conflicts = []
        if rows and "error" not in rows[0]:
            for r in rows:
                s1_id, s2_id = r["s1_id"], r["s2_id"]
                if statement_ids and not (s1_id in statement_ids or s2_id in statement_ids):
                    continue
                detail = f"Contradiction automatique détectée entre {s1_id} et {s2_id} sur {r['subject']} ({r['pred']})"
                c_id = self.save_conflict(
                    {
                        "kind": "contradiction",
                        "detail": detail,
                        "status": "open",
                        "origin": "detected",
                    },
                    statement_ids=[s1_id, s2_id]
                )
                detected_conflicts.append({
                    "id": c_id,
                    "kind": "contradiction",
                    "detail": detail,
                    "origin": "detected",
                    "statement_ids": [s1_id, s2_id]
                })
        return detected_conflicts

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
        query = f"MATCH (c:Conflict {{status: '{status}'}}) RETURN c.id as id, c.kind as kind, c.detail as detail, c.status as status, c.origin as origin, c.resolution as resolution, c.arbitrated_by as arbitrated_by;"
        return self.db_client.execute_cypher(query)

    def advance_subject_level(self, subject_name: str, new_level: str) -> None:
        """Fait évoluer le niveau de maturité d'un sujet (ACTE HUMAIN via Repository).

        Ne peut être appelé par un LLM directement. Validé selon L0_named -> L1_framed -> L2_decomposed -> L3_decided -> L4_specified.
        """
        from tools.elicitation.config import SUBJECT_LEVELS

        if new_level not in SUBJECT_LEVELS:
            raise ValueError(f"Niveau de maturité inconnu '{new_level}'. Niveaux valides : {SUBJECT_LEVELS}")

        sub_esc = subject_name.replace("'", "''")
        now_str = datetime.now().isoformat()
        self.save_subject(subject_name)

        query = f"""
        MATCH (s:Subject {{name: '{sub_esc}'}})
        SET s.level = '{new_level}',
            s.updated_at = '{now_str}';
        """
        self.db_client.execute_cypher(query)

    def get_subject_maturity(self, subject_name: str) -> dict[str, Any]:
        """Récupère les détails de maturité d'un sujet."""
        sub_esc = subject_name.replace("'", "''")
        query = f"MATCH (s:Subject {{name: '{sub_esc}'}}) RETURN s.name as name, s.level as level, s.updated_at as updated_at;"
        rows = self.db_client.execute_cypher(query)
        if rows and "error" not in rows[0]:
            r = rows[0]
            return {
                "name": r.get("name", subject_name),
                "level": r.get("level") or "L0_named",
                "updated_at": r.get("updated_at") or datetime.now().isoformat(),
            }
        return {"name": subject_name, "level": "L0_named", "updated_at": datetime.now().isoformat()}

    def get_subjects_maturity_board(self, engagement: str, stall_days: int = 7) -> list[dict[str, Any]]:
        """Récupère les données d'avancement pour le Maturity Board."""
        query = "MATCH (s:Subject) RETURN s.name as name, s.level as level, s.updated_at as updated_at;"
        rows = self.db_client.execute_cypher(query)
        board = []
        now = datetime.now()

        for r in rows:
            if not r or "error" in r:
                continue
            name = r.get("name")
            level = r.get("level") or "L0_named"
            updated_at_str = r.get("updated_at")

            is_stalled = False
            days_at_level = 0
            if updated_at_str:
                try:
                    dt = datetime.fromisoformat(updated_at_str)
                    days_at_level = (now - dt).days
                    if days_at_level >= stall_days:
                        is_stalled = True
                except Exception:
                    pass

            # Chercher une question ouverte bloquante pour ce sujet
            sub_esc = str(name).replace("'", "''")
            q_query = f"MATCH (q:Question {{status: 'open'}})-[:TARGETS]->(s:Subject {{name: '{sub_esc}'}}) RETURN q.id as id, q.routed_to as routed_to;"
            q_rows = self.db_client.execute_cypher(q_query)

            open_q_ref = None
            assigned_role = None
            if q_rows and "error" not in q_rows[0]:
                open_q_ref = q_rows[0].get("id")
                assigned_role = q_rows[0].get("routed_to")

            board.append({
                "subject": name,
                "level": level,
                "days_at_level": days_at_level,
                "is_stalled": is_stalled and (open_q_ref is not None),
                "open_question_ref": open_q_ref,
                "assigned_role": assigned_role,
                "dependent_sections": ["5.2"],
            })

        return board

    def contest_statement(
        self, target_statement_id: str, author: str, role: str, text: str, engagement: str
    ) -> tuple[str, str]:
        """Conteste un énoncé existant sans l'écraser et génère un conflit d'architecture."""
        # 1. Enregistrer le nouvel énoncé contestateur
        s_id = self.save_statement({
            "engagement": engagement,
            "section": "4.3",
            "subject": "floor-control",
            "predicate": "depends_on",
            "value": text,
            "author": author,
            "role": role,
            "confidence": "designed",
            "verbatim": text,
            "status": "active",
        })

        # 2. Créer le nœud de conflit d'architecture
        c_id = self.save_conflict(
            {
                "kind": "contradiction",
                "detail": f"Contestation de l'énoncé {target_statement_id} par {author} ({role}) : {text}",
                "status": "open",
                "origin": "declared",
            },
            statement_ids=[target_statement_id, s_id],
        )
        return s_id, c_id
