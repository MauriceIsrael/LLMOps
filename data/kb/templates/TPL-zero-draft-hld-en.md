---
id: TPL-zero-draft-hld-en
title: High-Level Design (HLD) Zero-Draft Deliverable Template (English)
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

# High-Level Design (HLD) Zero-Draft Template (English)

This template follows the **Integrated Architecture Framework (IAF)** logical ordering, progressing from mission context → service model → logical architecture → physical domains → security → operations → resilience → capacity → risks → hosting → delivery. It is automatically populated by the `ZeroDraftAssembler` engine from the master blueprint `BLU-hla-mcx.yaml`.

---

# High-Level Design (HLD) — {{ PROJECT_TITLE }}

> **Engagement:** `{{ ENGAGEMENT_ID }}`
> **Client / Recipient:** {{ CLIENT_NAME }}
> **Generation Date:** {{ GENERATION_DATE }}
> **Document Status:** `{{ STATUS }}` *(FINAL or ZERO-DRAFT — ELICITATION REQUIRED)*
> **Standard KB Coverage:** `{{ COVERAGE_RATE }}%` ({{ COVERED_COUNT }}/{{ TOTAL_COUNT }} requirements satisfied out-of-the-box)
> **Blueprint Version:** `BLU-hla-mcx v{{ BLUEPRINT_VERSION }}`

---

## 1. Document Purpose, Status and Reading Guide

This document defines the preliminary high-level solution design for **{{ PROJECT_TITLE }}**. It is structured to progress from the operational context and stakeholder needs through logical and physical architecture, security governance, operational model, resilience strategy, and phased delivery roadmap.

The document is written at solution level. It describes the architecture of the overall system, including its scope, interfaces, key design choices and architectural constraints. It does not replace functional specifications or detailed design.

| Reading Guide | |
|---|---|
| **Primary audience** | Solution architects, security architects, delivery leads, client technical authority |
| **Companion documents** | RFP / Statement of Work, Compliance Matrix, Risk Register |
| **Status** | {{ STATUS }} |
| **Open items** | See §{{ OPEN_ITEMS_SECTION }} |

---

## 2. Mission, Operational Context and Stakeholders

### 2.1 Mission, Strategic Vision and Expected Outcomes

{{ PROJECT_TITLE }} is envisioned as a **sovereign, secure, and future-ready mission-critical communications system** designed to serve {{ CLIENT_DOMAIN }} operational communities. The system shall provide uninterrupted mission-critical voice, data, video and location services under normal and degraded conditions.

**Strategic objectives:**
- {{ STRATEGIC_OBJECTIVE_1 }}
- {{ STRATEGIC_OBJECTIVE_2 }}
- {{ STRATEGIC_OBJECTIVE_3 }}

### 2.2 Stakeholders and Operational Roles

| Stakeholder Group | Role | Operational Authority |
|---|---|---|
| Field Operations | Frontline users (first responders, field teams) | Subscriber / End user |
| Dispatchers & Control Rooms | Real-time coordination | Dispatcher / Supervisor |
| NOC / SOC | Network and security operations | Operator |
| System Administration | Platform and identity management | Administrator |
| {{ STAKEHOLDER_4 }} | {{ ROLE_4 }} | {{ AUTHORITY_4 }} |

### 2.3 Business Use Cases Catalog and Critical Scenarios

The platform supports the following critical communication use case families:

| Use Case Family | Service Type | Criticality |
|---|---|---|
| Mission-critical group voice (MCPTT) | Real-time PTT, group call | Critical |
| Mission-critical video (MCVideo) | Surveillance, situational awareness | High |
| Mission-critical data (MCData) | File transfer, SDS messaging | High |
| Location and common operational picture | GIS, geofencing, COP | Critical |
| Device onboarding and provisioning | SIM/eSIM, MDM, fleet | Operational |
| {{ USE_CASE_N }} | {{ SERVICE_TYPE_N }} | {{ CRITICALITY_N }} |

---

## 3. System Scope, Boundaries and External Ecosystem

### 3.1 System Scope and Operational Boundaries

| Scope Dimension | In Scope | Out of Scope / Deferred |
|---|---|---|
| **Core Network** | {{ CORE_SCOPE }} | {{ CORE_OUT }} |
| **MCX Services** | {{ MCX_SCOPE }} | {{ MCX_OUT }} |
| **RAN / Radio** | {{ RAN_SCOPE }} | {{ RAN_OUT }} |
| **Device Fleet** | {{ DEVICE_SCOPE }} | {{ DEVICE_OUT }} |
| **Security** | {{ SEC_SCOPE }} | {{ SEC_OUT }} |
| **External Systems** | {{ EXT_SCOPE }} | {{ EXT_OUT }} |

### 3.2 Out-of-Scope Items

The following items are explicitly excluded from the present scope due to insufficient information or programme phasing constraints. They shall be incorporated at a later stage subject to confirmation:

- {{ OUT_OF_SCOPE_1 }}
- {{ OUT_OF_SCOPE_2 }}
- {{ OUT_OF_SCOPE_3 }} *(e.g., E2E FRMCS integration, EUCCS interfaces)*

---

## 4. Solution Governance and Architecture Principles

### 4.1 Architecture Vision and Guiding Principles

The architecture is governed by the following system-level principles, derived from the Knowledge Hub baseline:

- **`P-001` (Generalized GitOps)**: All network, radio, and platform configuration is declarative, version-controlled in Git, and deployed exclusively through automated CI/CD pipelines.
- **`P-003` (Bounded Unitary Actions)**: Closed automation loops operate with a bounded, predictable blast radius. On unexpected failure, execution halts cleanly and escalates without hazardous compensation.
- **`P-004` (Graduated Autonomy)**: Operational autonomy is earned through measured evidence in shadow validation mode, never granted as an unverified default.
- **`P-007` (Respect the Vendor Boundary)**: Orchestration interfaces strictly through vendor-supported northbound APIs without tampering with proprietary software internals.
- **`P-009` (Independent Failure Domain)**: Recovery, backup, and observability chains share zero infrastructure with the active systems they manage.
- **`P-010` (One Master per Data Domain)**: Exactly one authoritative master system per data domain (CMDB for inventory, HSS/UDM for subscriber profiles, SM-DP+ for eSIM).
- **`P-011` (Separate Observation Planes)**: Hermetic separation between platform infrastructure telemetry and mission-critical application signalling flows.
- **`P-015` (The Model Stays Inside the Trust Boundary)**: Sovereign local inference; no prompt, context, or operational metadata leaves the secure project boundary.

