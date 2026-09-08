---
id: CRA-REQ-SECBYDES-02
title: Essential Cybersecurity Requirements and Secure by Default Configuration
type: control
framework: CRA
version: "2024/2847"
jurisdiction: EU
domain: [security, hardening, device-security]
severity: mandatory
target_entities: [equipment-vendor, telecom-operator, ppdr-network]
terms: [cra, secure-by-default, security-by-design, hardening, root-of-trust, secure-boot]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: security-office
source_ref: "Cyber Resilience Act (EU) 2024/2847, Annex I Section 1"
---

# CRA-REQ-SECBYDES-02 — Essential Cybersecurity Requirements and Secure by Default Configuration

## Specification Reference
Regulation (EU) 2024/2847 (Cyber Resilience Act - CRA), Annex I Section 1 ("Essential cybersecurity requirements relating to the properties of products with digital elements").

## Technical Requirement
Products with digital elements (radio base stations, core routers, vehicle gateways, and mission-critical handhelds) must be designed, developed, and delivered in a hardened state with secure-by-default configurations, eliminating default credentials, disabling unnecessary ports/protocols, enforcing hardware-rooted integrity (Secure Boot), and protecting sensitive memory spaces against exploitation.

## Architecture Acceptance Criteria
- Hardware Root of Trust and authenticated Secure Boot verified at startup on all network nodes and field devices.
- Zero factory-default shared passwords; unique per-device cryptographic identity provisioned during manufacturing.
- Strict attack-surface minimization: unauthenticated debug interfaces (JTAG, UART, ADB) disabled or fused in production.
- Encrypted storage for all persistent user data, cryptographic keys, and operational logs.

