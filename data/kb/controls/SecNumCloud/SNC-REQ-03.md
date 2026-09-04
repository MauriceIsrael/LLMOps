---
id: SNC-REQ-03
title: Cryptographic Key Management on ANSSI-Qualified HSM
title_fr: Gestion des clés cryptographiques sur HSM qualifié ANSSI
type: control
framework: SecNumCloud
version: "3.2"
jurisdiction: FR-EU
domain: [cryptography, data-protection]
severity: mandatory
target_entities: [essential, critical-infrastructure]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "ANSSI SecNumCloud 3.2, Requirement 10.1"
terms: [hsm, envelope-encryption, root-of-trust]
---

# SNC-REQ-03 — Cryptographic Key Management on ANSSI-Qualified HSM

## Regulatory Reference
ANSSI SecNumCloud 3.2 Requirements Baseline, Requirement 10.1.

## Legal Requirement
All master keys for data-at-rest encryption and digital signatures must be generated, stored, and managed inside an ANSSI-qualified Hardware Security Module (HSM).

## Architecture Acceptance Criteria
- Integration of an ANSSI-qualified physical HSM for Root of Trust and platform KMS keys.
- Envelope encryption with automated, controlled Data Encryption Key (DEK) rotation.
- Separation of duties between infrastructure administrators and cryptographic custodians.
