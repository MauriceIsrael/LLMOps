/**
 * LLMOps MCP Tool Response Contract (schema_version: "1.14")
 * Generated automatically by scripts/generate_schemas.py. Do not edit manually.
 */

export type EnvelopeStatus = "ok" | "not_found" | "invalid_argument" | "error" | "unauthorized" | "unavailable";

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

/* ---- Contract 1.1: doctrine context & option judge ---------------------- */

export type DoctrineItemType = "principle" | "pattern" | "decision" | "control";

export interface DoctrineContextItem {
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
}

export interface DoctrineContext {
  items: DoctrineContextItem[];
  truncated: boolean;
  snapshot_id: string | null;
}

export interface DoctrineContextRequest {
  subject: string;
  domains?: string[];
  frameworks?: string[];
  phase?: string | null;
  max_items?: number;
  max_chars?: number;
}

export interface OptionStatement {
  subject: string;
  predicate: string;
  value: string;
}

export interface ArchitectureOption {
  title: string;
  description?: string;
  statements?: OptionStatement[];
}

export interface CheckOptionRequest {
  option: ArchitectureOption;
  subject?: string;
  domains?: string[];
  frameworks?: string[];
}

export type CheckVerdictValue = "supports" | "violates" | "unassessed";

export interface CheckVerdict {
  typed_id: string;
  check_id: string | null;
  verdict: CheckVerdictValue;
  message: string | null;
  matched_terms: string[];
  excerpt: string;
  source_ref: string;
  check_status?: "draft" | "validated" | null;
}

export interface CheckResult {
  verdicts: CheckVerdict[];
  summary: Record<CheckVerdictValue, number>;
  method: "deterministic-checks-v1";
  snapshot_id: string | null;
}

/* ---- Contract 1.2: KB candidate cycle ------------------------------------ */

export type KbCandidateKind = "new_asset" | "amendment" | "rex" | "framework_ingestion";
export type KbAssetType = "principle" | "pattern" | "decision" | "control" | "glossary";
export type KbCandidateStatus = "proposed" | "checks_failed" | "in_review" | "accepted" | "rejected" | "published";
export type KbProductionMode = "human-authored" | "llm-proposed-human-approved" | "llm-derived";
export type KbReviewAction = "accept" | "amend" | "reject";

export interface KbCandidateReview {
  reviewer: string;
  action: KbReviewAction;
  reason: string | null;
  at: string;
}

export interface KbCandidateSubmission {
  kind: KbCandidateKind;
  target_asset_id?: string | null;
  asset_type?: KbAssetType | null;
  domain?: string[];
  title: string;
  rationale?: string;
  proposed_content: string;
  source: {
    system: "archinex" | "document-studio" | "mcp" | "cli-ingestion";
    engagement?: string | null;
    decision_id?: string | null;
    author?: string | null;
    contact?: string | null;
    production_mode?: KbProductionMode;
  };
  evidence?: Array<{ kind: "measure" | "audit" | "engagement" | "vendor-doc"; ref: string }>;
}

export interface KbCandidate extends KbCandidateSubmission {
  id: string;
  asset_type: KbAssetType | null;
  domain: string[];
  rationale: string;
  status: KbCandidateStatus;
  checks: Array<{ name: string; status: "pass" | "fail" | "warn"; detail: string }>;
  review: KbCandidateReview | null;
  second_review_required: boolean;
  second_review: KbCandidateReview | null;
  assigned_owner: string | null;
  history: Array<{ at: string; actor: string; event: string; [detail: string]: unknown }>;
  promoted?: { path: string; asset_id: string; confidence: string };
  published?: { snapshot_id: string | null; at: string };
  created_at: string;
  updated_at: string;
}

/* ---- Contract 1.3: regulatory coverage ------------------------------------ */

export interface FrameworkCoverage {
  status: "covered" | "partial" | "missing";
  version: string | null;
  expected: number | null;
  present: number;
  validated: number;
  missing_ids: string[];
  declared_by: string | null;
  provisional?: boolean | null;
  manifest?: boolean;
}

export type FrameworkCoverageMap = Record<string, FrameworkCoverage>;

export interface ApplicableFrameworksResponse {
  status: "ok";
  engagement: string;
  applicable_frameworks: string[];
  count: number;
  coverage?: FrameworkCoverageMap;
}

/* ---- Contract 1.4: identity of the acting expert --------------------------- */

export type KbRole = "kb:review" | "kb:evaluate" | "kb:maintain" | "kb:admin";

export interface KbMe {
  handle: string;
  email: string | null;
  kb_roles: KbRole[];
  owned_domains: string[];
  pending_reviews: number;
}

/* ---- Contract 1.5: review and solicitation --------------------------------- */

export type ReviewReason = "review" | "second_review" | "advice";

export interface ReviewInboxItem {
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
}

