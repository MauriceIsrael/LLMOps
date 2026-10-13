---
id: NIS2-ART21-2J
title: Multi-Factor Authentication and Secured Communications
title_fr: Authentification multifacteur (MFA) et communications sécurisées
type: control
framework: NIS2
version: '2022/2555'
jurisdiction: EU
domain: [iam, mfa, secure-communications]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-10-12
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(2)(j)
terms: [fido2, emergency-comms, mtls]
# Draft check clauses proposed by the coding agent (regulatory frameworks) — NOT validated.
# To be accepted, amended or rejected by the domain expert through the KB review cycle (L2).
checks_status: draft
checks:
- id: NIS2-ART21-2J-C1
  kind: forbids
  when:
    terms_any: [password-only, password only, single-factor authentication, single factor authentication, login and password only, shared admin account, shared administrator account, shared administration account, mot de passe seul, authentification par mot de passe seul, authentification simple facteur, compte administrateur partage, compte d'administration partage, compte generique partage]
  message: 'NIS2 Art. 21(2)(j): access must use multi-factor or continuous authentication with personal accounts; password-only or shared accounts are not acceptable.'
- id: NIS2-ART21-2J-C2
  kind: requires
  when:
    terms_any: [remote access, administrative access, privileged access, admin console, administration console, remote administration, bastion, remote access vpn, client vpn, acces distant, acces a distance, acces d'administration, acces a privileges, acces privilegie, console d'administration, administration a distance, vpn nomade]
  expect:
    terms_any: [multi-factor authentication, two-factor, 2fa, fido2, webauthn, otp, one-time password, smart card, hardware token, security key, certificate-based authentication, continuous authentication, carte a puce, authentification continue, double authentification, authentification a deux facteurs, cle de securite]
  message: 'NIS2 Art. 21(2)(j): remote, administrative and privileged access requires multi-factor (or continuous) authentication.'
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:58:03Z'
revision: 2
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