### 4.2 Governance and Security Principles

**Security by Design**: Security is not an add-on but a foundational property of the architecture. All components are designed to be secure from their initial specification.

**Privacy by Design**: Personal data, location data, and communication records are protected by architectural means (tenant isolation, RBAC, pseudonymisation, retention rules) rather than process alone.

**Supply Chain Governance**: Third-party components are subject to software composition analysis, SBOM tracking, and vendor certification verification prior to integration.

**Security governance objectives:**
- Maintain strict separation between administrative, operational, and data planes
- Enforce least-privilege access across all operational profiles
- Ensure continuous compliance evidence production (automated, not periodic)
- Define explicit lines of defence (L1 Prevention / L2 Detection / L3 Response)

---

## 5. Responsibility and Demarcation Model

### 5.1 Responsibility Model

| Architecture Domain | {{ PARTY_A }} | {{ PARTY_B }} | {{ PARTY_C }} | Shared |
|---|---|---|---|---|
| Core Network | {{ RESP }} | | | |
| MCX Services | | {{ RESP }} | | |
| Transport / Underlay | | | {{ RESP }} | |
| RAN / Radio Access | | {{ RESP }} | | |
| Device Fleet & SIM | {{ RESP }} | | | |
| Security & SOC | | | | ✓ |
| OSS/BSS | {{ RESP }} | | | |
| {{ DOMAIN_N }} | | | | |

### 5.2 High-Level Boundary View

*(Architecture boundary diagram — see companion draw.io / Mermaid diagram)*

### 5.3 Shared Architecture Concerns

| Shared Concern | Owner | Consumer | Governance |
|---|---|---|---|
| PKI / Certificate Authority | {{ PKI_OWNER }} | All domains | Joint steering |
| CMDB / Source of Truth | {{ SOT_OWNER }} | OSS/BSS, Automation | {{ SOT_GOV }} |
| Security Event Logging | SOC | All domains | SOC charter |
| {{ CONCERN_N }} | {{ OWNER_N }} | {{ CONSUMER_N }} | {{ GOV_N }} |

### 5.4 Cross-Lot / Cross-Domain Dependency Register

| Dependency ID | Dependency | Providing Party | Consuming Party | Criticality |
|---|---|---|---|---|
| DEP-001 | {{ DEPENDENCY_1 }} | {{ PROVIDER }} | {{ CONSUMER }} | Critical |
| DEP-002 | {{ DEPENDENCY_2 }} | {{ PROVIDER }} | {{ CONSUMER }} | High |

---

## 6. Service Model and Critical Service Chains

### 6.1 Service Model

The service model is structured around four viewpoints:
- **Service catalogue**: the set of services delivered to end users and user organisations
- **Service-to-domain mapping**: which logical domain delivers which service
- **Critical service chains**: the end-to-end paths that must be preserved under degraded conditions
- **Target population and traffic behaviour**: the scale and nature of demand

### 6.2 Service Catalogue

| Service Layer | Service | Standard | Criticality |
|---|---|---|---|
| Mission-Critical Voice | MCPTT Group Call, Private Call, Emergency Call | 3GPP TS 23.379 | Critical |
| Mission-Critical Video | MCVideo | 3GPP TS 23.281 | High |
| Mission-Critical Data | SDS, File Transfer, MCData | 3GPP TS 23.282 | High |
| Location & COP | GIS, Geofencing, Real-time tracking | — | Critical |
| Key Management | KMS, E2E encryption | 3GPP TS 33.179 | Critical |
| Provisioning | SIM/eSIM OTA, User onboarding | GSMA SGP.22/32 | Operational |
| {{ SERVICE_N }} | {{ DESCRIPTION_N }} | {{ STANDARD_N }} | {{ CRITICALITY_N }} |

### 6.3 Critical Service Chains

| Chain ID | Chain | Traversed Domains | Priority |
|---|---|---|---|
| CSC-01 | MCPTT Emergency Call | UE → RAN → Core → MCX → Dispatcher | P1 — Highest |
| CSC-02 | Floor grant (push-to-talk access) | UE → RAN → Core → MCX floor controller | P1 |
| CSC-03 | Location update (GIS) | UE → RAN / MDM → Core → GIS | P2 |
| CSC-04 | Break-glass / admin access | OOB management network | P1 — Isolated |
| {{ CSC_N }} | {{ CHAIN_N }} | {{ DOMAINS_N }} | {{ PRIO_N }} |

### 6.4 Target Population and Traffic Behaviour

| Metric | Reference Value | Notes |
|---|---|---|
| Total subscriptions / devices | {{ SUBSCRIPTIONS }} | SOW target |
| MCX client applications | {{ MCX_CLIENTS }} | |
| Standalone dispatcher positions | {{ DISPATCHERS }} | |
| MCX talkgroups (at Final Acceptance) | {{ TALKGROUPS }} | Minimum |
| Expected devices at Final Acceptance | {{ DEVICES_FA }} | |
| IoT devices at Final Acceptance | {{ IOT_DEVICES }} | |
| Busy-hour active users | {{ BH_USERS }} | |
| MCX traffic profile | Predominantly group-based MCPTT, high concurrency, asymmetric downlink | Architecture driver |
| User organisations | {{ USER_ORGS }} | Multi-tenant |

---

## 7. Service Quality Commitments and Architecture Drivers

### 7.1 Architecture-Driving Quality Attributes

