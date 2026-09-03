---
id: SNC-REQ-02
title: Cloisonnement strict du réseau d'administration et bastion d'accès
type: control
framework: SecNumCloud
version: "3.2"
jurisdiction: FR-EU
domain: [network-security,identity-access-management]
severity: mandatory
target_entities: [essential,critical-infrastructure]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: security-compliance-team
---

# SNC-REQ-02 — Cloisonnement strict de l'administration et bastion d'accès

## Référence Réglementaire
Référentiel d'exigences ANSSI SecNumCloud version 3.2, Exigence 13.1 & 13.2 (Sécurité des réseaux et des accès d'administration).

## Exigence Légale
Les réseaux d'administration doivent être physiquement ou logiquement étanches vis-à-vis des réseaux clients et du réseau public. Aucun accès d'administration direct n'est autorisé.

## Critères d'Acceptation d'Architecture
- Utilisation obligatoire d'une passerelle de rebond (bastion d'administration qualifié) avec authentification multifacteur (MFA) physique.
- Chiffrement mTLS avec certificats émis par une autorité de certification (PKI) dédiée à l'administration.
- Répudiation de tout canal d'administration direct depuis Internet : coupure protocolaire et enregistrement vidéo/session d'audit.
