"""Enrich data/snapshots/ontology_export.json with governed_by_clauses and satisfies_clause triplets (Issue #184)."""

import json
from pathlib import Path

import jsonschema

from pipelines.ontology.catalog import build_clause_index, validate_clause_leaf_integrity

EXPORT_PATH = Path("data/snapshots/ontology_export.json")
SCHEMA_PATH = Path("schemas/ontology_catalog.schema.json")

clauses_map = {
    "urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256": [
        "urn:archinex:kb:clause:nis2:art21_crypto",
        "urn:archinex:kb:clause:3gpp:ts33_501_sec_s6a",
    ],
    "urn:archinex:ontology:security:crypto:luks2_kms_hsm": [
        "urn:archinex:kb:clause:nis2:art21_crypto",
        "urn:archinex:kb:clause:iso27001:a10_cryptography",
    ],
    "urn:archinex:ontology:security:iam:oidc_fido2_rbac": [
        "urn:archinex:kb:clause:nis2:art21_mfa",
        "urn:archinex:kb:clause:iso27001:a9_access_control",
    ],
    "urn:archinex:ontology:security:pki:cert_manager_spiffe_mtls": [
        "urn:archinex:kb:clause:3gpp:ts33_501_sba_security",
        "urn:archinex:kb:clause:nis2:art21_zerotrust",
    ],
    "urn:archinex:ontology:security:zone:oam": [
        "urn:archinex:kb:clause:3gpp:ts33_501_oam_segregation",
        "urn:archinex:kb:clause:nis2:art21_network_segregation",
    ],
    "urn:archinex:ontology:observability:soc:siem_syslog_tls_nis2": [
        "urn:archinex:kb:clause:nis2:art21_incident_handling",
        "urn:archinex:kb:clause:iso27001:a12_logging_monitoring",
    ],
    "urn:archinex:ontology:storage:backup:s3_object_lock_worm": [
        "urn:archinex:kb:clause:nis2:art21_backup_continuity",
        "urn:archinex:kb:clause:iso27001:a12_backup",
    ],
    "urn:archinex:ontology:resilience:drp:active_active_stretched": [
        "urn:archinex:kb:clause:nis2:art21_business_continuity",
    ],
    "urn:archinex:ontology:security:secrets:vault_dynamic_leases": [
        "urn:archinex:kb:clause:nis2:art21_access_control",
    ],
    "urn:archinex:ontology:telecom:network:oob": [
        "urn:archinex:kb:clause:3gpp:ts33_501_oam_segregation",
    ],
}

