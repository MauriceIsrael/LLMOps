"""Governance bootstrap at server start (deployment): schema, owners registry and evaluation dataset.

Idempotent: with a governance database configured, tables are created, the owners registry is
seeded from ``data/kb/owners.yaml`` when the database holds none (an existing registry is never
overwritten) and the ``check_option_v1`` evaluation dataset is imported when missing. Without a
database nothing happens. A failure is logged, not raised: the 1.0 to 1.3 interfaces keep serving.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("llmops.governance")

EVAL_DATASET = Path("tests/evals/datasets/check_option_v1.jsonl")


def ensure_governance_ready(kb_dir: str | Path = "data/kb", eval_dataset: str | Path | None = EVAL_DATASET) -> dict[str, Any] | None:
    from pipelines.governance.store import database_url

    if not database_url():
        return None
    try:
        from pipelines.governance.migrate import migrate_governance

        result = migrate_governance(kb_dir, candidates_dir="data/candidates", eval_dataset=eval_dataset)
        logger.warning("governance bootstrap: %s", result)
        return result
    except Exception as exc:  # the server must still start
        logger.error("governance bootstrap failed (governance routes will answer 5xx): %s", exc)
        return None
