---
id: 3GPP-TS28104-MDA
title: Management Data Analytics (MDA) for Autonomous 5GS Core and RAN Operations
type: control
framework: 3GPP
version: "Rel-18"
jurisdiction: International
domain: [observability, network-automation, ai-assistance]
severity: recommended
target_entities: [telecom-operator, noc-team, core-vendor]
terms: [mda, mdas, analytics, aiops, 3gpp-ts28104, closed-loop, anomaly-detection]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: 3gpp-management-wg
source_ref: "3GPP TS 28.104 (Management Data Analytics) & 3GPP TS 28.532"
---

# 3GPP-TS28104-MDA — Management Data Analytics (MDA) for Autonomous 5GS Core & RAN

## Specification Reference
3GPP TS 28.104 (Telecommunication management; Management Data Analytics) and 3GPP TS 28.532 (Generic management services).

## Technical Requirement
The Network Operations Center (NOC) and Service Operations Center (SOC) management systems must leverage standardized Management Data Analytics Services (MDAS) to ingest telemetry, performance metrics, and fault logs across both RAN and Core domains, delivering automated anomaly detection, root cause diagnosis, and predictive resource scaling.

## Architecture Acceptance Criteria
- Integration of standardized MDAS producers delivering Core and RAN analytics reports over HTTP REST/JSON interfaces.
- Machine learning-assisted anomaly detection flagging radio degradation or core signaling congestion prior to SLA breach.
- Closed-loop policy triggers capable of dynamically adjusting QoS allocations or re-routing critical traffic.

