---
id: SNC-REQ-04
title: Hypervisor Isolation and Container Hardening
title_fr: Isolation de l'hyperviseur et durcissement des environnements de conteneurs
type: control
framework: SecNumCloud
version: "3.2"
jurisdiction: FR-EU
domain: [infrastructure-security, container-security]
severity: mandatory
target_entities: [essential, critical-infrastructure]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "ANSSI SecNumCloud 3.2, Requirements 12.1 & 12.6"
terms: [hardened-container, rootless, network-policy]
---

# SNC-REQ-04 — Hypervisor Isolation and Container Hardening

## Regulatory Reference
ANSSI SecNumCloud 3.2 Requirements Baseline, Requirements 12.1 & 12.6.

## Legal Requirement
Tenant isolation and core system function separation must be resilient against side-channel attacks, hypervisor escape, and container breakouts.

## Architecture Acceptance Criteria
- Hypervisor and host OS hardened according to official ANSSI best practice guides (Secure Boot, TPM 2.0).
- Rootless container execution, ban on host docker/containerd socket mounting, and strict AppArmor/SELinux profiles.
- Inter-workload network micro-segmentation with default Deny-All NetworkPolicies.
