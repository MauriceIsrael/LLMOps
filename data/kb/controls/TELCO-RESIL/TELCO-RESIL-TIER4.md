---
id: TELCO-RESIL-TIER4
title: Dual-Site Geo-Redundant Datacenters Compliant with EN 50600 Class 4 / Tier IV
type: control
framework: TELCO-RESIL
version: "EN 50600 / Tier IV"
jurisdiction: International
domain: [infrastructure, resilience, cloud-platform]
severity: mandatory
target_entities: [telecom-operator, infrastructure-provider]
terms: [tier-iv, en-50600, class-4, datacenter, high-availability, five-nines, geo-redundancy]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: infrastructure-architecture-wg
source_ref: "EN 50600 (Information technology - Data centre facilities) & Uptime Institute Tier IV"
---

# TELCO-RESIL-TIER4 — Dual-Site Geo-Redundant Datacenters (EN 50600 Class 4 / Tier IV)

## Specification Reference
CENELEC EN 50600 series (Class 4 Data Centres) and Uptime Institute Tier IV Fault Tolerant Data Center criteria.

## Technical Requirement
The 5G core network and mission-critical application layer must be hosted across at least two geographically separated datacenters meeting EN 50600 Class 4 or Uptime Institute Tier IV standards, providing fault tolerance against concurrent active power/cooling failures and ensuring 99.999% ("five-nines") annual service availability.

## Architecture Acceptance Criteria
- Dual active-active or active-hot-standby topology across sites separated by sufficient geographic distance (> 20 km) with diverse dark fiber paths.
- N+N redundant power distribution paths, dual independent sub-stations, and onsite fuel autonomy > 72 hours.
- Automatic failover for voice/data signaling with RTO < 30 seconds and zero persistent data loss (RPO = 0).
- Independent fire compartmentalization and seismic/flood environmental protection.