| Quality Attribute | Architecture Expectation | Architectural Consequence |
|---|---|---|
| **Availability** | Mission-critical services remain available across component, access and site failures | Geo-redundant hosting, redundant interfaces, HA design, automated failover |
| **Resilience** | Controlled degradation; essential services preserved during abnormal conditions | MCPTT voice and location prioritised over video/non-critical data |
| **Performance** | MCX, GIS, onboarding and workflows meet mission-critical latency and concurrency targets | QoS, priority/pre-emption, capacity headroom, active probes, SLA monitoring |
| **Security** | All critical service chains authenticated, authorised, protected, logged and supervised | IAM, PAM, PKI, HSM/KMS, SecGW, SOC/SIEM, EDR, IDS, audit trails |
| **Privacy** | Identity, location, CDR and operational data protected on need-to-know basis | Tenant isolation, RBAC, pseudonymisation, retention rules, auditability |
| **Interoperability** | System interworks with RANs, external domains, government services, EUCCS, future MCX | Interface catalogue, security gateways, IWFs, standards-based protocols |
| **Operational continuity** | NOC, SOC, ITSM support detection, escalation, restoration and reporting during degraded states | Break-glass procedures, DR playbooks, dashboards, dedicated operational processes |

### 7.2 MCX Performance Reference Snapshot

> These figures are included as architecture reference inputs. They confirm the scale and service quality envelope the solution must support. Detailed engineering calculations and dimensioning are addressed separately.

| Metric | Reference Value | Verification Mode |
|---|---|---|
| MCPTT access time (in-cell) | < 300 ms | Active probe |
| End-to-end MCPTT access time | < 1,000 ms | End-to-end measurement |
| Mouth-to-ear latency | < 300 ms | ITU-T P.340 |
| MCX late entry time | < 350 ms | Active probe |
| MCPTT listening quality | > 4.0 MOS | Periodic assessment |
| GIS moving-device update rate | ≤ 30 s or ≤ 200 m movement | GIS probe |
| GIS display latency | ≤ 20 s after location measurement | End-to-end |
| MCX recording retention | {{ RECORDING_RETENTION }} (e.g. 10% of calls, 1 year) | Audit |
| MCX audit information retention | ≥ {{ AUDIT_RETENTION }} (e.g. 2 years) | Compliance |
| RTO / RPO | Defined by service criticality class (see §{{ DR_SECTION }}) | DR test |

**Preliminary assumptions and open decisions** — the following shall be tracked and refined during PDR/CDR:
- Architecture is designed for SOW target scale; operational population at Final Acceptance may be lower
- MCX traffic dominated by group voice with high concurrency and asymmetric distribution
- RTO/RPO not fixed at this stage; defined by service criticality class
- Retention rules (GIS history, CDRs, MCX records, security events) to be confirmed with legal and security stakeholders

---

## 8. Logical Solution Architecture and Trust Boundaries

### 8.1 Logical Architecture Overview

The system is structured around a set of **logical domains** that cooperate to deliver mission-critical services. Each domain has a clearly defined functional scope, ownership boundary, and set of controlled external interfaces.

*(See companion logical architecture diagram — consolidated end-to-end view)*

### 8.2 Logical Domain Models

| Logical Domain | Function | Mastered By |
|---|---|---|
| MCX Services Domain | Mission-critical application services (MCPTT, MCVideo, MCData, KMS) | {{ MCX_OWNER }} |
| Core Network Domain | Subscriber management, bearer, session, mobility | {{ CORE_OWNER }} |
| Transport & Underlay Domain | IP underlay, routing, synchronisation | {{ TRANSPORT_OWNER }} |
| Radio Access Domain | Radio bearers, spectrum management | {{ RAN_OWNER }} |
| Device & Fleet Domain | Terminal lifecycle, eSIM, MDM | {{ DEVICE_OWNER }} |
| GIS / COP Domain | Location, geospatial services, operational picture | {{ GIS_OWNER }} |
| Observation Domain | Telemetry, SIEM, service assurance, NOC | {{ OBS_OWNER }} |
| Automation Domain | GitOps, closed loops, configuration management | {{ AUTO_OWNER }} |
| Security Domain | IAM, PKI, KMS, HSM, SOC | {{ SEC_OWNER }} |
| Management Domain | OSS/BSS, CMDB, ITSM | {{ MGMT_OWNER }} |

### 8.3 Separation of Architectural Planes

The logical architecture enforces **four-plane separation** to avoid functional coupling and clarify responsibilities:

| Plane | Function | Isolation Rule |
|---|---|---|
| **Service Plane** | User-facing application traffic (MCX, GIS, data) | No direct access from management interfaces |
| **Control Plane** | Signalling, session control, mobility, policy | Separated from user data; rate-limited |
| **Management Plane** | Configuration, provisioning, monitoring, ITSM | Accessible only from dedicated management network |
| **Out-of-Band (OOB) Plane** | Break-glass, recovery, bastion access | Physically or logically isolated; independent power and transport |

> *Architectural rule:* A management path that shares compute, network or storage with the service it manages violates `P-009` (Independent Failure Domain) and must be rejected.

### 8.4 Trust Boundaries

The architecture is based on **explicit trust boundaries**. Each boundary defines where responsibility transfers, where authentication is enforced, and where traffic filtering is applied.

| Trust Boundary | Between | Enforcement Mechanism |
|---|---|---|
| External / DMZ | Internet / External systems → DMZ | Firewall, SecGW, IDS/IPS |
| DMZ / Service | DMZ → Internal service plane | mTLS, application gateway |
| Service / Management | Service plane → Management plane | Dedicated VLANs, PAM, MFA |
| Management / OOB | Management → Out-of-band | Physical or cryptographic isolation |
| Tenant | User Organisation A → User Organisation B | RBAC, network isolation, data segregation |
| {{ BOUNDARY_N }} | {{ FROM_N }} → {{ TO_N }} | {{ ENFORCEMENT_N }} |

### 8.5 Tenant and Administration Boundaries

{{ PROJECT_TITLE }} is a **multi-organisation system**. Tenant and administration boundaries are central to the security model:
- Each User Organisation (UO) has its own identity namespace, network segment, and data partition
- Cross-UO data access is prohibited by default; exceptions require explicit governance approval
- Administrator roles are scoped to a single tenant unless explicitly elevated

### 8.6 Controlled Inter-Domain Flows

| Flow Family | Source | Destination | Protocol | Security |
|---|---|---|---|---|
| MCX signalling | MCX client | MCX server | SIP / SDP over TLS | mTLS, certificate |
| MCX media | MCX client | MCX server | SRTP / RTP | SRTP mandatory |
| Location update | MCX client / MDM | GIS platform | HTTPS | mTLS, token |
| OTA provisioning | SM-DP+ | eSIM | HTTPS (LPA) | Certificate |
| Management southbound | Automation engine | Network elements | NETCONF/RESTCONF | mTLS, RBAC |
| Security events | All domains | SOC/SIEM | Syslog TLS / API | Authenticated |
| {{ FLOW_N }} | {{ SRC_N }} | {{ DST_N }} | {{ PROTO_N }} | {{ SEC_N }} |

