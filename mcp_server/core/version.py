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

The sealed snapshot format has its own ``schema_version`` (still ``1.0``).
"""

CONTRACT_VERSION = "1.10"
SNAPSHOT_SCHEMA_VERSION = "1.0"
