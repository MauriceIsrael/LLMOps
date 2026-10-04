"""Script to generate JSON Schemas and TypeScript types for all MCP tools."""

import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure root directory is in sys.path when script is executed directly
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.elicitation.config import (
    CONFIDENCE_LEVELS,
    CONFLICT_KINDS,
    GAP_TYPES,
    STATEMENT_STATUSES,
    SUBJECT_LEVELS,
)


def generate_envelope_schema() -> dict[str, Any]:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "ResponseEnvelope",
        "description": "Standardized envelope returned by all LLMOps FastMCP tools.",
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["ok", "not_found", "invalid_argument", "error", "unauthorized"],
            },
            "count": {
                "type": "integer",
                "minimum": 0,
            },
            "data": {
                "description": "Payload response whose structure depends on the tool called.",
            },
            "reason": {
                "type": "string",
                "description": "Explanation provided when status is error, invalid_argument, or unauthorized.",
            },
        },
        "required": ["status", "count", "data"],
    }


def generate_doctrine_context_schema() -> dict[str, Any]:
    """Response of get_doctrine_context / GET /api/knowledge/context (contract 1.1)."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "DoctrineContextResponse",
        "description": "Doctrine applicable to a subject: active principles, required controls, patterns and ADRs, ranked deterministically.",
        "type": "object",
        "required": ["status", "count", "data"],
        "properties": {
            "status": {"const": "ok"},
            "count": {"type": "integer", "minimum": 0},
            "data": {
                "type": "object",
                "required": ["items", "truncated", "snapshot_id"],
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "typed_id", "id", "type", "title", "status", "confidence", "domain",
                                "excerpt", "source_ref", "relevance", "has_checks",
                            ],
                            "properties": {
                                "typed_id": {"type": "string", "pattern": "^(principle|pattern|decision|control):.+$"},
                                "id": {"type": "string"},
                                "type": {"enum": ["principle", "pattern", "decision", "control"]},
                                "title": {"type": "string"},
                                "status": {"const": "active"},
                                "confidence": {"type": "string"},
                                "domain": {"type": "array", "items": {"type": "string"}},
                                "excerpt": {"type": "string"},
                                "source_ref": {"type": "string"},
                                "relevance": {"type": "number", "minimum": 0, "maximum": 1},
                                "has_checks": {"type": "boolean"},
                                "framework": {"type": ["string", "null"]},
                                "required": {"type": "boolean", "description": "Control of a framework listed in 'frameworks'."},
                            },
                        },
                    },
                    "truncated": {"type": "boolean"},
                    "snapshot_id": {"type": ["string", "null"]},
                },
            },
        },
    }


def generate_check_result_schema() -> dict[str, Any]:
    """Response of check_option / POST /api/knowledge/check (contract 1.1)."""
    verdict_enum = ["supports", "violates", "unassessed"]
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "CheckOptionResponse",
        "description": "Deterministic verdicts of an option against the doctrine's structured check clauses.",
        "type": "object",
        "required": ["status", "count", "data"],
        "properties": {
            "status": {"const": "ok"},
            "count": {"type": "integer", "minimum": 0},
            "data": {
                "type": "object",
                "required": ["verdicts", "summary", "method", "snapshot_id"],
                "properties": {
                    "verdicts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "typed_id", "check_id", "verdict", "message", "matched_terms", "excerpt", "source_ref",
                            ],
                            "properties": {
                                "typed_id": {"type": "string"},
                                "check_id": {"type": ["string", "null"]},
                                "verdict": {"enum": verdict_enum},
                                "message": {"type": ["string", "null"]},
                                "matched_terms": {"type": "array", "items": {"type": "string"}},
                                "excerpt": {"type": "string"},
                                "source_ref": {"type": "string"},
                                "check_status": {
                                    "enum": ["draft", "validated", None],
                                    "description": "Review status of the clause that produced the verdict (null when unassessed).",
                                },
                            },
                        },
                    },
                    "summary": {
                        "type": "object",
                        "required": verdict_enum,
                        "properties": {v: {"type": "integer", "minimum": 0} for v in verdict_enum},
                    },
                    "method": {"const": "deterministic-checks-v1"},
                    "snapshot_id": {"type": ["string", "null"]},
                },
            },
        },
    }


def generate_kb_candidate_schema() -> dict[str, Any]:
    """KB candidate (contract 1.2), see pipelines/kb_candidates/model.py."""
    from pipelines.kb_candidates.model import (
        ASSET_TYPES,
        CHECK_STATUSES,
        EVIDENCE_KINDS,
        KINDS,
        PRODUCTION_MODES,
        REVIEW_ACTIONS,
        SOURCE_SYSTEMS,
        STATUSES,
    )

    nullable_str = {"type": ["string", "null"]}
    review = {
        "type": ["object", "null"],
        "required": ["reviewer", "action", "at"],
        "properties": {
            "reviewer": {"type": "string"},
            "action": {"enum": list(REVIEW_ACTIONS)},
            "reason": nullable_str,
            "at": {"type": "string"},
        },
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "KbCandidate",
        "description": "Knowledge base candidate: proposed change going through automatic checks, human review, promotion and publication.",
        "type": "object",
        "required": [
            "id", "kind", "asset_type", "domain", "title", "rationale", "proposed_content", "source", "evidence",
            "status", "checks", "review", "second_review_required", "second_review", "assigned_owner", "history",
            "created_at", "updated_at",
        ],
        "properties": {
            "id": {"type": "string", "pattern": "^CAND-\\d{8}-\\d{4}$"},
            "kind": {"enum": list(KINDS)},
            "target_asset_id": nullable_str,
            "asset_type": {"enum": [*ASSET_TYPES, None]},
            "domain": {"type": "array", "items": {"type": "string"}},
            "title": {"type": "string", "minLength": 1},
            "rationale": {"type": "string"},
            "proposed_content": {"type": "string"},
            "source": {
                "type": "object",
                "required": ["system", "production_mode"],
                "properties": {
                    "system": {"enum": list(SOURCE_SYSTEMS)},
                    "engagement": nullable_str,
                    "decision_id": nullable_str,
                    "author": nullable_str,
                    "contact": nullable_str,
                    "production_mode": {"enum": list(PRODUCTION_MODES)},
                },
            },
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kind", "ref"],
                    "properties": {"kind": {"enum": list(EVIDENCE_KINDS)}, "ref": {"type": "string", "minLength": 1}},
                },
            },
            "status": {"enum": list(STATUSES)},
            "checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "status", "detail"],
                    "properties": {
                        "name": {"type": "string"},
                        "status": {"enum": list(CHECK_STATUSES)},
                        "detail": {"type": "string"},
                    },
                },
            },
            "review": review,
            "second_review_required": {"type": "boolean"},
            "second_review": review,
            "assigned_owner": nullable_str,
            "history": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["at", "actor", "event"],
                    "properties": {"at": {"type": "string"}, "actor": {"type": "string"}, "event": {"type": "string"}},
                },
            },
            "promoted": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "asset_id": {"type": "string"}, "confidence": {"type": "string"}},
            },
            "published": {
                "type": "object",
                "properties": {"snapshot_id": nullable_str, "at": {"type": "string"}},
            },
            "created_at": {"type": "string"},
            "updated_at": {"type": "string"},
        },
    }


def generate_framework_coverage_schema() -> dict[str, Any]:
    """Coverage entry (get_framework_coverage / coverage of GET /api/compliance/frameworks/applicable)."""
    entry = {
        "type": "object",
        "required": ["status", "version", "expected", "present", "validated", "missing_ids", "declared_by"],
        "properties": {
            "status": {"enum": ["covered", "partial", "missing"]},
            "version": {"type": ["string", "null"]},
            "expected": {"type": ["integer", "null"], "minimum": 0},
            "present": {"type": "integer", "minimum": 0},
            "validated": {"type": "integer", "minimum": 0},
            "missing_ids": {"type": "array", "items": {"type": "string"}},
            "declared_by": {"type": ["string", "null"]},
            "provisional": {"type": ["boolean", "null"]},
            "manifest": {"type": "boolean"},
        },
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "FrameworkCoverageResponse",
        "description": "Coverage of regulatory frameworks by the knowledge base (contract 1.3).",
        "type": "object",
        "required": ["status", "count", "data"],
        "properties": {
            "status": {"const": "ok"},
            "count": {"type": "integer", "minimum": 0},
            "data": {"type": "object", "additionalProperties": entry},
        },
        "definitions": {"FrameworkCoverage": entry},
    }


def generate_kb_me_schema() -> dict[str, Any]:
    """Acting expert (get_kb_me / GET /api/knowledge/me, contract 1.4)."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "KbMeResponse",
        "description": "Expert the calling client acts for (contract 1.4).",
        "type": "object",
        "required": ["status", "count", "data"],
        "properties": {
            "status": {"const": "ok"},
            "count": {"type": "integer"},
            "data": {
                "type": "object",
                "required": ["handle", "email", "kb_roles", "owned_domains", "pending_reviews"],
                "properties": {
                    "handle": {"type": "string"},
                    "email": {"type": ["string", "null"]},
                    "kb_roles": {"type": "array", "items": {"enum": ["kb:review", "kb:evaluate", "kb:maintain", "kb:admin"]}},
                    "owned_domains": {"type": "array", "items": {"type": "string"}},
                    "pending_reviews": {"type": "integer", "minimum": 0},
                },
            },
        },
    }