---

## 9. Mobile Core Network and Multi-RAN Integration Architecture

### 9.1 Core Network

#### 9.1.1 Functional Scope and Dual-Mode Architecture

The core network is based on a **dual-mode EPC/5GC architecture** supporting mission-critical networks. It provides:
- EPC (LTE/4G) capabilities for immediate operational continuity
- 5G Standalone (SA) readiness enabling progressive migration without service interruption
- MCX service continuity preserved across core migration phases

**Key architectural properties:**
- `ADR-0005`: 5G Service-Based Architecture (SBA) secured by mTLS and OAuth2
- All NF instances containerised and deployed on the telco cloud platform

#### 9.1.2 High Availability and Geographical Redundancy

- Active-active geo-redundant deployment across {{ N_SITES }} data centres (≥ {{ DC_DISTANCE }} km separation)
- Core NF redundancy: N+1 minimum for all stateful functions
- No single point of failure for any critical service chain (CSC-01, CSC-02)
- RTO < {{ CORE_RTO }} / RPO = {{ CORE_RPO }} for live mission-critical services

#### 9.1.3 Hardware Security Module (HSM) Usage

> *`ADR-0016`*: HSM is **mandatory** for all 5G NAS credential operations (SUCI/SUPI protection, AUSF key derivation). No software-only implementation is acceptable for a national mission-critical system.

| HSM Use Case | Protected Assets | Standard |
|---|---|---|
| 5G NAS / SUPI protection | Long-term subscriber credentials | 3GPP TS 33.501 |
| PKI root CA operations | Root and intermediate CA private keys | CC EAL4+ |
| KMS — MCX end-to-end keys | Group and individual MCX keys | 3GPP TS 33.179 |
| {{ HSM_USE_N }} | {{ ASSETS_N }} | {{ STD_N }} |

#### 9.1.4 Core Network Management

- Network management: {{ NMS_TOOL }} (e.g. Ericsson ENM or equivalent)
- Alarms, KPIs, configuration: FCAPS via northbound APIs (NETCONF/RESTCONF)
- Network-based location services: {{ LOCATION_SERVICE }}

### 9.2 Multi-RAN Integration Architecture

The system supports a **hybrid multi-RAN access strategy**:

| RAN Technology | Spectrum | Operated By | Use Case |
|---|---|---|---|
| 4G/LTE (GOV RAN) | Band {{ BAND_1 }} (e.g. B28/B68) | {{ RAN_OPERATOR }} | Primary PPDR coverage |
| 5G SA (GOV RAN) | {{ 5G_BAND }} | {{ RAN_OPERATOR }} | Evolution path |
| MNO Fallback | Commercial bands | MNO | Coverage extension, DR |
| WLAN | 2.4/5/6 GHz | Local | Indoor, campus |
| {{ RAN_N }} | {{ SPECTRUM_N }} | {{ OP_N }} | {{ USE_N }} |

---

## 10. Mission-Critical Services (MCX) Architecture

### 10.1 Layered Architecture and Logical Segmentation

The MCX service layer enforces strict segmentation based on functional role and criticality:
- A clearly defined network perimeter around the MCX domain
- Strictly controlled authorised inter-domain flows
- VLAN separation (Public / Private / Internal / Administration)
- Isolation of all administration interfaces

**Key architectural properties:**
- Resilience-oriented design: service continuity under single-site failure
- Transport-agnostic: MCX services operate independently of the underlying RAN technology
- Modular and scalable: MCX components scale horizontally without impacting other domains
- Security by design: all MCX flows authenticated, authorised and encrypted

### 10.2 Key ADRs for MCX

| ADR | Decision |
|---|---|
| `ADR-0005` | 5G SBA with mTLS for all inter-NF flows |
| `ADR-0013` | GSMA SGP.22/32 for SIM/eSIM provisioning |
| `{{ ADR_N }}` | {{ DECISION_N }} |

### 10.3 MCX Patterns

| Pattern | Application |
|---|---|
| `PAT-001` (Supervised Closed Loop) | NOC remediation on MCX alarm conditions |
| `PAT-006` (Sovereign Interconnection via SEPP/N32) | MCX roaming and inter-domain federation |
| `PAT-010` (4-Plane Network Separation) | MCX service / control / management / OOB isolation |
| `PAT-011` (MCX SLA Latency Budget) | End-to-end latency allocation per service chain component |

---

## 11. Location, GIS and Common Operational Picture Architecture

### 11.1 Scope and Objective

The GIS component provides the geospatial and cartographic capabilities required by the platform. It supports:
- Device location display and tracking
- Common Operational Picture (COP) for dispatchers and control rooms
- Situational awareness, geofencing, proximity analysis
- Correlation of identities, positions, resources, incidents and real-time events

### 11.2 Location Source Integration

| Location Source | Provider | Consumer | Update Mechanism |
|---|---|---|---|
| GNSS (MCX client) | MCX client application | GIS / COP | MCX location service |
| MDM agent location | MDM platform | GIS | MDM API push |
| RAN-derived location | Core network (TS 29.572) | GIS | Core API |
| External mapping | {{ MAP_PROVIDER }} | GIS | Tile / WMS feed |

**Performance obligations:**
- Moving-device update rate: ≤ 30 s or ≤ 200 m movement
- Display latency: ≤ 20 s after location measurement

### 11.3 Multi-Tenant and RBAC Principles

- Each User Organisation sees only its own assets and personnel on the COP
- Cross-UO visibility requires explicit governance approval and operator action
- Location history access subject to retention and privacy policy (see §{{ PRIVACY_SECTION }})

---

## 12. Subscription, SIM/eSIM, MDM and Device Ecosystem Architecture

### 12.1 SIM and eSIM Lifecycle Management

**eSIM model:**
- GSMA **SGP.22** for MCX smartphone users (consumer eSIM)
- GSMA **SGP.32** for IoT devices (industrial grade eUICC)
- **SMS-Free OTA**: all SIM management and OTA provisioning uses an OTA polling applet; no SMS dependency
- SIMs shall be **5G SA-ready from day 1**
- SM-DP+ operated by {{ SMDP_OPERATOR }}

