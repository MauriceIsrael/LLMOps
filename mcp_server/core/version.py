"""Contract version exposed by the server (see docs/VERSIONING.md).

Minor versions only add interfaces or optional fields:

* ``1.0`` — reference contract (frozen in ``tests/contract/frozen/``).
* ``1.1`` — doctrine context (``get_doctrine_context``, ``GET /api/knowledge/context``)
  and option judge (``check_option``, ``POST /api/knowledge/check``).
* ``1.2`` — KB candidate cycle (``submit_kb_candidate``, ``list_kb_candidates``,
  ``get_kb_candidate``, ``review_kb_candidate``, ``/api/knowledge/candidates``) and the
  optional ``candidate_id`` in the suggestion response.

The sealed snapshot format has its own ``schema_version`` (still ``1.0``).
"""

CONTRACT_VERSION = "1.2"
SNAPSHOT_SCHEMA_VERSION = "1.0"