new_triplets = [
    {
        "id": "tr-sc-001",
        "subject": "urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:nis2:art21_crypto",
        "rationale": "Chiffrement IPsec IKEv2 AES-256-GCM conforme aux exigences de cryptographie forte de NIS2 Article 21.",
    },
    {
        "id": "tr-sc-002",
        "subject": "urn:archinex:ontology:security:crypto:ipsec_ikev2_aes256",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:3gpp:ts33_501_sec_s6a",
        "rationale": "Protection et intégrité cryptographique des interfaces d'interconnexion 5G selon 3GPP TS 33.501.",
    },
    {
        "id": "tr-sc-003",
        "subject": "urn:archinex:ontology:security:crypto:luks2_kms_hsm",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:nis2:art21_crypto",
        "rationale": "Chiffrement systématique au repos par LUKS2 avec gestion centralisée des clés via KMS/HSM conforme NIS2 Art. 21.",
    },
    {
        "id": "tr-sc-004",
        "subject": "urn:archinex:ontology:security:crypto:luks2_kms_hsm",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:iso27001:a10_cryptography",
        "rationale": "Contrôle cryptographique des données stockées conforme à l'exigence ISO/IEC 27001 mesure A.10.1.",
    },
    {
        "id": "tr-sc-005",
        "subject": "urn:archinex:ontology:security:iam:oidc_fido2_rbac",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:nis2:art21_mfa",
        "rationale": "Authentification multifacteur (MFA matériel FIDO2) et contrôle d'accès continu selon NIS2 Art. 21.",
    },
    {
        "id": "tr-sc-006",
        "subject": "urn:archinex:ontology:security:iam:oidc_fido2_rbac",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:iso27001:a9_access_control",
        "rationale": "Attribution des privilèges selon le principe du moindre privilège (RBAC) conforme ISO 27001 mesure A.9.",
    },
    {
        "id": "tr-sc-007",
        "subject": "urn:archinex:ontology:security:pki:cert_manager_spiffe_mtls",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:3gpp:ts33_501_sba_security",
        "rationale": "Authentification mutuelle mTLS et validation d'identité des Network Functions 5G SBA (3GPP TS 33.501 clause 6.7).",
    },
    {
        "id": "tr-sc-008",
        "subject": "urn:archinex:ontology:security:pki:cert_manager_spiffe_mtls",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:nis2:art21_zerotrust",
        "rationale": "Chiffrement et authentification cryptographique de bout en bout des flux inter-services conforme NIS2 Art. 21.",
    },
    {
        "id": "tr-sc-009",
        "subject": "urn:archinex:ontology:security:zone:oam",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:3gpp:ts33_501_oam_segregation",
        "rationale": "Cloisonnement strict et étanche des flux d'exploitation et de management selon 3GPP TS 33.501.",
    },
    {
        "id": "tr-sc-010",
        "subject": "urn:archinex:ontology:security:zone:oam",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:nis2:art21_network_segregation",
        "rationale": "Ségrégation réseau et zonage de sécurité des accès d'administration conforme NIS2 Art. 21.",
    },
    {
        "id": "tr-sc-011",
        "subject": "urn:archinex:ontology:observability:soc:siem_syslog_tls_nis2",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:nis2:art21_incident_handling",
        "rationale": "Collecte centralisée, horodatage certifié et rétention 365 jours pour détection et réponse aux incidents NIS2 Art. 21.",
    },
    {
        "id": "tr-sc-012",
        "subject": "urn:archinex:ontology:observability:soc:siem_syslog_tls_nis2",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:iso27001:a12_logging_monitoring",
        "rationale": "Journalisation immuable et surveillance continue des événements conforme ISO 27001 mesure A.12.4.",
    },
    {
        "id": "tr-sc-013",
        "subject": "urn:archinex:ontology:storage:backup:s3_object_lock_worm",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:nis2:art21_backup_continuity",
        "rationale": "Sauvegardes immuables protégées contre l'altération et le chiffrement malveillant selon NIS2 Art. 21.",
    },
    {
        "id": "tr-sc-014",
        "subject": "urn:archinex:ontology:storage:backup:s3_object_lock_worm",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:iso27001:a12_backup",
        "rationale": "Sauvegarde et restauration vérifiée des informations critiques conforme ISO 27001 mesure A.12.3.",
    },
    {
        "id": "tr-sc-015",
        "subject": "urn:archinex:ontology:resilience:drp:active_active_stretched",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:nis2:art21_business_continuity",
        "rationale": "Maintien de la continuité d'activité et redondance multi-sites en cas d'incident majeur selon NIS2 Art. 21.",
    },
    {
        "id": "tr-sc-016",
        "subject": "urn:archinex:ontology:security:secrets:vault_dynamic_leases",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:nis2:art21_access_control",
        "rationale": "Élimination des secrets statiques par rotation dynamique et baux éphémères conforme NIS2 Art. 21.",
    },
    {
        "id": "tr-sc-017",
        "subject": "urn:archinex:ontology:telecom:network:oob",
        "predicate": "satisfies_clause",
        "object": "urn:archinex:kb:clause:3gpp:ts33_501_oam_segregation",
        "rationale": "Isolation physique et logique des interfaces de management BMC/iLO selon 3GPP TS 33.501.",
    },
]


def main():
    catalog = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))
    entities = catalog["entities"]
    triplets = catalog["triplets"]

    for urn, c_list in clauses_map.items():
        if urn in entities:
            entities[urn]["governed_by_clauses"] = c_list

    # Avoid duplicate addition if run multiple times
    existing_ids = {t["id"] for t in triplets}
    combined_triplets = list(triplets)
    for t in new_triplets:
        if t["id"] not in existing_ids:
            combined_triplets.append(t)

    catalog["triplets"] = combined_triplets
    catalog["clause_index"] = build_clause_index(entities, combined_triplets)

    errors = validate_clause_leaf_integrity(catalog)
    if errors:
        raise ValueError(f"Integrity errors found: {errors}")

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=catalog, schema=schema)

    EXPORT_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Successfully enriched {EXPORT_PATH} with {len(new_triplets)} satisfies_clause triplets!")


if __name__ == "__main__":
    main()
