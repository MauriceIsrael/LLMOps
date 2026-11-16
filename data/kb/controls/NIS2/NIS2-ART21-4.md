---
id: NIS2-ART21-4
title: Corrective measures for non-compliance
type: control
framework: NIS2
version: 2022/2555
jurisdiction: EU
domain: [security-governance]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: '2026-11-16'
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(4)
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:58:04Z'
revision: 2
title_fr: Mesures correctives en cas de non-conformité
terms: [corrective action, remediation, non-compliance, action corrective, remédiation, non-conformité]
satisfied_by: [P-001, ADR-0002]
links_production_mode: llm-proposed-human-approved
---

# NIS2-ART21-4 — Corrective measures for non-compliance

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21(4).

## Legal Requirement
Member States shall ensure that an entity that finds that it does not comply with the measures provided for in paragraph 2 takes, without undue delay, all necessary, appropriate and proportionate corrective measures.

## Architecture Acceptance Criteria
- Non-compliance with a measure of Article 21(2) found in the architecture or in operation is recorded with an owner, a corrective action and a deadline.
- The architecture allows corrective measures to be deployed without undue delay (configuration managed as code, tested rollout and rollback paths).