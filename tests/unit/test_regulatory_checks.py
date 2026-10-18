"""Unit tests — draft check clauses of the regulatory controls (NIS2 Art. 21(2), GDPR), judged deterministically.

The clauses are read from the control files of data/kb/controls; the judge runs on an in-memory index
of those controls with the glossary synonyms (no graph). Each clause must flag a non-compliant option
(``violates``) and leave a compliant one ``supports`` or ``unassessed``.
"""

from pathlib import Path

import pytest

from pipelines.doctrine.checks import parse_checks, validate_clause
from pipelines.doctrine.index import DoctrineEntry, DoctrineIndex, load_vocabulary, read_frontmatter
from pipelines.doctrine.judge import check_option

ROOT = Path(__file__).parent.parent.parent
KB = ROOT / "data" / "kb"
CONTROLS = {
    "NIS2-ART21-2C": "NIS2", "NIS2-ART21-2D": "NIS2", "NIS2-ART21-2E": "NIS2", "NIS2-ART21-2H": "NIS2",
    "NIS2-ART21-2J": "NIS2", "RGPD-REQ-PRIVACY-01": "RGPD", "RGPD-REQ-BREACH-02": "RGPD",
}


def _path(cid: str) -> Path:
    return KB / "controls" / CONTROLS[cid] / f"{cid}.md"


def _no_graph(query, params):
    raise RuntimeError("no graph in unit tests")


@pytest.fixture(scope="module")
def index() -> DoctrineIndex:
    entries = []
    for cid, fw in CONTROLS.items():
        fm = read_frontmatter(_path(cid))
        entries.append(DoctrineEntry(
            id=cid, type="control", title=str(fm["title"]), status=str(fm["status"]), confidence="verified",
            domain=list(fm.get("domain") or []), phase=[], source_ref=str(_path(cid)), body="", framework=fw,
            checks=parse_checks(fm.get("checks"), fm.get("checks_status")),
        ))
    return DoctrineIndex(entries=entries, vocabulary=load_vocabulary(_no_graph, KB))


@pytest.mark.parametrize("cid", sorted(CONTROLS))
def test_clauses_are_valid_drafts_on_active_controls(cid):
    text = _path(cid).read_text(encoding="utf-8")
    fm = read_frontmatter(_path(cid))
    assert fm["status"] == "active" and fm["checks_status"] in ("draft", "validated")
    if fm["checks_status"] == "draft":
        assert "proposed by the coding agent" in text and "NOT validated" in text
    assert fm["checks"], "at least one clause"
    for clause in fm["checks"]:
        assert validate_clause(clause) == [], clause["id"]
        assert clause["id"].startswith(f"{cid}-C") and clause["message"]
    assert len(parse_checks(fm["checks"], fm["checks_status"])) == len(fm["checks"])


def _verdicts(index, title, description=""):
    res = check_option(index, {"title": title, "description": description})
    return {v["check_id"]: v["verdict"] for v in res["verdicts"] if v["check_id"]}


