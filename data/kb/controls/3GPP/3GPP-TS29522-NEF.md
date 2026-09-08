---
id: 3GPP-TS29522-NEF
title: 5G Network Exposure Function (NEF) Northbound APIs for Dynamic QoS & Location
type: control
framework: 3GPP
version: "Rel-18"
jurisdiction: International
domain: [mobile-core, network-exposure, mcx]
severity: mandatory
target_entities: [core-vendor, application-developer, dispatch-provider]
terms: [nef, 3gpp-ts29522, n33, qos-on-demand, location-exposure, event-monitoring]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: 3gpp-core-wg
source_ref: "3GPP TS 29.522 (Network Exposure Function Northbound APIs)"
---

# 3GPP-TS29522-NEF — 5G Network Exposure Function (NEF) Northbound APIs

## Specification Reference
3GPP TS 29.522 (5G System; Network Exposure Function Northbound APIs; Stage 3) and TS 23.502 (Procedures for the 5G System).

## Technical Requirement
The 5G Core must provide a secure Network Exposure Function (NEF) exposing standardized Northbound (N33) RESTful APIs to authorized Mission Critical application servers and CAD/dispatch systems for on-demand QoS modification, subscriber location retrieval, and mobility event notifications.

## Architecture Acceptance Criteria
- Asynchronous event monitoring subscriptions (UE reachability, loss of connectivity, roaming status).
- Dynamic Session with QoS API invocation enabling real-time elevation to 5QI 65/66 (Mission Critical Voice) or 5QI 69/70 (Video/Data).
- Mutual TLS (mTLS) and OAuth2 token authorization enforced on all NEF API endpoints.
- API throttling and rate-limiting shielding core signaling from external application overload.