def generate_review_inbox_schema() -> dict[str, Any]:
    """Review inbox of the acting expert (get_review_inbox / GET /api/knowledge/reviews/inbox, contract 1.5)."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "ReviewInboxResponse",
        "type": "object",
        "required": ["status", "count", "data"],
        "properties": {
            "status": {"const": "ok"},
            "count": {"type": "integer"},
            "data": {
                "type": "object",
                "required": ["handle", "items"],
                "properties": {
                    "handle": {"type": "string"},
                    "items": {"type": "array", "items": {
                        "type": "object",
                        "required": ["candidate_id", "title", "kind", "reason", "waiting_since", "due_at"],
                        "properties": {
                            "candidate_id": {"type": "string"}, "title": {"type": "string"}, "kind": {"type": "string"},
                            "asset_type": {"type": ["string", "null"]},
                            "domain": {"type": "array", "items": {"type": "string"}},
                            "reason": {"enum": ["review", "second_review", "advice"]},
                            "waiting_since": {"type": "string"}, "due_at": {"type": "string"},
                            "message": {"type": ["string", "null"]},
                            "checks_failed": {"type": "array", "items": {"type": "string"}},
                        },
                    }},
                },
            },
        },
    }


def generate_governance_event_schema() -> dict[str, Any]:
    """Event of the governance feed (GET /api/knowledge/events, contract 1.5)."""
    from pipelines.governance.log import EVENT_TYPES

    event = {
        "type": "object",
        "required": ["id", "at", "type", "actor", "recipients", "payload"],
        "properties": {
            "id": {"type": "integer"}, "at": {"type": "string"}, "type": {"enum": list(EVENT_TYPES)},
            "candidate_id": {"type": ["string", "null"]}, "actor": {"type": "string"},
            "recipients": {"type": "array", "items": {"type": "string"}}, "payload": {"type": "object"},
        },
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "GovernanceEventFeed",
        "type": "object",
        "required": ["status", "count", "data"],
        "properties": {
            "status": {"const": "ok"}, "count": {"type": "integer"},
            "data": {"type": "object", "required": ["events", "next_cursor"], "properties": {
                "events": {"type": "array", "items": event}, "next_cursor": {"type": "integer"}}},
        },
        "definitions": {"GovernanceEvent": event},
    }


def _envelope(title: str, data: dict[str, Any], description: str) -> dict[str, Any]:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#", "title": title, "description": description,
        "type": "object", "required": ["status", "count", "data"],
        "properties": {"status": {"const": "ok"}, "count": {"type": "integer"}, "data": data},
    }


def generate_asset_template_schema() -> dict[str, Any]:
    return _envelope("AssetTemplateResponse", {
        "type": "object", "required": ["asset_type", "fields", "sections", "skeleton"],
        "properties": {
            "asset_type": {"type": "string"},
            "fields": {"type": "array", "items": {"type": "object", "required": ["name", "required", "type"], "properties": {
                "name": {"type": "string"}, "required": {"type": "boolean"}, "type": {"type": "string"},
                "values": {"type": ["array", "null"], "items": {"type": "string"}},
                "pattern": {"type": ["string", "null"]}, "help": {"type": ["string", "null"]}}}},
            "sections": {"type": "array", "items": {"type": "object", "properties": {
                "heading": {"type": "string"}, "required": {"type": "boolean"}}}},
            "next_id": {"type": ["string", "null"]}, "skeleton": {"type": "string"}, "help": {"type": "string"},
        }}, "Structured template of an asset type (GET /api/knowledge/templates/{type}, contract 1.6).")


def generate_simulation_schema() -> dict[str, Any]:
    verdicts = {"type": "array", "items": {"type": "object", "properties": {
        "check_id": {"type": ["string", "null"]}, "verdict": {"enum": ["supports", "violates"]},
        "matched_terms": {"type": "array", "items": {"type": "string"}}}}}
    metrics = {"type": "object", "properties": {
        "violation_recall": {"type": "number"}, "supports_recall": {"type": "number"},
        "unexpected_violations": {"type": "integer"}, "expected_violations": {"type": "integer"}}}
    return _envelope("ClauseSimulationResponse", {
        "type": "object", "required": ["asset_id", "typed_id", "clause_problems", "metrics", "regressions", "cases"],
        "properties": {
            "asset_id": {"type": "string"}, "typed_id": {"type": "string"},
            "clause_problems": {"type": "array", "items": {"type": "object"}},
            "metrics": {"type": "object", "properties": {"cases": {"type": "integer"}, "before": metrics, "after": metrics}},
            "regressions": {"type": "array", "items": {"type": "string"}},
            "improvements": {"type": "array", "items": {"type": "string"}},
            "cases": {"type": "array", "items": {"type": "object", "properties": {
                "case_id": {"type": "string"}, "expected": {"type": ["string", "null"]}, "before": verdicts,
                "after": verdicts, "changed": {"type": "boolean"}, "regression": {"type": "boolean"},
                "improvement": {"type": "boolean"}}}},
            "options": {"type": "array", "items": {"type": "object"}},
        }}, "Deterministic simulation of proposed clauses (POST /api/knowledge/checks/simulate, contract 1.6).")


def generate_eval_dataset_schema() -> dict[str, Any]:
    return _envelope("EvalDatasetResponse", {
        "type": "object", "required": ["dataset", "cases", "validated"],
        "properties": {
            "dataset": {"type": "string"}, "validated": {"type": "integer"},
            "cases": {"type": "array", "items": {"type": "object", "required": ["id", "option", "expected", "annotation_status"],
                "properties": {"id": {"type": "string"}, "sector": {"type": "string"},
                               "subject": {"type": ["string", "null"]}, "frameworks": {"type": "array"},
                               "option": {"type": "object"},
                               "expected": {"type": "object", "additionalProperties": {"enum": ["violates", "supports"]}},
                               "annotation_status": {"enum": ["proposed", "validated", "rejected"]},
                               "annotated_by": {"type": ["string", "null"]}, "annotated_at": {"type": ["string", "null"]}}}},
            "runs": {"type": "array", "items": {"type": "object"}},
        }}, "Evaluation dataset of the option judge (GET /api/knowledge/evals/{dataset}, contract 1.6).")


def generate_framework_ingestion_schema() -> dict[str, Any]:
    row = {
        "type": "object",
        "required": ["requirement_id", "title", "legal_text", "decision", "status"],
        "properties": {
            "requirement_id": {"type": "string"}, "title": {"type": "string"}, "source_ref": {"type": "string"},
            "domain": {"type": "array", "items": {"type": "string"}}, "in_kb": {"type": "boolean"},
            "legal_text": {"type": "string"},
            "proposed_links": {"type": "array", "items": {"type": "string"}},
            "proposed_acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "links_production_mode": {"enum": ["", "llm-derived"]},
            "proposed_terms": {"type": "array", "items": {"type": "string"}},
            "proposed_title_fr": {"type": "string"},
            "terms": {"type": "array", "items": {"type": "string"}}, "title_fr": {"type": "string"},
            "decision": {"enum": ["", "accept", "amend", "reject"]},
            "links": {"type": "array", "items": {"type": "string"}},
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "reviewer": {"type": "string"}, "comment": {"type": "string"},
            "status": {"enum": ["pending", "decided", "applied", "failed"]}, "result": {"type": ["string", "null"]},
        },
    }
    return _envelope("FrameworkIngestionResponse", {
        "type": "object", "required": ["id", "framework", "version", "status", "requirements", "decided", "total"],
        "properties": {
            "id": {"type": "integer"}, "framework": {"type": "string"}, "version": {"type": "string"},
            "tag": {"type": ["string", "null"]}, "source_name": {"type": "string"}, "source_sha256": {"type": "string"},
            "status": {"enum": ["reviewing", "partially_applied", "applied"]},
            "created_by": {"type": "string"}, "created_at": {"type": "string"}, "declaration_reset": {"type": "boolean"},
            "requirements": {"type": "array", "items": row}, "decided": {"type": "integer"}, "total": {"type": "integer"},
        }}, "Ingestion of a regulatory source (GET /api/frameworks/ingestions/{id}, contract 1.7).")


def generate_kb_health_schema() -> dict[str, Any]:
    return _envelope("KbHealthResponse", {
        "type": "object",
        "required": ["generated_at", "assets", "clauses", "coverage", "queue", "storage"],
        "properties": {
            "generated_at": {"type": "string"},
            "assets": {"type": "object", "properties": {
                "active": {"type": "integer"}, "by_type": {"type": "object"}, "by_domain": {"type": "object"},
                "unvalidated": {"type": "object", "properties": {
                    "count": {"type": "integer"}, "ids": {"type": "array", "items": {"type": "string"}}}}}},
            "clauses": {"type": "object", "properties": {
                "total": {"type": "integer"}, "draft": {"type": "integer"},
                "unassessed_verdict_share": {"type": ["number", "null"]}}},
            "coverage": {"type": "object"},
            "queue": {"type": "object", "properties": {
                "by_status": {"type": "object"}, "per_owner": {"type": "object"},
                "overdue": {"type": "array", "items": {"type": "object"}}}},
            "evaluation": {"type": ["object", "null"]},
            "last_snapshot": {"type": ["object", "null"]},
            "storage": {"type": "object", "properties": {
                "persistent": {"type": "boolean"}, "mode": {"enum": ["normal", "demo"]}}},
        }}, "Health indicators of the knowledge base (GET /api/knowledge/health, contract 1.8).")


def generate_similar_schema() -> dict[str, Any]:
    result = {
        "type": "object",
        "required": ["ref", "type", "title", "score", "scores", "zone", "requires_confirmation", "assumptions_documented"],
        "properties": {
            "ref": {"type": "string"}, "type": {"type": "string"}, "title": {"type": "string"},
            "score": {"type": "number"}, "scores": {"type": "object", "additionalProperties": {"type": "number"}},
            "zone": {"enum": ["strong", "possible", "weak", "superseded"]},
            "requires_confirmation": {"const": True},
            "stale": {"type": "boolean"}, "status": {"type": "string"},
            "domain": {"type": "array", "items": {"type": "string"}},
            "last_reviewed": {"type": ["string", "null"]}, "review_by": {"type": ["string", "null"]},
            "validated_by": {"type": "array", "items": {"type": "string"}}, "validated_at": {"type": ["string", "null"]},
            "superseded_by": {"type": ["string", "null"]},
            "assumptions": {"type": "array", "items": {"type": "string"}}, "assumptions_documented": {"type": "boolean"},
        },
    }
    return _envelope("SimilarKnowledgeResponse", {
        "type": "object", "required": ["model", "dim", "config", "results"],
        "properties": {"model": {"type": "string"}, "dim": {"type": "integer"}, "model_version": {"type": "string"},
                       "config": {"type": "object"}, "results": {"type": "array", "items": result}}},
        "Validated knowledge close to a subject (POST /api/knowledge/similar, contract 1.9). Never a decision.")


def generate_reuse_confirmation_schema() -> dict[str, Any]:
    return _envelope("ReuseConfirmationResponse", {
        "type": "object",
        "required": ["id", "at", "actor", "subject_fingerprint", "matched_ref", "outcome", "assumptions"],
        "properties": {
            "id": {"type": "integer"}, "at": {"type": "string"}, "actor": {"type": "string"},
            "subject_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "subject_label": {"type": "string"},
            "matched_ref": {"type": "string"}, "assumptions_digest": {"type": "string"}, "model": {"type": ["string", "null"]},
            "scores": {"type": "object"},
            "outcome": {"enum": ["reused", "reused_with_exception", "rejected_not_same", "rejected_assumption_fails", "deferred"]},
            "assumptions": {"type": "array", "items": {"type": "object", "required": ["text", "status"], "properties": {
                "text": {"type": "string"}, "status": {"enum": ["holds", "does_not_hold", "unknown"]},
                "note": {"type": ["string", "null"]}}}},
            "comment": {"type": ["string", "null"]},
        }}, "Judgement of a person on a reuse proposal (POST /api/knowledge/reuse-confirmations, contract 1.10).")


def generate_similarity_eval_schema() -> dict[str, Any]:
    return _envelope("SimilarityEvalRunResponse", {
        "type": "object", "required": ["id", "dataset", "cases", "false_strong", "by_family", "sweep"],
        "properties": {
            "id": {"type": "integer"}, "dataset": {"type": "string"}, "model": {"type": "string"},
            "cases": {"type": "integer"}, "validated_cases": {"type": "integer"},
            "same_subject_expected": {"type": "integer"}, "recall_at_3": {"type": ["number", "null"]},
            "false_strong": {"type": "integer"}, "reuse_trap_strong": {"type": "integer"}, "missed_strong": {"type": "integer"},
            "by_family": {"type": "object"}, "by_language": {"type": "object"},
            "sweep": {"type": "array", "items": {"type": "object", "properties": {
                "threshold": {"type": "number"}, "false_strong": {"type": "integer"}, "recall": {"type": ["number", "null"]}}}},
            "recommended_strong_threshold": {"type": ["number", "null"]}, "recommendation_note": {"type": "string"},
            "per_case": {"type": "array", "items": {"type": "object"}},
        }}, "Run of the similarity evaluation (POST /api/knowledge/similarity-evals/{dataset}/runs, contract 1.11).")


def generate_typescript_types() -> str:
    conf_union = " | ".join(f'"{c}"' for c in sorted(CONFIDENCE_LEVELS))
    subj_levels_union = " | ".join(f'"{lvl}"' for lvl in SUBJECT_LEVELS)
    conflict_kinds_union = " | ".join(f'"{k}"' for k in sorted(CONFLICT_KINDS))
    gap_types_union = " | ".join(f'"{g}"' for g in sorted(GAP_TYPES))
    stmt_statuses_union = " | ".join(f'"{s}"' for s in sorted(STATEMENT_STATUSES | {"contested", "under_review"}))

    return f"""/**
 * LLMOps MCP Tool Response Contract (schema_version: "1.21")
 * Generated automatically by scripts/generate_schemas.py. Do not edit manually.
 */

