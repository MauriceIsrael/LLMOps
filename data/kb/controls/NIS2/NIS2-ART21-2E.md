---
id: NIS2-ART21-2E
title: Security in Network and Information Systems Lifecycle
title_fr: Sécurité de l'acquisition, du développement et de la maintenance des SI
type: control
framework: NIS2
version: 2022/2555
jurisdiction: EU
domain: [secure-development, vulnerability-management]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: '2026-10-17'
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(2)(e)
terms: [shadow-environment, security-baseline, devsecops]
checks_status: validated
checks:
- id: NIS2-ART21-2E-C1
  kind: forbids
  when:
    terms_any: [end-of-life software, end-of-life operating system, end-of-life os, unsupported operating system, unsupported software, unsupported version, out-of-support, no longer supported, logiciel hors support, systeme hors support, version hors support, fin de support editeur, plus supporte par l'editeur, no security updates, sans mises a jour de securite, sans correctifs de securite]
  message: 'NIS2 Art. 21(2)(e): systems must stay maintained, with vulnerability handling; unsupported or unpatched software is not acceptable.'
  status: validated
  review: {by: '@maintainers', at: '2026-10-17T08:57:36Z', decision: validate}
- id: NIS2-ART21-2E-C2
  kind: requires
  when:
    terms_any: [custom development, in-house development, developed in-house, bespoke application, specific development, ci/cd pipeline, build pipeline, developpement specifique, developpement sur mesure, application sur mesure, chaine ci/cd, pipeline ci/cd]
  expect:
    terms_any: [sast, dast, code review, security code review, dependency scanning, software composition analysis, vulnerability scanning, penetration test, pentest, secure development lifecycle, sdlc, devsecops, sbom, revue de code, analyse de code, scan de vulnerabilites, analyse des dependances, test d'intrusion, tests d'intrusion, cycle de developpement securise]
  message: 'NIS2 Art. 21(2)(e): developed software needs secure development practices and vulnerability handling (code analysis, dependency scanning, penetration tests).'
  status: validated
  review: {by: '@maintainers', at: '2026-10-17T08:57:54Z', decision: validate}
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:57:59Z'
revision: 4
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
