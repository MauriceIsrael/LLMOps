---
id: GSMA-SGP32-IOT
title: Remote SIM Provisioning for Headless IoT and Mission-Critical In-Vehicle Routers
type: control
framework: GSMA
version: "SGP.32 v1.1"
jurisdiction: International
domain: [mobile-core, sim-identity, iot]
severity: mandatory
target_entities: [telecom-operator, vehicle-integrator, iot-vendor]
terms: [gsma, sgp32, esim-iot, epc, eim, headless-device, vehicle-router]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: telecom-architecture-wg
source_ref: "GSMA SGP.31 / SGP.32 eSIM IoT Architecture and Technical Specification"
---

# GSMA-SGP32-IOT — Remote SIM Provisioning for Headless IoT and In-Vehicle Routers

## Specification Reference
GSMA SGP.31 (eSIM IoT Architecture) and GSMA SGP.32 (eSIM IoT Technical Specification).

## Technical Requirement
The platform must support GSMA SGP.32 remote profile management for headless devices, tactical sensors, and in-vehicle routers lacking interactive human UI, driven by an eSIM IoT Remote Manager (eIM).

## Architecture Acceptance Criteria
- Direct profile switching and operational status reporting orchestrated via eIM without manual user intervention.
- Cryptographic authentication between the eIM and the IoT Profile Assistant (IPA).
- Fallback profile activation in case of operational network disconnection or unrecoverable transmission failure.

