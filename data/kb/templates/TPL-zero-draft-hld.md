---
id: TPL-zero-draft-hld
title: High-Level Design (HLD) Zero-Draft Deliverable Template
type: template
status: active
confidence: verified
phase: [BID, BUILD]
domain: [delivery, mcx, security]
owner: core-owner-architecture
last_reviewed: 2026-09-08
sources:
- TPL-hla-section-map
- BLU-hla-mcx
---

# High-Level Design (HLD) Zero-Draft Template

Ce template constitue la structure maîtresse du document d'architecture de haut niveau (HLD) produit automatiquement par le générateur neuro-symbolique `ZeroDraftAssembler`. Il respecte la décomposition du blueprint maître `BLU-hla-mcx.yaml` (44 sous-sections dérivées de la structure HLA mission-critical) et la matrice de projection `TPL-hla-section-map.md`.

---

# High-Level Design (HLD) — {{ PROJECT_TITLE }}

> **Engagement :** `{{ ENGAGEMENT_ID }}`  
> **Client / Destinataire :** {{ CLIENT_NAME }}  
> **Date de génération :** {{ GENERATION_DATE }}  
> **Statut du document :** `{{ STATUS }}` *(FINALISÉ ou ZERO-DRAFT - ÉLICITATION REQUISE)*  
> **Couverture Standard KB :** `{{ COVERAGE_RATE }}%` ({{ COVERED_COUNT }}/{{ TOTAL_COUNT }} exigences satisfaites d'emblée)  

---

## 1. Synthèse Exécutive & Scorecard de Conformité

### 1.1 Objet du Document & Vision Solution
Présentation synthétique de la réponse architecturale au cahier des charges émis par **{{ CLIENT_NAME }}**. La solution capitalise sur les actifs éprouvés de la base de connaissances d'architecture (ADRs, Patterns, Principes) garantissant une conformité native aux référentiels régaliens (3GPP Rel-18, NIS2, CER, CRA, RGPD, GSMA, Tier IV, PPDR).

### 1.2 Scorecard de Couverture Réglementaire & Technique
| Indicateur | Valeur | Statut d'Ingénierie |
|---|---|---|
| **Exigences Totales Analysées** | {{ TOTAL_COUNT }} | 📋 Découpées en items atomiques |
| **Conformité Standard Immédiate** | {{ COVERED_COUNT }} ({{ COVERAGE_RATE }}%) | ✅ Couvert par le socle KB |
| **Conformité Partielle** | {{ PARTIAL_COUNT }} | 🔍 Cadrage ou optionnel |
| **Écarts Résiduels (Gaps)** | {{ GAP_COUNT }} | 🚨 Questions d'élicitation émises |

---

## 2. Principes Directeurs d'Architecture (Guiding Principles)

L'ensemble de la solution est gouvernée par les principes immuables du socle :
- **`P-001` (Generalized GitOps)** : L'ensemble de la configuration réseau, radio et plateforme est déclaratif, versionné dans Git et déployé par pipelines automatisés.
- **`P-003` (Bounded Unitary Actions)** : Les boucles fermées et remédiations opèrent sur un rayon d'impact unitaire maîtrisé et prévisible.
- **`P-004` (Graduated Autonomy)** : L'autonomie opérationnelle est octroyée sur preuves mesurées en mode miroir (*shadow mode*), jamais par défaut.
- **`P-007` (Respect the Vendor Boundary)** : Respect strict des interfaces officielles des équipementiers (RAN, Core, HSM), sans altération interne.
- **`P-009` (Independent Failure Domain)** : Les chaînes de supervision, restauration et bastions ne partagent aucun chemin d'infrastructure avec les services qu'elles supervisent.
- **`P-010` (One Master per Data Domain)** : Une seule source de vérité maîtresse pour chaque domaine de données (CMDB, BSS, HSS/UDM).
- **`P-011` (Separate Observation Planes)** : Séparation étanche entre télémétrie de service applicatif et métriques de plateforme d'hébergement.
- **`P-015` (The Model Stays Inside the Trust Boundary)** : Inférence locale souveraine ; aucune donnée, métadonnée ou prompt ne franchit le périmètre de confiance.

---

## 3. Architecture de Référence & Motifs Clés (Patterns)

### 3.1 Motifs d'Infrastructure & Résilience
- **`PAT-003` (Dual-Site Active-Active Geo-Redundant Core)** : Topologie multi-datacenters Tier IV / EN 50600 Class 4 avec bascule automatique transparente (RTO < 30s, RPO = 0).
- **`PAT-004` (Isolated Local Inference & Secure Gateway)** : Passerelles d'isolation étanches, intégration HSM EAL4+ et synchronisation déterministe PTP v2.1 / GNSS Holdover > 30 jours.

### 3.2 Motifs d'Opération & Sécurité
- **`PAT-001` (Supervised Closed Loops with Human Gate)** : Automatisation supervisée des opérations NOC/SOC avec approbation humaine sur actions à criticité élevée.
- **`PAT-005` (Immutable Audit & Forensic Logging)** : Puits de logs inviolable Syslog RFC 5424 vers SIEM avec scellement cryptographique WORM.
- **`PAT-006` (Sovereign Interconnection via SEPP / N32)** : Sécurisation du roaming et des interconnexions inter-opérateurs selon 3GPP TS 33.501.

---

## 4. Décisions d'Architecture Structurantes (ADRs)

Choix technologiques éprouvés régissant la conception détaillée :
- **`ADR-0001`** : Git comme unique source de vérité pour la configuration réseau et plateforme (IaC).
- **`ADR-0005`** : Adoption exclusive de l'architecture basée sur les services (SBA) 5G avec mutual TLS et OAuth2.
- **`ADR-0007`** : Cluster d'administration dédié hors-bande avec stockage et chemins de commande étanches.
- **`ADR-0008`** : Journalisation d'audit inviolable et traçabilité médico-légale des accès opérateurs.
- **`ADR-0011`** : Inférence IA servie localement sur processeurs banalisés au sein de l'enclave souveraine.
- **`ADR-0013`** : Provisioning distant eSIM (GSMA SGP.22/32) et contrôle centralisé des identifiants matériels (Central EIR).

---

## 5. Décomposition Détaillée selon le Blueprint (44 Sections HLA)

*(Se référer au blueprint `BLU-hla-mcx.yaml` pour l'articulation détaillée)* :
1. **Périmètre & Délimitations Système** (Scope, frontières opérationnelles, interfaces externes)
2. **Couche Services Mission-Critical** (MCPTT TS 23.379, MCVideo TS 23.281, MCData TS 23.282, KMS TS 33.179)
3. **Cœur de Réseau 5GS & Contrôle de Session** (5GS SBA, AMF, SMF, UPF, NEF APIs TS 29.522, MDA TS 28.104)
4. **Transport & Réseau Sous-Jacent** (IP/MPLS, EVPN, Synchronisation IEEE 1588 PTP v2.1 / SyncE)
5. **Accès Radio & Bandes Souveraines** (Bandes PPDR 700 MHz B68/B28, Roaming MNO, Slicing)
6. **Flotte de Terminaux & Véhicules** (MIL-STD-810H, IP68/69K, ATEX Zones 1/21, ISO 11451 CEM véhicules)
7. **Plateforme d'Hébergement & Conteneurs** (Kubernetes durci, qualification Cloud souverain)
8. **Observabilité, NOC & AIOps** (FCAPS, ITIL v4, CMDB temps réel, Syslog RFC 5424)
9. **Gouvernance de Sécurité & Homologations** (NIS2 Art. 21, CER Art. 13, CRA SBOM, RGPD)

---

## 6. Matrice Triangulaire de Traçabilité des Exigences

| ID Exigence | Section RFP | Énoncé / Exigence | Statut | Actifs KB Mobilisés | Contrôles Réglementaires | Rationale / Justification |
|---|---|---|---|---|---|---|
| `{{ REQ_ID }}` | {{ SECTION }} | {{ REQUIREMENT_TEXT }} | {{ STATUS_BADGE }} | {{ MATCHED_ASSETS }} | {{ MATCHED_CONTROLS }} | {{ RATIONALE }} |

---

## 7. Plan de Traitement des Écarts & Élicitation Ciblée (Gaps)

*Section activée automatiquement en cas d'exigences spécifiques non couvertes par le standard.*

### {{ GAP_ID }} — {{ GAP_TITLE }}
- **Exigence Client :** *\"{{ GAP_TEXT }}\"*
- **Criticité :** `{{ CRITICALITY }}` | **Domaine :** `{{ CATEGORY }}`
- **Rôle sollicité pour arbitrage :** `{{ ASSIGNED_ROLE }}` *(ex. security-architect, network-architect)*
- **Question d'élicitation :** {{ QUESTION_TEXT }}
- **Options de résolution proposées :**
  1. *Option A (Extension standard) :* ...
  2. *Option B (Dérogation / Mesure compensatoire) :* ...
