---
id: CRA-REQ-VULN-01
title: Software Bill of Materials (SBOM), Vulnerability Handling & Patch Lifecycle
type: control
framework: CRA
version: "2024/2847"
jurisdiction: EU
domain: [supply-chain, vulnerability-management, security]
severity: mandatory
target_entities: [telecom-operator, equipment-vendor, software-supplier]
terms: [cra, sbom, cve, vulnerability-handling, patch-management, cyclonedx, spdx]
status: active
confidence: verified
last_reviewed: 2026-09-08
owner: security-office
source_ref: "Cyber Resilience Act (EU) 2024/2847, Article 13 & Annex I Section 2"
---

# CRA-REQ-VULN-01 — Software Bill of Materials (SBOM), Vulnerability Handling & Patch Lifecycle

## Specification Reference
Regulation (EU) 2024/2847 (Cyber Resilience Act - CRA), Article 13 ("Obligations of manufacturers") and Annex I Section 2 ("Vulnerability handling requirements").

## Technical Requirement
All software components, network functions (CNFs/VNFs), and hardware devices deployed within the mission-critical infrastructure must maintain machine-readable Software Bills of Materials (SBOMs), continuous vulnerability monitoring, coordinated vulnerability disclosure, and automated security patch delivery throughout their support lifecycle (minimum 5 years).

## Architecture Acceptance Criteria
- Machine-readable SBOMs (CycloneDX or SPDX format) generated and validated across all CI/CD release pipelines.
- Automated daily scanning against NVD and national vulnerability feeds for CVSS >= 7.0 (High/Critical) issues.
- Maximum remediation SLA of 7 calendar days for critical zero-day vulnerabilities in core network and terminal software.
- Secure, cryptographically signed remote firmware/software distribution mechanisms (FOTA/OTA).

