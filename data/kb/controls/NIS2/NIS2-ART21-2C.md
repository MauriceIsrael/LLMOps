---
id: NIS2-ART21-2C
title: Business Continuity and Crisis Management
title_fr: Continuité des activités et gestion de crise
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [business-continuity, disaster-recovery]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "Directive (EU) 2022/2555 (NIS 2), Article 21(2)(c)"
terms: [break-glass, fallback-plan, immutable-log]
---

# NIS2-ART21-2C — Business Continuity and Crisis Management

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21, Paragraph 2, Point (c).

## Legal Requirement
Business continuity, such as backup management and disaster recovery, and crisis management.

## Architecture Acceptance Criteria
- Redundant active/passive deployment topology across distinct availability zones.
- Independent failure domain with documented break-glass procedures and baseline-bound fallback plans.
- Immutable, write-once-read-many (WORM) backups logically and physically segregated from the primary network.
