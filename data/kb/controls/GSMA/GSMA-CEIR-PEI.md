---
id: GSMA-CEIR-PEI
title: GSMA Central EIR Integration for Stolen Device Tracking and PEI/IMEI Blacklisting
type: control
framework: GSMA
version: "PRD SG.18"
jurisdiction: International
domain: [mobile-core, security, device-management]
severity: mandatory
target_entities: [telecom-operator, public-safety, police-forces]
terms: [gsma, ceir, eir, imei, pei, blacklist, stolen-device, equipment-identity]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: security-office
source_ref: "GSMA PRD SG.18 / Central Equipment Identity Register (Central EIR)"
---

# GSMA-CEIR-PEI — GSMA Central EIR Integration for Stolen Device Tracking & PEI/IMEI Blacklisting

## Specification Reference
GSMA PRD SG.18 (Central Equipment Identity Register - Central EIR Specification).

## Technical Requirement
The 5G 5GS Core Equipment Identity Register (5G-EIR) must automatically synchronize with the GSMA Central EIR database to report stolen or compromised Permanent Equipment Identifiers (PEI/IMEI) and enforce national and cross-border blacklisting on radio access networks.

## Architecture Acceptance Criteria
- Automated daily bilateral exchange with GSMA Central EIR via secure SFTP or API.
- Instantaneous rejection of network registration and MCX attachment for blacklisted PEI/IMEI.
- White, Grey, and Black list management with granular exception policies for forensic or investigative operations.

