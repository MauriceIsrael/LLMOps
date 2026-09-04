---
id: SNC-REQ-02
title: Strict Administration Network Segregation and Bastion Access
title_fr: Cloisonnement strict du réseau d'administration et bastion d'accès
type: control
framework: SecNumCloud
version: "3.2"
jurisdiction: FR-EU
domain: [network-security, identity-access-management]
severity: mandatory
target_entities: [essential, critical-infrastructure]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "ANSSI SecNumCloud 3.2, Requirements 13.1 & 13.2"
terms: [bastion, mtls, least-privilege]
---

# SNC-REQ-02 — Strict Administration Network Segregation and Bastion Access

## Regulatory Reference
ANSSI SecNumCloud 3.2 Requirements Baseline, Requirements 13.1 & 13.2.

## Legal Requirement
Administrative management networks must be physically or logically isolated from customer payload networks and the public Internet. Direct administrative access is strictly prohibited.

## Architecture Acceptance Criteria
- Mandatory transit through a qualified administration bastion with hardware multi-factor authentication (MFA).
- Mutual TLS (mTLS) with certificates issued by a dedicated administration PKI.
- Complete denial of direct internet administration: protocol break and full session audit logging.
