---
id: PPDR-RADIO-B68
title: Dedicated BB-PPDR Spectrum Compliance (Band 68 / Band 28) per CEPT/ECC (16)02
type: control
framework: PPDR-DEVICE
version: "ECC/DEC/(16)02"
jurisdiction: Europe
domain: [ran, spectrum, ppdr-radio]
severity: mandatory
target_entities: [device-vendor, ran-vendor, telecom-operator]
terms: [band-68, band-28, cept, ecc, ppdr, bb-ppdr, gov-68, 700mhz]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: spectrum-engineering-wg
source_ref: "CEPT/ECC Decision (16)02 (Harmonised frequency range for BB-PPDR systems)"
---

# PPDR-RADIO-B68 — Dedicated BB-PPDR Spectrum Compliance (Band 68 / Band 28)

## Specification Reference
Electronic Communications Committee (ECC) Decision (16)02 on harmonised frequency range for Broadband Public Protection and Disaster Relief (BB-PPDR) systems in the 700 MHz range.

## Technical Requirement
All user equipment (handhelds, tablets, vehicular modems, and transportable tactical base stations) must support native operation within designated sovereign public safety frequency bands, specifically 3GPP Band 68 (Uplink 698-703 MHz / Downlink 753-758 MHz) and Band 28 (700 MHz APT).

## Architecture Acceptance Criteria
- RF front-end filtering certified compliant with ETSI EN 301 908 (E-UTRA / NR) specifications for Band 68 and Band 28.
- Dynamic network attachment and fast frequency roaming between dedicated sovereign BB-PPDR radio cells and commercial partner networks.
- Priority pre-emption (eMLPP / Access Identity 12, 13, 14) configured for public safety SIM profiles.

