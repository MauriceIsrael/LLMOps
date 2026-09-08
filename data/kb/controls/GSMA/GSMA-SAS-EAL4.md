---
id: GSMA-SAS-EAL4
title: Common Criteria EAL4+ and GSMA SAS Certification for eUICC & SM-DP+
type: control
framework: GSMA
version: "SGP.24 / SGP.25"
jurisdiction: International
domain: [cryptography, sim-identity, certification]
severity: mandatory
target_entities: [sm-dp-provider, euicc-manufacturer, security-evaluator]
terms: [gsma, sas, sas-sm, sas-up, common-criteria, eal4+, hsm, eim]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: security-office
source_ref: "GSMA SGP.23 / SGP.24 / SGP.25 & Common Criteria EAL4+ (ISO/IEC 15408)"
---

# GSMA-SAS-EAL4 — Common Criteria EAL4+ and GSMA SAS Certification for eUICC & SM-DP+

## Specification Reference
GSMA SGP.23/24/25 Security Assurance Scheme (SAS-SM for Subscription Management, SAS-UP for UICC Production) and Common Criteria EAL4+ certification (ISO/IEC 15408).

## Technical Requirement
All physical eUICC components deployed in field devices and all backend Subscription Management nodes (SM-DP+, SM-SR) must possess valid Common Criteria EAL4+ or higher security certificates and operate within GSMA SAS-accredited facilities.

## Architecture Acceptance Criteria
- Hardware Security Modules (HSM) utilized for profile encryption and key wrapping evaluated at CC EAL4+ or FIPS 140-3 Level 3.
- True Random Number Generator (TRNG) adhering to AIS 31 or NIST SP 800-90B standards.
- Independent third-party audit certificates verified prior to network integration.

