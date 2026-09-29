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


def generate_typescript_types() -> str:
    conf_union = " | ".join(f'"{c}"' for c in sorted(CONFIDENCE_LEVELS))
    subj_levels_union = " | ".join(f'"{lvl}"' for lvl in SUBJECT_LEVELS)
    conflict_kinds_union = " | ".join(f'"{k}"' for k in sorted(CONFLICT_KINDS))
    gap_types_union = " | ".join(f'"{g}"' for g in sorted(GAP_TYPES))
    stmt_statuses_union = " | ".join(f'"{s}"' for s in sorted(STATEMENT_STATUSES | {"contested", "under_review"}))

    return f"""/**
 * LLMOps MCP Tool Response Contract (schema_version: "1.1")
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
    ):
        (schemas_dir / filename).write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        print(f"Generated: schemas/{filename}")

    ts_types = generate_typescript_types()
    (schemas_dir / "types.ts").write_text(ts_types, encoding="utf-8")
    print("Generated: schemas/types.ts")


if __name__ == "__main__":
    main()
    os._exit(0)

