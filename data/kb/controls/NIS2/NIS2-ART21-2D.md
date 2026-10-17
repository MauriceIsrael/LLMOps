---
id: NIS2-ART21-2D
title: Supply Chain Security and Direct Vendor Relations
title_fr: Sécurité de la chaîne d'approvisionnement et relations avec les fournisseurs
type: control
framework: NIS2
version: 2022/2555
jurisdiction: EU
domain: [supply-chain, vendor-management]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: '2026-10-17'
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(2)(d)
terms: [supply-chain-security-baseline, northbound-interface, sbom]
checks_status: validated
checks:
- id: NIS2-ART21-2D-C1
  kind: requires
  when:
    terms_any: [managed service provider, managed services provider, third-party provider, third party provider, outsourced to, outsourcing, saas provider, cloud provider, hosting provider, external provider, infogerance, infogere, prestataire externe, prestataire de services, sous-traitance, sous-traitant, fournisseur tiers, fournisseur cloud, hebergeur]
  expect:
    terms_any: [supplier assessment, supplier security assessment, security assessment of the provider, vendor risk assessment, third-party risk, security requirements in the contract, security clauses, contractual security requirements, right to audit, audit right, iso 27001 certified, iso/iec 27001 certified, iso 27001 certification, soc 2, secnumcloud, csa star, evaluation du fournisseur, evaluation de securite du fournisseur, clauses de securite, exigences de securite contractuelles, droit d'audit, certifie iso 27001, certification iso 27001, qualifie secnumcloud]
  message: 'NIS2 Art. 21(2)(d) and 21(3): a supplier or service provider must be assessed for its security practices and bound by contractual security requirements.'
  status: validated
  review: {by: '@maintainers', at: '2026-10-17T08:57:34Z', decision: validate}
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:57:58Z'
revision: 3
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
