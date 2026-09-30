"""Evaluation datasets, runs and verdict feedback in the governance database (lot L7)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from pipelines.governance.log import now_iso
from pipelines.governance.store import (
    eval_cases,
    eval_datasets,
    eval_runs,
    get_engine,
    verdict_feedback,
)

ANNOTATION_STATUSES = ("proposed", "validated", "rejected")
EXPECTED_VERDICTS = ("violates", "supports")
FEEDBACK_KINDS = ("wrong_violation", "missed_violation", "correct")


class EvalError(ValueError):
    """Invalid evaluation request (400)."""

    def __init__(self, argument: str, reason: str) -> None:
        super().__init__(reason)
        self.argument, self.reason = argument, reason


class EvalNotFoundError(LookupError):
    pass


def validate_expected(expected: Any) -> dict[str, str]:
    if not isinstance(expected, dict) or not expected:
        raise EvalError("expected", "'expected' must map at least one typed_id to 'violates' or 'supports'.")
    clean: dict[str, str] = {}
    for typed_id, verdict in expected.items():
        if not isinstance(typed_id, str) or ":" not in typed_id or verdict not in EXPECTED_VERDICTS:
            raise EvalError("expected", f"each entry must be '<type>:<id>': one of {list(EXPECTED_VERDICTS)}.")
        clean[typed_id] = verdict
    return clean


def _case(row: Any) -> dict[str, Any]:
    doc = json.loads(row.doc)
    doc.update(annotation_status=row.annotation_status, annotated_by=row.annotated_by, annotated_at=row.annotated_at)
    return doc


class EvalStore:
    def __init__(self, url: str | None = None) -> None:
        self.engine = get_engine(url)

    # ---------------------------------------------------------------- datasets

    def has_dataset(self, name: str) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(select(eval_datasets.c.name).where(eval_datasets.c.name == name)).first() is not None

    def import_jsonl(self, name: str, path: str | Path, description: str = "") -> dict[str, int]:
        """Idempotent import: cases already in the database are left untouched."""
        lines = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
        imported = skipped = 0
        with self.engine.begin() as conn:
            if not self.has_dataset(name):
                conn.execute(eval_datasets.insert().values(name=name, description=description, created_at=now_iso()))
            for case in lines:
                exists = conn.execute(select(eval_cases.c.case_id).where(
                    (eval_cases.c.dataset == name) & (eval_cases.c.case_id == case["id"]))).first()
                if exists:
                    skipped += 1
                    continue
                conn.execute(eval_cases.insert().values(
                    dataset=name, case_id=case["id"], doc=json.dumps(case, ensure_ascii=False),
                    annotation_status=case.get("annotation_status", "proposed"),
                    annotated_by=case.get("annotated_by"), annotated_at=None))
                imported += 1
        return {"imported": imported, "skipped": skipped}

    def cases(self, name: str) -> list[dict[str, Any]]:
        if not self.has_dataset(name):
            raise EvalNotFoundError(name)
        with self.engine.connect() as conn:
            rows = conn.execute(select(eval_cases).where(eval_cases.c.dataset == name)
                                .order_by(eval_cases.c.case_id)).all()
        return [_case(r) for r in rows]

    def case(self, name: str, case_id: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(select(eval_cases).where(
                (eval_cases.c.dataset == name) & (eval_cases.c.case_id == case_id))).first()
        if row is None:
            raise EvalNotFoundError(f"{name}/{case_id}")
        return _case(row)

    def annotate(self, name: str, case_id: str, annotator: str, expected: Any = None,
                 status: str | None = None) -> dict[str, Any]:
        """Set the expected verdicts and/or the annotation status; the annotator is recorded."""
        case = self.case(name, case_id)
        if status is not None and status not in ANNOTATION_STATUSES:
            raise EvalError("annotation_status", f"must be one of {list(ANNOTATION_STATUSES)}.")
        if expected is not None:
            case["expected"] = validate_expected(expected)
        if (status or case["annotation_status"]) == "validated" and not case.get("expected"):
            raise EvalError("expected", "a validated case needs expected verdicts.")
        doc = {k: v for k, v in case.items() if k not in ("annotation_status", "annotated_by", "annotated_at")}
        with self.engine.begin() as conn:
            conn.execute(eval_cases.update().where(
                (eval_cases.c.dataset == name) & (eval_cases.c.case_id == case_id)).values(
                doc=json.dumps(doc, ensure_ascii=False), annotation_status=status or case["annotation_status"],
                annotated_by=annotator, annotated_at=now_iso()))
        return self.case(name, case_id)

    def add_case(self, name: str, case: dict[str, Any], annotator: str) -> dict[str, Any]:
        """New case (status ``proposed``) — used by evaluators and by verdict-feedback conversion."""
        if not self.has_dataset(name):
            raise EvalNotFoundError(name)
        option = case.get("option")
        if not isinstance(option, dict) or not str(option.get("title") or "").strip():
            raise EvalError("option", "'option.title' is required.")
        expected = validate_expected(case.get("expected"))
        with self.engine.connect() as conn:
            count = conn.execute(select(func.count()).select_from(eval_cases).where(eval_cases.c.dataset == name)).scalar()
        case_id = str(case.get("id") or f"CO-{int(count or 0) + 1:03d}")
        with self.engine.begin() as conn:
            if conn.execute(select(eval_cases.c.case_id).where(
                    (eval_cases.c.dataset == name) & (eval_cases.c.case_id == case_id))).first():
                raise EvalError("id", f"case '{case_id}' already exists.")
            doc = {"id": case_id, "sector": case.get("sector", ""), "subject": case.get("subject"),
                   "frameworks": case.get("frameworks") or [], "option": option, "expected": expected}
            conn.execute(eval_cases.insert().values(
                dataset=name, case_id=case_id, doc=json.dumps(doc, ensure_ascii=False),
                annotation_status="proposed", annotated_by=annotator, annotated_at=now_iso()))
        return self.case(name, case_id)

    # -------------------------------------------------------------------- runs

    def save_run(self, name: str, run_by: str, metrics: dict[str, Any]) -> dict[str, Any]:
        with self.engine.begin() as conn:
            res = conn.execute(eval_runs.insert().values(dataset=name, at=now_iso(), run_by=run_by,
                                                         metrics=json.dumps(metrics, ensure_ascii=False)))
            run_id = int((res.inserted_primary_key or (0,))[0])
        return self.run(name, run_id)

    def run(self, name: str, run_id: int) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(select(eval_runs).where((eval_runs.c.id == run_id) & (eval_runs.c.dataset == name))).first()
        if row is None:
            raise EvalNotFoundError(f"{name}/runs/{run_id}")
        return {"id": row.id, "dataset": row.dataset, "at": row.at, "run_by": row.run_by, **json.loads(row.metrics)}

    def runs(self, name: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(eval_runs).where(eval_runs.c.dataset == name).order_by(eval_runs.c.id.desc())).all()
        return [{"id": r.id, "at": r.at, "run_by": r.run_by,
                 **{k: v for k, v in json.loads(r.metrics).items() if k in ("violation_recall", "supports_recall", "cases")}}
                for r in rows]

    # --------------------------------------------------------------- feedback

    def add_feedback(self, reporter: str, typed_id: str, feedback: str, justification: str,
                     context: dict[str, Any], check_id: str | None = None) -> dict[str, Any]:
        if feedback not in FEEDBACK_KINDS:
            raise EvalError("feedback", f"must be one of {list(FEEDBACK_KINDS)}.")
        if not isinstance(typed_id, str) or ":" not in typed_id:
            raise EvalError("typed_id", "'typed_id' must look like 'principle:P-002'.")
        if not isinstance(justification, str) or not justification.strip():
            raise EvalError("justification", "'justification' is required.")
        option = context.get("option")
        if not isinstance(option, dict) or not str(option.get("title") or "").strip():
            raise EvalError("option", "'option.title' is required.")
        with self.engine.begin() as conn:
            res = conn.execute(verdict_feedback.insert().values(
                at=now_iso(), reporter=reporter, typed_id=typed_id, check_id=check_id, feedback=feedback,
                justification=justification.strip(), context=json.dumps(context, ensure_ascii=False), status="open"))
            fid = int((res.inserted_primary_key or (0,))[0])
        return self.feedback(fid)

    def feedback(self, feedback_id: int) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(select(verdict_feedback).where(verdict_feedback.c.id == feedback_id)).first()
        if row is None:
            raise EvalNotFoundError(f"verdict-feedback/{feedback_id}")
        return {"id": row.id, "at": row.at, "reporter": row.reporter, "typed_id": row.typed_id, "check_id": row.check_id,
                "feedback": row.feedback, "justification": row.justification, "status": row.status,
                "converted_to": row.converted_to, **json.loads(row.context)}

    def list_feedback(self, status: str | None = None) -> list[dict[str, Any]]:
        query = select(verdict_feedback.c.id).order_by(verdict_feedback.c.id.desc())
        if status:
            query = query.where(verdict_feedback.c.status == status)
        with self.engine.connect() as conn:
            ids = [r.id for r in conn.execute(query).all()]
        return [self.feedback(i) for i in ids]

    def close_feedback(self, feedback_id: int, status: str, converted_to: str | None = None) -> dict[str, Any]:
        with self.engine.begin() as conn:
            conn.execute(verdict_feedback.update().where(verdict_feedback.c.id == feedback_id).values(
                status=status, converted_to=converted_to))
        return self.feedback(feedback_id)
