---
id: 3GPP-TS33501-SEPP
title: Inter-PLMN Security Edge Protection Proxy (SEPP) & Roaming Confidentiality
type: control
framework: 3GPP
version: "Rel-18"
jurisdiction: International
domain: [5g-security,roaming,boundary-protection]
severity: mandatory
target_entities: [telecom-operator, critical-communications]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: 3gpp-security-wg
---

# 3GPP-TS33501-SEPP — Inter-PLMN Security Edge Protection Proxy (SEPP) & Roaming Confidentiality

## Référence Spécification
3GPP TS 33.501, Section 5.9 : Inter-PLMN signaling security (SEPP).

## Exigence Technique
Protection de la frontière inter-opérateur par des proxys SEPP assurant le chiffrement au niveau message (PRAS/N32) et l'intégrité de la signalisation.

## Critères d'Acceptation d'Architecture
- Chiffrement au niveau applicatif N32-c / N32-f masquant les identifiants d'abonnés et la topologie interne.
- Filtrage des attaques d'injection de signalisation et de déni de service inter-opérateur.
- Auditabilité et journalisation des flux transfrontaliers sans exposition des clés maîtresses.
