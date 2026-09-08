---
id: CER-ART13-RESIL
title: Critical Entities Resilience, Physical Security & Disaster Recovery
type: control
framework: CER
version: "2022/2557"
jurisdiction: EU
domain: [resilience, infrastructure, disaster-recovery]
severity: mandatory
target_entities: [telecom-operator, critical-communications, ppdr-network]
terms: [cer, resilience, critical-entity, physical-security, disaster-recovery, crisis-management]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: resilience-council
source_ref: "Directive (EU) 2022/2557 (CER), Article 13"
---

# CER-ART13-RESIL — Critical Entities Resilience, Physical Security & Disaster Recovery

## Specification Reference
Directive (EU) 2022/2557 of the European Parliament and of the Council on the resilience of critical entities (CER Directive), Article 13 ("Resilience measures of critical entities").

## Technical Requirement
Critical communication infrastructure providers must implement technical, physical, and organizational resilience measures to prevent incidents, protect facilities and physical assets against physical tampering and sabotage, ensure personnel security, and maintain operational continuity through rapid incident response, containment, and disaster recovery.

## Architecture Acceptance Criteria
- Physical perimeter security and multi-factor biometric/badge access control across all core datacenters and primary transmission hubs.
- Redundant power delivery (dual UPS chains + autonomous diesel generator holdover > 72 hours with priority fuel replenishment contracts).
- Geographically dispersed active-active or active-standby disaster recovery sites with deterministic RTO (< 30 seconds) and zero transaction loss (RPO = 0).
- Documented crisis management, personnel background vetting, and annual failover rehearsal procedures.

