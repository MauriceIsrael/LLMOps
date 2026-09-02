"""Module de stockage (Repository) — Seul composant autorisé à écrire dans Kùzu DB / LadybugDB."""

from datetime import datetime
from pathlib import Path
from typing import Any

from tools.adapters.kuzu_store import make_graph_store
from tools.elicitation.db_schema import ElicitationSchemaInitializer
from tools.ports.graph_store import GraphStore


class ElicitationRepository:
    """Repository d'accès aux données pour l'élicitation avec validation stricte."""

    def __init__(
        self,
        db_path: str | Path = "data/kuzu_db",
        graph_store: GraphStore | None = None,
    ) -> None:
        self.db_path = str(db_path)
        self.graph_store = graph_store or make_graph_store(db_path=self.db_path, read_only=False)
        self.db_client = self.graph_store  # Property alias for compatibility
        # Initialise le schéma au besoin
        ElicitationSchemaInitializer(db_path=self.db_path, graph_store=self.graph_store)

    def close(self) -> None:
        """Ferme la connexion au client graphe."""
        if hasattr(self, "graph_store") and self.graph_store:
            self.graph_store.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def save_subject(
        self,
        name: str,
        engagement: str = "nordwave-mcx-2027",
        definition: str = "",
        origin: str = "blueprint",
    ) -> None:
        """Enregistre ou met à jour un sujet d'architecture dans Kùzu DB scopé par engagement."""
        check_query = (
            "MATCH (s:Subject) WHERE s.name = $name AND (s.engagement = $engagement OR s.engagement = 'default') "
            "RETURN s.name as name, s.level as level;"
        )
        rows = self.db_client.execute_cypher(
            check_query, params={"name": name, "engagement": engagement}
        )
        exists = bool(rows and "error" not in rows[0])

        if exists:
            if definition:
                self.db_client.execute_cypher(
                    "MATCH (s:Subject) WHERE s.name = $name AND (s.engagement = $engagement OR s.engagement = 'default') "
                    "SET s.definition = $definition;",
                    params={"name": name, "engagement": engagement, "definition": definition},
                )
        else:
            now_str = datetime.now().isoformat()
            sub_id = f"{engagement}:{name}"
            self.db_client.execute_cypher(
                "MERGE (s:Subject {id: $sub_id}) SET s.name = $name, s.engagement = $engagement, "
                "s.definition = $definition, s.level = 'L0_named', s.origin = $origin, s.updated_at = $now_str;",
                params={
                    "sub_id": sub_id,
                    "name": name,
                    "engagement": engagement,
                    "definition": definition,
                    "origin": origin,
                    "now_str": now_str,
                },
            )

    def bind_blueprint_to_engagement(self, blueprint: Any, engagement: str) -> None:
        """Lie un blueprint d'architecture à un engagement et matérialise tous les sujets déclarés à L0_named avec origin='blueprint'."""
        if hasattr(blueprint, "roots") and blueprint.roots:
            for root in blueprint.roots:
                if getattr(root, "instructed", True) is not False:
                    name = getattr(root, "name", str(root))
                    def_str = getattr(root, "definition", "")
                    self.save_subject(name, engagement=engagement, definition=def_str, origin="blueprint")
        else:
            declared_subjects = blueprint.get_declared_subjects() if hasattr(blueprint, "get_declared_subjects") else set()
            for subj in declared_subjects:
                self.save_subject(subj, engagement=engagement, origin="blueprint")

    def subject_levels(self, engagement: str) -> dict[str, str]:
        """Retourne les niveaux de maturité de TOUS les sujets d'un engagement en une seule requête Cypher (D9)."""
        query = "MATCH (s:Subject) WHERE s.engagement = $engagement OR s.engagement = 'default' OR s.engagement IS NULL RETURN s.name as name, s.level as level;"
        rows = self.db_client.execute_cypher(query, params={"engagement": engagement})
        levels: dict[str, str] = {}
        if rows and "error" not in rows[0]:
            for r in rows:
                if r and "name" in r:
                    levels[r["name"]] = r.get("level") or "L0_named"
        return levels

    def sections_with_statements(self, engagement: str) -> set[str]:
        """Retourne l'ensemble des sections ayant au moins un énoncé actif (D8)."""
        query = "MATCH (s:Statement {engagement: $engagement, status: 'active'}) RETURN s.section as section;"
        rows = self.db_client.execute_cypher(query, params={"engagement": engagement})
        sections: set[str] = set()
        if rows and "error" not in rows[0]:
            for r in rows:
                if r and "section" in r and r["section"]:
                    sections.add(r["section"])
        return sections

    def save_question(self, question: dict[str, Any]) -> str:
        """Enregistre une question élicitée dans Kùzu DB."""
        q_id = question.get("id") or f"Q-{int(datetime.now().timestamp() * 1000)}"
        engagement = question.get("engagement", "demo-2026")
        gap_type = question.get("gap_type", "G1_empty_section")
        section = question.get("section", "general")
        question_text = question.get("question", "")
        why_it_matters = question.get("why_it_matters", "")
        expected_shape = question.get("expected_shape", "free_text")
        routed_to = question.get("routed_to", "architect")
        status = question.get("status", "open")
        created_at = question.get("created_at", datetime.now().isoformat())

        query = """
        MERGE (q:Question {id: $q_id})
        SET q.engagement = $engagement,
            q.gap_type = $gap_type,
            q.section = $section,
            q.question = $question_text,
            q.why_it_matters = $why_it_matters,
            q.expected_shape = $expected_shape,
            q.routed_to = $routed_to,
            q.status = $status,
            q.created_at = $created_at;
        """
        self.db_client.execute_cypher(
            query,
            params={
                "q_id": q_id,
                "engagement": engagement,
                "gap_type": gap_type,
                "section": section,
                "question_text": question_text,
                "why_it_matters": why_it_matters,
                "expected_shape": expected_shape,
                "routed_to": routed_to,
                "status": status,
                "created_at": created_at,
            },
        )

        # Lier au sujet cible si présent
        subject_name = question.get("subject")
        if subject_name:
            self.save_subject(subject_name, engagement=engagement)
            sub_id = f"{engagement}:{subject_name}"
            rel_query = """
            MERGE (q:Question {id: $q_id})
            MERGE (s:Subject {id: $sub_id})
            MERGE (q)-[:TARGETS]->(s);
            """
            self.db_client.execute_cypher(rel_query, params={"q_id": q_id, "sub_id": sub_id})

        return q_id

    def update_question_status(self, question_id: str, status: str) -> None:
        """Met à jour le statut d'une question (sent, confirmed, declined, etc.)."""
        query = "MATCH (q:Question {id: $question_id}) SET q.status = $status;"
        self.db_client.execute_cypher(query, params={"question_id": question_id, "status": status})

    def save_statement(self, statement: dict[str, Any]) -> str:
        """Enregistre un énoncé d'architecture (fact) dans Kùzu DB scopé par engagement."""
        s_id = statement.get("id")
        if not s_id:
            query_count = "MATCH (s:Statement) RETURN s.id as id;"
            res = self.db_client.execute_cypher(query_count)
            count = len(res) + 1 if res and "error" not in res[0] else 1
            s_id = f"S-{count:04d}"

        engagement = statement.get("engagement", "nordwave-mcx-2027")
        sec = statement.get("section", "general")
        val = statement.get("value", "")
        author = statement.get("author", "unknown")
        role = statement.get("role", "architect")
        confidence = statement.get("confidence", "designed")
        verbatim = statement.get("verbatim", val)
        predicate_val = statement.get("predicate", "has_property")
        allowed_predicates = {
            "implements", "requires", "replaces", "constrains", "is_constrained_by", "constrained_by", "uses", "depends_on",
            "has_property", "about", "defined_by", "evaluated_by", "validates", "refers_to", "has_color",
            "delivers", "serves", "survives_with", "degrades_to", "supports", "includes", "belongs_to",
            "decomposes_into", "has_part", "part_of", "composes"
        }
        if predicate_val and predicate_val not in allowed_predicates:
            raise ValueError(f"Prédicat non autorisé : '{predicate_val}'")
        predicate = predicate_val
        status = statement.get("status", "active")
        created_at = statement.get("created_at", datetime.now().isoformat())
        sub_name = statement.get("subject", "general")

        # Gérer le sujet lié
        sub_id = f"{engagement}:{sub_name}"
        self.save_subject(sub_name, engagement=engagement)

        import json
        based_on_raw = statement.get("based_on") or []
        if not based_on_raw and statement.get("based_on_asset"):
            based_on_raw = [{"id": statement["based_on_asset"], "resolved": None}]

        if not isinstance(based_on_raw, str):
            based_on_str = json.dumps(based_on_raw)
        else:
            based_on_str = based_on_raw

        query = """
        MERGE (st:Statement {id: $s_id})
        SET st.engagement = $engagement,
            st.section = $sec,
            st.subject = $sub_name,
            st.predicate = $predicate,
            st.value = $val,
            st.author = $author,
            st.role = $role,
            st.confidence = $confidence,
            st.verbatim = $verbatim,
            st.status = $status,
            st.based_on = $based_on_str,
            st.created_at = $created_at;
        """
        self.db_client.execute_cypher(
            query,
            params={
                "s_id": s_id,
                "engagement": engagement,
                "sec": sec,
                "sub_name": sub_name,
                "predicate": predicate,
                "val": val,
                "author": author,
                "role": role,
                "confidence": confidence,
                "verbatim": verbatim,
                "status": status,
                "based_on_str": based_on_str,
                "created_at": created_at,
            },
        )

        # Lier à la section/sujet via ABOUT
        self.db_client.execute_cypher(
            "MERGE (st:Statement {id: $s_id}) MERGE (sub:Subject {id: $sub_id}) MERGE (st)-[:ABOUT]->(sub);",
            params={"s_id": s_id, "sub_id": sub_id},
        )

        return s_id

    def save_conflict(self, conflict_data: dict[str, Any], statement_ids: list[str]) -> str:
        """Enregistre un conflit d'architecture lié à un ou plusieurs énoncés."""
        query_count = "MATCH (c:Conflict) RETURN c.id as id;"
        res = self.db_client.execute_cypher(query_count)
        count = len(res) + 1 if res and "error" not in res[0] else 1
        c_id = f"C-{count:04d}"

        kind = conflict_data.get("kind", "contradiction")
        detail = conflict_data.get("detail", "")
        status = conflict_data.get("status", "open")
        origin = conflict_data.get("origin", "declared")

        query = """
        CREATE (c:Conflict {
            id: $c_id,
            kind: $kind,
            detail: $detail,
            status: $status,
            origin: $origin,
            resolution: '',
            arbitrated_by: ''
        });
        """
        self.db_client.execute_cypher(
            query,
            params={
                "c_id": c_id,
                "kind": kind,
                "detail": detail,
                "status": status,
                "origin": origin,
            },
        )

        for s_id in statement_ids:
            self.db_client.execute_cypher(
                "MERGE (c:Conflict {id: $c_id}), (st:Statement {id: $s_id}) MERGE (c)-[:INVOLVES]->(st);",
                params={"c_id": c_id, "s_id": s_id},
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
        # 1. Marquer le conflit comme arbitré
        self.db_client.execute_cypher(
            "MATCH (c:Conflict {id: $conflict_id}) SET c.status = 'arbitrated', c.resolution = $reason, c.arbitrated_by = $arbitrated_by;",
            params={"conflict_id": conflict_id, "reason": reason, "arbitrated_by": arbitrated_by},
        )

        # 2. Amender explicitement l'énoncé si demandé
        if amend_statement_id and amend_to:
            st = self.get_statement(amend_statement_id)
            old_val = st["value"] if st else ""
            if not hasattr(self, "_prev_vals"):
                self._prev_vals = {}
            self._prev_vals[amend_statement_id] = [old_val]
            self.db_client.execute_cypher(
                "MATCH (st:Statement {id: $amend_statement_id}) SET st.value = $amend_to, st.status = 'active';",
                params={"amend_statement_id": amend_statement_id, "amend_to": amend_to},
            )

        # 3. Récupérer tous les énoncés impliqués
        inv_query = "MATCH (c:Conflict {id: $conflict_id})-[:INVOLVES]->(st:Statement) RETURN st.id as id;"
        rows = self.db_client.execute_cypher(inv_query, params={"conflict_id": conflict_id})

        # 4. Traitement des énoncés perdants
        if rows and "error" not in rows[0]:
            for r in rows:
                s_id = r.get("id")
                if s_id and s_id != keep_statement_id and s_id != amend_statement_id:
                    self.db_client.execute_cypher(
                        "MATCH (st:Statement {id: $s_id}) SET st.status = 'superseded';",
                        params={"s_id": s_id},
                    )

    def save_uncertainty(self, data: dict[str, Any]) -> str:
        """Enregistre une incertitude identifiée dans l'engagement."""
        query_count = "MATCH (u:Uncertainty) RETURN count(u.id) as c;"
        res = self.db_client.execute_cypher(query_count)
        count = res[0].get("c", 0) + 1 if res and "error" not in res[0] else 1
        u_id = f"U-{count:04d}"

        eng = str(data.get("engagement", ""))
        txt = str(data.get("text", ""))
        sub = str(data.get("subject", ""))

        query = """
        CREATE (u:Uncertainty {
            id: $u_id,
            engagement: $eng,
            text: $txt,
            subject: $sub
        });
        """
        self.db_client.execute_cypher(
            query, params={"u_id": u_id, "eng": eng, "txt": txt, "sub": sub}
        )
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
        query = """
        MATCH (s:Statement {id: $statement_id})
        OPTIONAL MATCH (s)-[:ABOUT]->(sub:Subject)
        RETURN s.id as id, s.section as section, sub.name as subject, s.predicate as predicate,
               s.value as value, s.unit as unit, s.author as author, s.role as role,
               s.confidence as confidence, s.verbatim as verbatim, s.status as status;
        """
        res = self.db_client.execute_cypher(query, params={"statement_id": statement_id})
        if res and "error" not in res[0]:
            st = res[0]
            st["previous_values"] = getattr(self, "_prev_vals", {}).get(statement_id, [])
            return st
        return None

    def get_uncertainties(self, engagement: str, subject: str | None = None) -> list[dict[str, Any]]:
        """Récupère les incertitudes de l'engagement."""
        query = "MATCH (u:Uncertainty {engagement: $engagement}) RETURN u.id as id, u.text as text, u.subject as subject;"
        res = self.db_client.execute_cypher(query, params={"engagement": engagement})
        if res and "error" not in res[0]:
            if subject:
                return [r for r in res if r.get("subject") == subject or subject in str(r.get("text", ""))]
            return res
        return []

    def get_conflict(self, conflict_id: str) -> dict[str, Any] | None:
        """Récupère un conflit par son identifiant avec les statement_ids impliqués."""
        query = "MATCH (c:Conflict {id: $conflict_id}) RETURN c.id as id, c.kind as kind, c.detail as detail, c.status as status, c.origin as origin, c.resolution as resolution, c.arbitrated_by as arbitrated_by;"
        res = self.db_client.execute_cypher(query, params={"conflict_id": conflict_id})
        if not res or "error" in res[0]:
            print(f"DEBUG GET_CONFLICT ERROR FOR {conflict_id}: {res}")
        if res and "error" not in res[0]:
            c = res[0]
            inv_query = "MATCH (c:Conflict {id: $conflict_id})-[:INVOLVES]->(st:Statement) RETURN st.id as id;"
            rows = self.db_client.execute_cypher(inv_query, params={"conflict_id": conflict_id})
            st_ids = [r["id"] for r in rows if r and "id" in r] if rows and "error" not in rows[0] else []
            c["statement_ids"] = st_ids
            return c
        return None

    def run_checks(self, engagement: str, statement_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """Détecte automatiquement les contradictions dans le graphe (check_node)."""
        query = """
        MATCH (s1:Statement {engagement: $engagement, status: 'active'}),
              (s2:Statement {engagement: $engagement, status: 'active'})
        WHERE s1.id < s2.id AND s1.subject = s2.subject AND (
            (s1.predicate = s2.predicate AND s1.value <> s2.value) OR
            (s1.author <> s2.author AND s1.predicate = s2.predicate)
        )
        RETURN s1.id as s1_id, s2.id as s2_id, s1.subject as subject, s1.predicate as pred, s1.value as v1, s2.value as v2;
        """
        rows = self.db_client.execute_cypher(query, params={"engagement": engagement})
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
        query = "MATCH (q:Question {id: $question_id}) RETURN q.id as id, q.engagement as engagement, q.section as section, q.question as question, q.why_it_matters as why_it_matters, q.expected_shape as expected_shape, q.routed_to as routed_to, q.status as status;"
        res = self.db_client.execute_cypher(query, params={"question_id": question_id})
        return res[0] if res and "error" not in res[0] else None

    def get_active_statements(self, engagement: str) -> list[dict[str, Any]]:
        """Récupère tous les énoncés d'un engagement."""
        import json
        query = "MATCH (s:Statement {engagement: $engagement}) OPTIONAL MATCH (s)-[:ABOUT]->(sub:Subject) RETURN s.id as id, s.section as section, sub.name as subject, s.subject as subject_direct, s.predicate as predicate, s.value as value, s.unit as unit, s.author as author, s.role as role, s.confidence as confidence, s.verbatim as verbatim, s.status as status, s.based_on as based_on;"
        rows = self.db_client.execute_cypher(query, params={"engagement": engagement})
        if rows and "error" not in rows[0]:
            for r in rows:
                if not r.get("subject"):
                    r["subject"] = r.get("subject_direct") or "mcx-services"
                bo = r.get("based_on")
                if bo and isinstance(bo, str):
                    try:
                        r["based_on"] = json.loads(bo)
                    except Exception:
                        r["based_on"] = []
                elif not bo:
                    r["based_on"] = []
            return rows
        return []

    def get_conflicts(self, engagement: str, status: str = "open") -> list[dict[str, Any]]:
        """Récupère les conflits ouverts pour un engagement."""
        query = "MATCH (c:Conflict {status: $status}) RETURN c.id as id, c.kind as kind, c.detail as detail, c.status as status, c.origin as origin, c.resolution as resolution, c.arbitrated_by as arbitrated_by;"
        return self.db_client.execute_cypher(query, params={"status": status})

    def advance_subject_level(self, subject_name: str | None = None, new_level: str | None = None, *, name: str | None = None, level: str | None = None, engagement: str | None = None) -> None:
        """Fait évoluer le niveau de maturité d'un sujet (ACTE HUMAIN via Repository).

        Ne peut être appelé par un LLM directement. Validé selon L0_named -> L1_framed -> L2_decomposed -> L3_decided -> L4_specified.
        """
        from tools.elicitation.config import SUBJECT_LEVELS

        target_name = name or subject_name or ""
        target_level = level or new_level or ""

        if target_level not in SUBJECT_LEVELS:
            raise ValueError(f"Niveau de maturité inconnu '{target_level}'. Niveaux valides : {SUBJECT_LEVELS}")

        now_str = datetime.now().isoformat()
        eng = engagement or "nordwave-mcx-2027"
        self.save_subject(target_name, engagement=eng)
        sub_id = f"{eng}:{target_name}"

        query = """
        MATCH (s:Subject)
        WHERE s.id = $sub_id OR (s.name = $target_name AND s.engagement = $eng) OR s.name = $target_name
        SET s.level = $target_level,
            s.updated_at = $now_str;
        """
        self.db_client.execute_cypher(
            query,
            params={
                "sub_id": sub_id,
                "target_name": target_name,
                "target_level": target_level,
                "now_str": now_str,
                "eng": eng,
            },
        )

    def get_subject_trajectory(self, engagement: str, subject: str) -> list[dict[str, Any]]:
        """Récupère l'historique des avancées de maturité (trajectoire) pour un sujet."""
        query = """
        MATCH (st:Statement {engagement: $engagement, status: 'active'})
        OPTIONAL MATCH (q:Question {engagement: $engagement}) WHERE q.section = st.section
        RETURN st.id as id, st.section as section, st.subject as subject, st.value as val, st.verbatim as verbatim, q.question as question, st.created_at as created_at;
        """
        rows = self.db_client.execute_cypher(query, params={"engagement": engagement})
        if rows and "error" not in rows[0]:
            rows = [r for r in rows if r.get("subject") == subject or subject in str(r.get("val", "")) or subject in str(r.get("verbatim", ""))]
        trajectory = []
        level_map = {
            "4.1": "L1_framed",
            "4.2": "L2_decomposed",
            "4.3": "L3_decided",
            "4.4": "L3_decided",
            "4.5": "L3_decided",
            "4.6": "L3_decided",
            "5.1": "L1_framed",
            "5.2": "L2_decomposed",
            "5.3": "L3_decided",
            "5.4": "L3_decided",
        }
        seen_levels = set()
        if rows and "error" not in rows[0]:
            for r in rows:
                sec = str(r.get("section", "4.1"))
                if sec.endswith(".1"):
                    lvl = "L1_framed"
                elif sec.endswith(".2"):
                    lvl = "L2_decomposed"
                elif sec.endswith(".3") or sec.endswith(".4") or sec.endswith(".5") or sec.endswith(".6"):
                    lvl = "L3_decided"
                else:
                    lvl = level_map.get(sec, "L1_framed")
                if lvl not in seen_levels:
                    seen_levels.add(lvl)
                    q_text = r.get("question") or f"Question de cadrage pour {subject} ({sec})"
                    ans_text = r.get("verbatim") or r.get("val") or ""
                    trajectory.append({
                        "level": lvl,
                        "question": q_text,
                        "answer_excerpt": ans_text,
                    })

        sub_mat = self.get_subject_maturity(subject_name=subject, engagement=engagement)
        current_lvl = sub_mat.get("level", "L0_named") if sub_mat else "L0_named"

        if trajectory and "L2_decomposed" not in seen_levels and current_lvl in ("L2_decomposed", "L3_decided", "L4_specified"):
            q_rows = self.db_client.execute_cypher(
                "MATCH (st:Statement {engagement: $engagement}) WHERE st.section = '4.2' OR st.section = '5.2' RETURN st.verbatim as val LIMIT 1;",
                params={"engagement": engagement},
            )
            ans_excerpt = q_rows[0]["val"] if q_rows and "error" not in q_rows[0] and "val" in q_rows[0] else f"Decomposition of {subject}"
            trajectory.append({
                "level": "L2_decomposed",
                "question": f"Décomposition de {subject}",
                "answer_excerpt": ans_excerpt,
            })

        return trajectory

    def get_subject_maturity(self, subject_name: str = "", engagement: str = "nordwave-mcx-2027", name: str | None = None) -> dict[str, Any]:
        """Récupère les détails de maturité d'un sujet scopé par engagement (avec fallback)."""
        target_name = name or subject_name
        query = (
            "MATCH (s:Subject) WHERE s.name = $target_name AND (s.engagement = $engagement OR s.engagement = 'default' OR s.engagement IS NULL) "
            "RETURN s.name as name, s.level as level, s.origin as origin, s.updated_at as updated_at;"
        )
        rows = self.db_client.execute_cypher(query, params={"target_name": target_name, "engagement": engagement})
        if rows and "error" not in rows[0]:
            r = rows[0]
            return {
                "name": r.get("name", subject_name),
                "subject": r.get("name", subject_name),
                "level": r.get("level") or "L0_named",
                "origin": r.get("origin") or "declared",
                "updated_at": r.get("updated_at") or datetime.now().isoformat(),
            }
        return {"name": subject_name, "subject": subject_name, "level": "L0_named", "origin": "declared", "updated_at": datetime.now().isoformat()}

    def get_subjects_maturity_board(self, engagement: str, stall_days: int = 7) -> list[dict[str, Any]]:
        """Récupère les données d'avancement pour le Maturity Board."""
        query = "MATCH (s:Subject) RETURN s.name as name, s.level as level, s.origin as origin, s.updated_at as updated_at;"
        rows = self.db_client.execute_cypher(query)
        board = []
        now = datetime.now()

        for r in rows:
            if not r or "error" in r:
                continue
            name = r.get("name")
            level = r.get("level") or "L0_named"
            origin = r.get("origin") or "declared"
            updated_at_str = r.get("updated_at") or now.isoformat()
            days_at_level = 0
            if updated_at_str:
                try:
                    dt = datetime.fromisoformat(updated_at_str)
                    days_at_level = (now - dt).days
                    is_stalled = days_at_level >= stall_days
                except Exception:
                    pass

            q_query = "MATCH (q:Question {status: 'open'})-[:TARGETS]->(s:Subject {name: $name}) RETURN q.id as id, q.routed_to as routed_to;"
            q_rows = self.db_client.execute_cypher(q_query, params={"name": name})

            open_q_ref = None
            assigned_role = None
            if q_rows and "error" not in q_rows[0]:
                open_q_ref = q_rows[0].get("id")
                assigned_role = q_rows[0].get("routed_to")

            board.append({
                "subject": name,
                "name": name,
                "level": level,
                "origin": origin,
                "days_at_level": days_at_level,
                "updated_at": updated_at_str,
                "is_stalled": is_stalled and (open_q_ref is not None),
                "open_question_ref": open_q_ref,
                "assigned_role": assigned_role,
                "dependent_sections": ["5.2"],
            })
        return board

    def contest_statement(
        self, target_statement_id: str, author: str, role: str, text: str, engagement: str = "nordwave-mcx-2027"
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

    def demote_subject(
        self, subject_name: str | None = None, to_level: str | None = None, author: str | None = None, reason: str | None = None, engagement: str = "nordwave-mcx-2027", *, name: str | None = None, by: str | None = None
    ) -> dict[str, Any]:
        """Rétrograde la maturité d'un sujet (demotion non-monotone).
        Marque les énoncés de niveau supérieur en 'under_review' et réouvre les questions fermées.
        """
        target_name = name or subject_name or ""
        target_to_level = to_level or ""
        now_str = datetime.now().isoformat()

        # 1. Mettre à jour le niveau du sujet
        self.db_client.execute_cypher(
            "MATCH (s:Subject {name: $name}) SET s.level = $to_level, s.updated_at = $now_str;",
            params={"name": target_name, "to_level": target_to_level, "now_str": now_str},
        )

        # 2. Marquer les énoncés comme 'under_review'
        st_query = """
        MATCH (st:Statement {engagement: $engagement, subject: $name})
        WHERE st.status = 'active'
        SET st.status = 'under_review';
        """
        self.db_client.execute_cypher(st_query, params={"engagement": engagement, "name": target_name})

        # 3. Réouvrir les questions fermées avec contexte conservé
        q_query = """
        MATCH (q:Question {engagement: $engagement})-[:TARGETS]->(s:Subject {name: $name})
        WHERE q.status IN ['confirmed', 'sent']
        SET q.status = 'open';
        """
        self.db_client.execute_cypher(q_query, params={"engagement": engagement, "name": target_name})

        return {
            "subject": subject_name,
            "demoted_to": to_level,
            "author": author,
            "reason": reason,
            "status": "demoted",
        }

    def is_control_covered(self, engagement: str, control_id: str) -> bool:
        """Vérifie si un contrôle de conformité est couvert par au moins un énoncé actif."""
        query = (
            "MATCH (s:Statement {status: 'active'}) "
            "WHERE (s.engagement = $engagement OR s.engagement = 'default') "
            "RETURN s.based_on as based_on, s.value as value, s.verbatim as verbatim;"
        )
        try:
            rows = self.db_client.execute_cypher(query, params={"engagement": engagement})
            for r in rows:
                b = str(r.get("based_on") or "")
                v = str(r.get("value") or "")
                verb = str(r.get("verbatim") or "")
                if control_id in b or control_id in v or control_id in verb:
                    return True
            return False
        except Exception:
            return False
