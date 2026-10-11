---
id: RGPD-REQ-BREACH-02
title: Personal Data Breach Detection, Forensic Logging & 72-Hour Notification
type: control
framework: RGPD
version: "2016/679"
jurisdiction: EU
domain: [data-protection, incident-response, security]
severity: mandatory
target_entities: [telecom-operator, data-controller, data-processor]
terms: [gdpr, rgpd, breach-notification, incident-response, forensic-logging, audit-trail]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: data-protection-officer
source_ref: "Regulation (EU) 2016/679 (GDPR), Articles 33 & 34"
# Draft check clauses proposed by the coding agent (regulatory frameworks) — NOT validated.
# To be accepted, amended or rejected by the domain expert through the KB review cycle (L2).
checks_status: draft
checks:
  - id: RGPD-REQ-BREACH-02-C1
    kind: forbids
    when:
      terms_any: [no logging, logging disabled, logs are not retained, no audit trail, no audit log, without audit logs, sans journalisation, journalisation desactivee, logs non conserves, sans piste d'audit, pas de journalisation]
    message: "GDPR Art. 33 and 34: breach detection and notification need security logs and audit trails kept as forensic evidence."
  - id: RGPD-REQ-BREACH-02-C2
    kind: requires
    when:
      terms_any: [personal data breach, data breach, violation de donnees, violation de donnees personnelles, fuite de donnees]
    expect:
      terms_any: [72 hours, 72 h, 72h, supervisory authority, data protection authority, cnpd, cnil, dpo, data protection officer, autorite de controle, delegue a la protection des donnees]
    message: "GDPR Art. 33: a personal data breach is notified to the competent supervisory authority within 72 hours, with the DPO involved."
---

# RGPD-REQ-BREACH-02 — Personal Data Breach Detection, Forensic Logging & 72-Hour Notification

## Specification Reference
Regulation (EU) 2016/679 (GDPR), Article 33 ("Notification of a personal data breach to the supervisory authority") and Article 34 ("Communication of a personal data breach to the data subject").

## Technical Requirement
The mission-critical platform must provide automated personal data breach detection, immutable forensic logging, and operational workflows capable of notifying the competent national data protection authority within 72 hours of detection.

## Architecture Acceptance Criteria
- Automated SIEM/SOC alerting on mass exfiltration or unauthorized queries against subscriber databases.
- Integration between the Security Operations Center (SOC) and the Data Protection Officer (DPO) ticketing workflow.
- Secure retention of forensic evidence and tamper-resistant access logs for at least 12 months.
- Incident severity classification matrix aligned with national supervisory authority guidelines.

