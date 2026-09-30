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

The sealed snapshot format has its own ``schema_version`` (still ``1.0``).
"""

CONTRACT_VERSION = "1.5"
SNAPSHOT_SCHEMA_VERSION = "1.0"