export type EnvelopeStatus = "ok" | "not_found" | "invalid_argument" | "error" | "unauthorized" | "unavailable";

export type ConfidenceLevel = {conf_union};

export type SubjectMaturityLevel = {subj_levels_union};

export type ConflictKind = {conflict_kinds_union};

export type GapType = {gap_types_union};

export type StatementStatus = {stmt_statuses_union};

export interface ResponseEnvelope<T = any> {{
  status: EnvelopeStatus;
  count: number;
  data: T;
  reason?: string;
}}

export interface AssetProvenance {{
  document?: string;
  version?: string;
  section?: string;
  text_sha256?: string;
}}

export interface Asset {{
  id: string;
  typed_id?: string;
  title: string;
  kind?: string;
  type?: string;
  status: "active" | "superseded" | string;
  confidence: ConfidenceLevel;
  domain?: string;
  phase?: string;
  owner?: string;
  vendor?: string;
  last_reviewed?: string;
  path?: string;
  source_path?: string;
  content?: string;
  /** Contract 1.15 (K3): citable revision, reference, and hash of `content` in the sealed snapshot. */
  revision?: number;
  knowledge_ref?: KnowledgeRef;
  content_sha256?: string;
  provenance?: AssetProvenance;
  supersedes?: Array<{{ id: string; title?: string }}>;
  superseded_by?: Array<{{ id: string; title?: string }}>;
}}

