---
id: 3GPP-TS33179-AFFILIATION
title: Secure User Affiliation and Mutual Authentication for Mission Critical Services
type: control
framework: 3GPP
version: "Rel-18"
jurisdiction: International
domain: [mcx-security,iam,identity]
severity: mandatory
target_entities: [telecom-operator, critical-communications]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: 3gpp-security-wg
---

# 3GPP-TS33179-AFFILIATION — Secure User Affiliation and Mutual Authentication for Mission Critical Services

## Référence Spécification
3GPP TS 33.179, Section 6 : Identity and Affiliation Security.

## Exigence Technique
Authentification mutuelle et autorisation stricte lors de l'affiliation d'un utilisateur critique à un talkgroup.

## Critères d'Acceptation d'Architecture
- Authentification mutuelle basée sur certificat d'équipement ou OpenID Connect / IdP sécurisé.
- Contrôle de plancher (Floor Control) inviolable avec horodatage et non-répudiation des prises de parole.
- Révocation et exclusion dynamique d'un terminal compromis sans impact sur les autres membres du groupe.
