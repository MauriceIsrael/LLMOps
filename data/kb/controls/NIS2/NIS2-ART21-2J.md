---
id: NIS2-ART21-2J
title: Authentification multifacteur (MFA) et communications sécurisées
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [iam,mfa,secure-communications]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: security-compliance-team
---

# NIS2-ART21-2J — Authentification multifacteur (MFA) et communications sécurisées

## Référence Réglementaire
Directive (UE) 2022/2555 (NIS 2), Article 21, Paragraphe 2, Point (j).

## Exigence Légale
Utilisation de solutions d'authentification à plusieurs facteurs ou d'authentification continue, de communications vocales, vidéo et textuelles sécurisées et de systèmes sécurisés de communication d'urgence.

## Critères d'Acceptation d'Architecture
- Exigence d'authentification multifacteur forte (FIDO2/WebAuthn) pour tous les accès d'administration.
- Chiffrement de bout en bout des communications critiques voix, vidéo et données.
- Disponibilité garantie des liaisons de crise même en cas de partitionnement réseau ou d'indisponibilité WAN.