/** KnowledgeRef of the suite (K3): a partial reference does not exist. */
export interface KnowledgeRef {{
  sourceId: "knowledge-hub";
  knowledgeKey: string;
  version: string;
}}

export interface Statement {{
  id: string;
  subject: string;
  predicate: string;
  value: string;
  confidence: ConfidenceLevel;
  author?: string;
  role?: string;
  status: StatementStatus;
  verbatim?: string;
  section?: string;
  based_on?: Array<{{ id: string; resolved?: boolean; note?: string }}>;
}}

export interface SubjectBoardItem {{
  id?: string;
  subject: string;
  name?: string;
  level: SubjectMaturityLevel;
  origin?: "blueprint" | "discovered" | string;
  active_statements_count?: number;
  days_at_level?: number;
  is_stalled?: boolean;
  stalled?: boolean;
  updated_at?: string;
}}

export interface Conflict {{
  id: string;
  kind: ConflictKind;
  detail: string;
  status: "open" | "arbitrated";
  origin: "declared" | "detected";
  statement_ids?: string[];
  resolution?: string;
  arbitrated_by?: string;
}}

export interface Uncertainty {{
  id: string;
  text: string;
  author?: string;
  role?: string;
}}

export interface RenderPayload {{
  engagement: string;
  status: "provisional" | "final";
  is_provisional: boolean;
  active_statements: Statement[];
  open_conflicts: Conflict[];
  uncertainties?: Uncertainty[];
  unripe_subjects: string[];
  maturity_board: SubjectBoardItem[];
}}

