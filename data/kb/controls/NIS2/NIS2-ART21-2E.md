---
id: NIS2-ART21-2E
title: Security in Network and Information Systems Lifecycle
title_fr: Sécurité de l'acquisition, du développement et de la maintenance des SI
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [secure-development, vulnerability-management]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "Directive (EU) 2022/2555 (NIS 2), Article 21(2)(e)"
terms: [shadow-environment, security-baseline, devsecops]
---

# NIS2-ART21-2E — Security in Network and Information Systems Lifecycle

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21, Paragraph 2, Point (e).

## Legal Requirement
Security in network and information systems acquisition, development and maintenance, including vulnerability handling and disclosure.

## Architecture Acceptance Criteria
- Shadow environment validation: automated pre-production evaluation with mirrored telemetry before active arming.
- Continuous vulnerability lifecycle management with strict, criticality-based remediation SLAs.
- Automated security quality gates embedded in continuous deployment pipelines (CI/CD).
