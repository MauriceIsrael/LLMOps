---
id: NIS2-ART21-2H
title: Cryptography and Information System Security for AI Systems
title_fr: Cryptographie, chiffrement et sécurité de l'intelligence artificielle
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [cryptography, ai-security]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "Directive (EU) 2022/2555 (NIS 2), Article 21(2)(h)"
terms: [cryptographic-baseline, ai-assistant, envelope-encryption]
---

# NIS2-ART21-2H — Cryptography and Information System Security for AI Systems

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21, Paragraph 2, Point (h).

## Legal Requirement
Policies and procedures regarding the use of cryptography and, where appropriate, encryption.

## Architecture Acceptance Criteria
- Systematic end-to-end encryption in transit (mTLS) and envelope encryption at rest with customer-held keys.
- AI inference bounded strictly within the security perimeter without context exfiltration to external third parties.
- Advisory assistant paradigm: the AI advises and prepares changes, but cannot commit or apply them autonomously.