export interface ReviewRequest {
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
}

export interface KbComment { id: number; candidate_id: string; author: string; body: string; at: string }

export type GovernanceEventType =
  | "candidate.submitted" | "candidate.assigned" | "review.requested" | "candidate.reviewed"
  | "candidate.commented" | "candidate.promoted" | "candidate.published" | "reminder.due"
  | "owners.updated" | "eval.updated" | "coverage.changed";

export interface GovernanceEvent {
  id: number;
  at: string;
  type: GovernanceEventType;
  candidate_id: string | null;
  actor: string;
  recipients: string[];
  payload: Record<string, unknown>;
}

export interface DomainOwner {
  handle: string;
  email: string | null;
  roles: KbRole[];
  delegated: boolean;
}

export interface DomainOwnersRegistry { owners: DomainOwner[]; domains: Record<string, string>; default_owner: string }

/* ---- Contract 1.6: doctrine workshop and evaluations ------------------------ */

export interface AssetTemplateField {
  name: string; required: boolean; type: string; values?: string[] | null; pattern?: string | null; help?: string | null;
}

export interface AssetTemplate {
  asset_type: string;
  fields: AssetTemplateField[];
  sections: Array<{ heading: string; required: boolean }>;
  next_id: string | null;
  skeleton: string;
  help: string;
}

export interface CandidateDryRun {
  checks: Array<{ name: string; status: "pass" | "fail" | "warn"; detail: string }>;
  would_be_status: "in_review" | "checks_failed";
  assigned_owner: string | null;
  second_review_required: boolean;
  asset_type: string | null;
  domain: string[];
}

export type ExpectedVerdict = "violates" | "supports";

export interface ClauseVerdictView { check_id: string | null; verdict: ExpectedVerdict; matched_terms: string[] }

export interface JudgeMetrics {
  violation_recall: number; supports_recall: number; unexpected_violations: number; expected_violations: number;
}

export interface ClauseSimulation {
  asset_id: string;
  typed_id: string;
  clause_problems: Array<{ clause: string | null; problems: string[] }>;
  metrics: { cases: number; before: JudgeMetrics; after: JudgeMetrics };
  regressions: string[];
  improvements: string[];
  cases: Array<{
    case_id: string; title?: string; expected: ExpectedVerdict | null; before: ClauseVerdictView[];
    after: ClauseVerdictView[]; changed: boolean; regression: boolean; improvement: boolean;
  }>;
  options: Array<{ title: string; before: ClauseVerdictView[]; after: ClauseVerdictView[] }>;
}

export interface EvalCase {
  id: string;
  sector?: string;
  subject?: string | null;
  frameworks?: string[];
  option: { title: string; description?: string };
  expected: Record<string, ExpectedVerdict>;
  annotation_status: "proposed" | "validated" | "rejected";
  annotated_by: string | null;
  annotated_at: string | null;
}

export interface EvalDataset { dataset: string; cases: EvalCase[]; validated: number; runs: Array<Record<string, unknown>> }

export interface EvalRun extends JudgeMetrics {
  id: number; dataset: string; at: string; run_by: string; cases: number; validated_cases: number;
  misses: Array<{ case_id: string; typed_id: string; expected: string; got: string[] }>;
}

export type VerdictFeedbackKind = "wrong_violation" | "missed_violation" | "correct";

export interface VerdictFeedback {
  id: number; at: string; reporter: string; typed_id: string; check_id: string | null;
  feedback: VerdictFeedbackKind; justification: string; status: "open" | "converted" | "dismissed";
  converted_to: string | null; option: { title: string; description?: string }; subject?: string | null; frameworks: string[];
}

/* ---- Contract 1.7: framework ingestion -------------------------------------- */

export type IngestionDecision = "" | "accept" | "amend" | "reject";

export interface IngestionRow {
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
}

export interface FrameworkIngestion {
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
}

export interface IngestionApplyResult {
  promoted: string[]; rejected: string[]; failed: Array<{ requirement: string; reason: string }>;
  skipped: string[]; status: FrameworkIngestion["status"]; applied_by: string;
}

/* ---- Contract 1.8: promotion, publication and health ----------------------- */

export interface StorageStatus { persistent: boolean; mode: "normal" | "demo" }

/** Responses of promote / publications carry ``warnings`` (``ephemeral-storage`` on the demo deployment). */
export interface WarningsMixin { warnings: Array<"ephemeral-storage"> }

