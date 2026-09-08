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

