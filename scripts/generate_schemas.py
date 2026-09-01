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


def generate_typescript_types() -> str:
    conf_union = " | ".join(f'"{c}"' for c in sorted(CONFIDENCE_LEVELS))
    subj_levels_union = " | ".join(f'"{lvl}"' for lvl in SUBJECT_LEVELS)
    conflict_kinds_union = " | ".join(f'"{k}"' for k in sorted(CONFLICT_KINDS))
    gap_types_union = " | ".join(f'"{g}"' for g in sorted(GAP_TYPES))
    stmt_statuses_union = " | ".join(f'"{s}"' for s in sorted(STATEMENT_STATUSES | {"contested", "under_review"}))

    return f"""/**
 * LLMOps MCP Tool Response Contract (schema_version: "1.0")
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
"""


def main() -> None:
    schemas_dir = Path(__file__).parent.parent / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    envelope_schema = generate_envelope_schema()
    (schemas_dir / "envelope.schema.json").write_text(
        json.dumps(envelope_schema, indent=2) + "\n", encoding="utf-8"
    )
    print("Generated: schemas/envelope.schema.json")

    ts_types = generate_typescript_types()
    (schemas_dir / "types.ts").write_text(ts_types, encoding="utf-8")
    print("Generated: schemas/types.ts")


if __name__ == "__main__":
    main()
    os._exit(0)