| SIM Type | Standard | Profile Replacement Rate | OTA Method |
|---|---|---|---|
| MCX user eSIM | GSMA SGP.22 | {{ ESIM_RENEWAL_RATE }} | OTA polling applet (no SMS) |
| IoT eUICC | GSMA SGP.32 | {{ IOT_RENEWAL_RATE }} | EIM polling applet |
| Physical SIM | — | {{ PSIM_RENEWAL_RATE }} | OTA applet |

**`ADR-0013`**: GSMA SGP.22/32 with SMS-Free OTA and Central EIR equipment lifecycle management.

### 12.2 Enterprise Mobility Management (EMM/MDM) and Fleet Device Lifecycle

| Lifecycle Phase | Capability | Tool |
|---|---|---|
| Enrolment | Zero-touch provisioning, DEP/Android Zero-Touch | {{ MDM_TOOL }} |
| Configuration | Policy push, application deployment, VPN/certificate | {{ MDM_TOOL }} |
| Compliance | Device posture check, remote wipe | {{ MDM_TOOL }} |
| Retirement | Secure wipe, IMEI blacklisting via Central EIR | {{ EIR_TOOL }} |

### 12.3 Device Portfolio

| Category | Key Requirements | Certification |
|---|---|---|
| Rugged handheld | PPDR bands ({{ BANDS }}), MIL-STD-810H, IP68, ATEX (if required) | {{ CERT }} |
| Rugged tablet | Large display, vehicle mount, external antenna | {{ CERT }} |
| Hybrid device | PTT button, MCX client, MDM-managed | {{ CERT }} |
| IoT device | SGP.32 eUICC, low power, industrial grade | {{ CERT }} |

---

## 13. Operations, OSS/BSS, NOC and Service Assurance Architecture

### 13.1 OSS/BSS Architecture Overview

The OSS/BSS landscape is structured around two complementary domains aligned with TM Forum Open Digital Architecture (ODA):

**Fulfilment and Provisioning domain** — answers: *"How do we create, configure and activate a service?"*
- Product Catalogue, Product Inventory
- Customer/User Organisation management (CRM)
- Order management and provisioning workflows
- SIM/eSIM provisioning integration (SM-DP+, Central EIR)

**Assurance and Monitoring domain** — answers: *"Is the service working, and how do we fix it?"*
- FCAPS: Fault, Configuration, Accounting, Performance, Security
- Real-time CMDB synchronisation (`P-010`: one master per data domain)
- ITSM integration (incident, problem, change management)
- Service assurance dashboards and SLA tracking

### 13.2 Mastership of Data Domains

| Data Domain | Master System | Consumers |
|---|---|---|
| Physical/virtual inventory | CMDB ({{ CMDB_TOOL }}) | Automation, NOC, OSS |
| Subscriber profiles | HSS/UDM | Core, MCX, IMS |
| SIM/eSIM state | SM-DP+ + Central EIR | MDM, OSS |
| Service configuration | Git (IaC — `P-001`) | Automation engine |
| Security events | SIEM ({{ SIEM_TOOL }}) | SOC |
| {{ DOMAIN_N }} | {{ MASTER_N }} | {{ CONSUMERS_N }} |

### 13.3 NOC and Operational Automation

- Observability architecture: `P-011` (Separate Observation Planes) — service telemetry and infrastructure telemetry are hermetically separated
- Automation approach: `PAT-001` (Supervised Closed Loop) — human gate on all high-impact actions
- Evolution roadmap: supervised automation → dark NOC with graduated autonomy (`P-004`)
- ITSM integration: `ADR-0008` — immutable audit trail for all operational actions

### 13.4 Field Service Management

- Field intervention workflows integrated with ITSM
- Device QoE/QoS probes for in-field service quality measurement
- Logistics tracking for physical asset movements

---

## 14. Security and Privacy Architecture

### 14.1 Security Posture Overview

All critical service chains are **authenticated, authorised, protected, logged and supervised**. The security posture is defined by five architectural layers:

| Layer | Scope | Key Controls |
|---|---|---|
| **Perimeter** | External boundaries, DMZ | Firewall, SecGW, IDS/IPS, DDoS mitigation |
| **Platform & Workload** | Container platform, VMs, OS | CIS benchmarks, runtime security, image signing |
| **Identity & Access** | All operational profiles | IAM, PAM, MFA, certificate-based auth |
| **Data & Cryptography** | Data at rest, in transit, in use | PKI, KMS, HSM (CC EAL4+), TLS 1.3 minimum |
| **Detection & Response** | Continuous monitoring | SOC, SIEM, EDR, CSIRT, vulnerability management |

### 14.2 Security Principles and Zero-Trust Architecture

- **Least privilege**: every user, service and component receives only the permissions required for its function
- **Assume breach**: architecture assumes perimeter compromise is possible; lateral movement must be prevented
- **Verify explicitly**: every access request authenticated and authorised, regardless of source location
- **Zero standing privileges**: administrative access granted on demand with time-bound sessions

**Security zoning:**

| Zone | Content | Access Rule |
|---|---|---|
| Public / DMZ | Internet-facing interfaces, SecGW | Strictly filtered inbound |
| Service | MCX, GIS, application workloads | Service-to-service mTLS only |
| Management | OSS/BSS, automation, NOC | PAM-gated, MFA mandatory |
| Out-of-Band | Break-glass, recovery, bastion | Physically / cryptographically isolated |
| Tenant-N | UO-specific resources | No cross-tenant access by default |

### 14.3 Identity, Authentication and Access Management (IAM)

| Profile | Authentication | Authorisation | Notes |
|---|---|---|---|
| End users (field) | MCX client certificate + PIN | RBAC (UO-scoped) | 3GPP TS 33.179 |
| Dispatchers | Certificate + MFA | Dispatcher role (RBAC) | |
| Administrators | Certificate + MFA + PAM | Least-privilege, time-bounded | PAM mandatory |
| Remote administrators | Certificate + MFA + VPN | PAM-gated | Privileged access review |
| SOC operators | Certificate + MFA | Read-only on production | |
| Automated processes | Service account certificate | Scoped to function | No human-equivalent privilege |

