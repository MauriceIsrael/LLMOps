---
id: TPL-zero-draft-hld
title: High-Level Design (HLD) Zero-Draft — Template de Livrable (Français)
type: template
status: active
confidence: verified
phase: [BID, BUILD]
domain: [delivery, mcx, security]
owner: core-owner-architecture
last_reviewed: 2026-09-17
sources:
- BLU-hla-mcx
- HLD-MCX-national-preliminary-v1
framework: IAF (Integrated Architecture Framework)
---

# Template HLD Zero-Draft (Français)

Ce template suit l'ordre logique du **Cadre d'Architecture Intégré (IAF)** : contexte de mission → modèle de service → architecture logique → domaines physiques → sécurité → opérations → résilience → capacité → risques → hébergement → livraison. Il est peuplé automatiquement par le moteur `ZeroDraftAssembler` depuis le blueprint maître `BLU-hla-mcx.yaml`.

---

# Architecture de Haut Niveau (HLD) — {{ PROJECT_TITLE }}

> **Engagement :** `{{ ENGAGEMENT_ID }}`
> **Client / Destinataire :** {{ CLIENT_NAME }}
> **Date de génération :** {{ GENERATION_DATE }}
> **Statut du document :** `{{ STATUS }}` *(FINALISÉ ou ZERO-DRAFT — ÉLICITATION REQUISE)*
> **Couverture Standard KB :** `{{ COVERAGE_RATE }}%` ({{ COVERED_COUNT }}/{{ TOTAL_COUNT }} exigences satisfaites d'emblée)
> **Version Blueprint :** `BLU-hla-mcx v{{ BLUEPRINT_VERSION }}`

---

## 1. Objet, Statut et Guide de Lecture

Ce document définit l'architecture de solution préliminaire de haut niveau pour **{{ PROJECT_TITLE }}**. Il progresse du contexte opérationnel et des besoins des parties prenantes vers l'architecture logique et physique, la gouvernance sécurité, le modèle opérationnel, la stratégie de résilience et le plan de livraison phasé.

Le document est rédigé au niveau solution. Il décrit l'architecture globale du système, incluant son périmètre, ses interfaces, ses choix de conception structurants et ses contraintes architecturales. Il ne se substitue pas aux spécifications fonctionnelles ni à la conception détaillée.

| Guide de lecture | |
|---|---|
| **Audience principale** | Architectes solution, architectes sécurité, chefs de projet, autorité technique client |
| **Documents complémentaires** | CCTP / Cahier des charges, Matrice de conformité, Registre des risques |
| **Statut** | {{ STATUS }} |
| **Points ouverts** | Voir §{{ OPEN_ITEMS_SECTION }} |

---

## 2. Mission, Contexte Opérationnel et Parties Prenantes

### 2.1 Mission, Vision Stratégique et Résultats Attendus

{{ PROJECT_TITLE }} est conçu comme un **système de communications mission-critiques souverain, sécurisé et pérenne** destiné à servir les communautés opérationnelles du domaine {{ CLIENT_DOMAIN }}. Le système doit fournir des services de voix, données, vidéo et localisation mission-critiques ininterrompus en conditions normales et dégradées.

**Objectifs stratégiques :**
- {{ STRATEGIC_OBJECTIVE_1 }}
- {{ STRATEGIC_OBJECTIVE_2 }}
- {{ STRATEGIC_OBJECTIVE_3 }}

### 2.2 Parties Prenantes et Rôles Opérationnels

| Groupe de parties prenantes | Rôle | Autorité opérationnelle |
|---|---|---|
| Opérations terrain | Utilisateurs finaux (premiers intervenants, équipes terrain) | Abonné / Utilisateur final |
| Dispatchers et salles de commandement | Coordination en temps réel | Dispatcher / Superviseur |
| NOC / SOC | Opérations réseau et sécurité | Opérateur |
| Administration système | Gestion plateforme et identité | Administrateur |
| {{ STAKEHOLDER_4 }} | {{ ROLE_4 }} | {{ AUTHORITY_4 }} |

### 2.3 Catalogue des Cas d'Usage Métier et Scénarios Critiques

La plateforme supporte les familles de cas d'usage de communication mission-critique suivantes :

| Famille de cas d'usage | Type de service | Criticité |
|---|---|---|
| Voix de groupe mission-critique (MCPTT) | PTT temps réel, appel de groupe | Critique |
| Vidéo mission-critique (MCVideo) | Surveillance, conscience situationnelle | Haute |
| Données mission-critiques (MCData) | Transfert de fichiers, messagerie SDS | Haute |
| Localisation et tableau de situation opérationnel | SIG, géofencing, COP | Critique |
| Embarquement et provisionnement des équipements | SIM/eSIM, MDM, flotte | Opérationnel |
| {{ USE_CASE_N }} | {{ SERVICE_TYPE_N }} | {{ CRITICALITY_N }} |

---

## 3. Périmètre Système, Frontières et Écosystème Externe

### 3.1 Périmètre Système et Frontières Opérationnelles

| Dimension du périmètre | Dans le périmètre | Hors périmètre / Différé |
|---|---|---|
| **Cœur de réseau** | {{ CORE_SCOPE }} | {{ CORE_OUT }} |
| **Services MCX** | {{ MCX_SCOPE }} | {{ MCX_OUT }} |
| **RAN / Radio** | {{ RAN_SCOPE }} | {{ RAN_OUT }} |
| **Flotte de terminaux** | {{ DEVICE_SCOPE }} | {{ DEVICE_OUT }} |
| **Sécurité** | {{ SEC_SCOPE }} | {{ SEC_OUT }} |
| **Systèmes externes** | {{ EXT_SCOPE }} | {{ EXT_OUT }} |

### 3.2 Éléments Hors Périmètre

Les éléments suivants sont explicitement exclus du périmètre actuel faute d'informations suffisantes ou pour des raisons de phasage programme. Ils seront incorporés ultérieurement sous réserve de confirmation :

- {{ OUT_OF_SCOPE_1 }}
- {{ OUT_OF_SCOPE_2 }}
- {{ OUT_OF_SCOPE_3 }} *(ex. : intégration E2E FRMCS, interfaces EUCCS)*

---

## 4. Gouvernance de Solution et Principes d'Architecture

### 4.1 Vision Architecturale et Principes Directeurs

L'architecture est gouvernée par les principes système suivants, issus de la base de connaissances :

- **`P-001` (GitOps Généralisé)** : L'ensemble de la configuration réseau, radio et plateforme est déclaratif, versionné dans Git et déployé exclusivement par des pipelines CI/CD automatisés.
- **`P-003` (Actions Unitaires Bornées)** : Les boucles d'automatisation opèrent avec un rayon d'impact borné et prévisible. En cas d'échec inattendu, l'exécution s'arrête proprement et escalade sans compensation hasardeuse.
- **`P-004` (Autonomie Progressive)** : L'autonomie opérationnelle est octroyée sur preuves mesurées en mode de validation miroir, jamais accordée par défaut non vérifié.
- **`P-007` (Respect de la Frontière Fournisseur)** : L'orchestration s'effectue strictement via les APIs northbound supportées par les fournisseurs, sans altération des composants propriétaires internes.
- **`P-009` (Domaine de Défaillance Indépendant)** : Les chaînes de récupération, sauvegarde et observabilité ne partagent aucune infrastructure avec les systèmes actifs qu'elles supervisent.
- **`P-010` (Un Maître par Domaine de Données)** : Un seul système maître autoritaire par domaine de données (CMDB pour l'inventaire, HSS/UDM pour les profils abonnés, SM-DP+ pour les eSIM).
- **`P-011` (Séparation des Plans d'Observation)** : Séparation hermétique entre la télémétrie d'infrastructure et les flux de signalisation applicatifs mission-critiques.
- **`P-015` (Le Modèle Reste dans le Périmètre de Confiance)** : Inférence locale souveraine ; aucune donnée, contexte ou métadonnée opérationnelle ne quitte le périmètre sécurisé du projet.

### 4.2 Principes de Gouvernance et de Sécurité

**Sécurité dès la conception (Security by Design)** : La sécurité n'est pas un ajout a posteriori mais une propriété fondatrice de l'architecture. Tous les composants sont conçus sécurisés dès leur spécification initiale.

**Protection de la vie privée dès la conception (Privacy by Design)** : Les données personnelles, de localisation et les enregistrements de communications sont protégés par des moyens architecturaux (isolation des tenants, RBAC, pseudonymisation, règles de rétention) et non uniquement par des processus.

**Gouvernance de la chaîne d'approvisionnement** : Les composants tiers font l'objet d'une analyse de composition logicielle (SCA), d'un suivi SBOM et d'une vérification des certifications fournisseurs avant intégration.

**Objectifs de gouvernance sécurité :**
- Maintenir une séparation stricte entre les plans administratif, opérationnel et données
- Appliquer le principe de moindre privilège à tous les profils opérationnels
- Assurer une production continue de preuves de conformité (automatisée, non périodique)
- Définir des lignes de défense explicites (L1 Prévention / L2 Détection / L3 Réponse)

---

## 5. Modèle de Responsabilité et de Démarcation

### 5.1 Modèle de Responsabilité

| Domaine architectural | {{ PARTIE_A }} | {{ PARTIE_B }} | {{ PARTIE_C }} | Partagé |
|---|---|---|---|---|
| Cœur de réseau | {{ RESP }} | | | |
| Services MCX | | {{ RESP }} | | |
| Transport / Sous-jacent | | | {{ RESP }} | |
| RAN / Accès radio | | {{ RESP }} | | |
| Flotte terminaux & SIM | {{ RESP }} | | | |
| Sécurité & SOC | | | | ✓ |
| OSS/BSS | {{ RESP }} | | | |
| {{ DOMAINE_N }} | | | | |

### 5.2 Vue des Frontières de Haut Niveau

*(Schéma de frontières architecturales — voir le diagramme draw.io / Mermaid associé)*

### 5.3 Préoccupations Architecturales Partagées

| Préoccupation partagée | Propriétaire | Consommateurs | Gouvernance |
|---|---|---|---|
| PKI / Autorité de certification | {{ PKI_OWNER }} | Tous les domaines | Comité de pilotage conjoint |
| CMDB / Source de vérité | {{ SOT_OWNER }} | OSS/BSS, Automatisation | {{ SOT_GOV }} |
| Journalisation des événements sécurité | SOC | Tous les domaines | Charte SOC |
| {{ CONCERN_N }} | {{ OWNER_N }} | {{ CONSUMER_N }} | {{ GOV_N }} |

### 5.4 Registre des Dépendances Inter-Lots / Inter-Domaines

| ID Dépendance | Dépendance | Fournisseur | Consommateur | Criticité |
|---|---|---|---|---|
| DEP-001 | {{ DEPENDENCY_1 }} | {{ PROVIDER }} | {{ CONSUMER }} | Critique |
| DEP-002 | {{ DEPENDENCY_2 }} | {{ PROVIDER }} | {{ CONSUMER }} | Haute |

---

## 6. Modèle de Service et Chaînes de Service Critiques

### 6.1 Modèle de Service

Le modèle de service s'articule autour de quatre points de vue :
- **Catalogue de services** : l'ensemble des services fournis aux utilisateurs finaux et aux organisations utilisatrices
- **Cartographie service-domaine** : quel domaine logique délivre quel service
- **Chaînes de service critiques** : les chemins bout en bout à préserver en conditions dégradées
- **Population cible et comportement du trafic** : la nature et le volume de la demande

### 6.2 Catalogue de Services

| Couche de service | Service | Standard | Criticité |
|---|---|---|---|
| Voix mission-critique | MCPTT Appel de groupe, Appel privé, Appel d'urgence | 3GPP TS 23.379 | Critique |
| Vidéo mission-critique | MCVideo | 3GPP TS 23.281 | Haute |
| Données mission-critiques | SDS, Transfert de fichiers, MCData | 3GPP TS 23.282 | Haute |
| Localisation & COP | SIG, Géofencing, Suivi temps réel | — | Critique |
| Gestion des clés | KMS, Chiffrement E2E | 3GPP TS 33.179 | Critique |
| Provisionnement | OTA SIM/eSIM, Embarquement utilisateurs | GSMA SGP.22/32 | Opérationnel |
| {{ SERVICE_N }} | {{ DESCRIPTION_N }} | {{ STANDARD_N }} | {{ CRITICALITY_N }} |

### 6.3 Chaînes de Service Critiques

| ID Chaîne | Chaîne | Domaines traversés | Priorité |
|---|---|---|---|
| CSC-01 | Appel d'urgence MCPTT | UE → RAN → Cœur → MCX → Dispatcher | P1 — Maximale |
| CSC-02 | Attribution de la parole (push-to-talk) | UE → RAN → Cœur → Contrôleur de parole MCX | P1 |
| CSC-03 | Mise à jour de position (SIG) | UE → RAN / MDM → Cœur → Plateforme SIG | P2 |
| CSC-04 | Accès brise-glace / administration | Réseau de gestion hors-bande | P1 — Isolé |
| {{ CSC_N }} | {{ CHAIN_N }} | {{ DOMAINS_N }} | {{ PRIO_N }} |

### 6.4 Population Cible et Comportement du Trafic

| Métrique | Valeur de référence | Notes |
|---|---|---|
| Total abonnements / équipements | {{ SUBSCRIPTIONS }} | Cible contractuelle |
| Applications clientes MCX | {{ MCX_CLIENTS }} | |
| Postes dispatcher autonomes | {{ DISPATCHERS }} | |
| Groupes d'appel MCX (à l'Acceptation Finale) | {{ TALKGROUPS }} | Minimum |
| Équipements attendus à l'Acceptation Finale | {{ DEVICES_FA }} | |
| Équipements IoT à l'Acceptation Finale | {{ IOT_DEVICES }} | |
| Utilisateurs actifs en heure chargée | {{ BH_USERS }} | |
| Profil de trafic MCX | Prédominance MCPTT de groupe, forte simultanéité, flux descendant asymétrique | Déterminant architectural |
| Organisations utilisatrices | {{ USER_ORGS }} | Multi-tenant |

---

## 7. Engagements de Qualité de Service et Déterminants Architecturaux

### 7.1 Attributs de Qualité Déterminant l'Architecture

| Attribut de qualité | Attente architecturale | Conséquence architecturale |
|---|---|---|
| **Disponibilité** | Les services mission-critiques restent disponibles malgré les défaillances composant, accès et site | Hébergement géo-redondant, interfaces redondantes, conception HA, basculement automatique |
| **Résilience** | Dégradation contrôlée ; services essentiels préservés en conditions anormales | Voix MCPTT et localisation prioritaires sur la vidéo et les données non critiques |
| **Performance** | MCX, SIG, embarquement et flux opérationnels satisfont les cibles de latence et simultanéité mission-critiques | QoS, priorité/préemption, marge de capacité, sondes actives, supervision des SLA |
| **Sécurité** | Toutes les chaînes de service critiques authentifiées, autorisées, protégées, journalisées et supervisées | IAM, PAM, PKI, HSM/KMS, SecGW, SOC/SIEM, EDR, IDS, pistes d'audit |
| **Confidentialité** | Identité, localisation, CDR et données opérationnelles protégées selon le besoin d'en connaître | Isolation des tenants, RBAC, pseudonymisation, règles de rétention, auditabilité |
| **Interopérabilité** | Le système interopère avec les RAN, domaines externes, services gouvernementaux, EUCCS, futurs domaines MCX | Catalogue d'interfaces, passerelles de sécurité, IWF, protocoles normalisés |
| **Continuité opérationnelle** | NOC, SOC, ITSM assurent la détection, l'escalade, la restauration et le reporting en états dégradés | Procédures brise-glace, guides DR, tableaux de bord, processus opérationnels dédiés |

### 7.2 Instantané de Référence des Performances MCX

> Ces valeurs sont incluses comme entrées de référence architecturale. Elles confirment l'enveloppe d'échelle et de qualité de service que la solution doit supporter. Les calculs d'ingénierie détaillés et le dimensionnement de plateforme sont traités séparément.

| Métrique | Valeur de référence | Mode de vérification |
|---|---|---|
| Temps d'accès MCPTT (intra-cellule) | < 300 ms | Sonde active |
| Temps d'accès MCPTT bout en bout | < 1 000 ms | Mesure E2E |
| Latence bouche à oreille | < 300 ms | ITU-T P.340 |
| Temps d'entrée tardive MCX | < 350 ms | Sonde active |
| Qualité d'écoute MCPTT | > 4,0 MOS | Évaluation périodique |
| Taux de mise à jour de position (mobile) | ≤ 30 s ou ≤ 200 m de déplacement | Sonde SIG |
| Latence d'affichage SIG | ≤ 20 s après mesure de position | E2E |
| Rétention des enregistrements MCX | {{ RECORDING_RETENTION }} (ex. : 10 % des appels, 1 an) | Audit |
| Rétention des informations d'audit MCX | ≥ {{ AUDIT_RETENTION }} (ex. : 2 ans) | Conformité |
| RTO / RPO | Définis par classe de criticité de service (voir §{{ DR_SECTION }}) | Test DR |

**Hypothèses préliminaires et décisions ouvertes** — à affiner lors des revues PDR/CDR :
- L'architecture est dimensionnée pour la cible contractuelle ; la population opérationnelle à l'Acceptation Finale peut être inférieure
- Le trafic MCX est supposé dominé par la voix de groupe avec forte simultanéité et distribution asymétrique
- Les valeurs RTO/RPO ne sont pas fixées à ce stade ; elles sont définies par classe de criticité de service
- Les règles de rétention (historique SIG, CDR, enregistrements MCX, événements sécurité) seront confirmées avec les parties prenantes légales et sécurité

---

## 8. Architecture Logique de Solution et Frontières de Confiance

### 8.1 Vue d'Ensemble de l'Architecture Logique

Le système s'articule autour d'un ensemble de **domaines logiques** qui coopèrent pour délivrer les services mission-critiques. Chaque domaine possède un périmètre fonctionnel clairement défini, une frontière de responsabilité et un ensemble d'interfaces externes contrôlées.

*(Voir le schéma d'architecture logique — vue consolidée bout en bout)*

### 8.2 Modèles de Domaines Logiques

| Domaine logique | Fonction | Maîtrisé par |
|---|---|---|
| Domaine Services MCX | Services applicatifs mission-critiques (MCPTT, MCVideo, MCData, KMS) | {{ MCX_OWNER }} |
| Domaine Cœur de Réseau | Gestion abonnés, porteur, session, mobilité | {{ CORE_OWNER }} |
| Domaine Transport & Sous-jacent | Sous-couche IP, routage, synchronisation | {{ TRANSPORT_OWNER }} |
| Domaine Accès Radio | Porteuses radio, gestion du spectre | {{ RAN_OWNER }} |
| Domaine Équipements & Flotte | Cycle de vie des terminaux, eSIM, MDM | {{ DEVICE_OWNER }} |
| Domaine SIG / COP | Localisation, services géospatiaux, tableau de situation | {{ GIS_OWNER }} |
| Domaine Observation | Télémétrie, SIEM, assurance service, NOC | {{ OBS_OWNER }} |
| Domaine Automatisation | GitOps, boucles fermées, gestion de configuration | {{ AUTO_OWNER }} |
| Domaine Sécurité | IAM, PKI, KMS, HSM, SOC | {{ SEC_OWNER }} |
| Domaine Management | OSS/BSS, CMDB, ITSM | {{ MGMT_OWNER }} |

### 8.3 Séparation des Plans Architecturaux

L'architecture logique applique une **séparation en quatre plans** pour éviter le couplage fonctionnel et clarifier les responsabilités :

| Plan | Fonction | Règle d'isolation |
|---|---|---|
| **Plan Service** | Trafic applicatif utilisateur (MCX, SIG, données) | Aucun accès direct depuis les interfaces de gestion |
| **Plan Contrôle** | Signalisation, contrôle de session, mobilité, politique | Séparé des données utilisateur ; limité en débit |
| **Plan Management** | Configuration, provisionnement, supervision, ITSM | Accessible uniquement depuis le réseau de gestion dédié |
| **Plan Hors-Bande (OOB)** | Brise-glace, récupération, accès bastion | Isolé physiquement ou logiquement ; alimentation et transport indépendants |

> *Règle architecturale :* Un chemin de gestion partageant calcul, réseau ou stockage avec le service qu'il gère viole `P-009` (Domaine de Défaillance Indépendant) et doit être rejeté.

### 8.4 Frontières de Confiance

L'architecture repose sur des **frontières de confiance explicites**. Chaque frontière définit le transfert de responsabilité, l'application de l'authentification et le filtrage du trafic.

| Frontière de confiance | Entre | Mécanisme d'application |
|---|---|---|
| Externe / DMZ | Internet / Systèmes externes → DMZ | Pare-feu, SecGW, IDS/IPS |
| DMZ / Service | DMZ → Plan service interne | mTLS, passerelle applicative |
| Service / Management | Plan service → Plan management | VLANs dédiés, PAM, MFA |
| Management / OOB | Management → Hors-bande | Isolation physique ou cryptographique |
| Tenant | Organisation A → Organisation B | RBAC, isolation réseau, ségrégation des données |
| {{ BOUNDARY_N }} | {{ FROM_N }} → {{ TO_N }} | {{ ENFORCEMENT_N }} |

### 8.5 Frontières Tenant et Administration

{{ PROJECT_TITLE }} est un **système multi-organisations**. Les frontières de tenant et d'administration sont centrales au modèle de sécurité :
- Chaque Organisation Utilisatrice (OU) dispose de son propre espace de nommage identité, segment réseau et partition de données
- L'accès inter-OU aux données est interdit par défaut ; les exceptions requièrent une approbation de gouvernance explicite
- Les rôles administrateurs sont scopés à un seul tenant sauf élévation explicite

### 8.6 Flux Inter-Domaines Contrôlés

| Famille de flux | Source | Destination | Protocole | Sécurité |
|---|---|---|---|---|
| Signalisation MCX | Client MCX | Serveur MCX | SIP / SDP over TLS | mTLS, certificat |
| Média MCX | Client MCX | Serveur MCX | SRTP / RTP | SRTP obligatoire |
| Mise à jour de position | Client MCX / MDM | Plateforme SIG | HTTPS | mTLS, jeton |
| Provisionnement OTA | SM-DP+ | eSIM | HTTPS (LPA) | Certificat |
| Management southbound | Moteur d'automatisation | Éléments réseau | NETCONF/RESTCONF | mTLS, RBAC |
| Événements sécurité | Tous domaines | SOC/SIEM | Syslog TLS / API | Authentifié |
| {{ FLOW_N }} | {{ SRC_N }} | {{ DST_N }} | {{ PROTO_N }} | {{ SEC_N }} |

---

## 9. Architecture du Cœur de Réseau et Intégration Multi-RAN

### 9.1 Cœur de Réseau

#### 9.1.1 Périmètre Fonctionnel et Architecture Dual-Mode

Le cœur de réseau repose sur une **architecture dual-mode EPC/5GC** adaptée aux réseaux mission-critiques. Il fournit :
- Capacités EPC (LTE/4G) pour la continuité opérationnelle immédiate
- Préparation au 5G Standalone (SA) permettant une migration progressive sans interruption de service
- Continuité des services MCX préservée tout au long des phases de migration du cœur

**Propriétés architecturales clés :**
- `ADR-0005` : Architecture basée sur les services 5G (SBA) sécurisée par mTLS et OAuth2
- Toutes les instances NF conteneurisées et déployées sur la plateforme cloud télécom

#### 9.1.2 Haute Disponibilité et Redondance Géographique

- Déploiement actif-actif géo-redondant sur {{ N_SITES }} centres de données (séparation ≥ {{ DC_DISTANCE }} km)
- Redondance des NF du cœur : N+1 minimum pour toutes les fonctions avec état
- Aucun point de défaillance unique sur aucune chaîne de service critique (CSC-01, CSC-02)
- RTO < {{ CORE_RTO }} / RPO = {{ CORE_RPO }} pour les services mission-critiques en vie

#### 9.1.3 Module de Sécurité Matériel (HSM) dans le Cœur de Réseau

> *`ADR-0016`* : Le HSM est **obligatoire** pour toutes les opérations de credentials NAS 5G (protection SUCI/SUPI, dérivation de clés AUSF). Aucune implémentation logicielle seule n'est acceptable pour un système mission-critique national.

| Cas d'usage HSM | Actifs protégés | Standard |
|---|---|---|
| Credentials 5G NAS / SUPI | Credentials abonnés long terme | 3GPP TS 33.501 |
| Opérations AC racine PKI | Clés privées AC racine et intermédiaires | CC EAL4+ |
| KMS — Clés MCX bout en bout | Clés MCX de groupe et individuelles | 3GPP TS 33.179 |
| {{ HSM_USE_N }} | {{ ASSETS_N }} | {{ STD_N }} |

#### 9.1.4 Gestion du Cœur de Réseau

- Gestion réseau : {{ NMS_TOOL }} (ex. : Ericsson ENM ou équivalent)
- Alarmes, KPIs, configuration : FCAPS via APIs northbound (NETCONF/RESTCONF)
- Services de localisation réseau : {{ LOCATION_SERVICE }}

### 9.2 Architecture d'Intégration Multi-RAN

Le système supporte une **stratégie d'accès multi-RAN hybride** :

| Technologie RAN | Spectre | Opéré par | Cas d'usage |
|---|---|---|---|
| 4G/LTE (RAN GOV) | Bande {{ BAND_1 }} (ex. : B28/B68) | {{ RAN_OPERATOR }} | Couverture PPDR primaire |
| 5G SA (RAN GOV) | {{ 5G_BAND }} | {{ RAN_OPERATOR }} | Trajectoire d'évolution |
| Repli MNO | Bandes commerciales | MNO | Extension de couverture, DR |
| WLAN | 2,4/5/6 GHz | Local | Intérieur, campus |
| {{ RAN_N }} | {{ SPECTRUM_N }} | {{ OP_N }} | {{ USE_N }} |

---

## 10. Architecture des Services Mission-Critiques (MCX)

### 10.1 Architecture en Couches et Segmentation Logique

La couche de service MCX applique une segmentation stricte basée sur le rôle fonctionnel et la criticité :
- Périmètre réseau clairement défini autour du domaine MCX
- Flux inter-domaines autorisés strictement contrôlés
- Séparation VLAN (Public / Privé / Interne / Administration)
- Isolation de toutes les interfaces d'administration

**Propriétés architecturales clés :**
- Conception orientée résilience : continuité de service sous défaillance d'un site unique
- Agnosticisme transport : les services MCX opèrent indépendamment de la technologie RAN sous-jacente
- Modularité et scalabilité : les composants MCX évoluent horizontalement sans impacter les autres domaines
- Sécurité dès la conception : tous les flux MCX authentifiés, autorisés et chiffrés

### 10.2 ADRs Clés pour MCX

| ADR | Décision |
|---|---|
| `ADR-0005` | SBA 5G avec mTLS pour tous les flux inter-NF |
| `ADR-0013` | GSMA SGP.22/32 pour le provisionnement SIM/eSIM |
| `{{ ADR_N }}` | {{ DECISION_N }} |

### 10.3 Patterns MCX

| Pattern | Application |
|---|---|
| `PAT-001` (Boucle Fermée Supervisée) | Remédiation NOC sur conditions d'alarme MCX |
| `PAT-006` (Interconnexion Souveraine via SEPP/N32) | Roaming MCX et fédération inter-domaines |
| `PAT-010` (Séparation en 4 Plans Réseau) | Isolation service / contrôle / management / OOB MCX |
| `PAT-011` (Budget de Latence MCX) | Allocation de latence E2E par composant de chaîne de service |

---

## 11. Architecture SIG, Localisation et Tableau de Situation Opérationnel

### 11.1 Périmètre et Objectif

Le composant SIG fournit les capacités géospatiales et cartographiques requises par la plateforme. Il supporte :
- Affichage et suivi de position des équipements
- Tableau de situation opérationnel (COP) pour les dispatchers et salles de commandement
- Conscience situationnelle, géofencing, analyse de proximité
- Corrélation des identités, positions, ressources, incidents et événements temps réel

### 11.2 Intégration des Sources de Localisation

| Source de localisation | Fournisseur | Consommateur | Mécanisme de mise à jour |
|---|---|---|---|
| GNSS (client MCX) | Application cliente MCX | SIG / COP | Service de localisation MCX |
| Agent MDM | Plateforme MDM | SIG | Push API MDM |
| Localisation dérivée RAN | Cœur de réseau (TS 29.572) | SIG | API cœur |
| Cartographie externe | {{ MAP_PROVIDER }} | SIG | Flux tuile / WMS |

**Obligations de performance :**
- Taux de mise à jour (mobile en mouvement) : ≤ 30 s ou ≤ 200 m de déplacement
- Latence d'affichage : ≤ 20 s après mesure de position

### 11.3 Principes Multi-Tenant et RBAC

- Chaque Organisation Utilisatrice voit uniquement ses propres actifs et personnels sur le COP
- La visibilité inter-OU requiert une approbation de gouvernance explicite et une action opérateur
- L'accès à l'historique de localisation est soumis aux règles de rétention et à la politique de confidentialité (voir §{{ PRIVACY_SECTION }})

---

## 12. Architecture Abonnement, SIM/eSIM, MDM et Flotte de Terminaux

### 12.1 Gestion du Cycle de Vie SIM et eSIM

**Modèle eSIM :**
- GSMA **SGP.22** pour les utilisateurs MCX sur smartphone (eSIM grand public)
- GSMA **SGP.32** pour les équipements IoT (eUICC industriel)
- **OTA sans SMS** : toute la gestion SIM et le provisionnement OTA utilisent un applet de polling OTA ; aucune dépendance SMS
- Les SIM doivent être **prêts 5G SA dès le premier jour**
- SM-DP+ opéré par {{ SMDP_OPERATOR }}

| Type SIM | Standard | Taux de renouvellement de profil | Méthode OTA |
|---|---|---|---|
| eSIM utilisateur MCX | GSMA SGP.22 | {{ ESIM_RENEWAL_RATE }} | Applet polling OTA (sans SMS) |
| eUICC IoT | GSMA SGP.32 | {{ IOT_RENEWAL_RATE }} | Applet polling EIM |
| SIM physique | — | {{ PSIM_RENEWAL_RATE }} | Applet OTA |

**`ADR-0013`** : GSMA SGP.22/32 avec OTA sans SMS et gestion du cycle de vie des équipements via Central EIR.

### 12.2 Gestion de la Mobilité d'Entreprise (EMM/MDM) et Cycle de Vie de la Flotte

| Phase du cycle de vie | Capacité | Outil |
|---|---|---|
| Embarquement | Provisionnement zéro-contact, Android Zero-Touch | {{ MDM_TOOL }} |
| Configuration | Déploiement de politiques et applications, VPN/certificat | {{ MDM_TOOL }} |
| Conformité | Contrôle de posture, effacement à distance | {{ MDM_TOOL }} |
| Retrait | Effacement sécurisé, mise sur liste noire IMEI via Central EIR | {{ EIR_TOOL }} |

### 12.3 Portefeuille de Terminaux

| Catégorie | Exigences clés | Certification |
|---|---|---|
| Terminal durci | Bandes PPDR ({{ BANDS }}), MIL-STD-810H, IP68, ATEX (si requis) | {{ CERT }} |
| Tablette durcissée | Grand écran, montage véhicule, antenne externe | {{ CERT }} |
| Terminal hybride | Bouton PTT, client MCX, géré MDM | {{ CERT }} |
| Équipement IoT | eUICC SGP.32, faible consommation, grade industriel | {{ CERT }} |

---

## 13. Architecture Opérations, OSS/BSS, NOC et Assurance Service

### 13.1 Vue d'Ensemble de l'Architecture OSS/BSS

Le paysage OSS/BSS s'articule autour de deux domaines complémentaires alignés sur l'Architecture Numérique Ouverte (ODA) TM Forum :

**Domaine Exécution et Provisionnement** — répond à : *"Comment créer, configurer et activer un service ?"*
- Catalogue et inventaire produits
- Gestion des Organisations Utilisatrices (CRM)
- Flux de gestion des commandes et workflows de provisionnement
- Intégration provisionnement SIM/eSIM (SM-DP+, Central EIR)

**Domaine Assurance et Supervision** — répond à : *"Le service fonctionne-t-il, et comment le corriger ?"*
- FCAPS : Défaillances, Configuration, Comptabilité, Performance, Sécurité
- Synchronisation CMDB temps réel (`P-010` : un maître par domaine de données)
- Intégration ITSM (gestion incidents, problèmes, changements)
- Tableaux de bord assurance service et suivi SLA

### 13.2 Maîtrise des Domaines de Données

| Domaine de données | Système maître | Consommateurs |
|---|---|---|
| Inventaire physique/virtuel | CMDB ({{ CMDB_TOOL }}) | Automatisation, NOC, OSS |
| Profils abonnés | HSS/UDM | Cœur, MCX, IMS |
| État SIM/eSIM | SM-DP+ + Central EIR | MDM, OSS |
| Configuration de service | Git (IaC — `P-001`) | Moteur d'automatisation |
| Événements sécurité | SIEM ({{ SIEM_TOOL }}) | SOC |
| {{ DOMAIN_N }} | {{ MASTER_N }} | {{ CONSUMERS_N }} |

### 13.3 NOC et Automatisation Opérationnelle

- Architecture d'observabilité : `P-011` (Séparation des Plans d'Observation) — télémétrie service et infrastructure hermétiquement séparées
- Approche d'automatisation : `PAT-001` (Boucle Fermée Supervisée) — validation humaine sur toutes les actions à fort impact
- Trajectoire d'évolution : automatisation supervisée → NOC sombre avec autonomie progressive (`P-004`)
- Intégration ITSM : `ADR-0008` — piste d'audit inviolable pour toutes les actions opérationnelles

### 13.4 Gestion des Interventions Terrain

- Flux d'intervention terrain intégrés à l'ITSM
- Sondes QoE/QoS équipements pour la mesure de la qualité de service en conditions réelles
- Suivi logistique des mouvements d'actifs physiques

---

## 14. Architecture Sécurité et Confidentialité

### 14.1 Vue d'Ensemble de la Posture Sécurité

Toutes les chaînes de service critiques sont **authentifiées, autorisées, protégées, journalisées et supervisées**. La posture sécurité est définie par cinq couches architecturales :

| Couche | Périmètre | Contrôles clés |
|---|---|---|
| **Périmètre** | Frontières externes, DMZ | Pare-feu, SecGW, IDS/IPS, atténuation DDoS |
| **Plateforme & Charges de travail** | Plateforme conteneurs, VMs, OS | Référentiels CIS, sécurité runtime, signature d'images |
| **Identité & Accès** | Tous les profils opérationnels | IAM, PAM, MFA, authentification par certificat |
| **Données & Cryptographie** | Données au repos, en transit, en usage | PKI, KMS, HSM (CC EAL4+), TLS 1.3 minimum |
| **Détection & Réponse** | Supervision continue | SOC, SIEM, EDR, CSIRT, gestion des vulnérabilités |

### 14.2 Principes de Sécurité et Architecture Zéro-Confiance

- **Moindre privilège** : chaque utilisateur, service et composant reçoit uniquement les permissions nécessaires à sa fonction
- **Supposer la compromission** : l'architecture suppose qu'une compromission du périmètre est possible ; le mouvement latéral doit être prévenu
- **Vérification explicite** : chaque demande d'accès authentifiée et autorisée, quelle que soit la source
- **Zéro privilège permanent** : les accès administrateurs sont accordés à la demande avec des sessions à durée limitée

**Zonage sécuritaire :**

| Zone | Contenu | Règle d'accès |
|---|---|---|
| Public / DMZ | Interfaces Internet, SecGW | Filtrage entrant strict |
| Service | MCX, SIG, charges applicatives | mTLS inter-service uniquement |
| Management | OSS/BSS, automatisation, NOC | Gestion via PAM, MFA obligatoire |
| Hors-bande | Brise-glace, récupération, bastion | Isolé physiquement / cryptographiquement |
| Tenant-N | Ressources dédiées à l'OU | Aucun accès inter-tenant par défaut |

### 14.3 Identité, Authentification et Gestion des Accès (IAM)

| Profil | Authentification | Autorisation | Notes |
|---|---|---|---|
| Utilisateurs finaux (terrain) | Certificat client MCX + code PIN | RBAC (scopé OU) | 3GPP TS 33.179 |
| Dispatchers | Certificat + MFA | Rôle dispatcher (RBAC) | |
| Administrateurs | Certificat + MFA + PAM | Moindre privilège, session bornée | PAM obligatoire |
| Administrateurs distants | Certificat + MFA + VPN | Accès PAM | Revue d'accès privilégié |
| Opérateurs SOC | Certificat + MFA | Lecture seule sur production | |
| Processus automatisés | Certificat compte de service | Scopé à la fonction | Aucun privilège équivalent humain |

### 14.4 Architecture Cryptographique et Protection des Données

Cinq cas d'usage cryptographiques (UC-CRYPTO) :

| Cas d'usage | Description | Protégé par HSM |
|---|---|---|
| **UC-CRYPTO-01** | PKI et Gestion du Cycle de Vie des Certificats | AC racine : oui |
| **UC-CRYPTO-02** | Gestion des Secrets | Coffre à secrets : oui |
| **UC-CRYPTO-03** | Protection HSM des Clés Cryptographiques et Opérations | Toutes clés critiques : oui |
| **UC-CRYPTO-04** | Anonymisation des Données lors de l'Export | Pipeline d'export | — |
| **UC-CRYPTO-05** | Conteneur d'Export Sécurisé | Lot d'export scellé | Oui |

`ADR-0016` : HSM obligatoire pour les credentials 5G NAS (SUCI/SUPI), les opérations AC racine et le matériel de clés KMS MCX.

### 14.5 Frontières Opérationnelles SOC et CSIRT

| Fonction | Périmètre | Chemin d'escalade |
|---|---|---|
| Centre des Opérations de Sécurité (SOC) | Supervision continue, triage alertes, réponse N1/N2 | → CSIRT pour incidents confirmés |
| CSIRT | Réponse aux incidents, forensique, coordination remédiation | → RSSI client / Autorité nationale |
| SOCaaS + CSIRT combinés | {{ SOC_MODEL }} | {{ SOC_SLA }} |
| Gestion des vulnérabilités | Analyse continue, priorisation des correctifs, suivi SBOM | SOC → Gestion des changements |

### 14.6 Protection contre les Menaces et Conformité Réglementaire

| Référentiel réglementaire | Exigences clés | Preuves de conformité |
|---|---|---|
| NIS2 Art. 21 | Gestion des risques, déclaration d'incidents, sécurité chaîne d'approvisionnement | Rapport de conformité automatisé continu |
| CER Art. 13 | Sécurité physique, continuité d'activité | Comptes-rendus de tests DR, audits de site |
| CRA | SBOM, divulgation de vulnérabilités, développement sécurisé | Registre SBOM, suivi CVE |
| RGPD / Confidentialité | Minimisation des données, consentement, rétention, notification de violation | Analyse d'impact sur la vie privée |
| 3GPP TS 33.501 / 33.179 | Sécurité NAS 5G, sécurité MCX | Certification fournisseur |
| {{ FRAMEWORK_N }} | {{ REQUIREMENT_N }} | {{ EVIDENCE_N }} |

---

## 15. Architecture des Interfaces Externes et Interopérabilité

### 15.1 Principes de Conception des Interfaces Externes

- Toutes les interfaces externes sont déclarées dans le catalogue d'interfaces avant le début de l'implémentation
- Chaque interface dispose d'une passerelle de sécurité (SecGW) ou passerelle applicative dédiée
- Les modifications d'interface suivent un processus de changement gouverné ; aucune connexion ad hoc n'est autorisée
- La conformité aux standards de protocole est obligatoire (pas de tunnels propriétaires sur les interfaces externes)

### 15.2 Catalogue des Interfaces Externes

| ID Interface | Nom | Système externe | Protocole | Sécurité | Direction |
|---|---|---|---|---|---|
| IF-001 | Interfonctionnement inter-systèmes MCX | {{ IWF_SYSTEM }} | SIP/TLS, IWF 3GPP | SecGW, certificat | Bidirectionnel |
| IF-002 | SM-DP+ (OTA eSIM) | Plateforme SM-DP+ | HTTPS / ES2+ | Certificat, TLS 1.3 | Sortant |
| IF-003 | Passerelle services gouvernementaux | {{ GOV_GATEWAY }} | API restreinte | SecGW dédié | Bidirectionnel |
| IF-004 | Repli MNO / roaming | {{ MNO_NAME }} | 3GPP N32 / SEPP | SEPP (`PAT-006`) | Bidirectionnel |
| IF-005 | EUCCS / interconnexion externe | {{ EUCCS_NAME }} | {{ EUCCS_PROTO }} | SecGW | Bidirectionnel |
| {{ IF_N }} | {{ NAME_N }} | {{ SYSTEM_N }} | {{ PROTO_N }} | {{ SEC_N }} | {{ DIR_N }} |

### 15.3 Connectivité des Organisations Utilisatrices et Infrastructure Locale

- Modèle de connectivité OU : {{ UO_CONNECTIVITY_MODEL }} (ex. : VPN dédié, SD-WAN)
- Infrastructure locale (postes de dispatching, passerelles locales) : {{ ONPREM_MODEL }}
- Passerelle de sécurité à chaque frontière OU : appliquée, sans exception

---

## 16. Résilience, Haute Disponibilité, Reprise Après Sinistre et Modes Dégradés

### 16.1 Stratégie Multi-RAN Hybride et Résilience Radio

| Niveau RAN | Technologie | Objectif | Comportement de repli |
|---|---|---|---|
| Primaire (RAN GOV) | {{ PRIMARY_RAN }} | Couverture PPDR primaire | Actif |
| Secondaire (Repli MNO) | LTE/5G commerciale | Extension de couverture, DR | Automatique en cas de défaillance RAN GOV |
| WLAN | 802.11 | Intérieur / campus | Complémentaire |
| Autre | {{ OTHER_RAN }} | {{ PURPOSE }} | {{ FALLBACK }} |

### 16.2 Architecture Haute Disponibilité des Centres de Données

- Topologie double site actif-actif : `PAT-003` (Cœur Géo-Redondant Actif-Actif Double Site)
- Séparation géographique : ≥ {{ DC_MIN_DISTANCE }} km entre le DC primaire et secondaire
- Aucun point de défaillance unique sur aucune chaîne de service critique
- Réplication synchrone pour les services stateful critiques (données abonnés, état MCX)

### 16.3 Stratégie de Reprise Après Sinistre

| Classe de service | Cible RTO | Cible RPO | Stratégie de récupération |
|---|---|---|---|
| Services mission-critiques en vie | < {{ RTO_L1 }} | = 0 (HA) | Actif-actif, aucune récupération requise |
| État de configuration | < {{ RTO_L2 }} | < {{ RPO_L2 }} | Restauration depuis Git (`P-001`) |
| Enregistrements historiques et journaux | < {{ RTO_L3 }} | < {{ RPO_L3 }} | Restauration sauvegarde, réplication asynchrone |
| Services non critiques | < {{ RTO_L4 }} | < {{ RPO_L4 }} | Sauvegarde standard |

> *Note :* Les valeurs finales RTO/RPO, les modes de réplication, les fréquences de sauvegarde et les procédures de restauration seront confirmés lors des revues PDR/CDR en alignement avec les seuils de disponibilité du CCTP.

### 16.4 Dégradation Contrôlée et Fonctionnement en Mode Isolé

> Section §5.3 du blueprint `BLU-hla-mcx` : Qu'est-ce qui continue de fonctionner sur un site coupé du cœur, et comment la priorité est-elle appliquée bout en bout ?

| Scénario dégradé | Services maintenus | Services suspendus | Déclencheur de récupération |
|---|---|---|---|
| Site isolé (coupure transport) | MCPTT local (sur site), appels d'urgence | Coordination à distance, SIG complet | Restauration du transport |
| Défaillance partielle du cœur | Sessions actives maintenues | Nouvelles sessions depuis le cœur affecté | Basculement HA du cœur |
| Perte totale d'un DC | Le DC secondaire prend le relais | S/O (actif-actif) | Automatique |
| Perte du plan management | Plan service continue (accès brise-glace uniquement) | Modifications de configuration proactives | Accès OOB |

**Procédure brise-glace :** Décrite dans le Guide Brise-Glace dédié. Accès via le plan OOB (`P-009`).

---

## 17. Architecture Capacité, Performance, Données et Observabilité

### 17.1 Population Utilisateurs et Hypothèses d'Échelle

| Métrique | Valeur | Source |
|---|---|---|
| Total abonnements | {{ SUBSCRIPTIONS }} | CCTP / contractuel |
| Équipements à l'Acceptation Finale | {{ DEVICES_FA }} | CCTP |
| Équipements IoT | {{ IOT_DEVICES }} | CCTP |
| Organisations utilisatrices | {{ USER_ORGS }} | CCTP |
| Sessions MCX simultanées en heure chargée | {{ BH_SESSIONS }} | Modèle de trafic |

### 17.2 Modèle de Trafic MCX

- Trafic dominé par le MCPTT de groupe, forte simultanéité, flux descendant asymétrique
- Modèle de groupes d'appel : {{ TALKGROUP_MODEL }}
- Taux de tentatives d'appel en heure chargée (BHCA) : {{ BHCA }}
- Taux de simultanéité : {{ CONCURRENCY_RATIO }}

### 17.3 Métriques de Référence pour le Dimensionnement MCX

*(Ces valeurs confirment l'enveloppe d'échelle architecturale ; le dimensionnement de plateforme est traité dans le chapitre infrastructure.)*

| Composant | Déterminant de dimensionnement | Valeur de référence |
|---|---|---|
| Capacité serveur MCX | Sessions simultanées | {{ MCX_SESSIONS }} |
| Débit contrôleur de parole | Requêtes de parole / seconde | {{ FLOOR_RPS }} |
| Plateforme SIG | Mises à jour de position / seconde | {{ GIS_UPS }} |
| Plateforme d'enregistrement | Stockage (Go / an) | {{ RECORDING_STORAGE }} |

### 17.4 Données, Enregistrements et Hypothèses de Rétention

| Type de données | Rétention | Classe de stockage | Souveraineté |
|---|---|---|---|
| Enregistrements d'appels MCX | {{ RECORD_RETENTION }} (ex. : 1 an, 10 % des appels) | Chiffré, WORM | Territoire souverain |
| CDR (enregistrements détaillés d'appels) | {{ CDR_RETENTION }} | Archive chiffrée | Territoire souverain |
| Journaux d'événements sécurité | {{ SEC_LOG_RETENTION }} | WORM, SIEM | Territoire souverain |
| Historique de localisation SIG | {{ GIS_RETENTION }} | Accès restreint | Territoire souverain |
| Piste d'audit | {{ AUDIT_RETENTION }} (≥ 2 ans) | Inviolable | Territoire souverain |

---

## 18. Risques Techniques, Hypothèses d'Architecture et Décisions Ouvertes

### 18.1 Registre des Risques Techniques

| ID Risque | Description | Probabilité | Impact | Atténuation |
|---|---|---|---|---|
| RISK-001 | {{ RISK_1 }} | {{ PROB }} | {{ IMPACT }} | {{ MITIGATION }} |
| RISK-002 | {{ RISK_2 }} | {{ PROB }} | {{ IMPACT }} | {{ MITIGATION }} |
| *(Voir le Registre des Risques complémentaire pour le registre complet)* | | | | |

### 18.2 Hypothèses d'Architecture

| ID Hypothèse | Énoncé | Propriétaire | Étape de confirmation |
|---|---|---|---|
| ASSM-001 | {{ ASSUMPTION_1 }} | {{ OWNER }} | PDR/CDR |
| ASSM-002 | {{ ASSUMPTION_2 }} | {{ OWNER }} | PDR/CDR |

### 18.3 Points d'Architecture Ouverts

| ID PAO | Sujet | Impact | Résolution cible |
|---|---|---|---|
| PAO-001 | {{ OPEN_POINT_1 }} | {{ IMPACT }} | {{ MILESTONE }} |
| PAO-002 | {{ OPEN_POINT_2 }} | {{ IMPACT }} | {{ MILESTONE }} |

### 18.4 Décisions d'Architecture Clés (Synthèse ADR)

| ADR | Décision | Statut |
|---|---|---|
| `ADR-0001` | Git comme unique source de vérité pour l'état réseau et plateforme | Actif |
| `ADR-0005` | SBA 5G sécurisé par mTLS et OAuth2 | Actif |
| `ADR-0007` | Cluster de management dédié hors-bande avec chemins de contrôle isolés | Actif |
| `ADR-0008` | Pistes d'audit inviolables et journalisation forensique opérateur | Actif |
| `ADR-0011` | Inférence IA locale sur infrastructure souveraine | Actif |
| `ADR-0013` | GSMA SGP.22/32, OTA sans SMS, Central EIR | Actif |
| `ADR-0016` | HSM obligatoire pour les credentials 5G NAS (SUCI/SUPI) | Actif |
| `{{ ADR_N }}` | {{ DECISION_N }} | {{ STATUS_N }} |

---

## 19. Hébergement Physique, Connectivité et Architecture de Référence de Zonage Sécuritaire

### 19.1 Architecture Réseau et Infrastructure

| Site | Rôle | Modèle d'hébergement | Distance |
|---|---|---|---|
| DC Primaire | Site de production actif | {{ HOSTING_MODEL }} | — |
| DC Secondaire | Site DR actif | {{ HOSTING_MODEL }} | ≥ {{ DC_DISTANCE }} km |
| NOC | Opérations réseau | {{ NOC_LOCATION }} | — |
| SOC | Opérations sécurité | {{ SOC_LOCATION }} | — |
| Local OU | Dispatching, passerelle locale | Opéré par l'OU | Sites multiples |

**Connectivité inter-DC :** {{ DC_INTERCONNECT }} (ex. : double fibre noire, routage diversifié, ≥ {{ BANDWIDTH }} Gbps)

### 19.2 Plateforme de Calcul et de Virtualisation Cloud Télécom

**Intention architecturale :** Fournir une plateforme d'hébergement conteneurisée, souveraine et de grade télécom, supportant les NF 5G cloud-native et les charges télécom avec des performances déterministes.

| Domaine d'hébergement | Charges de travail | Plateforme CaaS | Classe matériel |
|---|---|---|---|
| Domaine cœur | NF 5G (AMF, SMF, UPF, ...) | {{ CAAS_CORE }} | Grade télécom (NUMA-aware) |
| Domaine MCX | Pile applicative MCX | {{ CAAS_MCX }} | Calcul standard |
| Domaine management | OSS/BSS, ITSM, automatisation | {{ CAAS_MGMT }} | Calcul standard |
| OOB / Brise-glace | Bastion, outils de récupération | {{ CAAS_OOB }} | Isolé, alimentation indépendante |

**Dimensionnement Solution Minimale Viable (MVS) :** `{{ MVS_DESCRIPTION }}`

**Environnements multi-étapes :** Intégration → Pré-production (miroir) → Production — gouverné par `PAT-002` (Validation Miroir).

### 19.3 Plans NOC et SOC

| Centre d'opérations | Fonction | Outillage | Modèle de permanence |
|---|---|---|---|
| NOC | Supervision réseau, gestion des défaillances, intervention premier niveau | {{ NOC_TOOLING }} | {{ NOC_STAFFING }} |
| SOC | Supervision sécurité, triage alertes, coordination incidents | {{ SOC_TOOLING }} | {{ SOC_STAFFING }} |

---

## 20. Vues de Déploiement et Frontières de Validation Architecturale

### 20.1 Environnements de Déploiement

| Environnement | Objectif | Données | Accès |
|---|---|---|---|
| Intégration (INT) | Tests d'intégration des composants | Synthétiques | Équipe dev/test |
| Pré-production (PPD) | Tests d'acceptation, validation miroir | Anonymisées | Test + autorité technique client |
| Production (PROD) | Service en vie | Réelles | Opérateurs, PAM obligatoire |

### 20.2 Vue de Déploiement Site par Site

*(Voir le schéma de déploiement — placement au niveau site de tous les domaines de la solution)*

### 20.3 Jalons de Validation Architecturale

Jalons formels de validation architecturale :
- **PDR** (Revue Préliminaire de Conception) : architecture logique, catalogue d'interfaces, registre des risques confirmés
- **CDR** (Revue Critique de Conception) : architecture physique, sélection HSM, plan de test DR confirmés
- **FAT** (Tests de Recette Usine) : comportement des composants vis-à-vis des spécifications
- **SAT** (Tests de Recette Site) : comportement du système intégré en conditions de site
- **Acceptation Finale** : cibles SLA démontrées en conditions opérationnelles réelles

---

## 21. Matrice de Conformité Architecturale au CCTP

| ID Exigence CCTP | Synthèse de l'exigence | Réponse architecturale | Section | Statut | Actifs KB |
|---|---|---|---|---|---|
| {{ REQ_ID }} | {{ REQUIREMENT_SUMMARY }} | {{ ARCHITECTURE_RESPONSE }} | §{{ SECTION }} | {{ STATUS_BADGE }} | {{ KB_ASSETS }} |

*(Matrice de conformité complète générée par `ZeroDraftAssembler` à partir de l'analyse du CCTP)*

---

## 22. Analyse des Écarts RFP et Plan d'Élicitation Ciblée

*Activée automatiquement pour les exigences non couvertes d'emblée par le socle KB.*

| ID Écart | Titre | Exigence client | Criticité | Rôle assigné | Question d'élicitation |
|---|---|---|---|---|---|
| {{ GAP_ID }} | {{ GAP_TITLE }} | *"{{ GAP_TEXT }}"* | {{ CRITICALITY }} | {{ ROLE }} | {{ QUESTION }} |

Pour chaque écart, les options de résolution sont :
1. *Option A (Extension standard)* : Étendre un pattern ou ADR KB existant pour couvrir l'exigence
2. *Option B (Mesure compensatoire / dérogation)* : Définir une mesure locale avec acceptation formelle du risque

---

## 23. Feuilles de Route de Livraison Phasée

### 23.1 Feuille de Route Fonctionnelle des Services Utilisateurs

| Phase | Jalon | Services exposés aux utilisateurs | Condition de passage |
|---|---|---|---|
| Phase 1 | {{ MILESTONE_1 }} | {{ SERVICES_1 }} | {{ GATE_1 }} |
| Phase 2 | {{ MILESTONE_2 }} | {{ SERVICES_2 }} | {{ GATE_2 }} |
| Phase 3 | {{ MILESTONE_3 }} | {{ SERVICES_3 }} | {{ GATE_3 }} |

### 23.2 Feuille de Route Infrastructure et Plateforme ("Simplicité d'Abord")

| Étape | État de la plateforme | Validation | Condition de déblocage |
|---|---|---|---|
| MVS | Plateforme minimale viable, site unique | Test d'intégration | NF cœur opérationnels, voix MCX fonctionnelle |
| Pré-production | Double site complet, mode miroir actif | Test d'acceptation | Toutes les CSC validées sous charge simulée |
| Production | Plateforme complète, boucles automatisées | Acceptation opérationnelle | Critères d'Acceptation Finale satisfaits |

### 23.3 Stratégie de Migration des Systèmes Existants et Atténuation des Risques

| Système existant | Stratégie de migration | Période de coexistence | Atténuation des risques |
|---|---|---|---|
| {{ LEGACY_1 }} | {{ STRATEGY_1 }} | {{ PERIOD_1 }} | {{ RISK_MITIGATION_1 }} |
| {{ LEGACY_2 }} | {{ STRATEGY_2 }} | {{ PERIOD_2 }} | {{ RISK_MITIGATION_2 }} |

---

## Annexe A — Acronymes et Glossaire

| Acronyme / Terme | Définition |
|---|---|
| MCPTT | Mission Critical Push to Talk (3GPP TS 23.379) |
| MCVideo | Mission Critical Video (3GPP TS 23.281) |
| MCData | Mission Critical Data (3GPP TS 23.282) |
| KMS | Système de Gestion des Clés (3GPP TS 33.179) |
| EPC | Evolved Packet Core (cœur de réseau LTE 4G) |
| 5GC / 5G SA | Cœur 5G / 5G Standalone (3GPP Rel-15+) |
| HSM | Module de Sécurité Matériel (CC EAL4+) |
| SEPP | Security Edge Protection Proxy (3GPP TS 33.501) |
| SUCI / SUPI | Identifiant d'Abonné Dissimulé / Permanent |
| SecGW | Passerelle de Sécurité |
| GSMA SGP.22 | Spécification Remote SIM Provisioning eSIM grand public |
| GSMA SGP.32 | Spécification Remote SIM Provisioning eUICC IoT |
| SM-DP+ | Subscription Manager Data Preparation Plus (backend eSIM) |
| COP | Tableau de Situation Opérationnel |
| PPDR | Protection du Public et Secours en cas de Catastrophe |
| IAF | Cadre d'Architecture Intégré |
| PAM | Gestion des Accès Privilégiés |
| CMDB | Base de Données de Gestion des Configurations |
| FCAPS | Défaillances, Configuration, Comptabilité, Performance, Sécurité |
| ODA | Architecture Numérique Ouverte (TM Forum) |
| WORM | Write Once Read Many (stockage inviolable) |
| MOS | Mean Opinion Score (qualité vocale) |
| IWF | Fonction d'Interfonctionnement |
| OOB | Hors-Bande |
| RTO | Objectif de Délai de Récupération |
| RPO | Objectif de Point de Récupération |
| MVS | Solution Minimale Viable |
| PDR | Revue Préliminaire de Conception |
| CDR | Revue Critique de Conception |
| FAT | Tests de Recette Usine |
| SAT | Tests de Recette Site |
| {{ TERM_N }} | {{ DEFINITION_N }} |
