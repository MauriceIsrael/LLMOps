---
id: RGPD-REQ-PRIVACY-01
title: Privacy by Design & Default for Real-Time Location, CDRs and MCX Media
type: control
framework: RGPD
version: 2016/679
jurisdiction: EU
domain: [data-protection, privacy, security]
severity: mandatory
target_entities: [telecom-operator, public-safety, application-provider]
terms: [gdpr, rgpd, privacy-by-design, location-data, call-detail-records, cdr, data-retention]
status: active
confidence: verified
last_reviewed: '2026-10-17'
owner: data-protection-officer
source_ref: Regulation (EU) 2016/679 (GDPR), Article 25 (Data protection by design and by default)
checks_status: validated
checks:
- id: RGPD-REQ-PRIVACY-01-C1
  kind: forbids
  when:
    terms_any: [production data in test, production data copied to test, production data in the test environment, real personal data in test, unlimited retention, indefinite retention, kept indefinitely, retained indefinitely, no retention period, donnees de production en recette, donnees de production en test, copie de la production en recette, donnees reelles en recette, conservation illimitee, conservation indefinie, conservees indefiniment, sans duree de conservation]
  message: 'GDPR Art. 5(1)(c) and (e), Art. 25: personal data are minimised and kept no longer than necessary; real production data in test and unlimited retention are not acceptable.'
  status: validated
  review: {by: '@maintainers', at: '2026-10-17T08:59:26Z', decision: validate}
revision: 2
---

# RGPD-REQ-PRIVACY-01 — Privacy by Design & Default for Real-Time Location, CDRs and MCX Media

## Specification Reference
Regulation (EU) 2016/679 (General Data Protection Regulation - GDPR), Article 25 ("Data protection by design and by default") and Article 5 ("Principles relating to processing of personal data").

## Technical Requirement
Architectural mechanisms must enforce privacy by design and by default across all operational workflows involving highly sensitive subscriber data, including real-time GNSS/triangulation coordinates, Call Detail Records (CDRs), voice/video recordings, and MDM/MAM telemetry.

## Architecture Acceptance Criteria
- Explicit role-based access control (RBAC) and purpose limitation for real-time fleet geolocation tracking.
- Strict data retention schedules with automated cryptographic purging of media recordings and location trails after defined statutory periods.
- Pseudonymization or hashing of subscriber identifiers (IMSI/SUPI, MSISDN) in analytical, debugging, and billing platforms.
- Complete tamper-proof audit trails recording every operator query, playback, or data export.

