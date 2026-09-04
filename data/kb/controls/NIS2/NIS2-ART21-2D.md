---
id: NIS2-ART21-2D
title: Supply Chain Security and Direct Vendor Relations
title_fr: Sécurité de la chaîne d'approvisionnement et relations avec les fournisseurs
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [supply-chain, vendor-management]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "Directive (EU) 2022/2555 (NIS 2), Article 21(2)(d)"
terms: [supply-chain-security-baseline, northbound-interface, sbom]
---

# NIS2-ART21-2D — Supply Chain Security and Direct Vendor Relations

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21, Paragraph 2, Point (d).

## Legal Requirement
Supply chain security, including security-related aspects concerning the relationships between each entity and its direct suppliers or service providers.

## Architecture Acceptance Criteria
- Strict vendor boundary enforcement: external systems interact with domain functions exclusively via contracted, documented northbound interfaces.
- Continuous assessment of third-party software dependencies and cryptographic artifact signature verification.
- Isolated network segmentation for vendor remote maintenance and tele-operation channels.
