# Mission-critical mobile network — 2026

Reference engagement from which most of the current core assets were harvested.
Kept as a worked example of a filled instance.

- **System:** vendor mobile core on dedicated infrastructure, MCX suite and
  services on a container platform, IP transport underlay.
- **Management stack:** Git and CI, network source of truth with compliance,
  orchestration with approval, event-driven rules, split observability,
  optional advisory assistant with local inference.
- **Phase reached:** design complete, framing audits pending.

## Status of the gating audits

| Questionnaire | Status | Blocking |
|---|---|---|
| QST-core-ems | not started | Yes — determines the core automation scope |
| QST-service-management | not started | Yes — determines mastership and integration scope |
| QST-cloud-platform | not started | Only for the optional assistant lot |

## Decisions taken

ADR-0001 to ADR-0013. ADR-0009 and ADR-0013 carry `confidence: assumed` and are
the two most likely to move once the audits return.
