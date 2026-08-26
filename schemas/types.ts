/**
 * LLMOps MCP Tool Response Contract (schema_version: "1.0")
 * Generated automatically by scripts/generate_schemas.py. Do not edit manually.
 */

export type EnvelopeStatus = "ok" | "not_found" | "invalid_argument" | "error" | "unauthorized";

export interface ResponseEnvelope<T = any> {
  status: EnvelopeStatus;
  count: number;
  data: T;
  reason?: string;
}

export interface Asset {
  id: string;
  title: string;
  kind?: string;
  type?: string;
  status: string;
  confidence: "verified" | "vendor-stated" | "assumed";
  domain?: string;
  phase?: string;
  owner?: string;
  last_reviewed?: string;
  path?: string;
  content?: string;
}

export interface Statement {
  id: string;
  subject: string;
  predicate: string;
  value: string;
  confidence: "verified" | "designed" | "stated-by-client" | "assumed";
  author?: string;
  role?: string;
  status: "active" | "contested" | "under_review";
  based_on?: Array<{ id: string }>;
}

export interface SubjectBoardItem {
  id: string;
  subject: string;
  level: "L0_named" | "L1_framed" | "L2_decomposed" | "L3_decided" | "L4_specified";
  active_statements_count: number;
  stalled?: boolean;
}

export interface Conflict {
  id: string;
  kind: string;
  detail: string;
  status: "open" | "arbitrated";
  origin: "declared" | "detected";
}

export interface RenderPayload {
  engagement: string;
  status: "COMPLETE" | "PROVISIONAL";
  is_provisional: boolean;
  active_statements: Statement[];
  open_conflicts: Conflict[];
  unripe_subjects: SubjectBoardItem[];
  maturity_board: SubjectBoardItem[];
}

export interface GraphSummary {
  schema_version: "1.0";
  knowledge: {
    dataset: string;
    node_counts: Record<string, number>;
  };
  engagements: Array<{
    id: string;
    node_counts: Record<string, number>;
  }>;
}
