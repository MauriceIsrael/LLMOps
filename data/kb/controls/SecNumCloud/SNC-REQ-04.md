---
id: SNC-REQ-04
title: Isolation de l'hyperviseur et durcissement des environnements de conteneurs
type: control
framework: SecNumCloud
version: "3.2"
jurisdiction: FR-EU
domain: [infrastructure-security,container-security]
severity: mandatory
target_entities: [essential,critical-infrastructure]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: security-compliance-team
---

# SNC-REQ-04 — Isolation de l'hyperviseur et durcissement des conteneurs

## Référence Réglementaire
Référentiel d'exigences ANSSI SecNumCloud version 3.2, Exigence 12.1 & 12.6 (Sécurité de la virtualisation et de la conteneurisation).

## Exigence Légale
L'isolation entre locataires et entre fonctions système doit résister aux attaques par canal auxiliaire et aux évasions de conteneur ou de machine virtuelle.

## Critères d'Acceptation d'Architecture
- Hyperviseur et système hôte durcis selon les guides de bonnes pratiques ANSSI (désactivation des services superflus, Secure Boot, TPM 2.0).
- Exécution des conteneurs (Rancher / Kube) en mode non-privilégié (`rootless`), interdiction du montage du socket docker/containerd, et application de profils AppArmor/SELinux stricts.
- Cloisonnement réseau inter-pods via NetworkPolicies par défaut en mode `Deny-All`.
