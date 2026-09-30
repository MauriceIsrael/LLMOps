"""SQL repository parity with the file repository, owners registry and migration."""

import shutil
from pathlib import Path

import pytest
import yaml

from pipelines.governance.migrate import migrate_governance
from pipelines.governance.registry import load_registry_from_db
from pipelines.governance.store import dispose_engines
from pipelines.kb_candidates.model import CandidateNotFoundError
from pipelines.kb_candidates.owners import load_owners
from pipelines.kb_candidates.repository import (
    FileCandidateRepository,
    SqlCandidateRepository,
    get_repository,
)

ROOT = Path(__file__).parent.parent.parent


@pytest.fixture
def url(tmp_path, monkeypatch):
    dispose_engines()
    value = f"sqlite:///{tmp_path / 'gov.db'}"
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", value)
    yield value
    dispose_engines()


def _cand(cid, status="in_review", domain=("automation",), system="archinex"):
    return {"id": cid, "status": status, "domain": list(domain), "source": {"system": system, "engagement": "e1"},
            "assigned_owner": "@a", "history": []}


def test_sql_repository_matches_file_repository(tmp_path, url):
    sql, files = SqlCandidateRepository(), FileCandidateRepository(tmp_path / "f")
    for repo in (sql, files):
        repo.save(_cand("CAND-20260101-0001"))
        repo.save(_cand("CAND-20260101-0002", status="rejected", domain=("network/ip",), system="cli-ingestion"))
        updated = _cand("CAND-20260101-0001", status="accepted")
        repo.save(updated)  # update in place
    for filters in ({}, {"status": "accepted"}, {"source": "cli-ingestion"}, {"domain": "network"}, {"engagement": "e1"}):
        assert [c["id"] for c in sql.find(**filters)] == [c["id"] for c in files.find(**filters)], filters
    assert sql.get("CAND-20260101-0001")["status"] == "accepted"
    with pytest.raises(CandidateNotFoundError):
        sql.get("CAND-20260101-0009")
    with pytest.raises(CandidateNotFoundError):
        sql.get("../etc/passwd")


def test_sql_ids_are_sequential_per_day(url):
    repo = SqlCandidateRepository()
    ids = [repo.next_id() for _ in range(3)]
    assert [i[-4:] for i in ids] == ["0001", "0002", "0003"] and len({i[:-5] for i in ids}) == 1


def test_backend_selection(monkeypatch, url):
    monkeypatch.setenv("CANDIDATES_BACKEND", "sql")
    assert isinstance(get_repository(), SqlCandidateRepository)
    monkeypatch.setenv("CANDIDATES_BACKEND", "gcs")
    with pytest.raises(ValueError):
        get_repository()


def test_migration_is_idempotent_and_seeds_owners_once(tmp_path, url):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    files = FileCandidateRepository(tmp_path / "cands")
    files.save(_cand("CAND-20260101-0001"))
    first = migrate_governance(kb, tmp_path / "cands")
    assert first == {"candidates_imported": 1, "candidates_skipped": 0, "owners_seeded": True}
    assert migrate_governance(kb, tmp_path / "cands") == {
        "candidates_imported": 0, "candidates_skipped": 1, "owners_seeded": False}

    # The database is now the authority: editing owners.yaml changes nothing until --force-owners.
    data = yaml.safe_load((kb / "owners.yaml").read_text())
    data["owners"]["@ciso-office"]["email"] = "new@example.org"
    (kb / "owners.yaml").write_text(yaml.safe_dump(data))
    assert load_owners(kb).by_email("new@example.org") is None
    migrate_governance(kb, tmp_path / "cands", force_owners=True)
    assert load_owners(kb).by_email("new@example.org").handle == "@ciso-office"
    reg = load_registry_from_db()
    assert reg is not None and reg.default_owner == "@maintainers" and len(reg.owners) >= 20


def test_can_review_rules():
    from pipelines.kb_candidates.owners import Owner, OwnersRegistry

    reg = OwnersRegistry(
        owners={"@a": Owner("@a"), "@b": Owner("@b"), "@m": Owner("@m", roles=("kb:maintain",)), "@d": Owner("@d")},
        domains={"network": "@a", "network/ip": "@b"}, default_owner="@d")
    assert reg.can_review("@a", ["network/dns"])          # inherits the parent's owner
    assert reg.can_review("@a", ["network/ip"])           # the owner of a parent domain may review too
    assert reg.can_review("@b", ["network/ip"])
    assert not reg.can_review("@b", ["network/dns"])      # but not the other way round
    assert reg.can_review("@m", ["anything"]) and reg.can_review("@d", ["anything"])
    assert not reg.can_review("@unknown", ["network"])
    assert reg.owned_domains("@a") == ["network"]


def test_delegated_owner_is_not_notified_on_external_channels(monkeypatch):
    import mcp_server.core.notifier as notifier

    def boom(*args, **kwargs):
        raise AssertionError("no external channel expected")

    monkeypatch.setattr(notifier, "_post", boom)
    monkeypatch.setattr(notifier, "_send_email", boom)
    owner = {"handle": "@a", "email": "a@example.org", "discord_webhook": "https://example.invalid", "ntfy_topic": "t",
             "delegated": True}
    assert notifier.notify_owner(owner, "in_review", {"id": "CAND-20260101-0001", "title": "t"}) == ["log", "archinex"]