export interface SealedSnapshotEnvelope {{
  snapshot_id: string;
  created_at: string;
  source_revision: string;
  payload_sha256: string;
  schema_version: "1.0";
  /** Channel envelope (contract 1.15, K2). */
  emitter?: "knowledge-hub";
  checksum?: string;
  rebuiltByEmitterTest?: boolean;
  regenerate?: string;
  is_provisional?: boolean;
  provisional_reasons?: {{ unripe_subjects: number; open_conflicts: number }};
  applicability_index: Record<string, {{ rules?: string[]; layers?: string[]; domains?: string[] }}>;
  assets: Asset[];
  glossary: Array<{{ term: string; definition: string; context?: string }}>;
  engagements?: Array<{{
    id: string;
    render_payload: RenderPayload;
  }}>;
}}

export interface ExternalRef {{
  system: "KH" | "AS" | string;
  id: string;
  version: string;
  sha256?: string;
}}

export interface PatternSuggestion {{
  pattern_id: string;
  typed_id: string;
  title: string;
  summary: string;
  applicability: string;
  confidence: ConfidenceLevel;
  external_ref: string;
  trade_offs?: string[];
}}

export interface SuggestionCatalogContext {{
  issue_kind: "SPOF" | "LATENCY_RISK" | "SECURITY_ISOLATION" | "RESILIENCE" | string;
  domain?: string;
  context_tags?: string[];
}}

export interface SuggestionCatalogPort {{
  getSuggestions(context: SuggestionCatalogContext): Promise<ResponseEnvelope<{{
    context: SuggestionCatalogContext;
    suggestions: PatternSuggestion[];
  }}>>;
}}

/* ---- Contract 1.1: doctrine context & option judge ---------------------- */

export type DoctrineItemType = "principle" | "pattern" | "decision" | "control";

export interface DoctrineContextItem {{
  typed_id: string;
  id: string;
  type: DoctrineItemType;
  title: string;
  status: "active";
  confidence: ConfidenceLevel | string;
  domain: string[];
  excerpt: string;
  source_ref: string;
  relevance: number;
  has_checks: boolean;
  framework?: string | null;
  required?: boolean;
}}

export interface DoctrineContext {{
  items: DoctrineContextItem[];
  truncated: boolean;
  snapshot_id: string | null;
}}

