---
id: NIS2-ART21-2G
title: Basic Cyber Hygiene Practices and Cybersecurity Training
title_fr: Pratiques de base en cyber-hygiène et formation en cybersécurité
type: control
framework: NIS2
version: '2022/2555'
jurisdiction: EU
domain: [cyber-hygiene, training]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-10-12
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(2)(g)
terms: [security-baseline, least-privilege, secret-rotation]
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:58:00Z'
revision: 2
---

# NIS2-ART21-2G — Basic Cyber Hygiene Practices and Cybersecurity Training

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21, Paragraph 2, Point (g).

## Legal Requirement
Basic cyber hygiene practices and cybersecurity training.

## Architecture Acceptance Criteria
- Hardened base images (minimal distroless container images) and least privilege execution modes.
- Automated rotation policies for TLS certificates, API tokens, and service credentials.
- Codified operational playbooks eliminating untracked manual shell commands in production.