export interface KbHealth {
  generated_at: string;
  assets: {
    active: number; by_type: Record<string, number>; by_domain: Record<string, number>;
    unvalidated: { count: number; ids: string[] };
  };
  clauses: { total: number; draft: number; unassessed_verdict_share: number | null };
  coverage: Record<string, {
    status: "covered" | "partial" | "missing"; expected: number | null; present: number; validated: number;
    provisional: boolean | null;
  }>;
  queue: {
    by_status: Record<string, number>;
    per_owner: Record<string, { waiting: number; oldest_business_days: number }>;
    overdue: Array<{ candidate_id: string; owner: string | null; business_days: number }>;
  };
  evaluation: { cases: number; validated_cases: number; last_run: Record<string, unknown> | null } | null;
  last_snapshot: { snapshot_id: string | null; generated_at: string | null } | null;
  storage: StorageStatus;
}

/* ---- Contract 1.9: semantic similarity (vectors computed by the client) ----- */

export type SimilarityZone = "strong" | "possible" | "weak" | "superseded";

export interface EmbeddingPendingItem {
  ref: string; type: "principle" | "pattern" | "decision" | "control"; title: string;
  text: string; text_sha256: string; reason: "missing" | "stale";
}

export interface EmbeddingDeposit {
  model: string; model_version: string;
  items: Array<{ ref: string; text_sha256: string; vector: number[]; language?: "fr" | "en" }>;
}

export interface SimilarKnowledgeRequest {
  model: string; vector: number[]; query_text?: string; types?: string[]; domains?: string[]; top_k?: number;
  subject_fingerprint?: string;
}

/** A proposal, never a decision: ``requires_confirmation`` is always true, whatever the score. */
export interface SimilarKnowledgeItem {
  ref: string; type: string; title: string; score: number; scores: Record<string, number>;
  zone: SimilarityZone; requires_confirmation: true; stale: boolean; status: string; domain: string[];
  last_reviewed: string | null; review_by: string | null; validated_by: string[]; validated_at: string | null;
  superseded_by: string | null; assumptions: string[]; assumptions_documented: boolean;
  judgements?: PastJudgement[]; previous_confirmation_outdated?: boolean; reuse_summary?: Record<string, number>;
}

/* ---- Contract 1.10: reuse of validated knowledge ----------------------------- */

export type AssumptionStatus = "holds" | "does_not_hold" | "unknown";
export type ReuseOutcome =
  | "reused" | "reused_with_exception" | "rejected_not_same" | "rejected_assumption_fails" | "deferred";

export interface AssumptionJudgement { text: string; status: AssumptionStatus; note?: string | null }

/** ``assumptions`` must be exactly the asset's current ones; ``reused`` needs all of them to hold. */
export interface ReuseConfirmationRequest {
  subject_fingerprint: string;   // SHA-256 (64 hex) of the normalised subject
  subject_label: string;         // short and anonymised
  matched_ref: string;
  model?: string;
  scores?: Record<string, number>;
  outcome: ReuseOutcome;
  assumptions: AssumptionJudgement[];
  comment?: string;              // required for reused_with_exception and rejected_not_same
}

export interface ReuseConfirmation extends ReuseConfirmationRequest {
  id: number; at: string; actor: string; assumptions_digest: string;
}

export interface PastJudgement {
  id: number; at: string; actor: string; outcome: ReuseOutcome; comment: string | null;
  assumptions_changed_since: boolean;
}

/* ---- Contract 1.11: similarity evaluation (FR/EN dataset) -------------------- */

export type SimilarityFamily =
  | "cross_lingual" | "same_words_different_subject" | "same_topic_different_assumptions" | "out_of_base";
export type SimilarityRelation = "same_subject" | "related_not_same" | "same_topic_different_assumptions" | "unrelated";

export interface SimilarityCase {
  id: string; family: SimilarityFamily; language: "fr" | "en"; query_text: string;
  expected: Array<{ ref: string; relation: SimilarityRelation }>;
  annotation_status: "proposed" | "validated" | "rejected"; annotated_by: string | null; annotated_at: string | null;
}

export interface SimilarityRunBucket {
  cases: number; same_subject_expected: number; recall_at_3: number | null;
  false_strong: number; reuse_trap_strong: number; missed_strong: number;
}

/** ``false_strong`` is the number that matters: a wrong strong proposal is the failure the design exists to prevent. */
export interface SimilarityRun extends SimilarityRunBucket {
  id: number; dataset: string; at: string; run_by: string; model: string; validated_cases: number;
  by_family: Record<SimilarityFamily, SimilarityRunBucket>; by_language: Record<"fr" | "en", SimilarityRunBucket>;
  sweep: Array<{ threshold: number; false_strong: number; recall: number | null }>;
  recommended_strong_threshold: number | null; recommendation_note: string;
  per_case: Array<{ case_id: string; family: string; language: string; false_strong: string[];
                    reuse_trap_strong: string[]; missed_strong: string[];
                    top: Array<{ ref: string; score: number; zone: SimilarityZone }> }>;
}

export interface KbCandidateReviewRequest {
  action: KbReviewAction;
  reviewer: string;
  reason?: string;
  amended_content?: string;
}
