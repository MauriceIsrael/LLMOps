/**
 * LLMOps MCP Tool Response Contract (schema_version: "1.0")
 * Generated automatically by scripts/generate_schemas.py. Do not edit manually.
 */

export type EnvelopeStatus = "ok" | "not_found" | "invalid_argument" | "error" | "unauthorized";

export type ConfidenceLevel = "assumed" | "designed" | "stated-by-client" | "vendor-stated" | "verified";

export type SubjectMaturityLevel = "L0_named" | "L1_framed" | "L2_decomposed" | "L3_decided" | "L4_specified";

export type ConflictKind = "contradiction" | "principle_violation" | "stale_basis";

export type GapType = "G1_empty_section" | "G2_unanswered_blocking" | "G3_principle_unaddressed";

export type StatementStatus = "active" | "contested" | "proposed" | "superseded" | "under_review" | "withdrawn";

export interface ResponseEnvelope<T = any> {
  status: EnvelopeStatus;
  count: number;
  data: T;
  reason?: string;
}

export interface AssetProvenance {
  document?: string;
  version?: string;
  section?: string;
  text_sha256?: string;
}

export interface Asset {
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
  supersedes?: Array<{ id: string; title?: string }>;
  superseded_by?: Array<{ id: string; title?: string }>;
}

export interface Statement {
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
  based_on?: Array<{ id: string; resolved?: boolean; note?: string }>;
}

export interface SubjectBoardItem {
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
}

export interface Conflict {
  id: string;
  kind: ConflictKind;
  detail: string;
  status: "open" | "arbitrated";
  origin: "declared" | "detected";
  statement_ids?: string[];
  resolution?: string;
  arbitrated_by?: string;
}

export interface Uncertainty {
  id: string;
  text: string;
  author?: string;
  role?: string;
}

export interface RenderPayload {
  engagement: string;
  status: "provisional" | "final";
  is_provisional: boolean;
  active_statements: Statement[];
  open_conflicts: Conflict[];
  uncertainties?: Uncertainty[];
  unripe_subjects: string[];
  maturity_board: SubjectBoardItem[];
}

export interface SealedSnapshotEnvelope {
  snapshot_id: string;
  created_at: string;
  source_revision: string;
  payload_sha256: string;
  schema_version: "1.0";
  applicability_index: Record<string, { rules?: string[]; layers?: string[]; domains?: string[] }>;
  assets: Asset[];
  glossary: Array<{ term: string; definition: string; context?: string }>;
  engagements?: Array<{
    id: string;
    render_payload: RenderPayload;
  }>;
}

export interface ExternalRef {
  system: "KH" | "AS" | string;
  id: string;
  version: string;
  sha256?: string;
}

export interface PatternSuggestion {
  pattern_id: string;
  typed_id: string;
  title: string;
  summary: string;
  applicability: string;
  confidence: ConfidenceLevel;
  external_ref: string;
  trade_offs?: string[];
}

export interface SuggestionCatalogContext {
  issue_kind: "SPOF" | "LATENCY_RISK" | "SECURITY_ISOLATION" | "RESILIENCE" | string;
  domain?: string;
  context_tags?: string[];
}

export interface SuggestionCatalogPort {
  getSuggestions(context: SuggestionCatalogContext): Promise<ResponseEnvelope<{
    context: SuggestionCatalogContext;
    suggestions: PatternSuggestion[];
  }>>;
}
