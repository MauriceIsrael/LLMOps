# Rapport de migration de l'ontologie depuis la fixture d'Archinex

Généré par `scripts/migrate_ontology_from_fixture.py` (issue #192). **Aide à la relecture** : chaque ajout est de la doctrine à valider par les experts du domaine ; les conflits ne sont **pas** tranchés (la valeur du Hub est conservée).

## Synthèse

- Entités : 46 → **114** (73 ajoutées, 24 enrichies, 10 conflit(s) conservés côté Hub).
- Feuilles : 22 → **63** ; avec `projections` : 6 → **63**.
- Triplets : 60 → **205** (115 repris, 37 `satisfies_clause` générés, 38 écartés).
- Titres différents conservés côté Hub (sans conflit de fond) : 38.
- Données de projet retirées : 42.
- Doublons d'URN retirés : 5 (voir ci-dessous).

## À trancher par les experts : conflits (valeur du Hub conservée)

### `urn:archinex:ontology:concept:telco_cloud_platform` : `domain`

- **Hub (conservé)** : `"telecom"`
- **Fixture d'Archinex** : `"infrastructure"`

### `urn:archinex:ontology:infrastructure:compute:suse_telco_cloud_sylva` : `hydration_template`

- **Hub (conservé)** : `{"nautobot_device": {"role": "worker", "device_type": "HPE-ProLiant-DL380", "status": "planned", "cluster_pool": "sylva-standard-nis2", "dataplane_profile": "Standard Kernel CNI (Flannel/Cilium) + Hardening CIS Benchmark L2"}, "k8s_manifest": {"apiVersion": "infrastructure.cluster.x-k8s.io/v1alpha5", "kind": "BareMetalHost"}}`
- **Fixture d'Archinex** : `{"nautobot_device": {"role": "worker", "device_type": "HPE-ProLiant-DL380", "status": "planned", "cluster_pool": "sylva-standard-nis2", "dataplane_profile": "CNI Cilium Standard + NetworkPolicies NIS2"}, "k8s_manifest": {"apiVersion": "infrastructure.cluster.x-k8s.io/v1alpha5", "kind": "BareMetalHost"}}`

### `urn:archinex:ontology:security:zone:oam` : `keywords`

- **Hub (conservé)** : `["oam", "administration", "zone-securite", "firewall", "bastion", "nis2", "pci-dss", "segmentation"]`
- **Fixture d'Archinex** : `["oam", "exploitation", "bastion", "proxy", "isolation", "nis2", "zone", "sécurité", "admin"]`

### `urn:archinex:ontology:security:zone:oam` : `hydration_template`

- **Hub (conservé)** : `{"security_zone": {"name": "ZONE-OAM-SECURE", "nis2_tier": "critical", "ingress_firewall": "next-gen-fw-oam-01", "mfa_enforced": true}}`
- **Fixture d'Archinex** : `{"security_zone": {"zone_id": "ZONE-OAM", "isolation_level": "strict", "proxy_required": true}}`

### `urn:archinex:ontology:security:zone:oam` : `governed_by_clauses`

- **Hub (conservé)** : `["urn:archinex:kb:clause:3gpp:ts33_501_oam_segregation", "urn:archinex:kb:clause:nis2:art21_network_segregation"]`
- **Fixture d'Archinex** : `["urn:archinex:kb:clause:nis2:oam_strict_bastion"]`

### `urn:archinex:ontology:security:zone:oam` : `oracle_rules+projections`

- **Hub (conservé)** : `{"oracle_rules": ["data.archinex.edp.multiaxis.deny_insecure_security_zone"], "projections": {"isolation_level": "air-gap-logical", "bastion_required": true}}`
- **Fixture d'Archinex** : `{"oracle_rules": ["data.archinex.edp.multiaxis.deny_missing_oam_zone", "data.archinex.edp.multiaxis.deny_weak_oam_isolation", "data.archinex.edp.multiaxis.deny_unproxied_oam_access"], "projections": {"isolation_level": "strict", "proxy_required": true}}`

### `urn:archinex:ontology:telecom:network:oob` : `keywords`

- **Hub (conservé)** : `["oob", "hors-bande", "out-of-band", "bmc", "idrac", "ilo", "console", "management", "switch-oob"]`
- **Fixture d'Archinex** : `["oob", "hors-bande", "bmc", "idrac", "ilo", "redfish", "administration", "management", "ipmi"]`

### `urn:archinex:ontology:telecom:network:oob` : `hydration_template`

- **Hub (conservé)** : `{"network_segment": {"vlan_id": 999, "name": "OOB-MGMT-VRF", "subnet": "192.168.99.0/24", "dhcp_isolated": true}}`
- **Fixture d'Archinex** : `{"nautobot_interfaces": [{"name": "oob0", "type": "management", "ip": "192.0.2.10/24"}, {"name": "eth0", "type": "data", "ip": "10.20.0.10/24"}]}`

### `urn:archinex:ontology:telecom:network:oob` : `governed_by_clauses`

- **Hub (conservé)** : `["urn:archinex:kb:clause:3gpp:ts33_501_oam_segregation"]`
- **Fixture d'Archinex** : `["urn:archinex:kb:clause:telecom:oob_isolation"]`

### `urn:archinex:ontology:telecom:network:oob` : `oracle_rules+projections`

- **Hub (conservé)** : `{"oracle_rules": ["data.archinex.edp.multiaxis.deny_shared_oob_network"], "projections": {"requires_dedicated_vrf": true, "max_latency_ms": 50}}`
- **Fixture d'Archinex** : `{"oracle_rules": ["data.archinex.edp.multiaxis.deny_invalid_device_status", "data.archinex.edp.multiaxis.deny_insufficient_interfaces", "data.archinex.edp.multiaxis.deny_missing_oob_ip", "data.archinex.edp.multiaxis.deny_bmc_oob_drift"], "projections": {"required_status": "planned", "min_interfaces": 2}}`

## Doublons d'URN retirés (à confirmer par les experts)

Entités d'origine Hub qui désignent le même concept qu'une entité d'Archinex sous une autre URN. Les relations qui les touchaient sont reportées sur l'URN conservée (ou écartées si elles y existaient déjà) ; leurs règles d'oracle n'avaient pas d'implémentation côté Archinex. Rien d'autre n'est retiré.

- `urn:archinex:ontology:axis:environment_isomorphism` → `urn:archinex:ontology:axis:env_fidelity`
- `urn:archinex:ontology:axis:oob_management_plane` → `urn:archinex:ontology:axis:oob_management`
- `urn:archinex:ontology:axis:security_zoning_nis2` → `urn:archinex:ontology:axis:security_zoning`
- `urn:archinex:ontology:environment:staging_isoprod` → `urn:archinex:ontology:platform:env:iso_prod_3tiers`
- `urn:archinex:ontology:facilities:power:feed_2n` → `urn:archinex:ontology:facilities:power:dual_feed_2n`

Triplets reportés sur l'URN conservée : aucun. Triplets écartés (déjà présents) : `tr-002`, `tr-003`, `tr-004`, `tr-010a`, `tr-011a`, `tr-012a`, `tr-013a`.

## Données de projet retirées de la migration

- `urn:archinex:ontology:application:broadcast:embms_5mbs_group_broadcast` · `governed_by_clauses` : « REQ-MCX-eMBMS-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:application:gis:central_fusion_hybrid_geofencing` · `governed_by_clauses` : « REQ-Lot1-786 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:application:gis:central_fusion_hybrid_geofencing` · `governed_by_clauses` : « REQ-Lot1-795 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:application:gis:central_fusion_hybrid_geofencing` · `governed_by_clauses` : « REQ-Lot1-819 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:application:gis:central_fusion_hybrid_geofencing` · `governed_by_clauses` : « REQ-Lot1-830 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:application:gis:central_fusion_server_only_geofencing` · `governed_by_clauses` : « REQ-Lot1-786 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:application:gis:central_fusion_server_only_geofencing` · `governed_by_clauses` : « REQ-Lot1-795 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:application:gis:distributed_terminal_geofencing` · `governed_by_clauses` : « REQ-Lot1-819 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:application:gis:distributed_terminal_geofencing` · `governed_by_clauses` : « REQ-Lot1-830 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:concept:telco_cloud_platform` · `keywords` : mot-clé « lulu » (marque de projet)
- `urn:archinex:ontology:endpoint:crypto:fbe_hardware_keystore` · `governed_by_clauses` : « REQ-Endpoint-Crypto-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:endpoint:mdm:emm_zero_touch_enrollment` · `governed_by_clauses` : « REQ-Endpoint-MDM-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:endpoint:mdm:onprem_sovereign_emm` · `governed_by_clauses` : « REQ-Endpoint-MDM-02 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:endpoint:os:hardened_verified_boot` · `governed_by_clauses` : « REQ-Endpoint-OS-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:endpoint:ota:signed_ab_staged_rollout` · `governed_by_clauses` : « REQ-Endpoint-OTA-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:endpoint:sandbox:dedicated_kiosk_cobo` · `governed_by_clauses` : « REQ-Endpoint-Sandbox-02 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:endpoint:sandbox:work_profile_strict_isolation` · `governed_by_clauses` : « REQ-Endpoint-Sandbox-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:facilities:power:dual_feed_2n` · `governed_by_clauses` : « REQ-Lot1-269 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:infrastructure:compute:suse_telco_cloud_sylva` · `governed_by_clauses` : « REQ-Lot1-271 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:infrastructure:server:baremetal` · `governed_by_clauses` : « REQ-Lot1-268 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:network:interworking:atsss_multipath_steering` · `governed_by_clauses` : « REQ-Telecom-WLAN-02 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:network:interworking:n3iwf_epdg_ipsec` · `governed_by_clauses` : « REQ-Telecom-WLAN-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:operations:assurance:e2e_probes_5qi_qos` · `governed_by_clauses` : « REQ-OSS-Assurance-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:operations:cmdb:nautobot_itsm_reconciliation` · `governed_by_clauses` : « REQ-OSS-CMDB-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:operations:oss:mno_mocn_adapter_mediation` · `governed_by_clauses` : « REQ-OSS-MOCN-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:operations:oss:unified_nrm_ts28532_mediation` · `governed_by_clauses` : « REQ-OSS-NRM-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:operations:smo:graduated_hitl_remediation` · `governed_by_clauses` : « REQ-SMO-HITL-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:platform:env:iso_prod_3tiers` · `governed_by_clauses` : « REQ-Lot1-Env-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256` · `governed_by_clauses` : « REQ-Lot1-1343 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256` · `keywords` : mot-clé « lot3 » (marque de projet)
- `urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256` · `keywords` : mot-clé « lot 3 » (marque de projet)
- `urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256` · `projections.required_mediation_hops` : valeur d'instance d'un scénario de projet
- `urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256` · `hydration_template.mediation_chain` : valeur d'instance d'un scénario de projet
- `urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256` · `hydration_template.partner_tenant_id` : valeur d'instance d'un scénario de projet
- `urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256` · `hydration_template.reconciliation_graph` : valeur d'instance d'un scénario de projet
- `urn:archinex:ontology:security:esim:smdp_onprem_sovereign_hsm` · `governed_by_clauses` : « REQ-Telecom-eSIM-02 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:security:esim:smdp_sas_sm_eu_hsm` · `governed_by_clauses` : « REQ-Telecom-eSIM-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:security:pki:endpoint_scep_est_enrollment` · `governed_by_clauses` : « REQ-Endpoint-PKI-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:security:pqc:hybrid_mlkem_mldsa_agility` · `governed_by_clauses` : « REQ-Sec-PQC-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:security:zone:oam` · `governed_by_clauses` : « REQ-Lot1-SecZone-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:telecom:core:slicing_5qi_sst_isolation` · `governed_by_clauses` : « REQ-Core-Slicing-01 » n'est pas une URN de clause (identifiant d'exigence de projet)
- `urn:archinex:ontology:telecom:network:oob` · `governed_by_clauses` : « REQ-Lot1-OOB-01 » n'est pas une URN de clause (identifiant d'exigence de projet)

## Entités enrichies (champ absent du Hub complété ; `revision` incrémentée)

- `urn:archinex:ontology:concept:iam_security_zerotrust` : keywords (révision 1 → 2)
- `urn:archinex:ontology:concept:interconnection_gateway` : keywords (révision 1 → 2)
- `urn:archinex:ontology:concept:observability_noc_soc` : keywords (révision 1 → 2)
- `urn:archinex:ontology:concept:resilience_drp_continuity` : keywords (révision 1 → 2)
- `urn:archinex:ontology:concept:storage_data_persistence` : keywords (révision 1 → 2)
- `urn:archinex:ontology:concept:telco_cloud_platform` : keywords (révision 1 → 2)
- `urn:archinex:ontology:facilities:power:ups_battery_backup` : keywords, hydration_template, projections (révision 1 → 2)
- `urn:archinex:ontology:infrastructure:compute:suse_telco_cloud_sylva` : governed_by_clauses, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:infrastructure:server:baremetal` : governed_by_clauses (révision 1 → 2)
- `urn:archinex:ontology:observability:noc:alertmanager_slo_burnrate` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:observability:soc:siem_syslog_tls_nis2` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:observability:telemetry:otel_prometheus_loki` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:resilience:drp:active_active_stretched` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:resilience:drp:active_passive_warm_standby` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:resilience:testing:automated_gameday_quarterly` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:security:crypto:luks2_kms_hsm` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:security:iam:oidc_fido2_rbac` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:security:pki:cert_manager_spiffe_mtls` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:security:secrets:vault_dynamic_leases` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:storage:backup:s3_object_lock_worm` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:storage:csi:ceph_rbd_3replicas` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:storage:s3:object_erasure_coding` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)
- `urn:archinex:ontology:telecom:network:spine_leaf_evpn` : keywords, hydration_template, oracle_rules, projections (révision 1 → 2)

