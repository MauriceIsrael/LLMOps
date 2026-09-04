---
id: NIS2-ART21-2J
title: Multi-Factor Authentication and Secured Communications
title_fr: Authentification multifacteur (MFA) et communications sécurisées
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [iam, mfa, secure-communications]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "Directive (EU) 2022/2555 (NIS 2), Article 21(2)(j)"
terms: [fido2, emergency-comms, mtls]
---

# NIS2-ART21-2J — Multi-Factor Authentication and Secured Communications

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21, Paragraph 2, Point (j).

## Legal Requirement
The use of multi-factor authentication or continuous authentication solutions, secured voice, video and text communications and secured emergency communication systems within the entity.

## Architecture Acceptance Criteria
- Phishing-resistant Multi-Factor Authentication (FIDO2 / WebAuthn) required for all administrative access.
- End-to-end cryptographic protection of critical voice, video, and operational messaging channels.
- Guaranteed emergency operational channels maintaining survivability under WAN partition or network degradation.