export interface DoctrineContextRequest {{
  subject: string;
  domains?: string[];
  frameworks?: string[];
  phase?: string | null;
  max_items?: number;
  max_chars?: number;
}}

export interface OptionStatement {{
  subject: string;
  predicate: string;
  value: string;
}}

export interface ArchitectureOption {{
  title: string;
  description?: string;
  statements?: OptionStatement[];
}}

export interface CheckOptionRequest {{
  option: ArchitectureOption;
  subject?: string;
  domains?: string[];
  frameworks?: string[];
}}

export type CheckVerdictValue = "supports" | "violates" | "unassessed";

export interface CheckVerdict {{
  typed_id: string;
  check_id: string | null;
  verdict: CheckVerdictValue;
  message: string | null;
  matched_terms: string[];
  excerpt: string;
  source_ref: string;
  check_status?: "draft" | "validated" | null;
}}

export interface CheckResult {{
  verdicts: CheckVerdict[];
  summary: Record<CheckVerdictValue, number>;
  method: "deterministic-checks-v1";
  snapshot_id: string | null;
}}

/* ---- Contract 1.2: KB candidate cycle ------------------------------------ */

export type KbCandidateKind = "new_asset" | "amendment" | "rex" | "framework_ingestion";
export type KbAssetType = "principle" | "pattern" | "decision" | "control" | "glossary";
export type KbCandidateStatus = "proposed" | "checks_failed" | "in_review" | "accepted" | "rejected" | "published";
export type KbProductionMode = "human-authored" | "llm-proposed-human-approved" | "llm-derived";
export type KbReviewAction = "accept" | "amend" | "reject";

export interface KbCandidateReview {{
  reviewer: string;
  action: KbReviewAction;
  reason: string | null;
  at: string;
}}

export interface KbCandidateSubmission {{
  kind: KbCandidateKind;
  target_asset_id?: string | null;
  asset_type?: KbAssetType | null;
  domain?: string[];
  title: string;
  rationale?: string;
  proposed_content: string;
  source: {{
    system: "archinex" | "document-studio" | "mcp" | "cli-ingestion";
    engagement?: string | null;
    decision_id?: string | null;
    author?: string | null;
    contact?: string | null;
    production_mode?: KbProductionMode;
  }};
  evidence?: Array<{{ kind: "measure" | "audit" | "engagement" | "vendor-doc"; ref: string }}>;
}}

export interface KbCandidate extends KbCandidateSubmission {{
  id: string;
  asset_type: KbAssetType | null;
  domain: string[];
  rationale: string;
  status: KbCandidateStatus;
  checks: Array<{{ name: string; status: "pass" | "fail" | "warn"; detail: string }}>;
  review: KbCandidateReview | null;
  second_review_required: boolean;
  second_review: KbCandidateReview | null;
  assigned_owner: string | null;
  history: Array<{{ at: string; actor: string; event: string; [detail: string]: unknown }}>;
  promoted?: {{ path: string; asset_id: string; confidence: string }};
  published?: {{ snapshot_id: string | null; at: string }};
  created_at: string;
  updated_at: string;
}}

/* ---- Contract 1.3: regulatory coverage ------------------------------------ */

export interface FrameworkCoverage {{
  status: "covered" | "partial" | "missing";
  version: string | null;
  expected: number | null;
  present: number;
  validated: number;
  missing_ids: string[];
  declared_by: string | null;
  provisional?: boolean | null;
  manifest?: boolean;
}}

export type FrameworkCoverageMap = Record<string, FrameworkCoverage>;

export interface ApplicableFrameworksResponse {{
  status: "ok";
  engagement: string;
  applicable_frameworks: string[];
  count: number;
  coverage?: FrameworkCoverageMap;
}}

/* ---- Contract 1.4: identity of the acting expert --------------------------- */

export type KbRole = "kb:review" | "kb:evaluate" | "kb:maintain" | "kb:admin";

export interface KbMe {{
  handle: string;
  email: string | null;
  kb_roles: KbRole[];
  owned_domains: string[];
  pending_reviews: number;
}}

/* ---- Contract 1.5: review and solicitation --------------------------------- */

export type ReviewReason = "review" | "second_review" | "advice";

export interface ReviewInboxItem {{
  candidate_id: string;
  title: string;
  kind: string;
  asset_type?: string | null;
  domain: string[];
  reason: ReviewReason;
  waiting_since: string;
  due_at: string;
  message?: string | null;
  checks_failed: string[];
}}

export interface ReviewRequest {{
  id: number;
  candidate_id: string;
  requested_handle: string;
  kind: "second_review" | "advice";
  message: string | null;
  requested_by: string;
  due_at: string;
  status: "open" | "done" | "cancelled";
  created_at: string;
  closed_at: string | null;
}}

export interface KbComment {{ id: number; candidate_id: string; author: string; body: string; at: string }}

export type GovernanceEventType =
  | "candidate.submitted" | "candidate.assigned" | "review.requested" | "candidate.reviewed"
  | "candidate.commented" | "candidate.promoted" | "candidate.published" | "reminder.due"
  | "owners.updated" | "eval.updated" | "coverage.changed";

export interface GovernanceEvent {{
  id: number;
  at: string;
  type: GovernanceEventType;
  candidate_id: string | null;
  actor: string;
  recipients: string[];
  payload: Record<string, unknown>;
}}

export interface DomainOwner {{
  handle: string;
  email: string | null;
  roles: KbRole[];
  delegated: boolean;
}}

export interface DomainOwnersRegistry {{ owners: DomainOwner[]; domains: Record<string, string>; default_owner: string }}

/* ---- Contract 1.6: doctrine workshop and evaluations ------------------------ */

export interface AssetTemplateField {{
  name: string; required: boolean; type: string; values?: string[] | null; pattern?: string | null; help?: string | null;
}}