### 14.4 Cryptographic and Data Protection Architecture

Five cryptographic use cases (UC-CRYPTO):

| Use Case | Description | HSM-backed |
|---|---|---|
| **UC-CRYPTO-01** | PKI and Certificate Lifecycle Management | Root CA: yes |
| **UC-CRYPTO-02** | Secrets Management | Secrets vault: yes |
| **UC-CRYPTO-03** | HSM-Based Protection of Cryptographic Keys and Operations | All critical keys: yes |
| **UC-CRYPTO-04** | Data Anonymisation upon Export | Export pipeline | — |
| **UC-CRYPTO-05** | Export Secure Container | Sealed export bundle | Yes |

`ADR-0016`: HSM mandatory for 5G NAS credentials (SUCI/SUPI), root CA operations, and MCX KMS key material.

### 14.5 SOC and CSIRT Operational Boundaries

| Function | Scope | Escalation Path |
|---|---|---|
| Security Operations Centre (SOC) | Continuous monitoring, alert triage, L1/L2 response | → CSIRT for confirmed incidents |
| CSIRT | Incident response, forensics, remediation coordination | → Client CISO / National authority |
| Combined SOCaaS + CSIRT | {{ SOC_MODEL }} | {{ SOC_SLA }} |
| Vulnerability Management | Continuous scanning, patch prioritisation, SBOM tracking | SOC → Change management |

### 14.6 Threat Protection and Regulatory Compliance

| Regulatory Framework | Key Requirements | Compliance Evidence |
|---|---|---|
| NIS2 Art. 21 | Risk management, incident reporting, supply chain security | Continuous automated compliance report |
| CER Art. 13 | Physical security, business continuity | DR test records, site audit |
| CRA | SBOM, vulnerability disclosure, secure development | SBOM register, CVE tracking |
| GDPR / Privacy | Data minimisation, consent, retention, breach notification | Privacy impact assessment |
| 3GPP TS 33.501 / 33.179 | 5G NAS security, MCX security | Vendor certification |
| {{ FRAMEWORK_N }} | {{ REQUIREMENT_N }} | {{ EVIDENCE_N }} |

---

## 15. External Interface and Interoperability Architecture

### 15.1 External Interface Design Principles

- All external interfaces are declared in the interface catalogue before implementation begins
- Each interface has a designated security gateway (SecGW) or application gateway
- Interface changes follow a governed change process; no ad-hoc connection is permitted
- Protocol standard compliance is mandatory (no proprietary tunnels on external interfaces)

### 15.2 External Interface Catalogue

| Interface ID | Name | External System | Protocol | Security | Direction |
|---|---|---|---|---|---|
| IF-001 | MCX Inter-system interworking | {{ IWF_SYSTEM }} | SIP/TLS, 3GPP IWF | SecGW, certificate | Bi-directional |
| IF-002 | SM-DP+ (eSIM OTA) | SM-DP+ platform | HTTPS / ES2+ | Certificate, TLS 1.3 | Outbound |
| IF-003 | Government services gateway | {{ GOV_GATEWAY }} | Restricted API | Dedicated SecGW | Bi-directional |
| IF-004 | MNO fallback / roaming | {{ MNO_NAME }} | 3GPP N32 / SEPP | SEPP (`PAT-006`) | Bi-directional |
| IF-005 | EUCCS / external interconnect | {{ EUCCS_NAME }} | {{ EUCCS_PROTO }} | SecGW | Bi-directional |
| {{ IF_N }} | {{ NAME_N }} | {{ SYSTEM_N }} | {{ PROTO_N }} | {{ SEC_N }} | {{ DIR_N }} |

### 15.3 User Organisation Connectivity and On-Premises Infrastructure

- UO connectivity model: {{ UO_CONNECTIVITY_MODEL }} (e.g., dedicated VPN, SD-WAN)
- On-premises infrastructure (dispatching positions, local gateways): {{ ONPREM_MODEL }}
- Security gateway at each UO boundary: enforced, no exceptions

---

## 16. Resilience, High Availability, Disaster Recovery and Degraded Modes

### 16.1 Hybrid Multi-RAN Access Strategy and Radio Resilience

| RAN Tier | Technology | Purpose | Fallback Behaviour |
|---|---|---|---|
| Primary (GOV RAN) | {{ PRIMARY_RAN }} | Primary PPDR coverage | Active |
| Secondary (MNO Fallback) | Commercial LTE/5G | Coverage extension, DR | Automatic on GOV RAN failure |
| WLAN | 802.11 | Indoor / campus | Supplementary |
| Other | {{ OTHER_RAN }} | {{ PURPOSE }} | {{ FALLBACK }} |

### 16.2 Data Centre High Availability Architecture

- Dual-site active-active topology: `PAT-003` (Dual-Site Active-Active Geo-Redundant Core)
- Geographic separation: ≥ {{ DC_MIN_DISTANCE }} km between primary and secondary DC
- No single point of failure on any critical service chain
- Synchronous replication for critical stateful services (subscriber data, MCX state)

### 16.3 Disaster Recovery Strategy

| Service Class | RTO Target | RPO Target | Recovery Strategy |
|---|---|---|---|
| Live mission-critical services | < {{ RTO_L1 }} | = 0 (HA) | Active-active, no recovery needed |
| Configuration state | < {{ RTO_L2 }} | < {{ RPO_L2 }} | Git-based restore (`P-001`) |
| Historical records and logs | < {{ RTO_L3 }} | < {{ RPO_L3 }} | Backup restore, asynchronous replication |
| Non-critical services | < {{ RTO_L4 }} | < {{ RPO_L4 }} | Standard backup |

> *Note:* Final RTO/RPO values, replication modes, backup frequencies and restore procedures shall be confirmed during PDR/CDR in alignment with SOW availability thresholds.

### 16.4 Graceful Degradation and Isolated Mode Operation

> Section §5.3 of blueprint `BLU-hla-mcx`: What continues to operate at a site cut off from the core, and how is priority enforced end to end?