# (clause, non-compliant option, compliant option). The compliant option either satisfies the
# expectation (supports) or does not trigger the clause at all.
CASES = [
    ("NIS2-ART21-2C-C1",
     "Single data centre hosting, no backup of the application database",
     "Nightly backups replicated to a second site with immutable copies"),
    ("NIS2-ART21-2C-C1",
     "Hébergement mono-site sans sauvegarde des bases",
     "Sauvegardes quotidiennes chiffrées, copie hors ligne sur un site secondaire"),
    ("NIS2-ART21-2C-C2",
     "Backup solution writing to a NAS in the production rack",
     "Backup solution with immutable (WORM) copies stored off-site, restore tests every quarter"),
    ("NIS2-ART21-2C-C2",
     "Plan de reprise reposant sur une baie de stockage unique",
     "Plan de reprise avec un site secondaire, RTO de 4 heures et RPO de 15 minutes"),
    ("NIS2-ART21-2D-C1",
     "Operations outsourced to a managed service provider selected on price",
     "Operations outsourced to a managed service provider, ISO 27001 certified, with a right to audit"),
    ("NIS2-ART21-2D-C1",
     "Infogérance confiée à un prestataire externe offshore",
     "Infogérance par un prestataire qualifié SecNumCloud avec clauses de sécurité et droit d'audit"),
    ("NIS2-ART21-2E-C1",
     "Keep the legacy billing server on an end-of-life operating system to save licence costs",
     "Migrate the billing server to a supported LTS operating system with monthly patching"),
    ("NIS2-ART21-2E-C1",
     "Conserver l'application sur une version hors support de l'éditeur",
     "Montée de version vers une version maintenue par l'éditeur"),
    ("NIS2-ART21-2E-C2",
     "Custom development of the citizen portal, delivered by the integrator",
     "Custom development of the portal with SAST, dependency scanning and a penetration test before go-live"),
    ("NIS2-ART21-2H-C1",
     "Sensor data transmitted unencrypted over the public network for simplicity",
     "Sensor data protected with TLS 1.3 and mutual authentication"),
    ("NIS2-ART21-2H-C1",
     "Les mots de passe en clair sont stockés dans la base de configuration",
     "Les secrets sont stockés dans un coffre-fort avec chiffrement AES-256"),
    ("NIS2-ART21-2H-C2",
     "Central database of personal data of patients on a shared SQL server",
     "Central database of personal data, encrypted at rest with keys held in an HSM"),
    ("NIS2-ART21-2J-C1",
     "Administrators log in to the hypervisors with a shared admin account",
     "Administrators use personal named accounts behind a bastion with FIDO2 keys"),
    ("NIS2-ART21-2J-C2",
     "Remote access for the vendor support team through an SSH jump host on the internet",
     "Remote access for vendor support through a bastion with multi-factor authentication and session recording"),
    ("NIS2-ART21-2J-C2",
     "Accès distant des administrateurs par VPN nomade avec identifiant et mot de passe",
     "Accès distant des administrateurs par VPN nomade avec authentification multifacteur"),
    ("RGPD-REQ-PRIVACY-01-C1",
     "Refresh the test environment with a copy of production data in test every week",
     "Test environment fed with synthetic data and pseudonymised extracts"),
    ("RGPD-REQ-PRIVACY-01-C1",
     "Conservation illimitée des enregistrements d'appels",
     "Conservation des enregistrements d'appels limitée à 6 mois puis purge automatique"),
    ("RGPD-REQ-BREACH-02-C1",
     "Application logs: no logging on the citizen database to improve performance",
     "Security logs of the citizen database shipped to the SIEM and kept 12 months"),
    ("RGPD-REQ-BREACH-02-C2",
     "Data breach handling left to the hosting provider",
     "Data breach handling: SOC qualification, DPO alerted, notification to the CNPD within 72 hours"),
]


@pytest.mark.parametrize("clause, bad, good", CASES, ids=[f"{c[0]}-{i}" for i, c in enumerate(CASES)])
def test_clause_flags_the_non_compliant_option_only(index, clause, bad, good):
    assert _verdicts(index, bad).get(clause) == "violates"
    assert _verdicts(index, good).get(clause) in (None, "supports")


def test_negated_phrases_do_not_trigger_forbidding_clauses(index):
    verdicts = _verdicts(index, "Hardening", "There is no shared admin account and no data is stored unencrypted.")
    assert "violates" not in verdicts.values()


@pytest.mark.parametrize("option", [
    "Backup link between the two core routers over a microwave path",  # telecom redundancy, not data backup
    "Site-to-site VPN between the data centres",  # network link, not user remote access
    "En clair, la solution repose sur deux datacenters actifs",  # French idiom "en clair"
    "The vendor supplies the radio access network equipment",
])
def test_ordinary_options_are_not_flagged(index, option):
    assert "violates" not in _verdicts(index, option).values()


def test_a_violation_cites_the_control_and_its_status(index):
    res = check_option(index, {"title": "Administration with a shared admin account"}, frameworks=["NIS2"])
    hit = next(v for v in res["verdicts"] if v["check_id"] == "NIS2-ART21-2J-C1")
    assert hit["typed_id"] == "control:NIS2-ART21-2J" and hit["check_status"] in ("draft", "validated")
    assert hit["matched_terms"] == ["shared admin account"] and "21(2)(j)" in hit["message"]


def test_negated_expectation_violates_requires_clause(index):
    # Issue #110: « sans évaluation de sécurité du fournisseur » must violate NIS2-ART21-2D-C1 and report negated_terms
    res_fr = check_option(
        index,
        {
            "title": "Sous-traitance de l'exploitation",
            "description": "le RUN est confié à un prestataire sans évaluation de sécurité du fournisseur",
        },
        frameworks=["NIS2"],
    )
    hit_fr = next(v for v in res_fr["verdicts"] if v["check_id"] == "NIS2-ART21-2D-C1")
    assert hit_fr["verdict"] == "violates"
    assert "sous-traitance" in hit_fr["matched_terms"]
    assert "evaluation de securite du fournisseur" in hit_fr["negated_terms"]

    # English variant with 'without'
    res_en = check_option(
        index,
        {
            "title": "Operations outsourcing",
            "description": "the RUN is entrusted to a managed service provider without supplier assessment",
        },
        frameworks=["NIS2"],
    )
    hit_en = next(v for v in res_en["verdicts"] if v["check_id"] == "NIS2-ART21-2D-C1")
    assert hit_en["verdict"] == "violates"
    assert "managed service provider" in hit_en["matched_terms"]
    assert "supplier assessment" in hit_en["negated_terms"]

