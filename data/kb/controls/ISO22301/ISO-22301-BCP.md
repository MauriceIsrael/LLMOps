---
id: ISO-22301-BCP
title: Business Continuity Management System (BCMS), Contingency & Disaster Recovery
type: control
framework: ISO22301
version: "2019"
jurisdiction: International
domain: [resilience, operations, business-continuity]
severity: mandatory
target_entities: [telecom-operator, public-safety, managed-service-provider]
terms: [iso22301, bcms, bcp, drp, business-continuity, disaster-recovery, rto, rpo]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: resilience-council
source_ref: "ISO 22301:2019 (Security and resilience - Business continuity management systems)"
---

# ISO-22301-BCP — Business Continuity Management System (BCMS) & Disaster Recovery

## Specification Reference
ISO 22301:2019 (Security and resilience - Business continuity management systems - Requirements).

## Technical Requirement
The operator and service suppliers must establish, implement, maintain, and continually improve a documented Business Continuity Management System (BCMS), integrating comprehensive Disaster Recovery Plans (DRP), crisis communication chains, and technical contingency measures ensuring uncompromised mission-critical operations during severe disruptions.

## Architecture Acceptance Criteria
- Business Impact Analysis (BIA) identifying all critical operational paths with maximum allowable outage (MAO).
- Recovery Time Objective (RTO) < 30 seconds for mission-critical core voice/data, RTO < 4 hours for non-realtime portals.
- Recovery Point Objective (RPO) = 0 for user databases and subscriber group membership records.
- Bi-annual live disaster simulation exercises verifying failover to alternative operational centers.