export interface AssetTemplate {{
  asset_type: string;
  fields: AssetTemplateField[];
  sections: Array<{{ heading: string; required: boolean }}>;
  next_id: string | null;
  skeleton: string;
  help: string;
}}

export interface CandidateDryRun {{
  checks: Array<{{ name: string; status: "pass" | "fail" | "warn"; detail: string }}>;
  would_be_status: "in_review" | "checks_failed";
  assigned_owner: string | null;
  second_review_required: boolean;
  asset_type: string | null;
  domain: string[];
}}

export type ExpectedVerdict = "violates" | "supports";

export interface ClauseVerdictView {{ check_id: string | null; verdict: ExpectedVerdict; matched_terms: string[] }}

export interface JudgeMetrics {{
  violation_recall: number; supports_recall: number; unexpected_violations: number; expected_violations: number;
}}

export interface ClauseSimulation {{
  asset_id: string;
  typed_id: string;
  clause_problems: Array<{{ clause: string | null; problems: string[] }}>;
  metrics: {{ cases: number; before: JudgeMetrics; after: JudgeMetrics }};
  regressions: string[];
  improvements: string[];
  cases: Array<{{
    case_id: string; title?: string; expected: ExpectedVerdict | null; before: ClauseVerdictView[];
    after: ClauseVerdictView[]; changed: boolean; regression: boolean; improvement: boolean;
  }}>;
  options: Array<{{ title: string; before: ClauseVerdictView[]; after: ClauseVerdictView[] }}>;
}}

export interface EvalCase {{
  id: string;
  sector?: string;
  subject?: string | null;
  frameworks?: string[];
  option: {{ title: string; description?: string }};
  expected: Record<string, ExpectedVerdict>;
  annotation_status: "proposed" | "validated" | "rejected";
  annotated_by: string | null;
  annotated_at: string | null;
}}

export interface EvalDataset {{ dataset: string; cases: EvalCase[]; validated: number; runs: Array<Record<string, unknown>> }}

export interface EvalRun extends JudgeMetrics {{
  id: number; dataset: string; at: string; run_by: string; cases: number; validated_cases: number;
  misses: Array<{{ case_id: string; typed_id: string; expected: string; got: string[] }}>;
}}

export type VerdictFeedbackKind = "wrong_violation" | "missed_violation" | "correct";

export interface VerdictFeedback {{
  id: number; at: string; reporter: string; typed_id: string; check_id: string | null;
  feedback: VerdictFeedbackKind; justification: string; status: "open" | "converted" | "dismissed";
  converted_to: string | null; option: {{ title: string; description?: string }}; subject?: string | null; frameworks: string[];
}}

/* ---- Contract 1.7: framework ingestion -------------------------------------- */

export type IngestionDecision = "" | "accept" | "amend" | "reject";

export interface IngestionRow {{
  requirement_id: string;
  title: string;
  source_ref?: string;
  domain?: string[];
  in_kb?: boolean;
  legal_text: string;
  proposed_links: string[];
  proposed_acceptance_criteria: string[];
  links_production_mode: "" | "llm-derived";
  proposed_terms: string[];      // contract 1.12: search terms (FR and EN) proposed by the client's model
  proposed_title_fr: string;
  terms: string[];               // the expert's own terms (amend); they replace the proposal
  title_fr: string;
  decision: IngestionDecision;
  links: string[];
  acceptance_criteria: string[];
  reviewer: string;
  comment: string;
  status: "pending" | "decided" | "applied" | "failed";
  result: string | null;
}}

export interface FrameworkIngestion {{
  id: number;
  framework: string;
  version: string;
  tag: string | null;
  source_name: string;
  source_sha256: string;
  status: "reviewing" | "partially_applied" | "applied";
  created_by: string;
  created_at: string;
  declaration_reset: boolean;
  requirements: IngestionRow[];
  decided: number;
  total: number;
}}

export interface IngestionApplyResult {{
  promoted: string[]; rejected: string[]; failed: Array<{{ requirement: string; reason: string }}>;
  skipped: string[]; status: FrameworkIngestion["status"]; applied_by: string;
}}

/* ---- Contract 1.8: promotion, publication and health ----------------------- */

export interface StorageStatus {{ persistent: boolean; mode: "normal" | "demo" }}

/** Responses of promote / publications carry ``warnings`` (``ephemeral-storage`` on the demo deployment). */
export interface WarningsMixin {{ warnings: Array<"ephemeral-storage"> }}

export interface KbHealth {{
  generated_at: string;
  assets: {{
    active: number; by_type: Record<string, number>; by_domain: Record<string, number>;
    unvalidated: {{ count: number; ids: string[] }};
  }};
  clauses: {{ total: number; draft: number; unassessed_verdict_share: number | null }};
  coverage: Record<string, {{
    status: "covered" | "partial" | "missing"; expected: number | null; present: number; validated: number;
    provisional: boolean | null;
  }}>;
  queue: {{
    by_status: Record<string, number>;
    per_owner: Record<string, {{ waiting: number; oldest_business_days: number }}>;
    overdue: Array<{{ candidate_id: string; owner: string | null; business_days: number }}>;
  }};
  evaluation: {{ cases: number; validated_cases: number; last_run: Record<string, unknown> | null }} | null;
  last_snapshot: {{ snapshot_id: string | null; generated_at: string | null }} | null;
  storage: StorageStatus;
}}

/* ---- Contract 1.9: semantic similarity (vectors computed by the client) ----- */

export type SimilarityZone = "strong" | "possible" | "weak" | "superseded";

export interface EmbeddingPendingItem {{
  ref: string; type: "principle" | "pattern" | "decision" | "control"; title: string;
  text: string; text_sha256: string; reason: "missing" | "stale";
}}

