"""Contract version exposed by the server (see docs/VERSIONING.md).

Minor versions only add interfaces or optional fields:

* ``1.0`` — reference contract (frozen in ``tests/contract/frozen/``).
* ``1.1`` — doctrine context (``get_doctrine_context``, ``GET /api/knowledge/context``)
  and option judge (``check_option``, ``POST /api/knowledge/check``).
* ``1.2`` — KB candidate cycle (``submit_kb_candidate``, ``list_kb_candidates``,
  ``get_kb_candidate``, ``review_kb_candidate``, ``/api/knowledge/candidates``) and the
  optional ``candidate_id`` in the suggestion response.
* ``1.3`` — regulatory coverage: ``get_framework_coverage`` and the optional ``coverage``
  field of ``GET /api/compliance/frameworks/applicable``.
* ``1.4`` — identity of the acting expert (``X-Actor-Email`` with a ``kb:delegate`` token,
  ``get_kb_me``, ``GET /api/knowledge/me``); reviews by that expert are authorised by the
  owners registry.
* ``1.5`` — review and solicitation of experts: ``get_review_inbox``, ``assign_kb_candidate``,
  ``request_kb_review``, ``comment_kb_candidate``, ``list_domain_owners`` and the REST routes
  ``/api/knowledge/reviews/inbox``, ``.../candidates/{id}/{assign,request-review,comments}``,
  ``/api/knowledge/events``, ``/api/knowledge/owners``.
* ``1.6`` — doctrine workshop and evaluations (REST): ``/api/knowledge/templates/{type}``,
  ``/api/knowledge/candidates/validate``, ``/api/knowledge/checks/simulate``,
  ``/api/knowledge/evals/{dataset}`` (cases, runs) and ``/api/knowledge/verdict-feedback``.
* ``1.7`` — framework ingestion through the API (REST): ``/api/frameworks/ingestions`` (upload,
  rows, link proposals, apply) and ``/api/frameworks/{fw}/coverage-declaration``.
* ``1.8`` — promotion, publication and health (REST): ``POST /api/knowledge/candidates/{id}/promote``,
  ``POST /api/knowledge/publications`` and ``GET /api/knowledge/health``.
* ``1.9`` — semantic similarity over vectors computed by the client (REST):
  ``/api/knowledge/embeddings/pending``, ``PUT /api/knowledge/embeddings``, ``POST /api/knowledge/similar``.
* ``1.10`` — reuse of validated knowledge (REST): ``/api/knowledge/reuse-confirmations``; the similarity
  search remembers the judgements of a subject; optional ``assumptions`` and ``review_by`` in the front matter.
* ``1.11`` — similarity evaluation (REST): ``/api/knowledge/similarity-evals/{dataset}`` (FR/EN cases, annotation,
  runs with vectors supplied by the client, threshold sweep).
* ``1.12`` — bilingual search metadata at framework ingestion: optional ``terms`` and ``title_fr`` in the
  link proposals and in the row decisions (applied to the control only when the expert accepts or amends).
* ``1.13`` — deprecation of the engagement part (L4): ``Deprecation`` header, ``deprecation`` envelope field and a
  log line on the elicitation/arbitration routes and the engagement MCP tools; ``CONFLICT_DETECTION_MODE`` flag.
  No change of behaviour or shape.
* ``1.14`` — **cancels the 1.13 deprecation** (K10, ADR-KH-01 A10): the Hub holds two bases, knowledge and engagement,
  so the elicitation/arbitration routes and the engagement MCP tools are in service again. They no longer carry the
  ``Deprecation`` header nor the ``deprecation`` field; behaviour and shapes are those of 1.13. Authorisation answers
  ``403`` instead of ``500`` (K9).
* ``1.15`` — snapshot channel aligned on the suite (ADR-KH-01 D6-D8). K1: every seal follows the ``canonical-json v1``
  profile, so ``payload_sha256`` of the sealed snapshot and the ``checksum`` of the conformity snapshot are
  **recomputed** (same shapes, new values; a value the profile refuses fails the export). K2: additive channel
  envelope on the sealed snapshot (``emitter``, ``checksum``, ``rebuiltByEmitterTest``, ``regenerate``,
  ``is_provisional``, ``provisional_reasons``). K3: per-element ``revision``, ``knowledge_ref``, ``content`` and
  ``content_sha256`` in the sealed snapshot, a version ledger, ``GET /api/knowledge/assets/{id}`` and optional
  ``version`` / ``snapshot`` on ``get_asset`` (resolution from a verified sealed snapshot).
* ``1.16`` — managed engagements (K14, ADR-KH-01 A11): roles (reader, contributor, decider, admin), membership and
  audit; ``POST /api/engagements``, ``GET|PUT /api/engagements/{id}/members``, ``GET /api/engagements/{id}/me``,
  ``GET /api/engagements/{id}/audit``. A managed engagement is closed to everyone but its members in every environment;
  a refusal by role answers ``403`` with ``action`` and ``reason``. Unmanaged engagements behave as before.
* ``1.17`` — writing into a managed engagement (K15): ``POST /api/engagements/{id}/{subjects, subjects/{name}/maturity,
  statements, statements/{id}/assert, statements/{id}/withdraw, questions, questions/{id}/answers, requirements,
  conflicts/{id}/arbitrate}``. Contributions are proposed; only a decider who is not the author asserts.
* ``1.18`` — the sealed snapshot of an engagement (K11): ``POST|GET /api/engagements/{id}/exports`` and
  ``GET /api/engagements/{id}/exports/{snapshotId}``, schema ``schemas/engagement_snapshot.schema.json``. The Hub is the
  emitter of the channel; the export is refused (nothing produced) when its verification fails.
* ``1.19`` — decisions in the engagement base (K16): ``POST /api/engagements/{id}/decisions`` and ``…/decisions/{id}/{assert,
  withdraw}``; a subject is decided (``L3_decided``, ``L4_specified``) only on an **asserted decision** (was: an asserted
  statement). The snapshot gains ``decisions`` (``schemaVersion`` ``1.1``).
* ``1.20`` — importing an engagement from another system (K12): ``POST /api/engagements/{id}/import`` (role ``admin``,
  new action ``import``), ``?dry_run=true`` writes nothing. Provenance kept, nothing asserted in the batch's name; imported
  items are flagged ``imported`` in the snapshot (``schemaVersion`` ``1.2``).
* ``1.21`` — facts carried by decisions (K18): ``facts: [{key, value, source_excerpt}]`` on ``POST /api/engagements/{id}/decisions``
  (and on imported decisions), keys defined by the vocabulary ``data/kb/vocabulary/facts.yaml`` (sealed knowledge snapshot section
  ``fact_vocabulary``), refusals ``UNKNOWN_FACT_KEY`` / ``FACT_TYPE``; ``GET /api/engagements/{id}/facts`` (asserted decisions
  only); the engagement snapshot gains ``facts`` and each decision its ``facts`` (``schemaVersion`` ``1.3``).
* ``1.22`` — question triggers attached to the elements of the knowledge base (K19): declarative rules
  ``data/kb/triggers/TRG-*.yaml`` (``when`` conditions on the facts vocabulary of 1.21, ``question``, ``rationale``,
  ``initial_level``, ``suggested_role``, ``mandatory``), validated at ingestion and at publication, versioned and citable
  (``trigger:<id>``). The sealed knowledge snapshot gains the section ``question_triggers`` (own ``content_sha256``, outside
  ``payload_sha256``). No route: the rules are read in the snapshot.
* ``1.23`` — the cascade engine (K20): an asserted decision opens more precise subjects (``origin: derived``) from the question
  triggers of the engagement's **pinned** knowledge snapshot; truth maintenance (``foundation_contested``, never deleted);
  ``GET /api/engagements/{id}/lineage``, ``PUT /api/engagements/{id}/kb-pin`` (admin, new action ``pin``); asserting or
  withdrawing a decision, and an import, answer with a ``cascade`` report; a mandatory question is closed by a decider with a
  justification. The engagement snapshot gains ``lineage`` and the ``origin`` of each subject (``schemaVersion`` ``1.4``).
* ``1.24`` — rule adjustments per engagement (K21): ``POST /api/engagements/{id}/rules/{trigger_id}/{disable,enable}`` (a decider
  deactivates a reference rule with a mandatory justification, audited), ``POST /api/engagements/{id}/rules`` (a contributor
  proposes a local rule, same schema and checks as K19), ``…/rules/{id}/{assert,withdraw}`` (a decider other than the author
  asserts), ``GET /api/engagements/{id}/rules``. The engine reads the pinned base minus deactivations plus asserted local rules;
  the engagement snapshot gains ``rule_adjustments`` and the ``scope`` of each lineage item (``schemaVersion`` ``1.5``).
* ``1.25`` — local multilingual semantic search (issue #94): the Hub encodes with a local model on the processor
  (``intfloat/multilingual-e5-small`` through ``fastembed``, files pinned by SHA-256 in ``data/models/``, never a network
  call at query time). ``GET /health`` gains ``embedding {model, version, sha256, local: true, status}``; the doctrine
  context gains, per item, ``relevant``, ``semantic_relevance``, ``combined_relevance`` and ``relevance_method``, and
  ``relevance_method`` / ``embedding`` for the package (lexical ranking unchanged when the model is absent or
  ``KB_EMBEDDINGS=off``); ``POST /api/knowledge/similar`` encodes ``query_text`` itself when no ``vector`` is sent
  (``encoded_by``, ``409 model-mismatch``); a publication indexes the active assets (``embedding_index`` in its response)
  and the sealed snapshot declares ``embedding_model`` and ``embedding_index`` (outside ``payload_sha256``).
* ``1.26`` — decision on each check clause (issues #101, #105): a clause carries its own ``status``
  (``draft|validated|rejected``) and ``review {by, at, decision, comment}``; only ``validated`` blocks, ``rejected`` is
  never evaluated; ``checks_status`` becomes their aggregate (``draft|partial|validated``). Promoting a candidate never
  validates a clause (an unchanged clause keeps its decision, any other is a draft). ``GET /api/knowledge/checks``
  lists the clauses (``may_decide``, ``mandatory_without_clause``, ``pending_publication``);
  ``PATCH /api/knowledge/assets/{asset_id}/checks/{check_id}`` decides (``validate|amend|reject``, owner of the domain
  or ``kb:maintain``); decisions are appended to ``data/kb/clause-decisions.jsonl`` and taken into account by the next
  publication (CHANGELOG, ``clause_decisions`` in its response).
* ``1.27`` — the decision on each requirement of an engagement, and the requirements a subject carries (the sealed engagement
  snapshot is the content model for traceability): ``POST /api/engagements/{id}/requirements/{requirement_id}/disposition``
  (a contributor proposes ``deliberated``, ``evacuated`` with its motive or ``clarification_needed`` with the question for the
  client), ``…/disposition/assert`` (a decider other than the author) and ``…/disposition/withdraw``;
  ``POST /api/engagements/{id}/subjects/{name}/requirements`` (``add`` / ``remove``) and an optional ``requirement_ids`` on
  ``POST …/subjects``. A requirement decided ``evacuated`` or ``clarification_needed`` cannot be carried by a subject (``409``).
  The engagement snapshot gains, optionally, ``requirements[].disposition`` and ``subjects[].requirement_ids``
  (``schemaVersion`` ``1.6``); an engagement that uses neither is sealed as before. Nothing is exported when a decision to
  deliberate has no subject, or an evacuation no motive.

* ``1.28`` — doctrine explorer and asset history (issues Archinex #95, LLMOps #108):
  ``GET /api/knowledge/publications`` lists published snapshots with dates, added/revised/removed
  assets, entry path (``framework_ingestion``, ``doctrine_workshop``, ``amendment``, ``initial_baseline``)
  with source SHA-256 and version, and reviewers; ``GET /api/knowledge/assets/{id}/history`` returns successive
  revisions (date, snapshot, author, reviewers, change summary), entry path, initial date, validators,
  and clause decisions; ``list_frameworks`` enriched with ingested source, SHA-256, and associated publications.
* ``1.29`` — trigger rules and facts-vocabulary keys in the candidate cycle, and their review (K22): candidate ``asset_type``
  ``trigger`` and ``fact_key`` (``source.system`` ``kb-extraction``); ``GET /api/knowledge/triggers``,
  ``POST /api/knowledge/triggers/{validate,preview}``, ``POST /api/knowledge/candidates/{id}/merge-key``; offline command
  ``kb extract-triggers``.

* ``1.30`` — honest conformity snapshot (K6, issue #43): ``GET /api/compliance/conformity-snapshot`` no longer emits
  ``verified`` (a presence in the graph is a declared coverage: ``allocated``), evidence carries its real origin
  (``source: knowledge-hub``), and ``sourceSystem`` is fixed to ``knowledge-hub``: ``?source_system=`` / ``X-Source-System``
  with another value is refused (``400 invalid_argument``). The Hub verifies nothing (ADR-KH-01 D2).

* ``1.31`` — requirement → control coverage in the engagement snapshot (K17, issue #65; schema ``1.7``): section
  ``compliance {origin, kb_snapshot, items, unresolved}``. For each requirement and each control it was matched to
  (resolved in the pinned knowledge snapshot), ``status`` is ``allocated`` (an **asserted** decision cites the control or an
  asset that implements it), ``proposed`` (only a proposed decision does) or ``uncovered``. The Hub verifies nothing:
  ``verified`` does not exist and ``origin`` is always ``knowledge-hub``. The verification refuses a status that its
  decisions do not support (``COVERAGE_STATUS``) and any dangling reference. No route changes.

* ``1.32`` — the knowledge base holds no programme (K13, issue #51): the ``anonymization`` check of the candidate cycle and the
  ``subject_label`` of the reuse journal share one definition of a programme anchor
  (``pipelines/kb_candidates/anchors.py``): engagement identifier (registered, working base, or the one the candidate comes
  from), e-mail address (masked in the result), member handle, IP address or CIDR, denylisted name, and the front matter fields
  ``source_engagement`` / ``engagement`` / ``client`` / ``site``. An anchor fails the check (``checks_failed``), the message names
  what was found, and a refused reuse confirmation writes nothing. PAT-008, which still carried such an anchor, is cleaned
  (revision 2). No route or response shape changes.

* ``1.33`` — channel of proposals from the suite to the Hub (K7, issue #44; amendment KH-1 of ADR-SUITE-05): a suite application
  never calls the Hub, it **publishes** a sealed snapshot of proposals (``schemas/proposal_snapshot.schema.json``, suite envelope,
  canonical-json v1 seal; candidate type ``ExtractedCandidate`` with destination ``knowledge-hub-reference`` and the proposal in
  ``proposal``) and the Hub **reads** it: ``kb import-proposals <snapshot> [--dry-run]`` and ``POST
  /api/knowledge/proposals/import`` (``?dry_run=1``; for the clients that carry the file, not for the suite). Every proposal becomes a
  candidate of the ordinary cycle with its provenance (``source.system``, ``source.snapshot_id``, ``source.snapshot_checksum``,
  ``source.candidate_ref``); an altered snapshot is refused whole (``400``, ``problems``); reading it twice creates nothing twice
  (``skipped``). ``source.system`` accepts ``architecture-studio`` and ``requirements-intake``.

* ``1.34`` — capitalisation of a local rule toward the reference base (K21 point 4, issue #70): ``POST
  /api/engagements/{id}/rules/{trigger_id}/capitalise`` (role ``decide``; body ``{asset}``, the element of the base that carries
  the rule) returns the **sealed snapshot of proposals** of the channel K7 (``sourceSystem`` ``hub-engagement``,
  ``schemas/proposal_snapshot.schema.json``), never a direct write; a maintainer reads it with ``kb import-proposals`` and a
  person reviews the candidate. ``TRG-local-x`` becomes ``TRG-x``; a free text that still carries a programme anchor (K13) is
  refused with ``anchors_found``. Proposal ``asset_type`` accepts ``trigger`` and ``fact_key``; ``source.system`` accepts
  ``hub-engagement``.
* ``1.35`` — requirement → control coverage also from the chain the engagement declares (K17, issue #123): a requirement carried by a
  subject reaches the controls that an asset cited by a decision on that subject implements in the pinned knowledge snapshot, without
  any matching of text. Such rows carry ``basis: "declared_by_decision"`` (engagement snapshot ``schemaVersion`` ``1.8``); the rows
  already produced by ``matched_controls`` are unchanged. A typed key in ``based_on`` (``decision:ADR-0001``) is read as the asset it
  designates. No route is added or changed.
* ``1.36`` — governance freshness monitoring (issue #131), multilingual FR/EN doctrine matching (issue #132), and RFP coverage gap analytics (issue #133):
  ``GET /api/knowledge/freshness`` (MCP tool ``get_kb_freshness``), enriched bilingual glossary synonyms and clause term expansion (``expand_terms``,
  ``expand_clause_terms``), and RFP coverage blind spots analytics ``GET /api/rfp/coverage-gaps``, ``POST /api/rfp/coverage-gaps`` (MCP tool
  ``get_rfp_coverage_gaps``, and ``coverage_gaps`` in compliance matrix). K17 decision subject verification fix for matched controls (issue #127).
* ``1.37`` — expert authentication and fine-grained RBAC for KB governance (issue #7): EdDSA (Ed25519) signed actor assertions with published
  JWKS (RFC 8037) alongside the static tokens, anti-replay protection with mandatory unique ``jti``, immediate token and actor revocation (JTI, handle, email),
  domain-scoped roles, temporary delegations lifecycle (``kb:review``, ``kb:evaluate``), strict separation of duties (authors cannot review/self-validate
  their contributions), and access audit logging (``kb_access_audit``). MCP tools: ``list_kb_delegations``, ``create_kb_delegation``,
  ``revoke_kb_delegation``, ``revoke_kb_auth``, ``get_kb_audit``. REST routes: ``GET /.well-known/jwks.json``, ``GET|POST /api/knowledge/delegations``,
  ``POST /api/knowledge/delegations/{id}/revoke``, ``POST /api/knowledge/auth/revoke``, ``GET /api/knowledge/audit``.
* ``1.38`` — judge reliability (issues #106, #85), additive fields only: the doctrine context never drops a control of a required
  framework (``max_items`` caps the other doctrine; ``required_total`` and ``omitted_required`` in the response), and the knowledge
  health reports whether the compiled graph the judge reads still describes the knowledge base files (``compiled_base``; ``kb check``
  on the command line). Assets in the graph carry the fingerprint of their whole source file (``file_sha256``).
* ``1.39`` — identity and rights of the people who act (issues #144, #90, #91). Strict identity mode ``LLMOPS_REQUIRE_SIGNED_ACTOR``: the raw
  ``X-Actor-Email`` header is refused (401 ``signed_actor_required``, audited) and only a signed assertion names a person. The trusted public keys are
  declared by ``ARCHINEX_JWKS``, ``ARCHINEX_JWKS_FILE`` or ``ARCHINEX_JWKS_URL`` (fail closed; a named ``kid`` that is not declared is ``unknown_key``);
  an assertion lives at most ``ARCHINEX_ASSERTION_MAX_TTL`` seconds (default 900, ``lifetime_too_long``) with a clock tolerance of
  ``ARCHINEX_CLOCK_SKEW`` seconds (default 30). ``POST /api/frameworks/{fw}/coverage-declaration`` requires the owner of the framework's primary domain
  (or ``kb:maintain``, or the review role on that domain) and is audited. Applying a framework ingestion refuses (409 ``separation_of_duties``) the
  mandatory controls the applying maintainer decided. No route is added.

* ``1.40`` — conformity snapshot made honest and reproducible (issues #148, #149), no route added. ``GET /api/compliance/conformity-snapshot``:
  ``snapshotId`` now derives from the ``checksum`` (``kh-<engagement>-<framework>-<12 hex>``, as the engagement snapshot does) instead of the clock,
  so the same state gives the same identifier; a control that no asset declares to cover is ``identified`` instead of ``allocated`` (``allocated``
  needs at least one declaring asset, otherwise it was a coverage nobody declared). The shape (``schemaVersion`` ``2.0``) is unchanged and is still
  refused by the Document Engine's reader (§5.40: provenance, version, ``ref``, evidence source).

The sealed snapshot format has its own ``schema_version`` (still ``1.0``).
"""

CONTRACT_VERSION = "1.40"
SNAPSHOT_SCHEMA_VERSION = "1.0"

