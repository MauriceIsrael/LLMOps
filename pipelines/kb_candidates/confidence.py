"""Confidence of a promoted asset, computed from its evidence — never from its author.

| Evidence                                                       | Confidence      |
|----------------------------------------------------------------|-----------------|
| a traceable ``measure`` or ``audit``, or >= 2 distinct ``engagement`` | ``verified``    |
| a cited ``vendor-doc``                                         | ``vendor-stated`` |
| a single ``engagement`` without measure (or no evidence)       | ``assumed``     |
| ``production_mode: llm-derived`` not reviewed by a human       | not publishable |
"""

from __future__ import annotations

from typing import Any


class NotPublishableError(ValueError):
    """The candidate cannot be promoted (e.g. unreviewed llm-derived content)."""


def compute_confidence(evidence: list[dict[str, Any]] | None, production_mode: str | None) -> str:
    if production_mode == "llm-derived":
        raise NotPublishableError("llm-derived content must be reviewed by a human before promotion")
    evidence = evidence or []
    refs = {kind: {str(e.get("ref") or "").strip() for e in evidence if e.get("kind") == kind} - {""}
            for kind in ("measure", "audit", "engagement", "vendor-doc")}
    if refs["measure"] or refs["audit"] or len(refs["engagement"]) >= 2:
        return "verified"
    if refs["vendor-doc"]:
        return "vendor-stated"
    return "assumed"
