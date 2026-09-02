---
id: 3GPP-TS33179-KMS
title: Key Management Server (KMS) & End-to-End Media Encryption for MCX
type: control
framework: 3GPP
version: "Rel-18"
jurisdiction: International
domain: [mcx-security,cryptography,key-management]
severity: mandatory
target_entities: [telecom-operator, critical-communications]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: 3gpp-security-wg
---

# 3GPP-TS33179-KMS — Key Management Server (KMS) & End-to-End Media Encryption for MCX

## Référence Spécification
3GPP TS 33.179 / TS 33.180, Section 5 : Key Management and End-to-End Security Architecture.

## Exigence Technique
Distribution sécurisée des clés de chiffrement de groupe de bout en bout (GMK/GTK) via un Key Management Server (KMS) dédié.

## Critères d'Acceptation d'Architecture
- Chiffrement complet du média voix/vidéo/données entre terminaux sans déchiffrement au niveau du serveur MCX.
- Gestion de clés éphémères et politiques d'expiration déterministes.
- Découplage strict entre la signalisation SIP/HTTP et le flux média chiffré.
