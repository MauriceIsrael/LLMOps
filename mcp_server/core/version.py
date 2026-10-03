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

The sealed snapshot format has its own ``schema_version`` (still ``1.0``).
"""

CONTRACT_VERSION = "1.19"
SNAPSHOT_SCHEMA_VERSION = "1.0"
