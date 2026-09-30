"""Import of the file-based governance state into the database (``kb migrate-governance``).

Idempotent: candidates already in the database are left untouched (the database wins), and
the owners registry is seeded only when the database holds none (or with ``force``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipelines.governance.registry import load_registry_from_db, save_registry
from pipelines.kb_candidates.model import CandidateNotFoundError
from pipelines.kb_candidates.owners import load_owners_file
from pipelines.kb_candidates.repository import FileCandidateRepository, SqlCandidateRepository

DEFAULT_EVAL_DATASET = Path("tests/evals/datasets/check_option_v1.jsonl")


def migrate_governance(kb_dir: str | Path = "data/kb", candidates_dir: str | Path = "data/candidates",
                       force_owners: bool = False, url: str | None = None,
                       eval_dataset: str | Path | None = DEFAULT_EVAL_DATASET) -> dict[str, Any]:
    target = SqlCandidateRepository(url)
    imported, skipped = 0, 0
    for candidate in FileCandidateRepository(candidates_dir).all():
        try:
            target.get(candidate["id"])
            skipped += 1
        except CandidateNotFoundError:
            target.save(candidate)
            imported += 1
    owners_seeded = False
    if force_owners or load_registry_from_db() is None:
        registry = load_owners_file(kb_dir)
        save_registry(registry)
        owners_seeded = True
    result: dict[str, Any] = {"candidates_imported": imported, "candidates_skipped": skipped,
                              "owners_seeded": owners_seeded}
    if eval_dataset is not None and Path(eval_dataset).is_file():
        from pipelines.governance.evals import EvalStore

        result["eval_cases"] = EvalStore(url).import_jsonl(
            "check_option_v1", eval_dataset, "Annotated cases of the option judge (check_option).")
    return result
