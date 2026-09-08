---
id: TELCO-RESIL-GNSS-HOLDOVER
title: GNSS Anti-Jamming, Anti-Spoofing & Atomic Clock Holdover Exceeding 30 Days
type: control
framework: TELCO-RESIL
version: "2026"
jurisdiction: International
domain: [resilience, transport, electronic-warfare]
severity: mandatory
target_entities: [telecom-operator, public-safety, defense-network]
terms: [gnss, holdover, rubidium, ocxo, electronic-warfare, spoofing, jamming]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: transmission-architecture-wg
source_ref: "ITU-T G.811.1 & LUMICC Lot 1 Statement of Work Section 6"
---

# TELCO-RESIL-GNSS-HOLDOVER — GNSS Denial Resilience & Atomic Clock Holdover > 30 Days

## Specification Reference
ITU-T G.811.1 (Timing characteristics of enhanced primary reference clocks) and mission-critical specifications for resilient timing architectures.

## Technical Requirement
Primary reference timing servers must incorporate multi-constellation GNSS receivers equipped with hardware-based anti-jamming / anti-spoofing antennas and integrate local high-stability atomic oscillators (Rubidium or ultra-stable OCXO) ensuring autonomous time holdover for at least 30 consecutive days within acceptable 5G phase drift boundaries during complete GNSS loss.

## Architecture Acceptance Criteria
- Seamless autonomous transition into holdover mode upon loss or jamming of satellite constellation locks.
- Phase drift accumulation restricted to remain below the 3GPP 5G TDD frame threshold (+/- 1.5 microseconds) over the operational holdover window.
- Immediate telemetry alerts dispatched to NOC/SOC upon detection of GNSS spoofing, interference, or loss of tracking.

