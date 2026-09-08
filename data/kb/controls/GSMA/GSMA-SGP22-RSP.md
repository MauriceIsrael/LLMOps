---
id: GSMA-SGP22-RSP
title: Remote SIM Provisioning (RSP) Architecture & Profile Download
type: control
framework: GSMA
version: "SGP.22 v3.0"
jurisdiction: International
domain: [mobile-core, sim-identity, cryptography]
severity: mandatory
target_entities: [telecom-operator, sm-dp-provider, device-vendor]
terms: [gsma, rsp, esim, euicc, sm-dp, sm-ds, profile-download, lpa]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: telecom-architecture-wg
source_ref: "GSMA SGP.21 / SGP.22 Technical Specification"
---

# GSMA-SGP22-RSP — Remote SIM Provisioning (RSP) Architecture & Profile Download

## Specification Reference
GSMA SGP.21 (RSP Architecture) and GSMA SGP.22 (RSP Technical Specification).

## Technical Requirement
The system must support sovereign Remote SIM Provisioning (RSP) allowing over-the-air profile generation, encryption, and secure installation into field eUICC components, supporting both push (SM-DP+) and discovery (SM-DS) mechanisms without requiring physical SIM card replacement.

## Architecture Acceptance Criteria
- End-to-end cryptographic encapsulation of operator profiles between Subscription Manager Data Preparation (SM-DP+) and the target eUICC.
- Compatibility with Local Profile Assistant (LPA) embedded on MCX handhelds and vehicular modems.
- Multi-profile management allowing sovereign profiles to coexist with commercial MNO roaming profiles.
- Secure credential exchange using GSMA Certificate Issuer (CI) root certificates.