export interface EmbeddingDeposit {{
  model: string; model_version: string;
  items: Array<{{ ref: string; text_sha256: string; vector: number[]; language?: "fr" | "en" }}>;
}}

export interface SimilarKnowledgeRequest {{
  model: string; vector: number[]; query_text?: string; types?: string[]; domains?: string[]; top_k?: number;
  subject_fingerprint?: string;
}}

/** A proposal, never a decision: ``requires_confirmation`` is always true, whatever the score. */
export interface SimilarKnowledgeItem {{
  ref: string; type: string; title: string; score: number; scores: Record<string, number>;
  zone: SimilarityZone; requires_confirmation: true; stale: boolean; status: string; domain: string[];
  last_reviewed: string | null; review_by: string | null; validated_by: string[]; validated_at: string | null;
  superseded_by: string | null; assumptions: string[]; assumptions_documented: boolean;
  judgements?: PastJudgement[]; previous_confirmation_outdated?: boolean; reuse_summary?: Record<string, number>;
}}

/* ---- Contract 1.10: reuse of validated knowledge ----------------------------- */

export type AssumptionStatus = "holds" | "does_not_hold" | "unknown";
export type ReuseOutcome =
  | "reused" | "reused_with_exception" | "rejected_not_same" | "rejected_assumption_fails" | "deferred";

export interface AssumptionJudgement {{ text: string; status: AssumptionStatus; note?: string | null }}

/** ``assumptions`` must be exactly the asset's current ones; ``reused`` needs all of them to hold. */
export interface ReuseConfirmationRequest {{
  subject_fingerprint: string;   // SHA-256 (64 hex) of the normalised subject
  subject_label: string;         // short and anonymised
  matched_ref: string;
  model?: string;
  scores?: Record<string, number>;
  outcome: ReuseOutcome;
  assumptions: AssumptionJudgement[];
  comment?: string;              // required for reused_with_exception and rejected_not_same
}}

export interface ReuseConfirmation extends ReuseConfirmationRequest {{
  id: number; at: string; actor: string; assumptions_digest: string;
}}

export interface PastJudgement {{
  id: number; at: string; actor: string; outcome: ReuseOutcome; comment: string | null;
  assumptions_changed_since: boolean;
}}

/* ---- Contract 1.11: similarity evaluation (FR/EN dataset) -------------------- */

export type SimilarityFamily =
  | "cross_lingual" | "same_words_different_subject" | "same_topic_different_assumptions" | "out_of_base";
export type SimilarityRelation = "same_subject" | "related_not_same" | "same_topic_different_assumptions" | "unrelated";

export interface SimilarityCase {{
  id: string; family: SimilarityFamily; language: "fr" | "en"; query_text: string;
  expected: Array<{{ ref: string; relation: SimilarityRelation }}>;
  annotation_status: "proposed" | "validated" | "rejected"; annotated_by: string | null; annotated_at: string | null;
}}

export interface SimilarityRunBucket {{
  cases: number; same_subject_expected: number; recall_at_3: number | null;
  false_strong: number; reuse_trap_strong: number; missed_strong: number;
}}

/** ``false_strong`` is the number that matters: a wrong strong proposal is the failure the design exists to prevent. */
export interface SimilarityRun extends SimilarityRunBucket {{
  id: number; dataset: string; at: string; run_by: string; model: string; validated_cases: number;
  by_family: Record<SimilarityFamily, SimilarityRunBucket>; by_language: Record<"fr" | "en", SimilarityRunBucket>;
  sweep: Array<{{ threshold: number; false_strong: number; recall: number | null }}>;
  recommended_strong_threshold: number | null; recommendation_note: string;
  per_case: Array<{{ case_id: string; family: string; language: string; false_strong: string[];
                    reuse_trap_strong: string[]; missed_strong: string[];
                    top: Array<{{ ref: string; score: number; zone: SimilarityZone }}> }}>;
}}

export interface KbCandidateReviewRequest {{
  action: KbReviewAction;
  reviewer: string;
  reason?: string;
  amended_content?: string;
}}
"""


def main() -> None:
    schemas_dir = Path(__file__).parent.parent / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    envelope_schema = generate_envelope_schema()
    (schemas_dir / "envelope.schema.json").write_text(
        json.dumps(envelope_schema, indent=2) + "\n", encoding="utf-8"
    )
    print("Generated: schemas/envelope.schema.json")

    for filename, schema in (
        ("doctrine_context.schema.json", generate_doctrine_context_schema()),
        ("check_result.schema.json", generate_check_result_schema()),
        ("kb_candidate.schema.json", generate_kb_candidate_schema()),
        ("framework_coverage.schema.json", generate_framework_coverage_schema()),
        ("kb_me.schema.json", generate_kb_me_schema()),
        ("review_inbox.schema.json", generate_review_inbox_schema()),
        ("governance_event.schema.json", generate_governance_event_schema()),
        ("asset_template.schema.json", generate_asset_template_schema()),
        ("clause_simulation.schema.json", generate_simulation_schema()),
        ("eval_dataset.schema.json", generate_eval_dataset_schema()),
        ("framework_ingestion.schema.json", generate_framework_ingestion_schema()),
        ("kb_health.schema.json", generate_kb_health_schema()),
        ("similar_knowledge.schema.json", generate_similar_schema()),
        ("reuse_confirmation.schema.json", generate_reuse_confirmation_schema()),
        ("similarity_eval_run.schema.json", generate_similarity_eval_schema()),
    ):
        (schemas_dir / filename).write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        print(f"Generated: schemas/{filename}")

    ts_types = generate_typescript_types()
    (schemas_dir / "types.ts").write_text(ts_types, encoding="utf-8")
    print("Generated: schemas/types.ts")


if __name__ == "__main__":
    main()
    os._exit(0)

