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


def generate_typescript_types() -> str:
    conf_union = " | ".join(f'"{c}"' for c in sorted(CONFIDENCE_LEVELS))
    subj_levels_union = " | ".join(f'"{lvl}"' for lvl in SUBJECT_LEVELS)
    conflict_kinds_union = " | ".join(f'"{k}"' for k in sorted(CONFLICT_KINDS))
    gap_types_union = " | ".join(f'"{g}"' for g in sorted(GAP_TYPES))
    stmt_statuses_union = " | ".join(f'"{s}"' for s in sorted(STATEMENT_STATUSES | {"contested", "under_review"}))

    return f"""/**
 * LLMOps MCP Tool Response Contract (schema_version: "1.4")
 * Generated automatically by scripts/generate_schemas.py. Do not edit manually.
 */

export type EnvelopeStatus = "ok" | "not_found" | "invalid_argument" | "error" | "unauthorized";

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
  provenance?: AssetProvenance;
  supersedes?: Array<{{ id: string; title?: string }}>;
  superseded_by?: Array<{{ id: string; title?: string }}>;
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
    ):
        (schemas_dir / filename).write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        print(f"Generated: schemas/{filename}")

    ts_types = generate_typescript_types()
    (schemas_dir / "types.ts").write_text(ts_types, encoding="utf-8")
    print("Generated: schemas/types.ts")


if __name__ == "__main__":
    main()
    os._exit(0)

