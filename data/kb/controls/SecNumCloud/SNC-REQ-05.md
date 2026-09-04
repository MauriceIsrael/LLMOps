---
id: SNC-REQ-05
title: Immutable Audit Logging and Real-Time SOC Telemetry
title_fr: Journalisation immuable et transmission en temps réel au SOC
type: control
framework: SecNumCloud
version: "3.2"
jurisdiction: FR-EU
domain: [observability, security-monitoring]
severity: mandatory
target_entities: [essential, critical-infrastructure]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "ANSSI SecNumCloud 3.2, Requirement 12.4"
terms: [immutable-log, worm, siem]
---

# SNC-REQ-05 — Immutable Audit Logging and Real-Time SOC Telemetry

## Regulatory Reference
ANSSI SecNumCloud 3.2 Requirements Baseline, Requirement 12.4.

## Legal Requirement
Security, access, and administration events must be logged without delay, synchronized with certified time sources, cryptographically sealed, and analyzed in real time by a qualified SOC.

## Architecture Acceptance Criteria
- Asynchronous, encrypted log forwarding to a centralized SIEM with Write-Once-Read-Many (WORM) immutability.
- Clock synchronization across redundant, cryptographically secured NTP/PTP sources.
- Automated anomaly detection triggering immediate alerts to the CSIRT/SOC incident response team.
