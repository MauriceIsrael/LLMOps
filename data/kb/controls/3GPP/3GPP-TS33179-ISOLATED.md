---
id: 3GPP-TS33179-ISOLATED
title: Autonomous Security and Key Distribution in Isolated Local Site Operation (IOPS)
type: control
framework: 3GPP
version: "Rel-18"
jurisdiction: International
domain: [mcx-security,resilience,isolated-operation]
severity: mandatory
target_entities: [telecom-operator, critical-communications]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: 3gpp-security-wg
---

# 3GPP-TS33179-ISOLATED — Autonomous Security and Key Distribution in Isolated Local Site Operation (IOPS)

## Référence Spécification
3GPP TS 33.179 / TS 23.379 : Isolated Operation for Public Safety (IOPS).

## Exigence Technique
Maintien autonome de la sécurité, de l'authentification et de la distribution des clés sur un site local isolé sans connectivité cœur national.

## Critères d'Acceptation d'Architecture
- Cache local sécurisé des accréditations et clés de groupe autorisées sur site.
- Capacité du serveur MCX local à opérer en autonomie sans validation temps-réel du cœur central.
- Réconciliation sécurisée sans conflit lors du rétablissement de la liaison WAN.
