---
id: 3GPP-TS33501-SBI
title: 5G Service-Based Architecture (SBA) Token Authorization & TLS Protection
type: control
framework: 3GPP
version: "Rel-18"
jurisdiction: International
domain: [5g-security,api-security,sba]
severity: mandatory
target_entities: [telecom-operator, critical-communications]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: 3gpp-security-wg
---

# 3GPP-TS33501-SBI — 5G Service-Based Architecture (SBA) Token Authorization & TLS Protection

## Référence Spécification
3GPP TS 33.501, Section 13 : Security of the Service Based Architecture (SBA).

## Exigence Technique
Protection obligatoire des interfaces SBI par transport TLS 1.3 et autorisation granulaire via jetons OAuth 2.0 émis par le NRF.

## Critères d'Acceptation d'Architecture
- Authentification mutuelle mTLS systématique entre toutes les Network Functions (NF).
- Validation de jeton d'accès OAuth 2.0 à chaque appel d'API SBI.
- Filtrage et micro-segmentation réseau inter-NF (Service Mesh / NetDevOps policy).
