---
id: FCAPS-OAM-PROT
title: FCAPS Telemetry, Syslog RFC 5424 Bastion Forwarding & Secure O&M Protocols
type: control
framework: ITIL-FCAPS
version: "RFC 5424 / ITU-T M.3400"
jurisdiction: International
domain: [observability, operations, network-automation]
severity: mandatory
target_entities: [telecom-operator, noc-team, soc-team]
terms: [fcaps, syslog, rfc5424, snmpv3, netconf, restconf, yang, bastion, siem]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: operations-directorate
source_ref: "ITU-T M.3400 (TMN Management Functions / FCAPS), IETF RFC 5424 (Syslog)"
---

# FCAPS-OAM-PROT — FCAPS Telemetry, Syslog RFC 5424 Forwarding & Secure O&M Protocols

## Specification Reference
ITU-T Recommendation M.3400 (FCAPS: Fault, Configuration, Accounting, Performance, Security), IETF RFC 5424 (The Syslog Protocol), and IETF RFC 6241 / 8040 (NETCONF/RESTCONF).

## Technical Requirement
Network functions and radio elements must implement comprehensive FCAPS management interfaces utilizing secure protocols (SNMPv3 with authPriv, NETCONF/RESTCONF over TLS with YANG models), and forward all security-relevant audit logs formatted per RFC 5424 through a hardened bastion proxy into the operator's SIEM/SOC.

## Architecture Acceptance Criteria
- Syslog RFC 5424 structured data containing millisecond-precision UTC timestamps, facility, severity, and host identifiers.
- Segregated administration plane (out-of-band management network) isolated from user data planes.
- Disallowance of legacy cleartext protocols (SNMPv1/v2c, Telnet, unencrypted HTTP).
- High-throughput streaming telemetry (gNMI/OpenConfig or Prometheus endpoints) for real-time KPI monitoring.