| Degraded Scenario | Services Maintained | Services Suspended | Recovery Trigger |
|---|---|---|---|
| Site isolated (transport failure) | MCPTT local (on-site), Emergency calls | Remote coordination, full GIS | Transport restoration |
| Core partial failure | Active sessions maintained | New sessions from affected core | Core HA failover |
| Full DC loss | Secondary DC takes over | N/A (active-active) | Automatic |
| Management plane loss | Service plane continues (break-glass only) | Proactive configuration changes | OOB access |

**Break-glass procedure:** Described in the separate Break-Glass Runbook. Access via OOB plane (`P-009`).

---

## 17. Capacity, Performance, Data and Observability Architecture

### 17.1 User Population and Scale Assumptions

| Metric | Value | Source |
|---|---|---|
| Total subscriptions | {{ SUBSCRIPTIONS }} | SOW / contractual |
| Devices at Final Acceptance | {{ DEVICES_FA }} | SOW |
| IoT devices | {{ IOT_DEVICES }} | SOW |
| User organisations | {{ USER_ORGS }} | SOW |
| Busy-hour concurrent MCX sessions | {{ BH_SESSIONS }} | Traffic model |

### 17.2 MCX Traffic Model

- Traffic dominated by group-based MCPTT, high concurrency, asymmetric downlink
- Talkgroup model: {{ TALKGROUP_MODEL }}
- Busy-hour call attempt rate: {{ BHCA }}
- Concurrency ratio: {{ CONCURRENCY_RATIO }}

### 17.3 MCX Dimensioning Reference Metrics

*(These figures confirm the architecture-level scale envelope; platform dimensioning is addressed in the infrastructure chapter.)*

| Component | Dimensioning Driver | Reference Value |
|---|---|---|
| MCX server capacity | Concurrent sessions | {{ MCX_SESSIONS }} |
| Floor control throughput | Floor requests/second | {{ FLOOR_RPS }} |
| GIS platform | Location updates/second | {{ GIS_UPS }} |
| Recording platform | Storage (GB/year) | {{ RECORDING_STORAGE }} |

### 17.4 Data, Recording and Retention Assumptions

| Data Type | Retention | Storage Class | Sovereignty |
|---|---|---|---|
| MCX call recordings | {{ RECORD_RETENTION }} (e.g. 1 year, 10% of calls) | Encrypted, WORM | Sovereign territory |
| CDRs (call detail records) | {{ CDR_RETENTION }} | Encrypted archive | Sovereign territory |
| Security event logs | {{ SEC_LOG_RETENTION }} | WORM, SIEM | Sovereign territory |
| GIS location history | {{ GIS_RETENTION }} | Restricted access | Sovereign territory |
| Audit trail | {{ AUDIT_RETENTION }} (≥ 2 years) | Immutable | Sovereign territory |

---

## 18. Technical Risks, Architecture Assumptions and Open Decisions

### 18.1 Technical Risk Register

| Risk ID | Description | Probability | Impact | Mitigation |
|---|---|---|---|---|
| RISK-001 | {{ RISK_1 }} | {{ PROB }} | {{ IMPACT }} | {{ MITIGATION }} |
| RISK-002 | {{ RISK_2 }} | {{ PROB }} | {{ IMPACT }} | {{ MITIGATION }} |
| *(See companion Risk Register for full register)* | | | | |

### 18.2 Architecture Assumptions

| Assumption ID | Statement | Owner | Confirmation Stage |
|---|---|---|---|
| ASSM-001 | {{ ASSUMPTION_1 }} | {{ OWNER }} | PDR/CDR |
| ASSM-002 | {{ ASSUMPTION_2 }} | {{ OWNER }} | PDR/CDR |

### 18.3 Open Architecture Points

| OAP ID | Topic | Impact | Target Resolution |
|---|---|---|---|
| OAP-001 | {{ OPEN_POINT_1 }} | {{ IMPACT }} | {{ MILESTONE }} |
| OAP-002 | {{ OPEN_POINT_2 }} | {{ IMPACT }} | {{ MILESTONE }} |

### 18.4 Key Architecture Decisions (ADR Summary)

| ADR | Decision | Status |
|---|---|---|
| `ADR-0001` | Git as single source of truth for all network and platform state | Active |
| `ADR-0005` | 5G SBA secured by mTLS and OAuth2 | Active |
| `ADR-0007` | Dedicated out-of-band management cluster with isolated control paths | Active |
| `ADR-0008` | Immutable audit trails and forensic operator logging | Active |
| `ADR-0011` | Local LLM inference on sovereign infrastructure | Active |
| `ADR-0013` | GSMA SGP.22/32, SMS-Free OTA, Central EIR | Active |
| `ADR-0016` | HSM mandatory for 5G NAS credentials (SUCI/SUPI) | Active |
| `{{ ADR_N }}` | {{ DECISION_N }} | {{ STATUS_N }} |

---

## 19. Physical Hosting, Connectivity and Security-Zoning Reference Architecture

### 19.1 Infrastructure and Network Architecture

| Site | Role | Hosting Model | Distance |
|---|---|---|---|
| Primary DC | Active production site | {{ HOSTING_MODEL }} | — |
| Secondary DC | Active DR site | {{ HOSTING_MODEL }} | ≥ {{ DC_DISTANCE }} km |
| NOC | Network operations | {{ NOC_LOCATION }} | — |
| SOC | Security operations | {{ SOC_LOCATION }} | — |
| UO on-premises | Dispatching, local gateway | UO-operated | Multiple sites |

**DC-to-DC connectivity:** {{ DC_INTERCONNECT }} (e.g. dual dark-fibre, diverse routing, ≥ {{ BANDWIDTH }} Gbps)

### 19.2 Compute and Telco Cloud Virtualization Platform

**Architectural intent:** Provide a sovereign, telco-grade containerised hosting platform supporting both cloud-native 5G NFs and telco workloads with deterministic performance.

| Hosting Domain | Workloads | CaaS Platform | Hardware Class |
|---|---|---|---|
| Core domain | 5G NFs (AMF, SMF, UPF, ...) | {{ CAAS_CORE }} | Telco-grade (NUMA-aware) |
| MCX domain | MCX application stack | {{ CAAS_MCX }} | Standard compute |
| Management domain | OSS/BSS, ITSM, automation | {{ CAAS_MGMT }} | Standard compute |
| OOB / Break-glass | Bastion, recovery tools | {{ CAAS_OOB }} | Isolated, independent power |

