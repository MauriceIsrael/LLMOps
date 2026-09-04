---
id: SNC-REQ-06
title: Multi-Site Resilience and Disaster Recovery (BCP/DRP)
title_fr: Résilience multi-sites et plans de continuité d'activité (PCA/PRA)
type: control
framework: SecNumCloud
version: "3.2"
jurisdiction: FR-EU
domain: [resilience, business-continuity]
severity: mandatory
target_entities: [essential, critical-infrastructure]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "ANSSI SecNumCloud 3.2, Requirement 17.1"
terms: [disaster-recovery, zero-rpo, multi-site]
---

# SNC-REQ-06 — Multi-Site Resilience and Disaster Recovery (BCP/DRP)

## Regulatory Reference
ANSSI SecNumCloud 3.2 Requirements Baseline, Requirement 17.1.

## Legal Requirement
Services must be deployed redundantly across geographically separated availability zones not subject to shared physical risks. Failover mechanisms must be tested and automated.

## Architecture Acceptance Criteria
- Active/active or active/hot-standby topology across at least two distant sites (> 30 km).
- Zero data loss (RPO = 0) for critical transactional state and RTO < 60 seconds for priority mission services.
- Automated WAN traffic rerouting avoiding single points of failure.
