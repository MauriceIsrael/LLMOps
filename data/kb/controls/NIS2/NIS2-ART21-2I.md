---
id: NIS2-ART21-2I
title: Human Resources Security, Access Control and Asset Management
title_fr: Sécurité des ressources humaines, contrôle d'accès et gestion des actifs
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [iam, asset-management]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "Directive (EU) 2022/2555 (NIS 2), Article 21(2)(i)"
terms: [source-of-truth, least-privilege, rbac]
---

# NIS2-ART21-2I — Human Resources Security, Access Control and Asset Management

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21, Paragraph 2, Point (i).

## Legal Requirement
Human resources security, access control policies and asset management.

## Architecture Acceptance Criteria
- Strict single master of record per data domain for infrastructure assets and user identities.
- Granular Role-Based Access Control (RBAC) enforcing least privilege across engineering and operations roles.
- Automated instant de-provisioning and credential revocation upon role reassignment or termination.