**Minimum Viable Solution (MVS) dimensioning:** `{{ MVS_DESCRIPTION }}`

**Multi-environment staging:** Integration → Pre-production (shadow) → Production — governed by `PAT-002` (Shadow Validation).

### 19.3 NOC and SOC Layouts

| Operation Centre | Function | Tooling | Staffing Model |
|---|---|---|---|
| NOC | Network supervision, fault management, first-line intervention | {{ NOC_TOOLING }} | {{ NOC_STAFFING }} |
| SOC | Security monitoring, alert triage, incident coordination | {{ SOC_TOOLING }} | {{ SOC_STAFFING }} |

---

## 20. Deployment Views and Architecture Validation

### 20.1 Deployment Environments

| Environment | Purpose | Data | Access |
|---|---|---|---|
| Integration (INT) | Component integration testing | Synthetic | Dev/test team |
| Pre-production (PPD) | Acceptance testing, shadow validation | Anonymised | Test + client authority |
| Production (PROD) | Live service | Real | Operators, PAM-gated |

### 20.2 Site-Level Deployment View

*(See companion deployment diagram — site-level placement of all solution domains)*

### 20.3 Architecture Validation Boundaries

Formal architecture validation gates:
- **PDR** (Preliminary Design Review): logical architecture, interface catalogue, risk register confirmed
- **CDR** (Critical Design Review): physical architecture, HSM selection, DR test plan confirmed
- **FAT** (Factory Acceptance Test): component behaviour against specifications
- **SAT** (Site Acceptance Test): integrated system behaviour at site level
- **Final Acceptance**: SLA targets demonstrated under operational conditions

---

## 21. SoW Architecture Compliance Matrix

| SoW Requirement ID | Requirement Summary | Architecture Response | Section | Status | KB Assets |
|---|---|---|---|---|---|
| {{ REQ_ID }} | {{ REQUIREMENT_SUMMARY }} | {{ ARCHITECTURE_RESPONSE }} | §{{ SECTION }} | {{ STATUS_BADGE }} | {{ KB_ASSETS }} |

*(Full compliance matrix generated by `ZeroDraftAssembler` from RFP shredding output)*

---

## 22. RFP Gap Analysis and Targeted Elicitation Plan

*Activated automatically for requirements not covered out-of-the-box by the KB baseline.*

| Gap ID | Gap Title | Client Requirement | Criticality | Assigned Role | Elicitation Question |
|---|---|---|---|---|---|
| {{ GAP_ID }} | {{ GAP_TITLE }} | *"{{ GAP_TEXT }}"* | {{ CRITICALITY }} | {{ ROLE }} | {{ QUESTION }} |

For each gap, resolution options are:
1. *Option A (Standard extension)*: Extend an existing KB pattern or ADR to cover the requirement
2. *Option B (Compensatory measure / waiver)*: Define a local compensatory measure with formal risk acceptance

---

## 23. Staged Delivery Roadmaps

### 23.1 Business and Functional User Services Roadmap

| Phase | Milestone | User-Facing Services | Gate Condition |
|---|---|---|---|
| Phase 1 | {{ MILESTONE_1 }} | {{ SERVICES_1 }} | {{ GATE_1 }} |
| Phase 2 | {{ MILESTONE_2 }} | {{ SERVICES_2 }} | {{ GATE_2 }} |
| Phase 3 | {{ MILESTONE_3 }} | {{ SERVICES_3 }} | {{ GATE_3 }} |

### 23.2 Infrastructure and Platform Staging Roadmap ("Keep It Simple First")

| Stage | Platform State | Validation | Unlock Condition |
|---|---|---|---|
| MVS | Minimum viable platform, single site | Integration test | Core NFs operational, MCX voice functional |
| Pre-production | Full dual-site, shadow mode active | Acceptance test | All CSCs passing under simulated load |
| Production | Full platform, automated closed loops | Operational acceptance | Final Acceptance criteria met |

### 23.3 Legacy System Migration and Architectural Risk Mitigation

| Legacy System | Migration Strategy | Coexistence Period | Risk Mitigation |
|---|---|---|---|
| {{ LEGACY_1 }} | {{ STRATEGY_1 }} | {{ PERIOD_1 }} | {{ RISK_MITIGATION_1 }} |
| {{ LEGACY_2 }} | {{ STRATEGY_2 }} | {{ PERIOD_2 }} | {{ RISK_MITIGATION_2 }} |

---

## Appendix A — Acronyms and Glossary

| Acronym / Term | Definition |
|---|---|
| MCPTT | Mission Critical Push to Talk (3GPP TS 23.379) |
| MCVideo | Mission Critical Video (3GPP TS 23.281) |
| MCData | Mission Critical Data (3GPP TS 23.282) |
| KMS | Key Management System (3GPP TS 33.179) |
| EPC | Evolved Packet Core (4G LTE core network) |
| 5GC / 5G SA | 5G Core / 5G Standalone (3GPP Rel-15+) |
| HSM | Hardware Security Module (CC EAL4+) |
| SEPP | Security Edge Protection Proxy (3GPP TS 33.501) |
| SUCI / SUPI | Subscription Concealed/Permanent Identifier |
| SecGW | Security Gateway |
| GSMA SGP.22 | Remote SIM Provisioning specification for consumer eSIM |
| GSMA SGP.32 | Remote SIM Provisioning specification for IoT eUICC |
| SM-DP+ | Subscription Manager Data Preparation Plus (eSIM backend) |
| COP | Common Operational Picture |
| PPDR | Public Protection and Disaster Relief |
| IAF | Integrated Architecture Framework |
| PAM | Privileged Access Management |
| CMDB | Configuration Management Database |
| FCAPS | Fault, Configuration, Accounting, Performance, Security |
| ODA | Open Digital Architecture (TM Forum) |
| WORM | Write Once Read Many (immutable storage) |
| MOS | Mean Opinion Score (voice quality) |
| IWF | InterWorking Function |
| OOB | Out-of-Band |
| RTO | Recovery Time Objective |
| RPO | Recovery Point Objective |
| MVS | Minimum Viable Solution |
| PDR | Preliminary Design Review |
| CDR | Critical Design Review |
| FAT | Factory Acceptance Test |
| SAT | Site Acceptance Test |
| {{ TERM_N }} | {{ DEFINITION_N }} |
