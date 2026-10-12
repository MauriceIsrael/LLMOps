---
id: NIS2-ART21-2H
title: Cryptography and Information System Security for AI Systems
title_fr: Cryptographie, chiffrement et sécurité de l'intelligence artificielle
type: control
framework: NIS2
version: '2022/2555'
jurisdiction: EU
domain: [cryptography, ai-security]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-10-12
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(2)(h)
terms: [cryptographic-baseline, ai-assistant, envelope-encryption]
# Draft check clauses proposed by the coding agent (regulatory frameworks) — NOT validated.
# To be accepted, amended or rejected by the domain expert through the KB review cycle (L2).
checks_status: draft
checks:
- id: NIS2-ART21-2H-C1
  kind: forbids
  when:
    terms_any: [unencrypted connection, unencrypted protocol, unencrypted flow, unencrypted traffic, unencrypted link, unencrypted backup, unencrypted storage, unencrypted disk, stored unencrypted, sent unencrypted, transmitted unencrypted, in clear text, in cleartext, in plaintext, plaintext password, without encryption, http instead of https, non chiffre, non chiffree, non chiffres, non chiffrees, sans chiffrement, transmis en clair, transmises en clair, stocke en clair, stockee en clair, stockes en clair, stockees en clair, flux en clair, mots de passe en clair]
  message: 'NIS2 Art. 21(2)(h): data in transit and at rest must be protected with current cryptography; clear-text protocols and deprecated algorithms are not acceptable.'
- id: NIS2-ART21-2H-C2
  kind: requires
  when:
    terms_any: [personal data, sensitive data, health data, confidential data, donnees personnelles, donnees a caractere personnel, donnees sensibles, donnees de sante, donnees confidentielles]
  expect:
    terms_any: [encryption, encrypted, chiffre, chiffree, chiffres, chiffrees, tls, mtls, aes-256, aes, kms, hsm, key management, gestion des cles]
  message: 'NIS2 Art. 21(2)(h): sensitive and personal data must be encrypted, with managed keys.'
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:58:01Z'
revision: 2
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
