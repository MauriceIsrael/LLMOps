---
id: SNC-REQ-01
title: Extraterritorial Immunity and European Data Localization
title_fr: Immunité aux lois extraterritoriales et localisation européenne des données
type: control
framework: SecNumCloud
version: "3.2"
jurisdiction: FR-EU
domain: [sovereignty, legal-compliance]
severity: mandatory
target_entities: [essential, critical-infrastructure]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "ANSSI SecNumCloud 3.2, Requirement 19.2 (Protection against extraterritorial laws)"
terms: [sovereignty-boundary, data-localization]
---

# SNC-REQ-01 — Extraterritorial Immunity and European Data Localization

## Regulatory Reference
ANSSI SecNumCloud 3.2 Requirements Baseline, Requirement 19.2.

## Legal & Sovereignty Requirement
The cloud service provider and its subcontractors must be legally and technically protected against any extraterritorial disclosure orders from non-EU authorities. All production data, backups, and metadata must reside and be operated strictly within the European Union.

## Architecture Acceptance Criteria
- Exclusive hosting within data centers located in the European Union.
- Total exclusion of critical subcontractors subject to foreign extraterritorial regulations (Cloud Act, FISA 702) for sensitive workloads.
- Formal legal ownership auditing and airtight sovereign governance structure.