## Entités ajoutées

- `urn:archinex:ontology:application:broadcast:embms_5mbs_group_broadcast` (leaf, révision 1) : Diffusion Multicast/Broadcast eMBMS / 5MBS Authentifiée avec Repli Unicast (ptt-server)
- `urn:archinex:ontology:application:gis:central_fusion_hybrid_geofencing` (leaf, révision 1) : Fusion Centrale sur Serveur SIG (gis-server) & Géofencing Hybride (Relais Terminal ptt-server)
- `urn:archinex:ontology:application:gis:central_fusion_server_only_geofencing` (leaf, révision 1) : Fusion & Géofencing 100 % Centralisés sur Serveur SIG (gis-server seul)
- `urn:archinex:ontology:application:gis:distributed_terminal_geofencing` (leaf, révision 1) : Fusion & Géofencing Distribués côté Serveur Temps Réel / Terminal (ptt-server principal, gis-server passif)
- `urn:archinex:ontology:application:gis:geoserver_postgis_offline` (leaf, révision 1) : Serveur Cartographique GeoServer + PostGIS & Cache Tuiles Hors Ligne
- `urn:archinex:ontology:application:gis:qgis_server_wmts` (leaf, révision 1) : QGIS Server & MapProxy pour Rendu Cartographique OGC Souverain
- `urn:archinex:ontology:axis:cmdb_asset_inventory` (axis, révision 1) : Axe de Raffinement : Inventaire Réseau, CMDB & Réconciliation ITSM
- `urn:archinex:ontology:axis:core_5g_network_slicing` (axis, révision 1) : Axe de Raffinement : Tranchage Réseau 5G (Network Slicing SST / S-NSSAI / 5QI)
- `urn:archinex:ontology:axis:dns_dhcp_ipam` (axis, révision 1) : Axe de Raffinement : Services Réseau Fondamentaux (DNS, DHCP, IPAM)
- `urn:archinex:ontology:axis:egress_filtering_proxy` (axis, révision 1) : Axe de Raffinement : Proxy Sortant Explicite & Filtrage FQDN
- `urn:archinex:ontology:axis:embms_multicast_broadcast` (axis, révision 1) : Axe de Raffinement : Diffusion Multicast / Broadcast Groupe MCX (eMBMS / 5MBS)
- `urn:archinex:ontology:axis:endpoint_app_sandboxing` (axis, révision 1) : Axe de Raffinement : Cloisonnement Applicatif, Profil Professionnel & Sandboxing Terminal
- `urn:archinex:ontology:axis:endpoint_local_encryption` (axis, révision 1) : Axe de Raffinement : Chiffrement Local des Données Terminal (FBE / BitLocker / LUKS2)
- `urn:archinex:ontology:axis:endpoint_mdm_enrollment` (axis, révision 1) : Axe de Raffinement : Gestion de Flotte MDM / EMM & Enrôlement des Terminaux
- `urn:archinex:ontology:axis:endpoint_os_hardening` (axis, révision 1) : Axe de Raffinement : Durcissement OS Terminal, Verified Boot & Attestation Matérielle
- `urn:archinex:ontology:axis:endpoint_ota_updates` (axis, révision 1) : Axe de Raffinement : Mises à Jour OTA Signées, Partitionnement A/B & Rollback Automatique
- `urn:archinex:ontology:axis:endpoint_pki_enrollment` (axis, révision 1) : Axe de Raffinement : Enrôlement PKI des Terminaux (SCEP / EST / ACME)
- `urn:archinex:ontology:axis:env_fidelity` (axis, révision 1) : Axe de Raffinement : Fidélité & Parité des Environnements (Dev/Rec/Prod)
- `urn:archinex:ontology:axis:esim_smdp_provisioning` (axis, révision 1) : Axe de Raffinement : Provisioning eSIM SM-DP+ (GSMA SGP.22), SAS-SM & 4-Yeux
- `urn:archinex:ontology:axis:gis_location_fusion` (axis, révision 1) : Axe de Raffinement : Fusion de Localisation Multi-Sources, Cloisonnement & Géofencing SIG
- `urn:archinex:ontology:axis:gis_tile_engine` (axis, révision 1) : Axe de Raffinement : Serveur Cartographique SIG / GIS & Tuiles Hors Ligne
- `urn:archinex:ontology:axis:hsm_key_custody` (axis, révision 1) : Axe de Raffinement : Racine Matérielle HSM & Cérémonie de Clés
- `urn:archinex:ontology:axis:ingress_reverse_proxy` (axis, révision 1) : Axe de Raffinement : Reverse Proxy Ingress, TLS & WAF
- `urn:archinex:ontology:axis:non3gpp_wlan_interworking` (axis, révision 1) : Axe de Raffinement : Interworking Wi-Fi / WLAN Offload Non-3GPP (N3IWF / ePDG / ATSSS)
- `urn:archinex:ontology:axis:oci_artifact_registry` (axis, révision 1) : Axe de Raffinement : Registre d'Artéfacts OCI Signé & Scanner CVE
- `urn:archinex:ontology:axis:oob_management` (axis, révision 1) : Axe de Raffinement : Plan d'Administration Hors-Bande (OOB / Redfish)
- `urn:archinex:ontology:axis:oss_automation_hitl` (axis, révision 1) : Axe de Raffinement : Automatisation SMO/OSS, Corrélation RCA & Human-in-the-Loop
- `urn:archinex:ontology:axis:oss_smo_mediation` (axis, révision 1) : Axe de Raffinement : Médiation OSS / EMS & Modèle NRM Unifié (3GPP TS 28.532)
- `urn:archinex:ontology:axis:pam_admin_bastion` (axis, révision 1) : Axe de Raffinement : Bastion d'Administration PAM en Coupure Zone OAM
- `urn:archinex:ontology:axis:pki_3gpp_ndsaf` (axis, révision 1) : Axe de Raffinement : PKI Télécom 3GPP TS 33.310 (CMPv2 / NDS-AF)
- `urn:archinex:ontology:axis:pki_hierarchy` (axis, révision 1) : Axe de Raffinement : Hiérarchie PKI (Racine Hors Ligne & Autorités Intermédiaires)
- `urn:archinex:ontology:axis:pqc_crypto_agility` (axis, révision 1) : Axe de Raffinement : Cryptographie Post-Quantique (PQC) & Crypto-Agilité
- `urn:archinex:ontology:axis:security_zoning` (axis, révision 1) : Axe de Raffinement : Zonage de Sécurité & Cloisonnement NIS2
- `urn:archinex:ontology:axis:service_assurance_probes` (axis, révision 1) : Axe de Raffinement : Assurance de Service, Sondes Actives & Gouvernance QoS 5QI
- `urn:archinex:ontology:axis:timing_sync_ntp` (axis, révision 1) : Axe de Raffinement : Synchronisation Temporelle GNSS / IEEE 1588v2 / NTP
- `urn:archinex:ontology:axis:vault_unseal_mode` (axis, révision 1) : Axe de Raffinement : Coffre de Secrets & Déverrouillage Automatique PKCS#11
- `urn:archinex:ontology:endpoint:crypto:fbe_hardware_keystore` (leaf, révision 1) : Chiffrement Local File-Based Encryption (FBE) Ancré sur Keystore Matériel (endpoint-os-profile)
- `urn:archinex:ontology:endpoint:mdm:emm_zero_touch_enrollment` (leaf, révision 1) : Enrôlement Zero-Touch Supervisé via Plateforme MDM / EMM (mdm-emm)
- `urn:archinex:ontology:endpoint:mdm:onprem_sovereign_emm` (leaf, révision 1) : Enrôlement EMM Souverain On-Premises Déconnecté (mdm-emm)
- `urn:archinex:ontology:endpoint:os:hardened_verified_boot` (leaf, révision 1) : OS Terminal Durci avec Verified Boot, SELinux Enforcing & Attestation Matérielle (endpoint-os-profile)
- `urn:archinex:ontology:endpoint:ota:signed_ab_staged_rollout` (leaf, révision 1) : Déploiement OTA Signé par Vagues avec Partitionnement A/B & Rollback Automatique (mdm-emm)
- `urn:archinex:ontology:endpoint:sandbox:dedicated_kiosk_cobo` (leaf, révision 1) : Mode Kiosque Dédié COBO & Liste Blanche Applicative Stricte (endpoint-os-profile)
- `urn:archinex:ontology:endpoint:sandbox:work_profile_strict_isolation` (leaf, révision 1) : Conteneurisation Profil Professionnel COPE & Cloisonnement Inter-Applications (endpoint-os-profile)
- `urn:archinex:ontology:facilities:power:dual_feed_2n` (leaf, révision 1) : Alimentation Électrique Redondante Dual-Feed (2N)
- `urn:archinex:ontology:facilities:timing:gnss_ieee1588_stratum1` (leaf, révision 1) : Horloge Maître Redondante GNSS + Holdover Oscillateur Atomique (IEEE 1588v2 / NTP Stratum-1)
- `urn:archinex:ontology:network:dns:unbound_bind9_kea` (leaf, révision 1) : Services DNSSEC Unbound/Bind9 HA (Split-Horizon + RPZ) & Kea DHCP
- `urn:archinex:ontology:network:ingress:envoy_coraza_waf` (leaf, révision 1) : Reverse Proxy Ingress Envoy + WAF OWASP Coraza CRS en DMZ
- `urn:archinex:ontology:network:interworking:atsss_multipath_steering` (leaf, révision 1) : Pilotage Multi-Accès ATSSS 5G + WLAN avec N3IWF Chiffré (n3iwf-epdg-gateway)
- `urn:archinex:ontology:network:interworking:n3iwf_epdg_ipsec` (leaf, révision 1) : Passerelle N3IWF / ePDG avec Tunnel IPsec IKEv2 EAP-AKA' (n3iwf-epdg-gateway)
- `urn:archinex:ontology:network:proxy:squid_explicit_fqdn` (leaf, révision 1) : Proxy Sortant Explicite Squid DMZ avec Liste Blanche FQDN
- `urn:archinex:ontology:operations:assurance:e2e_probes_5qi_qos` (leaf, révision 1) : Sondes Actives Bout-en-Bout Non-Invasives & Référentiel QoS 5QI (oss-smo-mediation)
- `urn:archinex:ontology:operations:cmdb:nautobot_itsm_reconciliation` (leaf, révision 1) : Référentiel Source-of-Truth OSS/Nautobot Synchronisé avec la CMDB ITSM (cmdb-inventory)
- `urn:archinex:ontology:operations:oss:mno_mocn_adapter_mediation` (leaf, révision 1) : Médiation OSS MOCN Multi-Connecteurs MNO (RESTCONF / NETCONF / Kafka / SNMP)
- `urn:archinex:ontology:operations:oss:unified_nrm_ts28532_mediation` (leaf, révision 1) : Couche de Médiation OSS avec NRM Unifié 3GPP TS 28.532 (oss-smo-mediation)
- `urn:archinex:ontology:operations:smo:graduated_hitl_remediation` (leaf, révision 1) : Remédiation SMO Graduée avec Approbation Humaine Obligatoire sur Actions Critiques (oss-smo-mediation)
- `urn:archinex:ontology:platform:env:iso_prod_3tiers` (leaf, révision 1) : Topologie 3 Environnements (Dev / Recette Iso-Prod / Prod)
- `urn:archinex:ontology:platform:registry:harbor_cosign_trivy` (leaf, révision 1) : Registre OCI Souverain Harbor HA (Réplication Air-Gap, Cosign & Trivy)
- `urn:archinex:ontology:security:bastion:teleport_recorded_session` (leaf, révision 1) : Bastion Teleport Cloud-Native (Certificats SSH Éphémères & Audit Kubernetes)
- `urn:archinex:ontology:security:bastion:wallix_pam` (leaf, révision 1) : Bastion PAM Wallix / CyberArk (Rupture Protocolaire SSH/RDP & Traçabilité Vidéo)
- `urn:archinex:ontology:security:esim:smdp_onprem_sovereign_hsm` (leaf, révision 1) : SM-DP+ Souverain On-Premises Déconnecté Adossé au HSM Racine (esim-smdp)
- `urn:archinex:ontology:security:esim:smdp_sas_sm_eu_hsm` (leaf, révision 1) : Service Managé SM-DP+ Certifié GSMA SAS-SM en UE avec HSM FIPS 140-3 L3 & 4-Yeux (esim-smdp)
- `urn:archinex:ontology:security:hsm:eviden_proteccio` (leaf, révision 1) : HSM Réseau Eviden Proteccio (Qualifié ANSSI / CC EAL4+ / FIPS 140-3 L3)
- `urn:archinex:ontology:security:hsm:thales_luna` (leaf, révision 1) : HSM Réseau Thales Luna (FIPS 140-3 L3 / PKCS#11 HA)
- `urn:archinex:ontology:security:hsm:utimaco_secserver` (leaf, révision 1) : HSM Utimaco SecurityServer (FIPS 140-3 L3 / CC EAL4+)
- `urn:archinex:ontology:security:pki:ejbca_cmpv2` (leaf, révision 1) : PKI Télécom Keyfactor EJBCA (CMPv2 3GPP TS 33.310 / SCEP / ACME)
- `urn:archinex:ontology:security:pki:endpoint_scep_est_enrollment` (leaf, révision 1) : Enrôlement Automatique de Certificats Terminaux via SCEP / EST (pki-ca)
- `urn:archinex:ontology:security:pki:root_offline_airgap` (leaf, révision 1) : PKI Deux Niveaux : Autorité Racine Hors Ligne (HSM) & Subordonnées en Ligne
- `urn:archinex:ontology:security:pki:step_ca_acme_internal` (leaf, révision 1) : Autorité Intermédiaire Smallstep step-ca (ACME / OIDC) adossée au HSM
- `urn:archinex:ontology:security:pqc:hybrid_mlkem_mldsa_agility` (leaf, révision 1) : Profil Crypto-Agile Hybride Classique + PQC ML-KEM / ML-DSA (pki-ca)
- `urn:archinex:ontology:security:vault:hashicorp_enterprise_hsm` (leaf, révision 1) : HashiCorp Vault Enterprise HA avec Seal HSM PKCS#11
- `urn:archinex:ontology:security:vault:openbao_pkcs11_hsm` (leaf, révision 1) : Coffre OpenBao HA Raft avec Auto-Unseal PKCS#11 sur HSM
- `urn:archinex:ontology:security:zone:user_plane` (leaf, révision 1) : Zone Usager Telecom 5G UPF (Haut Débit DPDK/SR-IOV)
- `urn:archinex:ontology:telecom:core:slicing_5qi_sst_isolation` (leaf, révision 1) : Isolement Strict des Tranches 5G par S-NSSAI, DNN & Profils QoS 5QI (core-network)

## Triplets

Identifiants en collision avec le Hub (contenu différent), renumérotés :
- `tr-002` → `tr-mig-001`
- `tr-003` → `tr-mig-002`
- `tr-004` → `tr-mig-003`
- `tr-007` → `tr-mig-004`
- `tr-009` → `tr-mig-005`
- `tr-010` → `tr-mig-006`
- `tr-011` → `tr-mig-007`
- `tr-012` → `tr-mig-008`
- `tr-013` → `tr-mig-009`

Triplets `satisfies_clause` générés : 37 (justification « reprise de la fixture, à rédiger »).

Triplets de la source écartés :
- `tr-001` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-005` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-006` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-006b` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-008` : marque de projet dans le sujet ou l'objet
- `tr-008` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-008b` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-009` : marque de projet dans le sujet ou l'objet
- `tr-013b` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-014` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-015` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-016` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-020` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-021` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-022` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-030` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-031` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-032` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-040` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-041` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-042` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-050` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-053` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-060` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-061` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-062` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-063` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-064` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-065` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-066` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-067` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-068` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-069` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-070` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-071` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-072` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-073` : triplet déjà présent (même sujet, prédicat, objet)
- `tr-074` : triplet déjà présent (même sujet, prédicat, objet)

