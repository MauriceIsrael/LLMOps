---
id: PPDR-DMO-LEGACY
title: Legacy Direct Mode Operation (TETRA DMO) & 3GPP ProSe Interoperability
type: control
framework: PPDR-DEVICE
version: "ERC/DEC/(01)19"
jurisdiction: Europe
domain: [ran, tactical-comms, mcx]
severity: mandatory
target_entities: [device-vendor, public-safety, tactical-forces]
terms: [dmo, direct-mode, tetra, prose, off-network, erc-dec-01-19, 380mhz]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: tactical-communications-wg
source_ref: "CEPT ERC/DEC/(01)19 & 3GPP Proximity Services (ProSe) TS 23.303"
---

# PPDR-DMO-LEGACY — Legacy Direct Mode Operation (TETRA DMO) & 3GPP ProSe Interoperability

## Specification Reference
CEPT ERC Decision (01)19 on harmonised frequency bands for emergency services (380-400 MHz) and 3GPP TS 23.303 / TS 24.554 (Proximity Services - ProSe).

## Technical Requirement
To guarantee communication survivability during total infrastructure loss, hybrid field terminals must incorporate off-network direct mode capabilities, providing either native TETRA Direct Mode Operation (DMO) in the 380-400 MHz range or 3GPP 5G Proximity Services (ProSe) Sidelink communications (PC5 interface).

## Architecture Acceptance Criteria
- Seamless local Push-To-Talk group calling without network coverage between nearby terminals.
- Dual-watch or background scanning between LTE/5G mission-critical channels and legacy DMO emergency channels.
- Dedicated hardware Emergency PTT button operable while wearing firefighting or tactical gloves.

